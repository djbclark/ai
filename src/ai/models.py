"""Normalized data models for live provider quotas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    def to_dict(self) -> dict[str, Any]:
        return {
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
