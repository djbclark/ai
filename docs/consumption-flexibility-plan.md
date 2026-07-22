# Multi-Dimensional Use-It-or-Lose-It Scoring

## Problem

Current scoring (`use_or_lose.py:_score`) is one-dimensional — it weights **deadline
proximity** heavily and applies a blunt binary filter that discards all short-refill
windows (≤ 360 min). This hides real plan value being wasted daily and fails to
distinguish between:

- **Burstable** quotas (Codex monthly, OpenCode Go monthly): can consume 100% in one
  session. Deadline proximity is the only real constraint.
- **Throttled** quotas (Claude 5h, Gemini 5h): rate-limited per refill cycle. A user
  literally *cannot* burn through allotment faster than the refill rate. Missing
  one cycle wastes little; habitually missing them wastes significant plan value
  over time.

A throttled window with 80% remaining and 2h left is *more urgent in calendar
terms* than a burstable monthly window with 80% remaining and 10 days left —
because you only have one shot at the throttled window before it resets, while
the burstable window can wait.

When describing what a user should do *now* versus *later*, and how to allocate
coding time across providers, all three dimensions matter.

## Three Dimensions

### 1. Value at Risk (stake size)

> *How much money is at stake if this window resets fully unused?*

Roughly: `(monthly plan price × share of billing cycle × remaining%)`, or from a
known per-unit rate: `(remaining tokens × rate per 1M tokens)`.

A 5h window at $20/month is worth ~$0.14 (5h / 730h in month).  A monthly window
at $20/month with 80% remaining risks $16.  This alone justifies why monthly windows
outrank 5h windows, but the ranking should be continuous — not a binary filter.

**Data needed:**
- `window_duration_minutes` (already captured as `window_minutes` on `QuotaWindow`)
- plan price (config or inferred)
- `remaining_percent` / `used_percent`
- If available: per-token pricing to convert token quotas → dollars

### 2. Consumption Flexibility (burstability)

> *How fast can you physically consume the remaining allocation?*

| Flexibility | Description | Example |
|---|---|---|
| 1.0 (fully burstable) | Use entire window in one session | Codex monthly, OpenCode Go monthly |
| 0.5 (semi-throttled) | Burst possible but rate-limited per day | Grok weekly, Cursor monthly |
| 0.0 (fully throttled) | Max consumption = refill rate × time | Claude 5h, Gemini 5h |

**Data needed:**
- `window_duration_minutes` (shorter window → lower flexibility)
- `refill_amount_per_cycle` (how many tokens/requests in each refill, when known)
- Max sustained tokens per minute (human cognitive ceiling — roughly 100K–500K/min for
  heavy conversational use, or per-provider actual throughput)
- Provider-specific hints: is the provider known to rate-limit within its window?

**Derived metric — effective burn minutes:**

```
effective_burn_minutes = ceil(remaining_percent / 100 * window_capacity)
                         / max_sustained_tokens_per_minute

consumption_cycles_needed = max(1, ceil(effective_burn_minutes / burst_capacity_minutes))

earliest_start_calendar = resets_at - (consumption_cycles_needed * window_duration_minutes)
```

If `earliest_start_calendar` is already in the past, you've already lost some
capacity — raise urgency.

### 3. Deadline Pressure (calendar proximity)

> *How soon does it reset?*  (Already modeled.)

This dimension remains important but should interact with flexibility:

- Burstable quota: pure calendar pressure — urgency rises as reset approaches.
- Throttled quota: calendar pressure is dampened because most of the value can't
  be saved regardless.

**Existing:** `days_until_reset` — keep as-is.  Add `urgency_curve` that differs
by flexibility class.

## Data Model Changes

### QuotaWindow (extensions)

```python
@dataclass
class QuotaWindow:
    # ... existing fields ...

    # NEW: per-refill capacity when known (tokens, requests, $)
    refill_capacity: float | None = None       # e.g. Claude 5h block ≈ $5
    refill_capacity_unit: str | None = None    # "tokens" | "requests" | "usd"

    # NEW: is this window rate-limited internally? (Some providers enforce
    # additional throttles within a quota window, e.g. Grok rate-limits)
    internal_throttle: bool = False
```

### UseOrLoseAlert (extensions)

```python
@dataclass
class UseOrLoseAlert:
    # ... existing fields ...

    # NEW per-dimension display values
    value_at_risk_usd: float | None = None         # dimension 1
    consumption_flexibility: float | None = None    # dimension 2 (0–1)
    effective_deadline: datetime | None = None      # dimension 3, when you must start
```

### New enum: FlexibilityClass

```python
class FlexibilityClass(str, Enum):
    BURSTABLE = "burstable"         # use all at once
    SEMI_THROTTLED = "semi"         # burst possible but day-capped
    THROTTLED = "throttled"         # strictly rate-limited per refill
```

## Scoring Algorithm

### Weighted composite

```
urgency_score = (
    w_value * value_urgency
    + w_flex * flexibility_urgency
    + w_deadline * deadline_urgency
)
```

Default weights (configurable):
- `w_value = 0.35` (stake size)
- `w_flex = 0.30` (forced early start from throttling)
- `w_deadline = 0.35` (calendar proximity)

### Per-dimension urgency functions

**value_urgency** (0–100):
```
value_urgency = clamp((value_at_risk_usd / max_monthly_plan_price) * 100, 0, 100)
```
A $15 stake at $20 plan = 75. A $0.14 stake = ~0.7.

**flexibility_urgency** (0–100):
```
if flexibility >= 0.9:    # burstable
    urgency = 0
elif flexibility >= 0.5:  # semi
    urgency = 30 * (1 - flexibility) + 20 * clamp(days_until_reset / max_cycles, 0, 1)
else:                      # throttled
    cycles_needed = consumption_cycles_needed
    if earliest_start_calendar < now:
        urgency = 100     # you're already behind
    else:
        urgency = 60 + 40 * clamp(
            (earliest_start_calendar - now) / (resets_at - now), 0, 1
        )
```

**deadline_urgency** (0–100): same as current time-pressure bonus, but scaled by
flexibility: `raw_deadline * (1 - flexibility * 0.5)` so throttled windows get
less deadline panic.

### Tier assignment (backward-compatible)

Map score ranges to existing `Urgency` enum:
- `score ≥ 80` → CRITICAL
- `score ≥ 60` → HIGH
- `score ≥ 40` → MEDIUM
- `score ≥ 20` → LOW
- `score < 20`  → INFO (only if value_at_risk > $0.50)

## Collector Changes

### cswap
Already provides `windowMinutes` in the `usage` schema.  Add parsing for:
- `refillCapacity` field if cswap adds it
- Infer per-refill amount from plan type + price config

### CodexBar
Already provides `windowMinutes` in quota blocks.  Add:
- Detect `internal_throttle` from provider-specific behavior
- Use `extraRateWindows` capacity info for refill_amount

### tokscale
Already provides usage percent + label.  Add:
- Parse `window_minutes` if available from metrics
- Cross-reference with config for plan details

### Config
New `config/services.yaml` keys:

```yaml
plans:
  claude:
    monthly_price: 20      # USD
    window_values:          # approximate $ value per refill window
      5h: 0.14
      weekly: 4.62
      monthly: 20.0
  codex:
    monthly_price: 20
    window_values:
      weekly: 4.62
      monthly: 20.0

analysis:
  # existing thresholds ...
  consumption_flexibility_defaults:  # per-window-duration hint
    5h: 0.0          # fully throttled
    weekly: 0.7      # semi-burstable (some providers gate weekly usage)
    monthly: 1.0     # fully burstable
```

## Display Design

### Per-window detail (pretty report)

Each window line in the per-provider section gains a **three-bar micro-chart**:

```
Codex · djbclark@gmail.com · Codex weekly quota
  value  ████████░░  80% at risk ($3.70 of $4.62)
  flex   ██████████  100% burstable — use anytime
  clock  ██████░░░░  60% urgency · resets in 3.0d
```

Or compact one-liner for throttled:

```
Claude 5h · djbclark@mit.edu
  value ░░░░░░░░░░  <1% at risk   ($0.11 of $0.14)
  flex  ░░░░░░░░░░   0% burstable — must use now or lose it
  clock ████████░░  80% urgency · resets in 0.2d
  →  stake too small for action plan
```

### Unified action plan section

Instead of the current flat "use X by Y" list, the action plan groups into
**time buckets** with a short narrative:

```
## Unified Action Plan
----------------------------------------------------------------------
Your total at risk this cycle: $42.18 across 8 windows (3 providers).

  NOW (start today, before they reset this week)
  ─────────────────────────────────────────────
  !!! OpenCode Go weekly  99% left · 4.5d · $14.85 at risk
      Burstable — block 2 hours on calendar.
  !!  Grok usage limit    22% left · 0.8d · $0.92 at risk
      Throttled — use it now, or accept losing it.
  ·   Claude 5h (mit)     0% used · 0.2d · $0.00 at risk
      Fully used — no action needed.

  SOON (schedule this weekend)
  ─────────────────────────────
  !!  Codex weekly         88% left · 6.4d · $4.07 at risk
      Burstable — a Saturday heavy session will cover it.

  LATER (before end of month)
  ───────────────────────────
  ·   Cursor monthly       41% left · 11.5d · $8.20 at risk
      Semi-throttled — steady usage will exhaust it; no panic.

  THROTTLED — ACCUMULATING WASTE
  ──────────────────────────────
  ·   Gemini 5h: averaging 12% used per cycle across 6 daily cycles.
      At this rate you waste ~$0.84/month of your $20 plan.
      Consider: are you getting value from this subscription?
```

### JSON output

Add `consumption_analysis` block to each alert:

```json
{
  "urgency": "critical",
  "provider": "opencode-go",
  "window_label": "OpenCode Go weekly quota",
  "remaining_percent": 99.0,
  "days_until_reset": 4.5,
  "consumption_analysis": {
    "value_at_risk_usd": 14.85,
    "flexibility_class": "burstable",
    "consumption_flexibility": 1.0,
    "effective_deadline": "2026-07-26T23:59:00Z",
    "cycles_needed": 1,
    "earliest_start": null
  },
  "score": 88.5,
  "message": "..."
}
```

## Phased Implementation

### Phase 1 — Surface data (no scoring changes)

**Goal:** Collect and persist the new fields without changing urgency output.

1. Add `value_at_risk_usd`, `consumption_flexibility`, `flexibility_class` to
   `QuotaWindow` and `UseOrLoseAlert` dataclasses.
2. Add new config schema for `plans.*.window_values` and `analysis.consumption_flexibility_defaults`.
3. In each collector, compute `window_minutes` from existing data and attach
   `flexibility_class` from config defaults.
4. Compute `value_at_risk_usd` where plan price is configured.
5. Show all three dimensions in pretty report (behind `--show-consumption` flag
   initially, then always-on).
6. Include dimensions in JSON output.
7. **No scoring changes yet.**  Keep existing urgency logic.

### Phase 2 — New scoring (opt-in)

**Goal:** Implement the 3D scoring formula, default off.

1. Implement `_score_multi_dimension()` in `use_or_lose.py`.
2. Gate behind `analysis.use_multi_dim_scoring: true` config flag.
3. Compute `consumption_cycles_needed` and `earliest_start_calendar` for throttled windows.
4. Compute new urgency tier from composite score.
5. Integrate throttled-window waste accumulation tracking (`_throttled_waste_summary`).
6. Add `--alerts-only` support for the new action plan.
7. Add tests for all scoring edge cases: zero remaining, no plan price, unknown flexibility, etc.

### Phase 3 — Unified action plan (default on)

**Goal:** The new action plan format becomes the default.

1. Implement `render_action_plan()` in `report.py` with time-bucket grouping.
2. Replace current flat "Summary" section with unified plan.
3. Add `--traditional-summary` flag to get the old format.
4. Remove the `use_multi_dim_scoring` gate — new scoring is default.
5. Update README and screenshot examples.

### Phase 4 — Consumption rate learning (future)

**Goal:** Learn actual consumption rates from repeated runs.

1. Persist snapshots to `~/.cache/ai/snapshots/`.
2. On each run, diff against previous snapshot to compute *actual* `tokens_used_per_day`
   and `refill_cycles_used` per window.
3. Use learned rates to refine `consumption_flexibility` estimates.
4. Detect pattern: "you're routinely wasting 40% of your 5h blocks" → flag the
   subscription itself as questionable value.

## Testing Strategy

### Unit tests
- `_compute_flexibility_class(window_minutes, config)` — maps duration → class.
- `_value_at_risk(remaining, window_minutes, plan_price, window_values_config)` — correct dollar amounts.
- `_consumption_cycles(remaining, refill_capacity)` — integer ceiling, edge at 0.
- `_earliest_start(cycles, window_duration, resets_at)` — calendar math with tz.
- `_score_multi_dimension(value_urgency, flex_urgency, deadline_urgency, weights)` — clamping, tier mapping.
- `_throttled_waste_summary(historical_windows)` — accumulation math.

### Integration tests
- Full snapshot with mixed burstable + throttled windows → correct sort order.
- Config `plans.claude.monthly_price: 20` → 5h window value = $0.14.
- Missing plan config → value_at_risk_usd = None (graceful degradation).
- Throttled window with `earliest_start_calendar < now` → CRITICAL or HIGH.
- Burstable window with 90% remaining and 20 days → INFO or NONE.

### Golden-file tests
- Captured snapshots from real cswap/CodexBar/tokscale runs → compare alert output.

## Configuration Reference

```yaml
# config/services.yaml additions

analysis:
  # ... existing keys ...

  # Enable multi-dimensional scoring (Phase 2: opt-in, Phase 3: default on)
  use_multi_dim_scoring: false

  # Weights for composite urgency score (must sum to 1.0)
  weight_value: 0.35
  weight_flexibility: 0.30
  weight_deadline: 0.35

  # Minimum value-at-risk in USD to show an alert (filters out tiny 5h windows)
  min_value_at_risk_usd: 0.50

  # Default flexibility per window duration when the provider doesn't report
  # explicit rate-limiting behavior
  consumption_flexibility_defaults:
    5h: 0.0
    daily: 0.1
    weekly: 0.7
    monthly: 1.0

  # Max assumed tokens/minute a human can sustain (for burn-minute estimates)
  max_sustained_tokens_per_minute: 200000

plans:
  claude:
    monthly_price: 20
    window_values:          # per-refill-cycle approximate dollar value
      5h: 0.14              # $20 / (30 days * 24h / 5h window) = $0.139
      weekly: 4.62          # $20 / 4.33 weeks
      monthly: 20.0
  codex:
    monthly_price: 20
    window_values:
      weekly: 4.62
      monthly: 20.0
  grok:
    monthly_price: 30
    window_values:
      weekly: 6.93
      monthly: 30.0
  # ... per-provider ...
```
