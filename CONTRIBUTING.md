# Contributing to Facil Framework

> 🚧 **Pre-bootstrap status** — active development has not yet started. The framework is undergoing planning and architectural design. Public contributions will open once Phase A.5 (Module Loader) lands.

Thank you for your interest in contributing to Facil Framework. This document explains how to get involved as the project moves from planning to implementation.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Report unacceptable behavior to libressai@gmail.com.

## License

By contributing, you agree that your contributions will be licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE).

If you contribute code that you intend to be relicensed under the Cloud SaaS or Enterprise tier, you must sign the Contributor License Agreement (CLA) — process to be defined post-V1.

## How to contribute

### Reporting bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Before reporting:

1. Search existing issues to avoid duplicates
2. Confirm the bug on the latest `main` commit
3. Provide minimal reproduction steps
4. **Never include credentials, tokens, or production data** in bug reports

### Suggesting features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml). Before requesting:

1. Check the [ROADMAP](ROADMAP.md) — your idea may be planned
2. Search Discussions for prior conversations
3. Be specific about the *problem* you're solving, not just the solution

### Reporting security vulnerabilities

**Do not open a public issue.** See [SECURITY.md](SECURITY.md) for the private disclosure process.

### Submitting pull requests

#### Branching strategy

- `main` — protected, production-ready (or planning artifacts during pre-bootstrap)
- `develop` — integration branch (created when active dev begins)
- `feature/<short-name>` — your work branch

#### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

Example:
```
feat(workflows): add JSON import endpoint

Adds /api/v1/customize/workflows/import for Studio Designer round-trip.

Closes #42
```

#### Before opening a PR

- [ ] Tests pass locally (`pytest` / `npm test`)
- [ ] Type checks pass (`mypy app` / `npm run type-check`)
- [ ] Lint passes (`ruff` / `eslint`)
- [ ] CHANGELOG updated if user-visible
- [ ] Docs updated if API surface changed
- [ ] CODEOWNERS reviewers tagged

PRs must pass CI before merge. Squash merge is the default — keep your final commit message clean.

## Development setup

> Will be expanded once Phase A.5 lands. For now:

```bash
# Clone (when public)
git clone https://github.com/KouemouSah/facil-framework.git
cd facil-framework

# Backend
cd packages/backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest

# Frontend (from repo root)
npm install --legacy-peer-deps
cd packages/web
npm run dev

# Docker local (full stack)
cd deploy
python init.py --profile=empty --non-interactive
docker compose up
```

## Architecture decisions

Major architectural decisions are documented as ADRs in `docs/adr/` (to be created). Substantive changes to the framework architecture must be proposed via an RFC issue first.

## Getting help

- 📚 Read the [PRD](docs/PRD.md), [BPMN](docs/BPMN.md), [ROADMAP](ROADMAP.md)
- 💬 Open a [Discussion](https://github.com/KouemouSah/facil-framework/discussions) for general questions
- 🐛 Open a bug or feature issue using the templates

## Style guide (placeholder)

To be expanded:

- Python: `black` + `ruff` + `mypy --strict`
- TypeScript: ESLint + Prettier
- Naming: `snake_case` Python, `camelCase` TypeScript, `kebab-case` filenames
- Commits: present tense imperative ("add", "fix", not "added", "fixes")
