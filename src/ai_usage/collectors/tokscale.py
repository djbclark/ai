"""Collect subscription usage from tokscale (complementary to codexbar)."""

from __future__ import annotations

from typing import Any

from ai_usage.models import AccountUsage, BillingKind, QuotaWindow, parse_dt

from .base import CollectorError, run_json, which


def collect_tokscale() -> list[AccountUsage]:
    if not which("tokscale"):
        raise CollectorError("tokscale not found on PATH")

    payload = run_json(["tokscale", "usage", "--json"], timeout=120)
    rows = payload if isinstance(payload, list) else [payload]
    accounts: list[AccountUsage] = []
    for row in rows:
        if isinstance(row, dict):
            accounts.append(_from_row(row))
    return accounts


def _from_row(row: dict[str, Any]) -> AccountUsage:
    provider = str(row.get("provider") or "unknown")
    # Normalize for merge/dedupe with codexbar
    provider_key = provider.lower().replace(" ", "-")

    windows: list[QuotaWindow] = []
    for m in row.get("metrics") or []:
        if not isinstance(m, dict):
            continue
        used = m.get("used_percent")
        remaining = m.get("remaining_percent")
        if remaining is None and used is not None:
            remaining = max(0.0, 100.0 - float(used))
        windows.append(
            QuotaWindow(
                label=str(m.get("label") or "Quota"),
                used_percent=float(used) if used is not None else None,
                remaining_percent=float(remaining) if remaining is not None else None,
                resets_at=parse_dt(m.get("resets_at")),
                reset_description=m.get("remaining_label"),
                raw=m,
            )
        )

    notes: list[str] = []
    credit_status = row.get("credit_status")
    if isinstance(credit_status, dict):
        if credit_status.get("balance") is not None:
            notes.append(f"credit_balance={credit_status.get('balance')}")
        if credit_status.get("has_credits"):
            notes.append("has_credits=true")
        if credit_status.get("overage_limit_reached"):
            notes.append("overage_limit_reached")

    reset_credits = row.get("reset_credits")
    if isinstance(reset_credits, dict) and reset_credits.get("available_count") is not None:
        notes.append(f"reset_credits={reset_credits['available_count']}")

    return AccountUsage(
        source="tokscale",
        provider=provider_key,
        account=row.get("email"),
        plan=row.get("plan"),
        billing_kind=BillingKind.SUBSCRIPTION_WINDOW if windows else BillingKind.UNKNOWN,
        windows=windows,
        notes=notes,
        raw=row,
    )
