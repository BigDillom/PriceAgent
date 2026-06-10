# Standard Snowball Pricing

Price a knock-in/knock-out snowball structured note using Monte Carlo simulation.

## Input

- `task.yaml`: CSI1000-style market, `snowball.standard` product, MC engine (100k paths, seed 42)

## Output

Write results to `/app/output/result.json` with `pv` and `meta`.

## Command

```bash
python -m derivkit.integ.sandbox_runner task.yaml
```
