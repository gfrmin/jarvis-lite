#!/usr/bin/env python3
"""
Jarvis Lite - Personal GTD Task Management Telegram Bot

A simple, single-user GTD bot using:
- python-telegram-bot for Telegram integration
- PostgreSQL for storage
- Claude Haiku for natural language parsing
- APScheduler for daily digest
"""

import os
import re
import json
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])

# Constants
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
VALID_LISTS = ["inbox", "next", "scheduled", "someday"]


# =============================================================================
# Database Functions
# =============================================================================

def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Initialize the database table if it doesn't exist."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    text TEXT NOT NULL,
                    list VARCHAR(20) NOT NULL DEFAULT 'inbox',
                    due_date DATE,
                    is_today BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            # Add is_today column if it doesn't exist (for existing databases)
            cur.execute("""
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_today BOOLEAN DEFAULT FALSE
            """)
            conn.commit()
    logger.info("Database initialized")


def add_task(user_id: int, text: str, list_name: str = "inbox", due_date: date = None, is_today: bool = False) -> dict:
    """Add a new task and return it."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (user_id, text, list, due_date, is_today)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, text, list, due_date, is_today
                """,
                (user_id, text, list_name, due_date, is_today)
            )
            task = cur.fetchone()
            conn.commit()
            return task


def complete_task(user_id: int, task_id: int = None, text_match: str = None) -> dict | None:
    """Mark a task as complete by ID or text match. Returns the task if found."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if task_id:
                cur.execute(
                    """
                    UPDATE tasks SET completed_at = NOW(), is_today = FALSE
                    WHERE id = %s AND user_id = %s AND completed_at IS NULL
                    RETURNING id, text, list
                    """,
                    (task_id, user_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE tasks SET completed_at = NOW(), is_today = FALSE
                    WHERE user_id = %s AND completed_at IS NULL
                      AND LOWER(text) LIKE LOWER(%s)
                    RETURNING id, text, list
                    """,
                    (user_id, f"%{text_match}%")
                )
            task = cur.fetchone()
            conn.commit()
            return task


def delete_task(user_id: int, task_id: int) -> dict | None:
    """Delete a task by ID. Returns the task if found."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM tasks
                WHERE id = %s AND user_id = %s
                RETURNING id, text, list
                """,
                (task_id, user_id)
            )
            task = cur.fetchone()
            conn.commit()
            return task


def move_task(user_id: int, task_id: int, new_list: str, due_date: date = None) -> dict | None:
    """Move a task to a different list. Returns the task if found."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if due_date:
                cur.execute(
                    """
                    UPDATE tasks SET list = %s, due_date = %s
                    WHERE id = %s AND user_id = %s AND completed_at IS NULL
                    RETURNING id, text, list, due_date
                    """,
                    (new_list, due_date, task_id, user_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE tasks SET list = %s
                    WHERE id = %s AND user_id = %s AND completed_at IS NULL
                    RETURNING id, text, list, due_date
                    """,
                    (new_list, task_id, user_id)
                )
            task = cur.fetchone()
            conn.commit()
            return task


def mark_today(user_id: int, task_id: int, is_today: bool = True) -> dict | None:
    """Mark or unmark a task for today. Returns the task if found."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks SET is_today = %s
                WHERE id = %s AND user_id = %s AND completed_at IS NULL
                RETURNING id, text, list, is_today
                """,
                (is_today, task_id, user_id)
            )
            task = cur.fetchone()
            conn.commit()
            return task


def clear_today(user_id: int) -> int:
    """Clear all today flags. Returns count of cleared tasks."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks SET is_today = FALSE
                WHERE user_id = %s AND is_today = TRUE AND completed_at IS NULL
                RETURNING id
                """,
                (user_id,)
            )
            count = cur.rowcount
            conn.commit()
            return count


def get_tasks(user_id: int, list_name: str = None, include_completed: bool = False) -> list:
    """Get tasks, optionally filtered by list."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if list_name:
                if include_completed:
                    cur.execute(
                        "SELECT * FROM tasks WHERE user_id = %s AND list = %s ORDER BY id",
                        (user_id, list_name)
                    )
                else:
                    cur.execute(
                        "SELECT * FROM tasks WHERE user_id = %s AND list = %s AND completed_at IS NULL ORDER BY id",
                        (user_id, list_name)
                    )
            else:
                if include_completed:
                    cur.execute(
                        "SELECT * FROM tasks WHERE user_id = %s ORDER BY list, id",
                        (user_id,)
                    )
                else:
                    cur.execute(
                        "SELECT * FROM tasks WHERE user_id = %s AND completed_at IS NULL ORDER BY list, id",
                        (user_id,)
                    )
            return cur.fetchall()


def get_today_tasks(user_id: int) -> list:
    """Get tasks marked for today."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = %s AND is_today = TRUE AND completed_at IS NULL
                ORDER BY list, id
                """,
                (user_id,)
            )
            return cur.fetchall()


def get_tasks_by_tag(user_id: int, tag: str) -> list:
    """Get tasks containing a specific @tag."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = %s AND completed_at IS NULL AND text ILIKE %s
                ORDER BY list, id
                """,
                (user_id, f"%@{tag}%")
            )
            return cur.fetchall()


def get_tasks_due_today(user_id: int) -> list:
    """Get scheduled tasks due today."""
    today = date.today()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = %s AND list = 'scheduled' AND due_date = %s AND completed_at IS NULL
                ORDER BY id
                """,
                (user_id, today)
            )
            return cur.fetchall()


def get_overdue_tasks(user_id: int) -> list:
    """Get overdue scheduled tasks."""
    today = date.today()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = %s AND list = 'scheduled' AND due_date < %s AND completed_at IS NULL
                ORDER BY due_date, id
                """,
                (user_id, today)
            )
            return cur.fetchall()


def get_task_counts(user_id: int) -> dict:
    """Get counts of tasks by list."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT list, COUNT(*) as count
                FROM tasks
                WHERE user_id = %s AND completed_at IS NULL
                GROUP BY list
                """,
                (user_id,)
            )
            counts = {row["list"]: row["count"] for row in cur.fetchall()}
            # Ensure all lists are represented
            for lst in VALID_LISTS:
                counts.setdefault(lst, 0)
            # Get today count
            cur.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE user_id = %s AND is_today = TRUE AND completed_at IS NULL",
                (user_id,)
            )
            counts["today"] = cur.fetchone()["count"]
            return counts


def get_completed_this_week(user_id: int) -> list:
    """Get tasks completed in the last 7 days."""
    week_ago = datetime.now() - timedelta(days=7)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = %s AND completed_at >= %s
                ORDER BY completed_at DESC
                """,
                (user_id, week_ago)
            )
            return cur.fetchall()


# =============================================================================
# Claude Haiku Parsing
# =============================================================================

def parse_with_haiku(user_message: str) -> dict:
    """
    Use Claude Haiku to parse natural language into a structured action.

    Returns a dict with:
    - action: add | complete | delete | move | show | review | today | clear_today | process | help | unknown
    - text: task text (for add)
    - list: target list (inbox, next, scheduled, someday)
    - task_id: task ID (for complete, delete, move, today)
    - due_date: ISO date string (for scheduled tasks)
    - tag: context tag for filtering (e.g., "work", "home")
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today_date = date.today().isoformat()

    system_prompt = f"""You are a GTD task parser. Parse the user's message into a JSON action.

Today's date is {today_date}.

Actions:
- add: Add a new task. Extract the task text (keep @tags in the text) and determine the list.
- complete: Mark a task as done. Look for "done", "finished", "complete", etc.
- delete: Remove a task. Look for "delete", "remove", etc.
- move: Move a task to a different list. Look for "move X to Y", "X to next", "X scheduled tomorrow".
- show: Display tasks. Look for "show", "list", "what's next", etc. Can filter by @tag.
- review: Weekly review. Look for "review", "weekly review", etc.
- today: Mark a task for today's focus. Look for "today X", "focus X", "star X".
- clear_today: Clear all today markers. Look for "clear today", "reset today".
- process: Start inbox processing. Look for "process", "process inbox", "triage".
- help: User needs help.

Lists:
- inbox: Default for new tasks without a specific list
- next: Tasks to do within 7 days. Look for "#next", "next:", or context implying urgency
- scheduled: Tasks with a due date. Parse dates like "tomorrow", "next monday", "Dec 15", etc.
- someday: Future/maybe tasks. Look for "someday", "maybe", "later", etc.

Context tags (@work, @home, @errands, etc.) should be kept in the task text as-is.

Respond with ONLY valid JSON, no other text:
{{
  "action": "add|complete|delete|move|show|review|today|clear_today|process|help|unknown",
  "text": "task text if adding (include @tags)",
  "list": "inbox|next|scheduled|someday|today|null",
  "task_id": null or number,
  "due_date": null or "YYYY-MM-DD",
  "text_match": "partial text to match for completion",
  "tag": "tag name without @ for filtering"
}}

Examples:
- "Buy milk" -> {{"action": "add", "text": "Buy milk", "list": "inbox"}}
- "Buy milk @errands" -> {{"action": "add", "text": "Buy milk @errands", "list": "inbox"}}
- "Call bank tomorrow" -> {{"action": "add", "text": "Call bank", "list": "scheduled", "due_date": "{today_date}"}}
- "#next: finish report @work" -> {{"action": "add", "text": "finish report @work", "list": "next"}}
- "someday: learn guitar" -> {{"action": "add", "text": "learn guitar", "list": "someday"}}
- "Done: buy milk" -> {{"action": "complete", "text_match": "buy milk"}}
- "Done 3" -> {{"action": "complete", "task_id": 3}}
- "Delete 5" -> {{"action": "delete", "task_id": 5}}
- "Move 3 to next" -> {{"action": "move", "task_id": 3, "list": "next"}}
- "3 to next" -> {{"action": "move", "task_id": 3, "list": "next"}}
- "3 to scheduled tomorrow" -> {{"action": "move", "task_id": 3, "list": "scheduled", "due_date": "..."}}
- "3 someday" -> {{"action": "move", "task_id": 3, "list": "someday"}}
- "What's next?" -> {{"action": "show", "list": "next"}}
- "Show inbox" -> {{"action": "show", "list": "inbox"}}
- "Show today" -> {{"action": "show", "list": "today"}}
- "Show @work" -> {{"action": "show", "tag": "work"}}
- "Show all" -> {{"action": "show", "list": null}}
- "Weekly review" -> {{"action": "review"}}
- "Today 5" -> {{"action": "today", "task_id": 5}}
- "Focus 3" -> {{"action": "today", "task_id": 3}}
- "Star 7" -> {{"action": "today", "task_id": 7}}
- "Clear today" -> {{"action": "clear_today"}}
- "Process inbox" -> {{"action": "process"}}
- "Process" -> {{"action": "process"}}"""

    response = client.messages.create(
        model="claude-haiku-4-20250414",
        max_tokens=256,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    response_text = response.content[0].text.strip()

    # Try to parse JSON from response
    try:
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        return json.loads(response_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Haiku response: {response_text}")
        return {"action": "unknown"}


# =============================================================================
# Message Formatting
# =============================================================================

def format_task(task: dict, show_list: bool = False) -> str:
    """Format a single task for display."""
    star = "★ " if task.get("is_today") else ""
    parts = [f"{star}[{task['id']}] {task['text']}"]
    if show_list:
        parts.append(f"#{task['list']}")
    if task.get("due_date"):
        due = task["due_date"]
        if isinstance(due, date):
            due = due.isoformat()
        parts.append(f"(due: {due})")
    return " ".join(parts)


def format_task_list(tasks: list, title: str, show_list: bool = False) -> str:
    """Format a list of tasks for display."""
    if not tasks:
        return f"*{title}*\n_No tasks_"

    lines = [f"*{title}*"]
    for task in tasks:
        lines.append(f"  {format_task(task, show_list)}")
    return "\n".join(lines)


def extract_tags(text: str) -> list:
    """Extract @tags from task text."""
    return re.findall(r"@(\w+)", text)


# =============================================================================
# Telegram Handlers
# =============================================================================

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized."""
    return user_id == ALLOWED_USER_ID


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(
        "*Jarvis Lite* - GTD Assistant\n\n"
        "*Add tasks:*\n"
        "  'Buy milk' → inbox\n"
        "  'Buy milk @errands' → with tag\n"
        "  'Call bank tomorrow' → scheduled\n"
        "  '#next: finish report' → next actions\n"
        "  'someday: learn guitar' → someday\n\n"
        "*Manage:*\n"
        "  'Done 3' or 'Done: buy milk'\n"
        "  'Delete 3'\n"
        "  'Move 3 to next' or '3 to next'\n"
        "  '3 scheduled friday'\n\n"
        "*Today's focus (3-5 tasks):*\n"
        "  'Today 3' or 'Focus 3' → mark for today\n"
        "  'Clear today' → reset today list\n\n"
        "*View:*\n"
        "  'Show inbox/next/today/all'\n"
        "  'Show @work' → filter by tag\n"
        "  'Weekly review'\n\n"
        "*Process inbox:*\n"
        "  'Process' → guided inbox triage\n\n"
        "_Lists: inbox, next, scheduled, someday_",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages - the main bot logic."""
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return

    message_text = update.message.text.strip()
    if not message_text:
        return

    # Parse with Haiku
    parsed = parse_with_haiku(message_text)
    action = parsed.get("action", "unknown")

    logger.info(f"Parsed action: {parsed}")

    try:
        if action == "add":
            task = add_task(
                user_id=user_id,
                text=parsed.get("text", message_text),
                list_name=parsed.get("list", "inbox"),
                due_date=parsed.get("due_date")
            )
            list_info = f"#{task['list']}"
            if task.get("due_date"):
                list_info += f" (due: {task['due_date']})"
            await update.message.reply_text(
                f"Added [{task['id']}] {task['text']} to {list_info}"
            )

        elif action == "complete":
            task = complete_task(
                user_id=user_id,
                task_id=parsed.get("task_id"),
                text_match=parsed.get("text_match")
            )
            if task:
                await update.message.reply_text(f"Completed: {task['text']}")
            else:
                await update.message.reply_text("Task not found or already completed")

        elif action == "delete":
            task_id = parsed.get("task_id")
            if not task_id:
                await update.message.reply_text("Please specify a task ID to delete (e.g., 'Delete 3')")
                return
            task = delete_task(user_id, task_id)
            if task:
                await update.message.reply_text(f"Deleted: {task['text']}")
            else:
                await update.message.reply_text("Task not found")

        elif action == "move":
            task_id = parsed.get("task_id")
            new_list = parsed.get("list")
            due_date = parsed.get("due_date")
            if not task_id or not new_list:
                await update.message.reply_text("Please specify task ID and target list (e.g., 'Move 3 to next')")
                return
            if new_list not in VALID_LISTS:
                await update.message.reply_text(f"Invalid list. Use: {', '.join(VALID_LISTS)}")
                return
            task = move_task(user_id, task_id, new_list, due_date)
            if task:
                due_info = f" (due: {task['due_date']})" if task.get("due_date") else ""
                await update.message.reply_text(f"Moved [{task['id']}] {task['text']} to #{new_list}{due_info}")
            else:
                await update.message.reply_text("Task not found")

        elif action == "today":
            task_id = parsed.get("task_id")
            if not task_id:
                await update.message.reply_text("Please specify a task ID (e.g., 'Today 3')")
                return
            task = mark_today(user_id, task_id, True)
            if task:
                await update.message.reply_text(f"★ Marked for today: [{task['id']}] {task['text']}")
            else:
                await update.message.reply_text("Task not found")

        elif action == "clear_today":
            count = clear_today(user_id)
            await update.message.reply_text(f"Cleared {count} task(s) from today's focus")

        elif action == "process":
            # Show inbox items for processing
            inbox_tasks = get_tasks(user_id, "inbox")
            if not inbox_tasks:
                await update.message.reply_text("Inbox is empty! Nothing to process.")
                return

            lines = ["*PROCESS INBOX*\n"]
            for task in inbox_tasks[:10]:  # Show first 10
                lines.append(f"[{task['id']}] {task['text']}")

            if len(inbox_tasks) > 10:
                lines.append(f"\n_...and {len(inbox_tasks) - 10} more_")

            lines.append("\n*For each item, reply:*")
            lines.append("  '3 to next' → move to #next")
            lines.append("  '3 scheduled monday' → schedule")
            lines.append("  '3 someday' → move to someday")
            lines.append("  'Done 3' → complete")
            lines.append("  'Delete 3' → remove")
            lines.append("  'Today 3' → mark for today")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        elif action == "show":
            list_name = parsed.get("list")
            tag = parsed.get("tag")

            if tag:
                # Filter by tag
                tasks = get_tasks_by_tag(user_id, tag)
                title = f"@{tag}"
                response = format_task_list(tasks, title, show_list=True)
            elif list_name == "today":
                # Show today's focus
                tasks = get_today_tasks(user_id)
                title = "TODAY'S FOCUS"
                response = format_task_list(tasks, title, show_list=True)
            elif list_name and list_name in VALID_LISTS:
                tasks = get_tasks(user_id, list_name)
                title = f"#{list_name.upper()}"
                response = format_task_list(tasks, title, show_list=False)
            else:
                # Show all lists
                response_parts = []

                # Today's focus first
                today_tasks = get_today_tasks(user_id)
                if today_tasks:
                    response_parts.append(format_task_list(today_tasks, "★ TODAY'S FOCUS", show_list=True))

                for lst in VALID_LISTS:
                    tasks = get_tasks(user_id, lst)
                    response_parts.append(format_task_list(tasks, f"#{lst.upper()}", show_list=False))
                response = "\n\n".join(response_parts)

            await update.message.reply_text(response, parse_mode="Markdown")

        elif action == "review":
            # Weekly review
            counts = get_task_counts(user_id)
            completed = get_completed_this_week(user_id)
            overdue = get_overdue_tasks(user_id)

            lines = ["*WEEKLY REVIEW*\n"]

            # Task counts
            lines.append("*Task Counts:*")
            lines.append(f"  ★ today: {counts['today']}")
            for lst in VALID_LISTS:
                lines.append(f"  #{lst}: {counts[lst]}")

            lines.append(f"\n*Completed this week:* {len(completed)}")

            # Overdue
            if overdue:
                lines.append(f"\n*Overdue ({len(overdue)}):*")
                for task in overdue[:5]:
                    lines.append(f"  {format_task(task)}")

            # Someday review prompt
            someday_tasks = get_tasks(user_id, "someday")
            if someday_tasks:
                lines.append(f"\n*Someday/Maybe ({len(someday_tasks)}):*")
                for task in someday_tasks[:3]:
                    lines.append(f"  {format_task(task)}")
                if len(someday_tasks) > 3:
                    lines.append(f"  _...and {len(someday_tasks) - 3} more_")
                lines.append("\n_Review: promote, schedule, or delete?_")

            # Suggestions
            suggestions = []
            if counts["inbox"] > 5:
                suggestions.append("Process your inbox")
            if counts["next"] == 0 and counts["inbox"] > 0:
                suggestions.append("Move some inbox items to #next")
            if counts["today"] == 0 and counts["next"] > 0:
                suggestions.append("Pick 3-5 tasks for today's focus")
            if overdue:
                suggestions.append("Reschedule or complete overdue items")

            if suggestions:
                lines.append("\n*Suggestions:*")
                for s in suggestions:
                    lines.append(f"  • {s}")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        elif action == "help":
            await handle_start(update, context)

        else:
            # Unknown action - treat as a task to add to inbox
            task = add_task(user_id=user_id, text=message_text, list_name="inbox")
            await update.message.reply_text(
                f"Added [{task['id']}] {task['text']} to #inbox\n"
                f"_(Tip: say 'help' for commands)_",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text(f"Error: {str(e)}")


# =============================================================================
# Daily Digest
# =============================================================================

async def send_daily_digest(app: Application):
    """Send the daily digest at 7am Israel time."""
    try:
        user_id = ALLOWED_USER_ID

        # Get today's focus tasks
        today_tasks = get_today_tasks(user_id)

        # Get scheduled tasks due today
        due_today = get_tasks_due_today(user_id)

        # Get overdue tasks
        overdue = get_overdue_tasks(user_id)

        # Get top next actions (not already marked for today)
        next_tasks = [t for t in get_tasks(user_id, "next") if not t.get("is_today")][:3]

        # Get inbox count
        inbox_count = len(get_tasks(user_id, "inbox"))

        lines = ["*MORNING DIGEST*\n"]

        # Today's focus (carried over)
        if today_tasks:
            lines.append(f"*★ Today's Focus ({len(today_tasks)}):*")
            for task in today_tasks:
                lines.append(f"  [{task['id']}] {task['text']}")
            lines.append("")

        # Overdue
        if overdue:
            lines.append(f"*⚠️ Overdue ({len(overdue)}):*")
            for task in overdue[:5]:
                lines.append(f"  {format_task(task)}")
            lines.append("")

        # Due today
        if due_today:
            lines.append(f"*📅 Due Today ({len(due_today)}):*")
            for task in due_today:
                lines.append(f"  [{task['id']}] {task['text']}")
            lines.append("")

        # Suggested next actions
        if next_tasks:
            lines.append(f"*Suggested from #next:*")
            for task in next_tasks:
                lines.append(f"  [{task['id']}] {task['text']}")
            lines.append("")

        # Inbox reminder
        if inbox_count > 0:
            lines.append(f"_📥 Inbox: {inbox_count} items waiting_")

        # Morning prompt
        if not today_tasks and (due_today or next_tasks):
            lines.append("\n_Reply 'Today X' to mark tasks for today_")

        if len(lines) > 1:
            await app.bot.send_message(
                chat_id=user_id,
                text="\n".join(lines),
                parse_mode="Markdown"
            )
            logger.info("Daily digest sent")
        else:
            await app.bot.send_message(
                chat_id=user_id,
                text="*MORNING DIGEST*\n\nNo tasks lined up. Enjoy your day!",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error sending daily digest: {e}", exc_info=True)


# =============================================================================
# Main
# =============================================================================

async def post_init(app: Application):
    """Called after the Application is initialized and event loop is running."""
    scheduler = AsyncIOScheduler(timezone=ISRAEL_TZ)
    scheduler.add_job(
        send_daily_digest,
        trigger="cron",
        hour=7,
        minute=0,
        args=[app]
    )
    scheduler.start()
    logger.info("Scheduler started - daily digest at 7:00 AM Israel time")


def main():
    """Start the bot."""
    # Initialize database
    init_db()

    # Create application with post_init hook for scheduler
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Add handlers
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start polling
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
