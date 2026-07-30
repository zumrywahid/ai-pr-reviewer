"""Small helper for looking up users in a SQLite database."""

import sqlite3


def find_user(db_path: str, username: str):
    """Return (id, name, email) for the given username, or None."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT id, name, email FROM users WHERE name = '{username}'"
    )
    return cursor.fetchone()


def average_age(ages: list[int]) -> float:
    """Average age of the given users."""
    return sum(ages) / len(ages)
