from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import ObjectId
from flask import Blueprint, jsonify, redirect, request, url_for
from flask_login import UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.exceptions import BadRequest, Conflict, Unauthorized
from backend.users_db import (
    authenticate_user,
    create_user_with_password,
    ensure_user_indexes,
    get_user,
    get_user_by_email,
)

@dataclass
class MongoUser(UserMixin):
    _id: ObjectId
    email: str
    display_name: str | None = None

    @property
    def id(self) -> str:  # Flask-Login uses this as the session identifier
        return str(self._id)

    def to_json(self) -> dict[str, Any]:
        return {"id": str(self._id), "email": self.email, "display_name": self.display_name}


def load_user_by_id(user_id: str) -> MongoUser | None:
    # Rehydrate Flask-Login user from Mongo.
    doc = get_user(user_id)
    if not doc:
        return None
    return MongoUser(_id=doc["_id"], email=doc["email"], display_name=doc.get("display_name"))

bp = Blueprint("auth", __name__)


@bp.get("/auth/me")
def me():
    # Returns the currently logged-in user.
    if not current_user.is_authenticated:
        raise Unauthorized("Not logged in.")
    return jsonify({"ok": True, "user": current_user.to_json()})


@bp.post("/auth/register")
def register():
    # Accept JSON for API clients and form posts for server-rendered pages.
    is_json_request = request.is_json
    data = request.get_json(silent=True) if is_json_request else request.form.to_dict()
    data = data or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    # Keep backward compatibility with legacy fullName field.
    display_name = (data.get("display_name") or data.get("fullName") or "").strip() or None

    if not email or not password:
        raise BadRequest("email and password are required.")

    # Optional pre-check for a nicer error message (unique index will also enforce this)
    if get_user_by_email(email):
        raise Conflict("Account already exists.")

    try:
        doc = create_user_with_password(email=email, password=password, display_name=display_name)
    except Exception as exc:
        raise Conflict("Account already exists (or DB error).") from exc

    user = MongoUser(_id=doc["_id"], email=doc["email"], display_name=doc.get("display_name"))
    login_user(user)

    if not is_json_request:
        # Browser form flow: continue to profile setup page.
        return redirect(url_for("setup_page"))

    return jsonify({"ok": True, "user": user.to_json()}), 201


@bp.post("/auth/login")
def login():
    # Login stays JSON-based for now.
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        raise BadRequest("email and password are required.")

    doc = authenticate_user(email=email, password=password)
    if not doc:
        raise Unauthorized("Invalid email or password.")

    user = MongoUser(_id=doc["_id"], email=doc["email"], display_name=doc.get("display_name"))
    login_user(user)
    return jsonify({"ok": True, "user": user.to_json()})


@bp.post("/auth/logout")
@login_required
def logout():
    # Clear current session cookie.
    logout_user()
    return jsonify({"ok": True})
