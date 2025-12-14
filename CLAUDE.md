# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jarvis Lite is a single-user GTD (Getting Things Done) task management Telegram bot. It uses Claude Haiku for natural language parsing, PostgreSQL for storage, and APScheduler for daily digests.

## Commands

```bash
# Run the bot locally
python bot.py

# Install dependencies
pip install -r requirements.txt
# or with uv
uv sync
```

## Environment Variables

Required environment variables (set in `.env` for local dev, or in Render dashboard):
- `TELEGRAM_TOKEN` - Telegram bot token from BotFather
- `ANTHROPIC_API_KEY` - Anthropic API key
- `ALLOWED_USER_IDS` - Comma-separated list of authorized Telegram user IDs
- `DATABASE_URL` - PostgreSQL connection string

## Architecture

Single-file bot (`bot.py`) with these sections:
- **Database Functions** (lines 44-330): psycopg2 direct queries, no ORM
- **Claude Haiku Parsing** (lines 333-432): NLP intent detection returning structured JSON actions
- **Message Formatting** (lines 436-466): Task display helpers
- **Telegram Handlers** (lines 469-719): Command and message routing
- **Daily Digest** (lines 722-796): 7am Israel time scheduled summary

## GTD Model

Tasks have:
- `list`: inbox | next | scheduled | someday
- `due_date`: optional date for scheduled tasks
- `is_today`: boolean for daily focus (3-5 tasks)
- `@tags`: context tags embedded in task text (e.g., @work, @errands)

## Deployment

Render Blueprint (`render.yaml`) deploys as a worker service with managed PostgreSQL. The database schema auto-creates on first run via `init_db()`.
