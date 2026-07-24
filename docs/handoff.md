# Session handoff (current)

**Date:** 2026-07-24  
**Branch:** `main`  
**Local tree:** `~/src/aiuse` (reopen Cursor here — old `~/src/ai` is gone)  
**Remote:** https://github.com/djbclark/aiuse  
**Tests:** `.venv/bin/python -m pytest -q` — expect **200+** passing  
**Version:** **2.1.0** (first release of renamed `aiuse`; git `v2.0.0` is historical pre-rename)

Fresh agents: start at [`AGENTS.md`](../AGENTS.md). This file is the short
“where we left off” note so the next session does not re-discover status.

## Reopen checklist (operator)

1. Open Cursor workspace at **`~/src/aiuse`** (not `~/src/ai`).
2. Confirm config: `aiuse doctor` should show `~/.config/aiuse/`.
3. Optional: delete backup dirs when satisfied —
   `~/.config/ai.bak-migrated-to-aiuse`, `~/.cache/ai.bak-migrated-to-aiuse`.

## Done this stretch (do not re-open unless asked)

| Area | Notes |
| --- | --- |
| Fix plan Steps **1–32** + **34** | Review-derived correctness pass complete |
| Package rename | Python package + CLI **`aiuse`**; stub **`ai`** → same entrypoint |
| GitHub + local path | Repo `djbclark/aiuse`; working tree `~/src/aiuse` |
| Config dir | **`~/.config/aiuse/` only** — local files migrated; legacy `~/.config/ai/` no longer read |
| Cache | Snapshots under `~/.cache/aiuse/snapshots` |
| Pretty / priority ladder | Rich stdout ladder; meta on stderr; `--full` long report — [`pretty-display.md`](pretty-display.md) |
| Cursor / OpenCode Go quota | Docs: [`cursor-quota.md`](cursor-quota.md), [`opencode-go-quota.md`](opencode-go-quota.md) |
| Packaging (in progress) | `LICENSE`, `2.1.0`, `python -m build` + twine check green, publish workflow, Homebrew formula draft — see below |

Recent commits: `git log -8 --oneline`

## Operator preferences (standing)

- **Commit early/often; push after every commit** without waiting for per-push OK.
- Do **not** install/configure/authenticate `cswap` / `codexbar` / `tokscale` as part of code changes.
- Do **not** use ccusage / local JSONL as plan 5h/7d authority.
- Open-ended “what next?” → **do not restart fix plan at Step 1**.

## Loose ends / next options

### Packaging — remaining operator clicks (E)

1. **PyPI Trusted Publishing** (one-time): create pending publisher for project
   `aiuse`, workflow `publish.yml`, environment `pypi` — then publish GitHub
   Release `v2.1.0` so Actions uploads. Details: [`packaging.md`](packaging.md).
2. **Homebrew sha256**: after `v2.1.0` tag is on GitHub, fill
   `sha256` in [`packaging/homebrew/aiuse.rb`](../packaging/homebrew/aiuse.rb)
   and sync to tap `djbclark/homebrew-aiuse`.

### Blocked (only when upstream lands)

1. **Step 33 — consume cswap last-good JSON**  
   Upstream: [realiti4/claude-swap#170](https://github.com/realiti4/claude-swap/issues/170)  
   Ours: [djbclark/aiuse#1](https://github.com/djbclark/aiuse/issues/1)  
   Work: prefer `lastGoodUsage` (+ age) in `collectors/cswap.py`; keep cache hydrate as fallback; document min cswap version.

### Explicitly deferred (operator owns or said no)

| Item | Status |
| --- | --- |
| **A — Live smoke checklist** | Operator said they will do later |
| **Step 35 — local burn (ccusage)** | Do not start unless asked |
| **E — Packaging finish** | Code/docs/workflow ready; PyPI publisher + release + brew sha256 left |
| **G — History burn insights** | Not started |
| **H — Cron/LaunchAgent recipe** | Not started (exit codes + JSON contract already enable it) |

### Suggested if operator wants more product work

Small: live smoke (A), cron recipe (H), finish packaging clicks (E).  
Medium: history-backed pace note, consume #170 when merged.

## Key paths

| Path | Why |
| --- | --- |
| [`AGENTS.md`](../AGENTS.md) | Priorities, conventions, persistence |
| [`README.md`](../README.md) | Install, flags, daily workflow, exit codes |
| [`docs/packaging.md`](packaging.md) | pipx / PyPI / Homebrew |
| [`docs/pretty-display.md`](pretty-display.md) | Rich priority ladder |
| [`docs/json-contract.md`](json-contract.md) | Stable JSON for scripts |
| [`src/aiuse/`](../src/aiuse/) | Package source |
| [`completions/`](../completions/) | bash/zsh (`aiuse.*`; old `ai.*` sources them) |

## Quick verification for next agent

```bash
cd ~/src/aiuse
.venv/bin/python -m pytest -q
aiuse doctor          # config dir must be ~/.config/aiuse
aiuse --brief -q
aiuse --full -q
```

## Handoff rule

When ending a session with durable state: update **this file** and
[`AGENTS.md`](../AGENTS.md) active priorities, commit, push. Keep
[`memory/MEMORY.md`](memory/MEMORY.md) as an index only.
