from datetime import datetime, timezone
from bson import ObjectId
from db import get_db


def _oid(x):
    """Convert a string/ObjectId into ObjectId."""
    if isinstance(x, ObjectId):
        return x
    return ObjectId(str(x))


def add_comment(thread_id, author_id, author_display_name, body):
    """Insert a comment for a given thread."""
    db = get_db()
    now = datetime.now(timezone.utc)

    doc = {
        "thread_id": _oid(thread_id),
        "author_id": _oid(author_id),
        "author_display_name": author_display_name,
        "body": body.strip(),
        "created_at": now,
        "updated_at": now,
    }
    res = db.comments.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


def list_comments(thread_id, limit=50, skip=0):
    """List comments for a thread (oldest -> newest)."""
    db = get_db()
    cursor = (
        db.comments.find({"thread_id": _oid(thread_id)})
        .sort("created_at", 1)
        .skip(int(skip))
        .limit(int(limit))
    )
    return list(cursor)


def delete_comment(comment_id, author_id):
    """
    Delete a comment.

    Minimal permission rule:
    - Only the author can delete their own comment.
    """
    db = get_db()
    res = db.comments.delete_one({"_id": _oid(comment_id), "author_id": _oid(author_id)})
    return res.deleted_count == 1


def ensure_comment_indexes():
    """Create indexes for the comments collection."""
    db = get_db()
    db.comments.create_index([("thread_id", 1), ("created_at", 1)])