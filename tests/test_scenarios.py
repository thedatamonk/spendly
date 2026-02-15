"""
LLM scenario test script.

Calls IntentParser.parse() directly with real-world scenarios and prints
the raw LLM responses in a readable chat-style format.

Usage:
    uv run python -m tests.test_scenarios
"""

import sys
from pathlib import Path

from app.config import get_settings
from app.llm.parser import IntentParser
from app.models.schemas import LLMResponse, Obligation

SEPARATOR = "=" * 60
LOG_FILE = Path(__file__).parent / "results.log"

SCENARIOS = [
    {
        "name": "Equal split - petrol with Shivam",
        "messages": [
            "Weekend vacation with Shivam. Record petrol charges for car of 7K. Needs to be split equally.",
        ],
    },
    {
        "name": "Multi-turn - Ananya payment",
        "messages": [
            "Payment to be received from Ananya",
            "8900rs",
        ],
    },
    {
        "name": "Unequal split - stress test",
        "messages": [
            "Brunch with office friends at Daddy's. Total bill 3000. "
            "Total 4 people - Shivam, Yashasvi and Anjali. "
            "Anjali will pay only 1000rs while remaining amount split equally between the other 3.",
        ],
    },
    # ── Adversarial scenarios ───────────────────────────────────────
    {
        "name": "Recurring advance with multiple amounts — Anita double advance",
        "messages": [
            "Anita's salary is 4500 rs per month. I have already paid her advance "
            "500rs for her kid's fees and 500rs again for some emergency as cash. "
            "Record this so that I don't forget this when I am paying her salary.",
        ],
    },
    {
        "name": "Unnamed person — girlfriend",
        "messages": [
            "Dinner date with girlfriend, Total bill is 5K. Bill needs to be split equally",
        ],
    },
    {
        "name": "Missing amount — bill split with no total",
        "messages": [
            "Brunch with office friends at Bier Library. Total bill needs to be split equally.",
        ],
    },

    {
        "name": "Reversed direction — user owes someone else",
        "messages": [
            "I owe Rahul 5000 for the concert tickets he booked",
        ],
    },

    {
        "name": "Hinglish input",
        "messages": [
            "Sunita ko 5800 diya phone ke liye, har mahine 1000 katna",
        ],
    },

    {
        "name": "Off-topic / non-financial message",
        "messages": [
            "Remind me to call mom tomorrow at 10am",
        ],
    },

    {
        "name": "Head-count split math — user included in count",
        "messages": [
            "Dinner at Bombay Canteen. Total bill 4800. "
            "4 people — me, Kunal, Priya and Sid. Split equally.",
        ],
    },
    {
        "name": "Tip/tax on top of base — derived arithmetic",
        "messages": [
            "Lunch with Meera, bill was 2000 plus 18% GST. "
            "I paid the whole thing, split equally.",
        ],
    },

    {
        "name": "Partial settlement — Sunita paid 2000",
        "context": [
            Obligation(
                person_name="Sunita",
                type="recurring",
                total_amount=5800,
                remaining_amount=5800,
                expected_per_cycle=1000,
                note="Phone advance",
            ),
        ],
        "messages": [
            "Sunita ne 2000 de diye",
            "Abhi Sunita ke kitna amount due hai?"
        ],
    },
    {
        "name": "Edit existing obligation — change monthly deduction",
        "context": [
            Obligation(
                person_name="Sunita",
                type="recurring",
                total_amount=5800,
                remaining_amount=3800,
                expected_per_cycle=1000,
                note="Phone advance",
            ),
        ],
        "messages": [
            "Change Sunita's monthly deduction to 1500 instead of 1000",
        ],
    },
    # ── Settlement scenarios ─────────────────────────────────────────
    {
        "name": "Full settlement — Shivam paid back",
        "context": [
            Obligation(
                person_name="Shivam",
                type="one_time",
                total_amount=3500,
                remaining_amount=3500,
                note="Petrol charges",
            ),
        ],
        "messages": [
            "Shivam paid me back the 3500 for petrol",
        ],
    },
    {
        "name": "Chitchat — simple greeting",
        "messages": ["Hi!"],
    },
    {
        "name": "Settle with multiple obligations — Anjali partial",
        "context": [
            Obligation(
                person_name="Anjali",
                type="one_time",
                total_amount=1000,
                remaining_amount=1000,
                note="Brunch at Daddy's",
            ),
            Obligation(
                person_name="Anjali",
                type="one_time",
                total_amount=2500,
                remaining_amount=2500,
                note="Movie tickets",
            ),
        ],
        "messages": [
            "Anjali just paid 1000 for the brunch",
        ],
    },
    # ── New coverage scenarios ─────────────────────────────────────
    {
        "name": "Delete obligation — remove Rahul's entry",
        "context": [
            Obligation(
                person_name="Rahul",
                type="one_time",
                total_amount=5000,
                remaining_amount=5000,
                note="Concert tickets",
            ),
        ],
        "messages": [
            "Delete Rahul's concert tickets entry",
        ],
    },
    {
        "name": "Edit total amount — Anita's advance was actually 6000",
        "context": [
            Obligation(
                person_name="Anita",
                type="recurring",
                total_amount=5800,
                remaining_amount=5800,
                expected_per_cycle=1000,
                note="Phone advance",
            ),
        ],
        "messages": [
            "Actually Anita's total was 6000, not 5800. Update it.",
        ],
    },
    {
        "name": "Edit note — update Shivam's note",
        "context": [
            Obligation(
                person_name="Shivam",
                type="one_time",
                total_amount=3500,
                remaining_amount=3500,
                note="Petrol charges",
            ),
        ],
        "messages": [
            "Change Shivam's note to 'Petrol + toll charges'",
        ],
    },
    {
        "name": "Query — how much does Kunal owe",
        "messages": [
            "How much does Kunal owe me?",
        ],
    },
    {
        "name": "Settle i_owe — paid Rahul back",
        "context": [
            Obligation(
                person_name="Rahul",
                type="one_time",
                direction="i_owe",
                total_amount=5000,
                remaining_amount=5000,
                note="Concert tickets",
            ),
        ],
        "messages": [
            "I paid Rahul the 5000 I owed him for concert tickets",
        ],
    },
    {
        "name": "Delete with disambiguation — Anjali has two obligations",
        "context": [
            Obligation(
                person_name="Anjali",
                type="one_time",
                total_amount=1000,
                remaining_amount=1000,
                note="Brunch at Daddy's",
            ),
            Obligation(
                person_name="Anjali",
                type="one_time",
                total_amount=2500,
                remaining_amount=2500,
                note="Movie tickets",
            ),
        ],
        "messages": [
            "Delete Anjali's movie tickets entry",
        ],
    },
    {
        "name": "Edit with disambiguation — Anjali update amount",
        "context": [
            Obligation(
                person_name="Anjali",
                type="one_time",
                total_amount=1000,
                remaining_amount=1000,
                note="Brunch at Daddy's",
            ),
            Obligation(
                person_name="Anjali",
                type="one_time",
                total_amount=2500,
                remaining_amount=2500,
                note="Movie tickets",
            ),
        ],
        "messages": [
            "Anjali's movie tickets were actually 3000, update it",
        ],
    },
    {
        "name": "Query — what's pending overall",
        "messages": [
            "Show me all pending dues",
        ],
    },
]


def _intent_summary(result: LLMResponse) -> str:
    """Format a one-line summary of the parsed intent."""
    p = result.parsed
    if p is None:
        return "[parsed=None]"
    persons = [f'"{n}"' for n in p.persons]
    parts = [
        f"action={p.action}",
        f"persons=[{', '.join(persons)}]",
        f"direction={p.direction}",
        f"amount={p.amount}",
        f"type={p.obligation_type}",
        f"ambiguous={str(p.is_ambiguous).lower()}",
    ]
    if p.note:
        parts.append(f'note="{p.note}"')
    if p.expected_per_cycle is not None:
        parts.append(f"per_cycle={p.expected_per_cycle}")
    if p.clarifying_question:
        parts.append(f'question="{p.clarifying_question}"')
    return "[" + ", ".join(parts) + "]"


def _print_and_log(text: str, file):
    """Print to stdout and write to log file."""
    print(text)
    file.write(text + "\n")


def run_scenario(parser: IntentParser, index: int, scenario: dict, log):
    """Run a single scenario: feed each message in sequence, building history."""
    _print_and_log(f"\n{SEPARATOR}", log)
    _print_and_log(f"SCENARIO {index}: {scenario['name']}", log)
    _print_and_log(SEPARATOR, log)

    history: list[dict] = []

    for msg in scenario["messages"]:
        _print_and_log(f"\n  User: {msg}", log)

        result = parser.parse(msg, context=scenario.get("context"), history=history or None)

        _print_and_log(f"\n  Bot: {result.confirmation_message}", log)
        _print_and_log(f"\n  {_intent_summary(result)}", log)

        # Accumulate history for subsequent turns
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": result.confirmation_message})


def main():
    settings = get_settings()

    if not settings.openrouter_api_key:
        print("ERROR: OPENROUTER_API_KEY not set. Add it to .env and retry.")
        sys.exit(1)

    parser = IntentParser(api_key=settings.openrouter_api_key, model=settings.llm_model)

    print(f"Model: {settings.llm_model}")
    print(f"Log:   {LOG_FILE}")

    with open(LOG_FILE, "w") as log:
        _print_and_log(f"Model: {settings.llm_model}", log)

        for i, scenario in enumerate(SCENARIOS, 1):
            run_scenario(parser, i, scenario, log)

        _print_and_log(f"\n{SEPARATOR}", log)
        _print_and_log("Done. Review results above or in tests/results.log", log)
        _print_and_log(SEPARATOR, log)


if __name__ == "__main__":
    main()
