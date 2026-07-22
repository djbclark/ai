"""CLI entrypoint for the `ai` command.

Default output is a pretty human-readable report on stdout.
Use --json / --format json for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ai.__init__ import __version__
from ai.analysis.use_or_lose import analyze_use_or_lose
from ai.collectors.runner import run_collectors
from ai.config import default_config_path, load_config
from ai.models import provider_display_name
from ai.report import render_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai",
        description=(
            "Aggregate live AI subscription and API usage from cswap, "
            "codexbar, and tokscale; flag allotments that will reset unused. "
            "Default output is a pretty human-readable report; pass --json "
            "for machine-readable JSON."
        ),
    )
    p.add_argument(
        "--config",
        "-c",
        help=("Path to services.yaml (default: $XDG_CONFIG_HOME/ai/services.yaml or ~/.config/ai/services.yaml)"),
    )
    p.add_argument(
        "--show-config-path",
        action="store_true",
        help="Print the default per-user configuration path and exit",
    )
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument(
        "--format",
        choices=("pretty", "json"),
        default="pretty",
        help="Output format (default: pretty human-readable report)",
    )
    fmt.add_argument(
        "--json",
        action="store_true",
        help="Shorthand for --format json (full snapshot + alerts)",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in pretty output",
    )
    p.add_argument(
        "--alerts-only",
        action="store_true",
        help="Only print use-or-lose recommendations (pretty text, unless --json)",
    )
    p.add_argument(
        "--no-tokscale",
        action="store_true",
        help="Skip tokscale collector",
    )
    p.add_argument(
        "--no-cswap",
        action="store_true",
        help="Skip cswap collector",
    )
    p.add_argument(
        "--no-codexbar",
        action="store_true",
        help="Skip codexbar collector",
    )
    p.add_argument(
        "--providers",
        help=(
            "CodexBar providers: 'enabled' (default), 'all', or a comma-separated list queried one provider at a time"
        ),
    )
    p.add_argument(
        "--min-remaining",
        type=float,
        help="Override min remaining %% to flag (default 40)",
    )
    p.add_argument(
        "--max-days",
        type=float,
        help="Override max days-until-reset to flag (default 14)",
    )
    p.add_argument(
        "--save",
        metavar="PATH",
        help="Also write JSON snapshot to PATH (independent of stdout format)",
    )
    p.add_argument(
        "--show-consumption",
        action="store_true",
        help="Show per-window consumption flexibility analysis in pretty report",
    )
    p.add_argument(
        "--traditional-summary",
        action="store_true",
        help="Use legacy flat summary format instead of the unified action plan",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.show_config_path:
        print(default_config_path())
        return 0
    config = load_config(args.config)
    _apply_cli_overrides(config, args)

    as_json = bool(args.json) or args.format == "json"

    # Progress stays on stderr so --json stdout is clean for piping
    print("Collecting usage from local tools…", file=sys.stderr)
    snapshot = run_collectors(config)
    alerts = analyze_use_or_lose(snapshot, config)

    payload = {
        "snapshot": snapshot.to_dict(),
        "alerts": [a.to_dict() for a in alerts],
    }
    cross_check_warnings = [check.to_dict() for check in snapshot.cross_checks if check.status == "warning"]

    if args.save:
        path = Path(args.save).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {path}", file=sys.stderr)

    if as_json:
        if args.alerts_only:
            print(
                json.dumps(
                    {
                        "alerts": payload["alerts"],
                        "cross_check_warnings": cross_check_warnings,
                    },
                    indent=2,
                    default=str,
                )
            )
        else:
            print(json.dumps(payload, indent=2, default=str))
        return 0

    # Pretty human-readable (default)
    color = False if args.no_color else None
    if args.alerts_only:
        for warning in cross_check_warnings:
            account = f" · account={warning['account']}" if warning["account"] else ""
            sources = " versus ".join(warning["sources"])
            print(
                f"[cross-check warning] {provider_display_name(str(warning['provider']))}"
                f"{account} · "
                f"{sources}: {warning['message']}"
            )
        for a in alerts:
            print(f"[{a.urgency.value}] {a.message}")
        if not alerts and not cross_check_warnings:
            print("No use-or-lose alerts or cross-check warnings.")
        return 0

    print(
        render_report(
            snapshot,
            alerts,
            config=config,
            color=color,
            show_consumption=args.show_consumption,
            traditional_summary=args.traditional_summary,
        )
    )
    return 0


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    collectors = config.setdefault("collectors", {})
    if args.no_tokscale:
        collectors.setdefault("tokscale", {})["enabled"] = False
    if args.no_cswap:
        collectors.setdefault("cswap", {})["enabled"] = False
    if args.no_codexbar:
        collectors.setdefault("codexbar", {})["enabled"] = False
    if args.providers:
        collectors.setdefault("codexbar", {})["providers"] = args.providers
    analysis = config.setdefault("analysis", {})
    if args.min_remaining is not None:
        analysis["min_remaining_percent"] = args.min_remaining
    if args.max_days is not None:
        analysis["max_days_until_reset"] = args.max_days


if __name__ == "__main__":
    raise SystemExit(main())
