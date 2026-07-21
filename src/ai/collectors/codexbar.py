"""Collect live subscription/API quotas from CodexBar."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ai.models import (
    AccountUsage,
    BillingKind,
    QuotaWindow,
    classify_window_minutes,
    parse_dt,
)
from ai.models import coerce_float as _f
from ai.models import coerce_int as _int_or_none

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

# CodexBar itself queries providers serially within a single invocation, so a
# bundled "enabled providers" call costs the sum of every provider's latency.
# Querying one provider per subprocess and running those concurrently instead
# costs only the slowest provider's latency. Capped to avoid spawning an
# unreasonable number of processes for a very long explicit --providers list.
_MAX_CONCURRENT_PROVIDER_QUERIES = 16

_SLOT_LABELS: dict[str, tuple[str, str, str]] = {
    "copilot": (
        "GitHub Copilot completions",
        "GitHub Copilot chat messages",
        "GitHub Copilot premium requests",
    ),
    "grok": ("Grok usage limit", "Grok quota 2", "Grok quota 3"),
    "warp": ("Warp credits", "Warp quota 2", "Warp quota 3"),
    "elevenlabs": (
        "ElevenLabs character credits",
        "ElevenLabs quota 2",
        "ElevenLabs quota 3",
    ),
}


def collect_codexbar(*, providers: str | list[str] | None = "enabled") -> list[AccountUsage]:
    if not which("codexbar"):
        raise CollectorError("codexbar not found on PATH")

    provider_list = _normalize_providers(providers)
    # A single discovered provider stands in for what used to be one bundled,
    # more generously timed call; give it at least that same time ceiling.
    min_timeout: float | None = None
    if provider_list == [None]:
        # Discover the actual enabled-provider list ourselves so each can be
        # queried as its own concurrent subprocess, instead of asking CodexBar
        # for "enabled providers" in one call that it resolves serially.
        discovered = _discover_enabled_providers()
        if discovered:
            provider_list = discovered
            if len(provider_list) == 1:
                min_timeout = 180.0

    accounts: list[AccountUsage] = []
    errors: list[str] = []

    for provider_arg, outcome in _query_providers(provider_list, min_timeout=min_timeout):
        if isinstance(outcome, CollectorError):
            name = provider_arg or "enabled providers"
            errors.append(f"{name}: {outcome}")
            continue
        rows = outcome if isinstance(outcome, list) else [outcome]
        for row in rows:
            if isinstance(row, dict):
                accounts.append(_from_row(row))

    if not accounts and errors:
        raise CollectorError("; ".join(errors))
    if errors:
        accounts.append(
            AccountUsage(
                source="codexbar",
                provider="codexbar-query-errors",
                error="; ".join(errors),
                billing_kind=BillingKind.UNKNOWN,
            )
        )
    return accounts


def _normalize_providers(providers: str | list[str] | None) -> list[str | None]:
    """Return None for enabled-provider discovery, or explicit provider queries."""
    if providers is None:
        return [None]
    if isinstance(providers, list):
        items: list[str] = [str(provider).strip().lower() for provider in providers if str(provider).strip()]
    else:
        text = str(providers).strip().lower()
        if text in ("", "enabled", "configured", "default"):
            return [None]
        if text in ("all", "both"):
            return [text]
        items = [provider.strip().lower() for provider in text.split(",") if provider.strip()]
    return list(items) if items else [None]


def _discover_enabled_providers() -> list[str | None] | None:
    """Ask CodexBar's own fast, documented config lookup which providers are
    enabled (`codexbar config providers`, a local read that takes milliseconds),
    so the caller can query each one independently instead of via the slow
    bundled call. Returns None if unavailable or unparsable, so the caller
    falls back to that bundled call. Any failure here must fall back rather
    than propagate, since discovery is a best-effort optimization.
    """
    try:
        payload = run_json(["codexbar", "config", "providers", "--format", "json"], timeout=5.0)
    except Exception:  # noqa: BLE001
        return None
    return _parse_enabled_providers(payload)


def _parse_enabled_providers(payload: Any) -> list[str | None] | None:
    if not isinstance(payload, list):
        return None
    enabled: list[str | None] = [
        str(row["provider"]).lower()
        for row in payload
        if isinstance(row, dict) and row.get("enabled") and row.get("provider")
    ]
    return enabled or None


def _query_providers(
    provider_list: list[str | None],
    *,
    min_timeout: float | None = None,
) -> list[tuple[str | None, Any]]:
    """Run one `codexbar usage` call per entry in provider_list, concurrently.

    Returns (provider_arg, payload_or_error) pairs in provider_list order,
    regardless of which subprocess finishes first, so downstream account and
    error ordering stays deterministic. Duplicate entries are queried once —
    querying the same provider twice concurrently is never useful and would
    otherwise race on which duplicate's outcome survives.
    """
    deduped: list[str | None] = list(dict.fromkeys(provider_list))
    if len(deduped) <= 1:
        return [(provider_arg, _query_provider(provider_arg, min_timeout=min_timeout)) for provider_arg in deduped]

    workers = min(len(deduped), _MAX_CONCURRENT_PROVIDER_QUERIES)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_query_provider, provider_arg, min_timeout=min_timeout): provider_arg
            for provider_arg in deduped
        }
        outcomes: dict[str | None, Any] = {}
        for future in as_completed(futures):
            outcomes[futures[future]] = future.result()
    return [(provider_arg, outcomes[provider_arg]) for provider_arg in deduped]


def _query_provider(provider_arg: str | None, *, min_timeout: float | None = None) -> Any:
    # Omitting --provider asks CodexBar for its enabled-provider list and data
    # (only reached as a fallback if _discover_enabled_providers() fails).
    argv = ["codexbar", "usage", "--format", "json"]
    if provider_arg is not None:
        argv.extend(["--provider", provider_arg])
    timeout = 180.0 if provider_arg in (None, "all", "both") else 90.0
    if min_timeout is not None:
        timeout = max(timeout, min_timeout)
    try:
        return run_json(argv, timeout=timeout)
    except CollectorError as exc:
        return exc
    except Exception as exc:  # noqa: BLE001 — isolate this provider's failure from the rest of the batch
        return CollectorError(str(exc))


def _from_row(row: dict[str, Any]) -> AccountUsage:
    provider = str(row.get("provider") or "unknown").lower()
    source_tag = str(row.get("source") or "unknown mechanism")
    err = row.get("error")
    if isinstance(err, dict):
        err = err.get("message") or str(err)
    if isinstance(err, str):
        return AccountUsage(
            source="codexbar",
            provider=provider,
            error=err,
            billing_kind=_billing_kind(provider, None),
            raw=row,
        )

    usage_value = row.get("usage")
    usage: dict[str, Any] = usage_value if isinstance(usage_value, dict) else {}
    identity_value = usage.get("identity")
    identity: dict[str, Any] = identity_value if isinstance(identity_value, dict) else {}
    account = row.get("account") or usage.get("accountEmail") or identity.get("accountEmail")
    plan = usage.get("loginMethod") or identity.get("loginMethod")

    windows: list[QuotaWindow] = []
    extra_windows: list[QuotaWindow] = []
    for extra in usage.get("extraRateWindows") or []:
        if not isinstance(extra, dict) or not isinstance(extra.get("window"), dict):
            continue
        title = str(extra.get("title") or extra.get("id") or "Unnamed CodexBar quota")
        window = _window(title, extra["window"])
        if window:
            extra_windows.append(window)
    windows.extend(extra_windows)

    has_named_balance_blob = bool(usage.get("openRouterUsage") or usage.get("openAIAPIUsage"))
    for index, key in enumerate(("primary", "secondary", "tertiary"), start=1):
        block = usage.get(key)
        if not isinstance(block, dict):
            continue
        if provider in PREPAID_HINTS and has_named_balance_blob:
            continue
        label = _slot_label(provider, index, block)
        window = _window(label, block)
        if window and not any(window.same_measurement(extra) for extra in extra_windows):
            windows.append(window)

    # Provider-specific balance/usage blobs that are not subscription windows.
    for nested_key, label in (
        ("openRouterUsage", "OpenRouter prepaid balance usage"),
        ("openAIAPIUsage", "OpenAI pay-as-you-go API usage"),
    ):
        nested = usage.get(nested_key)
        if isinstance(nested, dict) and nested.get("usedPercent") is not None:
            used = _f(nested.get("usedPercent"))
            windows.append(
                QuotaWindow(
                    label=label,
                    used_percent=used,
                    remaining_percent=max(0.0, 100.0 - used) if used is not None else None,
                    raw=nested,
                )
            )

    balance_usd = None
    credits_remaining = None
    notes: list[str] = [f"Live data fetched by CodexBar via {source_tag}."]

    credits = row.get("credits")
    if isinstance(credits, dict):
        credits_remaining = _f(credits.get("remaining"))

    openrouter = usage.get("openRouterUsage")
    if isinstance(openrouter, dict):
        balance_usd = _f(openrouter.get("balance"))
        total = _f(openrouter.get("totalCredits"))
        used = _f(openrouter.get("totalUsage"))
        if total is not None and used is not None:
            notes.append(f"OpenRouter prepaid credits: ${total:.2f} funded, ${used:.2f} spent.")

    reset_credits = usage.get("codexResetCredits")
    if isinstance(reset_credits, dict) and reset_credits.get("availableCount") is not None:
        notes.append(f"Codex limit-reset credits available: {reset_credits['availableCount']}.")
    if usage.get("dataConfidence"):
        notes.append(f"CodexBar data confidence: {usage['dataConfidence']}.")

    billing = _billing_kind(provider, usage, windows)
    if billing == BillingKind.PREPAID_BALANCE and balance_usd is None and credits_remaining is not None:
        balance_usd = credits_remaining

    # DeepSeek-style prepaid balance embedded in a quota description. A "$" figure
    # immediately followed by "/" (e.g. "$0.002/1K tokens") is a per-unit rate, not
    # a balance, so it's skipped.
    for window in windows:
        description = (window.reset_description or "") + " " + str(window.raw.get("resetDescription") or "")
        if "$" in description and balance_usd is None:
            match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", description)
            if match and re.match(r"\s*/", description[match.end() :]):
                match = None
            if match:
                balance_usd = float(match.group(1))
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
        notes=notes,
        raw=row,
    )


def _window(label: str, block: dict[str, Any]) -> QuotaWindow | None:
    used = _f(block.get("usedPercent"))
    remaining = _f(block.get("remainingPercent"))
    description = block.get("resetDescription") or block.get("reset_description")

    # A provider reporting 0/0 has no usable entitlement; it is not 100% unused.
    quantity = re.search(
        r"([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)",
        str(description or ""),
    )
    if quantity and float(quantity.group(2)) == 0:
        used = None
        remaining = 0.0
    elif remaining is None and used is not None:
        remaining = max(0.0, 100.0 - used)

    resets = parse_dt(block.get("resetsAt") or block.get("resets_at"))
    if used is None and remaining is None and resets is None and not description:
        return None
    return QuotaWindow(
        label=label,
        used_percent=used,
        remaining_percent=remaining,
        resets_at=resets,
        window_minutes=_int_or_none(block.get("windowMinutes") or block.get("window_minutes")),
        reset_description=str(description) if description else None,
        raw=block,
    )


def _slot_label(provider: str, index: int, block: dict[str, Any]) -> str:
    mapped = _SLOT_LABELS.get(provider)
    if mapped:
        return mapped[index - 1]

    minutes = _int_or_none(block.get("windowMinutes") or block.get("window_minutes"))
    provider_name = {
        "codex": "Codex",
        "opencodego": "OpenCode Go",
        "antigravity": "Google AI / Antigravity",
    }.get(provider, provider.replace("-", " ").title())
    kind = classify_window_minutes(minutes)
    if kind == "5h":
        return f"{provider_name} 5-hour quota"
    if kind == "weekly":
        return f"{provider_name} weekly quota"
    if kind == "monthly":
        return f"{provider_name} monthly quota"
    return f"{provider_name} quota {index} (name not supplied by CodexBar)"


def _billing_kind(
    provider: str,
    usage: dict[str, Any] | None,
    windows: list[QuotaWindow] | None = None,
) -> BillingKind:
    # Usage-shape signals are checked before the generic provider-name hint list so a
    # provider that happens to be in PREPAID_HINTS but reports a real subscription
    # window (or an explicit pay-as-you-go usage blob) is not misclassified.
    if usage and usage.get("openAIAPIUsage"):
        return BillingKind.PAYG_API
    if usage and usage.get("openRouterUsage"):
        return BillingKind.PREPAID_BALANCE
    if windows and any(window.resets_at is not None for window in windows):
        return BillingKind.SUBSCRIPTION_WINDOW
    if provider.lower() in PREPAID_HINTS:
        return BillingKind.PREPAID_BALANCE
    if usage and any(usage.get(key) for key in ("primary", "secondary", "tertiary")):
        return BillingKind.UNKNOWN
    return BillingKind.UNKNOWN
