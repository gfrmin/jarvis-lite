#!/usr/bin/env python3
"""Jarvis Lite GTD MCP Server — thin wrappers around db.py for Claude Code."""

from mcp.server.fastmcp import FastMCP

import db

mcp = FastMCP("jarvis-gtd")


@mcp.tool()
def add_task(
    user_id: int,
    text: str,
    list_name: str = "inbox",
    due_date: str | None = None,
    is_today: bool = False,
) -> str:
    """Add a new task to the GTD system."""
    return db.add_task(user_id, text, list_name, due_date, is_today)


@mcp.tool()
def complete_task(
    user_id: int,
    task_id: int | None = None,
    text_match: str | None = None,
) -> str:
    """Complete a task by ID or partial text match."""
    return db.complete_task(user_id, task_id, text_match)


@mcp.tool()
def delete_task(user_id: int, task_id: int) -> str:
    """Delete a task by ID."""
    return db.delete_task(user_id, task_id)


@mcp.tool()
def move_task(
    user_id: int,
    task_id: int,
    new_list: str,
    due_date: str | None = None,
) -> str:
    """Move a task to a different list."""
    return db.move_task(user_id, task_id, new_list, due_date)


@mcp.tool()
def mark_today(user_id: int, task_id: int, is_today: bool = True) -> str:
    """Mark or unmark a task for today's focus."""
    return db.mark_today(user_id, task_id, is_today)


@mcp.tool()
def clear_today(user_id: int) -> str:
    """Clear all today flags for a user."""
    return db.clear_today(user_id)


@mcp.tool()
def get_tasks(user_id: int, list_name: str | None = None) -> str:
    """Get tasks, optionally filtered by list."""
    return db.get_tasks(user_id, list_name)


@mcp.tool()
def get_today_tasks(user_id: int) -> str:
    """Get tasks marked for today's focus."""
    return db.get_today_tasks(user_id)


@mcp.tool()
def get_tasks_by_tag(user_id: int, tag: str) -> str:
    """Get tasks containing a specific @tag."""
    return db.get_tasks_by_tag(user_id, tag)


@mcp.tool()
def get_tasks_due_today(user_id: int) -> str:
    """Get scheduled tasks due today."""
    return db.get_tasks_due_today(user_id)


@mcp.tool()
def get_overdue_tasks(user_id: int) -> str:
    """Get overdue scheduled tasks."""
    return db.get_overdue_tasks(user_id)


@mcp.tool()
def get_task_counts(user_id: int) -> str:
    """Get summary counts of tasks by list."""
    return db.get_task_counts(user_id)


@mcp.tool()
def get_completed_this_week(user_id: int) -> str:
    """Get tasks completed in the last 7 days."""
    return db.get_completed_this_week(user_id)


db.init_db()

if __name__ == "__main__":
    mcp.run(transport="stdio")
