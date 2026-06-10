# DerivKit API Reference (v0.1)

High-level entry points for agent and sandbox invocation. All functions accept a DSL spec as a **dict**, **YAML/JSON file path**, or validated `PricingSpec`.

## `price(spec) → PricingResult`

Price a derivative from market, product, and engine configuration.

```python
import derivkit as dk

# Dict spec
result = dk.price({
    "task": "price",
    "market": {
        "valuation_date": "2024-01-05",
        "underlyings": [{"id": "SPX", "asset_class": "index", "spot": 100.0}],
        "rates": [{"id": "USD_RF", "kind": "constant", "value": 0.05}],
        "vols": [{"id": "SPX_IV", "kind": "constant", "value": 0.2, "underlying_id": "SPX"}],
    },
    "product": {
        "type": "vanilla.european",
        "params": {"strike": 100, "maturity": "1y", "call_put": "call"},
    },
    "engine": {"method": "analytic"},
})

# YAML file
result = dk.price("src/derivkit/dsl/examples/snowball_standard.yaml")
```

### `PricingResult`

| Field | Type | Description |
|-------|------|-------------|
| `pv` | `float` | Present value |
| `greeks` | `dict[str, float]` | Sensitivities when requested in `output.fields` |
| `meta` | `dict` | Engine, product type, valuation date, alignment |

`result.to_dict()` serializes to JSON-compatible output for QFbench (`pv`, greeks, `meta`).

### Supported product types

| DSL `product.type` | Engines |
|--------------------|---------|
| `vanilla.european` | analytic, tree, fdm, mc, quad |
| `snowball.standard` | mc, fdm, quad |
| `barrier.up_and_out`, `barrier.down_and_in` | analytic, mc |
| `digital.cash` | analytic, mc |
| `asian.geometric` | analytic, mc |
| `phoenix.standard` | mc |
| `fcn.standard` | mc, quad |

See `src/derivkit/dsl/examples/` for complete YAML samples.

## `risk(spec) → PricingResult`

Same as `price()` but ensures greeks (`delta`, `gamma`, `vega`, `theta`, `rho`) are included in the output.

## `calibrate(spec) → PricingResult`

Calibrate annualized volatility. **`result.pv` is the calibrated σ (decimal, e.g. `0.22` = 22%)**. Details are in `result.meta`.

### Historical volatility

Close-to-close log returns on a price series (CSV path on underlying or `calibration.data`).

```python
result = dk.calibrate("examples/commodity/lh_calibrate_historical.yaml")
print(result.pv)  # calibrated sigma
print(result.meta["calibration"])  # window, n_obs, annualization, ...
```

```yaml
task: calibrate
market:
  valuation_date: "2024-06-14"
  underlyings:
    - id: LH2409
      asset_class: commodity
      spot:
        source: csv
        path: data/lh2409.csv
        field: close
calibration:
  method: historical
  underlying_id: LH2409
  window: 4              # rolling return window (observations)
  annualization: 243     # CN futures trading days
  field: close
```

Data sources for historical calibration:

| Source | Configuration |
|--------|----------------|
| CSV | `underlyings[].spot.source: csv` or `calibration.data: {source: csv, path: ...}` |
| Tushare | `calibration.data: {source: tushare, symbol: LH2409, exchange: DCE}` (requires `TUSHARE_TOKEN`) |

### Implied volatility

Invert BSM from an observed vanilla option price.

**PriceAgent shortcut:** `calibrate_volatility(method=implied, ...)` without `market_price`
auto-fetches a nearby option from Tushare (`opt_basic` contract match + `opt_daily` settle/close).
Use `get_tushare_option_quote` to inspect the matched contract and aligned price first.

```python
result = dk.calibrate("examples/commodity/lh_calibrate_implied.yaml")
```

```yaml
task: calibrate
market:
  valuation_date: "2024-06-14"
  underlyings:
    - id: LH2409
      asset_class: commodity
      spot: 15520.0
  rates:
    - id: CNY_RF
      kind: constant
      value: 0.025
product:
  type: vanilla.european
  params:
    strike: 15500
    maturity: 3m
    call_put: call
calibration:
  method: implied
  underlying_id: LH2409
  market_price: 738.05
```

### Calibrate then price

```python
sigma = dk.calibrate("examples/commodity/lh_calibrate_historical.yaml").pv
spec = dk.price({
    "task": "price",
    "market": {
        "valuation_date": "2024-06-14",
        "underlyings": [{"id": "LH2409", "asset_class": "commodity", "spot": 15520.0}],
        "rates": [{"id": "CNY_RF", "kind": "constant", "value": 0.025}],
        "vols": [{"id": "LH_IV", "kind": "constant", "value": sigma, "underlying_id": "LH2409"}],
    },
    "product": {"type": "vanilla.european", "params": {"strike": 15500, "maturity": "3m", "call_put": "call"}},
    "engine": {"method": "analytic"},
})
```

## DSL structure

```yaml
task: price          # price | risk | calibrate
market:
  valuation_date: "2024-01-05"
  underlyings: [...]
  rates: [...]
  vols: [...]        # optional for calibrate
calibration:         # required when task=calibrate
  method: historical # historical | implied
  underlying_id: LH2409
  window: 20
  annualization: 243
  market_price: 738.05   # implied only
product:
  type: snowball.standard
  params: {...}
engine:
  method: mc
  params: {n_paths: 100000}
output:
  fields: [pv]
  tolerance: {pv: 1.0}
  deterministic: true
  seed: 42
```

Dates must be quoted strings in YAML (`"2024-01-05"`) to avoid implicit date parsing.

## QFbench sandbox

In Harbor/QFbench containers, write output to `/app/output/result.json`:

```bash
python -m derivkit.integ.sandbox_runner task.yaml
python -m derivkit.integ.sandbox_runner task.yaml /app/output
```

Task instances live under `src/derivkit/integ/tasks/` (vanilla, snowball, barrier). Grading:

```python
from derivkit.integ import grade_result, load_expected
import derivkit as dk

result = dk.price("task.yaml")
expected = load_expected("expected.json")
report = grade_result(result, expected)
assert report.passed
```

## Errors

| Exception | When |
|-----------|------|
| `DslValidationError` | Invalid or incomplete DSL spec |
| `PricingError` | Engine or numerical failure |
| `DerivKitError` | Base class for library errors |
