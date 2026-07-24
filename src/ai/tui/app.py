"""Inline Textual app for the pretty usage report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, Static

from ai.models import Snapshot, UseOrLoseAlert
from ai.tui.builders import build_report_sections
from ai.tui.widgets import SectionPanel

_CSS_PATH = Path(__file__).with_name("report.tcss")
_NARROW_WIDTH = 80


class UsageApp(App[None]):
    """Inline (under-prompt) usage report. Quit with q."""

    CSS_PATH = str(_CSS_PATH)
    INLINE_PADDING = 0
    TITLE = "ai"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
    ]

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
        self._snapshot = snapshot
        self._alerts = alerts
        self._config = config
        self._brief = brief
        self._traditional_summary = traditional_summary
        self._sections = build_report_sections(
            snapshot,
            alerts,
            config=config,
            brief=brief,
            traditional_summary=traditional_summary,
        )

    def compose(self) -> ComposeResult:
        by_kind = {section.kind: section for section in self._sections}
        header = by_kind.get("header")
        if header:
            yield Vertical(
                Label(header.title, classes="section-title"),
                Static(header.lines[0] if header.lines else "", classes="section-meta", markup=False),
                id="header",
            )

        errors = by_kind.get("errors")
        if errors:
            yield SectionPanel(errors, id="errors")

        plan = by_kind.get("plan")
        providers = by_kind.get("providers")

        if self._brief:
            if plan:
                yield SectionPanel(plan, id="plan")
            meta = by_kind.get("meta")
            if meta:
                yield SectionPanel(meta, id="meta-brief")
        else:
            body_children: list = []
            if providers:
                body_children.append(SectionPanel(providers, id="providers"))
            if plan:
                body_children.append(SectionPanel(plan, id="plan"))
            yield Vertical(*body_children, id="body")

            meta_sections = [s for s in self._sections if s.kind in ("meta", "tips")]
            if meta_sections:
                yield Horizontal(
                    *[SectionPanel(section, id=f"meta-{section.kind}") for section in meta_sections],
                    id="meta-row",
                )

        yield Label("q quit · scroll panes · narrow terminals stack plan first", id="footer-hint")
        yield Footer()

    def on_resize(self) -> None:
        # Textual has no @media queries; toggle a class for Termux-width layouts.
        self.screen.set_class(self.size.width < _NARROW_WIDTH, "-narrow")

    def on_mount(self) -> None:
        self.screen.set_class(self.size.width < _NARROW_WIDTH, "-narrow")

    def action_quit(self) -> None:
        self.exit()


def run_usage_app(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
    brief: bool = False,
    traditional_summary: bool = False,
) -> None:
    """Run the inline Textual report (blocks until quit)."""
    app = UsageApp(
        snapshot,
        alerts,
        config=config,
        brief=brief,
        traditional_summary=traditional_summary,
    )
    app.run(inline=True)
