"""Styled static pretty report (Rich print — full scrollback, no TUI viewport)."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.text import Text

from ai.models import Snapshot, UseOrLoseAlert
from ai.tui.builders import ReportSection, build_report_sections


def _print_section(console: Console, section: ReportSection) -> None:
    title = section.title_ansi or section.title
    console.print(Text.from_ansi(title) if "\033" in title else title)
    if section.kind != "header":
        console.print("─" * 48, style="dim")
    for line in section.lines:
        if not line:
            console.print()
            continue
        console.print(Text.from_ansi(line) if "\033" in line else line)
    console.print()


def run_usage_app(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
    brief: bool = False,
    traditional_summary: bool = False,
) -> None:
    """Print the styled report to stdout (static; action plan at a glance last)."""
    sections = build_report_sections(
        snapshot,
        alerts,
        config=config,
        brief=brief,
        traditional_summary=traditional_summary,
    )
    console = Console(highlight=False, soft_wrap=False, emoji=False)
    for section in sections:
        _print_section(console, section)
