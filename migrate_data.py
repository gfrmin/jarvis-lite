#!/usr/bin/env python3
"""One-time migration: Render PostgreSQL → local SQLite. Delete after use."""

import os
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ["DATABASE_URL"]
DB_PATH = Path(__file__).parent / "jarvis.db"


def migrate():
    pg = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    sl = sqlite3.connect(DB_PATH)
    sl.execute("PRAGMA journal_mode=WAL")

    sl.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            list TEXT NOT NULL DEFAULT 'inbox',
            due_date TEXT,
            is_today INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """)
    sl.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)")
    sl.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            email TEXT NOT NULL,
            subscribed_at TEXT DEFAULT (datetime('now'))
        )
    """)

    with pg.cursor() as cur:
        cur.execute("SELECT * FROM tasks ORDER BY id")
        tasks = cur.fetchall()
        print(f"Migrating {len(tasks)} tasks...")
        for t in tasks:
            sl.execute(
                "INSERT INTO tasks (id, user_id, text, list, due_date, is_today, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    t["id"],
                    t["user_id"],
                    t["text"],
                    t["list"],
                    str(t["due_date"]) if t["due_date"] else None,
                    int(t.get("is_today", False)),
                    str(t["created_at"]) if t["created_at"] else None,
                    str(t["completed_at"]) if t["completed_at"] else None,
                ),
            )

        cur.execute("SELECT * FROM subscriptions ORDER BY id")
        subs = cur.fetchall()
        print(f"Migrating {len(subs)} subscriptions...")
        for s in subs:
            sl.execute(
                "INSERT INTO subscriptions (id, user_id, email, subscribed_at) VALUES (?, ?, ?, ?)",
                (s["id"], s["user_id"], s["email"], str(s["subscribed_at"]) if s["subscribed_at"] else None),
            )

    sl.commit()
    sl.close()
    pg.close()
    print(f"Done. Data written to {DB_PATH}")


if __name__ == "__main__":
    migrate()
