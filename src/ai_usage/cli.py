"""CLI entrypoint for ai-usage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ai_usage import __version__
from ai_usage.analysis import analyze_use_or_lose
from ai_usage.collectors import run_collectors
from ai_usage.config import load_config
from ai_usage.report import render_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-usage",
        description=(
            "Aggregate AI subscription and API usage from ccusage, cswap, "
            "codexbar, and tokscale; flag allotments that will reset unused."
        ),
    )
    p.add_argument(
        "--config",
        "-c",
        help="Path to services.yaml (default: config/services.yaml if present)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit full snapshot + alerts as JSON",
    )
    p.add_argument(
        "--alerts-only",
        action="store_true",
        help="Only print use-or-lose recommendations",
    )
    p.add_argument(
        "--no-tokscale",
        action="store_true",
        help="Skip tokscale collector",
    )
    p.add_argument(
        "--no-ccusage",
        action="store_true",
        help="Skip ccusage collector",
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
        help="CodexBar providers (default from config, usually 'all')",
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
        help="Also write JSON snapshot to PATH",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    _apply_cli_overrides(config, args)

    print("Collecting usage from local tools…", file=sys.stderr)
    snapshot = run_collectors(config)
    alerts = analyze_use_or_lose(snapshot, config)

    if args.save:
        path = Path(args.save).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "snapshot": snapshot.to_dict(),
                    "alerts": [a.to_dict() for a in alerts],
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {path}", file=sys.stderr)

    if args.json:
        payload = {
            "snapshot": snapshot.to_dict(),
            "alerts": [a.to_dict() for a in alerts],
        }
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if args.alerts_only:
        if not alerts:
            print("No use-or-lose alerts.")
            return 0
        for a in alerts:
            print(f"[{a.urgency.value}] {a.message}")
        return 0

    print(render_report(snapshot, alerts, config=config))
    return 0


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    collectors = config.setdefault("collectors", {})
    if args.no_tokscale:
        collectors.setdefault("tokscale", {})["enabled"] = False
    if args.no_ccusage:
        collectors.setdefault("ccusage", {})["enabled"] = False
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
