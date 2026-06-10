# Changelog

All notable changes to DerivKit are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- W9 release prep: coverage gate ≥ 85% (core modules; Numba JIT kernels excluded from coverage instrumentation)
- `CHANGELOG.md`, `docs/API_FREEZE.md`, `docs/DOCKER_HARBOR.md`
- `docker/Dockerfile` and `docker/requirements-harbor.txt` for Harbor/QFbench sandboxes
- `scripts/check_doc_links.py` for documentation link validation
- `tests/unit/test_w9_release.py` — API contract, alignment, orchestrator, and data-module coverage

### Changed

- `pyproject.toml` coverage `fail_under` raised from 70 to 85

## [0.1.0] — 2026-06-09

First public alpha aligned with development plan phase-one (v0.3 milestone).

### Added

- **Core (`derivkit.core`)**: enums, observable pattern, process/engine/product interfaces, conventions, RNG (pseudo / Sobol / Halton)
- **Data (`derivkit.data`)**: term structures, vol models, calendars, Chinese calendar + holidays JSON, Schedule, alignment, validators, MarketEnv
- **Pricing (`derivkit.pricing`)**: European vanilla (analytic, tree, FDM, MC, quad); snowball (MC, FDM, quad FFT); phoenix, FCN; barrier, digital, Asian; BSM formulas and processes
- **DSL / API / Contract**: Pydantic schema, YAML loader, `price()`, `risk()`, output contract
- **Verify / Integ**: multi-engine oracle, golden values, QFbench task instances, sandbox runner, grading
- **Examples**: DSL samples, commodity end-to-end (生猪 LH2409, 碳酸锂 LC2409)
- **Benchmarks**: `benchmarks/run_benchmarks.py` + baseline JSON; CI perf job (non-blocking)
- PriceLib algorithm port (Apache 2.0) with zero runtime `import pricelib`
- CI: lint, type-check, format, test with coverage
- Documentation: `docs/API.md`, `docs/DEVELOPMENT.md`, `docs/MULTI_WINDOW_PLAN.md`, `docs/DEVELOPMENT_PROGRESS.md`

### Known limitations

- `calibrate()` for historical and implied constant volatility
- Vanilla `quad` engine uses Simpson integration (snowball/FCN use FFT quad)
- Snowball observation dates not yet wired to `Schedule`

[Unreleased]: https://github.com/derivkit/derivkit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/derivkit/derivkit/releases/tag/v0.1.0
