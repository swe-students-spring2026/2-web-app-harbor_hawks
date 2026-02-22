from bson import ObjectId
try:
    from .threads_db import (
        ensure_thread_indexes,
        create_thread,
        list_threads,
        get_thread,
        update_thread,
        delete_thread,
        search_threads,
    )
except ImportError:  # allows `python backend/test_threads_crud.py`
    from threads_db import (
        ensure_thread_indexes,
        create_thread,
        list_threads,
        get_thread,
        update_thread,
        delete_thread,
        search_threads,
    )

def show_thread(t, label=""):
    if not t:
        print(label, "None")
        return
    print(label, {
        "id": str(t["_id"]),
        "author_display_name": t.get("author_display_name"),
        "title": t.get("title"),
        "tags": t.get("tags"),
    })

if __name__ == "__main__":
    ensure_thread_indexes()
    author_id = ObjectId()

    # CREATE
    t = create_thread(
        author_id=author_id,
        author_display_name="TestUser",
        title="Looking for study buddy",
        body="CSCI-UA 310 midterm prep",
        tags=["CSCI-UA 310", "study"]
    )
    show_thread(t, "CREATED:")

    # READ (list + get)
    all_threads = list_threads(limit=5)
    print("LIST count:", len(all_threads))
    one = get_thread(t["_id"])
    show_thread(one, "GOT:")

    # UPDATE (author only)
    ok = update_thread(t["_id"], author_id, {"title": "Updated title", "tags": ["study"]})
    print("UPDATE ok:", ok)
    show_thread(get_thread(t["_id"]), "AFTER UPDATE:")

    # SEARCH
    results = search_threads(q="Updated", limit=5)
    print("SEARCH results:", len(results))

    # DELETE (author only)
    deleted = delete_thread(t["_id"], author_id)
    print("DELETE ok:", deleted)
    print("AFTER DELETE get:", get_thread(t["_id"]))
