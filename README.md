# ai

Aggregate **monthly subscription** and **API** usage across your local AI tooling, then highlight allotments you should use **before they reset** (use-it-or-lose-it).

CLI command: **`ai`**

## Data sources

| Tool | Role | JSON |
|------|------|------|
| [**codexbar**](https://github.com/) `codexbar usage --format json` | Live quotas & balances (Codex, Claude, Cursor, Copilot, Grok, Gemini/Antigravity, OpenRouter, …) | ✅ |
| [**ccusage**](https://ccusage.com/) `ccusage monthly --json` | Historical token/cost from local agent logs (Claude Code, Codex, OpenCode, …) | ✅ |
| [**cswap**](https://github.com/) `cswap list --json` | Multi-account Claude slots + usage when credentials allow | ✅ |
| [**tokscale**](https://www.npmjs.com/) `tokscale usage --json` | Secondary live subscription view | ✅ |

This project shells out to tools already on your `PATH`; it does not scrape billing dashboards itself.

## Install

```bash
cd /path/to/ai
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional config:

```bash
cp config/services.example.yaml config/services.yaml
# edit plan prices / analysis thresholds
```

## Usage

```bash
# Pretty human-readable report (default)
ai
ai --format pretty
ai --no-color          # plain text, no ANSI

# or without install:
PYTHONPATH=src python -m ai_usage

# Machine-readable JSON on stdout (progress still on stderr)
ai --json
ai --format json
ai --json --alerts-only
ai --save ~/tmp/ai-snapshot.json   # also write JSON file

# Faster / partial
ai --providers copilot,grok,codex   # skip slow "all"
ai --no-tokscale
ai --min-remaining 50 --max-days 10
```

| Flag | Effect |
|------|--------|
| *(none)* / `--format pretty` | Colorized terminal report (default) |
| `--json` / `--format json` | Full snapshot + alerts as JSON |
| `--no-color` | Disable ANSI colors in pretty mode |
| `--alerts-only` | Recommendations only (respects pretty vs json) |

## What “use it or lose it” means

Most **subscription** coding plans (Claude Pro/Max, ChatGPT Plus/Codex, Cursor, Copilot, SuperGrok, Google AI Pro, …) grant **windows** of usage (5-hour, weekly, monthly). When the window resets, **unused capacity disappears** — you still paid for the month.

This tool:

1. Pulls **remaining %** and **reset times** from codexbar/tokscale (and cswap when available).
2. Scores windows that still have **lots left** and **reset soon**.
3. Skips pure **pay-as-you-go** history and treats **prepaid API balances** (OpenRouter, etc.) as non-urgent (they usually roll until spent).
4. Shows **ccusage** local spend so you can see where you actually burned tokens this month.

## Example recommendation

```
[!!! CRITICAL] codex          Weekly        100% left  reset in 3.0d
    Use codex (you@example.com, plus) soon: 100% of the Weekly window
    remains and resets in 3.0 day(s). Roughly ~$20 of a $20/mo plan is
    still unused.
```

## Project layout

```
src/ai_usage/
  cli.py                 # entrypoint
  collectors/            # ccusage, cswap, codexbar, tokscale
  analysis/use_or_lose.py
  report.py
config/services.example.yaml
tests/
```

## Tests

```bash
pytest
```

## Notes / limitations

- Live quota accuracy depends on each tool’s auth (browser cookies, OAuth, keychain). Errors are reported per account rather than aborting the whole run.
- `codexbar --provider all` can take ~1 minute; use `--providers` for a subset.
- ccusage costs are **API-equivalent estimates** from local logs, not your exact subscription bill.
- Short **5-hour** rate limits are ignored for “monthly waste” scoring (they refill often). Weekly/monthly windows are what matter for “I paid for this month.”

## Related reading

- [ccusage](https://ccusage.com/) — local multi-agent usage CLI
- Local quota dashboards in the same category as OpenUsage / CodexBar menu bar tools
