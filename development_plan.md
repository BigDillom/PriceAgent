# 面向金融衍生品的大模型智能体建模与求解组件 —— 工业化开发计划

> 文档版本：v1.0　|　适用范围：研发团队、工程负责人、测试与运维　|　对应项目：QFbench 互补课题（衍生品建模与求解模块）
> 工作代号：**DerivKit**（下文统一使用此代号指代本项目所开发的组件集合）

---

## 0. 文档说明

- **目的**：给出一份可直接据以排期、分工、编码、测试、发布的工业化开发计划，覆盖从架构设计到交付验收的全流程。
- **读者**：项目负责人、模块负责人、研发工程师、测试工程师、与腾讯方对接的集成工程师。
- **约定**：
  - 所有对外可见名称、接口、目录均采用英文；文档说明采用中文。
  - 时间以相对里程碑 `T`（项目启动日）表示，与任务书三阶段（T~T+4 / T+4~T+8 / T+8~T+12）对齐。
  - 版本号遵循语义化版本 SemVer（`MAJOR.MINOR.PATCH`）。

---

## 1. 项目目标与范围

### 1.1 一句话目标
开发一组**介于大模型智能体与底层数值计算之间、可被智能体可靠调用**的衍生品建模与求解组件，使智能体面对衍生品任务时，由"逐任务手写数据处理与求解代码"转为"声明式调用稳定、可复用的接口"，并可在 QFbench/Harbor 沙箱中被自动校验。

### 1.2 两大可交付模块
1. **跨资产数据治理模块（Data Governance, `dk.data`）**：处理标的/利率/波动率/期权链等多类型、多频率、多交易时段数据的对齐与约定切换。
2. **非线性建模与求解模块（Modeling & Solving, `dk.pricing`）**：多方法求解器 + 可组合的随机过程/波动率算子（含课题组前期 Levy-GARCH/跳跃/TCN/Quant-GANs 成果的算子化）。

两模块通过**统一领域 API（`dk.api`）+ 受控配置 DSL（`dk.dsl`）+ 显式输出契约（`dk.contract`）**对智能体暴露，并由**验证层（`dk.verify`）**与**集成层（`dk.integ`）**对接 QFbench。

### 1.3 成功标准（量化）
| 维度 | 指标 | 目标 |
|---|---|---|
| 正确性 | 解析解 vs 数值解多方法交叉一致性 | 相对误差 ≤ 阶段约定容差（默认 PV 1e-2） |
| 智能体可用性 | QFbench 衍生品任务一次性通过率 | 较"逐任务人工定制"基线显著提升（阈值第一阶段与腾讯对齐） |
| 边际成本 | 接入新衍生品任务所需人工改写量 | 随任务数量近似常数（非线性增长视为不达标） |
| 可复现 | 同输入+同种子的结果 | 逐位（bitwise）一致；CI 中确定性测试通过 |
| 质量 | 单元测试行覆盖率 | 核心模块 ≥ 85% |
| 性能 | 经典结构定价时延 | 见 §9 性能 SLA |

### 1.4 非目标（Out of Scope）
- 不重复 QFbench 的评测器/沙箱底座本身（由腾讯提供）。
- 不做实时行情接入与交易撮合；行情以离线/快照数据为主。
- 一期不覆盖资金/利息现金流账务系统、利率/汇率类衍生品（列入后续扩展）。

---

## 2. 总体架构

### 2.1 分层架构
```
┌───────────────────────────────────────────────────────────┐
│  大模型智能体（Claude / GPT / Gemini）  —— 调用方            │
└───────────────────────────────────────────────────────────┘
              │ 声明式调用（YAML/JSON DSL）/ Python 高层 API
┌───────────────────────────────────────────────────────────┐
│  L4 智能体调用层  dk.api / dk.dsl / dk.contract             │
│   · 高层函数 price()/calibrate()/risk()                     │
│   · 受控配置 DSL 解析与校验（pydantic schema）              │
│   · 显式输出契约（字段 + 数值容差 + 确定性声明）            │
├───────────────────────────────────────────────────────────┤
│  L3 编排层  dk.engine_orchestrator                          │
│   解析 DSL → 构建 MarketEnv → 组装 product+engine+process   │
│   → 求解 → 按契约格式化输出 → （沙箱内）回写                 │
├───────────────────────────────────────────────────────────┤
│  L2a 数据治理 dk.data        │  L2b 建模求解 dk.pricing      │
│  · adapters（分资产类）       │  · products（产品定义）       │
│  · term_structures（利率）    │  · processes（随机过程）      │
│  · volmodels（波动率）        │  · engines（解析/树/PDE/MC/积分）│
│  · calendars（交易日历/约定） │  · greeks（敏感性）           │
│  · alignment（跨资产对齐）    │  · perf（向量化/JIT/并行）    │
│  · validators（数据质检）     │                               │
├───────────────────────────────────────────────────────────┤
│  L1 公共内核  dk.core                                       │
│   enums（受控词表）· observable（单一数据源+自动传播）       │
│   · 抽象接口（Process/Engine/VolModel/Product 基类）        │
├───────────────────────────────────────────────────────────┤
│  L0 集成与验证  dk.integ（QFbench/Harbor 适配）/ dk.verify  │
└───────────────────────────────────────────────────────────┘
```

### 2.2 设计原则
- **策略 + 组合**：`产品 ← 求解引擎 ← 随机过程 ← 波动率模型` 四层均面向抽象接口，运行时可切换、可组合（新增产品/方法不影响公共内核）。
- **单一数据源 + 自动传播（观察者）**：行情参数（标的/利率/分红/波动率）为被观察对象，过程与引擎订阅其变更，保证一致性并支持增量重算与缓存。
- **受控词表即 DSL**：所有可选项（产品类型、行权方式、引擎方法、波动率类型、日历、day-count、随机数方法等）由枚举/schema 约束，杜绝自由文本，天然可校验、可被大模型稳定生成。
- **可验证优先**：每个产品至少由两种方法交叉校验；显式输出契约 + 数值容差是一等公民。
- **确定性**：随机过程统一种子管理，沙箱内结果逐位可复现。

### 2.3 控制流（一次定价请求）
1. 智能体提交 DSL（或调用高层 API）。
2. L4 解析并 schema 校验 → 失败即返回结构化错误（含字段路径）。
3. L3 调 `dk.data` 构建 `MarketEnv`（对齐+约定切换+质检）。
4. L3 按 DSL 组装 `product/engine/process/vol`。
5. 求解 → 计算 greeks（按需）。
6. 按输出契约格式化（字段/精度/单位）→ 校验容差 → 返回。
7. 沙箱场景下，`dk.integ` 将产出写入 `/app/output`，由 QFbench 的 pytest 校验并回写 reward。

---

## 3. 技术栈与工程规范

### 3.1 技术栈
| 类别 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.10+ | 与沙箱基础镜像一致 |
| 数值计算 | numpy, scipy, pandas | 向量化、插值、统计 |
| 加速 | numba（JIT）、pyfftw/scipy.fft（FFT） | 热点路径加速 |
| 配置/校验 | pydantic v2、PyYAML | DSL schema 与解析 |
| 测试 | pytest、pytest-cov、hypothesis | 单元/集成/属性测试 |
| 质量 | ruff、flake8、pylint、mypy、black、isort | 静态检查与格式化 |
| 文档 | mkdocs-material 或 Sphinx | API 文档与教程 |
| 打包 | hatch/poetry + build | wheel/sdist |
| 容器 | Docker | 与 Harbor 沙箱对齐 |
| CI/CD | GitHub Actions / GitLab CI | 见 §10 |
| 预提交 | pre-commit | 本地门禁 |

### 3.2 编码规范
- 全量类型注解；公共 API 必须有 docstring（含参数/返回/异常/示例）。
- 公共接口稳定性：标注 `@public`，破坏性变更须升 MAJOR 并写迁移说明。
- 数值约定统一（年化天数、day-count、greeks 定义口径）集中在 `dk.core.conventions`，避免散落。
- 严禁在库内 `print`；统一 `logging`，日志可开关、可落文件。
- 随机性必须经 `dk.core.rng` 统一入口（种子可注入、可复现）。

### 3.3 分支与协作
- 主干 `main`（受保护，仅经 PR 合入）；开发 `dev`；特性 `feat/*`；修复 `fix/*`；发布 `release/x.y`。
- 提交信息遵循 Conventional Commits（`feat: / fix: / test: / docs: / perf: / refactor:`）。
- 每个 PR 必须：通过 CI 全门禁 + 至少 1 名 reviewer + 关联 issue。

---

## 4. 代码仓库结构

```
derivkit/
├─ pyproject.toml / hatch.toml          # 打包与依赖
├─ README.md  CHANGELOG.md  LICENSE
├─ .pre-commit-config.yaml  ruff.toml  mypy.ini
├─ docs/                                # mkdocs 文档与教程
├─ src/derivkit/
│  ├─ core/                             # L1 公共内核
│  │  ├─ enums.py                       # 受控词表
│  │  ├─ observable.py                  # 被观察者/观察者
│  │  ├─ interfaces.py                  # Process/Engine/VolModel/Product 抽象基类
│  │  ├─ conventions.py                 # 年化/day-count/greeks 口径
│  │  └─ rng.py                         # 统一随机数与种子
│  ├─ data/                             # L2a 数据治理
│  │  ├─ adapters/{equity,index,fund,futures,commodity}.py
│  │  ├─ term_structures.py             # 常数利率 / 利率曲线 / 折现曲线
│  │  ├─ volmodels.py                   # 常数/局部/曲面/随机/跳跃
│  │  ├─ calendars.py                   # 交易日历/营业日规则/日程
│  │  ├─ alignment.py                   # 跨资产对齐与约定切换
│  │  ├─ validators.py                  # 数据质检规则
│  │  └─ market_env.py                  # MarketEnv 聚合
│  ├─ pricing/                          # L2b 建模求解
│  │  ├─ products/{vanilla,asian,digital,barrier,autocallable,accrual}.py
│  │  ├─ processes/{bsm,heston,levy,levy_garch,scenario_gan}.py
│  │  ├─ engines/{analytic,tree,fdm,mc,quad}/...
│  │  ├─ greeks.py
│  │  └─ perf/{numba_kernels,parallel,fft}.py
│  ├─ api/                              # L4 高层 API
│  │  ├─ facade.py                      # price()/risk()/calibrate()
│  │  └─ errors.py
│  ├─ dsl/                              # L4 DSL
│  │  ├─ schema.py                      # pydantic 模型
│  │  ├─ loader.py                      # YAML/JSON → spec
│  │  └─ examples/*.yaml
│  ├─ contract/                         # L4 输出契约
│  │  └─ output_contract.py
│  ├─ verify/                           # L0 验证
│  │  ├─ oracle.py                      # 多方法交叉一致性
│  │  └─ golden/                        # 黄金基准值
│  └─ integ/                            # L0 QFbench/Harbor 集成
│     ├─ sandbox_runner.py
│     └─ task_template/                 # task.toml/instruction.md/test 模板
├─ tests/
│  ├─ unit/  integration/  property/  determinism/  perf/
│  └─ resources/                        # 测试数据（行情/曲线/曲面）
├─ benchmarks/                          # 性能基准脚本与报告
└─ examples/                            # 端到端使用示例（含 生猪/碳酸锂）
```

---

## 5. 模块详细设计

### 5.1 公共内核 `dk.core`
- **`enums.py`（受控词表）**：`AssetClass{equity,index,fund,futures,commodity}`、`CallPut`、`ExerciseType{european,american,asian,bermudan}`、`BarrierType`、`EngineMethod{analytic,tree,fdm,mc,quad}`、`VolType{constant,local,surface,stochastic,jump}`、`ProcessType{bsm,heston,levy,levy_garch,scenario}`、`DayCount{ACT365,ACT360,ACT_ACT,...}`、`Compounding{simple,continuous,annual}`、`BusinessConvention{preceding,following,modified}`、`RandsMethod`、`QuadMethod`。
- **`observable.py`**：`Observable` / `Observer` / `Quote`（标量行情）/ `update-notify` 机制；下游缓存随变更失效。
- **`interfaces.py`（抽象基类）**：
```python
class StochProcess(ABC):
    @abstractmethod
    def evolve(self, t, x, dt, dw): ...
    @abstractmethod
    def drift(self, t): ...
    @abstractmethod
    def diffusion(self, t, x): ...
    @abstractmethod
    def pde_coef(self, t, x): ...        # 返回 PDE 系数 (a,b,c)

class VolModel(ABC):
    vol_type: VolType
    @abstractmethod
    def __call__(self, t, spot): ...     # 返回波动率

class PricingEngine(ABC):
    method: EngineMethod
    @abstractmethod
    def calc_present_value(self, product, env, t=None, spot=None): ...
    def calc_greeks(self, product, env, which): ...

class Product(ABC):
    @abstractmethod
    def payoff(self, path_or_spot): ...
    def price(self, engine=None, env=None): ...   # 默认引擎可推断
```
- **`conventions.py` / `rng.py`**：年化天数（365/360/243/244）、day-count 换算、greeks 定义（delta/gamma/vega/theta/rho 的扰动口径）；随机数统一入口与种子。

### 5.2 跨资产数据治理模块 `dk.data`
- **`adapters/`**：每类资产一个适配器，将原始行情归一化为统一 schema（见 §7）。处理：标的分时/收盘字段抽取、复权、单位归一、缺失与停牌标记。
- **`term_structures.py`**：
  - `ConstantRate`（一次性快照）与 `RateCurve`（分段曲线，线性/对数折现插值），统一 `__call__(t)` 与 `disc_factor(t2, t1)`。
  - 内置 day-count、复利约定、节假日日历归一。
- **`volmodels.py`**：`ConstantVol` / `LocalVolSurface` / `StochasticVol(Heston)` 提供统一 `vol(t, spot)`；跳跃/Levy 类波动在 `dk.pricing.processes` 中以过程形式承接，但在此登记口径（恒定/时变/曲面）。
- **`calendars.py`**：`Calendar`（节假日集合、`advance`、`business_days_between`）、`Schedule`（按频率/锁定期/营业日规则自动生成观察日序列）、营业日调整（提前/延后/修正跟随）、跨月修正。
- **`alignment.py`（核心难点）**：
  - **收盘时间对齐**：按各资产 `session_close` 与时区，将跨资产数据对齐到统一估值时点；对 A 股 15:00 与商品期货夜盘给出可配置对齐策略（同日/前一交易日/最近可用）。
  - **日历对齐**：多市场日历并/交集；缺失值填充策略（前值/插值/丢弃，可配置且可审计）。
  - **约定切换**：利率（快照↔曲线、day-count、复利）、波动率（恒定↔时变↔曲面）口径自动切换并记录转换溯源。
- **`validators.py`**：单调性、非负、无穷/NaN、期限覆盖、曲面无套利的基本检查；产出结构化质检报告。
- **`market_env.py`**：`MarketEnv` 聚合 valuation_date + underlyings + rates + vols + calendars，作为求解的唯一输入上下文。

### 5.3 非线性建模与求解模块 `dk.pricing`
- **`products/`**：vanilla（欧/美式、价差/跨式等组合）、asian、digital（含双边）、barrier（单/双边、安全气囊）、autocallable（雪球/凤凰/FCN/DCN 及变种）、accrual。每产品声明默认引擎与支持引擎集合。
- **`processes/`**：
  - `bsm`（广义 BSM：股票/连续股利/期货/外汇）、`heston`（随机波动）。
  - `levy`（无限纯跳 Levy 过程）、`levy_garch`（跳跃测度 + 时变波动，承接课题组成果）、`scenario_gan`（TCN/Quant-GANs 情景路径生成，用于 MC）。
  - 全部实现 `StochProcess` 接口 → 可被任意兼容引擎调用。
- **`engines/`**：
  - `analytic`（闭式/近似解）、`tree`（二叉/三叉）、`fdm`（PDE 有限差分，三对角快速求解、显式/隐式/Crank–Nicolson）、`mc`（方差缩减：对偶变量/控制变量；低差异序列 Sobol/Halton；路径复用）、`quad`（FFT 数值积分，O(N log N)）。
  - 引擎与过程/波动率的兼容矩阵在 `engines/__init__.py` 中声明并在运行时校验。
- **`greeks.py`**：统一 5 类希腊值；PDE/MC 下的网格/扰动法实现。
- **`perf/`**：numba 内核、并行（路径/格点）、FFT；JIT 缓存管理（移动目录后清缓存的运维说明）。

### 5.4 智能体调用层 `dk.api` / `dk.dsl` / `dk.contract`
- **两层 API**：
  - *高层*：`price(spec) -> Result`、`risk(spec)`、`calibrate(spec)`；spec 可为 DSL 文件或 dict。自动选默认引擎与合理默认参数。
  - *进阶*：直接构造 `MarketEnv + Product + Engine + Process + Vol`，完全可控。
- **DSL（受控配置）**：pydantic schema 严格约束（枚举闭集、必填校验、范围检查）；解析失败返回字段级错误。
- **输出契约**：声明字段集合、单位、数值精度/容差、是否确定性与种子；用于沙箱自动判分。

### 5.5 QFbench/Harbor 集成层 `dk.integ`
- `sandbox_runner`：在沙箱内读取 `instruction.md` 解析出的 spec → 调 API → 写 `/app/output`。
- `task_template/`：提供与 QFbench 目录规范一致的 `task.toml / instruction.md / environment / tests / solution` 模板，便于课题组贡献衍生品任务。
- 镜像：维护与腾讯共享基础镜像兼容的依赖清单（numpy/scipy/numba/pandas 等），固定版本。

### 5.6 验证层 `dk.verify`
- `oracle.py`：对同一 spec 用多引擎求解并比对（容差矩阵按方法设定）；作为开发期与回归期的"内部判分"。
- `golden/`：关键产品的黄金基准值（来源：闭式解或高精度 MC），纳入回归。

---

## 6. 领域 API 与配置 DSL 规范（示例）

### 6.1 DSL 示例（雪球定价，YAML）
```yaml
task: price                      # price | risk | calibrate
market:
  valuation_date: 2024-01-05
  underlyings:
    - id: CSI1000
      asset_class: index
      spot:
        source: csv
        path: data/csi1000.csv
        field: close
        tz: Asia/Shanghai
        session_close: "15:00"
  rates:
    - id: CN_RF
      kind: curve                # curve | constant
      day_count: ACT/365
      compounding: continuous
      calendar: CN
      data: { source: csv, path: data/rate_curve.csv }
  vols:
    - id: CSI1000_IV
      kind: surface              # constant | local | surface | stochastic | jump
      data: { source: csv, path: data/iv_surface.csv }
product:
  type: snowball.standard
  params:
    s0: 100, barrier_out: 103, barrier_in: 80
    coupon_out: 0.113, maturity: 1y, lock_term: 3m
engine:
  method: fdm                    # analytic | tree | mc | fdm | quad
  params: { s_step: 400, n_smax: 4, scheme: crank_nicolson }
output:
  fields: [pv, delta, gamma, vega, theta, rho]
  tolerance: { pv: 1.0e-2 }
  deterministic: true
  seed: 0
```

### 6.2 高层 API 示例（Python）
```python
import derivkit as dk

# 1) 声明式：智能体最常用
result = dk.price("task.yaml")
print(result.pv, result.greeks, result.meta)   # meta 含使用的引擎/过程/对齐溯源

# 2) 程序化：完全可控
env = dk.MarketEnv.from_spec("task.yaml")       # 已完成对齐+约定切换+质检
opt = dk.products.StandardSnowball(s0=100, barrier_out=103, barrier_in=80,
                                   coupon_out=0.113, maturity="1y", lock_term="3m")
res = opt.price(engine=dk.engines.Fdm(scheme="crank_nicolson"), env=env)
```

### 6.3 跨资产对齐示例（商品期权，含夜盘）
```yaml
underlyings:
  - id: LC2409                   # 碳酸锂期货
    asset_class: commodity
    spot: { source: csv, path: data/lc.csv, field: close,
            tz: Asia/Shanghai, session_close: "23:00", align_policy: nearest_available }
```
> `align_policy` 取值：`same_day | prev_business_day | nearest_available`；对齐结果与口径写入 `result.meta.alignment`，可审计。

---

## 7. 数据规范与数据治理

### 7.1 归一化行情 schema（内部统一）
| 字段 | 类型 | 说明 |
|---|---|---|
| `instrument_id` | str | 标的/合约唯一标识 |
| `asset_class` | enum | equity/index/fund/futures/commodity |
| `datetime` | tz-aware | 含时区与交易时段 |
| `ohlcv` | float | 开高低收量（按需） |
| `session_close` | str | 该资产收盘时点 |
| `adj_flag` | enum | 复权方式 |
| `quality` | struct | 缺失/停牌/异常标记 |

### 7.2 数据治理规则（可审计）
- 所有缺失填充、对齐、约定转换均**记录溯源**（输入→规则→输出），随结果返回 `meta`。
- 利率：支持快照与曲线两种来源；曲线含期限、零息/折现、day-count、复利；越界水平/线性外推策略可配置。
- 波动率：常数/时变/曲面；曲面做基本无套利检查；隐含↔历史口径转换需显式声明。

### 7.3 重点商品数据（生猪 / 碳酸锂）
- 依托课题组前期国社科/省自科项目数据与方法积累获取并扩展；建立 `examples/commodity/` 端到端样例（数据接入→建模→定价/对冲→风险评估）。
- 极端事件场景（如非洲猪瘟类）单列稳健性测试集。

---

## 8. 测试与质量保障

### 8.1 测试金字塔
| 层级 | 目录 | 内容 | 门禁 |
|---|---|---|---|
| 单元 | `tests/unit` | 函数/类级（曲线插值、日历、payoff、单引擎） | 覆盖率 ≥ 85% |
| 属性 | `tests/property` | hypothesis 随机参数下不变量（如看涨看跌平价、单调性） | 必过 |
| 交叉一致性（oracle） | `tests/integration` | 同产品多引擎结果在容差内一致 | 必过 |
| 黄金回归 | `tests/integration` | 与 `verify/golden` 基准比对 | 必过 |
| 确定性 | `tests/determinism` | 同输入+种子逐位一致 | 必过 |
| 性能 | `tests/perf` | 时延/收敛基准（非阻断，记录趋势） | 趋势监控 |
| 端到端 | `examples` + `dk.integ` | 沙箱内 DSL→产出→pytest 容差 | 必过 |

### 8.2 交叉一致性测试示例
```python
@pytest.mark.parametrize("method", ["analytic", "mc", "tree", "fdm", "quad"])
def test_vanilla_cross_consistency(method, golden_vanilla, tol):
    pv = dk.price(spec_vanilla, engine=method).pv
    assert abs(pv - golden_vanilla) <= tol[method]
```

### 8.3 质量门禁（CI 必过项）
- ruff/flake8/pylint 无新增告警；mypy 无类型错误；black/isort 已格式化。
- 全部"必过"测试通过；覆盖率不低于阈值且不回退。
- 文档构建无断链；公共 API 变更附 CHANGELOG。

---

## 9. 性能工程

### 9.1 加速手段
- numpy 向量化 + numba JIT（热点：MC 路径演化、PDE 推进、payoff）。
- PDE 三对角矩阵用 Thomas 算法（优于求逆/LU）。
- MC 方差缩减（对偶/控制变量）+ 低差异序列（Sobol/Halton）+ 路径复用。
- 数值积分用 FFT，将 O(N²)→O(N log N)。
- 路径/格点级并行；JIT 缓存管理。

### 9.2 性能 SLA（单机参考目标，CPU）
| 产品/方法 | 规模 | 目标时延 |
|---|---|---|
| 香草 解析解 | 单笔 | < 5 ms |
| 香草/价差 MC | 10 万路径 | < 0.6 s |
| 雪球 PDE | s_step=400 | < 0.3 s |
| 雪球 FFT 积分 | 标准 | < 0.2 s |
| 障碍/二元 多法交叉 | 单笔全方法 | < 1.5 s |
> SLA 写入 `benchmarks/`，每次发布出报告并对比上版（回退超 15% 触发告警）。

---

## 10. CI/CD 与发布

### 10.1 流水线阶段
1. `lint`（ruff/flake8/pylint/mypy/black-check）
2. `test`（unit/property/integration/determinism + 覆盖率）
3. `build`（wheel/sdist）
4. `docker`（构建与 Harbor 兼容镜像，跑端到端沙箱冒烟）
5. `docs`（构建并校验）
6. `release`（打 tag → 发布制品 → 生成 CHANGELOG）

### 10.2 GitHub Actions 片段（示意）
```yaml
name: ci
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.10" }
      - run: pip install -e .[dev]
      - run: ruff check . && mypy src && black --check .
      - run: pytest -m "not perf" --cov=derivkit --cov-fail-under=85
```

### 10.3 版本发布节奏
- 开发期每两周一个里程碑预览（`0.x` 系列）；阶段末打稳定 tag；项目末发布 `1.0.0`。

---

## 11. 里程碑与迭代计划

> 以两周为一个 Sprint。每个版本均含：代码 + 测试 + 文档 + CHANGELOG + 基准报告。

### 第一阶段（T ~ T+4 月）核心模块构建 → 目标版本 `v0.3`
| Sprint | 版本 | 交付物（Definition of Done） |
|---|---|---|
| S1 | v0.1 | `dk.core`（enums/observable/interfaces/conventions/rng）+ 仓库骨架 + CI 全门禁跑通；香草产品 + 解析解引擎；单元+交叉一致性测试 |
| S2 | v0.1.x | 二叉树、PDE、MC、FFT 四引擎对香草打通；多方法交叉一致性达容差；黄金值入库 |
| S3 | v0.2 | `dk.data`：常数/曲线利率、常数/局部/曲面波动率、交易日历与 Schedule；MarketEnv |
| S4 | v0.2.x | `dk.data.alignment` 收盘时间/日历/约定切换 + validators + 溯源 meta |
| S5 | v0.3 | `dk.dsl`+`dk.api`+`dk.contract` 初版；DSL 端到端 `price()`；与 QFbench 接入冒烟（`dk.integ` 模板） |
| S6 | v0.3.x | 阶段加固：文档、覆盖率达标、性能基准首版；**阶段评审与容差/通过率阈值与腾讯对齐** |

**阶段产出**：数据治理模块 V1.0 原型 + 四类基本求解器 V1.0 + 统一领域 API/DSL 初版 + QFbench 接入。

### 第二阶段（T+4 ~ T+8 月）算法引擎工程化与衍生品扩展 → 目标版本 `v0.7`
| Sprint | 版本 | 交付物 |
|---|---|---|
| S7 | v0.4 | 产品扩展：digital/barrier（单双边、安全气囊）/asian，全部多法交叉校验 |
| S8 | v0.4.x | autocallable：雪球/凤凰/FCN/DCN 及主要变种（MC/PDE/积分） |
| S9 | v0.5 | `processes`：Levy、Levy-GARCH（跳跃测度+时变波动）按统一接口封装为算子 |
| S10 | v0.6 | `scenario_gan`：TCN/Quant-GANs 情景路径生成接入 MC；非线性算子组合调用 |
| S11 | v0.6.x | 有界时间精度-稳定性优化（自适应步长/并行/Greeks）+ 性能 SLA 达标 |
| S12 | v0.7 | 与 QFbench 衍生品任务联调，迭代 API 规范；对比评测（vs 人工定制基线） |

**阶段产出**：前期成果算子化 + 典型奇异期权/结构化产品支持 + 精度-稳定性优化 + QFbench 联调对比。

### 第三阶段（T+8 ~ T+12 月）端到端验证与收尾 → 目标版本 `v1.0`
| Sprint | 版本 | 交付物 |
|---|---|---|
| S13 | v0.8 | 商品数据接入（生猪/碳酸锂）+ `examples/commodity` 端到端样例 |
| S14 | v0.8.x | 样本外 + 极端事件稳健性测试集与报告 |
| S15 | v0.9（RC） | 全量回归、文档完善、API 冻结、安全/许可证核查、开源发布准备 |
| S16 | v1.0 | 正式发布：开源组件 + 文档 + 数据集 + 评测报告 + 论文/专利材料归档 |

**阶段产出**：端到端验证报告与对策 + 论文投稿 + 专利材料 + 完整开源交付。

---

## 12. 团队与协作（建议 RACI）

| 工作包 | 负责人 | 配合 |
|---|---|---|
| 总体架构/技术路线/API 规范 | 项目负责人 | 全体 |
| 数据治理模块 `dk.data` | 博士生 | 硕士生（商品数据） |
| 建模求解模块 `dk.pricing` | 博士生 | 项目负责人（非线性算子指导） |
| DSL/API/契约 `dk.api/dsl/contract` | 博士生 | 集成工程 |
| QFbench 集成 `dk.integ` | 集成工程/硕士生 | 腾讯方 |
| 测试/CI/质量门禁 | 硕士/本科生 | 全体 |
| 商品端到端与稳健性 | 硕士生 | 项目负责人 |
| 文档/开源/专利材料 | 硕士/本科生 | 项目负责人 |

- 评审制度：架构评审（阶段初）、代码评审（每 PR）、阶段评审（每阶段末，含与腾讯对齐）。

---

## 13. 风险登记与应对

| 风险 | 影响 | 概率 | 应对 |
|---|---|---|---|
| 跨资产对齐口径分歧导致结果偏差 | 高 | 中 | 对齐策略可配置 + 溯源 meta + 与腾讯任务对齐基准；早期 S4 专项 |
| 非线性/跳跃求解在有界时间内不收敛 | 高 | 中 | 自适应步长/方差缩减/并行；设超时与降级策略；S11 专项 |
| 数据可得性（商品衍生品） | 中 | 中 | 依托课题组前期项目数据；建立合成与脱敏数据兜底 |
| 与 QFbench 接口变更 | 中 | 中 | 集成层薄适配 + 契约版本化；与腾讯定期同步 |
| 确定性/复现失败（随机数/JIT 缓存） | 中 | 低 | 统一 rng 入口 + 确定性测试 + 缓存运维规范 |
| 性能不达 SLA | 中 | 中 | 基准持续监控 + 热点 JIT/FFT/并行；回退告警 |
| 团队对数值方法熟悉度不一 | 中 | 中 | 内部分享 + oracle 兜底 + 结对开发 |

---

## 14. 验收标准与交付物清单

### 14.1 总验收标准
- §1.3 成功标准全部达标；`v1.0` 通过全量回归与端到端沙箱评测。
- 公共 API 文档完整；可由第三方按文档独立复现示例。

### 14.2 交付物清单
1. 开源组件 `derivkit`（源码 + wheel + 文档 + 示例 + 与 Harbor 兼容镜像清单）。
2. QFbench 衍生品任务模板与若干贡献任务（`dk.integ.task_template` + 实例）。
3. 评测报告（一次性通过率、人工成本曲线、多方法一致性、性能基准）。
4. 国内重点商品（生猪/碳酸锂）端到端验证报告与对策建议。
5. 论文初稿与投稿材料；国家发明专利申请材料。

---

## 15. 附录

### 15.1 术语表（节选）
- **MarketEnv**：完成对齐与约定切换后的统一估值上下文。
- **受控配置 DSL**：以枚举闭集与 schema 约束的声明式任务描述，可被大模型稳定生成、可机器校验。
- **输出契约**：对返回字段、单位、数值容差、确定性的显式声明，是自动判分依据。
- **多方法交叉一致性（oracle）**：同一产品由多种数值方法独立求解并在容差内互验。

### 15.2 关键工程约束清单（开发须遵守）
- 所有可选项进受控词表；DSL 不接受自由文本枚举。
- 所有随机性经 `dk.core.rng`；沙箱内必须可逐位复现。
- 所有数据转换可溯源并随结果返回。
- 新增产品/方法必须附：默认引擎、至少两种方法交叉校验、黄金值、文档与示例。
- 公共接口破坏性变更须升 MAJOR 并提供迁移说明。
