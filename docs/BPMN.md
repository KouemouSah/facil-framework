# Facil Framework — BPMN (Business Process Model & Notation)

> Diagrammes Mermaid pour rendre les processus du framework explicites.
> Tous les diagrams ci-dessous sont rendus nativement par GitHub.

---

## Vue d'ensemble — 5 processus clés

1. **Déploiement** : du clone repo à l'app fonctionnelle
2. **Customization** : du profile au runtime customisé
3. **Workflow execution** (runtime) : exécution d'un workflow utilisateur
4. **Module activation** : changement modules actifs sans rebuild
5. **Migration** : mise à jour d'un déploiement (nouveau release)

---

## 1. Déploiement (du clone à l'app fonctionnelle)

```mermaid
flowchart TD
    Start([Operator clones repo]) --> Wizard[python deploy/init.py]

    Wizard --> Q1{Provider?}
    Q1 -->|docker-local| L1[Choose database mode<br/>local-postgres / external]
    Q1 -->|gcp| L2[GCP project_id + region]
    Q1 -->|aws| L3[Phase A.5.7 not implemented]

    L1 --> Profile[Choose profile<br/>gov / private-services /<br/>saas / banking / empty]
    L2 --> Profile
    Profile --> Modules[Profile sets<br/>MODULES_ENABLED]
    Modules --> Secrets[Secrets generated<br/>JWT/SECRET/TOTP/CRON auto<br/>Gemini/Firebase asked]

    Secrets --> Validate[Pydantic validate config]
    Validate -->|invalid| Wizard
    Validate -->|valid| Files[Write deploy/config.yaml<br/>+ .env.secrets]

    Files --> Apply[python deploy/providers/X.py --apply]
    Apply --> Render[Render env templates]
    Render --> Compose{Provider}

    Compose -->|docker-local| Docker[docker compose up -d --build]
    Compose -->|gcp| GCP[gcloud run deploy<br/>+ secrets manifest]

    Docker --> DBInit[db-init service runs<br/>init_database.py mode=hybrid]
    GCP --> DBInit2[Cloud Run Job runs<br/>init_database.py]

    DBInit --> CheckEmpty{DB empty<br/>+ baseline.sql<br/>present?}
    CheckEmpty -->|yes| ApplyBaseline[Apply baseline.sql<br/>Mark migrations as<br/>'applied via baseline']
    CheckEmpty -->|no| ApplyMigs[Apply pending migrations]

    ApplyBaseline --> Seeds[Apply profile seeds<br/>roles, taxonomies, workflows]
    ApplyMigs --> Seeds

    Seeds --> Embeddings{LLM/RAG<br/>enabled?}
    Embeddings -->|yes| GenEmb[Generate embeddings<br/>via EmbeddingClient]
    Embeddings -->|no| Backend[Backend boots<br/>uvicorn]
    GenEmb --> Backend

    DBInit2 --> Backend
    Backend --> Frontend[Frontend boots<br/>Next.js]
    Frontend --> Done([App accessible<br/>localhost:3000 OR https://...])

    style Start fill:#90EE90
    style Done fill:#90EE90
    style L3 fill:#FFB6B6
    style Validate fill:#FFE4B5
    style CheckEmpty fill:#FFE4B5
    style Embeddings fill:#FFE4B5
```

**Légende** :
- 🟢 Start/End
- 🟡 Décisions
- 🔴 Phase non implémentée

---

## 2. Customization (du profile au runtime)

```mermaid
flowchart LR
    subgraph "Day 1 — Initial deployment"
        Wizard1[Wizard chooses profile]
        Wizard1 --> Seeds1[Profile seeds applied]
        Seeds1 --> Modules1[MODULES_ENABLED set]
        Modules1 --> App1[App running with<br/>profile defaults]
    end

    subgraph "Day 2-N — Operator customization via Studio UI"
        Studio[Operator opens<br/>/customize/*]
        Studio --> CustomA[Branding<br/>logo/colors/name]
        Studio --> CustomB[Languages<br/>add/remove/translate]
        Studio --> CustomC[RBAC<br/>roles/permissions matrix]
        Studio --> CustomD[Taxonomies<br/>ministries/divisions/branches]
        Studio --> CustomE[Catalog<br/>services/products]
        Studio --> CustomF[Workflows<br/>drag-drop designer]
        Studio --> CustomG[Providers<br/>LLM/Storage/Payment/Auth]
        Studio --> CustomH[Knowledge Base<br/>upload PDFs/docs]

        CustomA --> APIWrite[POST /api/v1/customize/branding]
        CustomB --> APIWrite
        CustomC --> APIWrite
        CustomD --> APIWrite
        CustomE --> APIWrite
        CustomF --> APIWrite
        CustomG --> APIWrite
        CustomH --> APIWrite

        APIWrite --> Audit[Audit log entry]
        APIWrite --> DBWrite[DB persistence]
        APIWrite --> Cache[Cache invalidation]

        Cache --> ReloadFE[Frontend re-fetches<br/>config + branding]
        DBWrite --> ReloadFE
    end

    App1 -.-> Studio
    ReloadFE --> Live[Live update<br/>visible immediately]

    style App1 fill:#90EE90
    style Live fill:#90EE90
```

---

## 3. Workflow execution (runtime, exécuté par un user)

```mermaid
sequenceDiagram
    actor User as End User<br/>(citizen / employee / customer)
    participant Web as Frontend Web
    participant API as Backend API
    participant WF as Workflow Engine
    participant DB as Postgres
    participant LLM as LLMClient<br/>(if needed)
    participant Email as Communications
    actor Agent as Agent / Reviewer

    User->>Web: Browse catalog, click "Request service X"
    Web->>API: GET /api/v1/services/X
    API->>DB: Fetch service + workflow_id
    DB-->>API: service + workflow definition
    API-->>Web: Form schema (steps, fields, docs)

    User->>Web: Fill form, upload docs, submit
    Web->>API: POST /api/v1/service-requests
    API->>WF: Initiate workflow X
    WF->>DB: INSERT service_request<br/>status=submitted
    WF->>WF: Evaluate first step<br/>(auto / agent / payment)

    alt Step is auto-validation
        WF->>LLM: Validate document via OCR + LLM
        LLM-->>WF: Validation result (ok / needs_review)
        WF->>DB: UPDATE status<br/>auto_processing → approved/pending
    else Step is agent review
        WF->>DB: UPDATE assigned_to_agent
        WF->>Email: Notify agent
        Agent->>Web: Open agent dashboard
        Agent->>API: Approve / Reject / Request docs
        API->>WF: Process agent decision
        WF->>DB: UPDATE status
    else Step is payment
        WF->>API: Generate payment session<br/>via PaymentGateway
        API-->>Web: Payment URL
        User->>Web: Pay via Stripe/BANGE/etc.
        Web->>API: Webhook callback
        API->>WF: Payment confirmed
        WF->>DB: UPDATE status=paid
    end

    WF->>WF: Next step or complete?
    alt Workflow complete
        WF->>Email: Send receipt + PDF
        Email->>User: Email with attachment
        WF->>DB: UPDATE status=completed
    else More steps
        WF->>WF: Loop to next step
    end

    User->>Web: Track status / download docs
    Web->>API: GET /api/v1/service-requests/{id}
    API->>DB: Fetch + audit log
    DB-->>Web: Status + history
    Web-->>User: Display
```

---

## 4. Module activation (changement modules sans rebuild)

```mermaid
stateDiagram-v2
    [*] --> Boot: Container starts
    Boot --> ReadConfig: Read MODULES_ENABLED env var

    ReadConfig --> LoadCheck: Verify each module exists
    LoadCheck --> AlertMissing: Module name typo or absent
    AlertMissing --> ReadConfig: Operator fixes config

    LoadCheck --> ImportLoop: For each enabled module

    ImportLoop --> ImportModule: importlib.import_module(...)
    ImportModule --> RegisterRouter: app.include_router(...)
    RegisterRouter --> ImportLoop: Next module

    ImportLoop --> Done: All loaded
    Done --> Healthy: GET /health returns 200

    Healthy --> RuntimeChange: Operator changes<br/>MODULES_ENABLED via Studio
    RuntimeChange --> SoftRestart: Backend graceful restart<br/>(uvicorn --reload OR k8s rolling)
    SoftRestart --> Boot

    note right of RuntimeChange
        In production:
        - Studio writes new config
        - Triggers compose restart OR
          k8s rolling deploy
        - 0 downtime possible
    end note
```

---

## 5. Migration (mise à jour d'un déploiement)

```mermaid
flowchart TD
    Start([New Facil release published<br/>v1.X.0]) --> Pull[Operator pulls new code]
    Pull --> CheckCompat{Schema migration<br/>needed?}

    CheckCompat -->|no| Build[docker compose build]
    CheckCompat -->|yes| MigrationCheck{Breaking schema<br/>changes?}

    MigrationCheck -->|no| AutoMigrate[init_database.py<br/>auto-applies new migrations]
    MigrationCheck -->|yes| Backup[Backup DB first<br/>operator confirms]

    Backup --> AutoMigrate
    AutoMigrate --> Build

    Build --> Restart[docker compose up -d<br/>rolling update]
    Restart --> Health{All services<br/>healthy?}

    Health -->|yes| Done([Deployment updated<br/>app accessible])
    Health -->|no| Logs[Operator runs<br/>--logs, identifies issue]
    Logs --> Decision{Fixable?}

    Decision -->|yes| Build
    Decision -->|no| Rollback[git checkout previous tag<br/>docker compose up -d]
    Rollback --> Restore{Schema<br/>changed?}

    Restore -->|yes| RestoreBackup[Restore DB backup]
    Restore -->|no| Done2([Rolled back])
    RestoreBackup --> Done2

    style Start fill:#90EE90
    style Done fill:#90EE90
    style Done2 fill:#FFB6B6
    style Backup fill:#FFE4B5
    style RestoreBackup fill:#FFE4B5
```

---

## 6. Bonus — Customization Studio Workflow Designer (drag-drop)

```mermaid
flowchart LR
    subgraph "Designer canvas"
        Start[Start node]
        Step1[Form step<br/>Submit application]
        Step2[Auto step<br/>OCR validation]
        Step3[Agent step<br/>Manual review]
        Step4[Payment step<br/>Stripe]
        Step5[Email step<br/>Notify completion]
        End[End node]

        Start --> Step1
        Step1 --> Step2
        Step2 -->|valid| Step3
        Step2 -->|invalid| Step1
        Step3 -->|approved| Step4
        Step3 -->|rejected| End
        Step4 -->|paid| Step5
        Step4 -->|failed| Step3
        Step5 --> End
    end

    subgraph "Studio toolbar"
        T1[Drag step types]
        T2[Save as draft]
        T3[Test mode<br/>simulate request]
        T4[Export JSON]
        T5[Publish<br/>active workflow]
    end

    T1 -.-> Step1
    T1 -.-> Step2
    T1 -.-> Step3

    T5 --> Activate[Workflow saved to DB<br/>workflows table]
    Activate --> Available[Available in catalog<br/>service_request creation]
```

---

## Notes pour les agents IA & devs

Ces BPMN servent **3 audiences** :

1. **Devs Voie B** : comprendre l'architecture cible avant de coder
2. **Agents IA marketing** : générer du content explicatif (vidéos, blog posts)
3. **Operators / clients potentiels** : comprendre comment Facil fonctionne sans creuser le code

Si vous éditez un diagramme : tester le rendu Mermaid sur <https://mermaid.live> avant commit.

Format BPMN 2.0 strict (XML) **non utilisé** ici car :
- Mermaid est lisible et versionnable
- Rendu GitHub natif (pas besoin d'outil externe)
- Pas de complex orchestration enterprise nécessaire au niveau doc

Si Phase H Workflow Designer adopte BPMN 2.0 XML pour les workflows utilisateurs runtime, ce sera dans le format propre du `Workflows table` (DB), pas dans cette doc.
