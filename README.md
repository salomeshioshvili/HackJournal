# Hackathon Journal

A personal tracker for hackathons I apply to and attend: deadlines, status, projects, teammates, plus insights (stats, skill gaps, prep checklists and reflections).

**Live:** https://sshioshvilieu2024ui.z28.web.core.windows.net

The first visit after a quiet period can take up to a minute while Azure starts the containers and resumes the database. If you see "starting up", wait a moment and press **Try again**.

## How it is built

In Assignment 1 this was one Flask app with one SQLite file. Now it is two services split along the seam from ADR 2, plus a static UI:

| Part | What it owns | Local | Azure |
|---|---|---|---|
| `services/log` | hackathons, status rules, teammates, projects, technologies | http://localhost:8001 | `sshioshvili-ieu2024-log` (Container Apps) + `sshioshvili-ieu2024-log-db` |
| `services/insights` | reflections, checklist rules, stats, skill gaps | http://localhost:8002 | `sshioshvili-ieu2024-insights` (Container Apps) + `sshioshvili-ieu2024-insights-db` |
| `ui/` | static HTML, CSS and JS (the Assignment 1 design) | http://localhost:8080 (nginx) | storage account `sshioshvilieu2024ui`, static website |

Insights gets log's data over HTTP with `GET /api/records` (`LOG_URL`, 2 second timeout). If log is down, insights answers 503 `log_unavailable` and the Insights page still shows saved reflections. Each service has its own SQL Server database and its own login, and neither can read the other's database.

- `ADR.md`: decisions 1–10 (6–10 are new for Assignment 2)
- `docs/architecture.md`: before/after architecture and deployment diagrams
- `docs/schema.md`: database diagram per service
- `system.yaml` and `services/*/openapi.yaml`: machine-readable description of the system

## Run locally with Docker Compose

Needs Docker Desktop (on Apple Silicon, turn on Rosetta emulation for SQL Server).

```bash
# one-time: create a local .env with random passwords (it is gitignored)
for v in MSSQL_SA_PASSWORD LOG_DB_PASSWORD INSIGHTS_DB_PASSWORD; do echo "$v=Dev1-$(openssl rand -hex 12)"; done > .env

docker compose up --build
```

Then open http://localhost:8080. Compose starts SQL Server, runs `db/init.sql` once (creates `log_db`, `insights_db` and one login for each), then starts log, insights and an nginx container serving `ui/`.

- Stop: `docker compose down` (data stays in the `mssql-data` volume)
- Wipe local data: `docker compose down -v`
- Partial failure: `docker compose stop log`, then open Insights. Reflections still show, with a "log service is unavailable" notice. `docker compose start log` brings it back.

## Run a single service

Start only the database and the one service:

```bash
docker compose up --build db db-init log
```

Insights needs log for its stats, so `docker compose up --build db db-init insights` also starts log (it is in `depends_on`).

Or run a service straight from Python against the compose database:

```bash
docker compose up -d db db-init
cd services/log
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="mssql+pymssql://log_user:<LOG_DB_PASSWORD from .env>@localhost:1433/log_db"
python app.py
```

## Configuration

Every setting is an environment variable (the full list with defaults is in `system.yaml`):

| Variable | Service | Default | Meaning |
|---|---|---|---|
| `PORT` | both | 8001 / 8002 | Listen port |
| `DATABASE_URL` | both | none (secret) | `mssql+pymssql://user:password@host:1433/db` |
| `UI_ORIGIN` | both | empty | Origins allowed by CORS, comma separated |
| `GIT_SHA` | both | `dev` | Version shown by `/health` |
| `LOG_URL` | insights | `http://log:8001` | Base URL of the log service |
| `LOG_TIMEOUT_S` | insights | `2` | Timeout for calls to log |

Each service applies its `migrations/*.sql` files on startup (only the ones not yet in `schema_migrations`), then seeds its tables if they are empty. `GET /health` writes and reads a row in its own database and returns 200 or 503. Every request is logged to stdout as `METHOD path -> status duration`.

## Tests and coverage

The tests run against a real SQL Server, so start it first:

```bash
docker compose up -d db db-init
set -a; . ./.env; set +a

cd services/log
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL="mssql+pymssql://log_user:${LOG_DB_PASSWORD}@localhost:1433/log_db"
ruff check .
pytest --cov=rules --cov=service --cov=migrate --cov-report=term-missing --cov-fail-under=70

cd ../insights
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL="mssql+pymssql://insights_user:${INSIGHTS_DB_PASSWORD}@localhost:1433/insights_db"
export LOG_DATABASE_URL="mssql+pymssql://log_user:${LOG_DB_PASSWORD}@localhost:1433/log_db"
ruff check .
pytest --cov=rules --cov=service --cov=migrate --cov-report=term-missing --cov-fail-under=70
```

The tests empty the tables they use, so run them on the local database only. `tests/test_seam.py` in insights is the cross-seam test: it starts the real log service on port 18001 and calls it over HTTP.

Last run: log 35 tests, 98% coverage; insights 17 tests, 94% coverage.

## How deployment works

`.github/workflows/ci.yml` runs on every push and pull request:

1. **describe:** `system.yaml` against `system.schema.json`, both `openapi.yaml` files against the OpenAPI spec, and `scripts/check_system.py` (every endpoint insights calls must exist in log's document).
2. **test** (per service): ruff, then pytest with the 70% coverage gate, against SQL Server from `docker-compose.yml` with passwords generated for that run. CI never touches Azure SQL.
3. **images:** builds both Docker images; on `main` pushes them to `ghcr.io/salomeshioshvili/<service>:<commit sha>`.
4. **deploy** (`main` only, after all of the above): logs in to Azure with OIDC as the managed identity, stores each `DATABASE_URL` as a Container Apps secret, points both apps at the new images, waits until both `/health` return ok with the new SHA, then writes `ui/config.js` with the two service URLs and uploads `ui/` to the `$web` container.

Changes reach `main` only through pull requests, so CI always runs before CD.

## Initial Azure setup (done once, by hand)

Everything after this is done by the pipeline. Run in zsh with the Azure CLI logged in (`az login`, then `az account set --subscription <Azure for Students id>`).

```bash
PREFIX=sshioshvili-ieu2024; STORAGE=sshioshvilieu2024ui; RG=rg-$PREFIX
REPO=salomeshioshvili/HackJournal; LOCATION=francecentral   # one of the regions your subscription allows

az extension add --name containerapp --upgrade
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace $p
done
az group create -n $RG -l $LOCATION

# passwords are generated and kept in a local file, never in the repo
SQL_ADMIN_PW="Ad-$(openssl rand -hex 16)Z"; LOG_PW="Lg-$(openssl rand -hex 16)Z"; INSIGHTS_PW="In-$(openssl rand -hex 16)Z"
printf "SQL_ADMIN_PW=%s\nLOG_PW=%s\nINSIGHTS_PW=%s\n" "$SQL_ADMIN_PW" "$LOG_PW" "$INSIGHTS_PW" > ~/sdd-azure-secrets.txt
chmod 600 ~/sdd-azure-secrets.txt

# SQL server and two serverless databases on the free offer
az sql server create -n $PREFIX-sql -g $RG -l $LOCATION --admin-user sqladmin --admin-password "$SQL_ADMIN_PW"
az sql server firewall-rule create -g $RG -s $PREFIX-sql -n AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
MYIP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g $RG -s $PREFIX-sql -n MyIPTemporary --start-ip-address $MYIP --end-ip-address $MYIP
for s in log insights; do
  az sql db create -g $RG -s $PREFIX-sql -n $PREFIX-$s-db \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 \
    --min-capacity 0.5 --capacity 1 --auto-pause-delay 60 --backup-storage-redundancy Local \
    --use-free-limit --free-limit-exhaustion-behavior AutoPause
done

# one login per service, each only in its own database
sqlrun() { docker run --rm mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd \
  -S $PREFIX-sql.database.windows.net -U sqladmin -P "$SQL_ADMIN_PW" -C -l 60 "$@"; }
sqlrun -d master -Q "CREATE LOGIN log_user WITH PASSWORD = '$LOG_PW'; CREATE LOGIN insights_user WITH PASSWORD = '$INSIGHTS_PW';"
sqlrun -d $PREFIX-log-db -Q "CREATE USER log_user FOR LOGIN log_user; ALTER ROLE db_owner ADD MEMBER log_user;"
sqlrun -d $PREFIX-insights-db -Q "CREATE USER insights_user FOR LOGIN insights_user; ALTER ROLE db_owner ADD MEMBER insights_user;"
az sql server firewall-rule delete -g $RG -s $PREFIX-sql -n MyIPTemporary

# Container Apps environment and two apps (placeholder image; the pipeline replaces it)
az containerapp env create -n $PREFIX-env -g $RG -l $LOCATION
for s in log insights; do
  az containerapp create -n $PREFIX-$s -g $RG --environment $PREFIX-env \
    --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 80 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi
done

# storage static website for the UI
az storage account create -n $STORAGE -g $RG -l $LOCATION --sku Standard_LRS --kind StorageV2 --allow-blob-public-access false
az storage blob service-properties update --account-name $STORAGE --static-website --index-document index.html --404-document index.html

# managed identity for GitHub Actions, Contributor on this resource group only, trusted for main only
az identity create -n $PREFIX-github -g $RG -l $LOCATION
PRINCIPAL_ID=$(az identity show -n $PREFIX-github -g $RG --query principalId -o tsv)
RG_ID=$(az group show -n $RG --query id -o tsv)
az role assignment create --assignee-object-id $PRINCIPAL_ID --assignee-principal-type ServicePrincipal --role Contributor --scope $RG_ID
az identity federated-credential create --name github-main --identity-name $PREFIX-github -g $RG \
  --issuer https://token.actions.githubusercontent.com --subject "repo:${REPO}:ref:refs/heads/main" \
  --audiences api://AzureADTokenExchange

# Reader access for grading
az role assignment create --assignee amartini@faculty.ie.edu --role Reader --scope $RG_ID
```

GitHub now sends the OIDC subject with numeric IDs, so the first deploy failed with `AADSTS700213`. I added a second federated credential with the exact subject from the error:

```bash
az identity federated-credential create --name github-main-ids --identity-name $PREFIX-github -g $RG \
  --issuer https://token.actions.githubusercontent.com \
  --subject 'repo:salomeshioshvili@79744349/HackJournal@1409404903:ref:refs/heads/main' \
  --audiences api://AzureADTokenExchange
```

GitHub repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | `az identity show -n $PREFIX-github -g $RG --query clientId -o tsv` |
| `AZURE_TENANT_ID` | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | `az account show --query id -o tsv` |
| `LOG_DATABASE_URL` | `mssql+pymssql://log_user:<LOG_PW>@sshioshvili-ieu2024-sql.database.windows.net:1433/sshioshvili-ieu2024-log-db` |
| `INSIGHTS_DATABASE_URL` | `mssql+pymssql://insights_user:<INSIGHTS_PW>@sshioshvili-ieu2024-sql.database.windows.net:1433/sshioshvili-ieu2024-insights-db` |

After the first image push, the `log` and `insights` packages on GHCR are made public so Container Apps can pull them.

## Project layout

```
├── services/
│   ├── log/            app.py, db.py, migrate.py, rules.py, service.py, seed.json,
│   │                   migrations/, tests/, openapi.yaml, Dockerfile, requirements*.txt
│   └── insights/       same layout
├── ui/                 index.html, app.js, config.js, static/ (styles and images)
├── db/init.sql         local databases and logins (run by the db-init compose service)
├── docker-compose.yml
├── system.yaml, system.schema.json
├── scripts/check_system.py
├── .github/workflows/ci.yml
├── docs/               architecture.md, schema.md
├── ADR.md, AI_USAGE.md
```

## Security incidents

**Committed passwords (10 November 2026).** In commit `fb62340` I committed three local database passwords: the SQL Server `sa` password in `.env.example`, and the `log_user` and `insights_user` passwords in `db/init.sql` and `.env.example`. I noticed it on 19 November while checking the repo against the Assignment 2 rules.

- They were only used for the local Docker setup. They were never used on Azure or anywhere else.
- `db/init.sql` now reads the passwords from environment variables, and `.env.example` only has placeholders. Real values live in my local `.env`, which is gitignored.
- I changed my local passwords and recreated the local database. Azure uses new passwords that have never been in the repo, stored as GitHub secrets.
- The old values are still in the Git history, so I treat them as burned and will never reuse them.

**Passwords shown in a terminal during setup (22 November 2026).** While setting up Azure, a zsh mistake printed the SQL admin password in an error message, and I later pasted terminal output with the two service passwords into my AI assistant chat. None of them were pushed to GitHub. I rotated the admin password right away (`az sql server update --admin-password`) and the two service passwords with `ALTER LOGIN`, then updated the two GitHub secrets.

## AI disclosure statement

I acknowledge the use of Claude (Anthropic) and Cursor to plan the project, draft application code, unit tests and documentation, and, in Assignment 2, to split the app into two services, write the Dockerfiles, compose file, migrations, GitHub Actions workflow, OpenAPI documents and system.yaml, and to walk me through the Azure setup. I made the decisions recorded in `ADR.md`, ran every Azure setup command myself, tested the system locally and on Azure, and kept my Assignment 1 design for the UI. The detailed record, including what I changed and how each file works, is in `AI_USAGE.md`.
