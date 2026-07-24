"""Pure pace-math for Phase 2 scoring (not wired into analyze_use_or_lose yet)."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiuse.models import PaceProfile, QuotaWindow, classify_window_minutes, nominal_window_minutes


def compute_pace(
    window: QuotaWindow,
    *,
    now: datetime,
    learned_rate_per_day: float | None = None,  # fraction/day, e.g. 0.30 == 30%/day
    learned_sample_count: int = 0,
    e_min: float = 0.05,
) -> PaceProfile | None:
    remaining = window.remaining()
    if remaining is None:
        return None
    used_fraction = (100.0 - remaining) / 100.0

    kind = classify_window_minutes(window.window_minutes)
    duration_minutes = window.window_minutes or nominal_window_minutes(kind)
    confidence = "measured" if window.window_minutes else ("inferred" if duration_minutes else "low")

    if not window.resets_at or not duration_minutes:
        return PaceProfile(
            elapsed_fraction=None,
            used_fraction=used_fraction,
            pace_ratio=None,
            projected_used_fraction=None,
            projected_waste_fraction=None,
            projected_waste_usd=None,
            projected_exhaust_at=None,
            confidence="low",
        )

    t_left_days = max(0.0, (window.resets_at - now).total_seconds() / 86400.0)
    d_days = duration_minutes / 1440.0
    elapsed = min(1.0, max(0.0, 1.0 - t_left_days / d_days))

    r_now = used_fraction / (max(elapsed, e_min) * d_days)  # fraction/day
    if learned_rate_per_day is not None and learned_sample_count > 0:
        lam = learned_sample_count / (learned_sample_count + 2.0)
        r_hat = (1 - lam) * r_now + lam * learned_rate_per_day
    else:
        r_hat = r_now

    projected_used = min(1.0, used_fraction + r_hat * t_left_days)
    waste = 1.0 - projected_used
    exhaust_at = now + timedelta(days=(1.0 - used_fraction) / r_hat) if r_hat > 1e-9 else None

    return PaceProfile(
        elapsed_fraction=elapsed,
        used_fraction=used_fraction,
        pace_ratio=used_fraction / max(elapsed, e_min),
        projected_used_fraction=projected_used,
        projected_waste_fraction=waste,
        projected_waste_usd=None,  # filled in by the caller once it knows the plan price
        projected_exhaust_at=exhaust_at,
        confidence=confidence,
    )


def classify_pace(
    pace: PaceProfile,
    *,
    resets_at: datetime | None,
    waste_alert_fraction: float,
    min_elapsed_fraction: float,
    conserve_min_lead_hours: float,
    has_learned_rate: bool,
) -> str:
    """Returns 'conserve' | 'burn' | 'on_pace' | 'unknown'."""
    if pace.projected_waste_fraction is None and pace.projected_exhaust_at is None:
        return "unknown"
    # Too early in the window (no learned rate) → do not trust burn/conserve yet.
    if (
        pace.elapsed_fraction is not None
        and pace.elapsed_fraction < min_elapsed_fraction
        and not has_learned_rate
    ):
        return "on_pace"
    if pace.projected_exhaust_at and resets_at:
        if pace.projected_exhaust_at < resets_at - timedelta(hours=conserve_min_lead_hours):
            return "conserve"
    if pace.projected_waste_fraction is None:
        return "unknown"
    if pace.projected_waste_fraction >= waste_alert_fraction:
        return "burn"
    return "on_pace"

def governing_partition(windows: list[QuotaWindow]) -> tuple[QuotaWindow | None, list[QuotaWindow]]:
    """Longest-duration window with usable remaining() governs; the rest are children.

    When durations tie (e.g. Cursor Included/Auto/API all monthly), prefer a
    window whose label looks like the overall included bar, then list order.
    """
    scored = [
        (
            w.window_minutes
            or nominal_window_minutes(classify_window_minutes(w.window_minutes))
            or 0,
            0 if "included" in (w.label or "").casefold() else 1,
            w,
        )
        for w in windows
        if w.remaining() is not None
    ]
    if not scored:
        return None, list(windows)
    # Longest minutes first; among ties, included (rank 0) before others.
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    governing = scored[0][2]
    children = [w for w in windows if w is not governing]
    return governing, children
