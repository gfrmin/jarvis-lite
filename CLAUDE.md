# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jarvis Lite is a multi-user GTD (Getting Things Done) task management Telegram bot. It uses Claude Haiku for natural language parsing, PostgreSQL for storage, and APScheduler for daily digests. Open to all users with per-user rate limiting to protect API costs.

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
- `DATABASE_URL` - PostgreSQL connection string

Optional environment variables:
- `RATE_LIMIT_HOURLY` - Max API calls per user per hour (default: 30)
- `RATE_LIMIT_DAILY` - Max API calls per user per day (default: 200)

## Architecture

Single-file bot (`bot.py`) with these sections:
- **Database Functions**: psycopg2 direct queries, no ORM
- **Rate Limiting Functions**: Per-user hourly/daily API usage tracking
- **Subscription Functions**: Email capture for updates
- **Claude Haiku Parsing**: NLP intent detection returning structured JSON actions
- **Message Formatting**: Task display helpers
- **Telegram Handlers**: Command and message routing (/start, /help, /subscribe)
- **Daily Digest**: 7am Israel time scheduled summary for all active users

Database tables:
- `tasks` - User tasks with GTD metadata
- `api_usage` - Rate limiting tracker (auto-cleaned daily)
- `subscriptions` - Email subscriptions for updates

## GTD Model

Tasks have:
- `list`: inbox | next | scheduled | someday
- `due_date`: optional date for scheduled tasks
- `is_today`: boolean for daily focus (3-5 tasks)
- `@tags`: context tags embedded in task text (e.g., @work, @errands)

## Deployment

Render Blueprint (`render.yaml`) deploys as a worker service with managed PostgreSQL. The database schema auto-creates on first run via `init_db()`.
