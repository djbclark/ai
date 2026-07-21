"""Human-readable terminal report (pretty by default)."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, TextIO

from ai_usage.models import (
    AccountUsage,
    Snapshot,
    SpendPeriod,
    Urgency,
    UseOrLoseAlert,
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
) -> str:
    s = _Style(use_color(force=color))
    lines: list[str] = []
    width = 72

    lines.append(s.bold("=" * width))
    lines.append(s.bold(s.cyan("AI USAGE — USE IT OR LOSE IT")))
    lines.append(s.dim(f"Collected at {snapshot.collected_at.isoformat()}"))
    lines.append(s.bold("=" * width))

    action = [a for a in alerts if a.urgency not in (Urgency.INFO, Urgency.NONE)]
    info = [a for a in alerts if a.urgency == Urgency.INFO]

    lines.append("")
    lines.append(s.bold("## Recommendations (use subscription allotment before reset)"))
    lines.append(s.dim("-" * width))
    if not action:
        lines.append(s.green("No high-priority use-or-lose windows found."))
        lines.append(
            s.dim(
                "(Either quotas are well-used, resets are far out, or live quota "
                "data is missing — see accounts below.)"
            )
        )
    else:
        for alert in action:
            icon = URGENCY_ICON.get(alert.urgency, "   ")
            days = (
                f"{alert.days_until_reset:.1f}d"
                if alert.days_until_reset is not None
                else "?"
            )
            badge = s.urgency(
                alert.urgency,
                f"[{icon} {alert.urgency.value.upper():8}]",
            )
            lines.append(
                f"{badge} "
                f"{s.bold(f'{alert.provider:14}')} {alert.window_label:12} "
                f"{alert.remaining_percent:5.0f}% left  reset in {days}"
            )
            lines.append(f"    {alert.message}")
            lines.append("")

    if info:
        lines.append(s.bold("## Notes (prepaid / non-expiring)"))
        lines.append(s.dim("-" * width))
        for alert in info:
            lines.append(s.dim(f"  - {alert.message}"))
        lines.append("")

    lines.append(s.bold("## Live accounts / quotas"))
    lines.append(s.dim("-" * width))
    for acc in _sorted_accounts(snapshot.accounts):
        lines.extend(_render_account(acc, s))

    if snapshot.spend_history:
        lines.append("")
        lines.append(s.bold("## Local spend history (ccusage, API-equivalent $)"))
        lines.append(s.dim("-" * width))
        lines.extend(_render_spend(snapshot.spend_history, s))

    if snapshot.collector_errors:
        lines.append("")
        lines.append(s.bold(s.red("## Collector errors")))
        lines.append(s.dim("-" * width))
        for err in snapshot.collector_errors:
            lines.append(s.red(f"  - {err}"))

    lines.append("")
    lines.append(_footer_tips(s))
    return "\n".join(lines)


def _sorted_accounts(accounts: list[AccountUsage]) -> list[AccountUsage]:
    return sorted(
        accounts,
        key=lambda a: (
            0 if a.error else 1,
            a.provider.lower(),
            (a.account or "").lower(),
            a.source,
        ),
    )


def _render_account(acc: AccountUsage, s: _Style) -> list[str]:
    lines: list[str] = []
    head = s.bold(acc.provider)
    if acc.account:
        head += f" · {acc.account}"
    if acc.plan:
        head += s.dim(f" · plan={acc.plan}")
    head += s.dim(f"  [{acc.source}]")
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
        rem_colored = rem_s
        if rem is not None:
            if rem >= 70:
                rem_colored = s.yellow(rem_s)
            elif rem >= 40:
                rem_colored = s.cyan(rem_s)
            else:
                rem_colored = s.green(rem_s)
        lines.append(
            f"  {w.label:12} {bar} {rem_colored:10} {used_s:10} {s.dim(reset_s)}"
        )

    for note in acc.notes:
        lines.append(s.dim(f"  · {note}"))
    lines.append("")
    return lines


def _render_spend(spend: list[SpendPeriod], s: _Style) -> list[str]:
    lines: list[str] = []
    rows = sorted(spend, key=lambda x: x.period)[-6:]
    for row in rows:
        agents = f" ({', '.join(row.agents)})" if row.agents else ""
        lines.append(
            f"  {row.period}:  {s.bold(f'${row.total_cost_usd:10,.2f}')}  "
            f"{row.total_tokens:>14,} tokens{s.dim(agents)}"
        )
    if len(rows) >= 2:
        last = rows[-1]
        prev = rows[-2]
        if prev.total_cost_usd > 0:
            delta = (
                (last.total_cost_usd - prev.total_cost_usd) / prev.total_cost_usd
            ) * 100
            delta_s = f"{delta:+.0f}%"
            if delta > 20:
                delta_s = s.yellow(delta_s)
            elif delta < -20:
                delta_s = s.green(delta_s)
            lines.append(
                f"  MoM change ({prev.period} → {last.period}): {delta_s}"
            )
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


def _footer_tips(s: _Style) -> str:
    tips = (
        "Tips:\n"
        "  • Subscription windows (weekly/monthly) expire unused — burn them on real work.\n"
        "  • Prepaid API balances usually roll; no rush unless a promo credit has an expiry.\n"
        "  • Fix cswap keychain / browser cookies if Claude/Cursor show errors.\n"
        "  • Re-run:  ai              (pretty human report, default)\n"
        "  • JSON:    ai --json       or  ai --format json\n"
        "  • Config:  copy config/services.example.yaml → config/services.yaml"
    )
    return s.dim(tips)
