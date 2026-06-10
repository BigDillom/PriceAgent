# DerivKit

Derivatives modeling and solving components designed for reliable invocation by LLM agents.

DerivKit sits between large language model agents and low-level numerical computation, providing declarative APIs and a controlled DSL for pricing, calibration, and risk analysis of financial derivatives.

## Features

- **Data Governance (`derivkit.data`)**: Cross-asset alignment, term structures, volatility models, calendars
- **Modeling & Solving (`derivkit.pricing`)**: Multiple pricing engines (analytic, tree, FDM, MC, quadrature)
- **Agent API (`derivkit.api`)**: High-level `price()`, `risk()`, `calibrate()` functions
- **Controlled DSL**: Pydantic-validated YAML/JSON configuration
- **Output Contracts**: Explicit field definitions with numerical tolerances
- **QFbench Integration**: Sandbox runner and task templates

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full environment setup and locked dependency versions.

```python
import derivkit as dk

result = dk.price({
    "task": "price",
    "market": {
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "SPX", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "USD_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "SPX_IV", "kind": "constant", "value": 0.2}],
    },
    "product": {
        "type": "vanilla.european",
        "params": {"strike": 100, "maturity": "1y", "call_put": "call"},
    },
    "engine": {"method": "analytic"},
})
print(result.pv, result.greeks)
```

## Product Examples

```python
import derivkit as dk

# Snowball (MC)
result = dk.price("src/derivkit/dsl/examples/snowball_standard.yaml")

# Barrier up-and-out (analytic)
result = dk.price("src/derivkit/dsl/examples/barrier_up_and_out.yaml")
```

More YAML samples: `src/derivkit/dsl/examples/`. API reference: [docs/API.md](docs/API.md).

## PriceAgent (数据接口 + LLM)

在 DerivKit 之上可用 `priceagent` 包做数据查询与 LLM 工具调用定价：

```bash
pip install -e ".[llm]"
cp .env.example .env   # 填入 OPENAI_API_KEY

python -m priceagent demo                              # 无需 LLM，跑通数据+定价
python -m priceagent run "对生猪 LH2409 香草看涨期权定价"
```

配置 Tushare + DeepSeek 的完整演示见 **[docs/RUN_DEMO.md](docs/RUN_DEMO.md)**。  
波动率校准（历史/隐含）见 `dk.calibrate()` 与 [docs/API.md](docs/API.md#calibratespec--pricingresult)。  
隐含波动率可从 Tushare 期权结算价自动拉取：`get_tushare_option_quote` / `calibrate_volatility(method=implied)`。

## QFbench Sandbox

```bash
python -m derivkit.integ.sandbox_runner src/derivkit/integ/tasks/vanilla_european/task.yaml ./output
```

Task instances with grading references: `src/derivkit/integ/tasks/`.

Core algorithms are ported from [PriceLib](https://gitee.com/lltech/pricelib) (Apache 2.0); see `THIRD_PARTY_NOTICES.md`.

## Development

Use the project virtual environment (`.venv/`); do not rely on system Python.

```bash
source .venv/bin/activate
pytest -m "not perf" --cov=derivkit --cov-fail-under=85
python scripts/check_doc_links.py
ruff check .
mypy src
```

See [CHANGELOG.md](CHANGELOG.md) and [docs/API_FREEZE.md](docs/API_FREEZE.md) for release notes and frozen API surface.

## License

MIT
