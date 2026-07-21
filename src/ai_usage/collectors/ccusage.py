"""Collect historical usage from ccusage (local agent logs)."""

from __future__ import annotations

from typing import Any

from ai_usage.models import AccountUsage, BillingKind, SpendPeriod

from .base import CollectorError, run_json, which


def collect_ccusage(*, offline: bool = True) -> tuple[list[AccountUsage], list[SpendPeriod]]:
    if not which("ccusage"):
        raise CollectorError("ccusage not found on PATH")

    base = ["ccusage", "--json"]
    if offline:
        base.append("--offline")

    monthly = run_json([*base, "monthly"], timeout=180)
    daily = run_json([*base, "daily", "--since", _first_of_month()], timeout=180)

    spend: list[SpendPeriod] = []
    for row in _monthly_rows(monthly):
        spend.append(
            SpendPeriod(
                period=str(row.get("period") or row.get("month") or "unknown"),
                total_cost_usd=float(row.get("totalCost") or 0),
                total_tokens=int(row.get("totalTokens") or 0),
                agents=list((row.get("metadata") or {}).get("agents") or []),
                models=list(row.get("modelsUsed") or []),
                source="ccusage",
            )
        )

    accounts: list[AccountUsage] = []
    current_month = _first_of_month()[:7]  # YYYY-MM
    current = next((s for s in spend if s.period == current_month), None)
    if current is None and spend:
        current = spend[-1]

    notes = [
        "Local log-based cost estimate (API-equivalent), not live subscription quota.",
        "Useful for burn rate; pair with codexbar/tokscale for remaining allotments.",
    ]
    if current:
        notes.append(
            f"This period ({current.period}): ~${current.total_cost_usd:,.2f} "
            f"across {current.total_tokens:,} tokens"
            + (f" via {', '.join(current.agents)}" if current.agents else "")
        )

    # Summarize recent daily burn for the current month.
    daily_costs = []
    for row in _daily_rows(daily):
        daily_costs.append(float(row.get("totalCost") or 0))
    if daily_costs:
        avg = sum(daily_costs) / len(daily_costs)
        notes.append(
            f"Recent daily average (local logs, {len(daily_costs)} days): "
            f"${avg:,.2f}/day"
        )

    accounts.append(
        AccountUsage(
            source="ccusage",
            provider="local-agents",
            account="all-detected",
            plan="historical",
            billing_kind=BillingKind.HISTORICAL,
            notes=notes,
            raw={"monthly_count": len(spend), "daily_days": len(daily_costs)},
        )
    )
    return accounts, spend


def _first_of_month() -> str:
    from datetime import date

    today = date.today()
    return f"{today.year:04d}-{today.month:02d}-01"


def _monthly_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        rows = payload.get("monthly") or payload.get("data") or []
        return [r for r in rows if isinstance(r, dict)]
    return []


def _daily_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        rows = payload.get("daily") or payload.get("data") or []
        return [r for r in rows if isinstance(r, dict)]
    return []
