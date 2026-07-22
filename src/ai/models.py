"""Normalized data models for live provider quotas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value: Any) -> int | None:
    number = coerce_float(value)
    return int(number) if number is not None else None


# Window-duration boundaries (minutes) shared by every collector that buckets a
# raw `windowMinutes` value into a human quota kind, and by the analysis layer
# that decides whether a window is a short rate-limit (not "monthly waste").
WINDOW_5H_MAX_MINUTES = 360
WINDOW_WEEKLY_MAX_MINUTES = 10080
WINDOW_MONTHLY_MAX_MINUTES = 44640


def classify_window_minutes(minutes: int | None) -> str | None:
    """Bucket a window's duration in minutes into '5h' | 'weekly' | 'monthly' | None."""
    if minutes is None:
        return None
    if minutes <= WINDOW_5H_MAX_MINUTES:
        return "5h"
    if minutes <= WINDOW_WEEKLY_MAX_MINUTES:
        return "weekly"
    if minutes <= WINDOW_MONTHLY_MAX_MINUTES:
        return "monthly"
    return None


PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "antigravity": "Google AI / Antigravity",
    "claude": "Claude Code",
    "codex": "Codex",
    "copilot": "GitHub Copilot",
    "grok": "Grok",
    "opencode-go": "OpenCode Go",
}


def provider_display_name(provider: str) -> str:
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.replace("-", " ").title())


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Common variants: ...Z, +00:00, space separator
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BillingKind(str, Enum):
    """How the allotment is billed / expires."""

    SUBSCRIPTION_WINDOW = "subscription_window"  # resets on schedule; unused is lost
    PREPAID_BALANCE = "prepaid_balance"  # rolls until spent
    PAYG_API = "payg_api"  # pay as you go, no allotment
    UNKNOWN = "unknown"


class Urgency(str, Enum):
    CRITICAL = "critical"  # lots remaining, resets very soon
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


class FlexibilityClass(str, Enum):
    BURSTABLE = "burstable"  # use all at once
    SEMI_THROTTLED = "semi"  # burst possible but day-capped
    THROTTLED = "throttled"  # strictly rate-limited per refill


@dataclass
class FlexibilityProfile:
    """Derived per-window consumption characteristics (not raw data)."""

    flexibility_class: FlexibilityClass
    consumption_flexibility: float  # 0.0–1.0 continuous
    value_at_risk_usd: float | None = None
    cycles_needed: int | None = None
    earliest_start_calendar: datetime | None = None
    effective_burn_minutes: float | None = None
    burn_estimate: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "flexibility_class": self.flexibility_class.value,
            "consumption_flexibility": self.consumption_flexibility,
            "value_at_risk_usd": self.value_at_risk_usd,
            "cycles_needed": self.cycles_needed,
            "effective_burn_minutes": self.effective_burn_minutes,
            "burn_estimate": self.burn_estimate,
        }
        if self.earliest_start_calendar:
            d["earliest_start_calendar"] = self.earliest_start_calendar.isoformat()
        else:
            d["earliest_start_calendar"] = None
        return d


@dataclass
class QuotaWindow:
    """A single rate-limit / credit window (5h, weekly, monthly, ...)."""

    label: str
    used_percent: float | None = None
    remaining_percent: float | None = None
    resets_at: datetime | None = None
    window_minutes: int | None = None
    reset_description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    # Per-refill capacity metadata (populated by collectors when known)
    refill_capacity: float | None = None
    refill_capacity_unit: str | None = None  # "tokens" | "requests" | "usd"
    internal_throttle: bool = False

    def remaining(self) -> float | None:
        if self.remaining_percent is not None:
            return self.remaining_percent
        if self.used_percent is not None:
            return max(0.0, 100.0 - self.used_percent)
        return None

    def days_until_reset(self, now: datetime | None = None) -> float | None:
        if not self.resets_at:
            return None
        now = now or utcnow()
        return (self.resets_at - now).total_seconds() / 86400.0

    def same_measurement(self, other: "QuotaWindow") -> bool:
        """Whether two windows look like the same underlying measurement (for dedup)."""
        return (
            self.resets_at == other.resets_at
            and self.used_percent == other.used_percent
            and self.window_minutes == other.window_minutes
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.resets_at:
            d["resets_at"] = self.resets_at.isoformat()
        return d


@dataclass
class AccountUsage:
    """Normalized usage for one provider account."""

    source: str  # cswap | codexbar | tokscale
    provider: str
    account: str | None = None
    plan: str | None = None
    billing_kind: BillingKind = BillingKind.UNKNOWN
    windows: list[QuotaWindow] = field(default_factory=list)
    balance_usd: float | None = None
    credits_remaining: float | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "provider": self.provider,
            "account": self.account,
            "plan": self.plan,
            "billing_kind": self.billing_kind.value,
            "windows": [w.to_dict() for w in self.windows],
            "balance_usd": self.balance_usd,
            "credits_remaining": self.credits_remaining,
            "error": self.error,
            "notes": self.notes,
        }


@dataclass
class UseOrLoseAlert:
    """Recommendation to burn remaining subscription allotment before reset."""

    urgency: Urgency
    provider: str
    account: str | None
    window_label: str
    remaining_percent: float
    days_until_reset: float | None
    plan: str | None
    message: str
    source: str
    score: float  # higher = more important

    flexibility_profile: FlexibilityProfile | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "urgency": self.urgency.value,
            "provider": self.provider,
            "account": self.account,
            "window_label": self.window_label,
            "remaining_percent": self.remaining_percent,
            "days_until_reset": self.days_until_reset,
            "plan": self.plan,
            "message": self.message,
            "source": self.source,
            "score": self.score,
        }
        if self.flexibility_profile:
            d["consumption_analysis"] = self.flexibility_profile.to_dict()
        return d


@dataclass
class CrossCheck:
    """Comparison of overlapping live measurements from independent tools."""

    provider: str
    account: str | None
    status: str  # consistent | warning | unavailable
    sources: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Snapshot:
    """Full collection snapshot."""

    collected_at: datetime
    accounts: list[AccountUsage] = field(default_factory=list)
    cross_checks: list[CrossCheck] = field(default_factory=list)
    collector_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collected_at": self.collected_at.isoformat(),
            "accounts": [a.to_dict() for a in self.accounts],
            "cross_checks": [check.to_dict() for check in self.cross_checks],
            "collector_errors": self.collector_errors,
        }
