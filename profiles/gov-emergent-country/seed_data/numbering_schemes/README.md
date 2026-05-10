# Numbering Schemes — `gov-emergent-country` profile

> **Status** : skeleton. Schemes to be implemented by **Phase Q** (Government Numbering & Public Accounting).

## Available templates

| File | Scheme | Use case |
|---|---|---|
| `module_11.json` | Module 11 (weights 2-7 cycle) | Government revenue/expense IDs (IUI/IUG style — PIMEPE TDR §2.2.4.1.4) |
| _(planned)_ `nif_es.json` | Spanish NIF | Citizens / business identifiers Spain-style |
| _(planned)_ `siret_fr.json` | French SIRET (Luhn 14) | Business identifiers France-style |
| _(planned)_ `rccm_ohada.json` | OHADA RCCM | Business registry OHADA region |
| _(planned)_ `luhn.json` | Luhn (cards) | Bank cards |

## How to add a country-specific scheme

1. Copy `module_11.json` as starting template
2. Define your `format` template, `fields`, and `checksum_algorithm`
3. Add the file to `install.yaml` → `features.numbering_schemes.available`
4. Test with Phase Q's `NumberingScheme.validate()` (no collision on 10k+ generated IDs)

## When this matters

For each country, the operator must validate :
- Format prefix and organization code conventions match local administrative practice
- Check digit algorithm is recognized by partner systems (banks, tax authorities)
- Sequence counter strategy (per organization / per year / per type) matches workflow

Cross-reference [pre-project audit checklist §2 (ERP)](../../../../docs/audit-templates/PRE_PROJECT_AUDIT_CHECKLIST.md) — your ERP must accept the chosen numbering format in journal entry references.
