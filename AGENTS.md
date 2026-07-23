# Agent entry point

This file is where an AI agent working in this repository should start. It
exists specifically so a fresh agent session — with no prior context — can
find what it needs in one hop instead of re-discovering the repo's shape.

**Mutual links:** this file, [`README.md`](README.md), and
[`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md) all link
to each other, each near the top of the file, so landing on any one of the
three gets you to the other two immediately.

## Persistence policy: durable project knowledge goes in this git repo

**If you are an AI agent — any tool, not just Claude Code — and you produce
something about this project that a *future* agent session or a *different*
tool should be able to find, put it under version control here, not in your
own tool's private local state.** That means not Claude Code's per-machine
memory store, not `.cursor/`, not `.aider.chat.history.md`, not `.copilot/`,
not any other tool-specific cache/history/rules directory — those live
outside git, are invisible to collaborators and to every other tool, and
(per an explicit ask on 2026-07-23) are not where this project wants anything
load-bearing to live. Concretely:

- Findings, designs, plans, decisions → a file under `docs/`, linked from
  `AGENTS.md`'s table above and from `README.md`'s "Related reading".
- A reusable script/tool config that produced a checked-in doc (e.g. the
  workflow that generated a review) → check the script in next to what it
  produced (see `docs/review-workflow.js`), not just in whatever ran it.
- If your own tool's persistent-memory feature is where you'd normally jot
  this down (Claude Code memory, Cursor rules, etc.) — still write the
  durable version into this repo. Local tool memory can be a *working*
  notepad for a single session, but treat anything meant to outlive that
  session as belonging in git first.
- `docs/agent-memory-snapshot.md` exists because this was retrofitted after
  the fact once for Claude Code's memory specifically — don't let that debt
  reaccumulate; check things in as you go instead of needing another sweep.

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
| `docs/review-workflow.js` | The Claude Code Workflow script that generated the review — not runnable outside that tool, checked in for methodology transparency/reproducibility. | If you need to know exactly what each review agent was asked, or want to re-run/extend the review. |
| `docs/agent-memory-snapshot.md` | Point-in-time export of this project's Claude Code persistent memory (which otherwise lives outside git, per-machine). May drift from the live memory store over time. | If a prior agent session's memory notes are referenced and you don't have local memory access. |
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
