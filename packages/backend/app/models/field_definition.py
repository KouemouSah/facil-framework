"""field_definition — user-defined fields, ALWAYS scoped to one organisation.

Storage strategy (spec §6): the VALUES live in the row's own `custom_fields`
JSONB column; only the DEFINITIONS live here. Odoo does ALTER TABLE at runtime —
in a single shared DB that adds a physical column visible to every tenant, locks
the table in production, and makes migrations unmanageable. We emit no mutating
DDL at all; the only DDL is an additive, concurrent, partial expression index.

`organization_id` is NOT NULL — the formal statement of tenant isolation. No row
can exist "above" the organisations, so no row can cross them: there is no such
thing as a global custom field.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, UUIDAuditBase


class FieldDefinition(UUIDAuditBase):
    __tablename__ = "field_definition"
    __table_args__ = (
        UniqueConstraint("organization_id", "target", "key",
                          name="uq_field_definition_org_target_key"),
    )

    # NOT NULL — the formal statement of isolation. No global custom field exists.
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True)

    # e.g. "site.custom_fields", "organization.custom_fields" — which extensible
    # entity + column this definition belongs to.
    target: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    widget: Mapped[str] = mapped_column(String(30), nullable=False, default="plain")

    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    label_fr: Mapped[str] = mapped_column(Text, nullable=False)
    label_es: Mapped[str] = mapped_column(Text, nullable=False)
    hint_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_es: Mapped[str | None] = mapped_column(Text, nullable=True)

    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    rules: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    options: Mapped[list] = mapped_column(JSONType, nullable=False, default=list)
    relation_resource: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    relation_filter: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

    group: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    col_span: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    indexed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # none | pending | ready | failed. A field whose index is not `ready` is NOT
    # offered for sorting — explicitly unavailable, never silently slow.
    index_state: Mapped[str] = mapped_column(String(10), nullable=False, default="none")

    inherit_to_suborgs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Archive, never destroy: the field leaves the form, the VALUES stay in JSONB.
    # A later, separate, audited task adds an explicit purge.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def as_spec(self) -> dict:
        """DB row -> FieldSpec dict (the wire format the resolver and UI speak).

        Carries `index_state` (not just `indexed`): `sortable_keys()` (a later
        task) reads it off the resolved spec — a field is only offered for
        sorting once its index is actually READY, never merely requested.
        """
        return {
            "key": self.key, "type": self.type, "widget": self.widget,
            "label": {"en": self.label_en, "fr": self.label_fr, "es": self.label_es},
            "hint": {"en": self.hint_en or "", "fr": self.hint_fr or "",
                     "es": self.hint_es or ""},
            "required": self.required, "default": self.default,
            "rules": self.rules or {}, "options": self.options or [],
            "relation_resource": self.relation_resource or "",
            "relation_filter": self.relation_filter or {},
            "group": self.group, "order": self.order, "col_span": self.col_span,
            "indexed": self.indexed, "index_state": self.index_state,
        }
