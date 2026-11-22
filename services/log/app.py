import os
import signal
import sys
import time

from flask import Flask, g, jsonify, request
from waitress import serve

import db
import service
from rules import MODES, RESULTS

PORT = int(os.environ.get("PORT", "8001"))
UI_ORIGINS = {o.strip() for o in os.environ.get("UI_ORIGIN", "").split(",") if o.strip()}


def create_app():
    conn = db.connect()
    try:
        service.setup_db(conn)
    finally:
        conn.close()

    app = Flask(__name__)

    @app.before_request
    def _start_timer():
        g.started = time.time()

    @app.after_request
    def _log_request(response):
        started = getattr(g, "started", None)
        duration_ms = int((time.time() - started) * 1000) if started else -1
        print(
            f"{request.method} {request.path} -> {response.status_code} {duration_ms}ms",
            flush=True,
        )
        origin = request.headers.get("Origin")
        if origin and origin in UI_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/health")
    def health():
        try:
            db_ok = db.check_health()
        except Exception:
            db_ok = False
        body = {
            "status": "ok" if db_ok else "error",
            "db": "ok" if db_ok else "error",
            "version": db.GIT_SHA,
            "service": "log",
        }
        return jsonify(body), (200 if db_ok else 503)

    @app.get("/api/hackathons")
    def list_hackathons():
        conn = db.connect(retries=5)
        try:
            return jsonify(service.list_hackathons(conn))
        finally:
            conn.close()

    @app.get("/api/records")
    def list_records():
        """Seam endpoint: full hackathon records for the insights service."""
        conn = db.connect(retries=5)
        try:
            return jsonify(service.list_records(conn))
        finally:
            conn.close()

    @app.post("/api/hackathons")
    def create_hackathon():
        data = request.get_json(silent=True) or {}
        conn = db.connect(retries=5)
        try:
            new_id = service.add_hackathon(conn, data)
            return jsonify(service.get_hackathon(conn, new_id)), 201
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        finally:
            conn.close()

    @app.get("/api/hackathons/<int:hackathon_id>")
    def get_hackathon(hackathon_id):
        conn = db.connect(retries=5)
        try:
            h = service.get_hackathon(conn, hackathon_id)
            if h is None:
                return jsonify({"error": "Hackathon not found."}), 404
            h["next_statuses"] = service.next_statuses(h["status"])
            h["modes"] = list(MODES)
            h["results"] = list(RESULTS)
            return jsonify(h)
        finally:
            conn.close()

    @app.post("/api/hackathons/<int:hackathon_id>/status")
    def update_status(hackathon_id):
        data = request.get_json(silent=True) or {}
        conn = db.connect(retries=5)
        try:
            service.change_status(conn, hackathon_id, data.get("status", ""))
            return jsonify(service.get_hackathon(conn, hackathon_id))
        except LookupError as err:
            return jsonify({"error": str(err)}), 404
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        finally:
            conn.close()

    @app.post("/api/hackathons/<int:hackathon_id>/teammates")
    def add_teammate(hackathon_id):
        data = request.get_json(silent=True) or {}
        conn = db.connect(retries=5)
        try:
            service.add_teammate(conn, hackathon_id, data.get("name", ""))
            return jsonify(service.get_hackathon(conn, hackathon_id))
        except LookupError as err:
            return jsonify({"error": str(err)}), 404
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        finally:
            conn.close()

    @app.post("/api/hackathons/<int:hackathon_id>/projects")
    def add_project(hackathon_id):
        data = request.get_json(silent=True) or {}
        conn = db.connect(retries=5)
        try:
            service.add_project(
                conn,
                hackathon_id,
                data.get("name", ""),
                data.get("result", ""),
                data.get("technologies", ""),
            )
            return jsonify(service.get_hackathon(conn, hackathon_id)), 201
        except LookupError as err:
            return jsonify({"error": str(err)}), 404
        except ValueError as err:
            return jsonify({"error": str(err)}), 400
        finally:
            conn.close()

    return app


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    serve(create_app(), host="0.0.0.0", port=PORT)
