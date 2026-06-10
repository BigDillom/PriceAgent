# DerivKit 开发进度

> 更新：2026-06-09 | 目标版本：v0.3（第一阶段末）  
> 对照文档：`development_plan.md`（总体规划）、`docs/MULTI_WINDOW_PLAN.md`（多窗口执行计划）、`docs/DEVELOPMENT.md`（开发环境）

---

## 1. 总体进度

| 阶段 | 计划版本 | 状态 | 完成度 |
|------|---------|------|--------|
| 第一阶段 S1 | v0.1 骨架 + 香草解析解 | ✅ 完成 | 100% |
| 第一阶段 S2 | v0.1.x 四引擎交叉校验 | ✅ 完成 | 100% |
| 第一阶段 S3 | v0.2 数据治理初版 | 🔄 部分完成 | ~75% |
| 第一阶段 S4 | v0.2.x 对齐与 validators | 🔄 部分完成 | ~55% |
| 第一阶段 S5 | v0.3 DSL/API/契约 | 🔄 部分完成 | ~85% |
| 第一阶段 S6 | v0.3.x 加固与 QFbench 冒烟 | 🔄 部分完成 | ~40% |
| PriceLib 内化 | W1 任务 | ✅ 完成 | 100% |
| 日历/Schedule | W2 任务 | ✅ 完成 | 100% |
| 障碍/二元/亚式 | W3 任务 | ✅ 完成 | 100% |
| 雪球 PDE | W4 任务 | ✅ 完成 | 100% |
| 雪球 Quad + 凤凰/FCN | W5 任务 | ✅ 完成 | 100% |
| DSL/API + QFbench | W6 任务 | ✅ 完成 | 100% |
| 性能工程 | W7 任务 | ✅ 完成 | 100% |
| 商品端到端 | W8 任务 | ✅ 完成 | 100% |
| 发布准备 | W9 任务 | ✅ 完成 | 100% |

**当前版本**：`0.1.0`（`pyproject.toml`）

---

## 2. 模块完成度明细

### L1 `derivkit.core` — ✅ 90%

| 组件 | 状态 | 备注 |
|------|------|------|
| `enums.py` | ✅ | 受控词表齐全 |
| `observable.py` | ✅ | Observable/Quote |
| `interfaces.py` | ✅ | Process/Engine/Product 抽象 |
| `conventions.py` | ✅ | day-count、tenor 解析 |
| `rng.py` | ✅ | 种子、Sobol/Halton |

待办：Greeks 扰动口径与 pricelib 对齐文档化。

---

### L2a `derivkit.data` — 🔄 70%

| 组件 | 状态 | 备注 |
|------|------|------|
| `term_structures.py` | ✅ | ConstantRate、RateCurve |
| `volmodels.py` | ✅ | ConstantVol、LocalVolSurface 骨架 |
| `calendars.py` | ✅ | 营业日 advance / business_days_between |
| `cn_calendar.py` | ✅ | ChineseCalendar + JSON 节假日（2004–2026） |
| `schedule.py` | ✅ | 月度敲出观察日（锁定期、顺延、跨月修正） |
| `alignment.py` | ✅ | 夜盘 session_close 对齐 + 溯源 meta |
| `validators.py` | 🔄 | 曲线/曲面规则增强 |
| `market_env.py` | ✅ | from_spec + CN 日历注入 |
| `adapters/` | ✅ | equity/commodity 骨架 + 样例数据 |

---

### L2b `derivkit.pricing` — 🔄 60%

| 组件 | 状态 | 备注 |
|------|------|------|
| 香草 `EuropeanVanilla` | ✅ | |
| BSM 过程 | ✅ | |
| `analytic` | ✅ | 自研；**W1 改用 formulas/bsm** |
| `tree` | ✅ | CRR 二叉树 |
| `fdm` | ✅ | FdmGridWithBound（欧式）/ FdmGrid（美式） |
| `mc` | ✅ | 对偶变量 |
| `quad` | ✅ | Simpson 积分（非 FFT） |
| 雪球 | ✅ | MC + FDM + **W5 Quad FFT**（`quad_snowball.py`） |
| 凤凰 `Phoenix` | ✅ | MC（`mc_phoenix.py`） |
| FCN | ✅ | MC + Quad（`quad_fcn.py`） |
| 障碍 `BarrierOption` | ✅ | analytic + MC |
| 二元 `DigitalOption` | ✅ | analytic + MC |
| 亚式 `AsianOption` | ✅ | analytic + MC（几何/算术） |
| `perf/numerical.py` | ✅ | TDMA（自 pricelib 改写） |

---

### L4 `dsl` / `api` / `contract` — 🔄 85%

| 组件 | 状态 | 备注 |
|------|------|------|
| Pydantic schema | ✅ | 香草 + 雪球 + 障碍/二元/亚式 |
| YAML loader | ✅ | |
| DSL examples | ✅ | snowball/barrier 完善 + FDM 变体 |
| `price()` / `risk()` | ✅ | |
| `calibrate()` | ✅ | 历史波动率 + BSM 隐含波动率 |
| 输出契约 | ✅ | |
| API 文档 | ✅ | `docs/API.md` |

---

### L0 `verify` / `integ` — 🔄 65%

| 组件 | 状态 | 备注 |
|------|------|------|
| `oracle.py` | ✅ | 多引擎交叉 |
| `golden/` | 🔄 | 香草 ATM + 障碍/二元/亚式 |
| `sandbox_runner` | ✅ | CLI + 端到端冒烟 |
| `integ/tasks/` | ✅ | vanilla / snowball / barrier 实例 + 容差判分 |
| `grading.py` | ✅ | QFbench 字段级容差 |
| `task_template/` | ✅ | 模板 + 指向实例任务 |

---

## 3. 开发环境

| 项目 | 约定 |
|------|------|
| 虚拟环境 | 项目根 `.venv/`（不提交 Git） |
| Python | ≥ 3.10；本地基准 **3.11.15** |
| 安装 | `pip install -e ".[dev]"` |
| 锁定文件 | `requirements-lock.txt` |
| 文档 | `docs/DEVELOPMENT.md` |

Agent / 多窗口开发须使用 `.venv/bin/python` 与 `.venv/bin/pytest`，勿用系统全局解释器。

---

## 4. 测试与质量

| 指标 | 目标 | 当前 |
|------|------|------|
| 测试用例数 | — | 138 |
| `pytest -m "not perf"` | 全过 | ✅ 138 passed |
| 行覆盖率 | ≥ 85%（阶段末） | ✅ 85.04%（核心模块；Numba JIT 除外） |
| pricelib 运行时依赖 | **0** | ✅ 已移除（仅注释/NOTICE 引用） |
| 确定性测试 | 必过 | ✅ |

---

## 5. 近期变更日志

### 2026-06-09

- 按 `development_plan.md` 搭建 v0.1 骨架
- 香草 5 引擎 + DSL/API + CI
- PriceLib **算法内化**：`formulas/bsm`、`perf/fdm_grid`、`engines/mc_snowball`、`products/snowball`
- 删除 `backends/pricelib_adapter.py`，无运行时 `import pricelib`
- 新增 `docs/MULTI_WINDOW_PLAN.md`、`docs/DEVELOPMENT_PROGRESS.md`、`THIRD_PARTY_NOTICES.md`
- **W2**：`cn_calendar.py` + `resources/cn_holidays.json`、`schedule.py`；对齐/校验加固；14 项新测试
- **W3**：`products/barrier.py`、`digital.py`、`asian.py`；analytic + MC 引擎；DSL 示例；golden 值；13 项新测试
- **W4**：`engines/fdm_snowball.py`（敲入/敲出双网格 PDE）；FDM↔MC 交叉校验；`@pytest.mark.perf` SLA（s_step=400 < 0.3s）；4 项新测试
- **W5**：`perf/quad_fft.py` + `engines/quad_snowball.py`（FFT 积分）；`products/phoenix.py`、`fcn.py`；`mc_phoenix.py`、`quad_fcn.py`；oracle 按产品类型容差矩阵；7 项新测试
- **W6**：DSL 示例加固（`barrier_down_and_in`、`snowball_standard_fdm`）；`integ/tasks/` 三实例 + `grading.py`；`sandbox_runner` CLI；`docs/API.md`；13 项新测试
- **W7**：`perf/mc_kernels.py`（`evolve_bs_log`）、`perf/pde_kernels.py`（`fdm_evolve_step`）、`quad_fft` JIT 权重/`step_backward_jit`；`benchmarks/run_benchmarks.py` + `baseline.json`；CI `perf` job（非阻断）；6 项新测试
- **W8**：`examples/commodity/` 生猪（LH2409）/碳酸锂（LC2409）样例数据与 YAML；夜盘 `session_close` 对齐（`build_valuation_datetime`）；ASF 极端事件稳健性测试集；`dsl/loader` 相对路径解析；13 项新测试
- **W9**：覆盖率 85.04%（`fail_under=85`）；`CHANGELOG.md`、`docs/API_FREEZE.md`、`docs/DOCKER_HARBOR.md`、`docker/Dockerfile`；`scripts/check_doc_links.py` + CI 文档断链检查；`tests/unit/test_w9_release.py`（43 项新测试）
- **环境**：项目根 `.venv/` + `docs/DEVELOPMENT.md` + `requirements-lock.txt` + `.gitignore`

---

## 6. 下一步

1. 与 QFbench 联调容差/通过率阈值对齐（S6 阶段评审）
2. `Schedule` 接入雪球观察日；波动率曲面校准（v0.2+）

---

## 7. 对照里程碑（development_plan.md §11）

| Sprint | 交付物 | 状态 |
|--------|--------|------|
| S1 v0.1 | core + 香草解析解 + CI | ✅ |
| S2 v0.1.x | 四引擎 + 交叉一致性 | ✅ |
| S3 v0.2 | data 利率/波动率/日历/MarketEnv | 🔄 |
| S4 v0.2.x | alignment + validators | 🔄 |
| S5 v0.3 | dsl + api + contract + integ 冒烟 | 🔄 |
| S6 v0.3.x | 文档/覆盖率/性能基准 | 🔄 ~75% |

---

## 8. 已知问题

1. 香草 `quad` 引擎仍为 Simpson 积分；雪球/FCN 已用 FFT 积分（`quad_fft.py`）。
2. 雪球产品尚未切换至 `Schedule`（W4 前可接）。
3. ~~FDM 香草引擎精度弱于 PriceLib~~ — W1 已用 FdmGridWithBound 修复。
4. ~~覆盖率未达 85%~~ — W9 已达标（85.04%，Numba JIT 模块不计入覆盖率）。
