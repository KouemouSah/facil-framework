# AI Agents & Secrets

This document describes the AI agent workflows configured for Facil Framework. **All use GitHub Models free tier — no external API key, no payment required.**

## Overview

| Agent | Model | Trigger | Status |
|-------|-------|---------|:---:|
| PR Reviewer | Claude 3.5 Sonnet | Every non-draft PR | active |
| Security Review | Claude 3.5 Sonnet | PRs touching auth / crypto / signatures / migrations / SQL OR `security` label | active |
| Code Quality Review | Claude 3.5 Sonnet | PRs touching production code OR `code-review` label | active |
| Issue Triage | Ministral 3B | New / reopened issue | active |
| Discussion Helper | Claude 3.5 Sonnet | New discussion or comment (humans only) | active |
| Issue/Milestone Automation | (no AI) | Issue close, PR merge, push to main | active |

## Cost summary

**$0 for all 5 AI agents.** GitHub Models free tier covers expected solo-dev volume.

| Component | Cost | Source |
|-----------|------|--------|
| All 5 AI agents | $0 | GitHub Models free tier (`models: read` permission, auto `GITHUB_TOKEN`) |
| CI / structure / link / spell / SAST | $0 | GitHub Actions free minutes |
| Issue automation | $0 | Built-in `actions/github-script` |
| GitHub Copilot Coding Agent (optional, separate from above) | $10/month | Copilot Pro subscription |
| CodeQL on private repo (optional, currently disabled) | $$ | Advanced Security |

## How GitHub Models works

[GitHub Models](https://docs.github.com/en/github-models) is GitHub's free model marketplace launched 2024. It provides programmatic access to OpenAI, Anthropic Claude, Meta Llama, Mistral, Microsoft Phi, DeepSeek and other models from GitHub Actions.

- **Free tier**: ~150 requests/day per model, ~10K tokens/request typical
- **Auth**: `GITHUB_TOKEN` with `models: read` permission scope (no API key)
- **Action**: [`actions/ai-inference@v1`](https://github.com/actions/ai-inference)
- **Premium tier**: higher limits, paid by usage

## Available models

Browse all: <https://github.com/marketplace?type=models>

| Model ID | Provider | Best for |
|----------|----------|----------|
| `anthropic/claude-3-5-sonnet` | Anthropic | Code reasoning, architecture, security analysis (used by PR/Security/Code/Discussion agents) |
| `anthropic/claude-3-5-haiku` | Anthropic | Faster Claude, cheaper context |
| `openai/gpt-4o` | OpenAI | Generalist, balanced |
| `openai/gpt-4o-mini` | OpenAI | Fast generalist |
| `openai/gpt-4.1` | OpenAI | Long context |
| `mistral-ai/Mistral-large-2411` | Mistral | Strong reasoning, multilingual |
| `mistral-ai/Codestral-2501` | Mistral | Code-focused |
| `mistral-ai/Ministral-3B` | Mistral | **Tiny, fast, perfect for triage** (used by Issue Triage agent) |
| `mistral-ai/Mixtral-8x22B-Instruct-v0.1` | Mistral | Open-weights MoE |
| `meta/Llama-3.3-70B-Instruct` | Meta | Open-weights alternative |
| `meta/Llama-3.1-405B-Instruct` | Meta | Largest open-weights |
| `microsoft/Phi-3.5-mini-instruct` | Microsoft | Smallest, fastest |
| `microsoft/Phi-4` | Microsoft | Reasoning-focused |
| `deepseek/DeepSeek-V3-0324` | DeepSeek | Code understanding |
| `cohere/Command-R-Plus` | Cohere | RAG-tuned |
| `ai21/Jamba-1.5-Large` | AI21 | Long context (256K) |

## Agent #1 — PR Reviewer (general)

**File:** `.github/workflows/agent-pr-reviewer.yml`
**Model:** `anthropic/claude-3-5-sonnet`

**Triggers:** PR opened / synchronize / ready_for_review (skips drafts, forks, `skip-review` label)

**Output sections:** Summary · Risk · Concerns (per category) · Suggestions · Verdict

## Agent #2 — Security Review

**File:** `.github/workflows/agent-security-review.yml`
**Model:** `anthropic/claude-3-5-sonnet`

**Triggers:** PRs touching security-sensitive paths OR `security` label:

- `packages/backend/app/modules/auth/**`
- `packages/backend/app/modules/permissions/**`
- `packages/backend/app/modules/rbac/**`
- `packages/backend/app/core/secrets.py`
- `packages/backend/app/core/auth_provider.py`
- `packages/backend/app/core/signature/**`
- `packages/backend/app/core/payment_gateway.py`
- `packages/backend/app/database/connection.py`
- `packages/backend/migrations/**`
- `**/*.sql`
- `.github/workflows/**`

**Output sections:** Threat assessment · Findings (CWE-tagged, severity-grouped) · Compliance check · Verdict

**Coverage:** OWASP Top 10, CWE references, eIDAS-aware crypto checks, asyncpg parameterized queries enforcement, lock ordering rules from TaxasGE memory.

## Agent #3 — Code Quality Review

**File:** `.github/workflows/agent-code-review.yml`
**Model:** `anthropic/claude-3-5-sonnet`

**Triggers:** PRs touching production code (`packages/{backend,web,mobile,inspector}/**`) OR `code-review` label.

**Output sections:** Quality rating · Findings by category · Patterns to encourage · Refactor opportunities · Test coverage suggestions · Verdict

**Dimensions:** SOLID, architecture compliance (Module Loader, abstractions), performance, complexity, naming, error handling, testability, type safety, async correctness, style.

## Agent #4 — Issue Triage

**File:** `.github/workflows/agent-issue-triage.yml`
**Model:** `mistral-ai/Ministral-3B`

**Triggers:** Issue opened / reopened (skips epics, `skip-triage` label).

**Why Ministral 3B:** issue triage is structured (JSON output, label classification), small model is sufficient and faster. Saves Claude quota for review-heavy tasks.

**Behaviour:** Fetches up to 30 open issues for duplicate detection, applies labels + milestone, posts triage comment with summary / clarifying questions / suggested action, removes `triage` label.

## Agent #5 — Discussion Helper

**File:** `.github/workflows/agent-discussion-helper.yml`
**Model:** `anthropic/claude-3-5-sonnet`

**Triggers:** New discussion or new discussion comment (humans only — no bot loops).

**Behaviour:** Posts a senior-architect response based on Facil Framework knowledge embedded in the system prompt: cites phases, challenges assumptions, ends with concrete next step.

## Issue / Milestone automation (no AI)

**File:** `.github/workflows/automation-issue-tracking.yml`

Pure GitHub Actions logic, no model calls:

- Auto-checks epic checklist boxes when child issue closes
- Comments milestone progress on PR merge + auto-closes 100% milestones
- Auto-labels new issues by content keywords (component / security)
- Closes issues from `Closes #N` keywords in commit messages on main

## Adding more agent roles

To add a new role (e.g., docs reviewer, performance auditor):

1. Copy `agent-pr-reviewer.yml` → `agent-{role}.yml`
2. Edit the `system-prompt:` for the new role
3. Adjust `paths:` filter or `if:` condition for the trigger
4. Choose appropriate model (Claude for nuanced review, Mistral/Phi for simple classification)

No new secrets needed — `GITHUB_TOKEN` + `models: read` permission covers all GitHub Models access.

## Native GitHub Copilot Coding Agent

The `/agents` tab on the repo is a separate paid feature.

- URL: <https://github.com/KouemouSah/facil-framework/agents>
- Requires: **Copilot Pro subscription ($10/month)** or higher
- How it works: assign an issue to "Copilot" → it creates a draft PR with proposed changes
- **Trade-offs vs the custom GitHub Models workflows above:**
  - Native UI, no workflow code to maintain
  - Can directly write code (create PRs), not just review
  - Requires paid Copilot Pro subscription
  - Cannot configure custom roles/personalities (single agent)
  - Less control over prompts and behaviour

**Recommendation:** stay on **free GitHub Models workflows** for V0 (review / triage / discussion / security / code). Re-evaluate Copilot Coding Agent when active dev starts and code-writing automation becomes valuable.

## Future secrets (Phase L+M)

When deployment workflows are added at Phase L (E2E) and M (release):

| Secret | Purpose | When |
|--------|---------|------|
| `GCP_SA_KEY` | Cloud Run deploy | Phase D / L |
| `DOCKER_HUB_TOKEN` | Image push | Phase L |
| `EAS_TOKEN` | Mobile builds | Phase K |
| `NPM_TOKEN` | Publish framework SDK | Phase M (if relevant) |
| `PYPI_TOKEN` | Publish backend SDK | Phase M (if relevant) |

**None required for V0.**

## Personal Access Token (PAT)

A user-level PAT is **not currently needed**. The auto-provided `GITHUB_TOKEN` covers everything:

- Issues / PRs / milestones / comments / discussions
- Labels / project boards
- Repo metadata
- GitHub Models inference (with `models: read` permission scope)

A fine-grained PAT would be needed only if:

- Cross-repository automation (e.g., sync `taxasge` → `facil-framework`)
- API rate limit issues (rare for solo dev)
- Acting as a different identity than `github-actions[bot]`

Create a fine-grained PAT at <https://github.com/settings/tokens?type=beta> with minimal scopes if needed later.

## Variables (non-secret config)

None required at V0. Future candidates:

| Variable | Purpose | Default |
|----------|---------|---------|
| `AGENT_PRIMARY_MODEL` | Override main reviewer model | `anthropic/claude-3-5-sonnet` |
| `AGENT_TRIAGE_MODEL` | Override triage model | `mistral-ai/Ministral-3B` |
| `AGENT_LANGUAGE` | Response language | `en` |
| `MAX_REVIEW_TOKENS` | PR review output budget | `1500` |

To add a variable: Settings → Secrets and variables → Actions → Variables tab.

## Rate limit monitoring

GitHub Models free tier limits per model per day. If hit, the workflow logs a 429 error and the agent comment is skipped.

If volume grows past free tier, options:

1. Switch to a cheaper model (e.g., `microsoft/Phi-3.5-mini-instruct`)
2. Throttle workflow triggers (e.g., only on `synchronize` after `opened`)
3. Upgrade to GitHub Models Premium (paid)
4. Distribute load across multiple models (already done — Mistral for triage, Claude for review)

## Honest disclaimer

GitHub does not natively support multiple "agent personalities" debating each other in one repo. Each workflow above is one model call configured for one specific role. To add a new role, create a new workflow file using `actions/ai-inference@v1`.

The native GitHub Copilot Coding Agent is a separate paid feature that can directly write code in PRs. The agents above only comment / review / triage — they do not modify code. That separation is intentional for V0 safety.
