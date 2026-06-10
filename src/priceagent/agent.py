"""LLM agent loop with OpenAI-compatible tool calling."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from priceagent.tools import ToolRegistry, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are PriceAgent, a derivatives pricing assistant.

You have tools to:
- fetch live/historical market data from Tushare (load_tushare_series, get_tushare_spot)
- manage option exchange mappings (list_tushare_option_mappings, save_tushare_option_mapping)
- probe option contracts (list_tushare_options) and fetch quotes (get_tushare_option_quote)
- list and load offline CSV datasets (lh2409, lc2409)
- align spot prices to valuation dates
- run DerivKit pricing via price_from_yaml or price_from_spec

Tushare futures and options may use different API exchange codes. You are responsible for
resolving this when needed:
1. Option tools apply locally cached futures_exchange→option_exchange mappings automatically.
2. Call list_tushare_option_mappings first to see what is already known.
3. If option lookup fails or no mapping exists, probe with list_tushare_options, pass the
   working option_exchange to quote/calibration tools, then save_tushare_option_mapping so
   later runs reuse the mapping without extra API calls.
4. Standard opt_code is OP+<futures_ts_code> unless list_tushare_options shows otherwise.

DSL product types (aliases like american/snowball/asian are auto-normalized):
- Vanilla: product.type=vanilla.european + params.exercise=european|american
- Snowball: snowball.standard | Phoenix: phoenix.standard | FCN: fcn.standard
- Asian: asian.geometric | asian.arithmetic | Barrier: barrier.up_and_out | digital.cash
American vanilla requires engine mc, tree, or fdm (not analytic).

When asked to price a vanilla option with Tushare data:
- Implied vol: calibrate_volatility(method=implied, ...) with strike; omit market_price to
  auto-fetch option settle/close, then price_tushare_vanilla with volatility=<calibrated value>.
- Historical vol: calibrate_volatility(method=historical, symbol=LH2609, lookback_days=90).
  Do NOT use dataset_id lh2409 unless you want the tiny built-in CSV sample.
- Prefer get_tushare_option_quote when you need to show which contract and price were used.
- Do NOT hand-build price_from_spec unless necessary.

For other products use price_from_yaml with an example path from list_pricing_examples.

Always use tools instead of guessing numerical results. State data source (tushare vs csv).
"""


@dataclass
class AgentRunResult:
    """Outcome of an agent conversation turn."""

    answer: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _llm_settings() -> tuple[str, str | None, str]:
    """Resolve API key, base URL, and model (DeepSeek-friendly defaults)."""
    _load_dotenv()

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip() or deepseek_key
    if not api_key:
        raise OSError(
            "Set DEEPSEEK_API_KEY or OPENAI_API_KEY in .env "
            "(see .env.example for DeepSeek configuration)"
        )

    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    base_url: str | None
    model: str
    if provider == "deepseek" or (deepseek_key and not os.environ.get("OPENAI_BASE_URL")):
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("OPENAI_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
    else:
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    return api_key, base_url, model


def _create_client():
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("Install LLM extras: pip install -e '.[llm]'") from exc

    api_key, base_url, _ = _llm_settings()
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def run_agent(
    user_prompt: str,
    *,
    model: str | None = None,
    max_turns: int = 8,
    registry: ToolRegistry | None = None,
) -> AgentRunResult:
    """Run an LLM agent with DerivKit tools until it produces a final answer."""
    client = _create_client()
    reg = registry or ToolRegistry()
    _, _, default_model = _llm_settings()
    model_name = model or default_model

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    tool_log: list[dict[str, Any]] = []

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=reg.schemas(),
            tool_choice="auto",
        )
        choice = response.choices[0]
        assistant_msg = choice.message

        msg_dict: dict[str, Any] = {"role": "assistant", "content": assistant_msg.content or ""}
        if assistant_msg.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_msg.tool_calls
            ]
        messages.append(msg_dict)

        if not assistant_msg.tool_calls:
            return AgentRunResult(
                answer=assistant_msg.content or "",
                messages=messages,
                tool_calls=tool_log,
            )

        for tc in assistant_msg.tool_calls:
            name = tc.function.name
            args = tc.function.arguments
            output = execute_tool(name, args, reg)
            tool_log.append({"name": name, "arguments": args, "output": output})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": output,
                }
            )

    return AgentRunResult(
        answer="Agent reached max turns without a final answer.",
        messages=messages,
        tool_calls=tool_log,
    )


def run_tushare_demo(
    symbol: str = "LH2409",
    valuation_date: str = "2024-06-14",
    *,
    strike: float = 15500,
    registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    """Fetch Tushare spot and price a vanilla European call (no LLM)."""
    reg = registry or ToolRegistry()
    spot_info = reg.execute(
        "get_tushare_spot",
        {"symbol": symbol, "valuation_date": valuation_date, "session_close": "15:00"},
    )
    instrument_id = spot_info["instrument_id"]
    spot = spot_info["spot"]
    spec = {
        "task": "price",
        "market": {
            "valuation_date": valuation_date,
            "calendar": "CN",
            "underlyings": [
                {"id": instrument_id, "asset_class": "commodity", "spot": spot},
            ],
            "rates": [
                {
                    "id": "CNY_RF",
                    "kind": "constant",
                    "value": 0.025,
                    "day_count": "ACT/365",
                    "compounding": "continuous",
                }
            ],
            "vols": [
                {
                    "id": f"{instrument_id}_IV",
                    "kind": "constant",
                    "value": 0.22,
                    "underlying_id": instrument_id,
                }
            ],
        },
        "product": {
            "type": "vanilla.european",
            "params": {"strike": strike, "maturity": "3m", "call_put": "call"},
        },
        "engine": {"method": "analytic"},
        "output": {"fields": ["pv", "delta"], "deterministic": True, "seed": 42},
    }
    pricing = reg.execute("price_from_spec", {"spec": spec})
    return {"tushare_spot": spot_info, "spec": spec, "pricing": pricing}


def run_demo_pricing(yaml_path: str, registry: ToolRegistry | None = None) -> dict[str, Any]:
    """Deterministic demo: data summary + pricing without LLM."""
    reg = registry or ToolRegistry()
    datasets = reg.execute("list_market_datasets", {})
    examples = reg.execute("list_pricing_examples", {})
    spot = reg.execute(
        "get_spot_quote",
        {"dataset_id": "lh2409", "valuation_date": "2024-06-14"},
    )
    price = reg.execute("price_from_yaml", {"yaml_path": yaml_path})
    return {
        "datasets": datasets,
        "examples_count": len(examples),
        "lh2409_spot": spot,
        "pricing": price,
    }
