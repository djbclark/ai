"""Shared subprocess helpers for collectors."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


class CollectorError(RuntimeError):
    pass


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run_json(
    argv: list[str],
    *,
    timeout: float = 120.0,
    allow_empty: bool = False,
) -> Any:
    """Run a command and parse JSON from stdout."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CollectorError(f"command not found: {argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CollectorError(f"timed out after {timeout}s: {' '.join(argv)}") from exc

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if not stdout:
        if allow_empty and proc.returncode == 0:
            return None
        detail = stderr or f"exit {proc.returncode}"
        raise CollectorError(f"no JSON from {' '.join(argv)}: {detail}")

    # Some tools print banners before JSON; try last JSON-looking blob.
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        start_candidates = [i for i, ch in enumerate(stdout) if ch in "{["]
        last_err: Exception | None = None
        for start in reversed(start_candidates[-5:]):
            try:
                return json.loads(stdout[start:])
            except json.JSONDecodeError as err:
                last_err = err
                continue
        raise CollectorError(
            f"invalid JSON from {' '.join(argv)}: {last_err or 'parse failed'}"
        ) from last_err
