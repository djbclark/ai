"""Human-readable terminal report."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_usage.models import (
    AccountUsage,
    Snapshot,
    SpendPeriod,
    Urgency,
    UseOrLoseAlert,
)

URGENCY_ORDER = [
    Urgency.CRITICAL,
    Urgency.HIGH,
    Urgency.MEDIUM,
    Urgency.LOW,
    Urgency.INFO,
]

URGENCY_ICON = {
    Urgency.CRITICAL: "!!!",
    Urgency.HIGH: "!! ",
    Urgency.MEDIUM: "!  ",
    Urgency.LOW: ".  ",
    Urgency.INFO: "i  ",
    Urgency.NONE: "   ",
}


def render_report(
    snapshot: Snapshot,
    alerts: list[UseOrLoseAlert],
    *,
    config: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("AI USAGE — USE IT OR LOSE IT")
    lines.append(f"Collected at {snapshot.collected_at.isoformat()}")
    lines.append("=" * 72)

    action = [a for a in alerts if a.urgency not in (Urgency.INFO, Urgency.NONE)]
    info = [a for a in alerts if a.urgency == Urgency.INFO]

    lines.append("")
    lines.append("## Recommendations (use subscription allotment before reset)")
    lines.append("-" * 72)
    if not action:
        lines.append("No high-priority use-or-lose windows found.")
        lines.append(
            "(Either quotas are well-used, resets are far out, or live quota "
            "data is missing — see accounts below.)"
        )
    else:
        for alert in action:
            icon = URGENCY_ICON.get(alert.urgency, "   ")
            days = (
                f"{alert.days_until_reset:.1f}d"
                if alert.days_until_reset is not None
                else "?"
            )
            lines.append(
                f"[{icon} {alert.urgency.value.upper():8}] "
                f"{alert.provider:14} {alert.window_label:12} "
                f"{alert.remaining_percent:5.0f}% left  reset in {days}"
            )
            lines.append(f"    {alert.message}")
            lines.append("")

    if info:
        lines.append("## Notes (prepaid / non-expiring)")
        lines.append("-" * 72)
        for alert in info:
            lines.append(f"  - {alert.message}")
        lines.append("")

    lines.append("## Live accounts / quotas")
    lines.append("-" * 72)
    for acc in _sorted_accounts(snapshot.accounts):
        lines.extend(_render_account(acc))

    if snapshot.spend_history:
        lines.append("")
        lines.append("## Local spend history (ccusage, API-equivalent $)")
        lines.append("-" * 72)
        lines.extend(_render_spend(snapshot.spend_history))

    if snapshot.collector_errors:
        lines.append("")
        lines.append("## Collector errors")
        lines.append("-" * 72)
        for err in snapshot.collector_errors:
            lines.append(f"  - {err}")

    lines.append("")
    lines.append(_footer_tips(config))
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


def _render_account(acc: AccountUsage) -> list[str]:
    lines: list[str] = []
    head = f"{acc.provider}"
    if acc.account:
        head += f" · {acc.account}"
    if acc.plan:
        head += f" · plan={acc.plan}"
    head += f"  [{acc.source}]"
    lines.append(head)

    if acc.error:
        lines.append(f"  ERROR: {acc.error}")

    if acc.balance_usd is not None:
        lines.append(f"  balance: ${acc.balance_usd:.2f}")
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
        bar = _bar(rem if rem is not None else 0)
        lines.append(f"  {w.label:12} {bar} {rem_s:10} {used_s:10} {reset_s}")

    for note in acc.notes:
        lines.append(f"  · {note}")
    lines.append("")
    return lines


def _render_spend(spend: list[SpendPeriod]) -> list[str]:
    lines: list[str] = []
    # Show last 6 months
    rows = sorted(spend, key=lambda s: s.period)[-6:]
    for s in rows:
        agents = f" ({', '.join(s.agents)})" if s.agents else ""
        lines.append(
            f"  {s.period}:  ${s.total_cost_usd:10,.2f}  "
            f"{s.total_tokens:>14,} tokens{agents}"
        )
    if len(rows) >= 2:
        last = rows[-1]
        prev = rows[-2]
        if prev.total_cost_usd > 0:
            delta = ((last.total_cost_usd - prev.total_cost_usd) / prev.total_cost_usd) * 100
            lines.append(
                f"  MoM change ({prev.period} → {last.period}): {delta:+.0f}%"
            )
    return lines


def _bar(remaining_percent: float, width: int = 12) -> str:
    remaining_percent = max(0.0, min(100.0, remaining_percent))
    filled = int(round((remaining_percent / 100.0) * width))
    return "[" + ("=" * filled) + ("-" * (width - filled)) + "]"


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "?"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _footer_tips(config: dict[str, Any] | None) -> str:
    return (
        "Tips:\n"
        "  • Subscription windows (weekly/monthly) expire unused — burn them on real work.\n"
        "  • Prepaid API balances usually roll; no rush unless a promo credit has an expiry.\n"
        "  • Fix cswap keychain / browser cookies if Claude/Cursor show errors.\n"
        "  • Re-run: python -m ai_usage   or   ai-usage\n"
        "  • JSON:   ai-usage --json\n"
        "  • Config: copy config/services.example.yaml → config/services.yaml"
    )
