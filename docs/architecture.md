# Architecture

## Before: Assignment 1 monolith

```mermaid
flowchart TD
    Browser["Browser"] --> App["app.py: create_app() registers both blueprints"]
    subgraph LOG["Domain 1: log"]
        LR["log/routes.py: pages and forms"] --> LS["log/service.py: status rules, urgency, SQL"]
    end
    subgraph INS["Domain 2: insights"]
        IR["insights/routes.py: stats, checklist, reflections"] --> IS["insights/service.py: stats, skill gaps, checklist, SQL"]
    end
    App --> LR
    App --> IR
    IR -. "THE SEAM: list_hackathon_records()" .-> LS
    LR --> DB["db.py: connection, schema, seed"]
    IR --> DB
    DB --> File[("SQLite file: DATA_DIR/hackathon_journal.db")]
    linkStyle 5 stroke:#8b5cf6,stroke-width:3px
```

The dotted arrow is the seam. Insights imports exactly one thing from log: `list_hackathon_records()`, which returns a list of plain dictionaries (each with its projects and teammates, including the hackathon `id`). Log never imports insights.

## After: two services and a static UI (Assignment 2)

```mermaid
flowchart LR
    Browser["Browser<br/>static UI: index.html, app.js, config.js"]
    subgraph LOGS["log service (Flask + waitress, port 8001)"]
        LAPI["/api/hackathons, /api/hackathons/{id}/...<br/>/api/records, /health"]
    end
    subgraph INSS["insights service (Flask + waitress, port 8002)"]
        IAPI["/api/summary, /api/checklist/{id}<br/>/api/reflections, /health"]
    end
    LDB[("log database<br/>hackathons, teammates, hackathon_teammates,<br/>projects, project_technologies")]
    IDB[("insights database<br/>reflections, checklist_rules")]

    Browser -- "HTTPS + CORS (LOG_URL)" --> LAPI
    Browser -- "HTTPS + CORS (INSIGHTS_URL)" --> IAPI
    IAPI -. "THE SEAM: GET /api/records<br/>LOG_URL, 2 s timeout, 503 log_unavailable on failure" .-> LAPI
    LAPI -- "log_user" --> LDB
    IAPI -- "insights_user" --> IDB
    linkStyle 2 stroke:#8b5cf6,stroke-width:3px
```

The seam is in the same place as in Assignment 1 (ADR 2, ADR 6): the function call became `GET /api/records`. Each service connects only to its own database with its own login. Locally both databases live in one SQL Server container; on Azure each is its own serverless database on one logical server.

## Deployment

```mermaid
flowchart LR
    Dev["git push / pull request"] --> GH["GitHub: salomeshioshvili/HackJournal"]
    GH --> CI["GitHub Actions ci.yml<br/>describe → test (SQL Server in compose) → images"]
    CI -- "main only: push :&lt;sha&gt;" --> GHCR["GHCR<br/>ghcr.io/salomeshioshvili/log<br/>ghcr.io/salomeshioshvili/insights"]
    CI -- "main only: deploy job, OIDC as sshioshvili-ieu2024-github" --> AZ

    subgraph AZ["Azure: rg-sshioshvili-ieu2024 (France Central)"]
        subgraph ENV["Container Apps environment sshioshvili-ieu2024-env (Consumption, 0 to 1 replica)"]
            CAL["sshioshvili-ieu2024-log"]
            CAI["sshioshvili-ieu2024-insights"]
        end
        subgraph SQL["SQL server sshioshvili-ieu2024-sql (serverless, free offer)"]
            DBL[("sshioshvili-ieu2024-log-db")]
            DBI[("sshioshvili-ieu2024-insights-db")]
        end
        ST["Storage account sshioshvilieu2024ui<br/>static website ($web)"]
        LA["Log Analytics workspace<br/>(container logs)"]
    end

    GHCR -- "image pull" --> CAL
    GHCR -- "image pull" --> CAI
    CAL --> DBL
    CAI --> DBI
    CAI -- "LOG_URL" --> CAL
    CAL --> LA
    CAI --> LA
    User["User browser"] -- "opens the live URL (static website endpoint)" --> ST
    User -- "HTTPS API calls" --> CAL
    User -- "HTTPS API calls" --> CAI
```
