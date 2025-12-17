# Jarvis Lite - GTD Telegram Bot

Multi-user task management bot using GTD principles. Uses Claude Haiku for natural language parsing, PostgreSQL for storage, and includes per-user rate limiting.

## Quick Deploy to Render

1. **Get Telegram Bot Token:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow prompts
   - Copy the token

2. **Get Your Telegram User ID:**
   - Message [@userinfobot](https://t.me/userinfobot)
   - It replies with your ID

3. **Deploy:**
   - Push this repo to GitHub
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **New** → **Blueprint**
   - Connect your repo
   - Render detects `render.yaml` automatically
   - Set the environment variables when prompted:
     - `TELEGRAM_TOKEN` - from BotFather
     - `ANTHROPIC_API_KEY` - from [Anthropic Console](https://console.anthropic.com)
   - Optional environment variables:
     - `RATE_LIMIT_HOURLY` - Max API calls per user per hour (default: 30)
     - `RATE_LIMIT_DAILY` - Max API calls per user per day (default: 200)
     - `ADMIN_USER_ID` - Your Telegram user ID (enables /admin command)

4. **Start chatting with your bot!**

## Usage

Just message your bot naturally:
- "Buy milk tomorrow"
- "Call dentist next week @errands"
- "Show my tasks"
- "What's due today?"

### Commands
- `/start` - Get started and see help
- `/today` - See today's focus tasks
- `/review` - Weekly review
- `/subscribe your@email.com` - Subscribe to updates
- `/admin` - Admin dashboard (requires ADMIN_USER_ID)
