"""Load YAML/JSON config with defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "analysis": {
        "min_remaining_percent": 40,
        "max_days_until_reset": 14,
        "urgent_remaining_percent": 70,
        "urgent_days_until_reset": 7,
        "min_plan_value_usd": 10,
    },
    "plans": {
        "codex": {
            "name": "ChatGPT / Codex Plus",
            "monthly_usd": 20,
            "notes": "Weekly Codex limits reset; unused weekly quota is lost.",
        },
        "claude": {
            "name": "Claude Pro / Max",
            "monthly_usd": 20,
            "notes": "5-hour and weekly limits; multi-account via cswap.",
        },
        "cursor": {
            "name": "Cursor",
            "monthly_usd": 20,
            "notes": "Monthly included usage resets with billing cycle.",
        },
        "copilot": {
            "name": "GitHub Copilot",
            "monthly_usd": 10,
            "notes": "Premium request quotas typically reset monthly.",
        },
        "grok": {
            "name": "SuperGrok",
            "monthly_usd": 30,
            "notes": "Credits / rate windows reset on a short cycle.",
        },
        "gemini": {
            "name": "Google AI Pro / Ultra",
            "monthly_usd": 20,
            "notes": "Often exposed via Antigravity / Gemini CLI.",
        },
        "opencode": {
            "name": "OpenCode Go",
            "monthly_usd": 0,
            "notes": "Has 5h / weekly / monthly windows when subscribed.",
        },
    },
    "collectors": {
        "ccusage": {"enabled": True, "offline": True},
        "cswap": {"enabled": True},
        "codexbar": {"enabled": True, "providers": "all"},
        "tokscale": {"enabled": True},
    },
}


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg = _deep_copy(DEFAULT_CONFIG)
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    else:
        here = Path(__file__).resolve()
        repo_root = here.parents[2]  # src/ai_usage/config.py → repo
        candidates.extend(
            [
                Path.cwd() / "config" / "services.yaml",
                Path.cwd() / "services.yaml",
                repo_root / "config" / "services.yaml",
                Path.home() / ".config" / "ai-usage" / "services.yaml",
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            data = _read_file(candidate)
            if isinstance(data, dict):
                cfg = _deep_merge(cfg, data)
            break
    return cfg


def _read_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "PyYAML is required for YAML config. "
                "Install with: pip install pyyaml  (or use JSON config)"
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
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = _deep_copy(value)
    return out
