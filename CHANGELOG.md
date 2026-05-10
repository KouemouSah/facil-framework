# Changelog

All notable changes to Facil Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Status

🚧 Pre-bootstrap. Active development has not started. Initial commits are planning artifacts and the snapshot of code reused from TaxasGE.

### Planning

- 19 detailed phase plans (A → N.5) under task-decomposition-expert format
- Product Requirements Document (`docs/PRD.md`)
- BPMN process diagrams (`docs/BPMN.md`)
- Inventory of code reused from TaxasGE (`docs/REUSE_FROM_TAXASGE.md`)
- 18 improvements over TaxasGE documented (`docs/IMPROVEMENTS_OVER_TAXASGE.md`)

## [0.0.1] — 2026-05-10

### Added

- Initial repository bootstrap from TaxasGE snapshot
- AGPL-3.0 license
- Profile structure stubs (`profiles/{empty,private-services-company,gov-emergent-country,saas-multitenant,banking}/`)
- Tools directory placeholder (`tools/`)
- Documentation skeleton (`docs/`)
- GitHub repository created (private)
- CI workflows (backend, frontend, CodeQL, stale)
- Issue and PR templates
- Contributing guide, Code of Conduct, Security policy

### Notes

This is a non-functional snapshot. The codebase under `packages/` is copied from TaxasGE and contains gov-specific seeds and modules that will be progressively abstracted in Phase A.5 onward.

[Unreleased]: https://github.com/KouemouSah/facil-framework/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/KouemouSah/facil-framework/releases/tag/v0.0.1
