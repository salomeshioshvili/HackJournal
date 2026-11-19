import os
import time
from urllib.parse import urlparse

import pymssql

GIT_SHA = os.environ.get("GIT_SHA", "dev")
LOG_URL = os.environ.get("LOG_URL", "http://log:8001").rstrip("/")
LOG_TIMEOUT_S = float(os.environ.get("LOG_TIMEOUT_S", "2"))


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
