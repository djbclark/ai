# Pretty display: Rich renderables, not Textual

**Decision (2026-07-24):** TTY pretty output uses **Rich** (non-`Layout`
renderables printed sequentially). Do **not** use Textual or Rich `Layout`
for the default report.

## Why Textual was the wrong fit

`ai` prints a **long static report** that must remain in the terminal
scrollback (detail first, compact **at a glance** trailer last). Textual and
Rich `Layout` are **viewport-oriented**: they claim a rectangular region and
redraw inside it. That design is fundamentally at odds with “dump every line
into the scrollback.”

| Approach | Layout help | Scrollback? |
| --- | --- | --- |
| Rich without `Layout` (Panel, Table, Rule, Group, Columns, …) | Strong | **Yes** |
| Rich `Layout` | Strong (grids) | No — clipped to terminal height |
| Textual (inline or full-screen) | Strongest | No — viewport + redraw |
| Plain `print` | None | Yes |

There is no mature library that gives Textual-style declarative layout *and*
then expands the finished result as ordinary lines into scrollback. For this
CLI, Rich’s lower-level renderables (or sequential `console.print`) are the
practical choice.

## Implementation

- Gate: `ai.tui.should_use_tui` (TTY, not `--json` / `--alerts-only` / `--no-tui`)
- Build: `ai.tui.builders.build_report_sections` (shared wording with classic path)
- Print: `ai.tui.app.run_usage_app` → `rich.console.Console` + Rule / Group / Panel
- Fallback: classic `render_report` string path when not a TTY or `--no-tui`

`--no-tui` keeps the classic plain-text report (name is historical).
