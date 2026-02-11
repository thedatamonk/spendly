# Memory Ledger - Project Plan

## Core Requirements

### Problem Statement
Build a personal financial memory logger to track:
1. Recurring obligations - e.g., maid advance (₹5k total, ₹1k/month deduction)
2. One-time expenses - e.g., dinner splits with friends

### Key Constraints
- Voice-first input via Telegram (zero friction)
- Manual tracking only (no auto-deductions)
- Single user (personal use)
- Small scale (100-500 entries maximum)
- Free infrastructure where possible

### User Interaction Model
- Primary interface: Telegram bot (voice notes and text messages)
- Secondary interface: Web dashboard (laptop access, todo-list style)
- Bot behavior: Always asks for confirmation, never assumes

---

## Core Components

### 1. Telegram Bot (Input Layer)
**Purpose**: Receive voice and text input from user, trigger backend actions

**Capabilities**:
- Accept voice notes (use Telegram's built-in transcription)
- Accept text messages
- Send confirmation prompts to user
- Send clarifying questions when input is ambiguous
- Provide conversational responses

### 2. Backend Service (Processing Layer)
**Purpose**: Handle business logic, LLM integration, data operations

**Responsibilities**:
- Receive messages from Telegram bot
- Send messages to LLM for intent parsing and entity extraction
- Execute CRUD operations on database
- Manage conversation context for multi-turn confirmations
- Expose REST API endpoints for web dashboard

**Key Actions to Support**:
1. Add One-Time Expense - Auto-split amount among multiple people
2. Add Recurring Obligation - Track advances with expected monthly amounts (reference only)
3. Mark as Settled - Support full or partial settlement
4. Query Status - Show pending obligations
5. Edit/Delete - Modify or remove existing entries

### 3. LLM Integration (Intelligence Layer)
**Purpose**: Parse natural language into structured actions

**Tasks**:
- Extract entities from user input: person names, amounts, type (recurring/one-time), frequency
- Classify user intent: add, settle, query, edit, delete
- Generate clarifying questions when input is ambiguous
- Format responses conversationally
- Handle both English and casual Hindi/English mix

**Provider**: OpenRouter API for access to multiple LLM models

### 4. Database (Storage Layer)
**Purpose**: Persist obligations and transaction history

**Data Schema**:

Obligations table:
- id (unique identifier)
- person_name (string)
- type (recurring or one_time)
- total_amount (number)
- expected_per_cycle (number, optional - for recurring obligations, reference only)
- remaining_amount (number)
- status (active or settled)
- created_at (timestamp)
- note (string, optional)
- transactions (array of transaction objects embedded within obligation)

Transaction object (embedded):
- amount (number)
- paid_at (timestamp)
- note (string, optional)

### 5. Web Dashboard (Display Layer)
**Purpose**: Simple todo-list style UI for viewing and managing obligations

**Features**:
- Active tab: List of pending obligations with checkboxes
- Settled tab: Archive of completed obligations
- Actions: Mark as settled, view details, search by person name
- No analytics or complex visualizations
- Clean, minimalist design

**UI Style**: Minimalist todo-list interface

---

## Tech Stack

### Bot Layer
- python-telegram-bot: Telegram Bot API wrapper
- Telegram built-in transcription: For voice-to-text conversion

### Backend
- FastAPI: REST API framework
- Uvicorn: ASGI server
- OpenAI SDK: For OpenRouter API integration
- Pydantic: Data validation and settings management
- python-dotenv: Environment variable management
- Loguru: Structured logging

### Database
- TinyDB: JSON-based lightweight database
- Single file storage: memory_ledger.json

### LLM Provider
- OpenRouter: Multi-model API gateway
- Primary model: google/gemini-2.0-flash-exp (free tier)
- Fallback options: anthropic/claude-haiku-4 or other models as needed

### Frontend
- React: UI framework
- TailwindCSS: Utility-first CSS framework
- Vite: Build tool and dev server
- Axios: HTTP client for API requests

### Hosting
- Railway: Backend hosting (always-on with free tier credit)
- Railway or similar: Static site hosting for React frontend

---

## Key Design Decisions

### Bot Behavior
1. No auto-deduction: Bot never automatically deducts recurring payments. User must explicitly report when payment is made and amount paid.

2. Always confirm: Bot always asks for confirmation before executing any action. Never assumes user intent.

3. Auto-split for expenses: When user mentions expense with multiple people, bot automatically divides amount equally among all parties unless user specifies otherwise.

4. Clarifying questions: If input is ambiguous or multiple matches exist in database, bot asks user to clarify before proceeding.

### Data Management
5. Simple data model: No complex relations. Transactions are embedded within obligation documents.

6. Manual updates only: All changes to remaining amounts happen only when user explicitly reports a payment.

7. Flexible amounts: For recurring obligations, expected_per_cycle is reference only. Actual payment amounts can vary each time.

### User Experience
8. Voice-first but text-capable: Primary input method is voice notes, but text messages work equally well.

9. Conversational tone: Bot maintains casual, friendly conversation style matching user's communication pattern.

10. Minimal friction: User should be able to log an expense in under 10 seconds via voice note.

---

## Example Conversation Flows

### Flow 1: Add Recurring Obligation
User sends voice note: "Gave Sunita 5k advance, deduct 1k monthly"

Bot responds: "Understood - Sunita's advance: Total: ₹5,000, Expected monthly: ₹1,000, 5 months to complete. Should I add this?"

User: "Yes"

Bot: "Added! Sunita's recurring obligation is active."

### Flow 2: Add One-Time Expense with Auto-Split
User sends voice note: "Dinner with Rahul and Priya, 3200, I paid"

Bot responds: "Got it! Dinner split: Rahul owes ₹1,067, Priya owes ₹1,067. Should I log this?"

User: "Yes"

Bot: "Done! Added to pending list."

### Flow 3: Settlement with Confirmation
User: "Rahul paid"

Bot checks database: Found 1 pending item for Rahul

Bot responds: "Rahul paid ₹1,067 for dinner split. Mark as settled?"

User: "Yes"

Bot: "Marked as settled!"

### Flow 4: Settlement with Multiple Matches
User: "Rahul paid"

Bot checks database: Found 2 pending items for Rahul

Bot responds: "Which one did Rahul settle? 1. ₹1,067 - Dinner split (Jan 15), 2. ₹500 - Movie tickets (Jan 20). Reply with number."

User: "1"

Bot: "Marked dinner split (₹1,067) as settled!"

### Flow 5: Query Pending Obligations
User: "What's pending?"

Bot responds: "You have 3 pending items: 1. Sunita - ₹3,000 remaining (Advance), 2. Rahul - ₹1,067 (Dinner split), 3. Priya - ₹1,067 (Dinner split)"

### Flow 6: Partial Settlement
User: "Rahul paid 500"

Bot checks database: Rahul owes ₹1,067

Bot responds: "Rahul paid ₹500 out of ₹1,067. Remaining: ₹567. Should I update this?"

User: "Yes"

Bot: "Updated! Rahul now owes ₹567."

### Flow 7: Recurring Payment (Manual Trigger)
User: "Paid Sunita 1k"

Bot checks database: Sunita has active advance of ₹5,000 remaining

Bot responds: "Sunita's advance payment: Paying: ₹1,000, Remaining after: ₹4,000. Should I update?"

User: "Yes"

Bot: "Updated! Sunita's advance: ₹4,000 remaining"

---

## Success Criteria

1. Friction-free input: User can log an expense in under 10 seconds via voice note
2. Accurate parsing: LLM correctly extracts entities and intent 95 percent of the time or better
3. Safe operations: Bot always confirms before making any changes to data
4. Simple dashboard: User can view all pending obligations at a glance on web interface
5. Reliable tracking: No data loss, accurate remaining amount calculations
6. Always available: Bot responds within reasonable time without downtime