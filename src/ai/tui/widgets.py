"""Compact static section widgets for the inline usage report."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static

from ai.tui.builders import ReportSection


class SectionBlock(Vertical):
    """Non-scrolling titled block; height follows content."""

    DEFAULT_CSS = """
    SectionBlock {
        width: 100%;
        height: auto;
        padding: 0 1 1 1;
    }
    SectionBlock > .section-title {
        text-style: bold;
        color: $accent;
        height: 1;
        text-overflow: ellipsis;
        margin-bottom: 0;
    }
    SectionBlock > .section-rule {
        color: $text-muted;
        height: 1;
    }
    SectionBlock > .section-body {
        height: auto;
        width: 100%;
    }
    SectionBlock.-header {
        padding-bottom: 0;
        background: $boost;
    }
    SectionBlock.-header > .section-title {
        color: $text;
    }
    SectionBlock.-plan > .section-title {
        color: $warning;
    }
    SectionBlock.-errors > .section-title {
        color: $error;
    }
    """

    def __init__(self, section: ReportSection, **kwargs) -> None:
        extra = f"-{section.kind}" if section.kind else ""
        existing = kwargs.pop("classes", None)
        classes = f"{existing} {extra}".strip() if existing else extra
        super().__init__(classes=classes, **kwargs)
        self._section = section

    def compose(self) -> ComposeResult:
        yield Label(self._section.title, classes="section-title")
        if self._section.kind != "header":
            yield Label("─" * 40, classes="section-rule")
        body = "\n".join(self._section.lines) if self._section.lines else ""
        if body:
            yield Static(body, classes="section-body", markup=False)
