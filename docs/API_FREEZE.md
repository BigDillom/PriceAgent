# API Freeze Review — v0.3 Milestone (2026-06-09)

> Status: **Frozen** for phase-one release (`0.1.0` / v0.3 milestone).  
> Breaking changes to the items below require a minor version bump and CHANGELOG entry.

## Frozen public surface

### Package entry (`import derivkit as dk`)

| Symbol | Signature | Notes |
|--------|-----------|-------|
| `price` | `price(spec) → PricingResult` | `spec`: dict, path, or `PricingSpec` |
| `risk` | `risk(spec) → PricingResult` | Ensures greeks in output |
| `calibrate` | `calibrate(spec) → PricingResult` | `pv` = calibrated σ; `meta.calibration_method` = `historical` \| `implied` |

### Exceptions (`derivkit.api.errors`)

| Class | Purpose |
|-------|---------|
| `DerivKitError` | Base exception |
| `DslValidationError` | Pydantic / schema failures (`.errors` list) |
| `PricingError` | Engine failures (`.details` dict) |

### Output contract (`derivkit.contract`)

| Type | Fields / methods |
|------|------------------|
| `PricingResult` | `pv`, `greeks`, `meta`; `to_dict()`, `get()` |
| `OutputContract` | `fields`, `tolerance`, `deterministic`, `seed` |

### DSL (`PricingSpec` schema)

**Tasks**: `price`, `risk`, `calibrate`

**Calibration block** (`task: calibrate`): `method`, `underlying_id`, `window`, `annualization`, `field`, `data`, `market_price` (implied)

**Product types** (frozen identifiers):

| `product.type` | Engines |
|----------------|---------|
| `vanilla.european` | analytic, tree, fdm, mc, quad |
| `snowball.standard` | mc, fdm, quad |
| `phoenix.standard` | mc |
| `fcn.standard` | mc, quad |
| `barrier.up_and_out`, `barrier.down_and_in` | analytic, mc |
| `digital.cash` | analytic, mc |
| `asian.geometric` | analytic, mc |

**Market block**: `valuation_date`, `underlyings[]`, `rates[]`, `vols[]`, optional `calendar` (`CN` / `default`)

**Output block**: `fields`, `tolerance`, `deterministic`, `seed`

### QFbench / Harbor CLI

```bash
python -m derivkit.integ.sandbox_runner <task.yaml> [output_dir]
```

Default output: `result.json` with `pv`, greeks, `meta` (compatible with QFbench grading).

### Integ grading

```python
from derivkit.integ import grade_result, load_expected
```

## Explicitly not frozen (may change in 0.2+)

- Internal modules under `derivkit.pricing.engines.*` constructor kwargs beyond documented DSL `engine.params`
- `derivkit.data.adapters.*` normalization helpers
- `benchmarks/` SLA thresholds and baseline JSON values
- Perf-marked tests (`@pytest.mark.perf`)

## Review checklist (W9)

- [x] Public API documented in `docs/API.md`
- [x] DSL examples cover all frozen product types
- [x] `calibrate()` implemented (historical + implied vol)
- [x] Exception types stable and tested
- [x] Sandbox runner output shape validated by integ tests
- [x] No runtime `import pricelib`

## Approved deferred items (post v0.3)

1. `Schedule` integration for snowball knock-out dates
2. Vol surface calibration (beyond constant σ)
3. Additional product types (DCN, airbag, etc.) — new `product.type` strings only
