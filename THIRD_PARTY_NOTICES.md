# Third-Party Notices

DerivKit incorporates code adapted from the following open-source projects.

## PriceLib

- **Source**: https://gitee.com/lltech/pricelib
- **Copyright**: Galaxy Technologies (上海凌瓴信息科技有限公司)
- **License**: Apache License 2.0
- **Files adapted in DerivKit**:
  - `src/derivkit/pricing/formulas/bsm.py` — from `analytic_vanilla_european_engine.py`
  - `src/derivkit/pricing/perf/numerical.py` — from `numerical.py` (TDMA)
  - `src/derivkit/pricing/perf/fdm_grid.py` — from `pde_engine_base.py`
  - `src/derivkit/pricing/perf/interpolation.py` — from `numerical.py`
  - `src/derivkit/pricing/perf/mc_kernels.py` — from `bsm_process.py` (`evolve_bs`)
  - `src/derivkit/pricing/perf/pde_kernels.py` — from `pde_engine_base.py`
  - `src/derivkit/pricing/perf/quad_fft.py` — from `quad_engine_base.py` (`step_backward_jit`)
  - `src/derivkit/pricing/engines/mc_snowball.py` — from `mc_autocallable_engine.py`

Modifications include: English docstrings, `MarketEnv`-based interfaces, removal of
global evaluation date, and integration with DerivKit `Product` / `PricingEngine` ABCs.

```
Copyright (C) 2024 Galaxy Technologies
Licensed under the Apache License, Version 2.0
```
