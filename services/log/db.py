import os
import time
from urllib.parse import urlparse

import pymssql

GIT_SHA = os.environ.get("GIT_SHA", "dev")


def db_params():
    raw = os.environ["DATABASE_URL"]
    for prefix in ("mssql+pymssql://", "mssql://", "pymssql://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    parsed = urlparse("mssql://" + raw)
    return {
        "server": parsed.hostname,
        "port": parsed.port or 1433,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def connect(retries=30):
    params = db_params()
    last = None
    for _ in range(retries):
        try:
            return pymssql.connect(as_dict=True, login_timeout=10, **params)
        except Exception as err:
            last = err
            time.sleep(2)
    raise RuntimeError(last)


def check_health():
    conn = connect(retries=1)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE health_check SET checked_at = SYSUTCDATETIME() WHERE id = 1;
            IF @@ROWCOUNT = 0
                INSERT INTO health_check (id, checked_at) VALUES (1, SYSUTCDATETIME());
            """
        )
        cur.execute("SELECT checked_at FROM health_check WHERE id = 1")
        row = cur.fetchone()
        conn.commit()
        return row is not None
    finally:
        conn.close()
