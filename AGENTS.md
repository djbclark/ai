# Agent entry point

This file is where an AI agent working in this repository should start. It
exists specifically so a fresh agent session — with no prior context — can
find what it needs in one hop instead of re-discovering the repo's shape.

**Mutual links:** this file, [`README.md`](README.md), and
[`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md) all link
to each other, each near the top of the file, so landing on any one of the
three gets you to the other two immediately.

## Active priorities (what to do next)

**Status (2026-07-23):** fix-plan Steps **1–32** and **34** are done. There is
no mandatory numbered step left. When the operator asks “what next?” without a
more specific goal, **do not restart at Step 1** — offer choices from the list
below (or ask what they want to work on).

1. **Blocked / wait on upstream (Step 33).** When
   [realiti4/claude-swap#170](https://github.com/realiti4/claude-swap/issues/170)
   merges, consume official `lastGoodUsage` fields in `collectors/cswap.py`
   (cache hydration becomes fallback). Tracked here:
   [djbclark/ai#1](https://github.com/djbclark/ai/issues/1). Design notes:
   [`docs/cswap-reliability.md`](docs/cswap-reliability.md).
2. **Operator-driven product work** — polish, UX, packaging, docs, live smoke,
   new features. Nothing is queued until the operator picks an item.
3. **Parked optional (do not start unless asked):**
   - **Step 35** — local ccusage / stats-cache burn section (activity only; not
     plan 5h/7d authority). See plan Phase 7 and
     [`docs/claude-local-usage.md`](docs/claude-local-usage.md).
4. **Historical:** full step list and rationale remain in
   [`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md) and
   [`docs/code-review-2026-07-23.html`](docs/code-review-2026-07-23.html).

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
| `docs/fix-implementation-plan.md` | Review-derived task list (Steps 1–32 + Phase 7 optional 33–35). **1–32 and 34 done.** | Historical scope / remaining optional steps only. |
| `docs/json-contract.md` | Stable `ai --json` fields and exit codes for scripts. | Cron / automation consumers. |
| `docs/collector-concurrency.md` | How collectors run in parallel and timeout (45s). | Perf / hang questions. |
| `completions/` | bash/zsh completion scripts. | Shell UX. |
| `https://github.com/djbclark/ai/issues/1` | Tracks consuming cswap#170 last-good JSON (Step 33). | When #170 merges or when checking upstream status. |
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

1. Check **Active priorities** above. Open-ended “what next?” → summarize status
   and offer choices (upstream Step 33 when unblocked, product polish, or
   parked Step 35). Do **not** restart the completed Steps 1–32.
2. For remaining optional plan work (33, 35), read the matching section in
   `docs/fix-implementation-plan.md` and any linked issue (ai#1 for 33).
3. If the task is not in the plan, check `docs/code-review-2026-07-23.html` and
   existing `docs/` before starting fresh analysis.
4. When implementing: full pytest before and after (`.venv/bin/python -m pytest
   -q`); one coherent change at a time; commit early and push (see
   Conventions).

## Conventions

- Python 3.14, `src/` layout, dependencies via `pyproject.toml` + `.venv`.
- Run tests with `.venv/bin/python -m pytest -q` (currently 80+ passing).
- This repo shells out to three external tools that must already be
  installed/authenticated (`cswap`, `codexbar`, `tokscale`) — do not attempt
  to install, configure, or authenticate them as part of a code change.
- **Commit early and often; push after every commit.** Prefer a commit at any
  opportune moment (green tests after a coherent change, end of a plan step,
  finished investigation docs) over holding a large uncommitted pile. More
  commits are better than fewer. After each commit, `git push` to the remote
  unless there is a concrete reason not to (e.g. the operator said not to, or
  the branch is deliberately local-only). Do not wait for separate push
  authorization.
