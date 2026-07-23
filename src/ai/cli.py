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
from ai.analysis.history import save_snapshot
from ai.analysis.use_or_lose import analyze_use_or_lose
from ai.collectors.base import which
from ai.collectors.runner import run_collectors
from ai.config import (
    DEFAULT_SUBPROCESS_TIMEOUT,
    default_config_dir,
    default_config_path,
    default_toml_config_path,
    generate_user_config,
    load_config,
    timeout_for,
)
from ai.models import provider_display_name
from ai.report import render_report

# External CLIs this project shells out to (must already be installed/auth'd).
_EXTERNAL_TOOLS: tuple[tuple[str, str], ...] = (
    ("cswap", "cswap"),
    ("codexbar", "codexbar"),
    ("tokscale", "tokscale"),
)

_HELP_EPILOG = f"""\
config & setup:
  ai --generate-config     write defaults under ~/.config/ai/ (never overwrites)
  ai --show-config-path    print services.yaml and config.toml paths
  ai doctor                check tools on PATH, config files, effective timeouts
  ai -t / --timeout SEC    force subprocess timeout for all tools this run
                           (default {DEFAULT_SUBPROCESS_TIMEOUT:g}s; also [timeouts] in config.toml)

Credentials stay with cswap / CodexBar / tokscale — this CLI never stores tokens.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai",
        description=(
            "Aggregate live AI subscription and API usage from cswap, "
            "codexbar, and tokscale; flag allotments that will reset unused. "
            "Default output is a pretty human-readable report; pass --json "
            "for machine-readable JSON."
        ),
        epilog=_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--config",
        "-c",
        help=("Path to services.yaml (default: $XDG_CONFIG_HOME/ai/services.yaml or ~/.config/ai/services.yaml)"),
    )
    p.add_argument(
        "--show-config-path",
        action="store_true",
        help="Print default config paths (services.yaml and config.toml) and exit",
    )
    p.add_argument(
        "--generate-config",
        action="store_true",
        help=(
            "Create default config files under ~/.config/ai/ (or $XDG_CONFIG_HOME/ai/). "
            "Creates missing directories; refuses to overwrite existing files"
        ),
    )
    p.add_argument(
        "--doctor",
        action="store_true",
        help=(
            "Check external tools on PATH, config file presence, and effective "
            "timeouts; exit without collecting usage (also: ai doctor)"
        ),
    )
    p.add_argument(
        "-t",
        "--timeout",
        type=float,
        metavar="SECONDS",
        help=(
            f"Default subprocess timeout in seconds for external tools "
            f"(default: {DEFAULT_SUBPROCESS_TIMEOUT:g}; also set in config.toml [timeouts])"
        ),
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
        "--traditional-summary",
        action="store_true",
        help="Use legacy flat summary format instead of the unified action plan",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _normalize_argv(argv: list[str] | None) -> list[str] | None:
    """Allow ``ai doctor`` as a synonym for ``ai --doctor``."""
    if argv is None:
        # Mutate a copy of sys.argv[1:] so argparse still sees full process argv
        # only through parse_args; we pass an explicit list instead.
        raw = sys.argv[1:]
    else:
        raw = list(argv)
    if raw and raw[0] == "doctor":
        return ["--doctor", *raw[1:]]
    return raw if argv is not None else raw


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(_normalize_argv(argv))
    if args.show_config_path:
        print(f"services: {default_config_path()}")
        print(f"settings: {default_toml_config_path()}")
        return 0
    if args.generate_config:
        return _run_generate_config()
    if args.doctor:
        return _run_doctor(config_path=args.config, timeout_override=args.timeout)
    config = load_config(args.config)
    _apply_cli_overrides(config, args)

    as_json = bool(args.json) or args.format == "json"

    # Progress stays on stderr so --json stdout is clean for piping
    print("Collecting usage from local tools…", file=sys.stderr)
    snapshot = run_collectors(config)
    alerts = analyze_use_or_lose(snapshot, config)

    analysis_cfg = config.get("analysis") if isinstance(config.get("analysis"), dict) else {}
    if analysis_cfg.get("learn_from_history"):
        try:
            snapshot_path = save_snapshot(snapshot, alerts)
            print(f"Saved snapshot to {snapshot_path}", file=sys.stderr)
        except OSError as exc:
            print(f"Warning: could not save snapshot: {exc}", file=sys.stderr)

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
        if snapshot.collector_errors and not snapshot.accounts:
            return 1
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
        if snapshot.collector_errors and not snapshot.accounts:
            return 1
        return 0

    print(
        render_report(
            snapshot,
            alerts,
            config=config,
            color=color,
            traditional_summary=args.traditional_summary,
        )
    )
    if snapshot.collector_errors and not snapshot.accounts:
        return 1
    return 0


def _run_generate_config() -> int:
    """Write default configs; never overwrite. Exit 1 if any path was skipped or errored."""
    result = generate_user_config()
    for path in result["created"]:
        print(f"created: {path}")
    for path in result["skipped"]:
        print(f"exists (not overwritten): {path}", file=sys.stderr)
    for msg in result["errors"]:
        print(f"error: {msg}", file=sys.stderr)

    if result["created"] and not result["skipped"] and not result["errors"]:
        print(
            f"Config directory ready: {default_config_path().parent}",
            file=sys.stderr,
        )
        return 0
    if result["created"] and result["skipped"] and not result["errors"]:
        print(
            "Some files already existed and were left unchanged. "
            "Remove or rename them if you want fresh defaults.",
            file=sys.stderr,
        )
        return 1
    if result["skipped"] and not result["created"] and not result["errors"]:
        print(
            "All default config files already exist; nothing written.",
            file=sys.stderr,
        )
        return 1
    if result["errors"]:
        return 1
    # No files defined edge case
    return 0


def _collector_enabled(config: dict[str, Any], name: str) -> bool:
    """Whether a collector is enabled (default True if omitted)."""
    collectors = config.get("collectors")
    if not isinstance(collectors, dict):
        return True
    entry = collectors.get(name)
    if entry is None:
        return True
    if isinstance(entry, bool):
        return entry
    if isinstance(entry, dict):
        return bool(entry.get("enabled", True))
    return True


def _path_status(path: Path) -> str:
    if path.is_file():
        return "present"
    if path.exists():
        return "exists but is not a regular file"
    return "missing (built-in defaults apply)"


def diagnose(
    config: dict[str, Any],
    *,
    which_fn=None,
) -> tuple[int, list[str]]:
    """Build doctor report lines and exit code (0 ok, 1 problems).

    Pure enough for tests: pass ``which_fn`` to stub PATH lookups.
    Does not shell out for usage or auth — only PATH + config presence.
    """
    lookup = which_fn if which_fn is not None else which
    lines: list[str] = [f"ai doctor  (v{__version__})", ""]
    problems = 0

    services = default_config_path()
    settings = default_toml_config_path()
    lines.append("Config")
    lines.append(f"  directory: {default_config_dir()}")
    lines.append(f"  services.yaml: {_path_status(services)} — {services}")
    lines.append(f"  config.toml:   {_path_status(settings)} — {settings}")
    lines.append("")

    lines.append("Timeouts (seconds)")
    timeouts = config.get("timeouts") if isinstance(config.get("timeouts"), dict) else {}
    force = timeouts.get("force")
    lines.append(f"  default: {timeout_for(config, 'default'):g}")
    lines.append(f"  force:   {force if force is not None else '(none)'}")
    for tool_key, _cmd in _EXTERNAL_TOOLS:
        lines.append(f"  {tool_key}: {timeout_for(config, tool_key):g}")
    lines.append("")

    lines.append("External tools (must already be installed and authenticated)")
    for collector_key, cmd in _EXTERNAL_TOOLS:
        enabled = _collector_enabled(config, collector_key)
        path = lookup(cmd)
        if path:
            status = "ok"
            detail = path
        else:
            status = "MISSING"
            detail = "not found on PATH"
            if enabled:
                problems += 1
        flag = "enabled" if enabled else "disabled in config"
        lines.append(f"  {cmd:<10} {status:<8} {detail}  [{flag}]")
    lines.append("")

    if problems:
        lines.append(f"Problems: {problems} enabled tool(s) missing from PATH.")
        lines.append("Install/authenticate the tool(s) above, or disable the collector in services.yaml.")
        exit_code = 1
    else:
        lines.append("No problems detected for enabled collectors.")
        exit_code = 0

    lines.append("")
    lines.append("Hints")
    lines.append("  ai --generate-config   # create ~/.config/ai defaults (no overwrite)")
    lines.append("  ai --show-config-path  # print config file paths")
    lines.append("  ai -t 45               # force all tool timeouts for one run")
    lines.append("  ai --help              # full flag list + setup epilog")
    return exit_code, lines


def _run_doctor(*, config_path: str | None, timeout_override: float | None) -> int:
    """Print environment diagnosis; do not collect usage."""
    config = load_config(config_path)
    if timeout_override is not None:
        if timeout_override <= 0:
            print("--timeout / -t must be a positive number of seconds", file=sys.stderr)
            return 2
        timeouts = config.setdefault("timeouts", {})
        timeouts["force"] = float(timeout_override)
        timeouts["default"] = float(timeout_override)
    code, lines = diagnose(config)
    print("\n".join(lines))
    return code


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    collectors = config.setdefault("collectors", {})
    if args.no_tokscale:
        collectors["tokscale"] = {"enabled": False}
    if args.no_cswap:
        collectors["cswap"] = {"enabled": False}
    if args.no_codexbar:
        collectors["codexbar"] = {"enabled": False}
    if args.providers:
        collectors.setdefault("codexbar", {})["providers"] = args.providers
    analysis = config.setdefault("analysis", {})
    if args.min_remaining is not None:
        analysis["min_remaining_percent"] = args.min_remaining
    if args.max_days is not None:
        analysis["max_days_until_reset"] = args.max_days
    if getattr(args, "timeout", None) is not None:
        if args.timeout <= 0:
            raise SystemExit("--timeout / -t must be a positive number of seconds")
        timeouts = config.setdefault("timeouts", {})
        # CLI wins over config.toml per-tool keys (see timeout_for precedence).
        timeouts["force"] = float(args.timeout)
        timeouts["default"] = float(args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
