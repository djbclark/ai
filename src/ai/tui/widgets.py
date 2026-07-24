"""Textual widgets for the inline usage report."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Label, Static

from ai.tui.builders import ReportSection


class SectionPanel(VerticalScroll):
    """Scrollable titled panel filled with plain Static lines."""

    DEFAULT_CSS = """
    SectionPanel {
        width: 100%;
        height: 1fr;
        min-height: 6;
        overflow-y: auto;
        border: solid $surface;
        padding: 0 1;
    }
    SectionPanel > .section-title {
        text-style: bold;
        color: $accent;
        height: 1;
        text-overflow: ellipsis;
    }
    SectionPanel > .section-line {
        height: auto;
        width: 100%;
    }
    SectionPanel.-plan {
        border: solid $warning;
    }
    SectionPanel.-errors {
        border: solid $error;
    }
    """

    def __init__(self, section: ReportSection, **kwargs) -> None:
        extra = f"-{section.kind}" if section.kind else ""
        existing = kwargs.pop("classes", None)
        if existing:
            classes = f"{existing} {extra}".strip()
        else:
            classes = extra
        super().__init__(classes=classes, **kwargs)
        self._section = section

    def compose(self) -> ComposeResult:
        yield Label(self._section.title, classes="section-title")
        body = "\n".join(self._section.lines) if self._section.lines else "(empty)"
        yield Static(body, classes="section-line", markup=False)
