# Agent memory snapshot

**See also:** [`../AGENTS.md`](../AGENTS.md) for the repo map, [`../README.md`](../README.md)
for the project itself.

This is a checked-in copy of Claude Code's persistent memory for this project,
exported by request so it's version-controlled instead of living only in a
local, per-machine memory store. Claude Code's memory tool always writes to a
fixed location outside any git repo
(`~/.claude/projects/<project-hash>/memory/`, keyed off the working directory,
not this repository) — checking it in here does not change where future writes
go, so **this file is a point-in-time snapshot, not a live mirror**. If you're
an AI agent maintaining this project, re-export it after any memory update
that future sessions should be able to find without local memory access.

Original files as of 2026-07-23: `MEMORY.md` (index) and
`checkpoint-ai-project-review.md` (one entry), reproduced below.

---

## `MEMORY.md` (index)

> - [ai project review — resolved](checkpoint-ai-project-review.md) — 2026-07-23 review/plan complete, checked into ~/src/ai repo (docs/, AGENTS.md); not pending work

## `checkpoint-ai-project-review.md`

```yaml
name: checkpoint-ai-project-review
description: RESOLVED — 2026-07-23 review/design/plan for ~/src/ai is complete and checked into the repo; this memory is now historical
metadata:
  type: project
```

# ai project review — complete (2026-07-23)

The multi-agent review, the two design proposals (tokscale timeout containment,
pace-based rating algorithm), and the resulting implementation plan are **done and
committed to the repo** — this memory's earlier "design synthesis pending" state no
longer applies; do not resume the workflow run referenced below.

**Everything durable now lives in the repo, not in memory:**
- `docs/code-review-2026-07-23.html` — the full review (45 findings, adversarially
  verified) and both design proposals.
- `docs/fix-implementation-plan.md` — 32-step, 6-phase implementation plan derived
  from the review (showstopper bugs → rating-algorithm redesign → everything else).
- `docs/consumption-flexibility-plan.md` — marked superseded, points to the two docs above.
- `AGENTS.md` (repo root) — entry point tying all of this together for future sessions.

None of it currently has code changes applied — the plan describes work not yet
started. If asked about "the review" or "the plan" for this project in a future
session, read the repo docs above, not this memory file or the raw
`checkpoint-ai-review-data.json` that previously sat alongside it (deleted —
it was redundant with `docs/code-review-2026-07-23.html`).

**How the repo got here** (for context only): a 79-agent Workflow run
(`wf_280ac10f-931`) did the review + verification + design panels; 5 of the design
agents hit a usage-credit limit mid-run, so the tokscale-containment design and
part of the rating-algorithm design were synthesized by hand from the completed
proposal plus verified facts rather than from a finished agent output. This is
already reflected honestly in the checked-in report's footer. The actual Workflow
script that produced the review is also checked in, at
[`review-workflow.js`](review-workflow.js).

---

## What wasn't brought into git, and why

Moving "everything outside of git" literally would also sweep in things that
shouldn't be version-controlled:

- **Raw session transcripts** (`~/.claude/projects/<project-hash>/<session-id>.jsonl`,
  1–3 MB each) — full conversation/tool-call logs for every session in this
  project, including this one. Left out: they're harness-internal, large, and
  can contain incidental sensitive content (file contents, tool arguments) that
  doesn't belong in a shared repo just because a session touched this project.
- **The scratchpad directory** (`~/.claude/projects/<project-hash>/scratch/`) —
  explicitly a temp working area; an earlier, superseded draft of the review
  workflow script lived here before it was finalized and run.
- **An unrelated prior workflow script**
  (`review-parallelization-diff-wf_e1dd295d-e73.js`, from a different, earlier
  session) — a separate adversarial review of a concurrency-focused diff, not
  part of this thread's work. Not included here since it wasn't part of what
  produced the checked-in docs; say the word if you want that session's output
  checked in too.
