"""
cycles.py — load named cycles from named_cycles.json, apply HA option overrides.

Each entry: {code, name, cycle_type, supported_cycle_types, options}
The 'name' field can be overridden via config entry options (cycle_names dict).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
_FILE   = Path(__file__).parent / "named_cycles.json"


def load(options: dict[str, Any] | None = None) -> list[dict]:
    """
    Return named cycle list with any user renames applied.
    options: config entry options dict (may contain 'cycle_names' key).
    """
    if not _FILE.exists():
        _LOGGER.warning("named_cycles.json not found in integration directory")
        return []

    try:
        raw = json.loads(_FILE.read_text()).get("cycles", [])
    except Exception as exc:
        _LOGGER.error("Failed to read named_cycles.json: %s", exc)
        return []

    overrides: dict[str, str] = (options or {}).get("cycle_names", {})

    return [
        {**c, "name": overrides.get(c["code"], c["name"])}
        for c in raw
    ]


def names(options: dict[str, Any] | None = None) -> list[str]:
    """Return just the display names (for select entity options list)."""
    return [c["name"] for c in load(options)]


def by_name(name: str, options: dict[str, Any] | None = None) -> dict | None:
    """Find a cycle entry by display name."""
    return next((c for c in load(options) if c["name"] == name), None)


def by_code(code: str, options: dict[str, Any] | None = None) -> dict | None:
    """Find a cycle entry by course code."""
    return next((c for c in load(options) if c["code"] == code), None)
