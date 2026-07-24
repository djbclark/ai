"""Styled static pretty report via Rich (full scrollback; no Textual/Layout)."""

from __future__ import annotations

from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from ai.models import Snapshot, UseOrLoseAlert
from ai.tui.builders import ReportSection, build_report_sections


def _as_text(value: str) -> str | Text:
    if "\033" in value:
        return Text.from_ansi(value)
    return value


def _body_group(lines: list[str]) -> Group:
    parts: list[Any] = []
    for line in lines:
        if not line:
            parts.append(Text(""))
            continue
        parts.append(_as_text(line))
    return Group(*parts) if parts else Group(Text(""))


def _print_section(console: Console, section: ReportSection) -> None:
    title = _as_text(section.title_ansi or section.title)
    body = _body_group(section.lines)

    if section.kind == "header":
        console.print(Panel(body, title=title, border_style="cyan", padding=(0, 1)))
        console.print()
        return

    if section.kind == "plan-glance":
        # Trailer: visible block that still expands into scrollback (not Layout).
        console.print(
            Panel(
                body,
                title=title,
                border_style="yellow",
                padding=(0, 1),
            )
        )
        console.print()
        return

    console.print(Rule(title, style="dim"))
    console.print(body)
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
