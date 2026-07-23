# Agent entry point

This file is where an AI agent working in this repository should start. It
exists specifically so a fresh agent session — with no prior context — can
find what it needs in one hop instead of re-discovering the repo's shape.

**Mutual links:** this file, [`README.md`](README.md), and
[`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md) all link
to each other, each near the top of the file, so landing on any one of the
three gets you to the other two immediately.

## Active priorities (what to do next)

1. Follow [`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md)
   (one step at a time, full pytest before/after). When asking “what next?”
   without a more specific goal, start at **Step 1**.
2. **cswap reliability** — initial fix landed (cache hydrate, countdown
   recompute, selection fallback). Design:
   [`docs/cswap-reliability.md`](docs/cswap-reliability.md). Optional tail
   items are **Phase 7 / Steps 33–35** of the fix plan (upstream JSON fields,
   usage-credits, optional ccusage burn section) — do not start unless
   prioritized after Steps 1–32.

## Persistence policy: durable project knowledge goes in this git repo

**If you are an AI agent — any tool, not just Claude Code — and you produce
something about this project that a *future* agent session or a *different*
tool should be able to find, put it under version control here, not in your
own tool's private local state.** That means not Claude Code's per-machine
memory store, not `.cursor/`, not `.aider.chat.history.md`, not `.copilot/`,
not any other tool-specific cache/history/rules directory. Concretely:

- Findings, designs, plans, decisions → a file under `docs/`, linked from
  this file and from `README.md`'s "Related reading".
- A reusable script/tool config that produced a checked-in doc → check the
  script in next to what it produced (see `docs/review-workflow.js`).
- Claude / vendor memory is fine as a *working* scratchpad inside one session;
  before ending a task, promote anything durable into a repo-tracked file.
  Prefer **not** duplicating long essays under `docs/memory/` when
  `AGENTS.md` or another doc already states the rule (token cost for agents
  that load both).

### Claude memory symlink (this project)

`~/.claude/projects/-Users-djbclark-src-ai/memory` is a **symlink** to
[`docs/memory/`](docs/memory/) in this repo. Keep that directory thin
([`MEMORY.md`](docs/memory/MEMORY.md) index only unless a short pointer is
truly needed). Writing a Claude memory for this project *is* writing into this
git tree — commit it if it should persist.

### Generic / private memory (sibling ops repo — not a symlink from here)

Cross-project private notes live in `~/ops/site-private` (Claude home-scoped
memory symlinks there). From this repo, **document** both forms — do not add
an in-repo symlink:

- Filesystem: `~/ops/site-private/memory/` and
  `~/ops/site-private/AGENTS.md`
- HTTPS:
  [memory/MEMORY.md](https://github.com/djbclark/site-private/blob/master/memory/MEMORY.md),
  [AGENTS.md](https://github.com/djbclark/site-private/blob/master/AGENTS.md)

Broader three-way ops policy (stayturgid / site-`<name>` / site-private) starts
at
[stayturgid AGENTS.md](https://github.com/djbclark/stayturgid/blob/master/AGENTS.md)
(`~/ops/stayturgid/AGENTS.md`). Independent projects like this one keep
project knowledge in **their own** repo.

**Never commit passwords or secrets.** IPs/hostnames are fine.

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
| `AGENTS.md` (this file) | Agent orientation, doc map, persistence policy, **active priorities**. | First, for "where is everything / what next." |
| `docs/fix-implementation-plan.md` | Step-by-step task list from the 2026-07-23 review (32 steps / 6 phases). | Before bug-fix or feature work already scoped there. |
| `docs/cswap-reliability.md` | Claude/cswap reliability: decision-stale JSON, cache hydration, fallbacks. | When Claude rows go missing or multi-account looks wrong. |
| `docs/claude-local-usage.md` | Local `stats-cache` / JSONL / ccusage vs subscription 5h/7d %. | When someone proposes parsing `~/.claude` instead of cswap. |
| `docs/code-review-2026-07-23.html` | Adversarial code review (45 findings) that the plan was derived from. Open in a browser. | For the *why* behind a plan step. |
| `docs/consumption-flexibility-plan.md` | Original scoring design. **Superseded** by pace-based scoring in the fix plan Phase 2. | Historical context only. |
| `docs/review-workflow.js` | Workflow script that generated the review. | Methodology / re-run. |
| `docs/memory/` | Thin Claude memory symlink target for this project (`MEMORY.md` index). | Rarely — prefer this file and `docs/` prose. |
| `src/ai/` | Source: collectors, analysis, report, cli, config, models. | When implementing. |
| `tests/` | Pytest suite. | Run `.venv/bin/python -m pytest -q` before and after any change. |
| `config/services.example.yaml` | Example user config. | Keep in sync with `config.py`'s `DEFAULT_CONFIG`. |

## If you were asked to fix a bug or implement a feature here

1. Check **Active priorities** above — if the ask is open-ended “what next,”
   start at **Step 1** of the fix plan (unless the operator re-opens cswap
   follow-ups listed at the plan tail).
2. Check `docs/fix-implementation-plan.md` — the task is often already scoped
   there with exact fix and test.
3. If it isn't in the plan, check `docs/code-review-2026-07-23.html` before
   starting fresh analysis.
4. Follow the plan's operating rules when working a numbered step: one step at
   a time, full test suite before and after, don't skip ahead.

## Conventions

- Python 3.14, `src/` layout, dependencies via `pyproject.toml` + `.venv`.
- Run tests with `.venv/bin/python -m pytest -q` (currently 80+ passing).
- This repo shells out to three external tools that must already be
  installed/authenticated (`cswap`, `codexbar`, `tokscale`) — do not attempt
  to install, configure, or authenticate them as part of a code change.
- **Commit early and often.** Prefer a commit at any opportune moment (green
  tests after a coherent change, end of a plan step, finished investigation
  docs) over holding a large uncommitted pile. More commits are better than
  fewer. When the operator has authorized pushes for the session or says
  “push,” push after commits rather than batching for later.
