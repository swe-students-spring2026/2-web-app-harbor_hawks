from datetime import datetime, timezone
from bson import ObjectId
from db import get_db


def _oid(x):
    """Convert a string/ObjectId into ObjectId."""
    if isinstance(x, ObjectId):
        return x
    return ObjectId(str(x))


def create_user(email, display_name, password_hash=None):
    """
    Create a user document.

    Note:
    - Store password_hash (NOT plaintext passwords).
    - password_hash can be None during early demo/dev.
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    doc = {
        "email": email.strip().lower(),
        "display_name": display_name.strip(),
        "password_hash": password_hash,
        "profile": {
            "major": "",
            "interests": [],
            "courses": [],
            "grad_year": "",
        },
        "created_at": now,
        "updated_at": now,
    }
    res = db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


def get_user_by_email(email):
    """Find a user by email."""
    db = get_db()
    return db.users.find_one({"email": email.strip().lower()})


def get_user(user_id):
    """Find a user by _id."""
    db = get_db()
    return db.users.find_one({"_id": _oid(user_id)})


def update_user_profile(user_id, patch):
    """
    Update profile fields for a user.

    Minimal rule:
    - "Only the owner can edit their profile" should be enforced by Flask routes.
    - DB layer only applies field whitelist + update.

    patch can include: major, interests, courses, grad_year
    """
    db = get_db()

    allowed = {"major", "interests", "courses", "grad_year"}
    patch = dict(patch)
    clean = {k: patch[k] for k in patch if k in allowed}

    # Light normalization
    if "major" in clean and isinstance(clean["major"], str):
        clean["major"] = clean["major"].strip()
    if "grad_year" in clean and isinstance(clean["grad_year"], str):
        clean["grad_year"] = clean["grad_year"].strip()

    res = db.users.update_one(
        {"_id": _oid(user_id)},
        {"$set": {"profile": clean, "updated_at": datetime.now(timezone.utc)}},
    )
    return res.modified_count == 1


def ensure_user_indexes():
    """Create indexes for the users collection."""
    db = get_db()
    db.users.create_index([("email", 1)], unique=True)
    db.users.create_index([("display_name", 1)])

    # Optional: helpful for filtering/search later
    db.users.create_index([("profile.major", 1)])
    db.users.create_index([("profile.grad_year", 1)])