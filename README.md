# Jarvis Lite - GTD Telegram Bot

Personal task management bot using GTD principles.

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
     - `ALLOWED_USER_ID` - your Telegram user ID

4. **Start chatting with your bot!**

## Usage

Just message your bot naturally:
- "Buy milk tomorrow"
- "Call dentist next week @errands"
- "Show my tasks"
- "What's due today?"
- `/today` - see today's focus
- `/review` - weekly review
