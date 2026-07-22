"""Load YAML/JSON config with defaults."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "analysis": {
        "min_remaining_percent": 40,
        "max_days_until_reset": 14,
        "urgent_remaining_percent": 70,
        "urgent_days_until_reset": 7,
        "use_multi_dim_scoring": True,
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
            "daily": 0.1,
            "weekly": 0.7,
            "monthly": 1.0,
        },
        "provider_overrides": {
            "claude": {"5h": {"flexibility": 0.0, "refill_capacity_unit": "requests"}},
            "grok": {"weekly": {"flexibility": 0.5, "refill_capacity_unit": "requests"}},
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


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg = _deep_copy(DEFAULT_CONFIG)
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    else:
        candidates.append(default_config_path())

    for candidate in candidates:
        if candidate.is_file():
            data = _read_file(candidate)
            if isinstance(data, dict):
                cfg = _deep_merge(cfg, data)
            break
    return cfg


def default_config_path() -> Path:
    """Return the XDG user configuration path for this CLI."""
    return _xdg_config_home() / "ai" / "services.yaml"


def _xdg_config_home() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        # XDG requires these environment-variable paths to be absolute.
        if candidate.is_absolute():
            return candidate
    return Path.home() / ".config"


def _read_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise SystemExit(
                "PyYAML is required for YAML config. Install with: pip install pyyaml  (or use JSON config)"
            ) from exc
        return yaml.safe_load(text)
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
