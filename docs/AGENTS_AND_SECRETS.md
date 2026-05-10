# AI Agents & Secrets

This document describes the AI agent workflows configured for Facil Framework. **All use GitHub Models free tier — no external API key, no payment required.**

## TL;DR

| Component | Cost | Status |
|-----------|------|--------|
| CI / structure check | $0 | ✅ active |
| Issue automation (epic checkboxes, milestone progress, auto-label) | $0 | ✅ active |
| Agent — PR Reviewer | $0 (GitHub Models free tier) | ✅ active when secret is provided* |
| Agent — Issue Triage | $0 (GitHub Models free tier) | ✅ active |
| Agent — Discussion Helper | $0 (GitHub Models free tier) | ✅ active |
| GitHub Copilot Coding Agent | $10/month (Copilot Pro) | ⏸ optional |
| CodeQL Security Analysis | $0 if public, $$ for private | ⏸ disabled (private + Free tier) |

\* GitHub Models requires no setup beyond the workflow `permissions: models: read`. Workflows use the auto-provided `GITHUB_TOKEN`.

## How GitHub Models works

[GitHub Models](https://docs.github.com/en/github-models) is GitHub's free model marketplace launched 2024. It provides programmatic access to OpenAI, Meta Llama, Microsoft Phi, Mistral and other models from GitHub Actions.

- **Free tier**: ~150 requests/day per model, ~10K tokens/request
- **Paid tier (GitHub Models Premium)**: higher limits, paid by usage
- **Auth**: `GITHUB_TOKEN` with `models: read` permission scope (no API key)
- **Action**: [`actions/ai-inference@v1`](https://github.com/actions/ai-inference)

For solo dev V0 volume (a few PRs / issues / discussions per week), free tier is more than enough.

## Models used

All 3 agent workflows use **`openai/gpt-4o-mini`** by default:

- Fast (~2s response)
- Cheap (counted as 1 unit per request on free tier)
- Reasoning quality good enough for review / triage / discussion

To switch model, edit the `model:` line in any workflow. Available models:

| Model | Use case |
|-------|----------|
| `openai/gpt-4o-mini` | Fast generalist (default) |
| `openai/gpt-4o` | Higher quality, lower rate limits |
| `meta/Llama-3.3-70B-Instruct` | Open-weights alternative |
| `mistral-ai/Mistral-Large-2411` | Strong reasoning |
| `microsoft/Phi-3.5-mini-instruct` | Smallest, fastest |
| `deepseek/DeepSeek-V3-0324` | Strong code understanding |

Browse all: https://github.com/marketplace?type=models

## Agent #1 — PR Reviewer

**File:** `.github/workflows/agent-pr-reviewer.yml`

**Triggers:** PR opened / synchronize / ready_for_review (skips drafts, forks, `skip-review` label)

**Behaviour:** Posts a structured review comment on the PR:

- Summary (1 paragraph)
- Risk assessment (🟢/🟡/🔴) with justification
- Concerns by category (Security · Correctness · Performance · Architecture · Tests · Docs)
- Specific code suggestions
- Verdict (Approve / Approve with comments / Request changes)

**Diff input:** truncated to 30K chars to fit free-tier context window.

**Output:** max 1500 tokens.

## Agent #2 — Issue Triage

**File:** `.github/workflows/agent-issue-triage.yml`

**Triggers:** Issue opened or reopened (skips epics, `skip-triage` label)

**Behaviour:**

1. Fetches up to 30 open issues for duplicate detection
2. Asks gpt-4o-mini for triage decision in JSON format
3. Applies suggested labels (validated against the official taxonomy)
4. Sets milestone if applicable
5. Posts a triage comment with summary, duplicate flag, clarifying questions, suggested action
6. Removes the `triage` label after successful processing

**Output:** max 800 tokens.

## Agent #3 — Discussion Helper

**File:** `.github/workflows/agent-discussion-helper.yml`

**Triggers:** New discussion or new discussion comment (humans only — bot loops are filtered out)

**Behaviour:** Posts a senior-architect response based on Facil Framework knowledge embedded in the system prompt: cites phases, challenges assumptions, ends with concrete next step.

**Output:** max 600 tokens.

## Native GitHub Copilot Coding Agent

The `/agents` tab on the repo is the **GitHub Copilot Coding Agent** feature.

- URL: https://github.com/KouemouSah/facil-framework/agents
- Requires: **Copilot Pro subscription ($10/month)** or higher
- How it works: assign an issue to "Copilot" → it creates a draft PR with proposed changes
- **Trade-offs vs the custom GitHub Models workflows above:**
  - ✅ Native UI, no workflow code to maintain
  - ✅ Can directly write code (create PRs), not just review
  - ❌ Requires paid Copilot Pro subscription
  - ❌ Cannot configure custom roles/personalities (single agent)
  - ❌ Less control over prompts and behaviour

**Recommendation:** stay on **free GitHub Models workflows** for V0 (review / triage / discussion). Re-evaluate Copilot Coding Agent when active dev starts and code-writing automation becomes valuable.

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

A user-level PAT is **not currently needed** for this repo. The auto-provided `GITHUB_TOKEN` covers everything:

- Issues / PRs / milestones / comments / discussions
- Labels / project boards
- Repo metadata
- GitHub Models inference (with `models: read` permission scope)

A fine-grained PAT would be needed only if:

- Cross-repository automation (e.g., sync `taxasge` → `facil-framework`)
- API rate limit issues (rare for solo dev)
- Acting as a different identity than the `github-actions[bot]`

If needed later, create a fine-grained PAT at https://github.com/settings/tokens?type=beta with minimal scopes.

## Variables (non-secret config)

None required at V0. Future candidates:

| Variable | Purpose | Default |
|----------|---------|---------|
| `AGENT_MODEL` | Override model used by agents | `openai/gpt-4o-mini` |
| `AGENT_LANGUAGE` | Response language | `en` |
| `MAX_REVIEW_TOKENS` | PR review output budget | `1500` |

To add a variable: Settings → Secrets and variables → Actions → Variables tab.

## Rate limit monitoring

GitHub Models free tier limits per model per day. If hit, the workflow logs a 429 error and the agent comment is skipped. Subsequent triggers retry tomorrow.

To monitor usage and switch to a less-loaded model if needed:

- Models marketplace: https://github.com/marketplace?type=models
- Workflow run logs: https://github.com/KouemouSah/facil-framework/actions

If volume grows past free tier, options:

1. Switch to a cheaper model (e.g., Phi-3.5-mini)
2. Throttle workflow triggers (e.g., only on `synchronize` after `opened`)
3. Upgrade to GitHub Models Premium (paid)

## Honest disclaimer

GitHub does not natively support multiple "agent personalities" debating each other in one repo. Each workflow above is one model call configured for one specific role. To add a new role, create a new workflow file using `actions/ai-inference@v1`.

The native GitHub Copilot Coding Agent is a separate paid feature that can directly write code in PRs — the agents above only comment / review / triage, they do not modify code. That separation is intentional for V0 safety.
