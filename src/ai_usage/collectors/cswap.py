"""Collect multi-account Claude status from cswap."""

from __future__ import annotations

from typing import Any

from ai_usage.models import AccountUsage, BillingKind, QuotaWindow, parse_dt

from .base import CollectorError, run_json, which


def collect_cswap() -> list[AccountUsage]:
    if not which("cswap"):
        raise CollectorError("cswap not found on PATH")

    data = run_json(["cswap", "list", "--json"], timeout=60)
    if not isinstance(data, dict):
        raise CollectorError("unexpected cswap list JSON shape")

    accounts: list[AccountUsage] = []
    for item in data.get("accounts") or []:
        if not isinstance(item, dict):
            continue
        accounts.append(_account_from_item(item, data.get("activeAccountNumber")))
    if not accounts:
        accounts.append(
            AccountUsage(
                source="cswap",
                provider="claude",
                error="no accounts registered with cswap",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
            )
        )
    return accounts


def _account_from_item(item: dict[str, Any], active_number: Any) -> AccountUsage:
    email = item.get("email")
    number = item.get("number")
    active = bool(item.get("active")) or number == active_number
    usage_status = item.get("usageStatus")
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else None

    windows: list[QuotaWindow] = []
    notes: list[str] = []
    plan = None
    error = None

    if usage_status and usage_status not in ("ok", "available", None):
        notes.append(f"usageStatus={usage_status}")
        if usage_status in ("keychain_unavailable", "no_credentials"):
            error = (
                f"Could not read live Claude usage ({usage_status}). "
                "Unlock keychain / re-auth this cswap slot for quota windows."
            )

    if usage:
        plan = usage.get("plan") or usage.get("subscription") or usage.get("tier")
        for key, label in (
            ("fiveHour", "5-hour"),
            ("five_hour", "5-hour"),
            ("session", "5-hour"),
            ("weekly", "Weekly"),
            ("sevenDay", "7-day"),
            ("seven_day", "7-day"),
            ("monthly", "Monthly"),
            ("primary", "Primary"),
            ("secondary", "Secondary"),
            ("tertiary", "Tertiary"),
        ):
            block = usage.get(key)
            if isinstance(block, dict):
                w = _window_from_block(label, block)
                if w:
                    windows.append(w)
            elif isinstance(block, (int, float)):
                # bare percent used
                windows.append(
                    QuotaWindow(label=label, used_percent=float(block))
                )

        # Nested utilization objects sometimes used by Claude-style APIs
        util = usage.get("utilization") or usage.get("rateLimit") or {}
        if isinstance(util, dict):
            for key, label in (
                ("five_hour", "5-hour"),
                ("seven_day", "7-day"),
                ("weekly", "Weekly"),
            ):
                block = util.get(key)
                if isinstance(block, dict):
                    w = _window_from_block(label, block)
                    if w and not any(x.label == label for x in windows):
                        windows.append(w)

    notes.append(f"slot={number}" + (" (active)" if active else ""))
    org = item.get("organizationName")
    if org:
        notes.append(f"org={org}")

    return AccountUsage(
        source="cswap",
        provider="claude",
        account=str(email) if email else f"slot-{number}",
        plan=str(plan) if plan else None,
        billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
        windows=windows,
        error=error,
        notes=notes,
        raw=item,
    )


def _window_from_block(label: str, block: dict[str, Any]) -> QuotaWindow | None:
    used = block.get("usedPercent")
    if used is None:
        used = block.get("utilization")
    if used is None and "used" in block and "limit" in block:
        try:
            limit = float(block["limit"])
            used = (float(block["used"]) / limit) * 100 if limit else 0
        except (TypeError, ValueError, ZeroDivisionError):
            used = None
    remaining = block.get("remainingPercent")
    if remaining is None and used is not None:
        try:
            remaining = max(0.0, 100.0 - float(used))
        except (TypeError, ValueError):
            remaining = None

    resets = parse_dt(
        block.get("resetsAt")
        or block.get("resets_at")
        or block.get("resetAt")
        or block.get("reset_at")
    )
    if used is None and remaining is None and resets is None:
        return None
    return QuotaWindow(
        label=label,
        used_percent=float(used) if used is not None else None,
        remaining_percent=float(remaining) if remaining is not None else None,
        resets_at=resets,
        window_minutes=block.get("windowMinutes") or block.get("window_minutes"),
        reset_description=block.get("resetDescription") or block.get("reset_description"),
        raw=block,
    )
