# Database schema per service

Each service owns its own database. The tables come from the numbered files in `services/<name>/migrations/`, and both databases also have a `schema_migrations` table that records which files have run.

## log database (`log_db` locally, `sshioshvili-ieu2024-log-db` on Azure)

Migrations: `001_init.sql` (tables), `002_health_check.sql` (health_check), `003_add_country.sql` (adds `country` to hackathons and fills it from `location`).

```mermaid
erDiagram
    hackathons ||--o{ projects : "has"
    hackathons ||--o{ hackathon_teammates : "has"
    teammates ||--o{ hackathon_teammates : "joins"
    projects ||--o{ project_technologies : "uses"

    hackathons {
        int id PK "IDENTITY"
        nvarchar name
        nvarchar location
        nvarchar country "added by 003"
        nvarchar mode
        date start_date
        date end_date
        date application_deadline
        nvarchar status
        bit travel_funded
        nvarchar notes
        datetime2 created_at
    }
    teammates {
        int id PK "IDENTITY"
        nvarchar name "UNIQUE"
    }
    hackathon_teammates {
        int hackathon_id PK, FK
        int teammate_id PK, FK
    }
    projects {
        int id PK "IDENTITY"
        int hackathon_id FK
        nvarchar name
        nvarchar result
    }
    project_technologies {
        int project_id PK, FK
        nvarchar technology PK
    }
    health_check {
        int id PK
        datetime2 checked_at
    }
    schema_migrations {
        nvarchar version PK
        datetime2 applied_at
    }
```

## insights database (`insights_db` locally, `sshioshvili-ieu2024-insights-db` on Azure)

Migrations: `001_init.sql` (tables), `002_health_check.sql` (health_check).

```mermaid
erDiagram
    reflections {
        int id PK "IDENTITY"
        int hackathon_id "plain id from log, no FK"
        nvarchar went_well
        nvarchar went_badly
        nvarchar lesson
        datetime2 created_at
    }
    checklist_rules {
        int id PK "IDENTITY"
        nvarchar condition_field
        nvarchar condition_value
        nvarchar item
    }
    health_check {
        int id PK
        datetime2 checked_at
    }
    schema_migrations {
        nvarchar version PK
        datetime2 applied_at
    }
```

`reflections.hackathon_id` points at `hackathons.id` in the other database, so SQL can't enforce it. Insights checks it in code instead: before saving a reflection it fetches the record from log and only accepts an attended hackathon (ADR 7). `checklist_rules` has a unique constraint on (condition_field, condition_value, item).
