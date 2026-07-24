"""Styled static pretty report via Rich (full scrollback; no Textual/Layout)."""

from __future__ import annotations

from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from ai.models import Snapshot, UseOrLoseAlert
from ai.tui.builders import ReportSection, build_report_sections

# Panel chrome (borders + padding) eats columns from glance clamp width.
_PANEL_CHROME = 4


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
    if section.kind == "footer":
        for line in section.lines:
            console.print(_as_text(line) if isinstance(line, str) else line)
        console.print()
        return

    title = _as_text(section.title_ansi or section.title)
    body = _body_group(section.lines)

    if section.kind == "header":
        # Title + meta only — no Panel box (empty-looking chrome around one dim line).
        console.print(title)
        console.print(body)
        console.print()
        return

    if section.kind == "plan-glance":
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

    if section.kind == "meta" and section.title == "Capacity":
        console.print(body)
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
    full: bool = False,
    brief: bool = False,
    traditional_summary: bool = False,
) -> None:
    """Print the styled report to stdout (static; action plan at a glance last)."""
    console = Console(highlight=False, soft_wrap=True, emoji=False)
    glance_width = max(40, console.width - _PANEL_CHROME)
    sections = build_report_sections(
        snapshot,
        alerts,
        config=config,
        full=full,
        brief=brief,
        traditional_summary=traditional_summary,
        glance_width=glance_width,
    )
    for section in sections:
        _print_section(console, section)
