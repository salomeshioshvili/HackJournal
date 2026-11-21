from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

CREATE_TRACKING_TABLE = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'schema_migrations')
CREATE TABLE schema_migrations (
    version NVARCHAR(255) PRIMARY KEY,
    applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
)
"""


def split_batches(sql):
    batches, current = [], []
    for line in sql.splitlines():
        if line.strip().upper() == "GO":
            batches.append("\n".join(current))
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current))
    return [b.strip() for b in batches if b.strip()]


def run_migrations(conn, migrations_dir=MIGRATIONS_DIR):
    cur = conn.cursor()
    cur.execute(CREATE_TRACKING_TABLE)
    conn.commit()

    cur.execute("SELECT version FROM schema_migrations")
    done = {row["version"] for row in cur.fetchall()}

    applied = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in done:
            continue
        try:
            for batch in split_batches(path.read_text(encoding="utf-8")):
                cur.execute(batch)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            conn.commit()
        except Exception:
            conn.rollback()
            print(f"migration failed: {path.name}", flush=True)
            raise
        print(f"migration applied: {path.name}", flush=True)
        applied.append(path.name)

    if not applied:
        print("migrations: nothing to apply", flush=True)
    return applied
