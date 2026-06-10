"""Unit tests for option exchange mapping cache."""

from __future__ import annotations

from pathlib import Path

from priceagent.option_exchange_store import OptionExchangeStore


def test_resolve_uses_defaults(tmp_path: Path):
    defaults = tmp_path / "defaults.json"
    defaults.write_text(
        '{"GFE": {"option_exchange": "GFEX", "verified_by": "defaults"}}',
        encoding="utf-8",
    )
    store = OptionExchangeStore(defaults_path=defaults, user_path=tmp_path / "user.json")
    option_ex, source = store.resolve("GFE")
    assert option_ex == "GFEX"
    assert source == "cache"


def test_resolve_explicit_overrides_cache(tmp_path: Path):
    defaults = tmp_path / "defaults.json"
    defaults.write_text(
        '{"GFE": {"option_exchange": "GFEX"}}',
        encoding="utf-8",
    )
    store = OptionExchangeStore(defaults_path=defaults, user_path=tmp_path / "user.json")
    option_ex, source = store.resolve("GFE", "CUSTOM")
    assert option_ex == "CUSTOM"
    assert source == "explicit"


def test_user_cache_overrides_defaults(tmp_path: Path):
    defaults = tmp_path / "defaults.json"
    user = tmp_path / "user.json"
    defaults.write_text('{"GFE": {"option_exchange": "GFEX"}}', encoding="utf-8")
    user.write_text('{"GFE": {"option_exchange": "OVERRIDE"}}', encoding="utf-8")
    store = OptionExchangeStore(defaults_path=defaults, user_path=user)
    option_ex, source = store.resolve("GFE")
    assert option_ex == "OVERRIDE"
    assert source == "cache"


def test_save_persists_to_user_cache(tmp_path: Path):
    user = tmp_path / "user.json"
    store = OptionExchangeStore(defaults_path=tmp_path / "missing.json", user_path=user)
    saved = store.save("SHF", "SHFE", note="verified via probe")
    assert saved["option_exchange"] == "SHFE"
    assert user.exists()
    reloaded = OptionExchangeStore(defaults_path=tmp_path / "missing.json", user_path=user)
    option_ex, source = reloaded.resolve("SHF")
    assert option_ex == "SHFE"
    assert source == "cache"
