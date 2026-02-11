from datetime import datetime

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import get_settings
from app.deps import repo, parser
from app.models.schemas import Obligation, Transaction

settings = get_settings()

# Conversation states
AWAITING_CONFIRMATION = 1
AWAITING_CHOICE = 2

MAX_HISTORY_MESSAGES = 10


def _append_to_history(
    context: ContextTypes.DEFAULT_TYPE, role: str, content: str
) -> None:
    """Append a message to the user's conversation history, trimming to max size."""
    history = context.user_data.setdefault("history", [])
    history.append({"role": role, "content": content})
    # Trim to keep only the most recent messages
    if len(history) > MAX_HISTORY_MESSAGES:
        context.user_data["history"] = history[-MAX_HISTORY_MESSAGES:]


def _format_inr(amount: float) -> str:
    """Format amount in INR style."""
    if amount == int(amount):
        return f"₹{int(amount):,}"
    return f"₹{amount:,.2f}"


def _pending_summary(obligations: list[Obligation]) -> str:
    """Build a summary of pending obligations."""
    if not obligations:
        return "No pending obligations! You're all clear."

    lines = ["*Pending obligations:*\n"]
    for i, ob in enumerate(obligations, 1):
        line = f"{i}. *{ob.person_name}* — {_format_inr(ob.remaining_amount)}"
        if ob.type == "recurring":
            line += " (recurring)"
        if ob.note:
            line += f" — {ob.note}"
        lines.append(line)

    total = sum(ob.remaining_amount for ob in obligations)
    lines.append(f"\n*Total pending: {_format_inr(total)}*")
    return "\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "Hey! I'm your Memory Ledger bot.\n\n"
        "Send me a voice note or text to log expenses, track advances, or check balances.\n\n"
        "Examples:\n"
        '• "Gave Sunita 5k advance, deduct 1k monthly"\n'
        '• "Dinner with Rahul and Priya, 3200, I paid"\n'
        '• "Rahul paid 500"\n'
        '• "What\'s pending?"\n\n'
        "Commands:\n"
        "/pending — Show active obligations\n"
        "/settled — Show settled obligations\n"
        "/help — Show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start_command(update, context)


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pending command."""
    obligations = repo.get_all(status="active")
    await update.message.reply_text(
        _pending_summary(obligations), parse_mode="Markdown"
    )


async def settled_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settled command."""
    obligations = repo.get_all(status="settled")
    if not obligations:
        await update.message.reply_text("No settled obligations yet.")
        return

    lines = ["*Settled obligations:*\n"]
    for i, ob in enumerate(obligations, 1):
        line = f"{i}. *{ob.person_name}* — {_format_inr(ob.total_amount)}"
        if ob.note:
            line += f" — {ob.note}"
        lines.append(line)
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages — the main conversation entry point."""
    user_text = update.message.text.strip()
    logger.info("Telegram message: {}", user_text)

    # Send typing indicator
    await update.message.chat.send_action("typing")

    # Parse through LLM
    active_obligations = repo.get_all(status="active")
    llm_result = parser.parse(
        user_text,
        context=active_obligations,
        history=context.user_data.get("history", []),
    )

    # If ambiguous, store history and relay the clarifying question
    if llm_result.parsed and llm_result.parsed.is_ambiguous:
        _append_to_history(context, "user", user_text)
        _append_to_history(context, "assistant", llm_result.confirmation_message)
        await update.message.reply_text(llm_result.confirmation_message)
        return

    # Conversation resolved — clear history
    context.user_data.pop("history", None)

    # If it's a query, respond directly
    if llm_result.parsed and llm_result.parsed.action == "query":
        if llm_result.parsed.persons:
            # Query for a specific person
            name = llm_result.parsed.persons[0]
            matches = repo.get_by_person(name, status="active")
            if matches:
                await update.message.reply_text(
                    _pending_summary(matches), parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"No pending obligations for {name}."
                )
        else:
            obligations = repo.get_all(status="active")
            await update.message.reply_text(
                _pending_summary(obligations), parse_mode="Markdown"
            )
        return

    # For actions that need confirmation, store state and ask
    if llm_result.requires_confirmation and llm_result.parsed:
        context.user_data["pending_action"] = llm_result.parsed.model_dump()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes ✓", callback_data="confirm_yes"),
                    InlineKeyboardButton("No ✗", callback_data="confirm_no"),
                ]
            ]
        )
        await update.message.reply_text(
            llm_result.confirmation_message, reply_markup=keyboard
        )
        return

    # No confirmation needed and no parsed action — just relay the message
    await update.message.reply_text(llm_result.confirmation_message)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice notes — download and use Telegram's transcription if available."""
    voice = update.message.voice

    # Check if Telegram provided a transcription (premium feature)
    # For non-premium, we'll prompt the user to send text instead
    if update.message.caption:
        # Some clients send caption with voice
        user_text = update.message.caption
    else:
        # Try to get the voice transcription
        # Telegram premium provides automatic transcription
        # For now, ask user to send text if transcription isn't available
        await update.message.reply_text(
            "I received your voice note! Unfortunately I can't transcribe it yet.\n"
            "Could you type out the message instead?"
        )
        return

    # If we got text from the voice note, process it like a regular message
    update.message.text = user_text
    await handle_message(update, context)


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Yes/No button presses for confirmation."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("history", None)
        await query.edit_message_text(query.message.text + "\n\n_Cancelled._", parse_mode="Markdown")
        return

    # confirm_yes
    action_data = context.user_data.pop("pending_action", None)
    context.user_data.pop("history", None)
    if not action_data:
        await query.edit_message_text("Nothing to confirm. Send a new message.")
        return

    action = action_data["action"]
    persons = action_data.get("persons", [])
    amount = action_data.get("amount")
    obligation_type = action_data.get("obligation_type")
    expected_per_cycle = action_data.get("expected_per_cycle")
    note = action_data.get("note")

    try:
        if action == "add":
            await _execute_add(
                query, persons, amount, obligation_type, expected_per_cycle, note
            )
        elif action == "settle":
            await _execute_settle(query, persons, amount, note)
        elif action == "delete":
            await _execute_delete(query, persons)
        elif action == "edit":
            await query.edit_message_text(
                "Edit support coming soon! For now, use the web dashboard."
            )
        else:
            await query.edit_message_text("I'm not sure what to do with that.")
    except Exception as e:
        logger.error("Error executing action: {}", e)
        await query.edit_message_text(f"Something went wrong: {e}")


async def _execute_add(query, persons, amount, obligation_type, expected_per_cycle, note):
    """Execute an add obligation action."""
    if not persons or not amount:
        await query.edit_message_text("Missing person or amount. Please try again.")
        return

    created_names = []
    if obligation_type == "one_time" and len(persons) > 1:
        # Split equally among persons
        per_person = round(amount / len(persons), 2)
        for person in persons:
            ob = Obligation(
                person_name=person,
                type="one_time",
                total_amount=per_person,
                remaining_amount=per_person,
                note=note,
            )
            repo.add(ob)
            created_names.append(f"{person} ({_format_inr(per_person)})")
    else:
        for person in persons:
            ob = Obligation(
                person_name=person,
                type=obligation_type or "one_time",
                total_amount=amount,
                expected_per_cycle=expected_per_cycle,
                remaining_amount=amount,
                note=note,
            )
            repo.add(ob)
            created_names.append(person)

    await query.edit_message_text(f"Done! Added: {', '.join(created_names)}")


async def _execute_settle(query, persons, amount, note):
    """Execute a settle action — full or partial."""
    if not persons:
        await query.edit_message_text("Couldn't determine who paid. Please try again.")
        return

    results = []
    for person in persons:
        matches = repo.get_by_person(person, status="active")
        if not matches:
            results.append(f"No active obligation found for {person}.")
            continue

        ob = matches[0]  # Take the first active match
        if amount and amount < ob.remaining_amount:
            # Partial payment
            txn = Transaction(amount=amount, paid_at=datetime.now(), note=note)
            updated = repo.add_transaction(ob.id, txn)
            results.append(
                f"{person}: paid {_format_inr(amount)}, "
                f"{_format_inr(updated.remaining_amount)} remaining."
            )
        else:
            # Full settlement
            repo.settle(ob.id)
            results.append(f"{person}: settled {_format_inr(ob.remaining_amount)}!")

    await query.edit_message_text("\n".join(results))


async def _execute_delete(query, persons):
    """Execute a delete action."""
    if not persons:
        await query.edit_message_text(
            "Couldn't determine which obligation to delete."
        )
        return

    results = []
    for person in persons:
        matches = repo.get_by_person(person, status="active")
        if not matches:
            results.append(f"No active obligation found for {person}.")
            continue
        repo.delete(matches[0].id)
        results.append(f"Deleted obligation for {person}.")

    await query.edit_message_text("\n".join(results))


def build_bot_app() -> Application:
    """Build and return the Telegram bot application."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("settled", settled_command))

    # Callback query handler for confirmations
    app.add_handler(CallbackQueryHandler(handle_confirmation))

    # Message handlers
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
