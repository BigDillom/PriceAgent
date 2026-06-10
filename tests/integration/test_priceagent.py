"""PriceAgent data interface and tool execution (no live LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from priceagent.agent import run_demo_pricing, run_tushare_demo
from priceagent.data_service import DataService
from priceagent.tools import ToolRegistry, execute_tool
from priceagent.tushare_client import resolve_option_opt_code, resolve_ts_code

COMMODITY_YAML = (
    Path(__file__).resolve().parents[2] / "examples" / "commodity" / "lh_vanilla_call.yaml"
)


@pytest.mark.integration
def test_resolve_ts_code():
    assert resolve_ts_code("LH2409") == "LH2409.DCE"
    assert resolve_ts_code("LC2409") == "LC2409.GFE"
    assert resolve_ts_code("LH2409.DCE") == "LH2409.DCE"


@pytest.mark.integration
def test_resolve_option_opt_code():
    assert resolve_option_opt_code("LH2609") == "OPLH2609.DCE"
    assert resolve_option_opt_code("LH2609", exchange="DCE") == "OPLH2609.DCE"


@pytest.mark.integration
def test_tushare_demo_mocked():
    import pandas as pd

    mock_df = pd.DataFrame(
        {
            "trade_date": ["20240610", "20240611", "20240614"],
            "open": [15100.0, 15180.0, 15450.0],
            "high": [15200.0, 15300.0, 15600.0],
            "low": [15050.0, 15100.0, 15400.0],
            "close": [15180.0, 15250.0, 15520.0],
            "vol": [8500, 9200, 8700],
        }
    )

    class FakePro:
        def fut_daily(self, **kwargs):
            return mock_df

    class FakeClient:
        def __init__(self):
            self._pro = FakePro()

        @property
        def pro(self):
            return self._pro

        def fetch_series(self, ts_code, start, end, asset_class="commodity"):
            from derivkit.core.enums import AssetClass
            from derivkit.data.adapters import commodity

            instrument_id = ts_code.split(".")[0]
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(mock_df["trade_date"], format="%Y%m%d"),
                    "open": mock_df["open"],
                    "high": mock_df["high"],
                    "low": mock_df["low"],
                    "close": mock_df["close"],
                    "volume": mock_df["vol"],
                }
            )
            return commodity.normalize(out, instrument_id, AssetClass.COMMODITY)

        def default_date_window(self, valuation_date, lookback_days=60):
            return "2024-05-01", valuation_date

    reg = ToolRegistry(DataService(tushare_client=FakeClient()))
    payload = run_tushare_demo(registry=reg)
    assert payload["tushare_spot"]["spot"] == 15520.0
    assert payload["pricing"]["pv"] > 0


@pytest.mark.integration
def test_data_service_list_and_spot():
    svc = DataService()
    datasets = svc.list_datasets()
    assert any(d["id"] == "lh2409" for d in datasets)

    spot = svc.get_spot("2024-06-14", dataset_id="lh2409")
    assert spot["spot"] == 15520.0
    assert spot["alignment"]["session_close"] == "23:00"


@pytest.mark.integration
def test_tool_registry_price_from_yaml():
    reg = ToolRegistry()
    out = reg.execute("price_from_yaml", {"yaml_path": str(COMMODITY_YAML)})
    assert out["pv"] > 0
    assert "meta" in out


@pytest.mark.integration
def test_demo_pricing_end_to_end():
    payload = run_demo_pricing(str(COMMODITY_YAML))
    assert payload["lh2409_spot"]["spot"] == 15520.0
    assert payload["pricing"]["pv"] > 0


@pytest.mark.integration
def test_execute_tool_json_error_handling():
    raw = execute_tool("get_spot_quote", {"dataset_id": "nope", "valuation_date": "2024-01-01"})
    data = json.loads(raw)
    assert "error" in data


@pytest.mark.integration
def test_calibrate_volatility_tushare_historical_mocked():
    import pandas as pd

    dates = pd.date_range("2026-03-01", periods=65, freq="B")
    prices = 11000 + pd.Series(range(65), index=dates) * 5.0
    mock_df = pd.DataFrame(
        {
            "trade_date": dates.strftime("%Y%m%d"),
            "open": prices,
            "high": prices + 10,
            "low": prices - 10,
            "close": prices,
            "vol": 1000,
        }
    )

    class FakePro:
        def fut_daily(self, **kwargs):
            return mock_df

    class FakeClient:
        def __init__(self):
            self._pro = FakePro()

        @property
        def pro(self):
            return self._pro

        def fetch_series(self, ts_code, start, end, asset_class="commodity"):
            from derivkit.core.enums import AssetClass
            from derivkit.data.adapters import commodity

            instrument_id = ts_code.split(".")[0]
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(mock_df["trade_date"], format="%Y%m%d"),
                    "open": mock_df["open"],
                    "high": mock_df["high"],
                    "low": mock_df["low"],
                    "close": mock_df["close"],
                    "volume": mock_df["vol"],
                }
            )
            return commodity.normalize(out, instrument_id, AssetClass.COMMODITY)

        def default_date_window(self, valuation_date, lookback_days=60):
            return "2026-03-01", valuation_date

    from unittest.mock import patch

    reg = ToolRegistry(DataService(tushare_client=FakeClient()))
    with patch("derivkit.data.tushare_loader.TushareClient", FakeClient):
        out = reg.execute(
            "calibrate_volatility",
            {
                "method": "historical",
                "symbol": "LH2609",
                "valuation_date": "2026-06-08",
                "lookback_days": 90,
                "window": 60,
                "exchange": "DCE",
            },
        )
    assert out["pv"] > 0
    assert out["meta"]["data_source"]["source"] == "tushare"


@pytest.mark.integration
def test_get_tushare_option_quote_mocked():
    import pandas as pd

    basic_df = pd.DataFrame(
        [
            {
                "ts_code": "LH2609-C-12200.DCE",
                "name": "生猪2609购12200",
                "opt_code": "LH",
                "call_put": "C",
                "exercise_price": 12200.0,
                "maturity_date": "20260807",
            },
        ]
    )
    daily_df = pd.DataFrame(
        {
            "trade_date": ["20260605", "20260608"],
            "open": [500.0, 510.0],
            "high": [520.0, 530.0],
            "low": [490.0, 500.0],
            "close": [515.0, 525.0],
            "settle": [512.0, 520.5],
            "vol": [1200, 1500],
            "oi": [8000, 8100],
        }
    )

    class FakePro:
        def opt_basic(self, **kwargs):
            return basic_df

        def opt_daily(self, **kwargs):
            return daily_df

        def fut_daily(self, **kwargs):
            return pd.DataFrame()

    class FakeClient:
        def __init__(self):
            self._pro = FakePro()

        @property
        def pro(self):
            return self._pro

        def fetch_option_basic(self, exchange, *, opt_code=None, call_put=None):
            return basic_df

        def fetch_option_daily(self, ts_code, start, end, *, exchange=None):
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(daily_df["trade_date"], format="%Y%m%d"),
                    "open": daily_df["open"],
                    "high": daily_df["high"],
                    "low": daily_df["low"],
                    "close": daily_df["close"],
                    "settle": daily_df["settle"],
                    "volume": daily_df["vol"],
                    "oi": daily_df["oi"],
                }
            )
            out["ts_code"] = ts_code
            return out

        def default_date_window(self, valuation_date, lookback_days=60):
            return "2026-05-01", valuation_date

    reg = ToolRegistry(DataService(tushare_client=FakeClient()))
    quote = reg.execute(
        "get_tushare_option_quote",
        {
            "symbol": "LH2609",
            "valuation_date": "2026-06-08",
            "strike": 12200,
            "maturity": "3m",
            "call_put": "call",
            "exchange": "DCE",
            "price_field": "settle",
        },
    )
    assert quote["market_price"] == 520.5
    assert quote["matched_contract"]["ts_code"] == "LH2609-C-12200.DCE"


@pytest.mark.integration
def test_calibrate_volatility_implied_auto_fetch_mocked():
    import pandas as pd

    basic_df = pd.DataFrame(
        [
            {
                "ts_code": "LH2609-C-12200.DCE",
                "name": "生猪2609购12200",
                "opt_code": "LH",
                "call_put": "C",
                "exercise_price": 12200.0,
                "maturity_date": "20260807",
            },
        ]
    )
    opt_daily_df = pd.DataFrame(
        {
            "trade_date": ["20260608"],
            "open": [510.0],
            "high": [530.0],
            "low": [500.0],
            "close": [525.0],
            "settle": [520.5],
            "vol": [1500],
            "oi": [8100],
        }
    )
    fut_daily_df = pd.DataFrame(
        {
            "trade_date": ["20260608"],
            "open": [11700.0],
            "high": [11800.0],
            "low": [11650.0],
            "close": [11750.0],
            "vol": [9000],
        }
    )

    class FakePro:
        def opt_basic(self, **kwargs):
            return basic_df

        def opt_daily(self, **kwargs):
            return opt_daily_df

        def fut_daily(self, **kwargs):
            return fut_daily_df

    class FakeClient:
        def __init__(self):
            self._pro = FakePro()

        @property
        def pro(self):
            return self._pro

        def fetch_option_basic(self, exchange, *, opt_code=None, call_put=None):
            return basic_df

        def fetch_option_daily(self, ts_code, start, end, *, exchange=None):
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(opt_daily_df["trade_date"], format="%Y%m%d"),
                    "open": opt_daily_df["open"],
                    "high": opt_daily_df["high"],
                    "low": opt_daily_df["low"],
                    "close": opt_daily_df["close"],
                    "settle": opt_daily_df["settle"],
                    "volume": opt_daily_df["vol"],
                    "oi": opt_daily_df["oi"],
                }
            )
            out["ts_code"] = ts_code
            return out

        def fetch_series(self, ts_code, start, end, asset_class="commodity"):
            from derivkit.core.enums import AssetClass
            from derivkit.data.adapters import commodity

            instrument_id = ts_code.split(".")[0]
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(fut_daily_df["trade_date"], format="%Y%m%d"),
                    "open": fut_daily_df["open"],
                    "high": fut_daily_df["high"],
                    "low": fut_daily_df["low"],
                    "close": fut_daily_df["close"],
                    "volume": fut_daily_df["vol"],
                }
            )
            return commodity.normalize(out, instrument_id, AssetClass.COMMODITY)

        def default_date_window(self, valuation_date, lookback_days=60):
            return "2026-05-01", valuation_date

    reg = ToolRegistry(DataService(tushare_client=FakeClient()))
    out = reg.execute(
        "calibrate_volatility",
        {
            "method": "implied",
            "symbol": "LH2609",
            "valuation_date": "2026-06-08",
            "strike": 12200,
            "maturity": "3m",
            "call_put": "call",
            "exchange": "DCE",
            "price_field": "settle",
        },
    )
    assert out["pv"] > 0
    assert out["meta"]["calibration_method"] == "implied"
    assert out["option_quote"]["market_price"] == 520.5


@pytest.mark.integration
def test_list_tushare_options_mocked():
    import pandas as pd

    basic_df = pd.DataFrame(
        [
            {
                "ts_code": "LC2609-C-244000.GFE",
                "name": "碳酸锂期权2609C244000",
                "opt_code": "OPLC2609.GFE",
                "call_put": "C",
                "exercise_price": 244000.0,
                "maturity_date": "20260807",
                "exchange": "GFEX",
            },
        ]
    )

    class FakeClient:
        def fetch_option_basic(self, exchange, *, opt_code=None, call_put=None):
            assert exchange == "GFEX"
            assert opt_code == "OPLC2609.GFE"
            return basic_df

    reg = ToolRegistry(DataService(tushare_client=FakeClient()))
    out = reg.execute(
        "list_tushare_options",
        {
            "option_exchange": "GFEX",
            "opt_code": "OPLC2609.GFE",
            "call_put": "call",
        },
    )
    assert out["count"] == 1
    assert out["contracts"][0]["ts_code"] == "LC2609-C-244000.GFE"
    assert "OPLC2609.GFE" in out["unique_opt_codes"]


@pytest.mark.integration
def test_get_tushare_option_quote_uses_cached_option_exchange_mocked(tmp_path):
    import pandas as pd

    from priceagent.option_exchange_store import OptionExchangeStore

    basic_df = pd.DataFrame(
        [
            {
                "ts_code": "LC2609-C-244000.GFE",
                "name": "碳酸锂期权2609C244000",
                "opt_code": "OPLC2609.GFE",
                "call_put": "C",
                "exercise_price": 244000.0,
                "maturity_date": "20260807",
            },
        ]
    )
    daily_df = pd.DataFrame(
        {
            "trade_date": ["20260608"],
            "open": [900.0],
            "high": [950.0],
            "low": [850.0],
            "close": [920.0],
            "settle": [910.0],
            "vol": [200],
            "oi": [1500],
        }
    )

    class FakeClient:
        def fetch_option_basic(self, exchange, *, opt_code=None, call_put=None):
            assert exchange == "GFEX"
            return basic_df

        def fetch_option_daily(self, ts_code, start, end, *, exchange=None):
            assert exchange == "GFEX"
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(daily_df["trade_date"], format="%Y%m%d"),
                    "open": daily_df["open"],
                    "high": daily_df["high"],
                    "low": daily_df["low"],
                    "close": daily_df["close"],
                    "settle": daily_df["settle"],
                    "volume": daily_df["vol"],
                    "oi": daily_df["oi"],
                }
            )
            out["ts_code"] = ts_code
            return out

        def default_date_window(self, valuation_date, lookback_days=60):
            return "2026-05-01", valuation_date

    defaults = tmp_path / "defaults.json"
    defaults.write_text(
        '{"GFE": {"option_exchange": "GFEX", "verified_by": "test"}}',
        encoding="utf-8",
    )
    store = OptionExchangeStore(defaults_path=defaults, user_path=tmp_path / "user.json")
    reg = ToolRegistry(
        DataService(tushare_client=FakeClient(), option_exchange_store=store)
    )
    quote = reg.execute(
        "get_tushare_option_quote",
        {
            "symbol": "LC2609",
            "valuation_date": "2026-06-08",
            "strike": 244000,
            "maturity": "3m",
            "call_put": "call",
        },
    )
    assert quote["option_exchange"] == "GFEX"
    assert quote["option_exchange_source"] == "cache"
    assert quote["market_price"] == 910.0


@pytest.mark.integration
def test_save_tushare_option_mapping_tool(tmp_path):
    from priceagent.option_exchange_store import OptionExchangeStore

    store = OptionExchangeStore(
        defaults_path=tmp_path / "defaults.json",
        user_path=tmp_path / "user.json",
    )
    reg = ToolRegistry(DataService(option_exchange_store=store))
    saved = reg.execute(
        "save_tushare_option_mapping",
        {
            "futures_exchange": "SHF",
            "option_exchange": "SHFE",
            "note": "probe ok",
        },
    )
    assert saved["option_exchange"] == "SHFE"
    mappings = reg.execute("list_tushare_option_mappings", {})
    assert any(m["futures_exchange"] == "SHF" and m["option_exchange"] == "SHFE" for m in mappings)


@pytest.mark.integration
def test_get_tushare_option_quote_with_option_exchange_mocked(tmp_path):
    import pandas as pd

    from priceagent.option_exchange_store import OptionExchangeStore

    basic_df = pd.DataFrame(
        [
            {
                "ts_code": "LC2609-C-244000.GFE",
                "name": "碳酸锂期权2609C244000",
                "opt_code": "OPLC2609.GFE",
                "call_put": "C",
                "exercise_price": 244000.0,
                "maturity_date": "20260807",
            },
        ]
    )
    daily_df = pd.DataFrame(
        {
            "trade_date": ["20260608"],
            "open": [900.0],
            "high": [950.0],
            "low": [850.0],
            "close": [920.0],
            "settle": [910.0],
            "vol": [200],
            "oi": [1500],
        }
    )

    class FakeClient:
        def fetch_option_basic(self, exchange, *, opt_code=None, call_put=None):
            assert exchange == "GFEX"
            assert opt_code == "OPLC2609.GFE"
            return basic_df

        def fetch_option_daily(self, ts_code, start, end, *, exchange=None):
            assert exchange == "GFEX"
            out = pd.DataFrame(
                {
                    "datetime": pd.to_datetime(daily_df["trade_date"], format="%Y%m%d"),
                    "open": daily_df["open"],
                    "high": daily_df["high"],
                    "low": daily_df["low"],
                    "close": daily_df["close"],
                    "settle": daily_df["settle"],
                    "volume": daily_df["vol"],
                    "oi": daily_df["oi"],
                }
            )
            out["ts_code"] = ts_code
            return out

        def default_date_window(self, valuation_date, lookback_days=60):
            return "2026-05-01", valuation_date

    store = OptionExchangeStore(
        defaults_path=tmp_path / "defaults.json",
        user_path=tmp_path / "user.json",
    )
    reg = ToolRegistry(
        DataService(tushare_client=FakeClient(), option_exchange_store=store)
    )
    quote = reg.execute(
        "get_tushare_option_quote",
        {
            "symbol": "LC2609",
            "valuation_date": "2026-06-08",
            "strike": 244000,
            "maturity": "3m",
            "call_put": "call",
            "exchange": "GFE",
            "option_exchange": "GFEX",
            "opt_code": "OPLC2609.GFE",
        },
    )
    assert quote["option_exchange"] == "GFEX"
    assert quote["option_exchange_source"] == "explicit"
    assert store.get_entry("GFE") is not None
    assert quote["exchange"] == "GFE"
    assert quote["market_price"] == 910.0
    assert quote["matched_contract"]["ts_code"] == "LC2609-C-244000.GFE"


@pytest.mark.integration
def test_run_agent_mocked_llm():
    reg = ToolRegistry()

    mock_client = MagicMock()
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "price_from_yaml"
    tool_call.function.arguments = json.dumps({"yaml_path": str(COMMODITY_YAML)})

    first = MagicMock()
    first.choices = [MagicMock()]
    first.choices[0].message.content = None
    first.choices[0].message.tool_calls = [tool_call]

    second = MagicMock()
    second.choices = [MagicMock()]
    second.choices[0].message.content = "PV is ready."
    second.choices[0].message.tool_calls = None

    mock_client.chat.completions.create.side_effect = [first, second]

    with (
        patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "LLM_PROVIDER": "deepseek"}),
        patch("priceagent.agent._create_client", return_value=mock_client),
    ):
        from priceagent.agent import run_agent

        result = run_agent("Price LH2409 vanilla call", registry=reg, max_turns=4)

    assert "PV" in result.answer
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "price_from_yaml"
