# Session handoff (current)

**Date:** 2026-07-24  
**Branch:** `main`  
**Local tree:** `~/src/aiuse`  
**Remote:** https://github.com/djbclark/aiuse  
**Tests:** `.venv/bin/python -m pytest -q` — expect **200+** passing  
**Version:** **2.1.4** (PyPI + Homebrew published)

Fresh agents: start at [`AGENTS.md`](../AGENTS.md).

## Reopen checklist (operator)

1. Open Cursor workspace at **`~/src/aiuse`**.
2. Confirm config: `aiuse doctor` → `~/.config/aiuse/`.
3. LaunchAgent: managed by **site-djbclark** —
   `cd ~/ops/site-djbclark && just site-agents-apply && just site-agents-status`
   ([`scheduling.md`](scheduling.md)).

## Done this stretch

| Area                             | Notes                                                               |
| -------------------------------- | ------------------------------------------------------------------- |
| Fix plan Steps **1–32** + **34** | Complete                                                            |
| Packaging                        | **2.1.4** on PyPI + Homebrew tap                                    |
| **H — LaunchAgent**              | Live: `com.djbclark.aiuse` via site-djbclark `site_agents` (hourly) |
| **G — History UX**               | `--full` History section + blended-with-history pace notes          |

## Packaging / scheduling

| Channel                | State                                                               |
| ---------------------- | ------------------------------------------------------------------- |
| PyPI / Homebrew / OIDC | **2.1.4 published** ([release](https://github.com/djbclark/aiuse/releases/tag/v2.1.4)) |
| LaunchAgent            | **Rolled out** via `~/ops/site-djbclark` (`just site-agents-apply`) |
| `persist_snapshots`    | **true** (set by site_agents)                                       |
| `learn_from_history`   | **`auto`** — learns once ≥ 2 snapshots exist                        |

## Operator preferences (standing)

- Commit early/often; push after every commit (SSH for workflow files).
- Do not install/configure `cswap` / `codexbar` / `tokscale` in code changes.
- Do not use ccusage as plan 5h/7d authority.
- Open-ended “what next?” → **do not restart fix plan at Step 1**.
- Scheduled agents / LaunchAgents for this Mac → **site-djbclark** `site_agents`, not ad-hoc plists.

## Loose ends / next options

### Blocked (upstream)

1. **Step 33** — [claude-swap#170](https://github.com/realiti4/claude-swap/issues/170) → [aiuse#1](https://github.com/djbclark/aiuse/issues/1)

### Deferred

| Item                        | Status                                 |
| --------------------------- | -------------------------------------- |
| **A — Live smoke**          | Operator-owned                         |
| **Step 35**                 | Parked                                 |
| **E — Packaging**           | Done (**2.1.4** on PyPI + Homebrew)    |
| **H — LaunchAgent**         | Done (site-djbclark)                   |
| **G — History learning**    | **`auto`** + deeper `--full` UX        |

## Quick verification

```bash
just -f ~/ops/site-djbclark/justfile site-agents-status
aiuse --version   # 2.1.4
ls ~/.cache/aiuse/snapshots | wc -l
aiuse --full -q --no-tui | head -25
```

## Handoff rule

Update **this file** + [`AGENTS.md`](../AGENTS.md) when ending a session with
durable state; commit and push.
