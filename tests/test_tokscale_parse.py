"""Tests for tokscale window inference cleanups (Step 27)."""

from ai.collectors.tokscale import _infer_window_minutes
from ai.models import WINDOW_NOMINAL_MINUTES


def test_premium_label_monthly_only_for_copilot():
    assert _infer_window_minutes("copilot", "premium", "Premium") == WINDOW_NOMINAL_MINUTES["monthly"]
    assert _infer_window_minutes("grok", "premium", "Premium") is None


def test_digit_7_in_label_does_not_force_weekly():
    assert _infer_window_minutes("grok", "usage", "Grok7 usage") is None


def test_5h_uses_nominal_300_not_bucket_max():
    assert _infer_window_minutes("claude", "session", "Session") == 300
    assert _infer_window_minutes("claude", "5h", "5-hour") == WINDOW_NOMINAL_MINUTES["5h"]


def test_15h_label_does_not_match_5h_bucket():
    assert _infer_window_minutes("claude", "15h window", "15h window") is None
