# Auth & Identité (Phase D4)

> **Statut** : D4.0 (Resend) · D4.1 (identité + NIU) · D4.2 (auth) **implémentés**.
> D4.1b (identité vérifiée / extraction) **préparé, différé**. D4.3 (RBAC) **à venir**.
> Plan interne : `.claude/plans/PHASE_D4_AUTH_RBAC_PLAN.md`. Légende legacy :
> mémoire `reference_legacy_auth_rbac_map`.

## 1. Vue d'ensemble

Trois briques distinctes, découplées :

- **Identité** (`app/identity/`) — *qui* est le compte : `Account` + `account_number`
  (NIU générique) + `organization_id` (multi-tenant) + `subject_type`.
- **Auth** (`app/auth/` + provider `auth/native`) — *comment* il le prouve :
  `Credential` (password bcrypt + TOTP), JWT access/refresh, lockout.
- **RBAC** (à venir, D4.3) — *ce qu'il a le droit de faire*, scopé org→unit→site.

```mermaid
flowchart LR
  acc["identity: Account (NIU, email, org, subject_type)"]
  cred["auth: Credential (bcrypt, TOTP, lockout)"]
  prov["AuthProvider (registre) — auth/native = JWT HS256"]
  api["API /api/v1/auth/*"]
  gate["require_auth (JWT OU admin-token break-glass)"]
  rbac["RBAC scope org/unit/site (D4.3)"]
  acc --- cred
  api --> prov
  cred --> prov
  gate --> prov
  gate -. remplacé par .-> rbac
```

## 2. Modèle de données (implémenté)

```mermaid
erDiagram
  ORGANIZATION ||--o{ ACCOUNT : "scope (nullable)"
  ACCOUNT ||--|| CREDENTIAL : "1:1"
  ACCOUNT {
    uuid id PK
    varchar account_number UK "NIU — NULL jusqu'à émission"
    varchar email UK "nullable"
    uuid organization_id FK "nullable (SET NULL)"
    varchar subject_type "national/foreigner/entity"
    varchar status "pending_identity/active/suspended/deactivated"
  }
  CREDENTIAL {
    uuid id PK
    uuid account_id FK "UNIQUE, CASCADE"
    varchar password_hash "bcrypt"
    varchar totp_secret "nullable (à chiffrer — D4.1b)"
    boolean totp_enabled
    int failed_attempts
    timestamptz locked_until
  }
```

Migrations : `0004_create_account`, `0005_create_credential`.

## 3. NIU (account_number) — identifiant générique

- **Numérique pur** par défaut : `[préfixe-catégorie] + corps ALÉATOIRE (anti-énumération)
  + 2 chiffres ISO 7064 Mod 97,10` (détecte toutes les erreurs 1 chiffre + transpositions).
- **Catégorie** (national/étranger/entité) = **préfixe** (fixé à l'émission, distinguable)
  **+** `subject_type` (attribut faisant autorité, évolue à la naturalisation).
- **Émission configurable** (`identity.issuance_policy`) :
  - `immediate` (défaut framework) — NIU émis à l'inscription.
  - `on_verified_document` (gov/banking) — NIU émis **après vérification d'une pièce** (D4.1b).
- **Sécurité** : `UNIQUE` en base ; **immutable** (`AlreadyIssued`) ; check-digit validé
  **avant tout accès BD** ; aléatoire = anti-énumération ; zéro PII encodée ; mint atomique
  (UNIQUE + SAVEPOINT retry). Stratégie verrouillée au deploy (changer ⇒ nouveaux comptes only).
- **Lié** à la pièce (D4.1b) de façon **relationnelle** (FK + blind-index UNIQUE), jamais
  *dérivé* du numéro de document (préserve immutabilité, multi-docs, privacy).

## 4. Flux d'authentification (implémenté)

```mermaid
sequenceDiagram
  participant C as Client
  participant API as /api/v1/auth
  participant S as auth.service
  participant P as AuthProvider (native)
  C->>API: POST /register {email?, password}
  API->>S: register (strength -> identity.register + Credential bcrypt)
  API-->>C: 201 Account (NIU si policy=immediate)
  C->>API: POST /login {identifier(email|NIU), password, totp_code?}
  API->>S: authenticate (resolve email|NIU, verify, lockout, TOTP)
  alt invalide
    API-->>C: 401 "invalid credentials" (uniforme, anti-oracle)
  else 2FA requise
    API-->>C: 401 "totp_required"
  else OK
    S->>P: issue(account.id, claims)
    API-->>C: 200 {access, refresh, account}
  end
  C->>API: POST /refresh {refresh_token}
  API->>P: refresh (rotation)
  API-->>C: 200 {access, refresh}
```

Endpoints : `POST /api/v1/auth/{register, login, refresh, logout, 2fa/setup, 2fa/enable}`.
Garde : `require_auth` = Bearer JWT **OU** `X-Admin-Token` (break-glass, pont jusqu'à D4.3/D4.4).
Secret JWT = `JWT_SECRET` (généré par `ensure_secrets`, rendu dans l'env backend).

## 5. Détails de sécurité

- **Anti-énumération** : login par email/NIU → **401 uniforme** (compte existant ou non) ;
  check-digit NIU validé avant lookup.
- **Lockout** : 5 échecs → verrou 15 min (`failed_attempts` / `locked_until`).
- **2FA** : TOTP (pyotp), issuer = `branding.app_name` (configurable, dé-couplé du legacy).
- **Passwords** : bcrypt (72 octets safe), policy min 8 + maj/min/chiffre.
- ⚠️ `totp_secret` stocké en clair pour l'instant → **à chiffrer at-rest** avec le helper
  AES-GCM/blind-index introduit en D4.1b.

## 6. D4.1b — identité vérifiée (PRÉPARÉ, DIFFÉRÉ)

Les hooks identité existent (policy `on_verified_document`, `issue_number(category)`,
`subject_type`). **Non activé/obligatoire** tant que l'**agent d'extraction LLM multimodal**
et les **liaisons BD externes** de vérification ne sont pas prêts (éviter le bâclage).
À implémenter le moment venu : table `identity_document` (doc chiffré AES-GCM + **blind-index
HMAC UNIQUE** = 1 pièce/1 compte, port `verified_identifiers` legacy) → extraction +
score de confiance + gate → `issue_number(category)`.

## 7. À venir (D4.3 RBAC)

`role` / `permission` / `account_role` avec **scope `{organization_id, org_unit_id, site_id}`**
(sous-arbre via `org_unit.path`) ; `require_permission(perm)` **scope par défaut** ; rôles
seedés **par profil YAML** ; permissions **déclarées par module**. Remplace `require_auth`
sur les routes métier/admin (D4.4).
