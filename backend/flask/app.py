from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Any

from bson import ObjectId
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_login import LoginManager, current_user, login_required
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from backend.flask.auth import bp as auth_bp
from backend.flask.auth import ensure_user_indexes, load_user_by_id
from backend.db import get_db
from backend.users_db import (
    get_user,
    get_user_by_email,
    update_user_account,
    update_user_profile,
)
# import the backend functions for threads that interact with the database
from backend.threads_db import (
    create_thread,
    delete_thread,
    get_thread,
    list_threads,
    search_threads,
    update_thread,
)

from backend.comments_db import (
    list_comments,
    add_comment,
    update_comment,
    delete_comment,
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


def _csv_to_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _list_to_csv(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        return value
    return ""


def _profile_template_context(
    *,
    user_id: str,
    page_mode: str,
    account_status: str | None = None,
    profile_status: str | None = None,
) -> dict[str, Any]:
    doc = get_user(user_id)
    if not doc:
        raise NotFound("User not found.")

    profile = doc.get("profile") or {}
    return {
        "page_mode": page_mode,
        "display_name": doc.get("display_name") or "",
        "email": doc.get("email") or "",
        "school": profile.get("school") or "",
        "grad_year": profile.get("grad_year") or "",
        "major": profile.get("major") or "",
        "interests": _list_to_csv(profile.get("interests")),
        "courses": _list_to_csv(profile.get("courses")),
        "account_status": account_status,
        "profile_status": profile_status,
    }


def _submit_profile_form():
    school = (request.form.get("school") or "").strip()
    grad_year = (request.form.get("grad_year") or request.form.get("classYear") or "").strip()
    major = (request.form.get("major") or "").strip()
    interests = _csv_to_list(request.form.get("interests") or "")
    courses = _csv_to_list(request.form.get("courses") or "")
    next_page = (request.form.get("next") or "profile").strip().lower()

    if not school or not grad_year or not major:
        raise BadRequest("school, classYear, and major are required.")

    ok = update_user_profile(
        user_id=current_user.id,
        patch={
            "school": school,
            "grad_year": grad_year,
            "major": major,
            "interests": interests,
            "courses": courses,
        },
    )
    if not ok:
        raise NotFound("User not found.")

    if next_page == "dashboard":
        return render_template("redirect.html", to="/dashboard")
    if next_page == "setup":
        return render_template("redirect.html", to="/setup?profile_status=saved")
    return render_template("redirect.html", to="/profile?profile_status=saved")


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

    @app.get("/img/<path:filename>")
    def image_asset(filename: str):
        # Serve logo/provider images from repo-level img/.
        return send_from_directory(project_root / "img", filename)

    app.register_blueprint(auth_bp, url_prefix="/api")

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
    @login_required
    def api_create_thread():
        data = request.get_json(silent=True) or {}

        title = data.get("title")
        body = data.get("body")
        if not title or not body:
            raise BadRequest("title and body are required.")
        
        author_id = current_user.id
        author_display_name = current_user.display_name or current_user.email

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

    @app.get("/t/<thread_id>")
    def page_thread(thread_id: str):
        try:
            thread = get_thread(thread_id)
        except Exception as exc:
            raise BadRequest("Invalid thread_id.") from exc

        if not thread:
            raise NotFound("Thread not found.")

        comments = list_comments(thread_id, limit=200, skip=0)  # 你已有 comments_db.list_comments
        is_owner = current_user.is_authenticated and str(current_user.id) == str(thread.get("author_id"))

        return render_template(
            "thread.html",
            thread=thread,
            comments=comments,
            is_owner=is_owner,
        )

    @app.patch("/api/threads/<thread_id>")
    @login_required
    def api_update_thread(thread_id: str):
        data = request.get_json(silent=True) or {}

        patch = {k: v for k, v in data.items() if k in {"title", "body", "tags", "photo_ids"}}

        try:
            ok = update_thread(thread_id=thread_id, author_id=current_user.id, patch=patch)
        except Exception as exc:
            raise BadRequest("Invalid thread_id.") from exc

        if not ok:
            raise NotFound("Thread not found (or you are not the author).")

        return _json(get_thread(thread_id))

    @app.delete("/api/threads/<thread_id>")
    @login_required
    def api_delete_thread(thread_id: str):
        try:
            ok = delete_thread(thread_id=thread_id, author_id=current_user.id)
        except Exception as exc:
            raise BadRequest("Invalid thread_id.") from exc

        if not ok:
            raise NotFound("Thread not found (or you are not the author).")

        return _json({"ok": True})

    return app


app = create_app()

@app.get("/login")
def login_page():
    return render_template("login.html")


@app.get("/setup")
@login_required
def setup_page():
    return render_template(
        "setup.html",
        **_profile_template_context(
            user_id=current_user.id,
            page_mode="setup",
            account_status=request.args.get("account_status"),
            profile_status=request.args.get("profile_status"),
        ),
    )


@app.post("/setup")
@login_required
def setup_submit():
    return _submit_profile_form()


@app.get("/profile")
@login_required
def profile_page():
    return render_template(
        "profile.html",
        **_profile_template_context(
            user_id=current_user.id,
            page_mode="profile",
            account_status=request.args.get("account_status"),
            profile_status=request.args.get("profile_status"),
        ),
    )


@app.post("/profile/setup")
@login_required
def profile_setup():
    return _submit_profile_form()


@app.post("/profile/account")
@login_required
def account_update():
    display_name = (request.form.get("display_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    next_page = (request.form.get("next") or "profile").strip().lower()

    if not display_name or not email:
        raise BadRequest("display_name and email are required.")

    existing = get_user_by_email(email)
    if existing and str(existing["_id"]) != str(current_user.id):
        if next_page == "setup":
            return render_template("redirect.html", to="/setup?account_status=email_taken")
        return render_template("redirect.html", to="/profile?account_status=email_taken")

    ok = update_user_account(
        user_id=current_user.id,
        patch={
            "display_name": display_name,
            "email": email,
            "password": password,
        },
    )
    if not ok:
        raise NotFound("User not found.")

    if next_page == "setup":
        return render_template("redirect.html", to="/setup?account_status=saved")
    return render_template("redirect.html", to="/profile?account_status=saved")


@app.get("/logout")
@login_required
def logout_page():
    return render_template("logout.html")


@app.get("/dashboard")
@login_required
def dashboard_page():
    # Optional: allow browsing even if not logged in
    q = request.args.get("q")
    tag = request.args.get("tag")
    if q or tag:
        items = search_threads(q=q, tag=tag, limit=50, skip=0)
    else:
        items = list_threads(limit=50, skip=0)
    return render_template("dashboard.html", threads=items, q=q or "", tag=tag or "")


@app.get("/t/<thread_id>")
def thread_page(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        raise NotFound("Thread not found.")
    comments = list_comments(thread_id, limit=200, skip=0)
    return render_template("thread.html", thread=thread, comments=comments)


@app.route("/t/new", methods=["GET", "POST"])
@login_required
def thread_new_page():
    if request.method == "GET":
        return render_template("thread_form.html", mode="new", thread=None)

    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    tags_raw = (request.form.get("tags") or "").strip()

    if not title or not body:
        raise BadRequest("title and body are required.")

    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    doc = create_thread(
        author_id=current_user.id,
        author_display_name=current_user.display_name or current_user.email,
        title=title,
        body=body,
        tags=tags,
        photo_ids=[],
    )
    return render_template("redirect.html", to=f"/t/{doc['_id']}")


@app.route("/t/<thread_id>/edit", methods=["GET", "POST"])
@login_required
def thread_edit_page(thread_id: str):
    thread = get_thread(thread_id)
    if not thread:
        raise NotFound("Thread not found.")

    # ownership check (thread['author_id'] is ObjectId)
    if str(thread.get("author_id")) != str(current_user.id):
        raise NotFound("Thread not found (or you are not the author).")

    if request.method == "GET":
        return render_template("thread_form.html", mode="edit", thread=thread)

    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    tags_raw = (request.form.get("tags") or "").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    ok = update_thread(thread_id=thread_id, author_id=current_user.id, patch={
        "title": title,
        "body": body,
        "tags": tags,
    })
    if not ok:
        raise NotFound("Thread not found (or you are not the author).")

    return render_template("redirect.html", to=f"/t/{thread_id}")


@app.post("/t/<thread_id>/delete")
@login_required
def thread_delete_page(thread_id: str):
    ok = delete_thread(thread_id=thread_id, author_id=current_user.id)
    if not ok:
        raise NotFound("Thread not found (or you are not the author).")
    return render_template("redirect.html", to="/dashboard")


@app.post("/t/<thread_id>/comment")
@login_required
def comment_add_page(thread_id: str):
    body = (request.form.get("body") or "").strip()
    if not body:
        raise BadRequest("comment body required.")

    add_comment(
        thread_id=thread_id,
        author_id=current_user.id,
        author_display_name=current_user.display_name or current_user.email,
        body=body,
    )
    return render_template("redirect.html", to=f"/t/{thread_id}")


@app.route("/c/<comment_id>/edit", methods=["GET", "POST"])
@login_required
def comment_edit_page(comment_id: str):
    # We don’t have get_comment() in DB layer, so fetch via query:
    db = get_db()
    c = db.comments.find_one({"_id": ObjectId(comment_id)})
    if not c:
        raise NotFound("Comment not found.")
    if str(c.get("author_id")) != str(current_user.id):
        raise NotFound("Comment not found (or you are not the author).")

    if request.method == "GET":
        return render_template("comment_form.html", comment=c)

    body = (request.form.get("body") or "").strip()
    ok = update_comment(comment_id=comment_id, author_id=current_user.id, body=body)
    if not ok:
        raise NotFound("Comment not found (or you are not the author).")

    return render_template("redirect.html", to=f"/t/{c['thread_id']}")


@app.post("/c/<comment_id>/delete")
@login_required
def comment_delete_page(comment_id: str):
    db = get_db()
    c = db.comments.find_one({"_id": ObjectId(comment_id)})
    if not c:
        raise NotFound("Comment not found.")

    ok = delete_comment(comment_id=comment_id, author_id=current_user.id)
    if not ok:
        raise NotFound("Comment not found (or you are not the author).")

    return render_template("redirect.html", to=f"/t/{c['thread_id']}")


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
