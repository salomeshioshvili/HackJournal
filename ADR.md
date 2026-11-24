# Architecture Decision Record

## 1. Backend language and framework: Flask with sqlite3
Date: 2026-10-08
Status: Superseded by [7]
Context: The app is a small single-user tracker with two domains, one SQLite file and one process, and I must explain all of its code on paper at the comprehension check. It needs server-rendered pages, simple routing and nothing more.
Decision: I chose Python 3.12 with Flask and the built-in sqlite3 module, rendering Jinja templates from the same process.
Alternatives considered: Django, rejected because its ORM, migrations and admin add hidden behaviour I would have to explain and the app needs none of it. FastAPI, rejected because the app serves HTML pages rather than a JSON API, so its async support and generated schemas buy nothing here. SQLAlchemy on top of Flask, rejected because plain SQL keeps every query visible and the schema is only seven tables.
Consequences: The code stays small and each request path is easy to follow, but I write validation and SQL by hand. Flask's built-in server is only for development, so Assignment 2 would need a production server.

## 2. Scoping the two domains so they can be split later
Date: 2026-10-09
Status: Decided
Context: Assignment 2 splits the app into separate services, so the hackathon log and the insights engine need a clear seam now. Both read and write one SQLite file.
Decision: The log domain (log/) owns hackathons, projects, teammates and the status rules, and the insights domain (insights/) will own reflections, checklist rules and statistics. Insights reads log data only through log.service.list_hackathon_records(), which returns a list of plain dictionaries (each including the hackathon id), and log never imports insights.
Alternatives considered: One shared module holding every query, rejected because it hides which tables belong to which domain. Letting insights run its own joins on the log's tables, rejected because splitting later would mean rewriting those queries.
Consequences: Only one read-only function and hackathon_id cross the seam, so Assignment 2 can turn that call into an API request. For now both domains still share one schema in db.py and one database file.

## 3. Schema: join tables for many-to-many data and a single hackathon_id link between domains
Date: 2026-10-11
Status: Superseded by [7]
Context: A hackathon has many teammates and a project has many technologies, and the insights domain needs to count both. The insights tables must also refer to a hackathon without owning any of the log's data.
Decision: Teammates and technologies live in join tables (hackathon_teammates and project_technologies) with composite primary keys, and the insights tables (reflections and checklist_rules) connect to the log only through hackathon_id. CHECK constraints on status, mode and result stop invalid values from being stored.
Alternatives considered: Comma-separated names in a text column, rejected because every count would need string parsing and spelling clean-up. A single wide hackathons table with JSON columns, rejected because SQLite cannot enforce allowed values or foreign keys inside JSON.
Consequences: Counting teammates and technologies becomes a plain query over rows, and each domain's tables could move to their own database with only hackathon_id to reconnect them. The cost is that CREATE TABLE IF NOT EXISTS never alters an existing table, so changing a column later needs a real migration.

## 4. Testing approach: test the rules directly, leave routes thin
Date: 2026-10-11
Status: Superseded by [9]
Context: The 70% bar applies to the business logic of the two domains, and my code is split into pure rule functions and functions that use SQLite.
Decision: I test log/service.py and insights/service.py directly with pytest, using an in-memory SQLite database built from the real schema for the database functions, and measure coverage only on those two packages, leaving out routes. I also test that booting twice keeps the seed data unchanged and keeps rows added later.
Alternatives considered: Testing through Flask's test client, rejected because it exercises routing and templates instead of the rules and makes a failure harder to trace. Mocking the database, rejected because the SQL is part of the logic and an in-memory SQLite is just as fast.
Consequences: Coverage is highest on the code I have to defend, but routes.py, the templates and app.py have no automated tests and are only checked by hand and with container/run.sh.

## 5. Deliberately not built: authentication and multiple users
Date: 2026-10-12
Status: Decided
Context: The journal is a personal tool for one student and holds no sensitive data, and the container contract needs the app to start with no manual setup.
Decision: I did not build login, user accounts or per-user data, so every page is open to anyone who can reach the app's port.
Alternatives considered: Flask sessions with a users table and password hashing, rejected because it adds a table, a secret key to configure and a login flow that I would have to test and defend, none of which a one-user tool needs. A single shared password in an environment variable, rejected because it protects little and would be one more required setting for the container.
Consequences: The app stays simple and every feature belongs to one of the two domains, but it must only run locally or on a private network. Assignment 2's Azure deployment would need authentication before the app is reachable from the internet.

## 6. Splitting the monolith along the Assignment 1 seam
Date: 2026-11-18
Status: Decided
Context: Assignment 2 needs each domain in its own container with its own database. In Assignment 1 I already decided the cut was list_hackathon_records(), so that call has to become an HTTP request. After the Assignment 1 feedback I also realised ADR-3 overstated the schema: I wrote that checklist_rules connect through hackathon_id, but in the real database that column only exists on reflections.
Decision: I kept that same seam. The log service owns hackathons, teammates, projects and technologies. The insights service owns reflections and checklist_rules. Insights asks log for data over HTTP using LOG_URL, with a timeout. reflections.hackathon_id is just a number now, not a foreign key across databases. checklist_rules stay global prep rules with condition_field / condition_value / item only — no hackathon_id. I am recording that correction here instead of rewriting ADR-3.
Alternatives considered: Letting only the browser call both services, rejected because the brief wants at least one server-side call across the seam. Putting everything back in one app, rejected because that would undo Assignment 1.
Consequences: SQL can no longer check that a reflection points at a real hackathon, so insights has to cope when log is down (clear error, not a crash). Both services, migrations and the static UI are in place now.

## 7. Database changes as numbered SQL migrations
Date: 2026-11-20
Status: Decided
Context: Until now each service created its tables from Python with "create if not exists". That works the first time, but it can't change a table that already has data, and I had no way to see which version of the schema a database was on. I also moved from one SQLite file to one SQL Server database per service.
Decision: Numbered SQL files in each service's migrations folder, applied by migrate.py into a schema_migrations table, in order, and rolled back as a whole if one fails. Seed data moved with its tables. The foreign key from reflections to hackathons was lost at the seam, so insights asks log before saving a reflection. If a migration fails in production, the new revision never gets healthy and the old one keeps serving; I fix it with a new file. If data is damaged, I restore from Azure's point-in-time backup and ship another migration.
Alternatives considered: Alembic, rejected because it needs SQLAlchemy, which I don't use. Keeping "create if not exists", rejected because it can't change existing tables.
Consequences: A second start applies nothing. Applied files are never edited. This is safe only with one replica, which matches my Azure setting.

## 8. Serverless hosting on Azure with scale to zero
Date: 2026-11-22
Status: Decided
Context: The journal is idle most of the time and runs on student credit, so it should cost nothing while idle but still answer when someone opens the link.
Decision: Container Apps (min 0, max 1), serverless Azure SQL on the free offer, a Storage static website, and GHCR. Services retry the database with backoff on cold starts, and the UI shows "starting up, try again". Migrations at startup stay safe because there is only one replica.
Alternatives considered: Always-on App Service, rejected for cost. Azure Container Registry, rejected because GHCR is free.
Consequences: Idle is cheap; the first visit after a pause can take up to a minute. At 100x traffic I would keep one warm replica, allow more replicas, move migrations into the pipeline, and leave the free SQL offer.

## 9. Pipeline gates and how the system is tested
Date: 2026-11-22
Status: Decided
Context: Every merge to main deploys on its own, so CI must catch mistakes before they reach Azure. The split also added an HTTP call that unit tests alone don't cover.
Decision: CI validates system.yaml and the OpenAPI files, then runs ruff and pytest per service against SQL Server from compose (coverage ≥70%), then builds the images. On main only, it pushes SHA-tagged images, deploys, and waits for /health. The cross-seam test starts the real log service; another test points insights at a closed port and expects 503.
Alternatives considered: A stub for log, rejected because it can't catch the two sides drifting apart.
Consequences: Broken migrations or response shapes never reach Azure. The UI and cold starts are checked by hand, not in CI.

## 10. Still not built: authentication
Date: 2026-11-22
Status: Decided
Context: ADR 5 left out login for a local app. The site is now on public HTTPS, and CORS only stops other websites, not someone using curl.
Decision: I still did not build authentication. The data is not sensitive, the brief asks for no new features, and login would need Entra ID in both services and the UI.
Alternatives considered: Container Apps Easy Auth with Entra ID, which I would add first. An API key in config.js, rejected because a static site makes it public.
Consequences: Anyone with the URLs can use the journal. Worth building when a second person uses it or real personal data goes in.
