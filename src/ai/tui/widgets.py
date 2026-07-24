"""Compact static section widgets for the inline usage report."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

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
        height: auto;
        width: 100%;
    }
    SectionBlock > .section-rule {
        color: $secondary;
        height: 1;
    }
    SectionBlock > .section-body {
        height: auto;
        width: 100%;
    }
    SectionBlock.-header {
        padding: 1 1 0 1;
        background: $primary 20%;
        border-bottom: tall $accent;
    }
    SectionBlock.-plan-glance {
        padding-top: 1;
        background: $warning 10%;
        border-top: tall $warning;
    }
    SectionBlock.-errors {
        background: $error 15%;
    }
    """

    def __init__(self, section: ReportSection, **kwargs) -> None:
        # CSS class names cannot use underscores the same way; map kind.
        kind = section.kind.replace("_", "-")
        extra = f"-{kind}" if kind else ""
        existing = kwargs.pop("classes", None)
        classes = f"{existing} {extra}".strip() if existing else extra
        super().__init__(classes=classes, **kwargs)
        self._section = section

    def compose(self) -> ComposeResult:
        title = self._section.title_ansi or self._section.title
        yield Static(Text.from_ansi(title), classes="section-title")
        if self._section.kind != "header":
            yield Static("─" * 48, classes="section-rule")
        body = "\n".join(self._section.lines) if self._section.lines else ""
        if body:
            yield Static(Text.from_ansi(body), classes="section-body")
