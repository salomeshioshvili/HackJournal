import os
import time

import requests
from flask import Flask, g, jsonify, request

import db
import service

PORT = int(os.environ.get("PORT", "8002"))


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
            "service": "insights",
        }
        return jsonify(body), (200 if db_ok else 503)

    @app.get("/api/summary")
    def summary():
        """Insights page data. Needs log for stats; reflections still load if log is down."""
        conn = db.connect(retries=5)
        try:
            reflections = service.list_reflections(conn)
        finally:
            conn.close()

        try:
            records = service.fetch_log_records()
        except (requests.RequestException, ValueError) as err:
            return (
                jsonify(
                    {
                        "error": "log_unavailable",
                        "message": "Stats need the log service. Reflections below may still be incomplete.",
                        "detail": str(err),
                        "stats": None,
                        "gaps": [],
                        "upcoming": [],
                        "reflections": reflections,
                    }
                ),
                503,
            )

        return jsonify(
            {
                "stats": service.compute_stats(records),
                "gaps": service.skill_gaps(records),
                "upcoming": service.upcoming(records),
                "reflections": service.label_reflections(reflections, records),
            }
        )

    @app.get("/api/checklist/<int:hackathon_id>")
    def checklist(hackathon_id):
        try:
            records = service.fetch_log_records()
        except (requests.RequestException, ValueError) as err:
            return (
                jsonify(
                    {
                        "error": "log_unavailable",
                        "message": "Checklist needs the log service.",
                        "detail": str(err),
                    }
                ),
                503,
            )
        record = service.find_record(records, hackathon_id)
        if record is None:
            return jsonify({"error": "Hackathon not found."}), 404
        conn = db.connect(retries=5)
        try:
            rules = service.list_checklist_rules(conn)
        finally:
            conn.close()
        return jsonify(
            {
                "hackathon": record,
                "items": service.generate_checklist(record, rules),
            }
        )

    @app.get("/api/reflections")
    def list_reflections():
        conn = db.connect(retries=5)
        try:
            reflections = service.list_reflections(conn)
        finally:
            conn.close()
        try:
            records = service.fetch_log_records()
            reflections = service.label_reflections(reflections, records)
        except (requests.RequestException, ValueError):
            for row in reflections:
                row["hackathon_name"] = "Unknown"
        return jsonify(reflections)

    @app.post("/api/reflections")
    def create_reflection():
        data = request.get_json(silent=True) or {}
        try:
            hackathon_id = int(data.get("hackathon_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "hackathon_id must be a number."}), 400

        try:
            records = service.fetch_log_records()
        except (requests.RequestException, ValueError) as err:
            return (
                jsonify(
                    {
                        "error": "log_unavailable",
                        "message": "Creating a reflection needs the log service.",
                        "detail": str(err),
                    }
                ),
                503,
            )

        try:
            cleaned = service.validate_reflection(
                service.find_record(records, hackathon_id),
                data.get("went_well"),
                data.get("went_badly"),
                data.get("lesson"),
            )
        except ValueError as err:
            return jsonify({"error": str(err)}), 400

        conn = db.connect(retries=5)
        try:
            new_id = service.add_reflection(conn, cleaned)
            return jsonify({"id": new_id, **cleaned}), 201
        finally:
            conn.close()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
