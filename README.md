# ai

Aggregate live **subscription quota** and **prepaid balance** information across
your local AI tooling, then highlight allotments you should use **before they
reset** (use-it-or-lose-it).

CLI command: **`ai`**

## Data sources

| Tool                                                               | Purpose                                                   | Authority                                                                         |
| ------------------------------------------------------------------ | --------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [**cswap**](https://github.com/) `cswap list --json`               | Live Claude Code quota for every configured email/account | Canonical for Claude; CodexBar is only an account-aware cross-check               |
| [**CodexBar**](https://github.com/) `codexbar usage --format json` | Live quotas and balances for enabled providers            | Preferred for non-Claude providers                                                |
| [**tokscale**](https://www.npmjs.com/) `tokscale usage --json`     | Independent live subscription quota measurement           | Cross-checked against CodexBar; selected for alerts when CodexBar has no live row |

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
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/ai"
cp config/services.example.yaml "${XDG_CONFIG_HOME:-$HOME/.config}/ai/services.yaml"
# edit plan notes / analysis thresholds
```

The default user config is `$XDG_CONFIG_HOME/ai/services.yaml`, falling back to
`~/.config/ai/services.yaml` when `XDG_CONFIG_HOME` is unset. Run
`ai --show-config-path` to print the resolved path. Provider credentials and
account identities remain owned by cswap, CodexBar, and tokscale; this config
does not duplicate email addresses, access tokens, or other provider state.

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
```

| Flag                         | Effect                                         |
| ---------------------------- | ---------------------------------------------- |
| _(none)_ / `--format pretty` | Colorized terminal report (default)            |
| `--json` / `--format json`   | Full snapshot + alerts as JSON                 |
| `--no-color`                 | Disable ANSI colors in pretty mode             |
| `--alerts-only`              | Recommendations only (respects pretty vs json) |

## What “use it or lose it” means

Most **subscription** coding plans (Claude Pro/Max, ChatGPT Plus/Codex, Cursor, Copilot, SuperGrok, Google AI Pro, …) grant **windows** of usage (5-hour, weekly, monthly). When the window resets, **unused capacity disappears** — you still paid for the month.

This tool:

1. Pulls **remaining %** and **reset times** from cswap for each distinct Claude
   Code account and from CodexBar/tokscale for other providers.
2. Scores windows that still have **lots left** and **reset soon**.
3. Skips pure **pay-as-you-go** history and treats **prepaid API balances** (OpenRouter, etc.) as non-urgent (they usually roll until spent).
4. Compares overlapping CodexBar and tokscale measurements and reports clear
   consistency warnings. Claude Code remains canonical in cswap, with CodexBar
   used only as an account-aware cross-check when possible.

This command intentionally does not report historical local-token usage or
API-equivalent cost estimates.

## Example recommendation

```
[!!! CRITICAL] Codex · you@example.com · Codex weekly quota: 100% left
    Use Codex (you@example.com, plus) soon: 100% of the Codex weekly quota
    remains and resets in 3.0 day(s).
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

- Live quota accuracy depends on each tool’s auth (browser cookies, OAuth, keychain). Errors are reported per account rather than aborting the whole run.
- cswap, CodexBar, and tokscale run concurrently, and by default each CodexBar
  provider (and any explicit comma-separated `--providers` list) is queried as
  its own concurrent subprocess, so total runtime tracks the slowest single
  provider rather than the sum of all of them. `--providers all` is
  intentionally thorough and stays a single, slower bundled CodexBar call.
- CodexBar's raw numbered quota slots are translated to provider-specific names
  where known. Unnamed slots are explicitly reported as unnamed; output never
  presents a bare numbered slot as if its meaning were known.
- Duplicate live measurements are retained for cross-checking but only one copy
  drives recommendations, preventing duplicate alerts.
- Short **5-hour** rate limits are ignored for “monthly waste” scoring (they refill often). Weekly/monthly windows are what matter for “I paid for this month.”

## Related reading

- Local quota dashboards in the same category as OpenUsage / CodexBar menu bar tools
