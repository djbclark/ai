# ai

Aggregate live **subscription quota** and **prepaid balance** information across
your local AI tooling, then highlight allotments you should use **before they
reset** (use-it-or-lose-it).

CLI command: **`ai`**

> **AI agents:** start at [`AGENTS.md`](AGENTS.md) for a map of this repo,
> active priorities, Claude/cswap reliability notes
> ([`docs/cswap-reliability.md`](docs/cswap-reliability.md)), and
> review-derived fixes in [`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md).

## Data sources

| Tool                                                               | Purpose                                                   | Authority                                                                         |
| ------------------------------------------------------------------ | --------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [**cswap**](https://github.com/realiti4/claude-swap) `cswap list --json` | Live Claude Code quota for every configured email/account | Canonical multi-account Claude source; may hydrate from cswap’s local usage cache when JSON is decision-stale |
| [**CodexBar**](https://github.com/) `codexbar usage --format json` | Live quotas and balances for enabled providers            | Preferred for non-Claude providers; Claude fallback if cswap has no live rows     |
| [**tokscale**](https://www.npmjs.com/) `tokscale usage --json`     | Independent live subscription quota measurement           | Cross-checked against CodexBar (and Claude/cswap); selected when preferred source has no live row |

This project shells out to tools already on your `PATH`; it does not scrape billing dashboards itself. For Claude multi-account reliability (stale JSON vs cache), see [`docs/cswap-reliability.md`](docs/cswap-reliability.md).

## Install

```bash
cd /path/to/ai
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional config (standard location: **`~/.config/ai/`**, or `$XDG_CONFIG_HOME/ai/`):

```bash
# Create directories + default files (never overwrites existing files)
ai --generate-config

# Or copy examples by hand:
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/ai"
cp config/services.example.yaml "${XDG_CONFIG_HOME:-$HOME/.config}/ai/services.yaml"
cp config/config.example.toml "${XDG_CONFIG_HOME:-$HOME/.config}/ai/config.toml"
```

| File | Purpose |
| --- | --- |
| `~/.config/ai/services.yaml` | Plans, analysis thresholds, which collectors are enabled |
| `~/.config/ai/config.toml` | Tool settings: subprocess **timeouts** (default **45s**), room for more later |

Run `ai --show-config-path` to print both paths. `ai --generate-config` creates
missing parent dirs (`~/.config`, `~/.config/ai`) and writes defaults; if a file
already exists it is left alone and reported on stderr. Provider credentials stay
with cswap, CodexBar, and tokscale — these files do not hold tokens or emails.

## Usage

```bash
# Pretty human-readable report (default)
ai
ai --format pretty
ai --no-color          # plain text, no ANSI

# or without install:
PYTHONPATH=src python -m ai

# Machine-readable JSON on stdout (progress still on stderr)
ai --json
ai --format json
ai --json --alerts-only
ai --save ~/tmp/ai-snapshot.json   # also write JSON file

# Faster / partial
ai --providers copilot,grok,codex   # query these separately
ai --no-tokscale
ai --min-remaining 50 --max-days 10

# Subprocess timeout for external tools (default 45s; also in config.toml)
ai --timeout 45
ai -t45
```

| Flag                                             | Effect                                                             |
| ------------------------------------------------ | ------------------------------------------------------------------ |
| _(none)_ / `--format pretty`                     | Colorized terminal report with time-bucketed action plan (default) |
| `--json` / `--format json`                       | Full snapshot + alerts as JSON                                     |
| `--no-color`                                     | Disable ANSI colors in pretty mode                                 |
| `--alerts-only`                                  | Recommendations only (respects pretty vs json)                     |
| `--traditional-summary`                          | Legacy flat summary format instead of unified action plan          |
| `--no-tokscale` / `--no-cswap` / `--no-codexbar` | Skip specific collectors                                           |
| `--providers copilot,grok`                       | Query specific CodexBar providers (CSV, one per subprocess)        |
| `-t` / `--timeout SECONDS`                       | Force subprocess timeout for all external tools (default **45**)   |
| `--generate-config`                              | Write default `~/.config/ai/*` files; never overwrites existing    |
| `--show-config-path`                             | Print services.yaml and config.toml paths                          |
| `--min-remaining 50 --max-days 10`               | Override alert thresholds                                          |
| `--save PATH`                                    | Also write full JSON snapshot to PATH                              |

## What “use it or lose it” means

Most **subscription** coding plans (Claude Pro/Max, ChatGPT Plus/Codex, Cursor, Copilot, SuperGrok, Google AI Pro, …) grant **windows** of usage (5-hour, weekly, monthly). When the window resets, **unused capacity disappears** — you still paid for the month.

This tool:

1. Pulls **remaining %** and **reset times** from cswap for each distinct Claude Code account and from CodexBar/tokscale for other providers.
2. Scores windows across **three dimensions**: dollar value at risk, consumption flexibility (can you burst-burn it, or is it rate-limited?), and deadline pressure.
3. Generates a **time-bucketed unified action plan**: THIS WEEK / THIS WEEKEND / LATER THIS MONTH / THROTTLED ACCUMULATING WASTE.
4. Skips pure **pay-as-you-go** history and treats **prepaid API balances** (OpenRouter, etc.) as non-urgent (they usually roll until spent).
5. Compares overlapping CodexBar and tokscale measurements and reports clear consistency warnings. Claude Code remains canonical in cswap, with CodexBar used only as an account-aware cross-check when possible.
6. Shows per-window **consumption flexibility** (burstable vs semi-throttled vs throttled) and estimated dollar value at risk.

This command intentionally does not report historical local-token usage or
API-equivalent cost estimates.

## Example output

```
========================================================================
AI USAGE — USE IT OR LOSE IT
========================================================================

## Per-provider usage
------------------------------------------------------------------------
Codex · account=you@example.com · plan=plus · selected live source: CodexBar
  quota: Codex weekly quota
    [============] 100% left   0% used   resets in 6.4d (Jul 28 21:59 UTC)
    $6.90 · flex:▒ semi

## Summary — use these before they reset
------------------------------------------------------------------------
  Available capacity this cycle: $35.65 across 6 windows (5 providers).

  THIS WEEK (start now — capacity will reset or needs lead time)
  ─────────────────────────────────────────────────────────────
  .   Codex · you@example.com · Codex weekly quota: 88% left · use within 6.4 days · $6.07 at risk
      Semi-throttled — steady usage will exhaust it.
  .   OpenCode Go · default · OpenCode Go weekly quota: 98% left · use within 4.5 days · $3.37 at risk
      Burstable — one heavy session will cover it.

  LATER THIS MONTH (before next billing cycle)
  ────────────────────────────────────────────
  .   Cursor · you@example.com · Cursor monthly quota: 41% left · use within 11.4 days · $12.41 at risk
      Burstable — one heavy session will cover it.

  THROTTLED — ACCUMULATING WASTE
  ──────────────────────────────
  · Gemini 5h: 0% left per cycle (~$0.00/cycle ≈ ~$0.00/month wasted)

  PREPAID / NON-EXPIRING (no hard deadline)
  ─────────────────────────────────────────
  · openrouter: $18.90 prepaid balance
```

## Project layout

```
src/ai/
  cli.py                 # entrypoint
  collectors/            # cswap, codexbar, tokscale
  analysis/use_or_lose.py
  report.py
config/services.example.yaml
tests/
```

## Tests

```bash
just test
just check # tests plus deterministic lint, type, spelling, and format checks
just lint  # full check plus Bandit, Semgrep, and Gitleaks
just format
```

The quality suite mirrors the applicable tools from `stayturgid`: pytest, Ruff,
mypy, yamllint, markdownlint, Prettier (including TOML support), typos, Bandit,
Semgrep, Gitleaks, pre-commit, and `just`. Ansible, shell, JavaScript/CSS, dotenv,
Caddy, and browser-page checks are omitted because this repository contains none
of those corresponding inputs.

## Notes / limitations

- Live quota accuracy depends on each tool's auth (browser cookies, OAuth, keychain). Errors are reported per account rather than aborting the whole run.
- cswap, CodexBar, and tokscale run concurrently, and by default each CodexBar provider (and any explicit comma-separated `--providers` list) is queried as its own concurrent subprocess, so total runtime tracks the slowest single provider rather than the sum of all of them. `--providers all` is intentionally thorough and stays a single, slower bundled CodexBar call.
- **5-hour windows** are no longer binary-filtered -- they appear with dollar value and throttled flexibility. Their low per-cycle value naturally deprioritizes them, but accumulating waste is flagged in the THROTTLED section of the action plan.
- Per-window consumption detail ($ value, flexibility class) is shown inline with each quota window.
- Scoring uses three dimensions: value-at-risk, consumption flexibility (burstable vs rate-limited), and deadline pressure. Set `analysis.use_multi_dim_scoring: false` in config to revert to legacy scoring.
- Duplicate live measurements are retained for cross-checking but only one copy drives recommendations, preventing duplicate alerts.
- Dollar values are derived from plan `monthly_price` in config with waking-hours correction (default 16h/day).

## Related reading

- [`docs/consumption-flexibility-plan.md`](docs/consumption-flexibility-plan.md) — design rationale for the multi-dimensional scoring model.
- [`docs/code-review-2026-07-23.html`](docs/code-review-2026-07-23.html) — a 79-agent adversarial code review (45 findings) plus design proposals for containing tokscale's collector timeouts and fixing the rating algorithm. Open it directly in a browser for the styled version; GitHub's file viewer only shows the source.
- [`docs/fix-implementation-plan.md`](docs/fix-implementation-plan.md) — the ordered, step-by-step plan for fixing everything the review above found, phased as showstopper bugs → rating-algorithm redesign → everything else.
- [`docs/cswap-reliability.md`](docs/cswap-reliability.md) — Claude multi-account reliability: why `cswap list --json` can drop usable quota, and how cache hydration + fallbacks work.
- [`docs/claude-local-usage.md`](docs/claude-local-usage.md) — Local Claude Code files / ccusage (token burn) vs subscription 5h/7d % from the OAuth usage API.
- [`docs/review-workflow.js`](docs/review-workflow.js) — the Claude Code Workflow script that generated the review, checked in for reproducibility.
- [`docs/memory/`](docs/memory/) — thin Claude symlink target for this project; see `AGENTS.md` for persistence policy and links to `~/ops/site-private` generic memory.
- Local quota dashboards in the same category as OpenUsage / CodexBar menu bar tools
