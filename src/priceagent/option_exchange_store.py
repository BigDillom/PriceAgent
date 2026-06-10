"""Persist verified Tushare futures_exchange → option_exchange mappings."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULTS_PATH = PACKAGE_ROOT / "data" / "option_exchange_defaults.json"
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
USER_CACHE_PATH = PROJECT_ROOT / ".priceagent" / "option_exchange_mappings.json"


class OptionExchangeStore:
    """Merge bundled defaults with a local JSON cache of verified mappings."""

    def __init__(
        self,
        defaults_path: Path | None = None,
        user_path: Path | None = None,
    ) -> None:
        self.defaults_path = defaults_path or DEFAULTS_PATH
        self.user_path = user_path or USER_CACHE_PATH
        self._defaults = self._load_file(self.defaults_path)
        self._user = self._load_file(self.user_path)

    @staticmethod
    def _load_file(path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load option exchange mappings from %s: %s", path, exc)
            return {}
        if not isinstance(raw, dict):
            return {}
        return {str(k).upper(): v for k, v in raw.items() if isinstance(v, dict)}

    def list_mappings(self) -> list[dict[str, Any]]:
        """Return merged mappings with source attribution."""
        keys = sorted(set(self._defaults) | set(self._user))
        out: list[dict[str, Any]] = []
        for key in keys:
            entry = self.get_entry(key)
            if entry is not None:
                out.append(entry)
        return out

    def get_entry(self, futures_exchange: str) -> dict[str, Any] | None:
        key = futures_exchange.upper()
        if key in self._user:
            entry = dict(self._user[key])
            entry["futures_exchange"] = key
            entry["source_file"] = "user_cache"
            return entry
        if key in self._defaults:
            entry = dict(self._defaults[key])
            entry["futures_exchange"] = key
            entry["source_file"] = "defaults"
            return entry
        return None

    def resolve(
        self,
        futures_exchange: str,
        option_exchange: str | None = None,
    ) -> tuple[str, str]:
        """Return (option_exchange, source) where source is explicit|cache|fallback."""
        if option_exchange:
            return option_exchange.upper(), "explicit"
        cached = self.get_entry(futures_exchange)
        if cached and cached.get("option_exchange"):
            return str(cached["option_exchange"]).upper(), "cache"
        return futures_exchange.upper(), "fallback"

    def save(
        self,
        futures_exchange: str,
        option_exchange: str,
        *,
        note: str = "",
        verified_by: str = "agent",
    ) -> dict[str, Any]:
        """Persist a verified mapping to the user cache."""
        key = futures_exchange.upper()
        entry: dict[str, Any] = {
            "option_exchange": option_exchange.upper(),
            "verified_at": date.today().isoformat(),
            "verified_by": verified_by,
        }
        if note:
            entry["note"] = note
        self._user[key] = entry
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_path.write_text(
            json.dumps(self._user, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "Saved option exchange mapping %s -> %s at %s",
            key,
            option_exchange.upper(),
            self.user_path,
        )
        saved = dict(entry)
        saved["futures_exchange"] = key
        saved["source_file"] = "user_cache"
        return saved
