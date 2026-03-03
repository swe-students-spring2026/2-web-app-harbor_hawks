from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, current_user, login_required
from werkzeug.exceptions import BadRequest, Conflict, HTTPException, NotFound

from backend.flask.auth import bp as auth_bp
from backend.flask.auth import ensure_user_indexes, load_user_by_id
from backend.db import get_db
from backend.users_db import get_user, update_user_account, update_user_profile
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


def _profile_form_values(user_doc: dict[str, Any]) -> dict[str, str]:
    profile = user_doc.get("profile") or {}

    school_raw = profile.get("school") or []
    if isinstance(school_raw, list):
        school = school_raw[0] if school_raw else ""
    elif isinstance(school_raw, str):
        school = school_raw
    else:
        school = ""

    interests = profile.get("interests") or []
    courses = profile.get("courses") or []

    return {
        "display_name": str(user_doc.get("display_name") or ""),
        "email": str(user_doc.get("email") or ""),
        "school": str(school),
        "grad_year": str(profile.get("grad_year") or ""),
        "major": str(profile.get("major") or ""),
        "interests": ", ".join(str(item).strip() for item in interests if str(item).strip()),
        "courses": ", ".join(str(item).strip() for item in courses if str(item).strip()),
    }


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
    @login_required
    def setup_page():
        # Server-rendered setup page, accessed after signup/login.
        user_doc = get_user(current_user.id)
        if not user_doc:
            raise NotFound("User not found.")
        return render_template(
            "setup.html",
            page_mode="setup",
            account_status=request.args.get("account_status", ""),
            profile_status=request.args.get("profile_status", ""),
            **_profile_form_values(user_doc),
        )

    @app.get("/profile")
    @login_required
    def profile_page():
        # Account/profile settings page.
        user_doc = get_user(current_user.id)
        if not user_doc:
            raise NotFound("User not found.")
        return render_template(
            "profile.html",
            page_mode="profile",
            account_status=request.args.get("account_status", ""),
            profile_status=request.args.get("profile_status", ""),
            **_profile_form_values(user_doc),
        )

    @app.get("/logout")
    def logout_page():
        # Server-rendered logout page that calls auth logout endpoint.
        return render_template("logout.html")

    @app.get("/img/<path:filename>")
    def image_asset(filename: str):
        # Serve logo/provider images from repo-level img/.
        return send_from_directory(project_root / "img", filename)

    @app.post("/api/account")
    @login_required
    def account_update():
        # Receives account updates from JSON clients or browser form posts.
        is_json_request = request.is_json
        data = request.get_json(silent=True) if is_json_request else request.form.to_dict()
        data = data or {}

        display_name = (data.get("display_name") or data.get("fullName") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        patch = {}
        if display_name:
            patch["display_name"] = display_name
        if email:
            patch["email"] = email
        if password:
            patch["password"] = password

        if not patch:
            raise BadRequest("At least one of display_name, email, or password is required.")

        try:
            updated = update_user_account(current_user.id, patch)
        except DuplicateKeyError as exc:
            if not is_json_request:
                return redirect(url_for("profile_page", account_status="email_taken"))
            raise Conflict("That email is already in use.") from exc

        if not updated:
            raise NotFound("User not found.")

        if not is_json_request:
            return redirect(url_for("profile_page", account_status="saved"))

        updated_user = get_user(current_user.id)
        if not updated_user:
            raise NotFound("User not found.")
        return _json(
            {
                "ok": True,
                "user": {
                    "id": str(updated_user["_id"]),
                    "display_name": updated_user.get("display_name"),
                    "email": updated_user.get("email"),
                },
            }
        )

    # Setup/profile submit endpoint.
    @app.post("/api/setup", endpoint="profile_setup")
    @app.post("/api/setup", endpoint="setup_submit")
    @login_required
    def setup_submit():
        # Receives profile updates from JSON clients or browser form posts.
        is_json_request = request.is_json
        data = request.get_json(silent=True) if is_json_request else request.form.to_dict()
        data = data or {}
        if not data:
            raise BadRequest("Form data is required.")

        school = (data.get("school") or "").strip()
        grad_year = (data.get("classYear") or data.get("grad_year") or "").strip()
        major = (data.get("major") or "").strip()
        interests_raw = data.get("interests") or ""
        courses_raw = data.get("courses") or ""
        next_target = (data.get("next") or "").strip().lower()

        if not major or not grad_year:
            raise BadRequest("major and classYear are required.")

        interests = [item.strip() for item in str(interests_raw).split(",") if item.strip()]
        courses = [item.strip() for item in str(courses_raw).split(",") if item.strip()]
        nyu_school = [school] if school else []

        updated = update_user_profile(
            current_user.id,
            {
                "major": major,
                "grad_year": grad_year,
                "interests": interests,
                "courses": courses,
                "school": nyu_school,
            },
        )
        if not updated:
            raise NotFound("User not found.")

        if not is_json_request:
            if next_target == "dashboard":
                return redirect(url_for("static", filename="dashboard.html"))
            return redirect(url_for("profile_page", profile_status="saved"))

        return _json({"ok": True})


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
