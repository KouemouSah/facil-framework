# ADR-0002 — Moteur d'inférence LLM pluggable (OpenAI-compatible)

- **Status** : Accepted
- **Date** : 2026-06-11
- **Related** : `.claude/plans/INFRA_HYBRID_DEPLOY_PLAN.md` (P2/P3/P10), `PHASE_B_LLM_ABSTRACTION.md`

## Context

Le code hérité est couplé à **Vertex AI / Gemini** (`VertexAIManager`). La cible souveraine exige
un LLM **local** (on-premise, données non sortantes), avec GPU. Plusieurs runtimes existent
(Ollama, Docker Model Runner, vLLM, TGI, llama.cpp), aux profils très différents, et la plupart
exposent une **API OpenAI-compatible**.

## Decision

Le backend ne dépend d'**aucun moteur** : il parle **OpenAI-compatible** via l'abstraction
`LLMClient` (Phase B). Le moteur est choisi **par configuration** (`ai.provider`,
`ai.local_inference.engine`) :

- **Dev / single-node** : **Ollama** (ou Docker Model Runner) — DX simple, CPU+GPU.
- **Haute charge GPU (millions)** : **vLLM** ou **TGI** (continuous batching, paged-attention).
  Ollama/DMR (llama.cpp) ont un plafond de débit insuffisant à cette échelle.

Les **poids** se gèrent via `weights_mode` : `pull` (volume), `baked` (dans l'image),
`volume_preseed`. **Air-gapped souverain → `baked` ou `volume_preseed`** (zéro dépendance réseau).

## Consequences

**Positives**
- Aucun verrouillage fournisseur ; bascule Ollama ↔ vLLM ↔ Vertex par config, sans toucher au code.
- Souveraineté (inférence locale) et scalabilité (vLLM) couvertes par la même abstraction.

**Négatives / risques**
- L'abstraction doit gérer les écarts inter-moteurs (function-calling, JSON mode, pricing) — cf
  `PHASE_B_LLM_ABSTRACTION.md`.
- L'inférence GPU ne scale pas comme du HTTP stateless : nécessite pool GPU + file/batching (P10).

## Alternatives

- **Tout-Ollama** — *rejeté* pour la haute charge (débit). Conservé pour dev/single-node.
- **Tout-managé (Vertex/Bedrock)** — *rejeté* comme défaut souverain (données sortantes), conservé
  comme **fallback** de pic.
