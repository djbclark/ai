"""Collect live subscription/API quotas from codexbar."""

from __future__ import annotations

import re
from typing import Any

from ai_usage.models import AccountUsage, BillingKind, QuotaWindow, parse_dt

from .base import CollectorError, run_json, which

# Providers that are typically pure prepaid / API balance (not use-or-lose monthly)
PREPAID_HINTS = {
    "openrouter",
    "openai",
    "deepseek",
    "deepinfra",
    "groqcloud",
    "together",
    "fireworks",
}


def collect_codexbar(*, providers: str | list[str] = "all") -> list[AccountUsage]:
    if not which("codexbar"):
        raise CollectorError("codexbar not found on PATH")

    provider_list = _normalize_providers(providers)
    accounts: list[AccountUsage] = []
    errors: list[str] = []

    for provider_arg in provider_list:
        # --provider all is thorough but can take ~60s
        timeout = 180.0 if provider_arg in ("all", "both") else 90.0
        try:
            payload = run_json(
                [
                    "codexbar",
                    "usage",
                    "--format",
                    "json",
                    "--provider",
                    provider_arg,
                ],
                timeout=timeout,
            )
        except CollectorError as exc:
            errors.append(f"{provider_arg}: {exc}")
            continue
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            if isinstance(row, dict):
                accounts.append(_from_row(row))

    if not accounts and errors:
        raise CollectorError("; ".join(errors))
    if errors:
        # Surface partial failures as synthetic account notes via a single error account
        accounts.append(
            AccountUsage(
                source="codexbar",
                provider="partial-errors",
                error="; ".join(errors),
                billing_kind=BillingKind.UNKNOWN,
            )
        )
    return accounts


def _normalize_providers(providers: str | list[str]) -> list[str]:
    """codexbar accepts one --provider value (or all/both), not CSV."""
    if isinstance(providers, list):
        items = [str(p).strip() for p in providers if str(p).strip()]
    else:
        text = (providers or "all").strip()
        if text in ("all", "both"):
            return [text]
        items = [p.strip() for p in text.split(",") if p.strip()]
    return items or ["all"]


def _from_row(row: dict[str, Any]) -> AccountUsage:
    provider = str(row.get("provider") or "unknown").lower()
    source_tag = str(row.get("source") or "codexbar")
    err = row.get("error")
    if isinstance(err, dict):
        msg = err.get("message") or str(err)
        return AccountUsage(
            source="codexbar",
            provider=provider,
            error=str(msg),
            billing_kind=_billing_kind(provider, None),
            raw=row,
        )
    if isinstance(err, str):
        return AccountUsage(
            source="codexbar",
            provider=provider,
            error=err,
            billing_kind=_billing_kind(provider, None),
            raw=row,
        )

    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    account = (
        row.get("account")
        or usage.get("accountEmail")
        or (usage.get("identity") or {}).get("accountEmail")
    )
    plan = usage.get("loginMethod") or (usage.get("identity") or {}).get("loginMethod")

    windows: list[QuotaWindow] = []
    for key, label in (
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("tertiary", "Tertiary"),
    ):
        block = usage.get(key)
        if isinstance(block, dict):
            w = _window(label, block)
            if w:
                windows.append(w)

    # Provider-specific nested usage blobs
    for nested_key, label_prefix in (
        ("openRouterUsage", "OpenRouter"),
        ("openAIAPIUsage", "OpenAI API"),
    ):
        nested = usage.get(nested_key)
        if isinstance(nested, dict):
            if "usedPercent" in nested:
                windows.append(
                    QuotaWindow(
                        label=f"{label_prefix} usage",
                        used_percent=_f(nested.get("usedPercent")),
                        remaining_percent=(
                            max(0.0, 100.0 - float(nested["usedPercent"]))
                            if nested.get("usedPercent") is not None
                            else None
                        ),
                        raw=nested,
                    )
                )

    balance_usd = None
    credits_remaining = None
    notes: list[str] = []

    # Top-level credits object
    credits = row.get("credits")
    if isinstance(credits, dict) and credits.get("remaining") is not None:
        try:
            credits_remaining = float(credits["remaining"])
        except (TypeError, ValueError):
            pass

    # OpenRouter balance
    oru = usage.get("openRouterUsage")
    if isinstance(oru, dict):
        if oru.get("balance") is not None:
            balance_usd = _f(oru.get("balance"))
        if oru.get("totalCredits") is not None and oru.get("totalUsage") is not None:
            notes.append(
                f"credits ${float(oru['totalCredits']):.2f}, "
                f"used ${float(oru['totalUsage']):.2f}"
            )

    # OpenAI API daily series → sum recent cost as note
    oai = usage.get("openAIAPIUsage")
    if isinstance(oai, dict):
        daily = oai.get("daily") or []
        if isinstance(daily, list) and daily:
            total = sum(float(d.get("costUSD") or 0) for d in daily if isinstance(d, dict))
            notes.append(f"OpenAI API ~${total:.4f} over last {len(daily)} days (admin API)")

    # Codex reset credits
    crc = usage.get("codexResetCredits")
    if isinstance(crc, dict) and crc.get("availableCount") is not None:
        notes.append(f"limit-reset credits available: {crc['availableCount']}")

    if usage.get("dataConfidence"):
        notes.append(f"confidence={usage['dataConfidence']}")

    # Relabel primary/secondary using windowMinutes / reset description
    windows = [_relabel_window(w) for w in windows]

    billing = _billing_kind(provider, usage, windows)
    if billing == BillingKind.PREPAID_BALANCE and balance_usd is None and credits_remaining:
        balance_usd = credits_remaining

    # DeepSeek-style: usedPercent 0 with a balance string in resetDescription
    for w in windows:
        desc = (w.reset_description or "") + " " + str(w.raw.get("resetDescription") or "")
        if "$" in desc and balance_usd is None:
            m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", desc)
            if m:
                balance_usd = float(m.group(1))
                if billing == BillingKind.UNKNOWN:
                    billing = BillingKind.PREPAID_BALANCE

    return AccountUsage(
        source="codexbar",
        provider=provider,
        account=str(account) if account else None,
        plan=str(plan) if plan else None,
        billing_kind=billing,
        windows=windows,
        balance_usd=balance_usd,
        credits_remaining=credits_remaining,
        notes=notes + [f"fetch_source={source_tag}"],
        raw=row,
    )


def _window(label: str, block: dict[str, Any]) -> QuotaWindow | None:
    used = block.get("usedPercent")
    remaining = None
    if used is not None:
        remaining = max(0.0, 100.0 - float(used))
    resets = parse_dt(block.get("resetsAt") or block.get("resets_at"))
    if used is None and resets is None and not block.get("resetDescription"):
        return None
    return QuotaWindow(
        label=label,
        used_percent=_f(used),
        remaining_percent=remaining,
        resets_at=resets,
        window_minutes=block.get("windowMinutes") or block.get("window_minutes"),
        reset_description=block.get("resetDescription") or block.get("reset_description"),
        raw=block,
    )


def _relabel_window(w: QuotaWindow) -> QuotaWindow:
    """Map generic Primary/Secondary to human labels using duration."""
    if w.label not in ("Primary", "Secondary", "Tertiary"):
        return w
    minutes = w.window_minutes
    if minutes is None and w.resets_at is not None:
        # Infer from time-to-reset when window length is missing
        days = w.days_until_reset()
        if days is not None:
            if days <= 0.5:
                minutes = 300
            elif days <= 8:
                minutes = 10080
            elif days <= 40:
                minutes = 43200
    if minutes is None:
        return w
    if minutes <= 360:
        label = "5-hour"
    elif minutes <= 10080:
        label = "Weekly"
    elif minutes <= 44640:
        label = "Monthly"
    else:
        label = w.label
    return QuotaWindow(
        label=label,
        used_percent=w.used_percent,
        remaining_percent=w.remaining_percent,
        resets_at=w.resets_at,
        window_minutes=w.window_minutes or minutes,
        reset_description=w.reset_description,
        raw=w.raw,
    )


def _billing_kind(
    provider: str,
    usage: dict[str, Any] | None,
    windows: list[QuotaWindow] | None = None,
) -> BillingKind:
    p = provider.lower()
    if p in PREPAID_HINTS:
        return BillingKind.PREPAID_BALANCE
    if usage and usage.get("openRouterUsage"):
        return BillingKind.PREPAID_BALANCE
    if usage and usage.get("openAIAPIUsage"):
        return BillingKind.PAYG_API
    # Subscription-style windows with real reset times
    if windows and any(w.resets_at is not None for w in windows):
        return BillingKind.SUBSCRIPTION_WINDOW
    if usage and any(usage.get(k) for k in ("primary", "secondary", "tertiary")):
        # primary present but may be balance-only (DeepSeek)
        for key in ("primary", "secondary", "tertiary"):
            block = usage.get(key) if usage else None
            if isinstance(block, dict) and block.get("resetsAt"):
                return BillingKind.SUBSCRIPTION_WINDOW
        return BillingKind.UNKNOWN
    return BillingKind.UNKNOWN


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
