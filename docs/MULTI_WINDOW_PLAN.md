# DerivKit 多窗口开发计划

> 版本：v1.0 | 更新：2026-06-09  
> 目的：在单窗口 context 有限的前提下，将开发任务拆分为可独立加载、有序执行的窗口单元。  
> 使用方式：在新 Cursor 窗口中 `@docs/MULTI_WINDOW_PLAN.md` 并指定窗口编号开始工作。

---

## 1. Context 预算与原则

| 项目 | 估计 |
|------|------|
| 单窗口有效 context | ~80–120K tokens（含代码阅读 + 编辑 + 测试） |
| 大型文件（>500 行） | 每次只读 1–2 个，避免与实现同轮加载 |
| 推荐单窗口产出 | 2–5 个模块文件 + 对应测试 + 文档增量更新 |
| 跨窗口依赖 | 每窗口结束必须：测试通过、更新 `DEVELOPMENT_PROGRESS.md` |

**原则**
1. 先读 `DEVELOPMENT_PROGRESS.md` 确认当前阶段，再读本窗口任务。
2. 使用项目虚拟环境：`.venv/bin/python` / `.venv/bin/pytest`（见 `docs/DEVELOPMENT.md`）。
3. PriceLib 代码以**复制 + 改写**纳入 `derivkit/`，禁止新增 `import pricelib`。
4. 每窗口交付必须可 `pytest` 通过（`-m "not perf"`）。
5. 窗口间通过文件路径交接，不依赖聊天历史。

---

## 2. 窗口总览

| 窗口 | 主题 | 预估 context | 状态 |
|------|------|-------------|------|
| W0 | 骨架 + 香草 + CI（已完成） | — | ✅ 完成 |
| W1 | 文档 + BSM 公式 + FdmGrid 移植 + 去除 pricelib 依赖 | 中 | ✅ 完成 |
| W2 | 中国日历/Schedule + 数据治理加固 | 中 | ✅ 完成 |
| W3 | 障碍/二元/亚式（解析解 + MC） | 大 | ✅ 完成 |
| W4 | 雪球 PDE 引擎（FdmSnowBall 完整移植） | 很大 | ✅ 完成 |
| W5 | 雪球 MC/Quad + 凤凰/FCN 产品 | 大 | ✅ 完成 |
| W6 | DSL/API 扩展 + QFbench 任务模板实例 | 中 | ✅ 完成 |
| W7 | 性能 SLA + numba 热点 + benchmarks | 中 | ✅ 完成 |
| W8 | 商品样例（生猪/碳酸锂）+ 稳健性测试 | 中 | ✅ 完成 |
| W9 | 文档/覆盖率/发布准备 | 小 | ✅ 完成 |

---

## 3. 各窗口详细任务

### W0 — 项目骨架（已完成）

**交付物**
- `derivkit.core` / `data` / `pricing`（香草 5 引擎）/ `dsl` / `api` / `verify` / `integ`
- CI、20+ 测试

**不要在本窗口重复做。**

---

### W1 — PriceLib 内化（当前窗口）

**目标**：移除 `pricelib` 运行时依赖；核心算法迁入本项目。

**必读（本地路径）**
```
/Users/leo/Desktop/pricelib/pricelib/pricing_engines/analytic_engines/analytic_vanilla_european_engine.py
/Users/leo/Desktop/pricelib/pricelib/common/pricing_engine_base/pde_engine_base.py  # FdmGrid 部分
/Users/leo/Desktop/pricelib/pricelib/pricing_engines/mc_engines/mc_autocallable_engine.py
```

**任务清单**
- [x] `docs/MULTI_WINDOW_PLAN.md`、`docs/DEVELOPMENT_PROGRESS.md`
- [x] `derivkit/pricing/formulas/bsm.py` — 移植 `bs_formula`、解析 Greeks
- [x] `derivkit/pricing/perf/fdm_grid.py` — 移植 `FdmGrid`（Crank-Nicolson + TDMA）
- [x] `derivkit/pricing/engines/fdm.py` — 改用 `FdmGridWithBound`（欧式）/ `FdmGrid`（美式）
- [x] `derivkit/pricing/products/snowball.py` — `StandardSnowball` 产品定义
- [x] `derivkit/pricing/engines/mc_snowball.py` — 移植 MC 雪球逻辑
- [x] 删除 `derivkit/backends/pricelib_adapter.py`，更新 orchestrator
- [x] `THIRD_PARTY_NOTICES.md`（Apache 2.0 归属）
- [x] 测试：雪球 MC 冒烟（`tests/integration/test_snowball.py`）

**验收**
```bash
pytest -m "not perf" -q
grep -r "import pricelib" src/   # 应无结果
```

**预估 context 消耗**：~60K（含 2 个 pricelib 源文件精读）

---

### W2 — 日历与数据治理

**目标**：移植 PriceLib 中国区日历与 Schedule，加固 `MarketEnv`。

**必读**
```
pricelib/common/time/calendars.py      # CN 节假日表（大文件，分段读）
pricelib/common/time/timeutils.py      # Schedule, Calendar
```

**任务清单**
- [x] `derivkit/data/cn_calendar.py` — `ChineseCalendar` + 节假日数据（JSON 或内嵌）
- [x] `derivkit/data/schedule.py` — 月度敲出观察日生成（锁定期、顺延规则）
- [x] `derivkit/data/alignment.py` — 增强溯源 meta
- [x] `derivkit/data/validators.py` — 曲面/曲线更多规则
- [x] 单元测试：Schedule 与 CN 节假日边界

**不要在本窗口做**：障碍/雪球 PDE（留给 W3/W4）。

**预估 context**：~70K

---

### W3 — 障碍 / 二元 / 亚式

**目标**：扩展产品线，每种产品至少 2 种方法交叉校验。

**必读（每次 1–2 个）**
```
pricelib/pricing_engines/analytic_engines/analytic_barrier_engine.py
pricelib/pricing_engines/analytic_engines/analytic_digital_engine.py
pricelib/pricing_engines/analytic_engines/analytic_asian_engine.py
pricelib/pricing_engines/mc_engines/mc_barrier_engine.py
```

**任务清单**
- [x] `products/barrier.py`, `digital.py`, `asian.py`
- [x] `engines/analytic_barrier.py` 等（改写为 `MarketEnv` 接口）
- [x] DSL schema 扩展 + examples
- [x] `engine_orchestrator.build_product` 路由
- [x] 集成测试 + golden 值

**预估 context**：~90K（分 2 个子会话亦可：W3a 障碍+二元，W3b 亚式）

---

### W4 — 雪球 PDE 引擎

**目标**：移植 `FdmSnowBallEngine`（~700 行），达到 PDE SLA（s_step=400 < 0.3s）。

**必读**
```
pricelib/pricing_engines/fdm_engines/fdm_autocallable_engine.py  # 分段读 358–727 行
pricelib/products/autocallable/autocallable_base.py
```

**前置**：W1 `FdmGrid`、W2 `Schedule` 必须完成。

**任务清单**
- [x] `engines/fdm_snowball.py` — 完整 PDE 逆向迭代（敲入/敲出双网格）
- [x] 与 W1 MC 雪球交叉校验（容差 pv 1e-2）
- [x] 性能测试 `@pytest.mark.perf`

**预估 context**：~100K+（**建议独占一个窗口，不要与其他产品同做**）

---

### W5 — 雪球 MC/Quad 优化 + 结构化扩展

**任务清单**
- [x] 移植 `QuadSnowballEngine`（scipy/numpy FFT 改写）
- [x] `products/phoenix.py`, `fcn.py`（参数模型 + 引擎路由）
- [x] oracle 容差矩阵按方法配置

**预估 context**：~90K

---

### W6 — DSL / API / QFbench 集成

**任务清单**
- [x] 完善 `snowball.standard` / `barrier.*` DSL 示例
- [x] `integ/tasks/` 真实任务实例（vanilla / snowball / barrier）+ pytest 容差判分
- [x] `sandbox_runner` 端到端冒烟（含 `python -m` CLI）
- [x] API 文档片段（`docs/API.md` + README 更新）

**预估 context**：~50K

---

### W7 — 性能工程

**任务清单**
- [x] `benchmarks/` 脚本与基线 JSON
- [x] numba 热点：MC 路径、PDE 推进（对照 pricelib `evolve_bs`, `step_backward_jit`）
- [x] CI perf 趋势（非阻断）

**预估 context**：~60K

---

### W8 — 商品端到端

**任务清单**
- [x] `examples/commodity/` 生猪、碳酸锂样例数据与 YAML
- [x] 夜盘 `align_policy` 端到端测试
- [x] 极端事件稳健性测试集（占位数据亦可）

**预估 context**：~60K

---

### W9 — 发布准备

**任务清单**
- [x] 覆盖率 ≥ 85%（核心模块；Numba JIT 内核 excluded from coverage instrumentation）
- [x] CHANGELOG、API 冻结审查（`CHANGELOG.md`、`docs/API_FREEZE.md`）
- [x] Docker/Harbor 依赖清单（`docker/`、`docs/DOCKER_HARBOR.md`）
- [x] 全量回归 + 文档断链检查（`scripts/check_doc_links.py`、CI）

**预估 context**：~40K

---

## 4. 窗口启动 Prompt 模板

复制到新窗口即可：

```
请阅读 @docs/DEVELOPMENT_PROGRESS.md、@docs/MULTI_WINDOW_PLAN.md 和 @docs/DEVELOPMENT.md，
执行窗口 W{N} 的全部任务。使用项目 .venv（source .venv/bin/activate 或 .venv/bin/pytest）。
PriceLib 源码在 /Users/leo/Desktop/pricelib，通过复制改写纳入 derivkit，不要 import pricelib。
完成后更新 DEVELOPMENT_PROGRESS.md 并用 .venv/bin/pytest -m "not perf" 验证。
```

将 `{N}` 替换为 1–9。

---

## 5. PriceLib → DerivKit 移植映射表

| PriceLib 路径 | DerivKit 目标 | 窗口 |
|---------------|---------------|------|
| `analytic_vanilla_european_engine.py` | `pricing/formulas/bsm.py` + `engines/analytic.py` | W1 |
| `pde_engine_base.py` (FdmGrid) | `pricing/perf/fdm_grid.py` | W1 |
| `fdm_vanilla_engine.py` | `pricing/engines/fdm.py` | W1 |
| `mc_autocallable_engine.py` | `pricing/engines/mc_snowball.py` | W1 |
| `standard_snowball.py` | `pricing/products/snowball.py` | W1 |
| `calendars.py` + `timeutils.py` | `data/cn_calendar.py`, `data/schedule.py` | W2 |
| `analytic_barrier_engine.py` | `engines/analytic_barrier.py` | W3 |
| `fdm_autocallable_engine.py` | `engines/fdm_snowball.py` | W4 |
| `quad_snowball_engine.py` | `engines/quad_snowball.py` | W5 |
| `numerical.py` (TDMA) | `pricing/perf/numerical.py` | W1 ✅ |

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 单窗口 context 不足读完 FDM 雪球 | W4 独占；分段读 `fdm_autocallable_engine.py` |
| 移植后数值偏差 | 每窗口写 cross-check 测试；保留 pricelib 本地路径仅作对照（不 import） |
| 节假日数据过大 | 抽 JSON 资源文件，不全量塞进 Python |
| 并行多窗口改同一文件 | 按窗口边界划分目录；合并前跑全量测试 |
