"""Unit tests for snapshot persistence and consumption-rate learning."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.analysis.history import (
    _account_window_key,
    _burn_rate_to_flexibility,
    _duration_key,
    _remaining_from_used,
    chronic_waste_summary,
    compute_learned_burn_rates,
    compute_learned_flexibility,
    load_recent_snapshots,
    merge_learned_flexibility,
    save_snapshot,
)
from ai.models import (
    AccountUsage,
    BillingKind,
    QuotaWindow,
    Snapshot,
    Urgency,
    UseOrLoseAlert,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_remaining_from_used():
    assert _remaining_from_used(30) == 70.0
    assert _remaining_from_used(100) == 0.0
    assert _remaining_from_used(0) == 100.0
    assert _remaining_from_used(None) is None
    assert _remaining_from_used("bad") is None


def test_duration_key():
    assert _duration_key(300) == "5h"
    assert _duration_key(360) == "5h"
    assert _duration_key(10080) == "weekly"
    assert _duration_key(20000) == "monthly"
    assert _duration_key(44640) == "monthly"
    assert _duration_key(None) is None
    assert _duration_key("bad") is None


def test_account_window_key():
    account = {"provider": "claude", "account": "test@example.com"}
    window = {"label": "5-hour", "resets_at": "2026-01-01T00:00:00Z"}
    key = _account_window_key(account, window)
    assert "claude" in key
    assert "test@example.com" in key
    assert "5-hour" in key
    assert "2026" in key


def test_burn_rate_to_flexibility():
    assert _burn_rate_to_flexibility(0) == 0.0
    assert _burn_rate_to_flexibility(5) > 0.0
    assert _burn_rate_to_flexibility(5) < 0.3
    assert _burn_rate_to_flexibility(20) > 0.25
    assert _burn_rate_to_flexibility(20) < 0.7
    assert _burn_rate_to_flexibility(60) > 0.7
    assert _burn_rate_to_flexibility(60) < 1.0
    assert _burn_rate_to_flexibility(100) == 1.0


def test_merge_learned_flexibility_no_learned():
    result = merge_learned_flexibility(0.7, "codex", "weekly", {})
    assert result == 0.7


def test_merge_learned_flexibility_with_match():
    learned = {"codex:weekly": 0.9}
    result = merge_learned_flexibility(0.7, "codex", "weekly", learned)
    assert result == 0.3 * 0.9 + 0.7 * 0.7


def test_merge_learned_flexibility_does_not_cross_providers():
    learned = {"grok:weekly": 0.3}
    result = merge_learned_flexibility(0.7, "codex", "weekly", learned)
    assert result == 0.7


def test_merge_learned_flexibility_no_duration():
    result = merge_learned_flexibility(0.5, "codex", None, {"codex:weekly": 0.9})
    assert result == 0.5


def test_save_and_load_snapshot(tmp_path: Path):
    with patch("ai.analysis.history.snapshot_dir", return_value=tmp_path):
        snap = Snapshot(
            collected_at=_now(),
            accounts=[
                AccountUsage(
                    source="codexbar",
                    provider="codex",
                    account="test",
                    billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                    windows=[
                        QuotaWindow(
                            label="weekly",
                            used_percent=20,
                            remaining_percent=80,
                            resets_at=_now() + timedelta(days=5),
                            window_minutes=10080,
                        )
                    ],
                )
            ],
        )
        alert = UseOrLoseAlert(
            urgency=Urgency.LOW,
            provider="codex",
            account="test",
            window_label="weekly",
            remaining_percent=80,
            days_until_reset=5.0,
            plan="plus",
            message="test alert",
            source="codexbar",
            score=35.0,
        )
        path = save_snapshot(snap, [alert])
        assert path.exists()

        loaded = load_recent_snapshots(retention_days=90, max_count=10)
        assert len(loaded) == 1
        assert loaded[0]["collected_at"] == snap.collected_at.isoformat()
        assert len(loaded[0]["accounts"]) == 1


def test_load_recent_snapshots_empty_dir(tmp_path: Path):
    with patch("ai.analysis.history.snapshot_dir", return_value=tmp_path):
        assert load_recent_snapshots() == []


def test_load_recent_snapshots_filters_old(tmp_path: Path):
    with patch("ai.analysis.history.snapshot_dir", return_value=tmp_path):
        old = tmp_path / "old.json"
        old_data = {"collected_at": (_now() - timedelta(days=100)).isoformat(), "accounts": []}
        old.write_text(json.dumps(old_data))

        recent = tmp_path / "recent.json"
        recent_data = {"collected_at": _now().isoformat(), "accounts": []}
        recent.write_text(json.dumps(recent_data))

        loaded = load_recent_snapshots(retention_days=90, max_count=10)
        assert len(loaded) == 1


def test_compute_learned_flexibility_needs_min_snapshots(tmp_path: Path):
    with patch("ai.analysis.history.snapshot_dir", return_value=tmp_path):
        snap = Snapshot(collected_at=_now(), accounts=[])
        learned = compute_learned_flexibility(current=snap, retention_days=90, min_snapshots=5)
        assert learned == {}


def test_compute_learned_flexibility_with_data(tmp_path: Path):
    with patch("ai.analysis.history.snapshot_dir", return_value=tmp_path):
        now = _now()

        snap1 = {
            "collected_at": (now - timedelta(days=1)).isoformat(),
            "accounts": [
                {
                    "provider": "codex",
                    "account": "test",
                    "windows": [{"label": "weekly", "remaining_percent": 80, "window_minutes": 10080}],
                }
            ],
        }
        snap2 = {
            "collected_at": (now - timedelta(days=2)).isoformat(),
            "accounts": [
                {
                    "provider": "codex",
                    "account": "test",
                    "windows": [{"label": "weekly", "remaining_percent": 95, "window_minutes": 10080}],
                }
            ],
        }
        (tmp_path / "s1.json").write_text(json.dumps(snap1))
        (tmp_path / "s2.json").write_text(json.dumps(snap2))

        current = Snapshot(
            collected_at=now,
            accounts=[
                AccountUsage(
                    source="codexbar",
                    provider="codex",
                    account="test",
                    billing_kind=BillingKind.SUBSCRIPTION_WINDOW,
                    windows=[
                        QuotaWindow(
                            label="weekly",
                            used_percent=55,
                            remaining_percent=45,
                            resets_at=now + timedelta(days=5),
                            window_minutes=10080,
                        )
                    ],
                )
            ],
        )
        learned = compute_learned_flexibility(current=current, retention_days=90, min_snapshots=2)
        assert "codex:weekly" in learned
        assert 0.0 <= learned["codex:weekly"] <= 1.0

        rates = compute_learned_burn_rates(current=current, retention_days=90, min_snapshots=2)
        assert "codex:weekly" in rates
        rate, n = rates["codex:weekly"]
        assert n >= 2
        assert rate > 0
        # Flexibility and raw rate move together (higher burn → higher flex).
        assert learned["codex:weekly"] == pytest.approx(_burn_rate_to_flexibility(rate * 100.0))


def test_chronic_waste_detection(tmp_path: Path):
    with patch("ai.analysis.history.snapshot_dir", return_value=tmp_path):
        now = _now()
        for i in range(1, 8):
            data = {
                "collected_at": (now - timedelta(days=i)).isoformat(),
                "accounts": [
                    {
                        "provider": "claude",
                        "windows": [{"label": "5-hour", "remaining_percent": 80 + i, "window_minutes": 300}],
                    }
                ],
            }
            (tmp_path / f"s{i}.json").write_text(json.dumps(data))

        current = Snapshot(collected_at=now, accounts=[])
        wasted = chronic_waste_summary(current=current, retention_days=90)
        assert len(wasted) >= 1
        assert wasted[0]["avg_remaining_pct"] > 80
