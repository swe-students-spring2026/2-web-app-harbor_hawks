# Central place to ensure all MongoDB indexes used by the app.

from threads_db import ensure_thread_indexes
from comments_db import ensure_comment_indexes
from users_db import ensure_user_indexes
from follows_db import ensure_follow_indexes


def ensure_all_indexes():
    """
    Ensure indexes for all collections.
    Safe to run multiple times.
    """
    ensure_thread_indexes()
    ensure_comment_indexes()
    ensure_user_indexes()
    ensure_follow_indexes()
    print("Indexes ensured: threads, comments, users, follows")