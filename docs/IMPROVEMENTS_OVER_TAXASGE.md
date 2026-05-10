# Améliorations Facil Framework vs TaxasGE

> **Objectif** : lister explicitement les pain points TaxasGE résolus dans Facil Framework. C'est l'argument différenciant majeur : **Voie B = TaxasGE sans douleurs accumulées**.

---

## Pain points TaxasGE identifiés + solutions Voie B

### 1. Permissions auto-sync = source de bugs

**Problème TaxasGE** :
- Permissions définies en code Python (`app/modules/permissions/module_permissions/*.py`)
- Au boot, `initialize_permissions()` fait UPSERT en BD
- Cleanup obsolète a effacé des permissions ajoutées par migration → incident 2026-05-04
- Fix : `cleanup_obsolete=False` par défaut depuis 2026-05-04 (Règle #37)
- Mais conséquence : permissions obsolètes peuvent s'accumuler en BD
- **Impossible** d'ajouter une permission via UI — il FAUT éditer un fichier `.py`

**Solution Voie B** : **DB-only, single source of truth**

| Mécanisme | Source de vérité | UI ? | Cleanup ? |
|---|---|---|---|
| TaxasGE actuel | Code `module_permissions/*.py` + sync BD | ❌ Non | Manuel via CLI |
| **Facil Framework** | **DB uniquement** | ✅ Studio UI | Automatique via UI ("delete unused") |

Implémentation :
- Migration initiale seede les permissions par profile depuis `profiles/<name>/permissions.yaml`
- Au boot : **pas de sync code → DB**. Lecture directe BD.
- API `POST/DELETE /api/v1/customize/permissions` pour CRUD
- Studio UI page "Permissions" : matrix view, drag-drop assign to roles
- Permissions "système" marquées `is_system=true` (UI affiche mais empêche delete)

Phase concernée : **F (Studio UI RBAC)** + **D (Profiles)**.

### 2. Workflows ajoutés manuellement par code

**Problème TaxasGE** :
- Workflows définis dans `database/migrations/*.sql` (INSERT INTO workflows + workflow_steps + workflow_document_requirements + workflow_tariffs)
- Pour ajouter un workflow → écrire SQL ou Python script
- Pas d'UI accessible aux opérateurs non-tech
- Modifications manuelles → erreurs faciles (steps oubliés, conditions mal formulées)
- 36 workflows TaxasGE = 36 fois la friction

**Solution Voie B** : **Workflow Designer drag-drop dans Studio**

| Mécanisme | Définition workflow | Source de vérité | Test mode |
|---|---|---|---|
| TaxasGE actuel | Migration SQL ou Python script | Migration files | Aucun (deploy + bug discovery) |
| **Facil Framework** | **Drag-drop UI graph** | **DB tables** | **Test mode** simule un parcours sans persister |

Implémentation :
- DB tables `workflows`, `workflow_steps`, `workflow_transitions` (déjà existant TaxasGE)
- Workflow Designer UI lit/écrit directement la DB
- Templates initiaux par profile : `profiles/<name>/workflows/*.json` importés au seed
- Export JSON disponible pour backup / versioning
- Test mode : simulate request → trace les transitions sans toucher la prod

Phase concernée : **H (Workflow Designer)** — c'est la phase R&D la plus longue (15-25j), mais c'est ce qui rend le framework vraiment plug-and-play pour non-tech.

### 3. Migrations rejouées à chaque deploy

**Problème TaxasGE** :
- Workflow `deploy-backend-staging.yml` rejoue les 319 migrations à chaque push
- Idempotent via try/except 'already exists' mais lent (3-5 min)
- Pas de tracking en BD → impossible de savoir quelles versions sont appliquées

**Solution Voie B** : ✅ **Déjà résolu cette session** — `init_database.py` + `schema_migrations` table + baseline.sql + `is_database_empty()` baseline-first.

### 4. Hardcoded Vertex AI / Gemini

**Problème TaxasGE** :
- 22 fichiers backend importent `GenerativeModel` directement
- `populate_embeddings.py` hardcode `text-embedding-005` (Vertex)
- Impossible d'utiliser Claude/Mistral/Ollama sans refacto code

**Solution Voie B** : **Phase B (LLM Abstraction)** + **Phase B.6 (Embedding/RAG Abstraction)** — sous-plans dédiés.

### 5. Hardcoded Firebase Storage

**Problème TaxasGE** :
- `documents/services/storage_service.py` couplé à Firebase Admin SDK
- Pas d'option S3/MinIO/Azure/local

**Solution Voie B** : **Phase C (Storage Abstraction)** — `StorageClient` ABC + 6 impls.

### 6. Hardcoded BANGE/Ecobank/MPGS payment gateways

**Problème TaxasGE** :
- 3 modules paiement spécifiques GE (`bange_payment/`, etc.)
- Webhook signature, currency, methods hardcoded par gateway
- Pas d'extension Stripe/PayPal/etc. simple

**Solution Voie B** : **Phase B.5 (Payment Gateway Abstraction)** — `PaymentGateway` ABC + Stripe/PayPal/Razorpay/Flutterwave + wrap des 3 existants.

### 7. Catalogue 850+ services hardcoded en SQL migrations

**Problème TaxasGE** :
- 850+ INSERT INTO fiscal_services dans migrations
- Modification = nouvelle migration manuelle
- Pas d'import Excel pour bulk update
- Pas d'UI pour création/edition individuelle

**Solution Voie B** : **Catalog UI editor (Phase G)** :
- DB single source
- Studio UI page "Catalog" : table éditable + import Excel/CSV + duplicate item
- Templates par profile dans `profiles/<name>/catalog-template.csv`
- Export CSV pour backup

### 8. Taxonomies hardcoded labels (ministries/sectors)

**Problème TaxasGE** :
- Labels "Ministry" / "Sector" hardcoded dans i18n strings
- Une banque qui veut "Agency / Branch" doit forker le code

**Solution Voie B** : **Taxonomies configurables (Phase G Studio Taxonomies)** :
- Hiérarchie 3-5 niveaux paramétrable (`level_1 = "Ministry" | "Department" | "Agency"`)
- Labels multilingues per niveau
- Items éditables via UI

### 9. Branding non configurable

**Problème TaxasGE** :
- Logo, couleurs, nom app hardcoded dans le frontend code
- Email templates contiennent "Facil DGI Guinea-Ecuatorial" en dur

**Solution Voie B** : **Branding via Studio (Phase F)** :
- DB table `app_settings` avec `theme JSONB`, `logo_url`, `app_name`, etc.
- Endpoint `/api/v1/branding` sert le branding au frontend dynamiquement
- Email templates utilisent `{{branding.app_name}}` placeholder
- Live preview dans Studio

### 10. i18n via migrations SQL (lourd à maintenir)

**Problème TaxasGE** :
- Translations dans table `translations` peuplée par migration
- Ajouter une langue = nouvelle migration avec 1000+ lignes
- Pas d'UI pour traduire

**Solution Voie B** : **i18n Studio (Phase F)** :
- DB single source
- Studio UI page "Languages" : ajout/suppression langue
- **Auto-translate via LLM** : "Translate from English → Spanish" (use existing LLMClient)
- Bulk import CSV pour grosses listes
- Marquer traductions auto comme "draft" (revue humaine recommandée)

### 11. OCR forms_templates en code

**Problème TaxasGE** :
- 14 form_templates avec coordinates OCR fields hardcoded
- Pas d'UI pour créer un nouveau template (PDF + drag boxes coordinates)

**Solution Voie B** (futur, Phase Studio Forms — V1.5) :
- Studio UI page "OCR Forms" : upload PDF + drag boxes pour annoter fields
- DB stocke les coordonnées
- Pas dans V1 (trop spécialisé), mais conceptuellement faisable

### 12. Documents indexation manuelle

**Problème TaxasGE** :
- `populate_pdf_embeddings.py` mentionné dans README mais inexistant
- Les PDFs (legislation, procédures) doivent être indexés manuellement

**Solution Voie B** : **drop-in folder + Studio Knowledge Base** (Phase B.6 + I.bis) :
- Drop folder `data/index-pending/` → indexé au boot ou via cron
- Studio UI Knowledge Base : drag-drop upload + statut indexation

### 13. Permissions modulaires : impossible de désactiver un module

**Problème TaxasGE** :
- Tous les modules chargés en dur dans `main.py`
- Impossible de désactiver "treasury" pour une déploiement qui n'en a pas besoin

**Solution Voie B** : **Module Loader (Phase A.5)** ✅ — clé de voûte.

### 14. Pas de mode demo

**Problème TaxasGE** :
- Pour tester, il faut un projet GCP, des secrets réels, du temps

**Solution Voie B** : **Mode `--demo`** (futur Phase D) :
- Pre-rempli avec fakes (Gemini key fake → DisabledClient, Firebase optionnel, Stripe testmode)
- App boote en 5 min sans aucun compte externe
- Profile `empty` + `--demo` flag

### 15. Wizard ne supporte pas profile choice

**Problème** : actuellement `deploy/init.py` est generic. Voie B ajoute `--profile=<name>`.

**Solution Voie B** : **Wizard étendu (Phase D)** :
- `python framework/init.py --profile=private-services-company`
- Charge `profiles/<name>/install.yaml`
- Applique modules + seeds + workflows + branding automatiquement

---

## Récap : 15 améliorations majeures

| # | Pain point TaxasGE | Solution Voie B | Phase |
|---|---|---|---|
| 1 | Permissions auto-sync code | DB-only + UI matrix | F + D |
| 2 | Workflows manuels SQL | Drag-drop Designer | H |
| 3 | Migrations rejouées 3-5min | baseline + schema_migrations | ✅ Déjà fait (cette session) |
| 4 | Hardcoded Gemini | LLM Abstraction | B |
| 5 | Hardcoded Firebase Storage | Storage Abstraction | C |
| 6 | Hardcoded BANGE/Ecobank/MPGS | Payment Gateway Abstraction | B.5 |
| 7 | Catalogue SQL hardcoded | Catalog Editor UI | G |
| 8 | Taxonomies labels hardcoded | Taxonomies configurable | G |
| 9 | Branding hardcoded | Branding Studio | F |
| 10 | i18n via migrations | i18n Studio + auto-translate | F |
| 11 | OCR forms en code | Studio Forms (V1.5) | Future |
| 12 | Indexation manuelle docs | Drop-in folder + KB Studio | B.6 + I.bis |
| 13 | Tous modules chargés dur | Module Loader | A.5 |
| 14 | Pas mode demo | --demo flag | D |
| 15 | Wizard pas de profile | Wizard --profile | D |

---

## Métrique d'impact

**Pour un opérateur non-tech** :
- TaxasGE : ~80% des customizations demandent un dev backend
- Facil Framework : **~95% via Studio UI**, ~5% advanced (custom code module)

**Pour le déployeur initial** :
- TaxasGE : 6-12 mois pour adapter à un nouveau contexte
- Facil Framework : **2-4 semaines** (choix profile + customizations)

C'est ce gap qui justifie l'investissement de 8 mois 1 FTE dans Voie B.
