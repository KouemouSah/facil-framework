"""
Chatbot Public Tools — Business tools for the public-facing RAG chatbot.

These tools give Gemini access to ALL public data on the Facil platform:
fiscal services, companies, ministries, office locations, workflow guides,
service categories, and platform information.

IMPORTANT: All functions accept (db, **kwargs) pattern.
  - db is the asyncpg connection
  - Gemini provides function-specific parameters via kwargs
  - No entity scoping (these are public, citizen-facing tools)

8 function-calling tools for Gemini:
1. search_fiscal_services  — Search services by keyword, category, or ministry
2. get_service_details     — Full details of a service (docs, procedures, tariffs)
3. search_companies        — Company directory (by name, NIF, zone, sector)
4. get_ministry_directory  — Ministry info with sectors and service counts
5. get_office_locations    — Office addresses, hours, and contact info
6. get_workflow_guide      — Complete guide for an administrative procedure
7. get_service_categories  — Browse service catalog by category
8. get_platform_info       — General platform information and FAQ
"""

from typing import Any, Dict, List
from loguru import logger

# Import FunctionDeclaration from Vertex AI
VERTEX_AVAILABLE = False
try:
    from vertexai.generative_models import FunctionDeclaration
    VERTEX_AVAILABLE = True
except ImportError:
    pass


# ============================================================================
# SQL FUNCTIONS — All use (db, **kwargs), citizen-facing (no entity scoping)
# ============================================================================

async def search_fiscal_services(db, **kwargs) -> dict:
    """Search fiscal services by keyword, category, or ministry."""
    query = kwargs.get("query", "")
    category = kwargs.get("category", "")
    ministry = kwargs.get("ministry", "")
    limit = min(int(kwargs.get("limit", 10)), 20)

    # No guard — allow listing popular services without filters
    conditions = ["fs.status = 'active'"]
    params = []
    idx = 1

    if query:
        conditions.append(f"""(
            fs.search_vector @@ plainto_tsquery('spanish', ${idx})
            OR fs.name_es ILIKE '%' || ${idx} || '%'
            OR EXISTS (SELECT 1 FROM service_keywords sk
                       WHERE sk.fiscal_service_id = fs.id
                       AND sk.keyword ILIKE '%' || ${idx} || '%')
        )""")
        params.append(query)
        idx += 1

    if category:
        conditions.append(f"c.name_es ILIKE '%' || ${idx} || '%'")
        params.append(category)
        idx += 1

    if ministry:
        conditions.append(f"m.name_es ILIKE '%' || ${idx} || '%'")
        params.append(ministry)
        idx += 1

    where = " AND ".join(conditions)
    params.append(limit)

    rows = await db.fetch(f"""
        SELECT fs.service_code, fs.name_es, fs.description_es,
               fs.service_type, fs.tasa_expedicion, fs.tasa_renovacion,
               fs.processing_time_days, fs.validity_period_months,
               c.name_es AS category_name,
               m.name_es AS ministry_name
        FROM fiscal_services fs
        LEFT JOIN categories c ON c.id = fs.category_id
        LEFT JOIN sectors s ON s.id = c.sector_id
        LEFT JOIN ministries m ON m.id = s.ministry_id
        WHERE {where}
        ORDER BY fs.calculation_count DESC NULLS LAST
        LIMIT ${idx}
    """, *params)

    return {
        "services": [
            {k: str(v) if v is not None else None for k, v in dict(r).items()}
            for r in rows
        ],
        "count": len(rows),
    }


async def get_service_details(db, **kwargs) -> dict:
    """Get full details of a fiscal service including documents, procedures, and tariffs."""
    service_code = kwargs.get("service_code", "")
    service_name = kwargs.get("service_name", "")

    if not service_code and not service_name:
        return {"error": "Provide service_code or service_name"}

    # Find service
    if service_code:
        svc = await db.fetchrow("""
            SELECT fs.id, fs.service_code, fs.name_es, fs.description_es,
                   fs.service_type, fs.calculation_method,
                   fs.tasa_expedicion, fs.tasa_renovacion,
                   fs.processing_time_days, fs.validity_period_months,
                   fs.legal_reference,
                   c.name_es AS category_name,
                   m.name_es AS ministry_name
            FROM fiscal_services fs
            LEFT JOIN categories c ON c.id = fs.category_id
            LEFT JOIN sectors s ON s.id = c.sector_id
            LEFT JOIN ministries m ON m.id = s.ministry_id
            WHERE fs.service_code = $1 AND fs.status = 'active'
        """, service_code)
    else:
        svc = await db.fetchrow("""
            SELECT fs.id, fs.service_code, fs.name_es, fs.description_es,
                   fs.service_type, fs.calculation_method,
                   fs.tasa_expedicion, fs.tasa_renovacion,
                   fs.processing_time_days, fs.validity_period_months,
                   fs.legal_reference,
                   c.name_es AS category_name,
                   m.name_es AS ministry_name
            FROM fiscal_services fs
            LEFT JOIN categories c ON c.id = fs.category_id
            LEFT JOIN sectors s ON s.id = c.sector_id
            LEFT JOIN ministries m ON m.id = s.ministry_id
            WHERE fs.name_es ILIKE '%' || $1 || '%' AND fs.status = 'active'
            ORDER BY fs.calculation_count DESC NULLS LAST
            LIMIT 1
        """, service_name)

    if not svc:
        return {"error": f"Service not found: {service_code or service_name}"}

    service_id = svc["id"]
    result = {k: str(v) if v is not None else None for k, v in dict(svc).items()}

    # Get required documents
    docs = await db.fetch("""
        SELECT dt.template_code, dt.document_name_es,
               sda.is_required_expedition, sda.is_required_renewal,
               dt.validity_duration_months
        FROM service_document_assignments sda
        JOIN document_templates dt ON dt.id = sda.document_template_id
        WHERE sda.fiscal_service_id = $1
        ORDER BY sda.display_order
    """, service_id)
    result["required_documents"] = [
        {k: str(v) if v is not None else None for k, v in dict(d).items()}
        for d in docs
    ]

    # Get procedures with steps (single query, no N+1)
    procs_with_steps = await db.fetch("""
        SELECT pt.id as proc_id, pt.name_es as proc_name, pt.description_es as proc_desc,
               pts.step_number, pts.description_es as step_desc,
               pts.instructions_es as step_instructions,
               pts.estimated_duration_minutes
        FROM service_procedure_assignments spa
        JOIN procedure_templates pt ON pt.id = spa.procedure_template_id
        LEFT JOIN procedure_template_steps pts ON pts.template_id = pt.id
        WHERE spa.fiscal_service_id = $1
        ORDER BY spa.display_order, pts.step_number
    """, service_id)

    # Group steps by procedure
    procedures_map: dict = {}
    for row in procs_with_steps:
        pid = row["proc_id"]
        if pid not in procedures_map:
            procedures_map[pid] = {
                "name": row["proc_name"],
                "description": row["proc_desc"],
                "steps": [],
            }
        if row["step_number"] is not None:
            procedures_map[pid]["steps"].append({
                "step_number": str(row["step_number"]),
                "description_es": row["step_desc"],
                "instructions_es": row["step_instructions"],
                "estimated_duration_minutes": str(row["estimated_duration_minutes"]) if row["estimated_duration_minutes"] else None,
            })
    result["procedures"] = list(procedures_map.values())

    return result


async def search_companies(db, **kwargs) -> dict:
    """Search the company directory by name, NIF, zone, or sector."""
    query = kwargs.get("query", "")
    zone = kwargs.get("zone", "")
    sector = kwargs.get("sector", "")
    limit = min(int(kwargs.get("limit", 10)), 20)

    conditions = ["c.is_verified = true"]
    params = []
    idx = 1

    if query:
        conditions.append(f"""(
            c.legal_name ILIKE '%' || ${idx} || '%'
            OR c.nif ILIKE '%' || ${idx} || '%'
            OR c.registration_number ILIKE '%' || ${idx} || '%'
        )""")
        params.append(query)
        idx += 1

    if zone:
        conditions.append(f"cz.name_es ILIKE '%' || ${idx} || '%'")
        params.append(zone)
        idx += 1

    if sector:
        conditions.append(f"c.sector_actividad ILIKE '%' || ${idx} || '%'")
        params.append(sector)
        idx += 1

    where = " AND ".join(conditions)
    params.append(limit)

    rows = await db.fetch(f"""
        SELECT c.legal_name, c.nif, c.registration_number,
               c.forma_juridica, c.sector_actividad, c.objeto_social,
               c.address, ci.name AS city_name, ci.provincia,
               cz.name_es AS zone_name
        FROM companies c
        LEFT JOIN cities ci ON ci.id = c.city_id
        LEFT JOIN commerce_zones cz ON cz.id = c.zone_id
        WHERE {where}
        ORDER BY c.legal_name
        LIMIT ${idx}
    """, *params)

    companies = [
        {k: str(v) if v is not None else None for k, v in dict(r).items()}
        for r in rows
    ]

    return {
        "companies": companies,
        "count": len(companies),
        "display_hint": "tabla" if len(companies) >= 2 else "lista",
    }


async def get_ministry_directory(db, **kwargs) -> dict:
    """Get information about government ministries, their sectors and services."""
    ministry_code = kwargs.get("ministry_code", "")

    if ministry_code:
        row = await db.fetchrow("""
            SELECT m.id, m.ministry_code, m.name_es, m.description_es,
                   m.contact_email, m.contact_phone, m.website_url,
                   (SELECT COUNT(*) FROM sectors s WHERE s.ministry_id = m.id) AS sector_count,
                   (SELECT COUNT(*) FROM fiscal_services fs
                    JOIN categories c ON c.id = fs.category_id
                    JOIN sectors s ON s.id = c.sector_id
                    WHERE s.ministry_id = m.id AND fs.status = 'active') AS service_count
            FROM ministries m
            WHERE m.ministry_code = $1 OR m.name_es ILIKE '%' || $1 || '%'
            LIMIT 1
        """, ministry_code)
        if not row:
            return {"error": f"Ministry not found: {ministry_code}"}

        # Get sectors for this ministry
        sectors = await db.fetch("""
            SELECT s.sector_code, s.name_es, s.description_es
            FROM sectors s WHERE s.ministry_id = $1 ORDER BY s.display_order
        """, row["id"])

        result = {k: str(v) if v is not None else None for k, v in dict(row).items()}
        result["sectors"] = [
            {k: str(v) if v is not None else None for k, v in dict(s).items()}
            for s in sectors
        ]
        return result
    else:
        # List all ministries
        rows = await db.fetch("""
            SELECT m.ministry_code, m.name_es,
                   m.contact_email, m.contact_phone,
                   (SELECT COUNT(*) FROM sectors s WHERE s.ministry_id = m.id) AS sector_count,
                   (SELECT COUNT(*) FROM fiscal_services fs
                    JOIN categories c ON c.id = fs.category_id
                    JOIN sectors s ON s.id = c.sector_id
                    WHERE s.ministry_id = m.id AND fs.status = 'active') AS service_count
            FROM ministries m
            WHERE m.is_active = true
            ORDER BY m.display_order, m.name_es
        """)
        return {
            "ministries": [
                {k: str(v) if v is not None else None for k, v in dict(r).items()}
                for r in rows
            ],
            "count": len(rows),
        }


async def get_office_locations(db, **kwargs) -> dict:
    """Get office locations, addresses, hours, and contact information."""
    entity_code = kwargs.get("entity_code", "")
    city = kwargs.get("city", "")

    conditions = ["el.is_active = true"]
    params = []
    idx = 1

    if entity_code:
        conditions.append(f"(el.entity_code ILIKE '%' || ${idx} || '%' OR e.name ILIKE '%' || ${idx} || '%')")
        params.append(entity_code)
        idx += 1

    if city:
        conditions.append(f"(el.city ILIKE '%' || ${idx} || '%' OR ci.name ILIKE '%' || ${idx} || '%')")
        params.append(city)
        idx += 1

    where = " AND ".join(conditions)

    rows = await db.fetch(f"""
        SELECT el.entity_code, el.location_name, el.city, el.region,
               el.location_address, el.phone, el.email,
               el.operating_hours,
               e.name AS entity_name,
               ci.name AS city_name
        FROM entity_locations el
        LEFT JOIN entities e ON e.code = el.entity_code
        LEFT JOIN cities ci ON ci.id = el.city_id
        WHERE {where}
        ORDER BY el.entity_code, el.city
    """, *params)

    return {
        "locations": [
            {k: str(v) if v is not None else None for k, v in dict(r).items()}
            for r in rows
        ],
        "count": len(rows),
    }


async def get_workflow_guide(db, **kwargs) -> dict:
    """Get a complete tutorial-style guide for an administrative procedure."""
    workflow_name = kwargs.get("workflow_name", "") or kwargs.get("workflow_code", "")

    if not workflow_name:
        # List all available workflows grouped by category
        rows = await db.fetch("""
            SELECT w.code, w.name_es, w.description_es, w.category,
                   w.requires_appointment, w.requires_agent_validation,
                   w.sla_hours, w.max_processing_days
            FROM workflows w
            WHERE w.is_active = true AND w.parent_workflow_code IS NULL
            ORDER BY w.category, w.name_es
        """)
        return {
            "available_workflows": [
                {k: str(v) if v is not None else None for k, v in dict(r).items()}
                for r in rows
            ],
            "count": len(rows),
            "hint": "Usa workflow_code para obtener la guía detallada de un trámite específico",
        }

    # Find workflow — always fuzzy search (user says "pasaporte", not "PASAPORTE_NUEVO")
    wf = await db.fetchrow("""
        SELECT w.code, w.name_es, w.description_es, w.category,
               w.requires_appointment, w.requires_agent_validation,
               w.sla_hours, w.max_processing_days,
               w.appointment_delay_days, w.appointment_entity_code
        FROM workflows w
        WHERE w.is_active = true
          AND (w.code ILIKE '%' || $1 || '%' OR w.name_es ILIKE '%' || $1 || '%')
        ORDER BY w.parent_workflow_code NULLS FIRST
        LIMIT 1
    """, workflow_name)

    if not wf:
        return {"error": f"Trámite no encontrado: {workflow_name}"}

    result = {k: str(v) if v is not None else None for k, v in dict(wf).items()}

    # Sub-workflows (e.g., PASAPORTE → NUEVO, RENOVACION, PERDIDA, ROBO)
    sub_workflows = await db.fetch("""
        SELECT code, name_es, description_es
        FROM workflows
        WHERE parent_workflow_code = $1 AND is_active = true
        ORDER BY display_order, name_es
    """, wf["code"])
    if sub_workflows:
        result["sub_types"] = [
            {k: str(v) if v is not None else None for k, v in dict(s).items()}
            for s in sub_workflows
        ]

    # Required documents with instructions
    docs = await db.fetch("""
        SELECT wdr.document_code, wdr.document_name_es, wdr.is_required,
               wdr.condition_type, wdr.instructions_es
        FROM workflow_document_requirements wdr
        WHERE wdr.workflow_code = $1 AND wdr.is_active = true
        ORDER BY wdr.display_order
    """, wf["code"])
    result["required_documents"] = [
        {k: str(v) if v is not None else None for k, v in dict(d).items()}
        for d in docs
    ]

    # Tariffs with details
    tariffs = await db.fetch("""
        SELECT wt.solicitud_type, wt.tariff_type, wt.amount,
               wt.currency, wt.legal_reference
        FROM workflow_tariffs wt
        WHERE wt.workflow_code = $1 AND wt.is_active = true
        ORDER BY wt.solicitud_type
    """, wf["code"])
    result["tariffs"] = [
        {k: str(v) if v is not None else None for k, v in dict(t).items()}
        for t in tariffs
    ]

    # Also get tariffs for sub-workflows
    if sub_workflows:
        sub_codes = [s["code"] for s in sub_workflows]
        sub_tariffs = await db.fetch("""
            SELECT wt.workflow_code, wt.solicitud_type, wt.amount, wt.currency
            FROM workflow_tariffs wt
            WHERE wt.workflow_code = ANY($1) AND wt.is_active = true
            ORDER BY wt.workflow_code
        """, sub_codes)
        result["sub_type_tariffs"] = [
            {k: str(v) if v is not None else None for k, v in dict(t).items()}
            for t in sub_tariffs
        ]

    # Entities that handle this workflow
    entities = await db.fetch("""
        SELECT e.code, e.name, e.entity_type
        FROM entities e
        WHERE e.workflow_codes @> $1::jsonb AND e.is_active = true
    """, f'["{wf["code"]}"]')
    result["handling_entities"] = [
        {k: str(v) if v is not None else None for k, v in dict(e).items()}
        for e in entities
    ]

    # Office locations for handling entities
    if entities:
        entity_codes = [e["code"] for e in entities]
        locations = await db.fetch("""
            SELECT el.entity_code, el.location_name, el.city, el.region,
                   el.location_address, el.phone, el.operating_hours
            FROM entity_locations el
            WHERE el.entity_code = ANY($1) AND el.is_active = true
            ORDER BY el.entity_code, el.city
        """, entity_codes)
        result["office_locations"] = [
            {k: str(v) if v is not None else None for k, v in dict(l).items()}
            for l in locations
        ]

    # Build tutorial steps — clear, simple, for anyone
    step_num = 1
    tutorial = []

    tutorial.append(
        f"{step_num}. **Accede a la plataforma Facil** → Entra en facil.gq, "
        f"crea una cuenta si no tienes, e inicia sesión"
    )
    step_num += 1

    tutorial.append(
        f"{step_num}. **Selecciona el trámite** → Busca '{wf['name_es']}' "
        f"en el catálogo de servicios"
    )
    step_num += 1

    doc_count = len(docs)
    if doc_count > 0:
        doc_names = ", ".join(d["document_name_es"] for d in docs[:3] if d.get("document_name_es"))
        extra = f" y {doc_count - 3} más" if doc_count > 3 else ""
        tutorial.append(
            f"{step_num}. **Prepara tus documentos** → Necesitas {doc_count} documentos: "
            f"{doc_names}{extra}. Escanéalos o toma fotos claras"
        )
        step_num += 1

    tutorial.append(
        f"{step_num}. **Sube los documentos** → Adjunta los archivos escaneados "
        f"en la plataforma, uno por uno"
    )
    step_num += 1

    if wf["requires_appointment"]:
        delay = wf.get("appointment_delay_days") or 3
        tutorial.append(
            f"{step_num}. **Reserva tu cita** → Elige una fecha disponible "
            f"(a partir de {delay} días desde hoy) y un horario"
        )
        step_num += 1

    tariff_amount = tariffs[0]["amount"] if tariffs and tariffs[0]["amount"] is not None else "0"
    tariff_currency = tariffs[0]["currency"] if tariffs and tariffs[0]["currency"] is not None else "XAF"
    tutorial.append(
        f"{step_num}. **Realiza el pago** → Paga **{tariff_amount} {tariff_currency}** "
        f"por BANGE Mobile Money, tarjeta, transferencia o efectivo en ventanilla"
    )
    step_num += 1

    if wf["requires_appointment"]:
        tutorial.append(
            f"{step_num}. **Acude a tu cita** → Lleva los documentos ORIGINALES "
            f"el día y hora reservados"
        )
        step_num += 1

    if wf["requires_agent_validation"]:
        sla = wf.get("sla_hours") or 48
        tutorial.append(
            f"{step_num}. **Espera la revisión** → Un agente verificará tu solicitud "
            f"en un plazo máximo de {sla} horas"
        )
        step_num += 1

    tutorial.append(
        f"{step_num}. **Recoge tu documento** → Recibirás una notificación "
        f"cuando esté listo. Acude a la oficina indicada con tu DIP"
    )

    processing = wf.get("max_processing_days")
    if processing:
        tutorial.append(f"\n**Tiempo total estimado:** {processing} días hábiles")

    result["tutorial_steps"] = tutorial

    return result


async def get_service_categories(db, **kwargs) -> dict:
    """Browse the service catalog by category, with service counts."""
    sector = kwargs.get("sector", "")

    conditions = ["c.is_active = true"]
    params = []
    idx = 1

    if sector:
        conditions.append(f"s.name_es ILIKE '%' || ${idx} || '%'")
        params.append(sector)
        idx += 1

    where = " AND ".join(conditions)

    rows = await db.fetch(f"""
        SELECT c.category_code, c.name_es AS category_name,
               c.description_es,
               s.name_es AS sector_name,
               m.name_es AS ministry_name,
               (SELECT COUNT(*) FROM fiscal_services fs
                WHERE fs.category_id = c.id AND fs.status = 'active') AS service_count
        FROM categories c
        LEFT JOIN sectors s ON s.id = c.sector_id
        LEFT JOIN ministries m ON m.id = s.ministry_id
        WHERE {where}
        ORDER BY m.name_es, s.name_es, c.name_es
    """, *params)

    return {
        "categories": [
            {k: str(v) if v is not None else None for k, v in dict(r).items()}
            for r in rows
        ],
        "count": len(rows),
    }


async def get_platform_info(db, **kwargs) -> dict:
    """Get general information about the Facil platform with live stats."""
    topic = kwargs.get("topic", "about")

    # Fetch live stats for "about" topic
    live_stats = {}
    if topic == "about":
        try:
            stats = await db.fetchrow("""
                SELECT
                    (SELECT COUNT(*) FROM fiscal_services WHERE status = 'active') as total_services,
                    (SELECT COUNT(*) FROM workflows WHERE is_active = true) as total_workflows,
                    (SELECT COUNT(*) FROM companies WHERE is_verified = true) as total_companies,
                    (SELECT COUNT(*) FROM ministries) as total_ministries
            """)
            if stats:
                live_stats = {
                    "total_services": stats["total_services"],
                    "total_workflows": stats["total_workflows"],
                    "total_companies": stats["total_companies"],
                    "total_ministries": stats["total_ministries"],
                }
        except Exception:
            pass

    info = {
        "about": {
            "name": "Facil (TaxasGE)",
            "description": "Plataforma digital inteligente de trámites fiscales y administrativos de Guinea Ecuatorial. Ofrece asistencia IA, pago integrado y seguimiento en tiempo real.",
            "services": f"{live_stats.get('total_services', '850+')} servicios fiscales disponibles",
            "workflows": f"{live_stats.get('total_workflows', '15+')} trámites administrativos automatizados",
            "companies": f"{live_stats.get('total_companies', '100+')} empresas registradas",
            "ministries": f"{live_stats.get('total_ministries', '20+')} ministerios",
            "languages": "Español (principal), Francés, Inglés",
            "coverage": "Todo el territorio de Guinea Ecuatorial (Región Insular y Continental)",
            "key_features": "Asistencia IA, pago integrado (BANGE, tarjeta, efectivo), seguimiento en tiempo real, verificación automática de documentos",
        },
        "hours": {
            "online_platform": "Disponible 24/7",
            "office_hours": "Lunes a Viernes, 08:00 - 15:00 (hora local GMT+1)",
            "note": "Los horarios pueden variar según la oficina. Use la función 'get_office_locations' para horarios específicos.",
        },
        "contact": {
            "website": "https://facil.gq",
            "support": "Disponible a través del sistema de tickets de soporte en la plataforma",
            "note": "Para consultas específicas sobre un trámite, contacte la entidad correspondiente.",
        },
        "faq": {
            "how_to_start": "1. Registrarse en la plataforma, 2. Seleccionar el servicio deseado, 3. Subir los documentos requeridos, 4. Realizar el pago, 5. Seguir el estado de su solicitud",
            "payment_methods": "BANGE Mobile Money, transferencia bancaria, tarjeta, efectivo (en ventanilla)",
            "processing_time": "Varía según el servicio. Consulte los detalles de cada servicio para tiempos estimados.",
            "documents": "Los documentos requeridos varían por servicio. Use la función 'get_service_details' para ver la lista completa.",
        },
    }

    return info.get(topic, info["about"])


# ============================================================================
# FUNCTION MAP — Maps function names to async callables
# ============================================================================

async def search_bundles(db, **kwargs) -> dict:
    """Search fiscal bundles (commerce packages) with pricing by zone."""
    commerce_type = kwargs.get("commerce_type", "")
    zone = kwargs.get("zone", "")

    try:
        if commerce_type:
            # Search specific bundle type
            rows = await db.fetch("""
                SELECT sb.name_es as bundle_name, sb.bundle_code,
                       cz.name_es as zone_name, cz.zone_code,
                       SUM(sbi.amount) as total,
                       array_agg(
                           fs.name_es || ': ' || sbi.amount || ' XAF'
                           ORDER BY sbi.display_order
                       ) as items
                FROM service_bundles sb
                JOIN service_bundle_items sbi ON sbi.bundle_id = sb.id AND sbi.is_active = true
                JOIN fiscal_services fs ON fs.id = sbi.fiscal_service_id
                JOIN commerce_zones cz ON cz.id = sbi.zone_id
                WHERE sb.name_es ILIKE '%' || $1 || '%' AND sb.is_active = true
                GROUP BY sb.name_es, sb.bundle_code, cz.name_es, cz.zone_code
                ORDER BY SUM(sbi.amount) DESC
            """, commerce_type)
        else:
            # List all bundles with price ranges
            rows = await db.fetch("""
                SELECT sb.name_es as bundle_name, sb.bundle_code,
                       MIN(zone_totals.total) as min_total,
                       MAX(zone_totals.total) as max_total
                FROM service_bundles sb
                JOIN (
                    SELECT sbi.bundle_id, sbi.zone_id, SUM(sbi.amount) as total
                    FROM service_bundle_items sbi WHERE sbi.is_active = true
                    GROUP BY sbi.bundle_id, sbi.zone_id
                ) zone_totals ON zone_totals.bundle_id = sb.id
                WHERE sb.is_active = true
                GROUP BY sb.name_es, sb.bundle_code
                ORDER BY MAX(zone_totals.total) DESC
            """)

        if not rows:
            return {"bundles": [], "message": "No se encontraron paquetes fiscales"}

        bundles = []
        for r in rows:
            bundle = {"bundle_name": r["bundle_name"], "bundle_code": r["bundle_code"]}
            if "zone_name" in r.keys():
                bundle["zone_name"] = r["zone_name"]
                bundle["zone_code"] = r["zone_code"]
                bundle["total_xaf"] = float(r["total"])
                bundle["items"] = list(r["items"]) if r.get("items") else []
            else:
                bundle["min_total_xaf"] = float(r["min_total"])
                bundle["max_total_xaf"] = float(r["max_total"])
            bundles.append(bundle)

        # Filter by zone if specified (supports city names, zone codes, zone names)
        if zone and bundles and "zone_code" in bundles[0]:
            zone_lower = zone.lower().strip()
            # Map city names to zone codes
            city_zone_map = {
                'malabo': 'A1', 'bata': 'A1',
                'ebebiyin': 'B1', 'evinayong': 'B1', 'mongomo': 'B1', 'luba': 'B1',
                'niefang': 'C1', 'micomeseng': 'C1', 'acurenam': 'C1',
            }
            zone_code_match = city_zone_map.get(zone_lower, zone.upper())
            filtered = [
                b for b in bundles
                if zone_code_match == b.get("zone_code", "")
                or zone_lower in b.get("zone_name", "").lower()
            ]
            if filtered:
                bundles = filtered

        return {
            "bundles": bundles[:20],
            "total_found": len(bundles),
            "note": "Precios varían por zona geográfica. A1=Capitales Regiones (Malabo/Bata), B1=Capitales Provincias, C1=Capitales Distritales, D1=Consejos Poblados"
        }

    except Exception as e:
        logger.error(f"search_bundles error: {e}")
        return {"bundles": [], "error": str(e)}


async def start_workflow(db, **kwargs) -> dict:
    """Generate a start link for a workflow procedure on Facil platform."""
    workflow_name = kwargs.get("workflow_name", "")
    if not workflow_name:
        return {"error": "Proporcione el nombre del trámite"}

    wf = await db.fetchrow("""
        SELECT w.code, w.name_es, w.description_es, w.category,
               w.requires_appointment, w.sla_hours, w.max_processing_days
        FROM workflows w
        WHERE w.is_active = true
          AND (w.code ILIKE '%' || $1 || '%' OR w.name_es ILIKE '%' || $1 || '%')
        ORDER BY w.parent_workflow_code NULLS FIRST
        LIMIT 1
    """, workflow_name)

    if not wf:
        return {"error": f"Trámite no encontrado: {workflow_name}"}

    code = wf["code"]

    # Get sub-types
    sub_types = await db.fetch("""
        SELECT code, name_es FROM workflows
        WHERE parent_workflow_code = $1 AND is_active = true
        ORDER BY name_es
    """, code)

    # Get tariff estimate
    tariff = await db.fetchrow("""
        SELECT amount, currency FROM workflow_tariffs
        WHERE workflow_code = $1 AND is_active = true
        ORDER BY solicitud_type LIMIT 1
    """, code)

    return {
        "workflow_name": wf["name_es"],
        "workflow_code": code,
        "wizard_url": f"/dashboard/service-requests/new?workflow={code}",
        "description": wf["description_es"],
        "estimated_cost_xaf": float(tariff["amount"]) if tariff and tariff["amount"] is not None else None,
        "estimated_time_days": wf["max_processing_days"],
        "requires_appointment": wf["requires_appointment"],
        "sub_types": [
            {"code": s["code"], "name": s["name_es"]}
            for s in sub_types
        ] if sub_types else [],
        "instructions": (
            f"Para iniciar el trámite de {wf['name_es']}, "
            f"acceda a la plataforma Facil y seleccione este servicio. "
            f"El asistente digital le guiará paso a paso."
        ),
    }


async def get_document_checklist(db, **kwargs) -> dict:
    """Get the exact document checklist for a workflow with conditions."""
    workflow_name = kwargs.get("workflow_name", "")
    solicitud_type = kwargs.get("solicitud_type", "")

    if not workflow_name:
        return {"error": "Proporcione el nombre del trámite"}

    wf = await db.fetchrow("""
        SELECT code, name_es FROM workflows
        WHERE is_active = true
          AND (code ILIKE '%' || $1 || '%' OR name_es ILIKE '%' || $1 || '%')
        ORDER BY parent_workflow_code NULLS FIRST
        LIMIT 1
    """, workflow_name)

    if not wf:
        return {"error": f"Trámite no encontrado: {workflow_name}"}

    docs = await db.fetch("""
        SELECT document_code, document_name_es, is_required,
               condition_type, instructions_es, display_order
        FROM workflow_document_requirements
        WHERE workflow_code = $1 AND is_active = true
        ORDER BY display_order
    """, wf["code"])

    documents = []
    for d in docs:
        doc = {
            "name": d["document_name_es"],
            "code": d["document_code"],
            "is_required": d["is_required"],
            "condition": d["condition_type"] or "always",
            "instructions": d["instructions_es"],
        }
        # Filter by solicitud_type if provided
        if solicitud_type:
            cond = (d["condition_type"] or "always").lower()
            if cond == "always" or solicitud_type.lower() in cond:
                documents.append(doc)
        else:
            documents.append(doc)

    required = [d for d in documents if d["is_required"]]
    optional = [d for d in documents if not d["is_required"]]

    return {
        "workflow_name": wf["name_es"],
        "workflow_code": wf["code"],
        "solicitud_type": solicitud_type or "todos",
        "documents": documents,
        "total_required": len(required),
        "total_optional": len(optional),
        "note": "Los documentos marcados como requeridos son obligatorios. Los opcionales pueden ser solicitados según el caso.",
    }


CHATBOT_FUNCTION_MAP = {
    "search_fiscal_services": search_fiscal_services,
    "get_service_details": get_service_details,
    "search_companies": search_companies,
    "get_ministry_directory": get_ministry_directory,
    "get_office_locations": get_office_locations,
    "get_workflow_guide": get_workflow_guide,
    "get_service_categories": get_service_categories,
    "get_platform_info": get_platform_info,
    "search_bundles": search_bundles,
    "start_workflow": start_workflow,
    "get_document_checklist": get_document_checklist,
}

# Authenticated-only tools (added dynamically when user is logged in)
from app.modules.chatbot.services.chatbot_tools_authenticated import (
    get_my_requests, get_request_detail, get_my_payments,
    get_my_appointments, get_my_notifications, get_my_profile,
    get_my_next_actions, get_my_documents,
    # Vault tools (Mes Documents)
    list_vault_documents, check_readiness, get_expiring_documents,
    get_vault_stats, suggest_next_uploads, prepare_renewal,
    get_agent_memory,
    # Workflow orchestrator (Level 2 agent)
    auto_prepare_wizard,
    # Appointment suggestions (Level 2, Phase 7)
    suggest_appointment_slots,
    # Executive tools (Level 3)
    submit_prepared_request,
    book_appointment,
)

CHATBOT_AUTH_FUNCTION_MAP = {
    "get_my_requests": get_my_requests,
    "get_request_detail": get_request_detail,
    "get_my_payments": get_my_payments,
    "get_my_appointments": get_my_appointments,
    "get_my_notifications": get_my_notifications,
    "get_my_profile": get_my_profile,
    "get_my_next_actions": get_my_next_actions,
    "get_my_documents": get_my_documents,
    # Vault tools (Mes Documents)
    "list_vault_documents": list_vault_documents,
    "check_readiness": check_readiness,
    "get_expiring_documents": get_expiring_documents,
    "get_vault_stats": get_vault_stats,
    "suggest_next_uploads": suggest_next_uploads,
    "prepare_renewal": prepare_renewal,
    "get_agent_memory": get_agent_memory,
    "auto_prepare_wizard": auto_prepare_wizard,
    # Appointment suggestions (Level 2, Phase 7)
    "suggest_appointment_slots": suggest_appointment_slots,
    # Executive tools (Level 3)
    "submit_prepared_request": submit_prepared_request,
    "book_appointment": book_appointment,
}


# ============================================================================
# FUNCTION DECLARATIONS — Gemini tool definitions
# ============================================================================

CHATBOT_FUNC_DECLS = []

if VERTEX_AVAILABLE:
    CHATBOT_FUNC_DECLS = [
        FunctionDeclaration(
            name="search_fiscal_services",
            description="Buscar servicios fiscales por palabra clave, categoría o ministerio. Usar cuando el usuario pregunta sobre un servicio específico, precios, o tipos de trámites disponibles.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Palabra clave de búsqueda (ej: 'pasaporte', 'licencia', 'residencia')"},
                    "category": {"type": "string", "description": "Filtrar por nombre de categoría (opcional)"},
                    "ministry": {"type": "string", "description": "Filtrar por nombre de ministerio (opcional)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_service_details",
            description="Obtener detalles completos de un servicio fiscal: documentos requeridos, procedimiento paso a paso, tarifas, tiempo de procesamiento y validez. Usar cuando el usuario pide información detallada sobre un servicio específico.",
            parameters={
                "type": "object",
                "properties": {
                    "service_code": {"type": "string", "description": "Código del servicio SI se conoce. Preferir service_name en lenguaje natural."},
                    "service_name": {"type": "string", "description": "Nombre parcial del servicio (si no se conoce el código)"},
                },
            },
        ),
        FunctionDeclaration(
            name="search_companies",
            description="Buscar en el directorio de empresas registradas en Guinea Ecuatorial. SIEMPRE llamar esta función cuando el usuario mencione empresas, directorio empresarial, NIF, o actividad comercial. Si no se especifica filtro, llamar SIN parámetros para listar las empresas registradas.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Opcional: nombre de empresa, NIF, o número de registro. Dejar vacío para listar todas."},
                    "zone": {"type": "string", "description": "Opcional: zona comercial (ej: 'Malabo', 'Bata')"},
                    "sector": {"type": "string", "description": "Opcional: sector de actividad (ej: 'Comercio')"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_ministry_directory",
            description="Obtener información sobre los ministerios del gobierno de Guinea Ecuatorial. SIEMPRE llamar cuando el usuario mencione ministerios, gobierno, o organización gubernamental. Sin parámetros = listar todos los ministerios.",
            parameters={
                "type": "object",
                "properties": {
                    "ministry_code": {"type": "string", "description": "Código o nombre del ministerio (dejar vacío para listar todos)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_office_locations",
            description="Obtener direcciones, horarios y contacto de oficinas gubernamentales. SIEMPRE llamar cuando el usuario pregunte dónde, horarios, ubicación, o dirección de oficinas. Sin parámetros = listar todas.",
            parameters={
                "type": "object",
                "properties": {
                    "entity_code": {"type": "string", "description": "Código o nombre de la entidad (ej: 'CNEDOGE', 'DGT', 'Extranjería')"},
                    "city": {"type": "string", "description": "Ciudad (ej: 'Malabo', 'Bata')"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_workflow_guide",
            description="Obtener guía tutorial completa de un trámite administrativo. SIEMPRE llamar cuando el usuario pregunte cómo hacer un trámite, pasos, documentos necesarios, o procedimiento. Sin parámetros = listar todos los trámites disponibles.",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": "Nombre del trámite en lenguaje natural tal como lo dice el usuario (ej: 'pasaporte', 'residencia', 'licencia de conducir', 'contrato'). NO usar códigos técnicos."},
                },
            },
        ),
        FunctionDeclaration(
            name="get_service_categories",
            description="Explorar el catálogo de servicios por categoría. SIEMPRE llamar cuando el usuario pregunte qué servicios hay, categorías, o quiera explorar el catálogo. Sin parámetros = listar todas las categorías.",
            parameters={
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "Filtrar por sector (opcional, ej: 'Hacienda', 'Seguridad')"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_platform_info",
            description="Información general sobre la plataforma Facil: qué es, horarios, contacto, preguntas frecuentes. Usar cuando el usuario pregunta sobre la plataforma, cómo funciona, o necesita ayuda general.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Tema de información",
                        "enum": ["about", "hours", "contact", "faq"],
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="search_bundles",
            description="Buscar paquetes fiscales (licencias comerciales) con precios por zona geográfica. SIEMPRE usar cuando el usuario pregunte sobre precios de apertura de negocio, licencia comercial, cuánto cuesta abrir un restaurante/farmacia/tienda/bar, o precios por zona. Los precios varían según la zona (A1=Malabo/Bata más caro, D1=Poblados más barato).",
            parameters={
                "type": "object",
                "properties": {
                    "commerce_type": {
                        "type": "string",
                        "description": "Tipo de comercio (ej: 'restaurante', 'farmacia', 'ferretería', 'cafetería', 'discoteca', 'taller', 'abacería'). Dejar vacío para ver todos los tipos.",
                    },
                    "zone": {
                        "type": "string",
                        "description": "Zona geográfica o ciudad (ej: 'A1', 'Malabo', 'Bata', 'Capitales de Regiones'). Dejar vacío para ver todas las zonas.",
                    },
                },
            },
        ),
        FunctionDeclaration(
            name="start_workflow",
            description="Iniciar un trámite administrativo en la plataforma Facil. Devuelve el enlace directo al asistente digital, costo estimado y tiempo de procesamiento. SIEMPRE usar cuando el usuario quiera INICIAR, COMENZAR, EMPEZAR, SOLICITAR un trámite o diga 'quiero hacer'.",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": "Nombre del trámite en lenguaje natural (ej: 'pasaporte', 'residencia', 'licencia de conducir')"},
                },
                "required": ["workflow_name"],
            },
        ),
        FunctionDeclaration(
            name="get_document_checklist",
            description="Obtener la lista exacta de documentos requeridos para un trámite, con instrucciones y condiciones. Usar cuando el usuario pregunte específicamente QUÉ DOCUMENTOS, REQUISITOS, o PAPELES necesita para un trámite.",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": "Nombre del trámite (ej: 'pasaporte', 'residencia')"},
                    "solicitud_type": {"type": "string", "description": "Tipo de solicitud (opcional: 'expedicion', 'renovacion', 'duplicado')"},
                },
                "required": ["workflow_name"],
            },
        ),
    ]

    # Authenticated-only function declarations (added when user is logged in)
    CHATBOT_AUTH_FUNC_DECLS = [
        FunctionDeclaration(
            name="get_my_requests",
            description="Ver mis solicitudes de trámites. USAR cuando el usuario pregunta por sus demandes, solicitudes, dossiers, expedientes, o estado de sus trámites.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filtrar por estado (opcional: SUBMITTED, UNDER_REVIEW, COMPLETED, REJECTED, PAID, DRAFT)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_request_detail",
            description="Ver el detalle completo de una solicitud específica con su timeline de acciones. USAR cuando el usuario pregunta por el estado de una solicitud concreta o menciona una referencia (SR-xxxx).",
            parameters={
                "type": "object",
                "properties": {
                    "reference": {"type": "string", "description": "Referencia de la solicitud (ej: SR-2026-0001) o parte de ella"},
                },
                "required": ["reference"],
            },
        ),
        FunctionDeclaration(
            name="get_my_payments",
            description="Ver mis pagos pendientes y realizados. USAR cuando el usuario pregunta por pagos, facturas, cuánto debe, o recibos.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filtrar por estado (opcional: pending, completed, failed)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_my_appointments",
            description="Ver mis citas programadas. USAR cuando el usuario pregunta por citas, rendez-vous, cuándo tiene que ir, o próxima cita.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_my_notifications",
            description="Ver las últimas acciones y cambios en mis solicitudes. USAR cuando el usuario pregunta '¿qué hay de nuevo?', '¿novedades?', o actividad reciente.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_my_profile",
            description="Ver mi información de cuenta (nombre, email, empresas). USAR cuando el usuario pregunta por su perfil, cuenta, o datos personales.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_my_next_actions",
            description="¿Qué debo hacer ahora? Muestra pagos pendientes, citas próximas, documentos faltantes y solicitudes que necesitan atención. USAR cuando el usuario pregunta '¿qué tengo pendiente?', '¿qué debo hacer?', o cualquier pregunta sobre sus tareas.",
            parameters={
                "type": "object",
                "properties": {},
            },
        ),
        FunctionDeclaration(
            name="get_my_documents",
            description="Ver mis documentos enviados y su estado de verificación. USAR cuando el usuario pregunta por sus documentos subidos, archivos, o documentos faltantes.",
            parameters={
                "type": "object",
                "properties": {
                    "reference": {"type": "string", "description": "Referencia de solicitud para filtrar (opcional)"},
                },
            },
        ),
        # ── Vault tools (Mes Documents) ──
        FunctionDeclaration(
            name="list_vault_documents",
            description="Listar documentos del cofre digital del usuario. USAR cuando pregunta por 'mis documentos', 'qué documentos tengo', 'documentos guardados', o quiere ver su cofre digital.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filtrar por categoría: identity, vehicle, legal, financial, administrative, medical, education, photo, business, employment, other"},
                    "expiry_status": {"type": "string", "description": "Filtrar por estado de expiración: valid, expiring_soon, expired"},
                    "workflow_code": {"type": "string", "description": "Filtrar por trámite compatible (ej: pasaporte_nuevo, residencia)"},
                    "limit": {"type": "integer", "description": "Máximo documentos a mostrar (default 10, max 20)"},
                },
            },
        ),
        FunctionDeclaration(
            name="check_readiness",
            description="Verificar si el usuario tiene todos los documentos necesarios para un trámite. USAR cuando pregunta '¿tengo todo para...?', '¿puedo iniciar...?', 'qué me falta para...'.",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_code": {"type": "string", "description": "Código del trámite (ej: pasaporte_nuevo, residencia, contrato_onrc)"},
                },
                "required": ["workflow_code"],
            },
        ),
        FunctionDeclaration(
            name="get_expiring_documents",
            description="Ver documentos que expiran pronto. USAR cuando pregunta por 'documentos por vencer', 'qué se me vence', 'renovaciones pendientes'.",
            parameters={
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Días hacia adelante (default 90, max 365)"},
                },
            },
        ),
        FunctionDeclaration(
            name="get_vault_stats",
            description="Estadísticas del cofre digital: total documentos, espacio usado, expirados. USAR cuando pregunta 'cuántos documentos tengo', 'espacio disponible', 'estadísticas'.",
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="suggest_next_uploads",
            description="Sugerir documentos que el usuario debería subir a su cofre para maximizar su preparación. USAR cuando pregunta 'qué debería subir', 'cómo mejorar mi cofre', 'qué documentos me faltan'.",
            parameters={"type": "object", "properties": {}},
        ),
        FunctionDeclaration(
            name="prepare_renewal",
            description="Preparar la renovación de un documento que expira. REQUIERE CONFIRMACIÓN del usuario. USAR cuando pide 'renovar mi pasaporte', 'iniciar renovación', o cuando un documento está por vencer y el usuario quiere actuar.",
            parameters={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "ID del documento a renovar"},
                    "workflow_code": {"type": "string", "description": "Código del trámite de renovación (opcional, se deduce del tipo)"},
                },
                "required": ["document_id"],
            },
        ),
        FunctionDeclaration(
            name="get_agent_memory",
            description="Mostrar lo que el asistente ha aprendido sobre las preferencias del usuario. USAR cuando pregunta 'qué sabes de mí', 'mis preferencias', 'qué has aprendido'.",
            parameters={"type": "object", "properties": {}},
        ),
        # ── Appointment Suggestions (Level 2) ──
        FunctionDeclaration(
            name="suggest_appointment_slots",
            description=(
                "Sugerir citas disponibles para un trámite específico. USAR cuando "
                "el usuario dice 'cuándo hay cita para...', 'qué citas tienes para "
                "mi pasaporte', 'proponme fechas', 'necesito una cita la semana "
                "que viene'. Retorna hasta 3 oficinas activas con hasta 4 citas "
                "cada una (máx 12 citas), priorizando la ciudad preferida del "
                "usuario. LEE únicamente — no reserva nada. Requiere el permiso "
                "'suggest_appointments' en los ajustes del asistente (Level 2)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "workflow_code": {
                        "type": "string",
                        "description": (
                            "Código del trámite para el que buscar citas. "
                            "Debe ser uno de los valores de la enum — el asistente "
                            "debe traducir la pregunta del usuario al código "
                            "correspondiente (ej: 'pasaporte nuevo' → "
                            "PASAPORTE_NUEVO)."
                        ),
                        "enum": [
                            "PASAPORTE_NUEVO",
                            "PASAPORTE_RENOVACION",
                            "PASAPORTE_PERDIDA",
                            "PASAPORTE_ROBO",
                            "PASAPORTE_DETERIORO",
                            "CONDUCIR_NUEVO",
                            "CONDUCIR_RENOVACION",
                            "CONDUCIR_CANJE",
                            "CONDUCIR_EXTENSION",
                            "CONDUCIR_DUPLICADO",
                            "RESIDENCIA_PRIMERA_VEZ",
                            "RESIDENCIA_RENOVACION",
                            "FP_CARNET_FUNCIONARIO",
                        ],
                    },
                    "from_date": {
                        "type": "string",
                        "description": (
                            "Fecha mínima a partir de la cual buscar citas, "
                            "en formato ISO YYYY-MM-DD. Opcional — por defecto "
                            "usa la fecha mínima según la regla de delay de la "
                            "entidad. Usar cuando el usuario dice 'a partir "
                            "del 20', 'la semana que viene', 'después del lunes'."
                        ),
                    },
                },
                "required": ["workflow_code"],
            },
        ),
        # ── Workflow Orchestrator (Level 2) ──
        FunctionDeclaration(
            name="auto_prepare_wizard",
            description="Preparar AUTOMATICAMENTE una solicitud de servicio cargando documentos desde el cofre digital del usuario. USAR cuando el usuario dice 'prepárame mi solicitud de...', 'quiero renovar mi...', 'inicia mi trámite de...', 'prepara mi pasaporte', 'quiero sacar residencia'. Este tool CREA una sesión wizard con documentos pre-cargados y formulario pre-rellenado. El usuario solo necesita verificar y pagar.",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": "Nombre del trámite en lenguaje natural (ej: pasaporte, residencia, licencia conducir, contrato, carnet funcionario)"},
                    "solicitud_type": {"type": "string", "description": "Tipo: expedicion, renovacion, duplicado, canje. Si no se indica, se deduce del workflow.", "enum": ["expedicion", "renovacion", "duplicado", "canje", "extension"]},
                    "motivo": {"type": "string", "description": "Motivo (solo para renovaciones): VENCIMIENTO, PERDIDA, ROBO, DETERIORO", "enum": ["VENCIMIENTO", "PERDIDA", "ROBO", "DETERIORO"]},
                    "skip_missing_docs": {"type": "boolean", "description": "Continuar aunque falten documentos (el usuario los agregará en el wizard). Default: false."},
                },
                "required": ["workflow_name"],
            },
        ),
        # ── Executive Tools (Level 3) ──
        FunctionDeclaration(
            name="submit_prepared_request",
            description="Enviar una solicitud preparada previamente con auto_prepare_wizard. USAR SOLO cuando el usuario CONFIRMA explicitamente que quiere enviar ('si, envia', 'confirmo', 'adelante'). NUNCA enviar sin confirmacion explicita.",
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "ID de la sesion wizard preparada previamente"},
                    "payment_method": {"type": "string", "description": "Metodo de pago: cash, mobile_money, card, bank_transfer", "enum": ["cash", "mobile_money", "card", "bank_transfer"]},
                },
                "required": ["session_id"],
            },
        ),
        FunctionDeclaration(
            name="book_appointment",
            description="Reservar una cita para un tramite. USAR SOLO cuando el usuario CONFIRMA fecha y lugar explicitamente.",
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "ID de la sesion wizard"},
                    "location_id": {"type": "string", "description": "ID de la ubicacion (entity_location)"},
                    "appointment_date": {"type": "string", "description": "Fecha: YYYY-MM-DD"},
                    "appointment_time": {"type": "string", "description": "Hora: HH:MM"},
                },
                "required": ["session_id", "appointment_date"],
            },
        ),
    ]
else:
    CHATBOT_AUTH_FUNC_DECLS = []
