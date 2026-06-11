"""Bundle Routes — API endpoints for service bundles and zone-based pricing.

Prefix: /api/v1/service-bundles
"""

from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from uuid import UUID
from loguru import logger
import csv
import io
import re

from app.database.connection import get_database
from app.modules.auth.middleware.auth_middleware import get_current_user
from app.modules.users.models.user import UserResponse
from app.modules.permissions.middleware.permission_middleware import permission_required
from app.modules.translations.middleware.language_middleware import detect_language
from app.modules.fiscal_services.models.bundles import (
    CommerceZoneResponse,
    ServiceBundleCreate,
    ServiceBundleUpdate,
    ServiceBundleResponse,
    ServiceBundlePublicResponse,
    BundleItemCreate,
    BundleItemResponse,
    BundleWithItemsResponse,
    BundleListResponse,
    BundleDocumentItem,
    PricingMatrixResponse,
    SimulatorResponse,
    FeeGroupItems,
    ZoneTotalItem,
    CopyZonePricesRequest,
    BulkImportRequest,
    ReorderItemRequest,
)
from app.modules.fiscal_services.repositories.bundle_repository import BundleRepository
from app.modules.fiscal_services.services.bundle_service import BundleService

router = APIRouter(prefix="/service-bundles", tags=["Service Bundles"])


def _escape_ilike(value: str) -> str:
    """Escape ILIKE wildcard characters in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ============================================================
# IMPORTANT: Static paths MUST be before /{bundle_id} to avoid
# FastAPI matching "zones", "admin" etc. as UUID → 422 error.
# ============================================================

# ============================================================
# Public Endpoints
# ============================================================

@router.get("/zones", response_model=List[CommerceZoneResponse])
async def list_zones(db=Depends(get_database)):
    """List all commerce zones (12 zones A1→D3)."""
    zones = await BundleService.list_zones(db)
    return [CommerceZoneResponse(**z) for z in zones]


@router.get("/", response_model=BundleListResponse)
async def list_bundles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100),
    commerce_type: Optional[str] = Query(None, max_length=100),
    is_active: Optional[bool] = Query(None),
    db=Depends(get_database),
):
    """List service bundles with pagination and filters."""
    bundles, total = await BundleService.list_bundles(
        db, is_active=is_active, search=search,
        commerce_type=commerce_type, page=page, page_size=page_size,
    )
    return BundleListResponse(
        items=[ServiceBundleResponse(**b) for b in bundles],
        total=total,
        page=page,
        page_size=page_size,
    )


FEE_TYPE_LABELS = {
    "tesoro": {"es": "TESORO PÚBLICO", "fr": "TRÉSOR PUBLIC", "en": "PUBLIC TREASURY"},
    "municipal": {"es": "AYUNTAMIENTO", "fr": "MUNICIPALITÉ", "en": "MUNICIPALITY"},
    "chamber": {"es": "CÁMARA DE COMERCIO", "fr": "CHAMBRE DE COMMERCE", "en": "CHAMBER OF COMMERCE"},
}


@router.get("/simulator", response_model=SimulatorResponse)
async def simulate_bundle_pricing(
    request: Request,
    commerce_type: str = Query(..., max_length=100, description="Commerce type (e.g. bar_restaurante)"),
    zone_code: str = Query(..., max_length=5, description="Zone code (e.g. A1)"),
    db=Depends(get_database),
):
    """Public simulator: commerce_type + zone_code → complete pricing in 1 call.

    Returns bundle info, items grouped by fee_type, totals, documents,
    and installment preview. Used by the /licencias-comerciales public page.
    Respects Accept-Language header for service/document name translations.
    """
    language = detect_language(request).value
    result = await BundleService.simulate(db, commerce_type, zone_code, language=language)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Transform fee_groups dict → list of FeeGroupItems for clean response
    fee_groups_list = []
    for ft in ["tesoro", "municipal", "chamber"]:
        items_raw = result["fee_groups"].get(ft, [])
        if not items_raw:
            continue
        fee_groups_list.append(FeeGroupItems(
            fee_type=ft,
            label_es=FEE_TYPE_LABELS.get(ft, {}).get(language, ft.upper()),
            items=[BundleItemResponse(**i) for i in items_raw],
            subtotal=result["fee_totals"].get(ft, "0"),
        ))

    return SimulatorResponse(
        bundle=ServiceBundlePublicResponse(**result["bundle"]),
        zone=CommerceZoneResponse(**result["zone"]),
        fee_groups=fee_groups_list,
        grand_total=result["grand_total"],
        documents=[BundleDocumentItem(**d) for d in result["documents"]],
        installment_preview=result.get("installment_preview"),
        currency=result["currency"],
    )


@router.get("/by-service/{fiscal_service_id}")
async def get_bundles_for_service(
    fiscal_service_id: int,
    db=Depends(get_database),
):
    """Get bundles that include a specific fiscal service.

    Used by /services/{id} detail page to show "Included in bundle X" badge.
    Returns minimal info: bundle id, name, commerce_type, bundle_code.
    """
    rows = await db.fetch("""
        SELECT DISTINCT sb.id, sb.bundle_code, sb.name_es, sb.commerce_type
        FROM service_bundle_items sbi
        JOIN service_bundles sb ON sb.id = sbi.bundle_id
        WHERE sbi.fiscal_service_id = $1
          AND sbi.is_active = true
          AND sb.is_active = true
        ORDER BY sb.name_es
    """, fiscal_service_id)
    return [
        {
            "id": str(r["id"]),
            "bundle_code": r["bundle_code"],
            "name_es": r["name_es"],
            "commerce_type": r["commerce_type"],
        }
        for r in rows
    ]


@router.get("/commerce-types")
async def list_commerce_types(db=Depends(get_database)):
    """List distinct commerce types with bundle names (for public selector). Cached 1h."""
    types = await BundleService.list_commerce_types(db)
    return [
        {
            "commerce_type": r["commerce_type"],
            "name_es": r["name_es"],
            "bundle_code": r["bundle_code"],
            "id": str(r["id"]),
            "description_es": r.get("description_es"),
            "installment_eligible": r["installment_eligible"],
        }
        for r in types
    ]


# ============================================================
# Admin Endpoints — BEFORE /{bundle_id} to avoid route conflict
# ============================================================

def _group_matrix_items(matrix_items: List, zones: List) -> Dict:
    """Group matrix items by (fee_type, fiscal_service_id) with zone amounts.

    Shared between CSV and XLSX exports. Returns dict keyed by (fee_type, service_id).
    """
    zone_id_map = {str(z["id"]): z["zone_code"] for z in zones}
    grouped: Dict = {}
    for item in matrix_items:
        ft = item.get("fee_type", "tesoro")
        key = (ft, item["fiscal_service_id"])
        if key not in grouped:
            grouped[key] = {
                "fee_type": ft,
                "service_code": item.get("service_code", ""),
                "service_name": item.get("service_name", ""),
                "ministry_name": item.get("ministry_name", ""),
                "is_fixed": item.get("is_fixed_across_zones", False),
                "zones": {},
            }
        zc = zone_id_map.get(str(item["zone_id"]), "?")
        grouped[key]["zones"][zc] = item["amount"]
    return grouped


@router.get("/admin/export/csv")
async def export_bundle_csv(
    bundle_id: UUID = Query(...),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Export pricing matrix as CSV for a bundle."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    matrix = await BundleService.get_pricing_matrix(db, bundle_id)
    zones = await BundleService.list_zones(db)
    zone_codes = [z["zone_code"] for z in zones]
    grouped = _group_matrix_items(matrix["items"], zones)

    output = io.StringIO()
    writer = csv.writer(output)

    header = ["Código Servicio", "Servicio", "Ministerio", "Tipo"] + zone_codes + ["Fijo"]
    writer.writerow(header)

    for svc in grouped.values():
        row = [svc["service_code"], svc["service_name"], svc["ministry_name"], svc["fee_type"]]
        for zc in zone_codes:
            row.append(str(svc["zones"].get(zc, 0)))
        row.append("Sí" if svc["is_fixed"] else "No")
        writer.writerow(row)

    # Totals row
    totals_row = ["", "TOTAL GENERAL", "", ""]
    zone_total_map = {
        str(zt.get("id", zt.get("zone_code", ""))): zt["total_amount"]
        for zt in matrix["zone_totals"]
    }
    for z in zones:
        totals_row.append(str(zone_total_map.get(str(z["id"]), 0)))
    totals_row.append("")
    writer.writerow(totals_row)

    output.seek(0)
    filename = f"bundle_{bundle['bundle_code']}_matrix.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/export/xlsx")
async def export_bundle_xlsx(
    bundle_id: UUID = Query(...),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Export pricing matrix as professional Excel (.xlsx) with fee_type sections."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        raise HTTPException(status_code=503, detail="openpyxl not installed")

    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    matrix = await BundleService.get_pricing_matrix(db, bundle_id)
    zones = await BundleService.list_zones(db)
    zone_codes = [z["zone_code"] for z in zones]
    fee_type_services = _group_matrix_items(matrix["items"], zones)

    # Styles
    wb = Workbook()
    ws = wb.active
    ws.title = "Matrice Tarifaire"

    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill("solid", fgColor="2563EB")
    section_fills = {
        "tesoro": PatternFill("solid", fgColor="1E40AF"),
        "municipal": PatternFill("solid", fgColor="047857"),
        "chamber": PatternFill("solid", fgColor="7C3AED"),
    }
    section_labels = {
        "tesoro": "TESORO PÚBLICO",
        "municipal": "AYUNTAMIENTO",
        "chamber": "CÁMARA DE COMERCIO",
    }
    subtotal_fill = PatternFill("solid", fgColor="DBEAFE")
    grand_total_fill = PatternFill("solid", fgColor="FEF3C7")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    money_fmt = '#,##0'

    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4 + len(zone_codes))
    title_cell = ws.cell(row=1, column=1,
                         value=f"{bundle['name_es']} — {bundle.get('commerce_type', '')}")
    title_cell.font = Font(bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center")

    ws.cell(row=2, column=1, value=f"Referencia Legal: {bundle.get('legal_reference', '—')}")

    # Header row (row 4)
    row_num = 4
    headers = ["Código", "Servicio", "Ministerio"] + zone_codes + ["Fijo"]
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=ci, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Column widths (using get_column_letter for safety beyond Z)
    from openpyxl.utils import get_column_letter
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 25
    for i in range(len(zone_codes)):
        ws.column_dimensions[get_column_letter(4 + i)].width = 12
    ws.column_dimensions[get_column_letter(4 + len(zone_codes))].width = 8

    # Freeze header row so it stays visible on scroll
    ws.freeze_panes = "A5"

    row_num = 5
    grand_totals: Dict[str, Decimal] = {zc: Decimal("0") for zc in zone_codes}

    # Write sections by fee_type
    for ft in ["tesoro", "municipal", "chamber"]:
        ft_items = {k: v for k, v in fee_type_services.items() if v["fee_type"] == ft}
        if not ft_items:
            continue

        # Section header
        ws.merge_cells(start_row=row_num, start_column=1,
                        end_row=row_num, end_column=3 + len(zone_codes) + 1)
        section_cell = ws.cell(row=row_num, column=1, value=section_labels.get(ft, ft.upper()))
        section_cell.font = Font(bold=True, color="FFFFFF", size=11)
        section_cell.fill = section_fills.get(ft, header_fill)
        section_cell.alignment = Alignment(horizontal="left")
        row_num += 1

        ft_zone_totals: Dict[str, Decimal] = {zc: Decimal("0") for zc in zone_codes}

        for svc in ft_items.values():
            ws.cell(row=row_num, column=1, value=svc["service_code"]).border = thin_border
            ws.cell(row=row_num, column=2, value=svc["service_name"]).border = thin_border
            ws.cell(row=row_num, column=3, value=svc["ministry_name"]).border = thin_border
            for zi, zc in enumerate(zone_codes):
                amt = svc["zones"].get(zc, Decimal("0"))
                cell = ws.cell(row=row_num, column=4 + zi, value=amt)
                cell.number_format = money_fmt
                cell.alignment = Alignment(horizontal="right")
                cell.border = thin_border
                ft_zone_totals[zc] += amt
                grand_totals[zc] += amt
            fixed_cell = ws.cell(row=row_num, column=4 + len(zone_codes),
                                  value="Sí" if svc["is_fixed"] else "No")
            fixed_cell.alignment = Alignment(horizontal="center")
            fixed_cell.border = thin_border
            row_num += 1

        # Sub-total row
        ws.cell(row=row_num, column=1, value="").border = thin_border
        st_cell = ws.cell(row=row_num, column=2,
                           value=f"Sub-Total {section_labels.get(ft, ft)}")
        st_cell.font = Font(bold=True)
        st_cell.fill = subtotal_fill
        st_cell.border = thin_border
        ws.cell(row=row_num, column=3, value="").fill = subtotal_fill
        ws.cell(row=row_num, column=3).border = thin_border
        for zi, zc in enumerate(zone_codes):
            cell = ws.cell(row=row_num, column=4 + zi, value=ft_zone_totals[zc])
            cell.number_format = money_fmt
            cell.font = Font(bold=True)
            cell.fill = subtotal_fill
            cell.alignment = Alignment(horizontal="right")
            cell.border = thin_border
        ws.cell(row=row_num, column=4 + len(zone_codes), value="").fill = subtotal_fill
        ws.cell(row=row_num, column=4 + len(zone_codes)).border = thin_border
        row_num += 1

    # Grand total row
    ws.cell(row=row_num, column=1, value="").border = thin_border
    gt_cell = ws.cell(row=row_num, column=2, value="TOTAL GENERAL")
    gt_cell.font = Font(bold=True, size=11)
    gt_cell.fill = grand_total_fill
    gt_cell.border = thin_border
    ws.cell(row=row_num, column=3, value="").fill = grand_total_fill
    ws.cell(row=row_num, column=3).border = thin_border
    for zi, zc in enumerate(zone_codes):
        cell = ws.cell(row=row_num, column=4 + zi, value=grand_totals[zc])
        cell.number_format = money_fmt
        cell.font = Font(bold=True, size=11)
        cell.fill = grand_total_fill
        cell.alignment = Alignment(horizontal="right")
        cell.border = thin_border
    ws.cell(row=row_num, column=4 + len(zone_codes), value="").fill = grand_total_fill
    ws.cell(row=row_num, column=4 + len(zone_codes)).border = thin_border

    # Write to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"bundle_{bundle['bundle_code']}_matrix.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/search-services")
async def search_fiscal_services(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(15, ge=1, le=50),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Search fiscal services for bundle item picker (autocomplete).

    Returns id, service_code, name_es, ministry chain — used by
    the admin UI to add items without knowing internal IDs.
    """
    rows = await db.fetch("""
        SELECT fs.id, fs.service_code, fs.name_es,
               m.id as ministry_id, m.name_es as ministry_name
        FROM fiscal_services fs
        LEFT JOIN categories c ON fs.category_id = c.id
        LEFT JOIN sectors s ON c.sector_id = s.id
        LEFT JOIN ministries m ON s.ministry_id = m.id
        WHERE fs.status = 'active'
          AND (fs.service_code ILIKE $1 OR fs.name_es ILIKE $1)
        ORDER BY fs.service_code
        LIMIT $2
    """, f"%{_escape_ilike(q)}%", limit)
    return [
        {
            "id": r["id"],
            "service_code": r["service_code"],
            "name_es": r["name_es"],
            "ministry_id": r["ministry_id"],
            "ministry_name": r["ministry_name"],
        }
        for r in rows
    ]


@router.get("/admin/stats")
async def get_bundle_stats(
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.view_bundles")),
):
    """Get aggregate stats: total bundles, zones, items."""
    row = await db.fetchrow("""
        SELECT
            (SELECT COUNT(*) FROM service_bundles WHERE is_active = true) as bundles,
            (SELECT COUNT(*) FROM commerce_zones) as zones,
            (SELECT COUNT(*) FROM service_bundle_items WHERE is_active = true) as items
    """)
    return {"bundles": row["bundles"], "zones": row["zones"], "items": row["items"]}


@router.post("/admin/bundles", response_model=ServiceBundleResponse, status_code=201)
async def create_bundle(
    data: ServiceBundleCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Create a new service bundle."""
    bundle = await BundleService.create_bundle(
        db, data.model_dump(), user_id=UUID(current_user.id)
    )
    return ServiceBundleResponse(**bundle)


@router.put("/admin/bundles/{bundle_id}", response_model=ServiceBundleResponse)
async def update_bundle(
    bundle_id: UUID,
    data: ServiceBundleUpdate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Update bundle metadata and installment config."""
    bundle = await BundleService.update_bundle(
        db, bundle_id, data.model_dump(exclude_unset=True),
        user_id=UUID(current_user.id),
    )
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return ServiceBundleResponse(**bundle)


@router.delete("/admin/bundles/{bundle_id}", status_code=204)
async def delete_bundle(
    bundle_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Soft delete a bundle (set is_active=false)."""
    success = await BundleService.delete_bundle(db, bundle_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bundle not found")


@router.post("/admin/bundles/{bundle_id}/items", response_model=Dict)
async def upsert_bundle_item(
    bundle_id: UUID,
    data: BundleItemCreate,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Add or update a bundle item (upsert on bundle+service+zone).

    ministry_id is auto-resolved from fiscal_service's category→sector→ministry
    chain if not provided explicitly.
    """
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    item_data = data.model_dump()

    # ministry_id is REQUIRED — per PDF decree, payment recipient ministry
    # differs from the FK chain (category→sector→ministry) for bundle items.
    # NEVER auto-resolve from FK chain — it gives WRONG ministry.
    if not item_data.get("ministry_id"):
        raise HTTPException(
            status_code=422,
            detail="ministry_id is required. The payment recipient ministry must be specified explicitly."
        )

    user_id = UUID(current_user.id)
    item = await BundleService.upsert_item(db, bundle_id, item_data, user_id=user_id)
    return item


@router.delete("/admin/items/{item_id}", status_code=204)
async def delete_bundle_item(
    item_id: UUID,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Delete a bundle item."""
    user_id = UUID(current_user.id)
    success = await BundleService.delete_item(db, item_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")


@router.post("/admin/bundles/{bundle_id}/copy-zone-prices")
async def copy_zone_prices(
    bundle_id: UUID,
    data: CopyZonePricesRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Copy all item prices from one zone to another with optional multiplier."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    user_id = UUID(current_user.id)
    count = await BundleService.copy_zone_prices(
        db, bundle_id, data.source_zone_id, data.target_zone_id, data.multiplier,
        user_id=user_id,
    )
    return {"copied_items": count, "source_zone_id": str(data.source_zone_id),
            "target_zone_id": str(data.target_zone_id)}


@router.post("/admin/bundles/{bundle_id}/reorder-items")
async def reorder_bundle_items(
    bundle_id: UUID,
    data: ReorderItemRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Update display_order for items based on provided order of IDs."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    updated = 0
    async with db.transaction():
        for idx, item_id in enumerate(data.item_ids):
            result = await db.execute(
                "UPDATE service_bundle_items SET display_order = $1, updated_at = now() "
                "WHERE id = $2 AND bundle_id = $3",
                idx, item_id, bundle_id,
            )
            if result == "UPDATE 1":
                updated += 1

    await BundleService._invalidate_cache(bundle_id)
    return {"updated": updated, "total": len(data.item_ids)}


@router.post("/admin/bundles/{bundle_id}/bulk-import")
async def bulk_import_items(
    bundle_id: UUID,
    data: BulkImportRequest,
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Bulk import items from parsed Excel/PDF data.

    Resolves service_code → fiscal_service_id and zone_code → zone_id
    from the database. Skips items with unknown codes.
    """
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    # Build lookup maps from BD
    service_rows = await db.fetch(
        "SELECT id, service_code FROM fiscal_services WHERE status = 'active'"
    )
    service_map = {r["service_code"]: r["id"] for r in service_rows}

    zone_rows = await db.fetch("SELECT id, zone_code FROM commerce_zones")
    zone_map = {r["zone_code"]: r["id"] for r in zone_rows}

    # Build ministry lookup from EXISTING bundle items (same bundle, any zone)
    # This is the correct source — it uses the ministry assigned at seed/creation time.
    ministry_lookup_rows = await db.fetch("""
        SELECT DISTINCT fiscal_service_id, ministry_id
        FROM service_bundle_items
        WHERE bundle_id = $1 AND ministry_id IS NOT NULL
    """, bundle_id)
    ministry_by_service = {r["fiscal_service_id"]: r["ministry_id"] for r in ministry_lookup_rows}

    imported = 0
    skipped = []

    # Pre-validate all items before touching the database
    valid_items = []
    for item in data.items:
        fs_id = service_map.get(item.service_code)
        z_id = zone_map.get(item.zone_code)
        if not fs_id or not z_id:
            skipped.append({
                "service_code": item.service_code,
                "zone_code": item.zone_code,
                "reason": "unknown_service" if not fs_id else "unknown_zone",
            })
            continue

        # Get ministry from existing items (correct recipient per decree)
        ministry_id = ministry_by_service.get(fs_id)
        if not ministry_id and hasattr(item, "ministry_id") and item.ministry_id:
            ministry_id = item.ministry_id

        if not ministry_id:
            skipped.append({
                "service_code": item.service_code,
                "zone_code": item.zone_code,
                "reason": "no_ministry_mapping",
            })
            continue

        valid_items.append({
            "fiscal_service_id": fs_id,
            "zone_id": z_id,
            "ministry_id": ministry_id,
            "amount": item.amount,
            "fee_type": getattr(item, "fee_type", "tesoro"),
            "is_fixed_across_zones": item.is_fixed_across_zones,
        })

    # Atomic: all-or-nothing import in a single transaction
    user_id = UUID(current_user.id)
    if valid_items:
        async with db.transaction():
            await db.execute(
                "SET LOCAL app.current_user_id = $1::text", str(user_id)
            )
            for item_data in valid_items:
                await BundleRepository.upsert_item(db, bundle_id, item_data)
                imported += 1
        await BundleService._invalidate_cache(bundle_id)

    return {"imported": imported, "skipped": skipped, "total": len(data.items)}


@router.post("/admin/parse-pdf")
async def parse_pdf_for_import(
    bundle_id: UUID = Query(...),
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: UserResponse = Depends(get_current_user),
    _: None = Depends(permission_required("fiscal_service.manage_bundles")),
):
    """Parse an uploaded PDF to extract pricing tables using pdfplumber.

    Deterministic: no LLM, no hallucination, exact numbers.
    Returns items for user review before bulk-import.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")

    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=503, detail="pdfplumber not installed")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    # Get valid zone codes and service codes from BD
    zone_rows = await db.fetch("SELECT zone_code FROM commerce_zones ORDER BY display_order")
    valid_zones = {r["zone_code"] for r in zone_rows}

    service_rows = await db.fetch(
        "SELECT service_code FROM fiscal_services WHERE status = 'active'"
    )
    valid_services = {r["service_code"] for r in service_rows}

    extracted_items = []
    tables_found = 0

    try:
        pdf_bytes = io.BytesIO(content)
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    tables_found += 1

                    # Identify header row — look for zone codes (A1, B2, etc.)
                    header = [str(cell or "").strip().upper() for cell in table[0]]
                    zone_cols = {}
                    service_col = None
                    for ci, cell in enumerate(header):
                        if cell in valid_zones:
                            zone_cols[ci] = cell
                        elif any(kw in cell for kw in ["CÓDIGO", "CODIGO", "CODE", "SERVICIO"]):
                            service_col = ci

                    if not zone_cols:
                        # Try second row as header
                        if len(table) > 1:
                            header2 = [str(cell or "").strip().upper() for cell in table[1]]
                            for ci, cell in enumerate(header2):
                                if cell in valid_zones:
                                    zone_cols[ci] = cell
                            if zone_cols:
                                table = table[1:]  # Skip first row

                    if not zone_cols:
                        continue

                    # If no explicit service_col, try first column
                    if service_col is None:
                        service_col = 0

                    # Parse data rows
                    for row in table[1:]:
                        if not row or len(row) <= max(zone_cols.keys()):
                            continue

                        raw_code = str(row[service_col] or "").strip().upper()
                        # Extract service code pattern (T-XXX, E-XXX, etc.)
                        code_match = re.search(r"[A-Z]-\d{3,4}", raw_code)
                        service_code = code_match.group(0) if code_match else raw_code

                        if not service_code:
                            continue

                        for ci, zone_code in zone_cols.items():
                            raw_amount = str(row[ci] if ci < len(row) else "").strip()
                            # Parse amount: remove separators, handle "50.000" or "50,000"
                            clean = re.sub(r"[^\d.,]", "", raw_amount)
                            if not clean:
                                continue
                            # Handle European format (50.000 = 50000)
                            if "." in clean and "," not in clean and clean.count(".") == 1:
                                parts = clean.split(".")
                                if len(parts[1]) == 3:  # thousands separator
                                    clean = clean.replace(".", "")
                            clean = clean.replace(".", "").replace(",", ".")
                            try:
                                amount = float(clean)
                                if amount > 0:
                                    extracted_items.append({
                                        "service_code": service_code,
                                        "zone_code": zone_code,
                                        "amount": amount,
                                        "is_fixed_across_zones": False,
                                        "known_service": service_code in valid_services,
                                    })
                            except ValueError:
                                continue

    except Exception as e:
        logger.error(f"PDF parsing failed: {e}")
        raise HTTPException(status_code=422, detail=f"PDF parsing error: {str(e)}")

    # Detect fixed-across-zones items
    service_amounts = {}
    for item in extracted_items:
        key = item["service_code"]
        if key not in service_amounts:
            service_amounts[key] = set()
        service_amounts[key].add(item["amount"])
    for item in extracted_items:
        if len(service_amounts.get(item["service_code"], set())) == 1:
            item["is_fixed_across_zones"] = True

    return {
        "extracted_items": extracted_items,
        "total_extracted": len(extracted_items),
        "tables_found": tables_found,
        "method": "pdfplumber",
        "note": "Review before importing. Use bulk-import endpoint to confirm.",
    }


# ============================================================
# Public Detail Endpoints — /{bundle_id} MUST be LAST
# ============================================================

@router.get("/{bundle_id}", response_model=ServiceBundleResponse)
async def get_bundle(bundle_id: UUID, db=Depends(get_database)):
    """Get a single bundle by ID."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
    return ServiceBundleResponse(**bundle)


@router.get("/{bundle_id}/pricing")
async def get_bundle_pricing(
    bundle_id: UUID,
    zone_id: UUID = Query(..., description="Zone ID for pricing"),
    db=Depends(get_database),
):
    """Get items + total for a bundle in a specific zone."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    pricing = await BundleService.get_bundle_pricing(db, bundle_id, zone_id)
    return {
        "bundle": ServiceBundleResponse(**bundle).model_dump(),
        "items": [BundleItemResponse(**i).model_dump() for i in pricing["items"]],
        "total_amount": pricing["total_amount"],
        "currency": pricing["currency"],
        "installment_eligible": bundle.get("installment_eligible", False),
        "max_installments": bundle.get("max_installments", 1),
    }


@router.get("/{bundle_id}/matrix")
async def get_pricing_matrix(bundle_id: UUID, db=Depends(get_database)):
    """Get complete pricing matrix (all zones × all services)."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    matrix = await BundleService.get_pricing_matrix(db, bundle_id)
    zones = await BundleService.list_zones(db)

    return {
        "bundle": ServiceBundleResponse(**bundle).model_dump(),
        "zones": [CommerceZoneResponse(**z).model_dump() for z in zones],
        "items": [BundleItemResponse(**i).model_dump() for i in matrix["items"]],
        "zone_totals": [
            {
                "zone": CommerceZoneResponse(**zt).model_dump(),
                "total_amount": str(zt["total_amount"]),
                "item_count": zt["item_count"],
                "tesoro_total": str(zt.get("tesoro_total", 0)),
                "municipal_total": str(zt.get("municipal_total", 0)),
                "chamber_total": str(zt.get("chamber_total", 0)),
            }
            for zt in matrix["zone_totals"]
        ],
        "currency": "XAF",
    }


@router.get("/{bundle_id}/documents", response_model=List[BundleDocumentItem])
async def get_bundle_documents(bundle_id: UUID, db=Depends(get_database)):
    """Get documents required by all services in the bundle."""
    bundle = await BundleService.get_bundle(db, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    docs = await BundleService.get_required_documents(db, bundle_id)
    return [BundleDocumentItem(**d) for d in docs]


@router.get("/{bundle_id}/installment-preview")
async def preview_installments(
    bundle_id: UUID,
    zone_id: UUID = Query(...),
    installments: int = Query(3, ge=1, le=12),
    db=Depends(get_database),
):
    """Preview installment payment plan for a bundle+zone."""
    result = await BundleService.preview_installments(
        db, bundle_id, zone_id, installments
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
