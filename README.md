# Memory Logger

A personal finance and debt-tracking application powered by natural language processing. Track who owes you money (and vice versa), record payments, split expenses, and manage recurring obligations — all through conversational messages via a Telegram bot or a React dashboard.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Core Functionalities](#core-functionalities)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Setup Instructions](#setup-instructions)
6. [Using the Telegram Bot](#using-the-telegram-bot)
7. [API Reference](#api-reference)
8. [Data Models](#data-models)
9. [How the Telegram Bot + LLM Pipeline Works](#how-the-telegram-bot--llm-pipeline-works)
10. [Frontend Features](#frontend-features)

---

## Project Overview

Memory Logger is a two-part application:

- **Backend** — A FastAPI REST API with a Telegram bot. Users send natural language messages (e.g. *"Gave Sunita 5k, deduct 1k monthly"*) and an LLM (Gemini Flash via OpenRouter) parses the intent, confirms the action, and persists it to a TinyDB JSON database.
- **Frontend** — A React single-page app that displays a summary dashboard of all obligations, lets users filter/sort/search, and provides CRUD operations through a clean card-based UI.

The two communicate over a REST API. The Telegram bot and the web frontend are independent entry points into the same data store.

---

## Core Functionalities

| Feature | Description |
|---|---|
| **NLP intent parsing** | Gemini Flash classifies every message into one of 7 actions (`add`, `settle`, `query`, `edit`, `delete`, `chitchat`, `off_topic`) and extracts structured fields. |
| **Obligation tracking** | Supports both **recurring** (monthly deductions) and **one-time** debts, in both directions (`owes_me` / `i_owe`). |
| **Multi-person splits** | *"Dinner 3200 with Rahul and Priya, I paid"* → auto-divides by headcount (including the user), creates one obligation per person, grouped by a shared `trxn_id`. |
| **Transaction recording** | Partial payments are appended to an obligation's transaction list; `remaining_amount` is decremented automatically. |
| **Settlement** | Mark an obligation fully settled — remaining amount drops to zero and a closing transaction is recorded. |
| **Telegram bot** | `/start`, `/help`, `/pending`, `/settled` commands plus free-text and voice-note input. |
| **Conversation history** | Last 10 messages are passed to the LLM so it can resolve multi-turn references (*"yes, 500"* after being asked *"How much did Rahul pay?"*). |
| **Disambiguation** | When a person has multiple active obligations, the bot shows an inline keyboard listing each one so the user can pick the right record. |
| **Confirmation flow** | Mutating actions show an inline Yes/No keyboard before executing. |

---

## Tech Stack

### Backend

| Dependency | Purpose |
|---|---|
| Python 3.10+ | Runtime |
| FastAPI | REST framework |
| Uvicorn | ASGI server |
| TinyDB | Lightweight JSON document database |
| OpenAI SDK (via OpenRouter) | LLM API client |
| Pydantic / Pydantic Settings | Data validation and config management |
| python-telegram-bot | Telegram Bot API wrapper |
| Loguru | Structured logging |

### Frontend

| Dependency | Purpose |
|---|---|
| React 19 | UI library |
| Vite 7 | Build tool and dev server |
| Tailwind CSS 4 | Utility-first styling |

---

## Project Structure

### Backend (`memory-logger/`)

```
memory-logger/
├── main.py                    # FastAPI app, CORS, Telegram bot lifecycle
├── pyproject.toml             # Dependencies and project metadata
├── memory_ledger.json         # TinyDB data file (auto-created)
├── app/
│   ├── config.py              # Pydantic Settings — env vars
│   ├── deps.py                # Singleton repo + parser instances
│   ├── api/
│   │   └── routes.py          # All REST endpoint handlers
│   ├── bot/
│   │   └── handler.py         # Telegram commands, message handler, callbacks
│   ├── db/
│   │   └── repository.py      # TinyDB repository (CRUD + transactions)
│   ├── llm/
│   │   ├── parser.py          # IntentParser — builds prompt, calls LLM
│   │   └── prompts.py         # System prompt (~260 lines of rules & examples)
│   └── models/
│       └── schemas.py         # Pydantic models (Obligation, Transaction, etc.)
└── tests/
    └── test_scenarios.py      # LLM scenario tests
```

### Frontend (`memory-logger-frontend/`)

```
memory-logger-frontend/
├── index.html                 # HTML shell
├── package.json               # Dependencies and scripts
├── vite.config.js             # Vite config + API proxy to :8000
├── src/
│   ├── main.jsx               # React entry point
│   ├── App.jsx                # Root component — tabs, stats, search, sort
│   ├── api.js                 # Fetch wrappers for all REST endpoints
│   ├── index.css              # Tailwind import
│   └── components/
│       ├── AddObligationForm.jsx      # Modal form — multi-person, split logic
│       ├── ObligationList.jsx         # Grouping by trxn_id, sort, empty states
│       ├── ObligationCard.jsx         # Single obligation card with inline edit
│       ├── GroupedObligationCard.jsx   # Expandable card for multi-person splits
│       ├── TransactionForm.jsx        # Inline payment recording form
│       └── ConfirmDialog.jsx          # Generic Yes/No confirmation modal
└── dist/                      # Production build output
```

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An OpenRouter API key (from [openrouter.ai](https://openrouter.ai))

### Backend

```bash
cd memory-logger

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Create .env file
cat <<EOF > .env
OPENROUTER_API_KEY=your_openrouter_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DB_PATH=memory_ledger.json
LLM_MODEL=google/gemini-2.0-flash-exp
EOF

# Run the server (starts FastAPI on :8000 + Telegram bot polling)
python main.py
```

### Frontend

```bash
cd memory-logger-frontend

# Install dependencies
npm install

# Start dev server (proxies API calls to localhost:8000)
npm run dev
```

The frontend dev server runs on `http://localhost:5173` and proxies `/obligations` and `/parse` requests to the backend at `http://localhost:8000`.

---

## Using the Telegram Bot

### Commands

| Command | Description |
|---|---|
| `/start` | Welcome message with usage examples |
| `/help` | Same as `/start` |
| `/create` | Start a guided session to add a new obligation |
| `/pending` | Show all active obligations with subtotals |
| `/settled` | Show all settled obligations |

### Adding obligations

Use `/create` to start a session, then describe the transaction in plain language. The bot parses your message, shows a structured field-by-field summary for review, and saves on confirmation.

```
You:     /create
Bot:     Let's create a new obligation. Describe the transaction...

You:     Gave Sunita 5k advance, deduct 1k monthly
Bot:     Sunita's advance: Total ₹5,000, monthly deduction ₹1,000 (~5 months).
         Should I add this?

         Person: Sunita
         Amount: ₹5,000
         Direction: They owe you
         Type: Recurring
         Monthly deduction: ₹1,000
         Note: Advance

         [Yes ✓] [No ✗]
```

If something looks wrong, type a correction instead of tapping Yes — the bot re-parses with the updated info:

```
You:     Make it 8k
Bot:     (updated summary with Amount: ₹8,000)
         [Yes ✓] [No ✗]
```

### Sample queries

**One-time debt — someone owes you:**
```
/create → "Rahul owes me 2500 for concert tickets"
```

**One-time debt — you owe someone:**
```
/create → "I owe Priya 1800 for groceries"
```

**Splitting a group expense:**
```
/create → "Dinner with Rahul and Priya, total 3200, I paid"
```
The bot divides by headcount (3 people) and creates one obligation per person.

**Recurring obligation:**
```
/create → "Gave Sunita 5000 advance, deduct 1000 per month"
```

**Recording a payment:**
```
"Rahul paid 500"
```
Deducts ₹500 from Rahul's remaining balance. No `/create` needed — settlements work from normal chat.

**Settling in full:**
```
"Sunita settled up"
```
Marks the obligation fully settled (remaining drops to zero).

**Editing an existing obligation:**
```
"Change Rahul's amount to 3000"
```

**Deleting an obligation:**
```
"Delete Priya's obligation"
```

**Checking balances:**
```
"What does Rahul owe?"
"What's pending?"
```

### Tips

- You only need `/create` for **adding** new obligations. Settlements, edits, deletes, and queries all work from normal chat.
- When a person has multiple active obligations, the bot shows a picker so you can choose the right one.
- The bot remembers the last 10 messages, so you can answer follow-up questions naturally (e.g., "yes, 500" after the bot asks "How much did Rahul pay?").

---

## API Reference

All endpoints are served at `http://localhost:8000`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/parse` | Parse a natural-language message into a structured `LLMResponse` |
| `POST` | `/obligations` | Create a new obligation |
| `GET` | `/obligations` | List obligations (optional `?status=active\|settled`) |
| `GET` | `/obligations/{id}` | Get a single obligation by ID |
| `PATCH` | `/obligations/{id}` | Update obligation fields (partial) |
| `DELETE` | `/obligations/{id}` | Delete an obligation |
| `POST` | `/obligations/{id}/transactions` | Record a payment against an obligation |
| `POST` | `/obligations/{id}/settle` | Settle an obligation (remaining → 0) |

---

## Data Models

### Obligation

```
id                 int | None          Auto-assigned DB doc ID
trxn_id            str | None          UUID grouping multi-person splits
person_name        str                 Name of the other party
type               "recurring" | "one_time"
direction          "owes_me" | "i_owe"
total_amount       float               Original/total amount
expected_per_cycle float | None        Monthly amount (recurring only)
remaining_amount   float               How much is still owed
status             "active" | "settled"
created_at         datetime            Auto-set on creation
note               str | None          Free-text description
transactions       list[Transaction]   Payment history
```

### Transaction

```
amount             float               Payment amount
paid_at            datetime            When the payment occurred
note               str | None          Optional note
```

### ParsedIntent

```
action             "add" | "settle" | "query" | "edit" | "delete" | "chitchat" | "off_topic"
persons            list[str]           People involved
amount             float | None        Amount in INR
direction          "owes_me" | "i_owe"
obligation_type    "recurring" | "one_time" | None
expected_per_cycle float | None
note               str | None
is_ambiguous       bool                Whether clarification is needed
clarifying_question str | None         Question to ask if ambiguous
```

### LLMResponse

```
parsed               ParsedIntent | None   Structured intent (None on parse failure)
confirmation_message str                   Human-readable summary
requires_confirmation bool                 Whether to show Yes/No buttons
```

---

## How the Telegram Bot + LLM Pipeline Works

### Step 1: User Sends a Message

A text message (or voice note) arrives in `handler.py:handle_message`. The handler:

1. Clears any stale inline-keyboard state from a previous turn (`pending_message_id`).
2. Sends a typing indicator so the user sees the bot is working.

### Step 2: LLM Intent Parsing

`IntentParser.parse()` in `parser.py` constructs a message array and sends it to OpenRouter (Gemini Flash) at **temperature 0.1**:

| # | Role | Content |
|---|---|---|
| 1 | `system` | The full system prompt from `prompts.py` (~260 lines of rules covering action types, amount parsing, split math, direction rules, recurring vs one-time, ambiguity handling, and worked examples). |
| 2 | `user` | **Active obligations context** — a formatted dump of every active obligation so the LLM knows the current state of the ledger. |
| 3 | `user`/`assistant` (alternating) | **Last 10 conversation messages** — enables multi-turn resolution (e.g. answering a clarifying question). |
| 4 | `user` | The current user message. |

The LLM responds with JSON, which is validated into an `LLMResponse` containing a `ParsedIntent`, a `confirmation_message`, and a `requires_confirmation` flag.

### Step 3: Intent Routing

Based on `parsed.action`, the handler branches:

- **`chitchat` / `off_topic`** — Reply with the LLM's friendly message. No database action. Conversation history is cleared.
- **`query`** — Look up obligations via `repo.get_by_person()` or `repo.get_all()`, format a summary, and reply directly. No confirmation needed.
- **`is_ambiguous = true`** — Store the exchange in conversation history, relay the LLM's clarifying question, and wait for the user's follow-up message.
- **`add` / `settle` / `edit` / `delete`** — Proceed to the confirmation step.

### Step 4: User Confirmation

For mutating actions, the bot sends the LLM's `confirmation_message` together with inline **Yes / No** buttons. The pending `ParsedIntent` is stored in `context.user_data["pending_action"]`. When the user taps a button, `handle_confirmation` fires.

### Step 5: Action Execution

- **Yes** — Dispatches to the appropriate executor:
  - `_execute_add` — Creates one or more obligations. For multi-person splits, generates a shared `trxn_id` and creates one obligation per person with the per-person amount.
  - `_execute_settle` — Records a partial payment (with amount) or marks the obligation fully settled (without amount).
  - `_execute_edit` — Calls `repo.update()` with only the changed fields.
  - `_execute_delete` — Calls `repo.delete()` to remove the record.
- **No** — Clears `pending_action`, appends "Cancelled" to the message.

### Step 6: Disambiguation

When a settle, edit, or delete targets a person who has **multiple active obligations**, the bot presents an inline keyboard listing each one (showing amount, type, and note). The user picks one, and `_handle_choice()` executes the action on that specific record.

Example:

```
Rahul has 2 active obligations. Which one?

[₹1,067 (one_time) — Dinner]
[₹5,000 (recurring) — Phone advance]
[Cancel]
```

### Multi-Turn Conversation

Up to 10 messages are stored in `context.user_data["history"]` and passed to the LLM on every turn. This lets the model resolve references like *"yes, 500"* after it asked *"How much did Rahul pay?"*. History is cleared once an action is confirmed or cancelled.

### Pipeline Diagram

```
User (Telegram)
    │
    ▼
handle_message()
    │
    ├─ Clears stale keyboard state
    ├─ Sends typing indicator
    │
    ▼
IntentParser.parse(message, obligations_context, history)
    │
    ▼
LLM returns LLMResponse { parsed, confirmation_message, requires_confirmation }
    │
    ├─ AMBIGUOUS ──────► Store in history, send clarifying question, wait
    ├─ CHITCHAT/OFF_TOPIC ► Reply, clear history
    ├─ QUERY ──────────► Fetch from DB, format, reply
    └─ ADD/SETTLE/EDIT/DELETE
           │
           ▼
       Show Yes / No inline keyboard
       Store pending_action
           │
           ▼
       handle_confirmation()
           │
           ├─ No  ► Clear state, reply "Cancelled"
           └─ Yes
               │
               ├─ Multiple matches? ► Show disambiguation keyboard
               │       │
               │       ▼
               │   _handle_choice() ► Execute on selected obligation
               │
               └─ Single match ► Execute directly
                       │
                       ▼
                   _execute_add / _execute_settle / _execute_edit / _execute_delete
                       │
                       ▼
                   repo.add / repo.settle / repo.update / repo.delete
                       │
                       ▼
                   TinyDB (memory_ledger.json)
```

---

## Frontend Features

### Summary Dashboard

The top of the page shows three stat cards:

- **Owed to you** — Total remaining across all `owes_me` obligations
- **You owe** — Total remaining across all `i_owe` obligations
- **Net balance** — Difference between the two

### Tabs

- **Active** — Obligations with `status = "active"`. Supports direction filtering (All / They owe me / I owe).
- **Settled** — Obligations with `status = "settled"`. Read-only view.

### Search, Filter, and Sort

- **Search** — Filter by person name (case-insensitive substring match).
- **Direction filter** — All, They owe me, I owe (active tab only).
- **Sort** — Newest first, Highest amount, Alphabetical.

### Obligation Cards

Single obligations render as **ObligationCard** — showing person name, amount, type badge, direction indicator (green left border for "owes me", orange for "I owe"), and an overflow menu with Settle, Edit, and Delete actions. Recurring obligations show a "Record Payment" button. Each card can expand to show full transaction history.

### Grouped Cards for Multi-Person Splits

Obligations sharing a `trxn_id` are rendered as a **GroupedObligationCard** — an expandable card showing the group note, total amount, person count, and avatar circles with initials. Expanding reveals per-person rows with individual amounts, payment history, and action menus.

### Add Obligation Form

A modal form supporting:

- Multi-person chip input (press Enter or comma to add names)
- Total amount (auto-split equally among all people)
- Direction toggle and type toggle
- Conditional monthly deduction field for recurring obligations
- Optional note

### Auto-Refresh

The dashboard polls the backend every 5 seconds to stay in sync with changes made via the Telegram bot.
