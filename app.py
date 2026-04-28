# =============================================================================
# app.py  —  University Fee Tracking System  |  Flask entry point
# =============================================================================
# Project structure
# ├── app.py                   ← you are here
# ├── database/
# │   ├── db.py
# │   ├── schema.sql
# │   └── seed.sql
# ├── routes/
# │   ├── student.py
# │   └── fees.py
# ├── static/
# │   ├── index.html
# │   ├── css/
# │   │   └── style.css
# │   └── js/
# │       └── app.js
# ├── requirements.txt
# ├── render.yaml
# └── .env
# =============================================================================

import os
from flask import Flask, jsonify
from flask_cors import CORS

from database.db import init_db, seed_db
from routes.student import students_bp
from routes.fees    import fees_bp


def create_app() -> Flask:
    """Application factory — called by gunicorn in production."""
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    # ── Blueprints ─────────────────────────────────────────────────────────
    app.register_blueprint(students_bp)   # /api/students/…
    app.register_blueprint(fees_bp)       # /api/fees/…

    # ── Serve the SPA for every non-API route ──────────────────────────────
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        return app.send_static_file("index.html")

    # ── Global error handlers ───────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(exc):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(exc):
        return jsonify({"error": "Internal server error"}), 500

    return app


# ── Gunicorn entry point ────────────────────────────────────────────────────
# Gunicorn imports this as:  gunicorn "app:application"
init_db()
application = create_app()


# ── Local dev entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    seed_db()   # seed only in local dev; not in production
    application.run(debug=True, host="0.0.0.0", port=5000)