import uuid
from bson import ObjectId

from indexes import ensure_all_indexes

from users_db import create_user, get_user_by_email, update_user_profile, get_user
from threads_db import create_thread, list_threads, get_thread, update_thread, delete_thread, search_threads
from comments_db import add_comment, list_comments, delete_comment
from follows_db import follow, unfollow, list_following, list_followers


def test_users():
    print("\n=== USERS TEST ===")
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    u = create_user(email=email, display_name="Test User", password_hash="dummy_hash")
    print("Created user:", u["_id"], u["email"])

    u2 = get_user_by_email(email)
    assert u2 is not None, "get_user_by_email should return a user"
    print("Lookup by email:", u2["_id"])

    ok = update_user_profile(u2["_id"], {
        "major": "Math & CS",
        "interests": ["study buddy", "tennis"],
        "courses": ["CSCI-UA 310", "Probability"],
        "grad_year": "2027",
        "unexpected_field": "should_be_ignored",
    })
    assert ok is True, "update_user_profile should succeed"

    u3 = get_user(u2["_id"])
    print("Profile now:", u3["profile"])
    assert u3["profile"]["major"] == "Math & CS", "profile.major should be updated"

    return u3


def test_threads(author_id):
    print("\n=== THREADS TEST ===")
    t = create_thread(
        author_id=author_id,
        author_display_name="Alice",
        title="Looking for study buddy",
        body="CSCI-UA 310 midterm prep",
        tags=["CSCI-UA 310", "study"]
    )
    print("Created thread:", t["_id"])

    ts = list_threads(limit=5)
    print("List threads count:", len(ts))

    one = get_thread(t["_id"])
    assert one is not None, "get_thread should return the created thread"
    print("Got thread title:", one["title"])

    ok = update_thread(t["_id"], author_id, {"title": "Updated title", "tags": ["study"]})
    assert ok is True, "update_thread should succeed for the author"

    after = get_thread(t["_id"])
    assert after["title"] == "Updated title", "thread title should be updated"
    print("Updated thread title:", after["title"])

    results = search_threads(q="Updated", limit=5)
    print("Search results:", len(results))

    return t


def test_comments(thread_id, author_id):
    print("\n=== COMMENTS TEST ===")
    c1 = add_comment(thread_id, author_id, "Alice", "First comment!")
    c2 = add_comment(thread_id, author_id, "Alice", "Second comment!")
    print("Created comments:", c1["_id"], c2["_id"])

    cs = list_comments(thread_id)
    print("List comments count:", len(cs))
    assert len(cs) >= 2, "Should list at least 2 comments"

    ok = delete_comment(c1["_id"], author_id)
    assert ok is True, "delete_comment should succeed for the author"
    cs2 = list_comments(thread_id)
    print("After delete count:", len(cs2))


def test_follows():
    print("\n=== FOLLOWS TEST ===")
    a = ObjectId()
    b = ObjectId()

    f = follow(a, b)
    print("Follow created:", f is not None)

    following = list_following(a)
    followers = list_followers(b)
    print("A following count:", len(following))
    print("B followers count:", len(followers))

    ok = unfollow(a, b)
    assert ok is True, "unfollow should succeed"
    print("Unfollow ok:", ok)


def cleanup_thread(thread_id, author_id):
    print("\n=== CLEANUP ===")
    ok = delete_thread(thread_id, author_id)
    print("Delete thread ok:", ok)


if __name__ == "__main__":
    # This line guarantees you see output immediately if the file runs.
    print("STARTING DB TESTS...")

    # Ensure indexes first (safe to run multiple times).
    ensure_all_indexes()

    # Users
    user = test_users()
    author_id = user["_id"]

    # Threads
    thread = test_threads(author_id)

    # Comments
    test_comments(thread["_id"], author_id)

    # Follow/unfollow
    test_follows()

    # Cleanup
    cleanup_thread(thread["_id"], author_id)

    print("\nALL DB TESTS PASSED")