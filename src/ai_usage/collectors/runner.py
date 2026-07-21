"""Orchestrate all collectors into a Snapshot."""

from __future__ import annotations

from typing import Any

from ai_usage.models import Snapshot, utcnow

from .ccusage import collect_ccusage
from .codexbar import collect_codexbar
from .cswap import collect_cswap
from .tokscale import collect_tokscale


def run_collectors(config: dict[str, Any] | None = None) -> Snapshot:
    config = config or {}
    collectors_cfg = config.get("collectors") or {}
    snapshot = Snapshot(collected_at=utcnow())

    # ccusage — historical burn
    if _enabled(collectors_cfg, "ccusage"):
        try:
            offline = bool((collectors_cfg.get("ccusage") or {}).get("offline", True))
            accounts, spend = collect_ccusage(offline=offline)
            snapshot.accounts.extend(accounts)
            snapshot.spend_history.extend(spend)
        except Exception as exc:  # noqa: BLE001 — isolate collector failures
            snapshot.collector_errors.append(f"ccusage: {exc}")

    # cswap — Claude multi-account
    if _enabled(collectors_cfg, "cswap"):
        try:
            snapshot.accounts.extend(collect_cswap())
        except Exception as exc:  # noqa: BLE001
            snapshot.collector_errors.append(f"cswap: {exc}")

    # codexbar — live quotas across many providers
    if _enabled(collectors_cfg, "codexbar"):
        try:
            providers = (collectors_cfg.get("codexbar") or {}).get("providers", "all")
            snapshot.accounts.extend(collect_codexbar(providers=providers))
        except Exception as exc:  # noqa: BLE001
            snapshot.collector_errors.append(f"codexbar: {exc}")

    # tokscale — secondary live view
    if _enabled(collectors_cfg, "tokscale"):
        try:
            snapshot.accounts.extend(collect_tokscale())
        except Exception as exc:  # noqa: BLE001
            snapshot.collector_errors.append(f"tokscale: {exc}")

    return snapshot


def _enabled(collectors_cfg: dict[str, Any], name: str) -> bool:
    section = collectors_cfg.get(name)
    if section is None:
        return True
    if isinstance(section, bool):
        return section
    if isinstance(section, dict):
        return bool(section.get("enabled", True))
    return True
