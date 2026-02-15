import uuid
from datetime import datetime

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
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
    """Build a summary of pending obligations grouped by direction."""
    if not obligations:
        return "No pending obligations! You're all clear."

    they_owe = [ob for ob in obligations if ob.direction != "i_owe"]
    i_owe = [ob for ob in obligations if ob.direction == "i_owe"]

    lines = ["*Pending obligations:*\n"]
    counter = 1

    if they_owe:
        lines.append("*They owe you:*")
        for ob in they_owe:
            line = f"{counter}. *{ob.person_name}* — {_format_inr(ob.remaining_amount)}"
            if ob.type == "recurring":
                line += " (recurring)"
            if ob.note:
                line += f" — {ob.note}"
            lines.append(line)
            counter += 1
        total_owed = sum(ob.remaining_amount for ob in they_owe)
        lines.append(f"_Subtotal: {_format_inr(total_owed)}_\n")

    if i_owe:
        lines.append("*You owe:*")
        for ob in i_owe:
            line = f"{counter}. *{ob.person_name}* — {_format_inr(ob.remaining_amount)}"
            if ob.type == "recurring":
                line += " (recurring)"
            if ob.note:
                line += f" — {ob.note}"
            lines.append(line)
            counter += 1
        total_you_owe = sum(ob.remaining_amount for ob in i_owe)
        lines.append(f"_Subtotal: {_format_inr(total_you_owe)}_\n")

    total = sum(ob.remaining_amount for ob in obligations)
    lines.append(f"*Total pending: {_format_inr(total)}*")
    return "\n".join(lines)


def _build_obligation_label(ob: Obligation) -> str:
    """One-line label for an obligation: '₹5,800 (recurring) — Phone advance'."""
    label = _format_inr(ob.remaining_amount)
    if ob.type == "recurring":
        label += " (recurring)"
    if ob.note:
        label += f" — {ob.note}"
    return label


def _serialize_obligation(ob: Obligation) -> dict:
    """Serialize an Obligation to a JSON-safe dict for storage in user_data."""
    data = ob.model_dump()
    # Convert datetime fields to ISO strings
    data["created_at"] = data["created_at"].isoformat()
    for txn in data.get("transactions", []):
        txn["paid_at"] = txn["paid_at"].isoformat()
    return data


def _deserialize_obligation(data: dict) -> Obligation:
    """Deserialize an Obligation from a stored dict."""
    data["created_at"] = datetime.fromisoformat(data["created_at"])
    for txn in data.get("transactions", []):
        txn["paid_at"] = datetime.fromisoformat(txn["paid_at"])
    return Obligation(**data)


async def _show_disambiguation(
    query, matches: list[Obligation], action_data: dict,
    context: ContextTypes.DEFAULT_TYPE, person: str,
) -> None:
    """Present an inline keyboard for the user to pick one obligation."""
    buttons = []
    for i, ob in enumerate(matches):
        buttons.append(
            [InlineKeyboardButton(
                _build_obligation_label(ob), callback_data=f"choose_{i}"
            )]
        )
    buttons.append(
        [InlineKeyboardButton("Cancel", callback_data="choose_cancel")]
    )

    context.user_data["pending_choice"] = {
        "action_data": action_data,
        "matches": [_serialize_obligation(ob) for ob in matches],
        "person": person,
    }

    await query.edit_message_text(
        f"{person} has {len(matches)} active obligations. Which one?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    context.user_data["pending_message_id"] = query.message.message_id


async def _handle_choice(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a disambiguation choice callback."""
    context.user_data.pop("pending_message_id", None)
    choice_data = context.user_data.pop("pending_choice", None)
    if not choice_data:
        await query.edit_message_text("Session expired. Please send a new message.")
        return

    if query.data == "choose_cancel":
        await query.edit_message_text("Cancelled.")
        return

    idx = int(query.data.split("_")[1])
    matches = [_deserialize_obligation(d) for d in choice_data["matches"]]
    if idx < 0 or idx >= len(matches):
        await query.edit_message_text("Invalid choice. Please try again.")
        return

    ob = matches[idx]
    action_data = choice_data["action_data"]
    action = action_data["action"]

    try:
        if action == "settle":
            await _execute_settle_single(
                query, ob, action_data.get("amount"), action_data.get("note")
            )
        elif action == "edit":
            await _execute_edit_single(query, ob, action_data)
        elif action == "delete":
            repo.delete(ob.id)
            await query.edit_message_text(
                f"Deleted obligation for {choice_data['person']}: {_build_obligation_label(ob)}"
            )
    except Exception as e:
        logger.error("Error executing choice action: {}", e)
        await query.edit_message_text(f"Something went wrong: {e}")


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

    # Clear any pending inline-keyboard state from a previous interaction
    stale_msg_id = context.user_data.pop("pending_message_id", None)
    had_pending = context.user_data.pop("pending_action", None)
    had_choice = context.user_data.pop("pending_choice", None)
    if stale_msg_id and (had_pending or had_choice):
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.message.chat_id,
                message_id=stale_msg_id,
                reply_markup=None,
            )
        except Exception:
            pass  # Message may have been deleted or already edited

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

    # Chitchat or off-topic — just relay the LLM's message
    if llm_result.parsed and llm_result.parsed.action in ("chitchat", "off_topic"):
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
        sent = await update.message.reply_text(
            llm_result.confirmation_message, reply_markup=keyboard
        )
        context.user_data["pending_message_id"] = sent.message_id
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
    """Handle Yes/No button presses and disambiguation choices."""
    query = update.callback_query
    await query.answer()

    # Disambiguation choice
    if query.data and query.data.startswith("choose_"):
        await _handle_choice(query, context)
        return

    if query.data == "confirm_no":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_message_id", None)
        context.user_data.pop("history", None)
        await query.edit_message_text(query.message.text + "\n\n_Cancelled._", parse_mode="Markdown")
        return

    # confirm_yes
    action_data = context.user_data.pop("pending_action", None)
    context.user_data.pop("pending_message_id", None)
    context.user_data.pop("history", None)
    if not action_data:
        await query.edit_message_text("Nothing to confirm. Send a new message.")
        return

    action = action_data["action"]
    persons = action_data.get("persons", [])
    amount = action_data.get("amount")
    direction = action_data.get("direction", "owes_me")
    obligation_type = action_data.get("obligation_type")
    expected_per_cycle = action_data.get("expected_per_cycle")
    note = action_data.get("note")

    try:
        if action == "add":
            await _execute_add(
                query, persons, amount, obligation_type, expected_per_cycle, note, direction
            )
        elif action == "settle":
            await _execute_settle(query, persons, amount, note, context=context, action_data=action_data)
        elif action == "delete":
            await _execute_delete(query, persons, context=context, action_data=action_data)
        elif action == "edit":
            await _execute_edit(query, persons, action_data, context=context)
        else:
            await query.edit_message_text("I'm not sure what to do with that.")
    except Exception as e:
        logger.error("Error executing action: {}", e)
        await query.edit_message_text(f"Something went wrong: {e}")


async def _execute_add(query, persons, amount, obligation_type, expected_per_cycle, note, direction="owes_me"):
    """Execute an add obligation action."""
    if not persons or not amount:
        await query.edit_message_text("Missing person or amount. Please try again.")
        return

    trxn_id = str(uuid.uuid4()) if len(persons) > 1 else None

    created_names = []
    if obligation_type == "one_time":
        # Split equally among persons
        per_person = round(amount, 2)
        for person in persons:
            ob = Obligation(
                person_name=person,
                type=obligation_type,
                direction=direction,
                total_amount=per_person,
                remaining_amount=per_person,
                note=note,
                trxn_id=trxn_id,
            )
            repo.add(ob)
            created_names.append(f"{person} ({_format_inr(per_person)})")
    elif obligation_type == "recurring":
        for person in persons:
            ob = Obligation(
                person_name=person,
                type=obligation_type,
                direction=direction,
                total_amount=amount,
                expected_per_cycle=expected_per_cycle,
                remaining_amount=amount,
                note=note,
                trxn_id=trxn_id,
            )
            repo.add(ob)
            created_names.append(person)
    else:
        raise ValueError(f"Unknown obligation type: {obligation_type}")

    await query.edit_message_text(f"Done! Added: {', '.join(created_names)}")


async def _execute_settle_single(query, ob: Obligation, amount, note):
    """Settle a single obligation — full or partial."""
    if amount and amount < ob.remaining_amount and ob.type != "one_time":
        txn = Transaction(amount=amount, paid_at=datetime.now(), note=note)
        updated = repo.add_transaction(ob.id, txn)
        await query.edit_message_text(
            f"{ob.person_name}: paid {_format_inr(amount)}, "
            f"{_format_inr(updated.remaining_amount)} remaining."
        )
    else:
        repo.settle(ob.id)
        await query.edit_message_text(
            f"{ob.person_name}: settled {_format_inr(ob.remaining_amount)}!"
        )


async def _execute_settle(query, persons, amount, note, *, context=None, action_data=None):
    """Execute a settle action — full or partial, with disambiguation if needed."""
    if not persons:
        await query.edit_message_text("Couldn't determine who paid. Please try again.")
        return

    results = []
    for person in persons:
        matches = repo.get_by_person(person, status="active")
        if not matches:
            results.append(f"No active obligation found for {person}.")
            continue

        if len(matches) > 1 and context is not None and action_data is not None:
            await _show_disambiguation(query, matches, action_data, context, person)
            return

        ob = matches[0]
        if amount and amount < ob.remaining_amount and ob.type != "one_time":
            txn = Transaction(amount=amount, paid_at=datetime.now(), note=note)
            updated = repo.add_transaction(ob.id, txn)
            results.append(
                f"{person}: paid {_format_inr(amount)}, "
                f"{_format_inr(updated.remaining_amount)} remaining."
            )
        else:
            repo.settle(ob.id)
            results.append(f"{person}: settled {_format_inr(ob.remaining_amount)}!")

    await query.edit_message_text("\n".join(results))


async def _execute_edit_single(query, ob: Obligation, action_data: dict):
    """Apply edits to a single obligation."""
    updates = {}
    changes = []

    if action_data.get("expected_per_cycle") is not None:
        updates["expected_per_cycle"] = action_data["expected_per_cycle"]
        changes.append(f"monthly deduction → {_format_inr(action_data['expected_per_cycle'])}")

    if action_data.get("amount") is not None:
        new_total = action_data["amount"]
        already_paid = ob.total_amount - ob.remaining_amount
        new_remaining = max(new_total - already_paid, 0)
        updates["total_amount"] = new_total
        updates["remaining_amount"] = new_remaining
        changes.append(f"total → {_format_inr(new_total)} ({_format_inr(new_remaining)} remaining)")

    if action_data.get("note") is not None:
        updates["note"] = action_data["note"]
        changes.append(f"note → {action_data['note']}")

    if not updates:
        await query.edit_message_text("No changes to apply.")
        return

    repo.update(ob.id, **updates)
    await query.edit_message_text(
        f"Updated {ob.person_name}: {'; '.join(changes)}"
    )


async def _execute_edit(query, persons, action_data, *, context=None):
    """Execute an edit action, with disambiguation if needed."""
    if not persons:
        await query.edit_message_text("Couldn't determine who to edit. Please try again.")
        return

    person = persons[0]
    matches = repo.get_by_person(person, status="active")
    if not matches:
        await query.edit_message_text(f"No active obligation found for {person}.")
        return

    if len(matches) > 1 and context is not None:
        await _show_disambiguation(query, matches, action_data, context, person)
        return

    await _execute_edit_single(query, matches[0], action_data)


async def _execute_delete(query, persons, *, context=None, action_data=None):
    """Execute a delete action, with disambiguation if needed."""
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

        if len(matches) > 1 and context is not None and action_data is not None:
            await _show_disambiguation(query, matches, action_data, context, person)
            return

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
