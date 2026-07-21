"""Collect canonical, multi-account Claude Code quota status from cswap."""

from __future__ import annotations

from typing import Any

from ai.models import (
    AccountUsage,
    BillingKind,
    QuotaWindow,
    classify_window_minutes,
    parse_dt,
)
from ai.models import coerce_float as _number
from ai.models import coerce_int as _int_or_none

from .base import CollectorError, run_json, which


def collect_cswap() -> list[AccountUsage]:
    if not which("cswap"):
        raise CollectorError("cswap not found on PATH")

    data = run_json(["cswap", "list", "--json"], timeout=60)
    if not isinstance(data, dict):
        raise CollectorError("unexpected cswap list JSON shape")
    if isinstance(data.get("error"), dict):
        raise CollectorError(str(data["error"].get("message") or data["error"]))
    if data.get("schemaVersion") not in (None, 1):
        raise CollectorError(f"unsupported cswap JSON schema version: {data.get('schemaVersion')}")

    accounts: list[AccountUsage] = []
    for item in data.get("accounts") or []:
        if isinstance(item, dict):
            accounts.append(_account_from_item(item, data.get("activeAccountNumber")))
    if not accounts:
        accounts.append(
            AccountUsage(
                source="cswap",
                provider="claude",
                error="cswap has no registered Claude Code accounts",
                billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
            )
        )
    return accounts


def _account_from_item(item: dict[str, Any], active_number: Any) -> AccountUsage:
    email = item.get("email")
    number = item.get("number")
    active = bool(item.get("active")) or number == active_number
    usage_status = str(item.get("usageStatus") or "unavailable")
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else None

    windows: list[QuotaWindow] = []
    notes: list[str] = [f"cswap slot {number}" + ("; active" if active else "")]
    error: str | None = None
    billing_kind = BillingKind.SUBSCRIPTION_WINDOW

    if item.get("alias"):
        notes.append(f"cswap alias: {item['alias']}")
    if item.get("disabled"):
        notes.append("This Claude Code account is disabled in cswap rotation.")
    if item.get("organizationName"):
        notes.append(f"Claude organization: {item['organizationName']}")
    if item.get("usageFetchedAt"):
        freshness = f"Quota fetched at {item['usageFetchedAt']}"
        if item.get("usageAgeSeconds") is not None:
            freshness += f" ({float(item['usageAgeSeconds']):.0f}s old)"
        notes.append(freshness + ".")

    if usage_status != "ok":
        if usage_status == "api_key":
            billing_kind = BillingKind.PAYG_API
            notes.append("API-key account: cswap reports no Claude subscription quota.")
        else:
            detail = {
                "keychain_unavailable": "the macOS Keychain could not be read",
                "no_credentials": "this cswap slot has no readable credentials",
                "token_expired": "the active Claude token is expired",
                "relogin_required": "Claude login is required again",
                "unavailable": "live Claude quota could not be fetched",
            }.get(usage_status, f"cswap returned status {usage_status}")
            error = f"Canonical Claude usage unavailable: {detail}."

    if usage:
        windows.extend(_named_window(usage, ("fiveHour", "five_hour"), "Claude Code 5-hour"))
        windows.extend(_named_window(usage, ("sevenDay", "seven_day", "weekly"), "Claude Code weekly"))
        windows.extend(_named_window(usage, ("monthly",), "Claude Code monthly"))

        for index, key in enumerate(("primary", "secondary", "tertiary"), start=1):
            block = usage.get(key)
            if not isinstance(block, dict):
                continue
            label = _generic_label(block, index)
            window = _window_from_block(label, block)
            if window and not _same_window_present(windows, window):
                windows.append(window)

        scoped = usage.get("scoped")
        if isinstance(scoped, list):
            for block in scoped:
                if not isinstance(block, dict):
                    continue
                model_name = str(block.get("name") or "unnamed model")
                window = _window_from_block(f"Claude Code weekly — {model_name}", block)
                if window and not _same_window_present(windows, window):
                    windows.append(window)

        spend = usage.get("spend")
        if isinstance(spend, dict):
            used = _number(spend.get("used"))
            limit = _number(spend.get("limit"))
            currency = str(spend.get("currency") or "currency units")
            if used is not None and limit is not None:
                notes.append(f"Current Claude pay-as-you-go spend limit: {used:g} of {limit:g} {currency}.")

    account_name = str(email) if email else f"cswap-slot-{number}"
    return AccountUsage(
        source="cswap",
        provider="claude",
        account=account_name,
        billing_kind=billing_kind,
        windows=windows,
        error=error,
        notes=notes,
        raw=item,
    )


def _named_window(usage: dict[str, Any], keys: tuple[str, ...], label: str) -> list[QuotaWindow]:
    for key in keys:
        block = usage.get(key)
        if isinstance(block, dict):
            window = _window_from_block(label, block)
            return [window] if window else []
        if isinstance(block, (int, float)):
            return [QuotaWindow(label=label, used_percent=float(block))]
    return []


def _window_from_block(label: str, block: dict[str, Any]) -> QuotaWindow | None:
    # cswap schema v1 uses `pct`; the other spellings keep compatibility with
    # older/future adapters without weakening cswap's authority.
    used = _number(
        block.get("pct")
        if block.get("pct") is not None
        else block.get("usedPercent")
        if block.get("usedPercent") is not None
        else block.get("utilization")
    )
    if used is None and "used" in block and "limit" in block:
        raw_used = _number(block.get("used"))
        limit = _number(block.get("limit"))
        if raw_used is not None and limit is not None and limit > 0:
            used = (raw_used / limit) * 100

    remaining = _number(block.get("remainingPercent"))
    if remaining is None and used is not None:
        remaining = max(0.0, 100.0 - used)

    resets = parse_dt(block.get("resetsAt") or block.get("resets_at") or block.get("resetAt") or block.get("reset_at"))
    description = block.get("countdown") or block.get("resetDescription") or block.get("reset_description")
    if used is None and remaining is None and resets is None and not description:
        return None
    return QuotaWindow(
        label=label,
        used_percent=used,
        remaining_percent=remaining,
        resets_at=resets,
        window_minutes=_int_or_none(block.get("windowMinutes") or block.get("window_minutes")),
        reset_description=description,
        raw=block,
    )


def _generic_label(block: dict[str, Any], index: int) -> str:
    minutes = _int_or_none(block.get("windowMinutes") or block.get("window_minutes"))
    kind = classify_window_minutes(minutes)
    if kind == "5h":
        return "Claude Code 5-hour"
    if kind == "weekly":
        return "Claude Code weekly"
    if kind == "monthly":
        return "Claude Code monthly"
    return f"Claude Code quota {index} (unnamed by cswap)"


def _same_window_present(windows: list[QuotaWindow], candidate: QuotaWindow) -> bool:
    return any(window.same_measurement(candidate) for window in windows)
