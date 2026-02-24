from datetime import datetime, timezone
from bson import ObjectId
from db import get_db


def _oid(x):
    """Convert a string/ObjectId into ObjectId."""
    if isinstance(x, ObjectId):
        return x
    return ObjectId(str(x))


def follow(follower_id, followee_id):
    """
    Create a follow relationship.

    If the relationship already exists, this returns None (due to unique index).
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    doc = {
        "follower_id": _oid(follower_id),
        "followee_id": _oid(followee_id),
        "created_at": now,
    }
    try:
        res = db.follows.insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc
    except Exception:
        return None


def unfollow(follower_id, followee_id):
    """Remove a follow relationship."""
    db = get_db()
    res = db.follows.delete_one({"follower_id": _oid(follower_id), "followee_id": _oid(followee_id)})
    return res.deleted_count == 1


def list_following(user_id, limit=50, skip=0):
    """List who the user is following."""
    db = get_db()
    cursor = (
        db.follows.find({"follower_id": _oid(user_id)})
        .sort("created_at", -1)
        .skip(int(skip))
        .limit(int(limit))
    )
    return list(cursor)


def list_followers(user_id, limit=50, skip=0):
    """List who follows the user."""
    db = get_db()
    cursor = (
        db.follows.find({"followee_id": _oid(user_id)})
        .sort("created_at", -1)
        .skip(int(skip))
        .limit(int(limit))
    )
    return list(cursor)


def ensure_follow_indexes():
    """Create indexes for follows collection."""
    db = get_db()
    db.follows.create_index([("follower_id", 1), ("created_at", -1)])
    db.follows.create_index([("followee_id", 1), ("created_at", -1)])
    db.follows.create_index([("follower_id", 1), ("followee_id", 1)], unique=True)