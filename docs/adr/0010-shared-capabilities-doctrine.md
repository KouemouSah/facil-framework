# ADR-0010 — Doctrine des capacités partagées (où vit un outil, quand on l'introduit)

- **Statut** : Proposé (2026-07-15)
- **Décideurs** : KouemouSah (owner), Claude Code (analyse)
- **Contexte lié** : ADR-0001 (monolithe modulaire), ADR-0002 (inférence pluggable),
  ADR-0003 (secrets OpenBao), ADR-0005 (storage MinIO). Complète, ne remplace aucun.
- **Portée** : tout « outil / bibliothèque / service partagé » candidat à l'ajout
  (moteur de workflow, moteur de règles, signature, horodatage, hash-chain, Kafka,
  Elasticsearch, vision/YOLO, anonymisation, OLAP, RPA, pipeline d'ingestion, etc.).

---

## 1. Contexte

Une question récurrente : *« ces outils partagés par plusieurs modules, faut-il les mettre
directement dans l'infra ? tous ? ou par activation (toggle) ? »*

Cette question repose sur un cadre mental **trop plat** (« l'infra » comme un seul bac où
tout s'empile). Le produit vise l'inverse : un socle **souverain, léger, on-premise,
customisable sans code**, déployable pour des profils très différents (gov / enterprise /
SaaS / banking / telco / HR). Tout précharger contredirait cet objectif : chaque déploiement
porterait des services que 90 % des profils n'utilisent jamais (RAM, surface d'attaque, ops).

Le mécanisme d'activation existe déjà par conception : **Module Loader** (`MODULES_ENABLED`,
livré en Phase D3), **Provider Abstractions** (ABC pluggables), **Profiles**, et **services
compose/Helm profile-gated**. La vraie question n'est donc pas *si* on toggle, mais **dans
quelle couche** chaque outil tombe et **à quel moment** on le construit.

## 2. Décision

### 2.1 — Cinq couches, pas « l'infra »

Tout outil partagé appartient à **exactement une** de ces couches. Le classement dicte où il
vit, comment on l'active, et son coût d'activation.

| Couche | Nature | Emplacement | Activation | Coût |
|---|---|---|---|---|
| **Middleware core** | Transverse à *tous* les modules | Le noyau, toujours actif | Non-toggleable (c'est le cœur) | Fait partie du socle |
| **Service d'infra** | Un conteneur qui consomme RAM/CPU | Compose profile / template Helm | Toggle **au déploiement** | RAM + ops |
| **Provider (ABC)** | Code derrière une interface | `core/providers/…` + registry BD | Toggle **runtime** (config-store) | 1 lib + config |
| **Module métier** | Routers + permissions + schéma | `app/modules/…` | `MODULES_ENABLED` | Migrations (restent en BD) |
| **Profile** | Sélection cohérente des ci-dessus | `install.yaml` + seeds | Choisi à l'installation | — |

Un outil peut relever de **deux** couches : un moteur de workflow = un **service d'infra**
(le moteur, ex. Zeebe) **+** un **module** (le designer + l'intégration).

### 2.2 — Test de décision (à appliquer à CHAQUE candidat)

1. **« Tous les modules en dépendent-ils ? »** → oui = *middleware core* (audit, RBAC, config-store, field-schema).
2. **« Est-ce un processus qui tourne (conteneur) ? »** → oui = *service d'infra*, **profile-gated, OFF par défaut**.
3. **« Est-ce une implémentation interchangeable d'un contrat ? »** → oui = *provider (ABC)*, déclaré dans le registry, instancié via config-store.
4. **« Est-ce une capacité métier avec ses endpoints/schéma ? »** → oui = *module*, activé par `MODULES_ENABLED`.
5. **« Existe-t-il AUJOURD'HUI un module qui l'appelle ? »** → **non = on définit le contrat (ABC/flag) mais on NE déploie PAS.** Un service sans consommateur = RAM immobilisée + surface d'attaque, pas une capacité.

### 2.3 — Règle de séquençage (quand introduire)

1. **Services cœur dont tout module dépend** → dans le socle, immédiatement. *(Déjà fait :
   Postgres, Redis, config-store, audit, RBAC, field-schema, abstractions storage/secrets/LLM.)*
2. **Capacité avec un module consommateur concret** → construite **avec** ce module, jamais « au cas où ».
3. **Services d'infra lourds** (Kafka, Elasticsearch, moteur BPMN, OLAP) → **différés** jusqu'à
   une charge réelle, **et** toujours profile-gated, **jamais** actifs par défaut. Les ajouter
   sans consommateur = scaling prématuré (anti-pattern).

### 2.4 — Invariants (non négociables)

- **Aucun préchargement dans le socle** d'un outil relevant des couches 2/3/4. Le socle ne
  contient que du *middleware core*.
- **OFF par défaut** pour tout service d'infra et tout provider non-cœur. Le profil `empty`
  démarre le strict minimum.
- **Un provider se déclare avant de se déployer** : l'ABC + l'entrée registry peuvent exister
  sans que le service tourne (test 5).
- **Parité compose ⇄ Helm** : si un service est profile-gated côté compose, il DOIT avoir un
  template Helm correspondant (sinon le flag `enabled:` est un mensonge — cf. dette Helm actuelle).

### 2.5 — Corrections de concepts (à figer)

- **OpenBao ≡ HashiCorp Vault** (fork open-source). On n'en fait **pas** tourner deux. Un client
  exigeant Vault Enterprise = simple bascule du `SecretsProvider` (ABC), zéro nouveau service.
- **BPMN (workflow) ≠ DMN (règles)** : deux moteurs distincts. Ne pas supposer qu'un seul couvre les deux.
- **Confiance documentaire = une préoccupation, trois facettes** : signature (XAdES/PAdES),
  horodatage (TSA RFC 3161), inviolabilité (hash-chain). À regrouper conceptuellement
  (providers `Signature`/`Timestamp` + extension hash-chain de l'audit core), pas à éparpiller.
- **Anonymisation ≠ OLAP** : confidentialité (middleware egress LLM) vs analytique (BI). Sans rapport.
- **RPA** : par défaut YAGNI. Une intégration API bat la RPA dans la quasi-totalité des cas.
  N'entre qu'en présence d'un système-cible sans API identifié (couche *adaptateur externe*).

## 3. Application à la liste courante (référence)

| Outil | Vrai concept | Couche | Décision |
|---|---|---|---|
| Camunda / workflow | Moteur **BPMN** | Infra + module | Différé (Phase H). Préférer léger/embarqué avant d'imposer Zeebe. |
| Drools / OpenRules | Moteur de **règles (DMN)** | Provider ou module | Non planifié → à cadrer (cf. `docs/DECISION_MODEL.md`). JVM = friction. |
| RPA | Automatisation robotisée | Adaptateur externe | YAGNI sauf cible sans API. |
| XAdES / PAdES | Signature | Provider `SignatureProvider` | Avec le module document (Phase N.5). |
| TSA RFC 3161 | Horodatage | Provider `TimestampProvider` | Facette « confiance documentaire ». |
| Hash chain | Journal inviolable | Middleware core (extension audit) | Phase P. Durcit `audit.record` existant. |
| Elasticsearch | Recherche | Infra | Postgres FTS + pgvector d'abord. ES à l'échelle, gated. |
| YOLO26 | Vision | Provider IA | Seulement si un module consomme la vision. |
| HashiCorp Vault | Secrets | — | Redondant avec OpenBao. Rien à ajouter. |
| Anonymisation | DLP egress | Middleware couche LLM | Greffe sur le routing LLM. |
| Cube OLAP | BI | Infra | Différé. |
| File processing legacy | Ingestion documentaire | Module | Prolonge SP1 field-schema (fait) + Phase N. |

## 4. Conséquences

**Positives**
- Chaque déploiement ne porte que ce que son profil réclame → léger, souverain, moins de surface.
- Un cadre opposable : aucune capacité n'est ajoutée hors de ce classement + test de décision.
- Élimine les redondances (OpenBao/Vault) et les mélanges de concepts avant qu'ils ne coûtent.

**Négatives / coûts**
- Discipline requise : refuser l'ajout « au cas où » demande de tenir la ligne (test 5).
- La parité compose⇄Helm impose du travail de template à chaque service gated (dette actuelle à solder).
- Certaines capacités attendront leur module consommateur (frustration possible côté roadmap).

**À solder avant tout nouvel outil** (dettes de cohérence, cf. plan `INFRA_COHERENCE_DEBT_PLAN.md`)
1. Réconcilier **config de déploiement (`config.yaml`) ↔ config runtime (config-store BD)** :
   aujourd'hui les providers choisis à l'infra ne sont pas seedés dans `provider_settings`.
2. Combler l'**asymétrie Helm** (templates keycloak/otel-grafana/ollama/mail/caddy manquants).
3. Clore **`feat/infra-p2-safe-update`** (backup/rollback k3s) après réconciliation avec le
   `k3s.py` de develop.

## 5. Alternatives écartées

- **Tout précharger dans l'infra** : contredit l'objectif produit (léger/souverain). Rejeté.
- **Tout en modules, rien en provider** : perdrait l'interchangeabilité (secrets/storage/LLM)
  et forcerait des migrations pour des choix qui sont de la config. Rejeté.
- **Marketplace / installation depuis URL externe** : risque supply-chain (cf. politique
  agents/skills du CLAUDE.md). Hors périmètre pour l'instant.
