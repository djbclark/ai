"""Load YAML/JSON/TOML config with defaults.

User config layers (later wins on deep-merge where keys overlap):

1. Built-in ``DEFAULT_CONFIG``
2. Optional ``~/.config/ai/config.toml`` (or ``$XDG_CONFIG_HOME/ai/config.toml``)
   — preferred home for tool settings (timeouts, future knobs)
3. Optional services file (``services.yaml`` / JSON via ``--config`` or default
   path) — plans, analysis thresholds, collector enable flags
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Default wall-clock budget for every external CLI subprocess. Tools either
# return within tens of seconds or hang; long budgets only delay failure.
DEFAULT_SUBPROCESS_TIMEOUT = 45.0

DEFAULT_CONFIG: dict[str, Any] = {
    # Subprocess timeouts (seconds). ``default`` applies to any tool that does
    # not set its own key. Known keys: cswap, codexbar, codexbar_discovery,
    # tokscale. Override via config.toml or CLI ``--timeout`` / ``-t``.
    "timeouts": {
        "default": DEFAULT_SUBPROCESS_TIMEOUT,
    },
    "analysis": {
        "min_remaining_percent": 40,
        "max_days_until_reset": 14,
        "urgent_remaining_percent": 70,
        "urgent_days_until_reset": 7,
        "use_multi_dim_scoring": True,
        "scoring_mode": "pace",
        "pace": {
            "waste_alert_fraction": 0.30,
            "min_elapsed_fraction": 0.15,
            "conserve_min_lead_hours": 4.0,
        },
        "learn_from_history": False,
        "snapshot_retention_days": 90,
        "waking_hours_per_day": 16,
        "min_value_at_risk_usd": 0.50,
        "min_value_fraction": 0.05,
        "max_sustained_tokens_per_minute": 200000,
        "max_requests_per_minute": 0.5,
        "max_usd_per_minute": 0.05,
        "consumption_flexibility_defaults": {
            "5h": 0.0,
            "weekly": 0.7,
            "monthly": 1.0,
        },
        "provider_overrides": {
            "claude": {
                "shared_allotment": True,  # 5h ⊂ weekly; pace-score governing window only
                "5h": {"flexibility": 0.0, "refill_capacity_unit": "requests", "refill_capacity": 45},
            },
            "gemini": {
                "shared_allotment": True,
                "5h": {"flexibility": 0.0, "refill_capacity_unit": "requests", "refill_capacity": 50},
            },
            "grok": {"weekly": {"flexibility": 0.5, "refill_capacity_unit": "requests", "refill_capacity": 100}},
        },
    },
    "plans": {
        "codex": {
            "name": "ChatGPT / Codex Plus",
            "notes": "Weekly Codex limits reset; unused weekly quota is lost.",
            "monthly_price": 20,
        },
        "claude": {
            "name": "Claude Pro / Max",
            "notes": "5-hour and weekly limits; multi-account via cswap.",
            "monthly_price": 20,
            "value_multiplier": {"5h": 1.4},
        },
        "cursor": {
            "name": "Cursor",
            "notes": "Monthly included usage resets with billing cycle.",
            "monthly_price": 20,
        },
        "copilot": {
            "name": "GitHub Copilot",
            "notes": "Premium request quotas typically reset monthly.",
            "monthly_price": 10,
        },
        "grok": {
            "name": "SuperGrok",
            "notes": "Credits / rate windows reset on a short cycle.",
            "monthly_price": 30,
        },
        "gemini": {
            "name": "Google AI Pro / Ultra",
            "notes": "Often exposed via Antigravity / Gemini CLI.",
            "monthly_price": 20,
        },
        "opencode": {
            "name": "OpenCode Go",
            "notes": "Has 5h / weekly / monthly windows when subscribed.",
            "monthly_price": 10,
        },
    },
    "collectors": {
        "cswap": {"enabled": True},
        "codexbar": {"enabled": True, "providers": "enabled"},
        "tokscale": {"enabled": True},
    },
}


def timeout_for(config: dict[str, Any] | None, name: str) -> float:
    """Resolve subprocess timeout (seconds) for a named tool.

    Precedence:

    1. ``timeouts.force`` — set by CLI ``--timeout`` / ``-t`` (wins over everything)
    2. ``timeouts.<name>`` — per-tool override in config.toml / services.yaml
    3. ``timeouts.default``
    4. :data:`DEFAULT_SUBPROCESS_TIMEOUT`
    """
    timeouts = (config or {}).get("timeouts") if isinstance((config or {}).get("timeouts"), dict) else {}
    if timeouts.get("force") is not None:
        return float(timeouts["force"])
    default = float(timeouts.get("default", DEFAULT_SUBPROCESS_TIMEOUT))
    if name in timeouts and timeouts[name] is not None:
        return float(timeouts[name])
    return default


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg = _deep_copy(DEFAULT_CONFIG)

    toml_path = default_toml_config_path()
    if toml_path.is_file():
        data = _read_file(toml_path)
        if isinstance(data, dict):
            cfg = _deep_merge(cfg, data)

    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    else:
        candidates.append(default_config_path())

    for candidate in candidates:
        if path is not None and not candidate.is_file():
            raise SystemExit(f"Config file not found: {candidate}")
        if candidate.is_file():
            data = _read_file(candidate)
            if isinstance(data, dict):
                cfg = _deep_merge(cfg, data)
            break
    return cfg


def default_config_dir() -> Path:
    """User config directory: ``$XDG_CONFIG_HOME/ai`` or ``~/.config/ai``."""
    return _xdg_config_home() / "ai"


def default_config_path() -> Path:
    """Return the XDG user configuration path for services.yaml."""
    return default_config_dir() / "services.yaml"


def default_toml_config_path() -> Path:
    """Optional TOML settings path (timeouts and future tool knobs)."""
    return default_config_dir() / "config.toml"


def _xdg_config_home() -> Path:
    """XDG config home: prefer absolute ``$XDG_CONFIG_HOME``, else ``~/.config``."""
    configured = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        # XDG requires these environment-variable paths to be absolute.
        if candidate.is_absolute():
            return candidate
    return Path.home() / ".config"


def ensure_config_dir() -> Path:
    """Create ``~/.config`` (or XDG home) and ``…/ai`` if missing; return the ai dir.

    Creates each path component that does not exist. Raises ``OSError`` if a
    component exists but is not a directory.
    """
    xdg = _xdg_config_home()
    ai_dir = xdg / "ai"
    for path in (xdg, ai_dir):
        if path.exists():
            if not path.is_dir():
                raise OSError(f"config path exists but is not a directory: {path}")
            continue
        path.mkdir(mode=0o755)
    return ai_dir


def generate_user_config() -> dict[str, list[str]]:
    """Write default config files under the standard config directory.

    Creates parent directories as needed. Never overwrites an existing file —
    conflicts are listed in the return value under ``skipped``.

    Returns a dict with keys ``created``, ``skipped``, ``errors`` (path strings).
    """
    created: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    try:
        ensure_config_dir()
    except OSError as exc:
        return {"created": [], "skipped": [], "errors": [str(exc)]}

    targets: list[tuple[Path, str]] = [
        (default_toml_config_path(), _default_toml_text()),
        (default_config_path(), _default_services_yaml_text()),
    ]
    for path, content in targets:
        try:
            if path.exists():
                skipped.append(str(path))
                continue
            path.write_text(content, encoding="utf-8")
            # Restrictive perms for user config (plans are not secrets, but habit).
            try:
                path.chmod(0o600)
            except OSError:
                pass
            created.append(str(path))
        except OSError as exc:
            errors.append(f"{path}: {exc}")

    return {"created": created, "skipped": skipped, "errors": errors}


def _default_toml_text() -> str:
    """Default config.toml body matching built-in timeout defaults."""
    return (
        "# Tool settings for the `ai` CLI (generated by `ai --generate-config`).\n"
        f"# Location: {default_toml_config_path()}\n"
        "#\n"
        "# This file is separate from services.yaml (plans / analysis thresholds).\n"
        "# Both are optional; built-in defaults apply when a file is missing.\n"
        "\n"
        "[timeouts]\n"
        "# Wall-clock seconds for every external CLI (cswap, codexbar, tokscale).\n"
        "# Tools either return quickly or hang — long budgets only delay failure.\n"
        f"default = {DEFAULT_SUBPROCESS_TIMEOUT:g}\n"
        "\n"
        "# Optional per-tool overrides (omit to use default):\n"
        "# cswap = 45\n"
        "# codexbar = 45\n"
        "# codexbar_discovery = 45   # `codexbar config providers` (local, usually ms)\n"
        "# tokscale = 45\n"
        "\n"
        "# CLI `--timeout` / `-t` overrides every tool for that run.\n"
    )


def _default_services_yaml_text() -> str:
    """Default services.yaml from DEFAULT_CONFIG (analysis / plans / collectors)."""
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "PyYAML is required to generate services.yaml. Install with: pip install pyyaml"
        ) from exc

    payload = {
        "analysis": _deep_copy(DEFAULT_CONFIG["analysis"]),
        "plans": _deep_copy(DEFAULT_CONFIG["plans"]),
        "collectors": _deep_copy(DEFAULT_CONFIG["collectors"]),
    }
    header = (
        f"# Generated by `ai --generate-config`\n"
        f"# Location: {default_config_path()}\n"
        "# Override plan metadata and analysis thresholds for use-it-or-lose-it alerts.\n"
        "# Provider credentials stay in cswap / CodexBar / tokscale — not here.\n"
        "\n"
    )
    body = yaml.safe_dump(
        payload,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return header + body


def _read_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise SystemExit(
                "PyYAML is required for YAML config. Install with: pip install pyyaml  (or use JSON config)"
            ) from exc
        return yaml.safe_load(text)
    if suffix == ".toml":
        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover — project requires 3.11+
            import tomli as tomllib  # type: ignore[no-redef]
        return tomllib.loads(text)
    return json.loads(text)


def _deep_copy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = _deep_copy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = _deep_copy(value)
    return out
