"""Detect monthly/weekly subscription allotments that will expire unused."""

from __future__ import annotations

from typing import Any

from ai_usage.models import (
    AccountUsage,
    BillingKind,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
    utcnow,
)

# Windows shorter than this are rate-limits, not "monthly plan waste"
SHORT_WINDOW_LABELS = {"5-hour", "5h", "session", "hourly"}


def analyze_use_or_lose(
    snapshot: Snapshot,
    config: dict[str, Any] | None = None,
) -> list[UseOrLoseAlert]:
    cfg = (config or {}).get("analysis") or {}
    min_remaining = float(cfg.get("min_remaining_percent", 40))
    max_days = float(cfg.get("max_days_until_reset", 14))
    urgent_remaining = float(cfg.get("urgent_remaining_percent", 70))
    urgent_days = float(cfg.get("urgent_days_until_reset", 7))
    plans = (config or {}).get("plans") or {}

    now = utcnow()
    alerts: list[UseOrLoseAlert] = []
    seen: set[tuple[str, str, str]] = set()

    for account in snapshot.accounts:
        if account.error and not account.windows:
            continue
        if account.billing_kind in (BillingKind.PAYG_API, BillingKind.HISTORICAL):
            continue
        if account.billing_kind == BillingKind.PREPAID_BALANCE:
            # Prepaid usually rolls; only note large idle balances as INFO
            if account.balance_usd is not None and account.balance_usd >= 10:
                alerts.append(
                    UseOrLoseAlert(
                        urgency=Urgency.INFO,
                        provider=account.provider,
                        account=account.account,
                        window_label="prepaid balance",
                        remaining_percent=100.0,
                        days_until_reset=None,
                        plan=account.plan,
                        estimated_plan_value_usd=account.balance_usd,
                        message=(
                            f"{account.provider}: ${account.balance_usd:.2f} prepaid "
                            "balance (usually does not expire — spend when useful, "
                            "not urgent like subscription windows)."
                        ),
                        source=account.source,
                        score=5.0,
                    )
                )
            continue

        plan_meta = _plan_meta(account.provider, plans)
        plan_value = plan_meta.get("monthly_usd")

        for window in account.windows:
            if _is_short_window(window.label):
                # Still flag 5h if nearly full and you have alternate accounts idle
                continue

            remaining = window.remaining()
            if remaining is None:
                continue
            days = window.days_until_reset(now)

            # Skip fully used windows
            if remaining < min_remaining:
                continue
            # Skip far-away resets (unless remaining is extremely high and monthly)
            if days is not None and days > max_days:
                if remaining < 90 or not _looks_monthly(window.label):
                    continue

            key = (
                account.provider.lower(),
                (account.account or "").lower(),
                window.label.lower(),
            )
            # Prefer codexbar over tokscale when both report same window
            if key in seen:
                continue
            seen.add(key)

            urgency, score = _score(
                remaining=remaining,
                days=days,
                urgent_remaining=urgent_remaining,
                urgent_days=urgent_days,
                min_remaining=min_remaining,
                plan_value=plan_value,
                label=window.label,
            )
            if urgency == Urgency.NONE:
                continue

            message = _message(
                account=account,
                window_label=window.label,
                remaining=remaining,
                days=days,
                plan_value=plan_value,
                plan_notes=plan_meta.get("notes"),
            )
            alerts.append(
                UseOrLoseAlert(
                    urgency=urgency,
                    provider=account.provider,
                    account=account.account,
                    window_label=window.label,
                    remaining_percent=remaining,
                    days_until_reset=days,
                    plan=account.plan or plan_meta.get("name"),
                    estimated_plan_value_usd=float(plan_value) if plan_value else None,
                    message=message,
                    source=account.source,
                    score=score,
                )
            )

        # Multi-account Claude: if one account is idle, surface it
        if account.source == "cswap" and not account.windows and account.error:
            alerts.append(
                UseOrLoseAlert(
                    urgency=Urgency.MEDIUM,
                    provider="claude",
                    account=account.account,
                    window_label="unknown (usage unavailable)",
                    remaining_percent=100.0,
                    days_until_reset=None,
                    plan=account.plan,
                    estimated_plan_value_usd=float(plan_value) if plan_value else None,
                    message=(
                        f"Claude account {account.account}: live quota unavailable "
                        f"({account.error}). If this seat is paid monthly, re-auth "
                        "cswap so we can tell whether unused allotment is about to reset."
                    ),
                    source="cswap",
                    score=40.0,
                )
            )

    alerts.sort(key=lambda a: (-a.score, a.provider, a.window_label))
    return alerts


def _is_short_window(label: str) -> bool:
    low = label.lower().strip()
    if low in SHORT_WINDOW_LABELS:
        return True
    if "5-hour" in low or "5 hour" in low or "5h" in low:
        return True
    return False


def _looks_monthly(label: str) -> bool:
    low = label.lower()
    return "month" in low or "billing" in low


def _plan_meta(provider: str, plans: dict[str, Any]) -> dict[str, Any]:
    key = provider.lower().replace(" ", "-")
    # common aliases
    aliases = {
        "chatgpt": "codex",
        "codex": "codex",
        "openai-codex": "codex",
        "grok-build": "grok",
        "supergrok": "grok",
        "github-copilot": "copilot",
        "antigravity": "gemini",
        "google-ai-pro": "gemini",
        "opencode-go": "opencode",
        "opencodego": "opencode",
        "opencode": "opencode",
    }
    lookup = aliases.get(key, key)
    meta = plans.get(lookup) or plans.get(provider) or {}
    return meta if isinstance(meta, dict) else {}


def _score(
    *,
    remaining: float,
    days: float | None,
    urgent_remaining: float,
    urgent_days: float,
    min_remaining: float,
    plan_value: Any,
    label: str,
) -> tuple[Urgency, float]:
    # Base score from remaining fraction that would be wasted
    score = remaining

    # Time pressure
    if days is not None:
        if days <= 1:
            score += 40
        elif days <= 3:
            score += 30
        elif days <= 7:
            score += 20
        elif days <= 14:
            score += 10
        else:
            score += 2
    else:
        score += 5  # unknown reset — still interesting if high remaining

    # Monthly windows weigh more than weekly (bigger $ bucket typically)
    if _looks_monthly(label):
        score += 15
    elif "week" in label.lower() or "7" in label.lower():
        score += 8

    if plan_value:
        try:
            score += min(30.0, float(plan_value) / 2.0)
        except (TypeError, ValueError):
            pass

    if remaining >= urgent_remaining and (days is None or days <= urgent_days):
        urgency = Urgency.CRITICAL if (days is not None and days <= 3) or remaining >= 90 else Urgency.HIGH
    elif remaining >= min_remaining and (days is None or days <= 14):
        urgency = Urgency.MEDIUM if remaining >= 50 else Urgency.LOW
    else:
        urgency = Urgency.NONE

    return urgency, score


def _message(
    *,
    account: AccountUsage,
    window_label: str,
    remaining: float,
    days: float | None,
    plan_value: Any,
    plan_notes: Any,
) -> str:
    who = account.account or "default"
    plan = account.plan or "subscription"
    time_part = (
        f"resets in {days:.1f} day(s)"
        if days is not None
        else "reset time unknown"
    )
    waste = ""
    if plan_value:
        try:
            est = float(plan_value) * (remaining / 100.0)
            waste = f" Roughly ~${est:.0f} of a ${float(plan_value):.0f}/mo plan is still unused."
        except (TypeError, ValueError):
            waste = ""
    note = f" {plan_notes}" if plan_notes else ""
    return (
        f"Use {account.provider} ({who}, {plan}) soon: "
        f"{remaining:.0f}% of the {window_label} window remains and {time_part}."
        f"{waste}{note}"
    )
