# Workflow Templates — `gov-emergent-country` profile

> **Status** : skeleton. Templates to be implemented by **Phase H** (Workflow Designer) + **Phase O** (ERP) + **Phase P** (Audit chain) + **Phase R** (Banking) + **Phase T** (Recours / Formation).

## Available templates (skeletons)

| File | Workflow | Phase |
|---|---|---|
| `recettes_collection.json` | Treasury revenue collection (PIMEPE-style: agent → IUI → audit chain → bank → reconcile → closed) | O + P + Q + R |
| `recours_administratif.json` | Citizen administrative appeal (submit → assign → review → decision → notify → close) | T.3 |
| _(planned)_ `depenses_engagement.json` | Treasury expense commitment (agent enters engagement → 4-eyes validation → ERP post → payment) | O + P |
| _(planned)_ `reclamation_simple.json` | Simple complaint workflow (lighter than recours) | T.3 |
| _(planned)_ `demande_echeancier.json` | Citizen requests installment payment plan | T.3 |

## How to use

1. Templates are loaded by **Phase H Workflow Designer** at first boot
2. Operator can customize per-tenant via Studio UI (drag-drop or YAML editor)
3. Each transition can trigger side effects (post audit chain, sync ERP, send notification, etc.)

## Schema

See `$schema` field in each JSON (when finalized in Phase H).

## Notes

- All templates support multi-language labels (es / fr / en) — extend per country
- All transitions are logged in audit chain (Phase P)
- Required features must be enabled in `install.yaml` before workflow can run
- Operator can disable specific templates by removing them from `install.yaml` → `seeds.workflow_templates`
