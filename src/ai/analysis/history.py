"""Snapshot persistence and consumption-rate learning (Phase 4 — experimental)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ai.models import Snapshot, utcnow

_DEFAULT_SNAPSHOT_DIR = "~/.cache/ai/snapshots"
_DEFAULT_RETENTION_DAYS = 90
_DEFAULT_MIN_SNAPSHOTS = 2
_DEFAULT_LOOKBACK_DAYS = 7


def snapshot_dir() -> Path:
    return Path(os.path.expanduser(_DEFAULT_SNAPSHOT_DIR))


def save_snapshot(snapshot: Snapshot, alerts: list[Any]) -> Path:
    path = snapshot_dir()
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    ts = snapshot.collected_at.strftime("%Y-%m-%dT%H%M%SZ")
    filepath = path / f"{ts}.json"
    payload = {
        "collected_at": snapshot.collected_at.isoformat(),
        "accounts": [a.to_dict() for a in snapshot.accounts],
        "alerts": [a.to_dict() for a in alerts],
    }
    filepath.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    filepath.chmod(0o600)
    return filepath


def load_recent_snapshots(
    *, retention_days: int = _DEFAULT_RETENTION_DAYS, max_count: int = 30
) -> list[dict[str, Any]]:
    directory = snapshot_dir()
    if not directory.is_dir():
        return []
    cutoff = utcnow() - timedelta(days=retention_days)
    snapshots: list[dict[str, Any]] = []
    for entry in sorted(directory.iterdir(), reverse=True):
        if not entry.is_file() or not entry.suffix.lower() == ".json":
            continue
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ts_str = data.get("collected_at")
        if ts_str:
            try:
                collected = datetime.fromisoformat(ts_str)
                if collected.tzinfo is None:
                    collected = collected.replace(tzinfo=timezone.utc)
                if collected < cutoff:
                    continue
            except ValueError:
                continue
        snapshots.append(data)
        if len(snapshots) >= max_count:
            break
    return snapshots


def _account_window_key(account: dict[str, Any], window: dict[str, Any]) -> str:
    provider = str(account.get("provider", "")).lower()
    acct = str(account.get("account", "")).lower()
    label = str(window.get("label", "")).lower()
    resets = window.get("resets_at") or ""
    return f"{provider}|{acct}|{label}|{resets}"


def compute_learned_burn_rates(
    *,
    current: Snapshot,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
    min_snapshots: int = _DEFAULT_MIN_SNAPSHOTS,
) -> dict[str, tuple[float, int]]:
    """Return ``{'provider:duration_kind': (avg_fraction_per_day, sample_count)}``.

    ``avg_fraction_per_day`` is remaining-percent consumed per day / 100
    (e.g. 0.30 means ~30% of the window per day).
    """
    history = load_recent_snapshots(retention_days=retention_days)
    if len(history) < min_snapshots:
        return {}

    provider_window_burns: dict[str, list[tuple[float, float]]] = {}

    now = utcnow()
    for prev_data in history:
        ts_str = prev_data.get("collected_at", "")
        try:
            prev_time = datetime.fromisoformat(ts_str)
            if prev_time.tzinfo is None:
                prev_time = prev_time.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        time_delta_days = max(0.01, (now - prev_time).total_seconds() / 86400.0)
        if time_delta_days > retention_days:
            continue

        for prev_account in prev_data.get("accounts") or []:
            provider = str(prev_account.get("provider", "")).lower()
            for prev_window in prev_account.get("windows") or []:
                prev_remaining = prev_window.get("remaining_percent")
                if prev_remaining is None:
                    prev_remaining = _remaining_from_used(prev_window.get("used_percent"))
                if prev_remaining is None:
                    continue

                current_remaining = _find_current_remaining(current, prev_account, prev_window)
                if current_remaining is None:
                    continue

                consumed = prev_remaining - current_remaining
                if consumed <= 0:
                    continue

                burn_rate = consumed / time_delta_days  # percent of window per day
                window_minutes = prev_window.get("window_minutes")
                duration_key = _duration_key(window_minutes)
                if duration_key:
                    pk = f"{provider}:{duration_key}"
                    provider_window_burns.setdefault(pk, []).append((burn_rate, 1.0))

    rates: dict[str, tuple[float, int]] = {}
    for pk, burns in provider_window_burns.items():
        if len(burns) < 2:
            continue
        avg_burn_pct = sum(b * w for b, w in burns) / sum(w for _, w in burns)
        rates[pk] = (avg_burn_pct / 100.0, len(burns))
    return rates


def compute_learned_flexibility(
    *,
    current: Snapshot,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
    min_snapshots: int = _DEFAULT_MIN_SNAPSHOTS,
) -> dict[str, float]:
    rates = compute_learned_burn_rates(
        current=current,
        retention_days=retention_days,
        min_snapshots=min_snapshots,
    )
    return {k: _burn_rate_to_flexibility(rate * 100.0) for k, (rate, _n) in rates.items()}


def _burn_rate_to_flexibility(burn_rate_pct_per_day: float) -> float:
    if burn_rate_pct_per_day >= 80:
        return 1.0
    if burn_rate_pct_per_day >= 40:
        return 0.7 + 0.3 * (burn_rate_pct_per_day - 40) / 40
    if burn_rate_pct_per_day >= 10:
        return 0.25 + 0.45 * (burn_rate_pct_per_day - 10) / 30
    if burn_rate_pct_per_day >= 2:
        return 0.05 + 0.20 * (burn_rate_pct_per_day - 2) / 8
    return 0.0


def merge_learned_flexibility(
    base_flex: float,
    provider: str,
    duration_kind: str | None,
    learned: dict[str, float],
) -> float:
    if not duration_kind or not learned:
        return base_flex
    key = f"{provider.lower().replace(' ', '-')}:{duration_kind}"
    learned_flex = learned.get(key)
    if learned_flex is None:
        for learned_key, val in learned.items():
            if learned_key.endswith(f":{duration_kind}"):
                learned_flex = val
                break
    if learned_flex is None:
        return base_flex
    return 0.3 * learned_flex + 0.7 * base_flex


def chronic_waste_summary(
    *,
    current: Snapshot,
    retention_days: int = _DEFAULT_RETENTION_DAYS,
) -> list[dict[str, Any]]:
    history = load_recent_snapshots(retention_days=retention_days)
    if len(history) < _DEFAULT_MIN_SNAPSHOTS:
        return []

    wasted: dict[str, dict[str, Any]] = {}

    for prev_data in history[:7]:
        ts_str = prev_data.get("collected_at", "")
        try:
            prev_time = datetime.fromisoformat(ts_str)
            if prev_time.tzinfo is None:
                prev_time = prev_time.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        for prev_account in prev_data.get("accounts") or []:
            provider = str(prev_account.get("provider", "")).lower()
            for prev_window in prev_account.get("windows") or []:
                window_minutes = prev_window.get("window_minutes")
                if not window_minutes or window_minutes > 360:
                    continue
                prev_remaining = prev_window.get("remaining_percent")
                if prev_remaining is None:
                    prev_remaining = _remaining_from_used(prev_window.get("used_percent"))
                if prev_remaining is None:
                    continue

                key = f"{provider}:{prev_window.get('label', '')}"
                wasted.setdefault(key, {"provider": provider, "label": prev_window.get("label", ""), "samples": []})
                wasted[key]["samples"].append(prev_remaining)

    result: list[dict[str, Any]] = []
    for key, data in wasted.items():
        samples = data["samples"]
        if len(samples) < 2:
            continue
        avg = sum(samples) / len(samples)
        result.append(
            {
                "provider": data["provider"],
                "label": data["label"],
                "avg_remaining_pct": round(avg, 1),
                "sample_count": len(samples),
            }
        )
    result.sort(key=lambda x: x["avg_remaining_pct"], reverse=True)
    return result


def _remaining_from_used(used: Any) -> float | None:
    if used is None:
        return None
    try:
        return max(0.0, 100.0 - float(used))
    except (TypeError, ValueError):
        return None


def _find_current_remaining(
    snapshot: Snapshot, prev_account: dict[str, Any], prev_window: dict[str, Any]
) -> float | None:
    prev_provider = str(prev_account.get("provider", "")).lower()
    prev_account_id = str(prev_account.get("account", "")).lower()
    prev_label = str(prev_window.get("label", "")).lower()
    prev_resets = prev_window.get("resets_at") or ""

    for acc in snapshot.accounts:
        if acc.provider.lower() != prev_provider:
            continue
        if (acc.account or "").lower() != prev_account_id:
            continue
        for w in acc.windows:
            if w.label.lower() != prev_label:
                continue
            if prev_resets:
                w_resets = w.resets_at.isoformat() if w.resets_at else ""
                if w_resets != prev_resets:
                    continue
            val = w.remaining()
            if val is not None:
                return val
            return _remaining_from_used(w.used_percent)
    return None


def _duration_key(window_minutes: Any) -> str | None:
    if window_minutes is None:
        return None
    try:
        m = int(window_minutes)
    except (TypeError, ValueError):
        return None
    if m <= 360:
        return "5h"
    if m <= 10080:
        return "weekly"
    if m <= 44640:
        return "monthly"
    return None
