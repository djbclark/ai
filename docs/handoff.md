# Session handoff (current)

**Date:** 2026-07-24  
**Branch:** `main`  
**Local tree:** `~/src/aiuse`  
**Remote:** https://github.com/djbclark/aiuse  
**Tests:** `.venv/bin/python -m pytest -q` — expect **200+** passing  
**Version:** **2.1.1**

Fresh agents: start at [`AGENTS.md`](../AGENTS.md).

## Reopen checklist (operator)

1. Open Cursor workspace at **`~/src/aiuse`**.
2. Confirm config: `aiuse doctor` → `~/.config/aiuse/`.
3. Optional: LaunchAgent is managed by site-djbclark —
   `cd ~/ops/site-djbclark && just site-agents-apply`
   ([`scheduling.md`](scheduling.md)).

## Done this stretch

| Area                             | Notes                                                                                              |
| -------------------------------- | -------------------------------------------------------------------------------------------------- |
| Fix plan Steps **1–32** + **34** | Complete                                                                                           |
| Package rename / packaging       | **aiuse** on PyPI + Homebrew + OIDC                                                                |
| **H — LaunchAgent**              | Recipe + `install.sh`; 6h; `persist_snapshots`                                                     |
| **G — History (thin)**           | `persist_snapshots` decoupled; `--full` history line; [`history-learning.md`](history-learning.md) |

## Packaging / scheduling

| Channel                | State                                           |
| ---------------------- | ----------------------------------------------- |
| PyPI / Homebrew / OIDC | Done                                            |
| LaunchAgent            | Docs + template — operator runs `install.sh`    |
| `learn_from_history`   | Still **opt-in** (enable after snapshots exist) |

## Operator preferences (standing)

- Commit early/often; push after every commit (SSH for workflow files).
- Do not install/configure `cswap` / `codexbar` / `tokscale` in code changes.
- Do not use ccusage as plan 5h/7d authority.
- Open-ended “what next?” → **do not restart fix plan at Step 1**.

## Loose ends / next options

### Blocked (upstream)

1. **Step 33** — [claude-swap#170](https://github.com/realiti4/claude-swap/issues/170) → [aiuse#1](https://github.com/djbclark/aiuse/issues/1)

### Deferred

| Item                        | Status                                          |
| --------------------------- | ----------------------------------------------- |
| **A — Live smoke**          | Operator-owned                                  |
| **Step 35**                 | Parked                                          |
| **E — Packaging**           | Done                                            |
| **H — LaunchAgent**         | Recipe done; operator installs when ready       |
| **G — History learning on** | Opt-in after snapshots; richer insights later   |
| **G deeper UX**             | Thin status line done; more report polish later |

## Quick verification

```bash
cd ~/src/aiuse
.venv/bin/python -m pytest -q
aiuse doctor
# after enabling persist_snapshots:
aiuse --full -q --no-tui | head -15
```

## Handoff rule

Update **this file** + [`AGENTS.md`](../AGENTS.md) when ending a session with
durable state; commit and push.
