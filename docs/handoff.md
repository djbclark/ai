# Session handoff (current)

**Date:** 2026-07-24  
**Branch:** `main`  
**Local tree:** `~/src/aiuse`  
**Remote:** https://github.com/djbclark/aiuse  
**Tests:** `.venv/bin/python -m pytest -q` — expect **200+** passing  
**Version:** **2.1.1** — packaging / OIDC verify release

Fresh agents: start at [`AGENTS.md`](../AGENTS.md).

## Reopen checklist (operator)

1. Open Cursor workspace at **`~/src/aiuse`** (not `~/src/ai`).
2. Confirm config: `aiuse doctor` should show `~/.config/aiuse/`.
3. Optional: delete backup dirs when satisfied —
   `~/.config/ai.bak-migrated-to-aiuse`, `~/.cache/ai.bak-migrated-to-aiuse`.

## Done this stretch

| Area                             | Notes                                                                  |
| -------------------------------- | ---------------------------------------------------------------------- |
| Fix plan Steps **1–32** + **34** | Complete                                                               |
| Package rename                   | **`aiuse`** + stub **`ai`**                                            |
| Config / cache                   | `~/.config/aiuse/`, `~/.cache/aiuse/`                                  |
| Packaging                        | PyPI + Homebrew + **Trusted Publishing (OIDC)** verified via **2.1.1** |

## Packaging status (E)

| Channel                   | State                                                    |
| ------------------------- | -------------------------------------------------------- |
| GitHub Release            | `v2.1.1`                                                 |
| Homebrew `djbclark/aiuse` | Live (refresh formula on each tag)                       |
| PyPI                      | Live (`pipx install aiuse`)                              |
| Trusted Publishing (OIDC) | Done — publisher on pypi.org; `publish.yml` + env `pypi` |

Details: [`packaging.md`](packaging.md) (OIDC fields, release checklist, brew
sha256). Optional local token: `secretspec` / `.env` (`PYPI_TOKEN`, not required).

**Proof:** [publish run `v2.1.1`](https://github.com/djbclark/aiuse/actions/runs/30099193664)
→ https://pypi.org/project/aiuse/2.1.1/

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

| Item                     | Status         |
| ------------------------ | -------------- |
| **A — Live smoke**       | Operator-owned |
| **Step 35**              | Parked         |
| **E — Packaging**        | Done           |
| **G — History insights** | Not started    |
| **H — Cron recipe**      | Not started    |

## Quick verification

```bash
cd ~/src/aiuse
.venv/bin/python -m pytest -q
aiuse doctor
aiuse --version
```

## Handoff rule

Update **this file** + [`AGENTS.md`](../AGENTS.md) when ending a session with
durable state; commit and push.
