"""Detect monthly/weekly subscription allotments that will expire unused."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ai.models import (
    WINDOW_5H_MAX_MINUTES,
    AccountUsage,
    BillingKind,
    FlexibilityClass,
    FlexibilityProfile,
    QuotaWindow,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
    classify_window_minutes,
    provider_display_name,
    utcnow,
)

# Windows shorter than this are rate-limits, not "monthly plan waste"
SHORT_WINDOW_LABELS = {"5-hour", "5h", "session", "hourly"}

DAYS_PER_MONTH = 30.44
MINUTES_PER_MONTH = DAYS_PER_MONTH * 24 * 60

# Default burn-rate assumptions
_DEFAULT_MAX_TOKENS_PER_MINUTE = 200000
_DEFAULT_MAX_REQUESTS_PER_MINUTE = 0.5
_DEFAULT_MAX_USD_PER_MINUTE = 0.05
_DEFAULT_WAKING_HOURS = 16


def _compute_value_at_risk(
    *,
    remaining: float,
    window_minutes: int,
    monthly_price: float,
    waking_hours_per_day: float,
    value_multiplier: float = 1.0,
) -> float:
    active_minutes_per_month = waking_hours_per_day * DAYS_PER_MONTH * 60
    if active_minutes_per_month <= 0 or window_minutes <= 0:
        return 0.0
    active_cycles = active_minutes_per_month / window_minutes
    value_per_refill = monthly_price / active_cycles
    return value_per_refill * (remaining / 100.0) * value_multiplier


def _classify_flexibility(
    *,
    window_minutes: int | None,
    provider: str,
    config: dict[str, Any],
) -> tuple[FlexibilityClass, float]:
    duration_kind = classify_window_minutes(window_minutes)
    defaults_cfg = config.get("consumption_flexibility_defaults") or {}
    defaults = defaults_cfg if isinstance(defaults_cfg, dict) else {}
    overrides_cfg = config.get("provider_overrides") or {}
    overrides = overrides_cfg if isinstance(overrides_cfg, dict) else {}

    flex = None
    provider_key = provider.lower().replace(" ", "-")

    if provider_key in overrides and duration_kind:
        prov_overrides = overrides[provider_key]
        if isinstance(prov_overrides, dict) and duration_kind in prov_overrides:
            per_window = prov_overrides[duration_kind]
            if isinstance(per_window, dict) and "flexibility" in per_window:
                flex = float(per_window["flexibility"])
    if flex is None and duration_kind:
        raw = defaults.get(duration_kind)
        flex = float(raw) if raw is not None else None
    if flex is None:
        flex = 0.5

    flex = max(0.0, min(1.0, flex))
    if flex >= 0.9:
        return FlexibilityClass.BURSTABLE, flex
    if flex >= 0.4:
        return FlexibilityClass.SEMI_THROTTLED, flex
    return FlexibilityClass.THROTTLED, flex


def _compute_flexibility_profile(
    *,
    window: QuotaWindow,
    provider: str,
    config: dict[str, Any],
    monthly_price: float | None,
    value_multiplier: float = 1.0,
    now: Any | None = None,
) -> FlexibilityProfile | None:
    remaining = window.remaining()
    if remaining is None:
        return None

    cfg = config or {}
    waking = float(cfg.get("waking_hours_per_day", _DEFAULT_WAKING_HOURS))
    flex_class, flex_score = _classify_flexibility(window_minutes=window.window_minutes, provider=provider, config=cfg)

    value_usd: float | None = None
    if monthly_price is not None and window.window_minutes:
        value_usd = round(
            _compute_value_at_risk(
                remaining=remaining,
                window_minutes=window.window_minutes,
                monthly_price=monthly_price,
                waking_hours_per_day=waking,
                value_multiplier=value_multiplier,
            ),
            2,
        )

    cycles_needed: int | None = None
    earliest: Any | None = None
    burn_minutes: float | None = None

    capacity = window.refill_capacity
    capacity_unit = window.refill_capacity_unit
    if capacity is not None and capacity > 0 and window.window_minutes:
        cycles_needed = max(1, int(round((remaining / 100.0) * capacity / capacity)))
        if capacity_unit == "tokens":
            rate = float(cfg.get("max_sustained_tokens_per_minute", _DEFAULT_MAX_TOKENS_PER_MINUTE))
        elif capacity_unit == "requests":
            rate = float(cfg.get("max_requests_per_minute", _DEFAULT_MAX_REQUESTS_PER_MINUTE))
        elif capacity_unit == "usd":
            rate = float(cfg.get("max_usd_per_minute", _DEFAULT_MAX_USD_PER_MINUTE))
        else:
            rate = 1.0
        burn_minutes = capacity / max(rate, 0.001)
        burn_minutes = round(burn_minutes, 1)

        now_dt = now or utcnow()
        if window.resets_at and isinstance(window.resets_at, type(now_dt)):
            earliest = window.resets_at - timedelta(minutes=cycles_needed * window.window_minutes)

    burn_text = _burn_estimate_text(
        burn_minutes=burn_minutes,
        capacity_unit=capacity_unit,
        cycles_needed=cycles_needed,
    )

    return FlexibilityProfile(
        flexibility_class=flex_class,
        consumption_flexibility=flex_score,
        value_at_risk_usd=value_usd,
        cycles_needed=cycles_needed,
        earliest_start_calendar=earliest if isinstance(earliest, type(utcnow())) else None,
        effective_burn_minutes=burn_minutes,
        burn_estimate=burn_text,
    )


def _burn_estimate_text(
    *,
    burn_minutes: float | None,
    capacity_unit: str | None,
    cycles_needed: int | None,
) -> str | None:
    if burn_minutes is None:
        return None
    if capacity_unit == "requests":
        if burn_minutes < 60:
            return f"~{burn_minutes:.0f} min of focused use"
        return f"~{burn_minutes / 60:.1f}h of focused use"
    if burn_minutes < 60:
        return f"~{burn_minutes:.0f} min at typical pace"
    if burn_minutes < 180:
        return f"~{burn_minutes / 60:.1f}h at typical pace"
    sessions = max(1, (cycles_needed or 1))
    return f"~{burn_minutes / 60:.1f}h across {sessions} session(s)"


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
    analysis_cfg = cfg
    multi_dim = bool(analysis_cfg.get("use_multi_dim_scoring", False))
    min_value_usd = float(analysis_cfg.get("min_value_at_risk_usd", 0.50))
    min_value_fraction = float(analysis_cfg.get("min_value_fraction", 0.05))

    for account in snapshot.accounts:
        if account.error and not account.windows:
            continue
        if account.billing_kind == BillingKind.PAYG_API:
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
        monthly_price = plan_meta.get("monthly_price")
        value_multipliers = plan_meta.get("value_multiplier")

        for window in account.windows:
            if not multi_dim and _is_short_window(window):
                continue

            remaining = window.remaining()
            if remaining is None:
                continue
            days = window.days_until_reset(now)

            # Deadlines in the past are not actionable
            if days is not None and days <= 0:
                continue

            key = (
                account.provider.lower(),
                (account.account or "").lower(),
                f"{window.label.lower()}|{window.resets_at.isoformat() if window.resets_at else ''}",
            )
            if key in seen:
                continue
            seen.add(key)

            duration_kind = classify_window_minutes(window.window_minutes)
            window_value_mult = 1.0
            if isinstance(value_multipliers, dict) and duration_kind:
                window_value_mult = float(value_multipliers.get(duration_kind, 1.0))

            flex_profile = _compute_flexibility_profile(
                window=window,
                provider=account.provider,
                config=analysis_cfg,
                monthly_price=monthly_price,
                value_multiplier=window_value_mult,
                now=now,
            )

            if multi_dim:
                if flex_profile is None:
                    continue

                urgency, score = _score_multi_dimension(
                    profile=flex_profile,
                    remaining=remaining,
                    days=days,
                    config=config,
                )

                value_usd = flex_profile.value_at_risk_usd
                plan_price = float(monthly_price or 0)

                if urgency in (Urgency.NONE,):
                    continue
                if value_usd is not None:
                    if value_usd < min_value_usd:
                        if plan_price > 0 and (value_usd / plan_price) < min_value_fraction:
                            continue
                        elif plan_price <= 0:
                            continue
                    elif plan_price > 0 and (value_usd / plan_price) < min_value_fraction:
                        if urgency in (Urgency.INFO, Urgency.LOW):
                            continue
                if urgency == Urgency.INFO and value_usd is not None and value_usd < min_value_usd:
                    continue
            else:
                if days is None:
                    continue
                if remaining < min_remaining:
                    continue
                if days > max_days:
                    continue

                urgency, score = _score(
                    remaining=remaining,
                    days=days,
                    urgent_remaining=urgent_remaining,
                    urgent_days=urgent_days,
                    min_remaining=min_remaining,
                    label=window.label,
                    max_days=max_days,
                )
                if urgency == Urgency.NONE:
                    continue

            message = _message(
                account=account,
                window_label=window.label,
                remaining=remaining,
                days=days,
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
                    message=message,
                    source=account.source,
                    score=score,
                    flexibility_profile=flex_profile,
                )
            )
    alerts.sort(key=lambda a: (-a.score, a.provider.casefold(), a.window_label.casefold()))
    return alerts


def _is_short_window(window: QuotaWindow) -> bool:
    if window.window_minutes is not None and window.window_minutes <= WINDOW_5H_MAX_MINUTES:
        return True
    low = window.label.lower().strip()
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
    # By the time an account reaches here, runner.py's _canonical_provider has already
    # rewritten raw collector slugs (chatgpt, grok-build, github-copilot, ...) to their
    # canonical provider name. This maps canonical provider -> plans.yaml config key,
    # for the providers whose config key differs from the canonical provider name.
    aliases = {
        "antigravity": "gemini",
        "opencode-go": "opencode",
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
    label: str,
    max_days: float,
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

    # Longer-lived quotas are generally more important than short refill windows.
    if _looks_monthly(label):
        score += 15
    elif "week" in label.lower() or "7" in label.lower():
        score += 8

    if remaining >= urgent_remaining and days is not None and days <= urgent_days:
        urgency = Urgency.CRITICAL if days <= 3 or remaining >= 90 else Urgency.HIGH
    elif remaining >= min_remaining and days is not None and days <= max_days:
        urgency = Urgency.MEDIUM if remaining >= 50 else Urgency.LOW
    else:
        urgency = Urgency.NONE

    return urgency, score


def _redistribute_weights(flexibility: float) -> tuple[float, float, float]:
    base_value = 0.35
    base_flex = 0.30
    base_deadline = 0.35

    redistributed = base_flex * flexibility
    w_flex = base_flex - redistributed
    w_value = base_value + redistributed * 0.50
    w_deadline = base_deadline + redistributed * 0.50

    return (w_value, w_flex, w_deadline)


def _score_multi_dimension(
    *,
    profile: FlexibilityProfile,
    remaining: float,
    days: float | None,
    config: dict[str, Any] | None = None,
) -> tuple[Urgency, float]:
    cfg = config or {}
    raw_plans = cfg.get("plans")
    plans_cfg: dict[str, Any] = raw_plans if isinstance(raw_plans, dict) else {}

    if remaining < 1.0:
        return Urgency.NONE, 0.0

    max_plan_price = 20.0
    for plan in plans_cfg.values():
        if isinstance(plan, dict):
            price = plan.get("monthly_price")
            if isinstance(price, (int, float)) and price > max_plan_price:
                max_plan_price = float(price)

    flex = profile.consumption_flexibility

    # --- value_urgency (0-100) ---
    value_urgency = 0.0
    if profile.value_at_risk_usd is not None and max_plan_price > 0:
        value_urgency = max(0.0, min(100.0, (profile.value_at_risk_usd / max_plan_price) * 100))

    # --- flexibility_urgency (0-100) ---
    flexibility_urgency = 0.0
    if flex >= 0.9:
        flexibility_urgency = 0.0
    elif flex >= 0.4:
        flexibility_urgency = 30.0 * (1.0 - flex) + 10.0
    else:
        if profile.earliest_start_calendar is not None:
            now = utcnow()
            remaining_sec = profile.earliest_start_calendar.timestamp() - now.timestamp()
            total_sec = 3600.0
            if days is not None and days > 0:
                total_sec = days * 86400.0
            if remaining_sec <= 0:
                flexibility_urgency = 100.0
            else:
                ratio = max(0.0, min(1.0, remaining_sec / total_sec))
                flexibility_urgency = 60.0 + 40.0 * (1.0 - ratio)
        elif flex < 0.1:
            flexibility_urgency = 30.0
        else:
            flexibility_urgency = 15.0

    # --- deadline_urgency (0-100) ---
    deadline_urgency = 0.0
    if days is not None:
        if days <= 0.5:
            raw = 100.0
        elif days <= 1:
            raw = 80.0
        elif days <= 3:
            raw = 60.0
        elif days <= 7:
            raw = 40.0
        elif days <= 14:
            raw = 20.0
        else:
            raw = 5.0
        deadline_urgency = max(0.0, min(100.0, raw * (0.5 + flex * 0.5)))

    # --- composite ---
    w_value, w_flex, w_deadline = _redistribute_weights(flex)
    score = (w_value * value_urgency + w_flex * flexibility_urgency + w_deadline * deadline_urgency) * 1.5

    if score >= 100:
        urgency = Urgency.CRITICAL
    elif score >= 75:
        urgency = Urgency.HIGH
    elif score >= 60:
        urgency = Urgency.MEDIUM
    elif score >= 30:
        urgency = Urgency.LOW
    elif score >= 10:
        urgency = Urgency.INFO
    else:
        urgency = Urgency.NONE

    return urgency, score


def _message(
    *,
    account: AccountUsage,
    window_label: str,
    remaining: float,
    days: float | None,
    plan_notes: Any,
) -> str:
    who = account.account or "default"
    plan = account.plan or "subscription"
    time_part = f"resets in {days:.1f} day(s)" if days is not None else "reset time unknown"
    note = f" {plan_notes}" if plan_notes else ""
    return (
        f"Use {provider_display_name(account.provider)} ({who}, {plan}) soon: "
        f"{remaining:.0f}% of the {window_label} remains and {time_part}."
        f"{note}"
    )
