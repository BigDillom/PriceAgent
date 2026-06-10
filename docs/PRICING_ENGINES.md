# 定价引擎说明

本文说明 DerivKit 中 `engine.method` 的含义、五种通用数值方法、各产品支持的引擎，以及**套利定价**与**新产品定价**场景下的选用建议。

DSL 配置示例：

```yaml
engine:
  method: analytic   # analytic | tree | fdm | mc | quad
  params: {...}      # 可选，如 mc 的 n_paths
```

完整 API 见 [API.md](API.md)。

---

## 1. 「analytic 引擎定价」是什么？

**analytic（解析定价 / 闭式公式定价）** 不把期权价值交给随机模拟或偏微分方程网格迭代，而是**直接代入已知数学公式**一步算出结果。

在本项目中，最典型的实现是 **Black-Scholes-Merton（BSM）公式**（`AnalyticEngine` + `derivkit.pricing.formulas.bsm`）：

- 输入：spot、行权价、到期时间、无风险利率、波动率、看涨/看跌
- 输出：欧式香草期权的 PV；可扩展计算 Delta、Gamma、Vega 等希腊字母
- 特点：**极快**（毫秒级）、在模型假设下**精确**、但**仅适用于有闭式解的结构**

模型假设（与 BSM 一致）：标的对数正态、常数波动率、无摩擦、欧式行权（到期才可行权）。

演示或 Agent 中说「用 analytic 引擎定价」，通常指：**对欧式香草期权用 BSM 闭式解计算 PV 和 Delta**。隐含波动率反解（`calibrate(method=implied)`）与 analytic 定价使用同一套 BSM 模型。

---

## 2. 五种通用定价方法

| `engine.method` | 俗称 | 计算思路 | 速度 | 典型用途 |
|-----------------|------|----------|------|----------|
| `analytic` | 解析 / 闭式解 | 套公式（如 BSM） | 最快 | 欧式香草基准价；隐含波动率反解；与市场价对标 |
| `tree` | 二叉/三叉树 | 在离散价格树上向前/向后递推 | 快 | 欧式/美式香草；含早赎条款时 analytic 不适用 |
| `fdm` | 有限差分（PDE） | 在 spot–time 网格上解 BSM 偏微分方程 | 中 | 美式期权；雪球等路径依赖结构（`FdmSnowballEngine`） |
| `mc` | 蒙特卡洛模拟 | 模拟大量随机价格路径，对 payoff 取期望 | 慢（可调精度） | 复杂路径依赖；无闭式解时的通用数值法 |
| `quad` | 数值积分 | 在价格维度上积分（雪球用 FFT 加速） | 中–慢 | 雪球、FCN；常与 MC 交叉验证 |

### 方法对比（通俗理解）

```
analytic  →  有公式就直接算（计算器按公式）
tree/fdm  →  把价格/时间离散化，在网格上推（画表格递推）
mc        →  反复「掷骰子」模拟股价路径，看平均能赚多少
quad      →  对 payoff 在价格轴上做积分（雪球用 FFT 提速）
```

欧式香草五种方法均可使用；项目通过 `derivkit.verify.oracle.cross_check` 在容差内互验，**analytic 通常作为参考基准**。

---

## 3. 各产品支持的引擎

### 3.1 DSL 配置一览

| `product.type` | 可用 `engine.method` |
|----------------|----------------------|
| `vanilla.european` | analytic, tree, fdm, mc, quad |
| `snowball.standard` | mc, fdm, quad |
| `barrier.up_and_out`, `barrier.down_and_in` | analytic, mc |
| `digital.cash` | analytic, mc |
| `asian.geometric` | analytic, mc |
| `phoenix.standard` | mc |
| `fcn.standard` | mc, quad |

YAML 样例：`src/derivkit/dsl/examples/`、`examples/commodity/`。

### 3.2 代码中的具体引擎类

编排层（`engine_orchestrator._create_engine_for_product`）按产品类型选择实现类：

| 实现类 | `method` | 产品 |
|--------|----------|------|
| `AnalyticEngine` | analytic | 欧式香草（BSM） |
| `TreeEngine` | tree | 欧式/美式香草 |
| `FdmEngine` | fdm | 欧式/美式香草 |
| `McEngine` | mc | 欧式香草 |
| `QuadEngine` | quad | 欧式香草（Simpson 积分） |
| `AnalyticBarrierEngine` | analytic | 障碍期权 |
| `McBarrierEngine` | mc | 障碍期权 |
| `AnalyticDigitalEngine` | analytic | 二元期权 |
| `McDigitalEngine` | mc | 二元期权 |
| `AnalyticAsianEngine` | analytic | 几何平均亚式 |
| `McAsianEngine` | mc | 亚式 |
| `McSnowballEngine` | mc | 雪球 |
| `FdmSnowballEngine` | fdm | 雪球 |
| `QuadSnowballEngine` | quad | 雪球（FFT 积分） |
| `McPhoenixEngine` | mc | 凤凰、FCN |
| `QuadFcnEngine` | quad | FCN |

通用工厂 `derivkit.pricing.engines.create_engine(method)` 仅注册香草五引擎；雪球/障碍等产品由编排层路由到上表专用类。

### 3.3 引擎兼容性矩阵（香草）

`derivkit.pricing.engines.COMPATIBILITY_MATRIX` 约束 BSM 过程下行权方式与方法：

| 行权 | 可用方法 |
|------|----------|
| 欧式 `EUROPEAN` | analytic, tree, fdm, mc, quad |
| 美式 `AMERICAN` | tree, fdm, mc（无 analytic 闭式解） |

---

## 4. 业务场景：怎么选引擎？

### 4.1 套利定价（有市场可交易价格）

目标：模型价与市场价对齐，或从市场价反推波动率。

| 步骤 | 推荐 |
|------|------|
| 从期权市场价反推 IV | `calibrate(method=implied)`（BSM 反函数，与 analytic 同模型） |
| 用 IV 给标准化香草定价 | `engine.method: analytic` |
| 校验模型没算错 | 同一 spec 用 tree / mc 等与 analytic 做 `cross_check` |

**主力引擎：`analytic`**。tree、mc 等用于内部交叉验证，不是日常对市价的主引擎。

典型链路（PriceAgent + Tushare）：

```
get_tushare_spot → get_tushare_option_quote / calibrate(implied) → price_tushare_vanilla(engine=analytic)
```

### 4.2 新产品定价（结构化产品，无挂牌价）

目标：对雪球、FCN、凤凰等给出模型公允价，并用多方法互验。

| 产品 | 主力引擎 | 说明 |
|------|----------|------|
| 雪球 | mc、fdm、quad | 无闭式解；三种数值法应在容差内一致 |
| FCN | mc、quad | 同上 |
| 凤凰 | mc | 目前仅蒙特卡洛 |
| 障碍/二元/亚式 | analytic + mc | 有公式时用 analytic 作基准 |

**一般不用 analytic**（除障碍/二元/几何亚式等少数有公式的产品）。新产品定价依赖 **mc / fdm / quad** 及 `oracle` 交叉检验。

---

## 5. 与校准、验证的关系

| 能力 | 说明 |
|------|------|
| `calibrate(historical)` | 从历史价格序列估计 σ，不依赖某一种 pricing engine |
| `calibrate(implied)` | 用 BSM 从期权市场价反解 σ，与 `analytic` 定价模型一致 |
| `verify.oracle.cross_check` | 同一产品结构、多种 engine 算 PV，在容差内互验 |
| QFbench 沙箱 | 对 `result.pv` 与期望值的容差判分 |

---

## 6. 相关文件

| 路径 | 内容 |
|------|------|
| `src/derivkit/pricing/engines/` | 各引擎实现 |
| `src/derivkit/pricing/formulas/bsm.py` | BSM 闭式公式 |
| `src/derivkit/engine_orchestrator.py` | 产品 → 引擎路由 |
| `src/derivkit/verify/oracle.py` | 多引擎交叉检验 |
| `benchmarks/run_benchmarks.py` | 各引擎性能基准 |
