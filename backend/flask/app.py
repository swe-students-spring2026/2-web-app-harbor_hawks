from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Any

from bson import ObjectId
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from backend.flask.auth import bp as auth_bp
from backend.flask.auth import ensure_user_indexes, load_user_by_id
from backend.db import get_db
from backend.users_db import update_user_profile
# import the backend functions for threads that interact with the database
from backend.threads_db import (
    create_thread,
    delete_thread,
    get_thread,
    list_threads,
    search_threads,
    update_thread,
)


def _to_jsonable(value: Any) -> Any:
    # Normalize Mongo/Datetime values so jsonify can serialize them.
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def _json(payload: Any, status: int = 200):
    return jsonify(_to_jsonable(payload)), status

# Initialize the Flask app and all routes.
def create_app() -> Flask:
    project_root = Path(__file__).resolve().parents[2]
    app = Flask(
        __name__,
        template_folder=str(project_root / "public"),
        static_folder=str(project_root / "public"),
        static_url_path="",
    )
    app.config["JSON_SORT_KEYS"] = False
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    cors_origins = {
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://127.0.0.1:5500,http://localhost:5500",
        ).split(",")
        if origin.strip()
    }

    @app.after_request
    def _add_cors_headers(response):
        # Only echo trusted origins from env config.
        origin = request.headers.get("Origin")
        if origin and origin in cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def _user_loader(user_id: str):
        return load_user_by_id(user_id)

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        return _json({"ok": False, "error": exc.description}, exc.code or 500)

    @app.errorhandler(Exception)
    def _handle_uncaught_exception(exc: Exception):
        return _json({"ok": False, "error": str(exc)}, 500)

    @app.get("/api/health")
    def health():
        # Lightweight DB connectivity probe.
        db = get_db()
        db.client.admin.command("ping")
        return _json({"ok": True, "db": db.name})

    @app.get("/")
    def signup_page():
        # Server-rendered landing/signup page.
        return render_template("index.html")

    @app.get("/setup")
    def setup_page():
        # Server-rendered setup page, accessed after signup.
        return render_template("profile.html")

    @app.get("/img/<path:filename>")
    def image_asset(filename: str):
        # Serve logo/provider images from repo-level img/.
        return send_from_directory(project_root / "img", filename)

    @app.post('/api/setup')
    @login_required
    def profile_setup():
        # Receives data from http form (xxx-form-urlencoded)
        data = request.form.to_dict()
        if not data:
            raise BadRequest("Form data is required.")

        school = (data.get("school") or "").strip()
        grad_year = (data.get("classYear") or data.get("grad_year") or "").strip()
        major = (data.get("major") or "").strip()
        courses_raw = data.get("courses") or ""

        if not major or not grad_year:
            raise BadRequest("major and classYear are required.")

        courses = [item.strip() for item in str(courses_raw).split(",") if item.strip()]
        nyu_school = [school] if school else []

        updated = update_user_profile(
            current_user.id,
            {
                "major": major,
                "grad_year": grad_year,
                "courses": courses,
                "school": nyu_school,
            },
        )
        if not updated:
            raise NotFound("User not found.")
        
        print('User profile data saved.')
        return redirect(url_for("static", filename="dashboard.html"))


    # Register auth routes
    app.register_blueprint(auth_bp, url_prefix="/api")
    
    # -- API Routes for threads --
    @app.get("/api/threads")
    def api_list_threads():
        # Supports pagination and optional text/tag filtering.
        limit = request.args.get("limit", default=20, type=int)
        skip = request.args.get("skip", default=0, type=int)
        q = request.args.get("q", default=None, type=str)
        tag = request.args.get("tag", default=None, type=str)

        limit = max(1, min(int(limit), 100))
        skip = max(0, int(skip))

        if q or tag:
            threads = search_threads(q=q, tag=tag, limit=limit, skip=skip)
        else:
            threads = list_threads(limit=limit, skip=skip)

        return _json({"items": threads, "limit": limit, "skip": skip})

    @app.post("/api/threads")
    def api_create_thread():
        # Thread create remains JSON-only.
        data = request.get_json(silent=True) or {}

        author_id = data.get("author_id") or ObjectId()
        author_display_name = data.get("author_display_name")
        title = data.get("title")
        body = data.get("body")

        if not author_display_name or not title or not body:
            raise BadRequest("author_display_name, title, and body are required.")

        thread = create_thread(
            author_id=author_id,
            author_display_name=author_display_name,
            title=title,
            body=body,
            tags=data.get("tags"),
            photo_ids=data.get("photo_ids"),
        )
        return _json(thread, 201)

    @app.get("/api/threads/<thread_id>")
    def api_get_thread(thread_id: str):
        # Return one thread by id.
        try:
            thread = get_thread(thread_id)
        except Exception as exc:
            raise BadRequest("Invalid thread_id.") from exc

        if not thread:
            raise NotFound("Thread not found.")
        return _json(thread)

    @app.patch("/api/threads/<thread_id>")
    def api_update_thread(thread_id: str):
        # Author id is required to enforce ownership.
        data = request.get_json(silent=True) or {}
        author_id = data.get("author_id")
        if not author_id:
            raise BadRequest("author_id is required for updates.")

        patch = {k: v for k, v in data.items() if k != "author_id"}
        try:
            ok = update_thread(thread_id=thread_id, author_id=author_id, patch=patch)
        except Exception as exc:
            raise BadRequest("Invalid thread_id or author_id.") from exc

        if not ok:
            raise NotFound("Thread not found (or you are not the author).")

        return _json(get_thread(thread_id))

    @app.delete("/api/threads/<thread_id>")
    def api_delete_thread(thread_id: str):
        # Delete also enforces author ownership.
        data = request.get_json(silent=True) or {}
        author_id = data.get("author_id")
        if not author_id:
            raise BadRequest("author_id is required for deletes.")

        try:
            ok = delete_thread(thread_id=thread_id, author_id=author_id)
        except Exception as exc:
            raise BadRequest("Invalid thread_id or author_id.") from exc

        if not ok:
            raise NotFound("Thread not found (or you are not the author).")
        return _json({"ok": True})

    try:
        ensure_user_indexes()
    except Exception:
        # Keep the server booting even if MongoDB isn't running yet.
        pass

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
