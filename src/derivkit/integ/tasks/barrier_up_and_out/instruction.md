# Barrier Up-and-Out Call Pricing

Price an up-and-out barrier call option using the analytic barrier formula.

## Input

- `task.yaml`: SPX market, `barrier.up_and_out` product, analytic engine

## Output

Write results to `/app/output/result.json` with `pv` and `meta`.

## Command

```bash
python -m derivkit.integ.sandbox_runner task.yaml
```
