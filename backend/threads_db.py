from datetime import datetime, timezone
from bson import ObjectId
try:
    from .db import get_db
except ImportError:  # allows `python backend/threads_db.py`
    from db import get_db

def _oid(x):
    """Convert string/ObjectId -> ObjectId."""
    if isinstance(x, ObjectId):
        return x
    return ObjectId(str(x))

def create_thread(author_id, author_display_name, title, body, tags=None, photo_ids=None):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "author_id": _oid(author_id),
        "author_display_name": author_display_name,
        "title": title.strip(),
        "body": body.strip(),
        "tags": tags or [],
        "photo_ids": photo_ids or [],
        "created_at": now,
        "updated_at": now,
    }
    res = db.threads.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

def list_threads(limit=20, skip=0):
    db = get_db()
    cursor = db.threads.find({}).sort("created_at", -1).skip(int(skip)).limit(int(limit))
    return list(cursor)

def get_thread(thread_id):
    db = get_db()
    return db.threads.find_one({"_id": _oid(thread_id)})

def update_thread(thread_id, author_id, patch):
    """
    Only allow the author to update.
    patch can include: title, body, tags, photo_ids
    """
    db = get_db()
    patch = dict(patch)

    # Only allow safe fields
    allowed = {"title", "body", "tags", "photo_ids"}
    patch = {k: v for k, v in patch.items() if k in allowed}

    if "title" in patch and isinstance(patch["title"], str):
        patch["title"] = patch["title"].strip()
    if "body" in patch and isinstance(patch["body"], str):
        patch["body"] = patch["body"].strip()

    patch["updated_at"] = datetime.now(timezone.utc)

    res = db.threads.update_one(
        {"_id": _oid(thread_id), "author_id": _oid(author_id)},
        {"$set": patch},
    )
    return res.modified_count == 1

def delete_thread(thread_id, author_id):
    db = get_db()
    res = db.threads.delete_one({"_id": _oid(thread_id), "author_id": _oid(author_id)})
    return res.deleted_count == 1

def search_threads(q=None, tag=None, limit=20, skip=0):
    """
    Simple search:
    - if you have a text index, uses $text
    - tag filter uses exact match in tags array
    """
    db = get_db()
    filter_ = {}
    if tag:
        filter_["tags"] = tag
    if q:
        filter_["$text"] = {"$search": q}

    cursor = db.threads.find(filter_).sort("created_at", -1).skip(int(skip)).limit(int(limit))
    return list(cursor)

def ensure_thread_indexes():
    """
    Run once at startup or manually.
    """
    db = get_db()
    db.threads.create_index([("created_at", -1)])
    db.threads.create_index([("tags", 1)])
    db.threads.create_index([("title", "text"), ("body", "text")])
