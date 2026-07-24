# Collector concurrency and timeouts

Audit of how `ai` shells out to external tools (post 45s default timeout policy).
No code change required from this write-up unless noted.

## Architecture (wall-clock)

```
ai main
 └─ run_collectors (ThreadPoolExecutor, max_workers = N enabled collectors ≤ 3)
     ├─ collect_cswap        → one `cswap list --json` (timeout: cswap)
     ├─ collect_codexbar     → discovery + concurrent per-provider queries
     └─ collect_tokscale     → one `tokscale usage --json` (timeout: tokscale)
```

**Wall-clock cost ≈ max(collector durations)**, not the sum, while all three
are enabled and healthy. Sequential would be sum(cswap + codexbar + tokscale).

## Defaults

| Knob | Default | Where |
| --- | --- | --- |
| `timeouts.default` | **45s** | `config.toml` / built-in |
| Per-tool keys | inherit default | `cswap`, `codexbar`, `codexbar_discovery`, `tokscale` |
| CLI `-t` / `--timeout` | sets `timeouts.force` | wins over every tool for that run |
| Doctor version probe | **5s** hard cap | does not use usage endpoints |

Tools either return in tens of seconds or hang; long budgets only delay failure
(see fix-plan history: 180s → 45s).

## Per-collector detail

### cswap

- Single subprocess: `cswap list --json`.
- Timeout: `timeout_for(config, "cswap")`.
- Multi-account JSON; may hydrate from on-disk last-good when decision-stale
  (see [cswap-reliability.md](cswap-reliability.md)).

### CodexBar

- Discovers enabled providers (`codexbar config providers` or equivalent),
  timeout `codexbar_discovery` (usually milliseconds).
- Then **one subprocess per provider**, concurrent via `ThreadPoolExecutor`,
  capped at **`_MAX_CONCURRENT_PROVIDER_QUERIES = 16`**.
- Per-provider timeout: `timeout_for(config, "codexbar")` (full 45s budget
  **each** — a stuck provider can hold its own slot that long).
- Rationale: bundled “all enabled” calls inside CodexBar are serial; fan-out
  makes wall-clock ≈ slowest provider, not sum.

### tokscale

- Single subprocess: `tokscale usage --json`.
- Timeout: `timeout_for(config, "tokscale")` (45s).
- No per-provider fan-out today — investigation:
  [tokscale-per-provider-investigation.md](tokscale-per-provider-investigation.md).

## Executor lifecycle note

`run_collectors` submits all jobs inside a `with ThreadPoolExecutor(...)` block,
then reads `.result()` **after** the context exits. Exiting the context calls
`shutdown(wait=True)`, so work is finished before results are collected. Correct,
if slightly unusual; do not “optimize” by dropping `wait` without also moving
result collection inside the `with` block.

## Failure isolation

- A raised exception from one collector becomes a `snapshot.collector_errors`
  string; other collectors still contribute accounts.
- CodexBar partial provider failures can attach an error row without wiping
  successful providers.
- Exit code **1** only when there are errors **and** zero accounts overall.

## What looks healthy

| Scenario | Expected |
| --- | --- |
| All three tools warm / cached | Often **under ~5–15s** wall-clock |
| Cold CodexBar multi-provider | Dominated by slowest provider; still **≤ 45s** per provider slot |
| tokscale hang | Fails that collector at 45s; cswap + codexbar still usable |
| `ai -t 10` | Every tool forced to 10s (faster fail for scripts) |

## Recommendations (standing)

1. Keep **45s** as default; use `-t` only for tighter scripts.
2. Prefer `--no-tokscale` when iterating on Claude-only workflows if tokscale is slow.
3. Use `aiuse doctor` for PATH + version probe; full usage still needs `ai`.
4. Do not raise global timeout back toward 180s without evidence a tool needs it.

## Code map

| Piece | Path |
| --- | --- |
| Concurrent top-level collect | `src/ai/collectors/runner.py` → `run_collectors` |
| CodexBar provider fan-out | `src/ai/collectors/codexbar.py` → `_query_providers` |
| Timeout resolution | `src/ai/config.py` → `timeout_for` |
| Doctor probe | `src/ai/cli.py` → `probe_tool_version` |
