from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_login import UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.exceptions import BadRequest, Conflict, Unauthorized
from werkzeug.security import check_password_hash, generate_password_hash

from backend.db import get_db


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
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    doc = db.users.find_one({"_id": oid})
    if not doc:
        return None
    return MongoUser(_id=doc["_id"], email=doc["email"], display_name=doc.get("display_name"))


def ensure_user_indexes() -> None:
    db = get_db()
    db.users.create_index([("email", 1)], unique=True)


bp = Blueprint("auth", __name__)


@bp.get("/auth/me")
def me():
    if not current_user.is_authenticated:
        raise Unauthorized("Not logged in.")
    return jsonify({"ok": True, "user": current_user.to_json()})


@bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or None

    if not email or not password:
        raise BadRequest("email and password are required.")

    db = get_db()
    doc = {
        "email": email,
        "password_hash": generate_password_hash(password),
        "display_name": display_name,
    }

    try:
        res = db.users.insert_one(doc)
    except Exception as exc:
        # Most likely duplicate email (unique index) or DB down.
        raise Conflict("Account already exists (or DB error).") from exc

    user = MongoUser(_id=res.inserted_id, email=email, display_name=display_name)
    login_user(user)
    return jsonify({"ok": True, "user": user.to_json()}), 201


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        raise BadRequest("email and password are required.")

    db = get_db()
    doc = db.users.find_one({"email": email})
    if not doc or not check_password_hash(doc.get("password_hash", ""), password):
        raise Unauthorized("Invalid email or password.")

    user = MongoUser(_id=doc["_id"], email=doc["email"], display_name=doc.get("display_name"))
    login_user(user)
    return jsonify({"ok": True, "user": user.to_json()})


@bp.post("/auth/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True})

