# Vanilla European Option Pricing

Price an at-the-money European call option using the analytic BSM engine.

## Input

- `task.yaml`: Market, product (`vanilla.european`), and engine configuration

## Output

Write results to `/app/output/result.json` with:

- `pv`: Present value
- `greeks` (optional): delta, gamma, vega, theta, rho
- `meta`: Engine and alignment metadata

## Command

```bash
python -m derivkit.integ.sandbox_runner task.yaml
```
