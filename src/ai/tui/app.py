"""Inline Textual app for the pretty usage report (static, auto-exits)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical

from ai.models import Snapshot, UseOrLoseAlert
from ai.tui.builders import build_report_sections
from ai.tui.widgets import SectionBlock

_CSS_PATH = Path(__file__).with_name("report.tcss")


class UsageApp(App[None]):
    """Inline static report under the prompt; paints once then exits."""

    CSS_PATH = str(_CSS_PATH)
    INLINE_PADDING = 0
    TITLE = "ai"

    def __init__(
        self,
        snapshot: Snapshot,
        alerts: list[UseOrLoseAlert],
        *,
        config: dict[str, Any] | None = None,
        brief: bool = False,
        traditional_summary: bool = False,
    ) -> None:
        super().__init__()
        self._sections = build_report_sections(
            snapshot,
            alerts,
            config=config,
            brief=brief,
            traditional_summary=traditional_summary,
        )

    def compose(self) -> ComposeResult:
        yield Vertical(
            *[SectionBlock(section) for section in self._sections],
            id="report",
        )

    def on_mount(self) -> None:
        # Paint one static frame into scrollback, then return to the shell.
        self.call_after_refresh(self.exit)


def run_usage_app(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
    brief: bool = False,
    traditional_summary: bool = False,
) -> None:
    """Render the inline Textual report once (does not wait for input)."""
    app = UsageApp(
        snapshot,
        alerts,
        config=config,
        brief=brief,
        traditional_summary=traditional_summary,
    )
    app.run(inline=True, inline_no_clear=True)
