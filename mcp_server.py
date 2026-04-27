#!/usr/bin/env python3
"""Jarvis Lite GTD MCP Server — task management tools for Claude Code."""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "jarvis.db"
VALID_LISTS = ("inbox", "next", "scheduled", "someday")

mcp = FastMCP("jarvis-gtd")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_list
            ON tasks (user_id, list) WHERE completed_at IS NULL
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                email TEXT NOT NULL,
                subscribed_at TEXT DEFAULT (datetime('now'))
            )
        """)


def _parse_due_date(s: str | None) -> str | None:
    if not s:
        return None
    try:
        date.fromisoformat(s)
        return s
    except (ValueError, TypeError):
        return None


def _format_task(row: sqlite3.Row) -> str:
    parts = [f"[{row['id']}]"]
    if row["is_today"]:
        parts.append("★")
    parts.append(row["text"])
    parts.append(f"#{row['list']}")
    if row["due_date"]:
        parts.append(f"(due {row['due_date']})")
    return " ".join(parts)


def _format_task_list(rows: list[sqlite3.Row], header: str = "") -> str:
    if not rows:
        return f"{header}\nNo tasks." if header else "No tasks."
    lines = [header] if header else []
    for row in rows:
        lines.append(f"  {_format_task(row)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------

@mcp.tool()
def add_task(
    user_id: int,
    text: str,
    list_name: str = "inbox",
    due_date: str | None = None,
    is_today: bool = False,
) -> str:
    """Add a new task to the GTD system."""
    if list_name not in VALID_LISTS:
        return f"Invalid list '{list_name}'. Use one of: {', '.join(VALID_LISTS)}"
    parsed_date = _parse_due_date(due_date)
    if due_date and not parsed_date:
        return f"Invalid date '{due_date}'. Use YYYY-MM-DD format."
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, text, list, due_date, is_today) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, list_name, parsed_date, int(is_today)),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    due_info = f" (due {parsed_date})" if parsed_date else ""
    return f"Added [{row['id']}] {text} to #{list_name}{due_info}"


@mcp.tool()
def complete_task(
    user_id: int,
    task_id: int | None = None,
    text_match: str | None = None,
) -> str:
    """Complete a task by ID or partial text match."""
    with get_db() as conn:
        if task_id is not None:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND user_id = ? AND completed_at IS NULL",
                (task_id, user_id),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE tasks SET completed_at = datetime('now'), is_today = 0 WHERE id = ? AND user_id = ?",
                    (task_id, user_id),
                )
        elif text_match:
            row = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL AND text LIKE ? ORDER BY id LIMIT 1",
                (user_id, f"%{text_match}%"),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE tasks SET completed_at = datetime('now'), is_today = 0 WHERE id = ? AND user_id = ?",
                    (row["id"], user_id),
                )
        else:
            return "Specify a task_id or text_match to complete."
    if not row:
        return "Task not found."
    return f"Completed: {row['text']}"


@mcp.tool()
def delete_task(user_id: int, task_id: int) -> str:
    """Delete a task by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
        ).fetchone()
        if not row:
            return "Task not found."
        conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    return f"Deleted: {row['text']}"


@mcp.tool()
def move_task(
    user_id: int,
    task_id: int,
    new_list: str,
    due_date: str | None = None,
) -> str:
    """Move a task to a different list."""
    if new_list not in VALID_LISTS:
        return f"Invalid list '{new_list}'. Use one of: {', '.join(VALID_LISTS)}"
    parsed_date = _parse_due_date(due_date)
    if due_date and not parsed_date:
        return f"Invalid date '{due_date}'. Use YYYY-MM-DD format."
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET list = ?, due_date = ? WHERE id = ? AND user_id = ? AND completed_at IS NULL",
            (new_list, parsed_date, task_id, user_id),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
    if not row:
        return "Task not found."
    due_info = f" (due {parsed_date})" if parsed_date else ""
    return f"Moved [{row['id']}] {row['text']} to #{new_list}{due_info}"


@mcp.tool()
def mark_today(user_id: int, task_id: int, is_today: bool = True) -> str:
    """Mark or unmark a task for today's focus."""
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET is_today = ? WHERE id = ? AND user_id = ? AND completed_at IS NULL",
            (int(is_today), task_id, user_id),
        )
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)).fetchone()
    if not row:
        return "Task not found."
    action = "Marked for today" if is_today else "Unmarked from today"
    return f"{action}: [{row['id']}] {row['text']}"


@mcp.tool()
def clear_today(user_id: int) -> str:
    """Clear all today flags for a user."""
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE tasks SET is_today = 0 WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL",
            (user_id,),
        )
    return f"Cleared today flag from {cur.rowcount} tasks."


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_tasks(user_id: int, list_name: str | None = None) -> str:
    """Get tasks, optionally filtered by list."""
    with get_db() as conn:
        if list_name:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND list = ? AND completed_at IS NULL ORDER BY id",
                (user_id, list_name),
            ).fetchall()
            header = f"#{list_name}:"
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL ORDER BY list, id",
                (user_id,),
            ).fetchall()
            header = "All tasks:"
    return _format_task_list(rows, header)


@mcp.tool()
def get_today_tasks(user_id: int) -> str:
    """Get tasks marked for today's focus."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL ORDER BY list, id",
            (user_id,),
        ).fetchall()
    return _format_task_list(rows, "Today's focus:")


@mcp.tool()
def get_tasks_by_tag(user_id: int, tag: str) -> str:
    """Get tasks containing a specific @tag."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND completed_at IS NULL AND text LIKE ? ORDER BY list, id",
            (user_id, f"%@{tag}%"),
        ).fetchall()
    return _format_task_list(rows, f"@{tag} tasks:")


@mcp.tool()
def get_tasks_due_today(user_id: int) -> str:
    """Get scheduled tasks due today."""
    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date = ? AND completed_at IS NULL ORDER BY id",
            (user_id, today),
        ).fetchall()
    return _format_task_list(rows, "Due today:")


@mcp.tool()
def get_overdue_tasks(user_id: int) -> str:
    """Get overdue scheduled tasks."""
    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND list = 'scheduled' AND due_date < ? AND completed_at IS NULL ORDER BY due_date, id",
            (user_id, today),
        ).fetchall()
    return _format_task_list(rows, "Overdue:")


@mcp.tool()
def get_task_counts(user_id: int) -> str:
    """Get summary counts of tasks by list."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT list, COUNT(*) as count FROM tasks WHERE user_id = ? AND completed_at IS NULL GROUP BY list",
            (user_id,),
        ).fetchall()
        counts = {row["list"]: row["count"] for row in rows}
        for lst in VALID_LISTS:
            counts.setdefault(lst, 0)
        today_count = conn.execute(
            "SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND is_today = 1 AND completed_at IS NULL",
            (user_id,),
        ).fetchone()["count"]
        counts["today"] = today_count
    lines = ["Task counts:"]
    for lst in VALID_LISTS:
        lines.append(f"  #{lst}: {counts[lst]}")
    lines.append(f"  ★ today: {counts['today']}")
    return "\n".join(lines)


@mcp.tool()
def get_completed_this_week(user_id: int) -> str:
    """Get tasks completed in the last 7 days."""
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND completed_at >= ? ORDER BY completed_at DESC",
            (user_id, week_ago),
        ).fetchall()
    return _format_task_list(rows, "Completed this week:")


init_db()

if __name__ == "__main__":
    mcp.run(transport="stdio")
