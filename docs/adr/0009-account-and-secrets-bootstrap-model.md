# ADR-0009 — Modèle de bootstrap des comptes & des secrets

- **Status** : Accepted
- **Date** : 2026-06-18
- **Related** : ADR-0003 (secrets & cloud), ADR-0006 (k3s + PKI interne), ADR-0007 (chiffrement at-rest), `docs/architecture-notes/KEYCLOAK_INTEGRATION.md`, `.claude/plans/SECRETS_VAULT_KEYCLOAK_INTEGRATION_PLAN.md`

## Context

Le framework se déploie dans des environnements multiples (gov / enterprise / SaaS /
banking). Deux questions de bootstrap reviennent à chaque déploiement :

1. **Comment naît le premier administrateur** sans livrer de *compte par défaut* à
   mot de passe connu (anti-pattern CWE-1392/798) ?
2. **Où vivent les secrets et les comptes**, et qui en est la source de vérité ?

Une partie de la réponse était déjà implémentée mais **inerte ou incohérente**
(OpenBao provisionné mais jamais lu ; Keycloak orphelin). Les phases S0-S3 + K l'ont
rendue réelle ; cet ADR fige le modèle.

## Decision

### 1. Aucun compte par défaut — création forcée et contrôlée

Le framework **ne livre jamais** de compte à mot de passe par défaut. « Installed »
est **dérivé du RBAC** (`/api/v1/system/install-status` : existe-t-il un compte portant
un rôle qui grante `*` ?), pas un flag falsifiable. Tant qu'aucun super-admin réel
n'existe, l'UI affiche l'**installeur first-run**, pas le login.

Deux modèles de naissance du 1er admin, selon le mode d'auth :

- **Natif (break-glass)** : un `ADMIN_TOKEN` **aléatoire généré** (jamais un mot de
  passe par défaut) autorise l'installeur web (`/install`) à créer le 1er super-admin
  avec un mot de passe **choisi par l'opérateur**, puis à seed les rôles + branding.
- **Fédéré (IdP)** : en mode `keycloak_oidc`, le 1er admin peut provenir d'un **groupe
  IdP** mappé sur le rôle `admin` (`auth.oidc.role_map`), provisionné à la 1ère
  connexion OIDC (`app/auth/federation.py`). Aucun compte local à créer.

### 2. Stockage : comptes en BD, secrets infra dans le vault

- **Comptes utilisateurs** (humains + agents) → **Postgres** : `account`,
  `credential` (hash **bcrypt**), `federated_identity` (liens OIDC), `account_role`
  (assignations RBAC scopées). **Jamais** dans OpenBao.
- **Identités de service infra** (rôle PG `facil_app`, SA MinIO, AppRole OpenBao,
  client OIDC Keycloak) : provisionnées idempotemment par le bootstrap ; leurs
  *secrets* sont **mirrorés dans OpenBao** (`facil/{boot,runtime,infra}`) — le vault
  est la **source de vérité consommée par le backend** (S0-S2).
- **`.env.secrets`** reste autoritaire pour l'**interpolation compose** (démarrage des
  conteneurs du data-plane — le vault ne peut pas servir à ça) ; le backend, lui,
  **résout ses creds depuis le vault** au boot, l'env n'étant qu'un fallback.

### 3. Fail-secure & cycle de vie du break-glass

- En mode `secrets=openbao`, l'hydratation vault est **requise par défaut** hors dev
  (`SECRETS_VAULT_REQUIRED` dérivé de `ENVIRONMENT`) : la prod **échoue fermée** plutôt
  que de démarrer sur des secrets potentiellement périmés.
- Le **break-glass `ADMIN_TOKEN` est transitoire** : une fois le 1er admin réel créé,
  il DOIT être **rotationné ou désactivé** (`tools/break_glass.py`, idempotent, refuse
  si non-installé pour ne pas stranger le bootstrap). Désactiver = `admin_token=""`
  (l'API admin se verrouille) ; rotationner = nouveau token aléatoire (conserve un
  accès d'urgence, invalide le token d'amorçage qui a pu transiter dans des logs).

## Consequences

- ✅ Zéro credential par défaut livré ; fenêtre d'exposition supprimée.
- ✅ Source de vérité claire : comptes = BD, secrets infra = vault, env = boot data-plane.
- ✅ Bootstrap automatisable ET sûr (token aléatoire à usage unique, pas un mot de passe).
- ⚠️ L'opérateur DOIT exécuter le hook post-install (rotation/désactivation break-glass)
  — non automatique par défaut pour ne pas retirer l'accès d'urgence sans intention.
- ⚠️ Mode fédéré : la sécurité du 1er admin dépend de la config IdP (groupe→rôle).

## Follow-ups (hors scope, tracés)

- **SEC-003** : cycle de vie du `secret_id` AppRole (TTL/num_uses, response-wrapping)
  + ACL réelle du state file sur Windows — durcissement P7/P8.
- Keycloak production DB-backed + TLS + `KC_HOSTNAME` (Phase J).
- Câbler `tools/break_glass.py` dans le flux de déploiement prod (post-install).

## Alternatives écartées

- **Compte `admin`/`admin` + changement forcé au 1er login** (ERP legacy) : fenêtre
  d'exposition réelle (instance joignable avant 1er login, forçage imparfait) ;
  déconseillé par OWASP ASVS / NIST. Rejeté au profit du no-default + setup forcé.
- **Secrets utilisateurs dans le vault** : inutile et coûteux ; les hash bcrypt en BD
  sont l'état de l'art. Le vault est pour les secrets *machine*.
