# Agent entry point

This file is where an AI agent working in this repository should start. It
exists specifically so a fresh agent session — with no prior context — can
find what it needs in one hop instead of re-discovering the repo's shape.

**Mutual links:** this file, [`README.md`](README.md), and
[`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md) all link
to each other, each near the top of the file, so landing on any one of the
three gets you to the other two immediately.

## What this project is

`ai` is a CLI that aggregates live AI-subscription quota data (Claude, Codex,
Copilot, Grok, Gemini/Antigravity, OpenCode Go, prepaid balances, …) from
three external tools already on `PATH` (`cswap`, `CodexBar`, `tokscale`), then
tells the user what to burn before it resets unused. See `README.md` for the
full description, install steps, CLI flags, and config.

## Where things live

| Path | What it is | When to read it |
| --- | --- | --- |
| `README.md` | Project overview: install, usage, CLI flags, config, output format. | First, for "what does this tool do / how do I run it." |
| `AGENTS.md` (this file) | Agent orientation and doc map. | First, for "where is everything." |
| `docs/fix-implementation-plan.md` | **The current, actionable, step-by-step task list.** 32 steps across 6 phases (showstopper bugs → rating-algorithm redesign → everything else), each with exact files/functions, the bug, the fix, and a test gate. | Before doing any bug-fix or feature work in this repo — check whether the task is already scoped as a step here. |
| `docs/code-review-2026-07-23.html` | The adversarial code review (45 findings, 79 agents) that `fix-implementation-plan.md` was derived from. Open directly in a browser — GitHub's file viewer shows it as source, not rendered HTML. | For the *why* and full evidence behind a specific plan step, or before adding a new finding (check it isn't already documented here). |
| `docs/consumption-flexibility-plan.md` | Original design doc for the multi-dimensional scoring model. **Superseded** — the review found bugs in this design's implementation, and `fix-implementation-plan.md` Phase 2 replaces its scoring mechanics with pace-based scoring. Still accurate as problem-framing background. | For historical context on why scoring has a value/flexibility/deadline split at all. |
| `src/ai/` | Source: `collectors/` (cswap, CodexBar, tokscale, plus `runner.py` orchestration), `analysis/` (`use_or_lose.py` scoring, `history.py` snapshot learning), `report.py`, `cli.py`, `config.py`, `models.py`. | When implementing. |
| `tests/` | Pytest suite, one file per module roughly mirroring `src/ai/`. | Run `.venv/bin/python -m pytest -q` before and after any change. |
| `config/services.example.yaml` | Example user config (copy to `$XDG_CONFIG_HOME/ai/services.yaml`). | When touching `config.py`'s `DEFAULT_CONFIG` — keep this example in sync. |

## If you were asked to fix a bug or implement a feature here

1. Check `docs/fix-implementation-plan.md` first — the task is very likely
   already scoped there as a numbered step, with the exact fix and test
   specified, so implementing it should not require re-deriving anything.
2. If it isn't in the plan, check `docs/code-review-2026-07-23.html` for
   related findings before starting fresh analysis.
3. Follow the plan's own operating rules (top of that file): one step at a
   time, run the full test suite before and after, don't skip ahead.

## Conventions

- Python 3.14, `src/` layout, dependencies via `pyproject.toml` + `.venv`.
- Run tests with `.venv/bin/python -m pytest -q` (currently 80+ passing).
- This repo shells out to three external tools that must already be
  installed/authenticated (`cswap`, `codexbar`, `tokscale`) — do not attempt
  to install, configure, or authenticate them as part of a code change.
