# Memory Ledger — Setup Guide

## 1. OpenRouter API Key

1. Sign up at [openrouter.ai](https://openrouter.ai/)
2. Go to **Keys** and generate a new API key
3. The default model (`google/gemini-2.5-flash-lite`) is available on the free tier

## 2. Telegram Bot Token (optional for now)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the bot token provided

## 3. Environment Setup

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```
OPENROUTER_API_KEY=sk-or-...
TELEGRAM_BOT_TOKEN=your-bot-token
```

## 4. Install & Run

```bash
uv sync
uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## 5. Test It

```bash
# Parse a natural language message
curl -X POST http://localhost:8000/parse \
  -H "Content-Type: application/json" \
  -d '{"message": "Gave Sunita 5k advance, deduct 1k monthly"}'

# Create an obligation
curl -X POST http://localhost:8000/obligations \
  -H "Content-Type: application/json" \
  -d '{"person_name": "Sunita", "type": "recurring", "total_amount": 5000, "expected_per_cycle": 1000, "note": "Advance"}'

# List active obligations
curl http://localhost:8000/obligations?status=active
```
