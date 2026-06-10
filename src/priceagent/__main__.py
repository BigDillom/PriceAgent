"""CLI: python -m priceagent [demo|direct|run] ..."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from priceagent.agent import run_agent, run_demo_pricing, run_tushare_demo
from priceagent.tools import ToolRegistry, execute_tool

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_YAML = "examples/commodity/lh_vanilla_call.yaml"


def cmd_demo(args: argparse.Namespace) -> int:
    payload = run_demo_pricing(args.yaml)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    pv = payload["pricing"].get("pv")
    print(f"\nDemo OK — pv={pv}")
    return 0


def cmd_direct(args: argparse.Namespace) -> int:
    output = execute_tool("price_from_yaml", {"yaml_path": args.yaml})
    print(output)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    result = run_agent(args.prompt, model=args.model, max_turns=args.max_turns)
    print(result.answer)
    if args.verbose and result.tool_calls:
        print("\n--- tool trace ---", file=sys.stderr)
        for call in result.tool_calls:
            print(f"{call['name']}: {call['arguments'][:120]}...", file=sys.stderr)
    return 0


def cmd_tushare_demo(args: argparse.Namespace) -> int:
    payload = run_tushare_demo(
        symbol=args.symbol,
        valuation_date=args.date,
        strike=args.strike,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    pv = payload["pricing"].get("pv")
    spot = payload["tushare_spot"].get("spot")
    print(f"\nTushare demo OK — spot={spot}, pv={pv}")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    reg = ToolRegistry()
    print("Datasets:")
    print(json.dumps(reg.execute("list_market_datasets", {}), indent=2))
    print("\nYAML examples:")
    print(json.dumps(reg.execute("list_pricing_examples", {}), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PriceAgent — LLM + data interface for DerivKit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Run data + pricing demo without LLM")
    p_demo.add_argument("--yaml", default=DEFAULT_YAML, help="YAML task path")
    p_demo.set_defaults(func=cmd_demo)

    p_direct = sub.add_parser("direct", help="Price from YAML directly (no LLM)")
    p_direct.add_argument("yaml", nargs="?", default=DEFAULT_YAML)
    p_direct.set_defaults(func=cmd_direct)

    p_run = sub.add_parser("run", help="Run LLM agent with tool calling")
    p_run.add_argument("prompt", help="Natural language pricing request")
    p_run.add_argument("--model", default=None, help="Model name (default: OPENAI_MODEL or gpt-4o-mini)")
    p_run.add_argument("--max-turns", type=int, default=12)
    p_run.add_argument("-v", "--verbose", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_ts = sub.add_parser("tushare-demo", help="Tushare data + pricing demo (no LLM)")
    p_ts.add_argument("--symbol", default="LH2409", help="Futures symbol or ts_code")
    p_ts.add_argument("--date", default="2024-06-14", help="Valuation date YYYY-MM-DD")
    p_ts.add_argument("--strike", type=float, default=15500, help="Option strike")
    p_ts.set_defaults(func=cmd_tushare_demo)

    sub.add_parser("list", help="List datasets and YAML examples").set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


def cli() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
