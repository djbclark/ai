"""Report sections for the styled pretty display (ANSI-colored, plan-glance last)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai.models import Snapshot, Urgency, UseOrLoseAlert, provider_display_name
from ai.report import (
    ACTION_PLAN_MAX_LINES,
    ACTION_PLAN_WIDTH,
    URGENCY_ICON,
    _human_deadline,
    _render_account,
    _render_action_plan,
    _render_brief_action_plan,
    _render_cross_checks,
    _sorted_accounts,
    _Style,
    _tips_lines,
)


@dataclass(frozen=True)
class ReportSection:
    """One titled block of lines (may include ANSI) for display."""

    title: str
    lines: list[str] = field(default_factory=list)
    kind: str = "body"  # header | providers | plan | plan-glance | errors | meta | tips
    # Title may also carry ANSI when set via Style.
    title_ansi: str | None = None


def build_report_sections(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
    brief: bool = False,
    traditional_summary: bool = False,
) -> list[ReportSection]:
    """Build sections for the styled report.

    Detail first; **Action plan — at a glance** is always last so scrollback
    lands on the compact plan (same idea as the classic string report).
    """
    del traditional_summary
    s = _Style(True)
    sections: list[ReportSection] = []
    accounts = _sorted_accounts(snapshot.accounts)
    n_accounts = len(accounts)
    n_actionable = sum(1 for a in alerts if a.urgency not in (Urgency.INFO, Urgency.NONE))

    meta = f"Collected at {snapshot.collected_at.isoformat()}"
    meta += f" · {n_accounts} account{'s' if n_accounts != 1 else ''}"
    if n_actionable:
        meta += f" · {n_actionable} alert{'s' if n_actionable != 1 else ''}"
    else:
        meta += " · no burn/conserve alerts"
    title = "AI USAGE — USE IT OR LOSE IT"
    if brief:
        title += " (brief)"
    sections.append(
        ReportSection(
            title=title,
            title_ansi=s.bold(s.cyan(title)),
            lines=[s.dim(meta)],
            kind="header",
        )
    )

    if snapshot.collector_errors:
        sections.append(
            ReportSection(
                title="Collector errors",
                title_ansi=s.bold(s.red("Collector errors")),
                lines=[s.red(f"- {err}") for err in snapshot.collector_errors],
                kind="errors",
            )
        )

    if brief:
        sections.append(
            ReportSection(
                title="Brief mode",
                title_ansi=s.dim("Brief mode"),
                lines=[s.dim("Omit per-provider, cross-checks, tips; full: ai")],
                kind="meta",
            )
        )
    else:
        provider_lines: list[str] = []
        if accounts:
            for acc in accounts:
                provider_lines.extend(_render_account(acc, s, config=config))
        else:
            provider_lines.append(s.dim("(no provider data collected)"))
        sections.append(
            ReportSection(
                title="Per-provider usage",
                title_ansi=s.bold(s.cyan("Per-provider usage")),
                lines=provider_lines,
                kind="providers",
            )
        )

        cross_lines = [
            s.dim(
                "Tools poll at different times; multi-account Claude is cswap-only. "
                "Gaps rarely mean both tools are wrong."
            )
        ]
        if snapshot.cross_checks:
            cross_lines.extend(_render_cross_checks(snapshot.cross_checks, s))
        else:
            cross_lines.append(s.dim("(no overlapping live measurements were available)"))
        sections.append(
            ReportSection(
                title="Cross-checks (informational)",
                title_ansi=s.bold(s.magenta("Cross-checks (informational)")),
                lines=cross_lines,
                kind="meta",
            )
        )
        sections.append(
            ReportSection(
                title="Tips",
                title_ansi=s.bold(s.cyan("Tips")),
                lines=list(_tips_lines(s)),
                kind="tips",
            )
        )

    analysis_cfg = (config or {}).get("analysis") or {}
    waking_hours = float(analysis_cfg.get("waking_hours_per_day", 16))
    width = ACTION_PLAN_WIDTH

    if not brief:
        detailed = _render_action_plan(
            alerts, s, width=width, waking_hours_per_day=waking_hours
        )
        sections.append(
            ReportSection(
                title="Action plan (detailed)",
                title_ansi=s.bold(s.yellow("Action plan (detailed)")),
                lines=[line for line in detailed if line is not None],
                kind="plan",
            )
        )

    # Compact plan always last — what the terminal lands on.
    glance = _render_brief_action_plan(
        alerts, s, width=width, max_lines=ACTION_PLAN_MAX_LINES - 2
    )
    sections.append(
        ReportSection(
            title="Action plan — at a glance",
            title_ansi=s.bold(s.yellow("Action plan — at a glance")),
            lines=[line for line in glance if line is not None],
            kind="plan-glance",
        )
    )
    return sections


def alert_headline(alert: UseOrLoseAlert) -> str:
    """One-line headline for an alert (plain text)."""
    icon = URGENCY_ICON.get(alert.urgency, "   ").strip() or "·"
    who = alert.account or "default"
    when = _human_deadline(alert.days_until_reset)
    verb = "pace" if alert.kind == "conserve" else "use"
    return (
        f"{icon} {provider_display_name(alert.provider)} · {who} · "
        f"{alert.window_label}: {alert.remaining_percent:.0f}% left · {verb} {when}"
    )
