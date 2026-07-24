# Session handoff (current)

**Date:** 2026-07-24  
**Branch:** `main`  
**Local tree:** `~/src/aiuse`  
**Remote:** https://github.com/djbclark/aiuse  
**Tests:** `.venv/bin/python -m pytest -q` — expect **200+** passing  
**Version:** **2.1.0** — [release](https://github.com/djbclark/aiuse/releases/tag/v2.1.0)

Fresh agents: start at [`AGENTS.md`](../AGENTS.md).

## Reopen checklist (operator)

1. Open Cursor workspace at **`~/src/aiuse`** (not `~/src/ai`).
2. Confirm config: `aiuse doctor` should show `~/.config/aiuse/`.
3. Optional: delete backup dirs when satisfied —
   `~/.config/ai.bak-migrated-to-aiuse`, `~/.cache/ai.bak-migrated-to-aiuse`.

## Done this stretch

| Area                             | Notes                                                                       |
| -------------------------------- | --------------------------------------------------------------------------- |
| Fix plan Steps **1–32** + **34** | Complete                                                                    |
| Package rename                   | **`aiuse`** + stub **`ai`**                                                 |
| Config / cache                   | `~/.config/aiuse/`, `~/.cache/aiuse/`                                       |
| Packaging **2.1.0**              | LICENSE, GitHub Release, Homebrew tap, **PyPI live** (`pipx install aiuse`) |

## Packaging status (E)

| Channel                   | State                                             |
| ------------------------- | ------------------------------------------------- |
| GitHub Release `v2.1.0`   | Done                                              |
| Homebrew `djbclark/aiuse` | Done                                              |
| PyPI `aiuse` 2.1.0        | Done (token via `secretspec` / gitignored `.env`) |
| Trusted Publishing (OIDC) | Optional follow-up for CI                         |

Details: [`packaging.md`](packaging.md).

**Note:** HTTPS `git push` from this environment lacks `workflow` scope — push
workflow file changes via SSH (`git@github.com:djbclark/aiuse.git`).

## Operator preferences (standing)

- **Commit early/often; push after every commit** (SSH for workflow files).
- Do **not** install/configure/authenticate `cswap` / `codexbar` / `tokscale`.
- Do **not** use ccusage / local JSONL as plan 5h/7d authority.
- Open-ended “what next?” → **do not restart fix plan at Step 1**.

## Loose ends / next options

### Blocked (upstream)

1. **Step 33** — [claude-swap#170](https://github.com/realiti4/claude-swap/issues/170) → [aiuse#1](https://github.com/djbclark/aiuse/issues/1)

### Deferred

| Item                     | Status                                                |
| ------------------------ | ----------------------------------------------------- |
| **A — Live smoke**       | Operator-owned                                        |
| **Step 35**              | Parked                                                |
| **E — Packaging**        | PyPI + Homebrew done; OIDC trusted publisher optional |
| **G — History insights** | Not started                                           |
| **H — Cron recipe**      | Not started                                           |

## Quick verification

```bash
cd ~/src/aiuse
.venv/bin/python -m pytest -q
aiuse doctor
/opt/homebrew/bin/aiuse --version   # 2.1.0 if brew-installed
```

## Handoff rule

Update **this file** + [`AGENTS.md`](../AGENTS.md) when ending a session with
durable state; commit and push.
