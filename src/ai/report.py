"""Human-readable terminal report (pretty by default)."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, TextIO

from ai.analysis.use_or_lose import DAYS_PER_MONTH, _classify_flexibility, _compute_value_at_risk
from ai.models import (
    AccountUsage,
    CrossCheck,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
    classify_window_minutes,
    provider_display_name,
)

URGENCY_ICON = {
    Urgency.CRITICAL: "!!!",
    Urgency.HIGH: "!! ",
    Urgency.MEDIUM: "!  ",
    Urgency.LOW: ".  ",
    Urgency.INFO: "i  ",
    Urgency.NONE: "   ",
}


class _Style:
    """ANSI colors when stdout is a TTY and color is not disabled."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def dim(self, t: str) -> str:
        return self._wrap("2", t)

    def red(self, t: str) -> str:
        return self._wrap("31", t)

    def yellow(self, t: str) -> str:
        return self._wrap("33", t)

    def green(self, t: str) -> str:
        return self._wrap("32", t)

    def cyan(self, t: str) -> str:
        return self._wrap("36", t)

    def magenta(self, t: str) -> str:
        return self._wrap("35", t)

    def urgency(self, level: Urgency, text: str) -> str:
        if level == Urgency.CRITICAL:
            return self.bold(self.red(text))
        if level == Urgency.HIGH:
            return self.red(text)
        if level == Urgency.MEDIUM:
            return self.yellow(text)
        if level == Urgency.LOW:
            return self.cyan(text)
        if level == Urgency.INFO:
            return self.dim(text)
        return text


def use_color(*, stream: TextIO | None = None, force: bool | None = None) -> bool:
    if force is not None:
        return force
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def render_report(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
    color: bool | None = None,
    traditional_summary: bool = False,
) -> str:
    """
    Report order:
      1. Tips
      2. Per-provider live quota detail
      3. Cross-checks between overlapping live tools
      4. Summary — what to use, by when, so paid allotment is not wasted
    """
    s = _Style(use_color(force=color))
    lines: list[str] = []
    width = 72

    lines.append(s.bold("=" * width))
    lines.append(s.bold(s.cyan("AI USAGE — USE IT OR LOSE IT")))
    lines.append(s.dim(f"Collected at {snapshot.collected_at.isoformat()}"))
    lines.append(s.bold("=" * width))

    # 1) Tips first
    lines.append("")
    lines.append(s.bold("## Tips"))
    lines.append(s.dim("-" * width))
    lines.extend(_tips_lines(s))

    # 2) Per-provider live quota detail
    lines.append("")
    lines.append(s.bold("## Per-provider usage"))
    lines.append(s.dim("-" * width))
    accounts = _sorted_accounts(snapshot.accounts)
    if accounts:
        for acc in accounts:
            lines.extend(_render_account(acc, s, config=config))
    else:
        lines.append(s.dim("  (no provider data collected)"))

    # 3) Independent live-source consistency checks
    lines.append("")
    lines.append(s.bold("## Cross-checks between live tools"))
    lines.append(s.dim("-" * width))
    if snapshot.cross_checks:
        lines.extend(_render_cross_checks(snapshot.cross_checks, s))
    else:
        lines.append(s.dim("  (no overlapping live measurements were available)"))
    lines.append("")

    if snapshot.collector_errors:
        lines.append(s.bold(s.red("## Collector errors")))
        lines.append(s.dim("-" * width))
        for err in snapshot.collector_errors:
            lines.append(s.red(f"  - {err}"))
        lines.append("")

    # 4) Summary — use within timeframe or lose subscription capacity
    lines.append(s.bold("## Summary — use these before they reset"))
    lines.append(s.dim("-" * width))
    if traditional_summary:
        lines.extend(_render_traditional_summary(alerts, s, width=width))
    else:
        analysis_cfg = (config or {}).get("analysis") or {}
        waking_hours = float(analysis_cfg.get("waking_hours_per_day", 16))
        lines.extend(
            _render_action_plan(alerts, s, width=width, waking_hours_per_day=waking_hours)
        )

    return "\n".join(lines)


def _tips_lines(s: _Style) -> list[str]:
    return [
        s.dim("  • Subscription windows (weekly/monthly) expire unused — burn them on real work."),
        s.dim("  • Prepaid API balances usually roll; no rush unless a promo credit has an expiry."),
        s.dim("  • Claude Code accounts come only from cswap, the canonical Claude source."),
        s.dim("  • Each Claude Code email is reported as a separate account."),
        s.dim("  • Overlapping tools are cross-checked; only one copy drives alerts."),
        s.dim("  • Re-run:  ai              (pretty human report, default)"),
        s.dim("  • JSON:    ai --json       or  ai --format json"),
        s.dim("  • Config:  $XDG_CONFIG_HOME/ai/services.yaml (default ~/.config/ai/services.yaml)"),
    ]


def _render_traditional_summary(
    alerts: list[UseOrLoseAlert],
    s: _Style,
    *,
    width: int,
) -> list[str]:
    action = [a for a in alerts if a.urgency not in (Urgency.INFO, Urgency.NONE)]
    info = [a for a in alerts if a.urgency == Urgency.INFO]
    lines: list[str] = []

    if not action:
        lines.append(s.green("  Nothing urgent: no large unused subscription windows"))
        lines.append(s.green("  are about to reset under your current thresholds."))
        lines.append(s.dim("  (Quotas may be well-used, resets far out, or live quota data missing"))
        lines.append(s.dim("   — check per-provider detail above.)"))
    else:
        lines.append(s.dim("  Paid plan capacity that goes unused when the window resets is gone forever."))
        lines.append(s.dim("  Prefer these providers/accounts soon so you do not leave tokens on the table."))
        lines.append("")

        # Group by time bucket for a clear "within X" narrative
        buckets: dict[str, list[UseOrLoseAlert]] = {
            "within 24 hours": [],
            "within 3 days": [],
            "within 7 days": [],
            "within 14 days": [],
            "later / unknown reset": [],
        }
        for alert in action:
            buckets[_time_bucket(alert.days_until_reset)].append(alert)

        for bucket_name, items in buckets.items():
            if not items:
                continue
            lines.append(s.bold(f"  → {bucket_name}"))
            for alert in sorted(
                items,
                key=lambda a: (
                    a.days_until_reset if a.days_until_reset is not None else 999,
                    -a.remaining_percent,
                ),
            ):
                lines.append(_summary_alert_line(alert, s))
            lines.append("")

        # One-line action plan
        lines.append(s.bold("  Action plan"))
        lines.append(s.dim("  " + "-" * (width - 4)))
        for i, alert in enumerate(
            sorted(
                action,
                key=lambda a: (
                    a.days_until_reset if a.days_until_reset is not None else 999,
                    -a.score,
                ),
            ),
            start=1,
        ):
            when = _human_deadline(alert.days_until_reset)
            who = alert.account or "default account"
            lines.append(
                f"  {i}. {s.bold(provider_display_name(alert.provider))} ({who}): burn "
                f"{s.yellow(f'{alert.remaining_percent:.0f}%')} of "
                f"{alert.window_label} {when}"
            )
        lines.append("")

    if info:
        lines.append(s.bold("  Advisory / low urgency (no hard deadline)"))
        lines.append(s.dim("  " + "-" * (width - 4)))
        for alert in info:
            lines.append(s.dim(f"  · {alert.message}"))
        lines.append("")

    return lines


def _render_action_plan(
    alerts: list[UseOrLoseAlert],
    s: _Style,
    *,
    width: int,
    waking_hours_per_day: float = 16.0,
) -> list[str]:
    action = [a for a in alerts if a.urgency not in (Urgency.INFO, Urgency.NONE)]
    info = [a for a in alerts if a.urgency == Urgency.INFO]
    lines: list[str] = []

    total_value_usd = sum(
        a.flexibility_profile.value_at_risk_usd
        for a in action
        if a.flexibility_profile and a.flexibility_profile.value_at_risk_usd is not None
    )
    providers = len({a.provider for a in action})

    if not action and not info:
        lines.append(s.green("  Nothing urgent: no large unused subscription windows"))
        lines.append(s.green("  are about to reset under your current thresholds."))
        lines.append(s.dim("  (Quotas may be well-used, resets far out, or live quota data missing"))
        lines.append(s.dim("   — check per-provider detail above.)"))
        return lines

    if action:
        if total_value_usd > 0:
            lines.append(
                s.dim(
                    f"  Available capacity this cycle: {s.bold(f'${total_value_usd:.2f}')} across {len(action)} windows ({providers} providers)."
                )
            )
        else:
            lines.append(s.dim(f"  {len(action)} windows with unused capacity across {providers} providers."))
        lines.append("")

        buckets = _action_buckets(action)
        for bucket_label, bucket_name in [
            ("THIS WEEK", "start now — capacity will reset or needs lead time"),
            ("THIS WEEKEND", "plan ahead"),
            ("LATER THIS MONTH", "before next billing cycle"),
        ]:
            items = buckets.get(bucket_label, [])
            if not items:
                continue
            lines.append(f"  {s.bold(bucket_label)} ({s.dim(bucket_name)})")
            lines.append(s.dim(f"  {'─' * (width - 4)}"))
            for alert in sorted(items, key=lambda a: (-a.score,)):
                lines.append(_action_plan_line(alert, s))
            lines.append("")

        throttled = buckets.get("THROTTLED", [])
        if throttled:
            lines.append(f"  {s.bold('THROTTLED — ACCUMULATING WASTE')}")
            lines.append(s.dim(f"  {'─' * (width - 4)}"))
            lines.append(s.dim("  These windows refill so fast you can't use them all. Estimated"))
            lines.append(s.dim("  plan value silently wasted each month:"))
            lines.append("")
            for alert in sorted(throttled, key=lambda a: (-a.score,)):
                lines.append(
                    _throttled_waste_line(alert, s, waking_hours_per_day=waking_hours_per_day)
                )
            lines.append("")

    if info:
        lines.append(s.bold("  ADVISORY / LOW URGENCY (no hard deadline)"))
        lines.append(s.dim(f"  {'─' * (width - 4)}"))
        for alert in info:
            lines.append(s.dim(f"  · {alert.message}"))
        lines.append("")

    return lines


def _action_buckets(alerts: list[UseOrLoseAlert]) -> dict[str, list[UseOrLoseAlert]]:
    buckets: dict[str, list[UseOrLoseAlert]] = {
        "THIS WEEK": [],
        "THIS WEEKEND": [],
        "LATER THIS MONTH": [],
        "THROTTLED": [],
    }
    for alert in alerts:
        profile = alert.flexibility_profile
        is_throttled = profile is not None and profile.consumption_flexibility < 0.2
        days = alert.days_until_reset

        if is_throttled and days is not None and days <= 3:
            buckets["THIS WEEK"].append(alert)
        elif is_throttled:
            buckets["THROTTLED"].append(alert)
        elif days is not None and days <= 7:
            buckets["THIS WEEK"].append(alert)
        elif days is not None and days <= 10:
            buckets["THIS WEEKEND"].append(alert)
        else:
            buckets["LATER THIS MONTH"].append(alert)

    return buckets


def _action_plan_line(alert: UseOrLoseAlert, s: _Style) -> str:
    icon = URGENCY_ICON.get(alert.urgency, "   ")
    badge = s.urgency(alert.urgency, f"{icon}")
    who = alert.account or "default"
    when = _human_deadline(alert.days_until_reset)

    profile = alert.flexibility_profile
    value_part = ""
    flex_note = ""
    if profile:
        if profile.value_at_risk_usd is not None:
            value_part = f" · ${profile.value_at_risk_usd:.2f} at risk"
        if profile.consumption_flexibility >= 0.9:
            flex_note = "Burstable — one heavy session will cover it."
        elif profile.consumption_flexibility >= 0.4:
            flex_note = "Semi-throttled — steady usage will exhaust it."
        else:
            flex_note = "Throttled — single shot, use it or accept losing it."
        if profile.burn_estimate:
            flex_note = f"{flex_note} ({profile.burn_estimate})"

    return (
        f"  {badge} {s.bold(provider_display_name(alert.provider))} · "
        f"{who} · {alert.window_label}: {alert.remaining_percent:.0f}% left · "
        f"use {when}{value_part}\n"
        f"      {s.dim(flex_note)}"
    )


def _throttled_waste_line(
    alert: UseOrLoseAlert,
    s: _Style,
    *,
    waking_hours_per_day: float = 16.0,
) -> str:
    who = alert.account or "default"
    profile = alert.flexibility_profile
    value_usd = profile.value_at_risk_usd if profile else None
    remaining = alert.remaining_percent

    if value_usd is not None and value_usd > 0.01 and alert.window_minutes:
        active_cycles = (waking_hours_per_day * DAYS_PER_MONTH * 60) / alert.window_minutes
        monthly_waste = value_usd * active_cycles
        return s.dim(
            f"  · {provider_display_name(alert.provider)} · {who} · "
            f"{alert.window_label}: {remaining:.0f}% left per cycle "
            f"(~${value_usd:.2f}/cycle ≈ ~${monthly_waste:.2f}/month wasted at this pace)"
        )
    return s.dim(
        f"  · {provider_display_name(alert.provider)} · {who} · {alert.window_label}: {remaining:.0f}% left per cycle"
    )


def _summary_alert_line(alert: UseOrLoseAlert, s: _Style) -> str:
    icon = URGENCY_ICON.get(alert.urgency, "   ")
    badge = s.urgency(alert.urgency, f"[{icon} {alert.urgency.value.upper():8}]")
    when = _human_deadline(alert.days_until_reset)
    who = alert.account or "default"
    return (
        f"    {badge} {s.bold(provider_display_name(alert.provider))} · {who} · "
        f"{alert.window_label}: {alert.remaining_percent:.0f}% left · use {when}"
    )


def _time_bucket(days: float | None) -> str:
    if days is None:
        return "later / unknown reset"
    if days <= 1:
        return "within 24 hours"
    if days <= 3:
        return "within 3 days"
    if days <= 7:
        return "within 7 days"
    if days <= 14:
        return "within 14 days"
    return "later / unknown reset"


def _human_deadline(days: float | None) -> str:
    if days is None:
        return "before the next reset (time unknown)"
    if days <= 0:
        return "immediately (reset imminent or past)"
    if days < 1:
        hours = max(1, int(round(days * 24)))
        return f"within ~{hours}h"
    if days < 2:
        return "within 1 day"
    return f"within {days:.1f} days"


def _sorted_accounts(accounts: list[AccountUsage]) -> list[AccountUsage]:
    return sorted(
        accounts,
        key=lambda a: (
            provider_display_name(a.provider).casefold(),
            (a.account or "").casefold(),
            a.source.casefold(),
        ),
    )


def _render_account(acc: AccountUsage, s: _Style, *, config: dict[str, Any] | None = None) -> list[str]:
    lines: list[str] = []
    cfg = config or {}
    raw_plans = cfg.get("plans")
    raw_analysis = cfg.get("analysis")
    plans: dict[str, Any] = raw_plans if isinstance(raw_plans, dict) else {}
    analysis: dict[str, Any] = raw_analysis if isinstance(raw_analysis, dict) else {}

    head = s.bold(provider_display_name(acc.provider))
    if acc.account:
        head += f" · account={acc.account}"
    if acc.plan:
        head += s.dim(f" · plan={acc.plan}")
    head += s.dim(f" · {_source_description(acc.source)}")
    lines.append(head)

    if acc.error:
        lines.append(s.red(f"  ERROR: {acc.error}"))

    if acc.balance_usd is not None:
        lines.append(f"  balance: {s.green(f'${acc.balance_usd:.2f}')}")
    if acc.credits_remaining is not None and acc.balance_usd is None:
        lines.append(f"  credits remaining: {acc.credits_remaining}")

    for w in acc.windows:
        rem = w.remaining()
        rem_s = f"{rem:.0f}% left" if rem is not None else "n/a"
        used_s = f"{w.used_percent:.0f}% used" if w.used_percent is not None else ""
        days = w.days_until_reset()
        if days is not None:
            reset_s = f"resets in {days:.1f}d ({_fmt_dt(w.resets_at)})"
        elif w.reset_description:
            reset_s = w.reset_description
        else:
            reset_s = "reset unknown"
        bar = _colored_bar(rem if rem is not None else 0, s)
        rem_padded = f"{rem_s:10}"
        rem_colored = rem_padded
        if rem is not None:
            if rem >= 70:
                rem_colored = s.yellow(rem_padded)
            elif rem >= 40:
                rem_colored = s.cyan(rem_padded)
            else:
                rem_colored = s.green(rem_padded)
        lines.append(f"  quota: {w.label}")
        lines.append(f"    {bar} {rem_colored} {used_s:10} {s.dim(reset_s)}")

        if rem is not None and w.window_minutes:
            detail = _consumption_line(w, rem, acc.provider, plans, analysis, s)
            if detail:
                lines.append(s.dim(f"    {detail}"))

    for note in acc.notes:
        lines.append(s.dim(f"  · {note}"))
    lines.append("")
    return lines


def _render_cross_checks(checks: list[CrossCheck], s: _Style) -> list[str]:
    lines: list[str] = []
    order = {"warning": 0, "unavailable": 1, "consistent": 2}
    for check in sorted(
        checks,
        key=lambda item: (
            order.get(item.status, 9),
            item.provider.casefold(),
            (item.account or "").casefold(),
        ),
    ):
        status = {
            "warning": s.red("WARNING"),
            "unavailable": s.yellow("UNAVAILABLE"),
            "consistent": s.green("CONSISTENT"),
        }.get(check.status, check.status.upper())
        subject = provider_display_name(check.provider)
        if check.account:
            subject += f" · account={check.account}"
        sources = " versus ".join(check.sources)
        lines.append(f"  [{status}] {s.bold(subject)} · {sources}")
        lines.append(f"    {check.message}")
    return lines


def _colored_bar(remaining_percent: float, s: _Style, width: int = 12) -> str:
    remaining_percent = max(0.0, min(100.0, remaining_percent))
    filled = int(round((remaining_percent / 100.0) * width))
    body = "=" * filled + "-" * (width - filled)
    bar = f"[{body}]"
    if remaining_percent >= 70:
        return s.yellow(bar)
    if remaining_percent >= 40:
        return s.cyan(bar)
    return s.green(bar)


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "?"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _source_description(source: str) -> str:
    return {
        "cswap": "canonical source: cswap",
        "codexbar": "selected live source: CodexBar",
        "tokscale": "selected live source: tokscale",
    }.get(source, f"source: {source}")


def _consumption_line(
    window: Any, remaining: float, provider: str, plans: dict[str, Any], analysis: dict[str, Any], s: _Style
) -> str | None:
    if not window.window_minutes:
        return None

    aliases = {"antigravity": "gemini", "opencode-go": "opencode"}
    provider_key = aliases.get(provider.lower().replace(" ", "-"), provider.lower().replace(" ", "-"))
    plan_meta: dict[str, Any] = {}
    meta = plans.get(provider_key)
    if isinstance(meta, dict):
        plan_meta = meta

    monthly_price = plan_meta.get("monthly_price")
    value_multipliers = plan_meta.get("value_multiplier")
    waking = float(analysis.get("waking_hours_per_day", 16))
    duration_kind = classify_window_minutes(window.window_minutes)

    flex_class, flex_score = _classify_flexibility(
        window_minutes=window.window_minutes, provider=provider, config=analysis
    )

    value_usd: float | None = None
    if monthly_price is not None and window.window_minutes:
        window_mult = 1.0
        if isinstance(value_multipliers, dict) and duration_kind:
            window_mult = float(value_multipliers.get(duration_kind, 1.0))
        value_usd = round(
            _compute_value_at_risk(
                remaining=remaining,
                window_minutes=window.window_minutes,
                monthly_price=float(monthly_price),
                waking_hours_per_day=waking,
                value_multiplier=window_mult,
            ),
            2,
        )

    flex_bar = "░" if flex_score <= 0.1 else "▓" if flex_score >= 0.9 else "▒"
    class_label = flex_class.value

    parts: list[str] = []
    if value_usd is not None:
        parts.append(f"${value_usd:.2f}")
    parts.append(f"flex:{flex_bar} {class_label}")

    capacity = window.refill_capacity
    capacity_unit = window.refill_capacity_unit
    if capacity is None and duration_kind:
        overrides_cfg = analysis.get("provider_overrides") or {}
        overrides = overrides_cfg if isinstance(overrides_cfg, dict) else {}
        prov_overrides = overrides.get(provider_key)
        if isinstance(prov_overrides, dict):
            window_overrides = prov_overrides.get(duration_kind)
            if isinstance(window_overrides, dict):
                capacity = window_overrides.get("refill_capacity")
                if capacity_unit is None:
                    capacity_unit = window_overrides.get("refill_capacity_unit")

    if capacity and window.window_minutes:
        unit = capacity_unit or ""
        parts.append(f"{capacity:.0f}{unit}/cycle")

    return " · ".join(parts)
