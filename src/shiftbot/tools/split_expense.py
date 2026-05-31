"""Tool: log a shared expense split among multiple participants."""

import uuid
from datetime import timezone

from agents import function_tool
from shared.dates import local_now
from shiftbot.db import get_conn


@function_tool
async def split_expense(
    user_id: str,
    description: str,
    total_amount: float,
    participants: str,
    expense_date: str = "",
) -> str:
    """Record a shared expense and split it evenly among participants.

    USE WHEN: the user wants to split a bill, shared cost, or group
    expense among named participants. Each participant's share is stored
    separately so outstanding balances can be tracked.

    Args:
        user_id:      Telegram user ID string (the person logging the expense).
        description:  What the expense was for (e.g. "Fuel", "Parking", "Tools").
        total_amount: Total expense amount.
        participants: Comma-separated list of participant names or identifiers
                      (e.g. "Alex,Jordan,Sam"). The logged user is automatically
                      included if not already listed.
        expense_date: Date in YYYY-MM-DD format. Defaults to today.
    """
    if not expense_date:
        expense_date = local_now().strftime("%Y-%m-%d")

    names = [n.strip() for n in participants.split(",") if n.strip()]
    if not names:
        return "No participants provided. Please list names separated by commas."

    # Ensure the logging user is counted in the split
    if user_id not in names:
        names.append(user_id)

    per_person = round(total_amount / len(names), 2)
    # Correct rounding to ensure sum matches total
    shares = [per_person] * len(names)
    diff = round(total_amount - sum(shares), 2)
    if diff:
        shares[0] = round(shares[0] + diff, 2)

    expense_id = str(uuid.uuid4())
    created_at = local_now().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO expenses (id, user_id, expense_date, description, total_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (expense_id, user_id, expense_date, description, total_amount, created_at),
        )
        for name, amount in zip(names, shares):
            conn.execute(
                """
                INSERT INTO expense_splits (expense_id, participant, amount_owed, settled)
                VALUES (?, ?, ?, 0)
                """,
                (expense_id, name, amount),
            )

    participant_lines = "\n".join(
        f"  {name}: ${amt:.2f}" for name, amt in zip(names, shares)
    )

    return (
        f"<b>Expense logged</b>\n"
        f"<b>{description}</b> - {expense_date}\n"
        f"<b>Total:</b> ${total_amount:.2f}  |  "
        f"<b>{len(names)} participants</b>\n\n"
        f"{participant_lines}\n\n"
        f"<code>Expense ID: {expense_id[:8]}...</code>"
    )
