from datetime import datetime, timezone
from db import get_db

print("INDEX.PY STARTED")

def insert_sample_thread():
    db = get_db()
    doc = {
        "author_display_name": "TestUser",
        "title": "Hello from VSCode",
        "body": "If you see this in Compass, DB works!",
        "tags": ["test"],
        "created_at": datetime.now(timezone.utc),
    }
    res = db.threads.insert_one(doc)
    print("Inserted thread id:", res.inserted_id)

if __name__ == "__main__":
    print("ABOUT TO INSERT")
    insert_sample_thread()