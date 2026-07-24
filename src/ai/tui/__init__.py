"""Inline Textual display for pretty `ai` output."""

from __future__ import annotations

import sys
from typing import Any

from ai.models import Snapshot, UseOrLoseAlert


def textual_available() -> bool:
    try:
        import textual  # noqa: F401
    except ImportError:
        return False
    return True


def should_use_tui(
    *,
    as_json: bool = False,
    alerts_only: bool = False,
    no_tui: bool = False,
    stream: Any = None,
) -> bool:
    """Whether the pretty path should open the inline Textual app."""
    if as_json or alerts_only or no_tui:
        return False
    if sys.platform == "win32":
        return False
    out = stream if stream is not None else sys.stdout
    if not getattr(out, "isatty", lambda: False)():
        return False
    return textual_available()


def run_inline_report(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
    brief: bool = False,
    traditional_summary: bool = False,
) -> None:
    from ai.tui.app import run_usage_app

    run_usage_app(
        snapshot,
        alerts,
        config=config,
        brief=brief,
        traditional_summary=traditional_summary,
    )
