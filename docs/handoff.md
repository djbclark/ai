# Session handoff (current)

**Date:** 2026-07-24  
**Branch:** `main`  
**Tests:** `.venv/bin/python -m pytest -q` — **190** passing

Fresh agents: start at [`AGENTS.md`](../AGENTS.md). This file is the short
“where we left off” note so the next session does not re-discover status.

## Done (do not re-open unless asked)

| Area | Notes |
| --- | --- |
| Fix plan Steps **1–32** | Review-derived correctness pass complete |
| Step **34** | cswap `usage.spend` → `UsageCredits` + pretty section |
| cswap reliability (interim) | Cache hydrate, countdown recompute, CodexBar/tokscale fallback — [`cswap-reliability.md`](cswap-reliability.md) |
| Tracker | [ai#1](https://github.com/djbclark/ai/issues/1) documents consumer contract for upstream #170 |
| CLI discoverability | `ai doctor`, `--help` epilog, `--generate-config` under `~/.config/ai/` |
| Product polish batch | Exit codes 0/1/2, `-q`, soft cross-checks, daily workflow README |
| Second polish batch | Doctor version probe + config validation, `--brief`, completions, JSON contract, concurrency audit |
| Action plan last | Report ends on action plan (≤~23×80); if detailed is taller, detailed + **at a glance** brief trailer |
| **OpenCode Go quota** | Prefer CodexBar `--source web` for `opencodego` (local SQLite/$caps heuristic lied vs TUI “limit reached”); `opencode` shared_allotment on; docs — [`opencode-go-quota.md`](opencode-go-quota.md) |
| **Styled pretty output** | TTY pretty path uses Rich (full scrollback); at-a-glance plan last, ≤3 alert lines/provider; `--no-tui` / pipes keep classic text |

Recent commits (newest first): see `git log -5 --oneline`

## Operator preferences (standing)

- **Commit early/often; push after every commit** without waiting for per-push OK.
- Do **not** install/configure/authenticate `cswap` / `codexbar` / `tokscale` as part of code changes.
- Do **not** use ccusage / local JSONL as plan 5h/7d authority.
- Open-ended “what next?” → **do not restart fix plan at Step 1**.

## Loose ends / next options

### Blocked (only when upstream lands)

1. **Step 33 — consume cswap last-good JSON**  
   Upstream: [realiti4/claude-swap#170](https://github.com/realiti4/claude-swap/issues/170)  
   Ours: [djbclark/ai#1](https://github.com/djbclark/ai/issues/1)  
   Work: prefer `lastGoodUsage` (+ age) in `collectors/cswap.py`; keep cache hydrate as fallback; document min cswap version.

### Explicitly deferred (operator owns or said no)

| Item | Status |
| --- | --- |
| **A — Live smoke checklist** | Operator said they will do later (manual multi-account Claude / credits / exit codes) |
| **Step 35 — local burn (ccusage)** | Do not start unless asked |
| **E — Packaging** (Homebrew/pipx) | Not started |
| **G — History burn insights** | Not started |
| **H — Cron/LaunchAgent recipe** | Not started (exit codes + JSON contract already enable it) |

### Suggested if operator wants more product work

Small: live smoke (A), cron recipe (H), packaging (C/E).  
Medium: history-backed pace note, consume #170 when merged.

## Key paths

| Path | Why |
| --- | --- |
| [`AGENTS.md`](../AGENTS.md) | Priorities, conventions, persistence |
| [`README.md`](../README.md) | Install, flags, daily workflow, exit codes |
| [`docs/json-contract.md`](json-contract.md) | Stable JSON for scripts |
| [`docs/collector-concurrency.md`](collector-concurrency.md) | Parallel collect + 45s timeouts |
| [`docs/cswap-reliability.md`](cswap-reliability.md) | Claude multi-account / stale JSON |
| [`docs/opencode-go-quota.md`](opencode-go-quota.md) | OpenCode Go web vs local CodexBar source |
| [`docs/fix-implementation-plan.md`](fix-implementation-plan.md) | Historical steps + Phase 7 optional |
| [`src/ai/cli.py`](../src/ai/cli.py) | doctor, exit codes, quiet, brief, completions |
| [`src/ai/collectors/cswap.py`](../src/ai/collectors/cswap.py) | Claude collect + hydrate |
| [`src/ai/collectors/codexbar.py`](../src/ai/collectors/codexbar.py) | CodexBar fan-out; OpenCode Go prefers `--source web` |
| [`src/ai/tui/`](../src/ai/tui/) | Styled Rich pretty report (full scrollback) |
| [`completions/`](../completions/) | bash/zsh |

## Quick verification for next agent

```bash
.venv/bin/python -m pytest -q
ai doctor
ai --brief -q
# OpenCode Go should match TUI when cookies work:
codexbar usage --provider opencodego --source web --no-color
```

## Handoff rule

When ending a session with durable state: update **this file** and
[`AGENTS.md`](../AGENTS.md) active priorities, commit, push. Keep
[`memory/MEMORY.md`](memory/MEMORY.md) as an index only.
