---
name: feedback-git-over-memory
description: "In ~/src/ai, durable project knowledge belongs in the git repo, not in Claude Code's private memory store"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c04f00b5-2340-47fc-990c-a0ab34c4c72f
---

For the `ai` project (`~/src/ai`), write anything durable — findings, designs,
plans, decisions, reusable scripts that produced a checked-in doc — into the
git repo (typically `docs/`, linked from `AGENTS.md` and `README.md`), not
into this memory store.

**Why:** on 2026-07-23 I wrote a review handoff into Claude Code memory
(outside git) when a workflow got interrupted by usage-credit exhaustion.
After the work finished, the user explicitly asked me to move it (and
anything else outside git) into the repo instead, then to make that the
standing policy: "make sure that this also applies to anything in the future
— we want everything in git, not in .claude." They also asked me to check for
similar hiding spots from other agent tools (`.cursor`, `.aider`, `.copilot`,
etc.) — none existed for this project, but the request implies the same rule
applies regardless of which tool produced the content.

**How to apply:** memory here is fine as a *working* scratchpad within a
single session (e.g. a mid-workflow checkpoint in case of interruption), but
before ending a task, promote anything a future session or a different tool
would need into a repo-tracked file, and link it from
[[AGENTS.md]] (this project now has one — it's the entry point and states
this same policy explicitly, see its "Persistence policy" section) and from
`README.md`. Don't leave the durable copy only in memory once the repo copy
can exist. This preference is specific to this project, not a general rule
about my memory system — other projects may not have made this ask.
