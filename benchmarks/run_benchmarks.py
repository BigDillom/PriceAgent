#!/usr/bin/env python3
"""DerivKit performance benchmark runner with baseline comparison.

Usage:
    python benchmarks/run_benchmarks.py
    python benchmarks/run_benchmarks.py --compare
    python benchmarks/run_benchmarks.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from derivkit.core.enums import BarrierType, CallPut
from derivkit.core.rng import set_seed
from derivkit.data.market_env import MarketEnv, UnderlyingSpec
from derivkit.core.enums import AssetClass
from derivkit.data.term_structures import ConstantRate
from derivkit.data.volmodels import ConstantVol
from derivkit.pricing.engines.analytic import AnalyticEngine
from derivkit.pricing.engines.analytic_barrier import AnalyticBarrierEngine
from derivkit.pricing.engines.fdm_snowball import FdmSnowballEngine
from derivkit.pricing.engines.mc import McEngine
from derivkit.pricing.engines.mc_barrier import McBarrierEngine
from derivkit.pricing.engines.quad_snowball import QuadSnowballEngine
from derivkit.pricing.perf.mc_kernels import evolve_bs_log, simulate_gbm_terminal
from derivkit.pricing.perf.pde_kernels import fdm_evolve_step
from derivkit.pricing.perf.quad_fft import get_quad_vector_jit, step_backward_jit
from derivkit.pricing.products.barrier import BarrierOption
from derivkit.pricing.products.snowball import StandardSnowball
from derivkit.pricing.products.vanilla import EuropeanVanilla

BASELINE_PATH = Path(__file__).parent / "baseline.json"


@dataclass
class BenchCase:
    name: str
    fn: Callable[[], float]
    warmup: Callable[[], None] | None = None


def _warmup_numba() -> None:
    """Compile JIT kernels before timed runs."""
    z = __import__("numpy").random.default_rng(0).standard_normal((64, 32))
    evolve_bs_log(100.0, 0.001, 0.02, z)
    simulate_gbm_terminal(100.0, 0.01, 0.2, z[:, 0])
    iv = __import__("numpy").arange(1, 51, dtype=float)
    yv = __import__("numpy").ones(50)
    a = __import__("numpy").full(50, 0.04)
    b = __import__("numpy").zeros(50)
    c = __import__("numpy").full(50, 0.05)
    fdm_evolve_step(iv, a, b, c, -0.01, 0.5, yv, 0.0, 0.0, 0.0, 0.0)
    qv, qi = get_quad_vector_jit(51, True)
    x = __import__("numpy").linspace(80, 120, 41)
    y = __import__("numpy").linspace(70, 130, 51)
    v = __import__("numpy").ones(51)
    step_backward_jit(x, y, v, 0.01, 0.05, 0.0, 0.2, qv, qi)


def _make_env_spot() -> tuple[MarketEnv, float]:
    env = MarketEnv(
        valuation_date=date(2024, 1, 5),
        underlyings={"SPX": UnderlyingSpec("SPX", AssetClass.INDEX, 100.0)},
        rates=ConstantRate(0.05),
        vols={"SPX": ConstantVol(0.2)},
    )
    return env, 100.0


def build_cases() -> list[BenchCase]:
    env, _ = _make_env_spot()
    vanilla = EuropeanVanilla(strike=100, maturity=1.0, call_put=CallPut.CALL, underlying_id="SPX")
    analytic = AnalyticEngine()
    mc = McEngine(n_paths=100_000, seed=42)

    snowball_env = MarketEnv.from_spec({
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "CSI1000", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "CN_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "CSI1000", "kind": "constant", "value": 0.2, "underlying_id": "CSI1000"}],
    })
    snowball = StandardSnowball.from_params(
        {"s0": 100, "barrier_out": 103, "barrier_in": 80, "coupon_out": 0.113, "maturity": "1y"},
        "CSI1000",
        valuation_date=snowball_env.valuation_date,
    )
    fdm = FdmSnowballEngine(s_step=400)
    quad = QuadSnowballEngine(n_points=901)

    barrier = BarrierOption(
        strike=100,
        barrier=110,
        rebate=0.0,
        maturity=1.0,
        call_put=CallPut.CALL,
        barrier_type=BarrierType.UP_AND_OUT,
        underlying_id="SPX",
    )
    barrier_analytic = AnalyticBarrierEngine()
    barrier_mc = McBarrierEngine(n_paths=50_000, seed=42)

    return [
        BenchCase(
            "vanilla_analytic",
            lambda: analytic.calc_present_value(vanilla, env),
            lambda: analytic.calc_present_value(vanilla, env),
        ),
        BenchCase(
            "vanilla_mc_100k",
            lambda: mc.calc_present_value(vanilla, env),
            lambda: McEngine(n_paths=1000, seed=42).calc_present_value(vanilla, env),
        ),
        BenchCase(
            "snowball_fdm_400",
            lambda: fdm.calc_present_value(snowball, snowball_env),
            lambda: FdmSnowballEngine(s_step=100).calc_present_value(snowball, snowball_env),
        ),
        BenchCase(
            "snowball_quad",
            lambda: quad.calc_present_value(snowball, snowball_env),
            lambda: QuadSnowballEngine(n_points=201).calc_present_value(snowball, snowball_env),
        ),
        BenchCase(
            "barrier_multi",
            lambda: (
                barrier_analytic.calc_present_value(barrier, env)
                + barrier_mc.calc_present_value(barrier, env)
            ),
            lambda: barrier_analytic.calc_present_value(barrier, env),
        ),
    ]


def time_case(case: BenchCase, repeats: int = 3) -> dict:
    if case.warmup:
        case.warmup()
    samples_ms: list[float] = []
    last_pv = 0.0
    for _ in range(repeats):
        t0 = time.perf_counter()
        last_pv = case.fn()
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    return {
        "name": case.name,
        "median_ms": statistics.median(samples_ms),
        "min_ms": min(samples_ms),
        "max_ms": max(samples_ms),
        "pv": last_pv,
    }


def load_baseline() -> dict:
    with BASELINE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def compare_results(results: list[dict], baseline: dict) -> list[str]:
    threshold = baseline.get("regression_threshold", 0.15)
    warnings: list[str] = []
    cases = baseline.get("cases", {})
    for row in results:
        spec = cases.get(row["name"], {})
        target = spec.get("target_ms")
        ref = spec.get("baseline_ms")
        median = row["median_ms"]
        if target is not None and median > target:
            warnings.append(f"{row['name']}: {median:.1f}ms exceeds SLA target {target}ms")
        if ref is not None and ref > 0:
            ratio = (median - ref) / ref
            if ratio > threshold:
                warnings.append(
                    f"{row['name']}: {median:.1f}ms regressed {ratio:.0%} vs baseline {ref}ms"
                )
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DerivKit performance benchmarks")
    parser.add_argument("--compare", action="store_true", help="Compare against baseline.json")
    parser.add_argument("--json", type=Path, help="Write JSON report to path")
    parser.add_argument("--repeats", type=int, default=3, help="Timed repetitions per case")
    args = parser.parse_args(argv)

    set_seed(42)
    _warmup_numba()

    cases = build_cases()
    results = [time_case(c, repeats=args.repeats) for c in cases]

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
    }

    print("DerivKit benchmarks (median ms):")
    for row in results:
        print(f"  {row['name']:20s}  {row['median_ms']:8.2f} ms  (pv={row['pv']:.4f})")

    exit_code = 0
    if args.compare:
        baseline = load_baseline()
        warnings = compare_results(results, baseline)
        if warnings:
            exit_code = 1
            print("\nPerformance warnings:")
            for w in warnings:
                print(f"  - {w}")
        else:
            print("\nAll cases within baseline thresholds.")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {args.json}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
