"""Interactive fuzzy channel picker using InquirerPy."""

from __future__ import annotations

from typing import Any

from InquirerPy import inquirer
from InquirerPy.base.control import Choice


def pick_channel(channels: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Launch an interactive fuzzy search prompt and return the selected channel dict.

    Returns None if the user cancels (Ctrl+C / Ctrl+D).
    """
    if not channels:
        return None

    choices = [
        Choice(
            value=ch,
            name=f"{ch['name']}  [{ch['group']}]" if ch.get("group") else ch["name"],
        )
        for ch in channels
    ]

    try:
        result = inquirer.fuzzy(
            message="Select a channel (type to filter):",
            choices=choices,
            max_height="70%",
            match_exact=False,
            instruction="(↑↓ navigate  Enter select  Ctrl+C cancel)",
        ).execute()
    except (KeyboardInterrupt, EOFError):
        return None

    return result
