# Derivatives Pricing Task Template

Price a derivative using the provided market data and DSL specification.

See instance tasks under `src/derivkit/integ/tasks/` (vanilla, snowball, barrier).

## Input

- `task.yaml`: Pricing specification with market, product, and engine configuration

## Output

Write results to `/app/output/result.json` with:
- `pv`: Present value
- `greeks`: Optional sensitivities (delta, gamma, vega, theta, rho)
- `meta`: Engine and alignment metadata

## Command

```bash
python -m derivkit.integ.sandbox_runner task.yaml
```
