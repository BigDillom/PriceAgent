# PriceAgent 完整运行演示（Tushare + DeepSeek）

本文档说明如何配置 **Tushare 数据接口** 和 **DeepSeek LLM**，并逐步跑通项目。

---

## 0. 前置条件

| 项目 | 要求 |
|------|------|
| Python | ≥ 3.10（推荐 3.11） |
| Tushare | 在 [tushare.pro](https://tushare.pro/register) 注册并获取 Token |
| DeepSeek | 在 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 申请 API Key |
| 网络 | 能访问 Tushare 与 DeepSeek API |

> Tushare 期货/期权日线接口（`fut_daily` / `opt_daily`）需要一定积分（通常 ≥2000）；若积分不足，可先用本文 **第 3 节** 的离线 CSV 演示。

---

## 1. 环境安装

在项目根目录 `PriceAgent/` 执行：

```bash
# 创建并激活虚拟环境
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 安装 DerivKit + PriceAgent + Tushare + DeepSeek 依赖
pip install --upgrade pip
pip install -e ".[dev,agent]"
```

验证安装：

```bash
.venv/bin/python -c "import derivkit, priceagent; print('OK')"
```

---

## 2. 配置 `.env`

```bash
cp .env.example .env
```

编辑 `.env`，填入你的真实密钥：

```bash
# DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx      # 与 DEEPSEEK_API_KEY 相同即可
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# Tushare
TUSHARE_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 配置说明

| 变量 | 作用 |
|------|------|
| `TUSHARE_TOKEN` | Tushare Pro API Token，用于拉取期货/股票/期权日线 |
| `DEEPSEEK_API_KEY` | DeepSeek 平台 API Key |
| `OPENAI_BASE_URL` | 固定为 `https://api.deepseek.com`（OpenAI SDK 兼容） |
| `OPENAI_MODEL` | 推荐 `deepseek-chat`；推理任务可用 `deepseek-reasoner` |
| `LLM_PROVIDER=deepseek` | 自动使用 DeepSeek 默认地址与模型 |

---

## 3. 演示 A：离线 CSV（无需 Tushare，验证定价链路）

```bash
source .venv/bin/activate

# 3.1 列出内置数据集与 YAML 样例
python -m priceagent list

# 3.2 数据 + 定价联调（生猪 LH2409，内置 CSV）
python -m priceagent demo

# 3.3 直接定价（无 Agent）
python -m priceagent direct examples/commodity/lh_vanilla_call.yaml
```

**预期输出要点：**

- `lh2409_spot.spot` = `15520.0`（2024-06-14 夜盘收盘价）
- `pricing.pv` ≈ `738`（3 个月看涨，strike=15500）

---

## 4. 演示 B：Tushare 数据接口（无需 LLM）

从 Tushare 拉取生猪期货 LH2409 日线，对齐 spot 并定价：

```bash
source .venv/bin/activate
python -m priceagent tushare-demo --symbol LH2409 --date 2024-06-14 --strike 15500
```

**执行流程：**

```
Tushare fut_daily(LH2409.DCE)
    → 归一化为 DerivKit 行情 schema
    → align_spot_to_valuation(2024-06-14)
    → derivkit.price(vanilla.european, analytic)
    → 输出 spot + pv + delta
```

也可在 Python 中调用：

```python
from priceagent import DataService

svc = DataService()

# 拉取并汇总行情
print(svc.load_tushare_series("LH2409", "2024-06-14"))

# 获取估值日 spot
print(svc.get_tushare_spot("2024-06-14", symbol="LH2409"))

# 查找相近期权并取结算价（用于隐含波动率）
print(svc.get_tushare_option_quote(
    "2026-06-08", symbol="LH2609", strike=12200, maturity="3m", call_put="call"
))
```

### 常用合约代码

| 品种 | symbol | 自动解析 ts_code |
|------|--------|------------------|
| 生猪期货 | `LH2409` | `LH2409.DCE` |
| 碳酸锂期货 | `LC2409` | `LC2409.GFE` |
| 自定义 | `LH2409.DCE` | 直接使用完整 ts_code |

若自动解析失败，在工具调用中传入 `exchange=DCE`。

---

## 5. 演示 C：DeepSeek Agent 全自动定价

配置好 `.env` 后，用自然语言驱动 Agent：

```bash
source .venv/bin/activate

# 使用 Tushare 实时拉数 + 定价
python -m priceagent run \
  "从 Tushare 获取 LH2409 在 2024-06-14 的收盘价作为 spot，" \
  "对 strike=15500、3个月到期的看涨期权用 analytic 引擎定价，" \
  "给出 pv、delta 和对齐说明" \
  -v
```

`-v` 会在 stderr 打印工具调用轨迹（`get_tushare_spot` → `price_from_spec` 等）。

### 使用 Tushare 隐含波动率的 Agent 示例

当用户要求「相近期权的隐含波动率」时，Agent 应自动从 Tushare 拉期权结算价并反推 IV：

```bash
python -m priceagent run \
  "从 Tushare 获取大商所生猪期货主力合约在 2026-06-08 的收盘价作为 spot，" \
  "对 strike=12200、3个月到期的看涨期权用 analytic 引擎定价，" \
  "波动率使用相近期权的隐含波动率，给出 pv、delta 和对齐说明" \
  -v
```

**预期工具链：**

```
get_tushare_spot(LH2609)                    → 期货 spot
calibrate_volatility(method=implied, ...)   → opt_basic 匹配合约 + opt_daily 取 settle
                                              → BSM 反解隐含波动率
price_tushare_vanilla(volatility=<IV>)      → 用 IV 定价
```

也可分步调用：

```python
from priceagent import ToolRegistry

reg = ToolRegistry()

# 1. 查相近期权结算价
quote = reg.execute("get_tushare_option_quote", {
    "symbol": "LH2609",
    "valuation_date": "2026-06-08",
    "strike": 12200,
    "maturity": "3m",
    "call_put": "call",
    "price_field": "settle",  # 商品期权默认用结算价
})

# 2. 反推隐含波动率（可省略 market_price，工具会自动拉取）
iv = reg.execute("calibrate_volatility", {
    "method": "implied",
    "symbol": "LH2609",
    "valuation_date": "2026-06-08",
    "strike": 12200,
    "maturity": "3m",
    "call_put": "call",
})
print("implied vol =", iv["pv"])
print("matched option =", iv["option_quote"]["matched_contract"])
```

### 使用离线 CSV 的 Agent 示例

```bash
python -m priceagent run \
  "用内置 lh2409 数据集，对 2024-06-14 的生猪看涨期权定价" \
  -v
```

---

## 6. 演示 D：QFbench 沙箱模式

```bash
python -m derivkit.integ.sandbox_runner \
  src/derivkit/integ/tasks/vanilla_european/task.yaml \
  ./output

cat ./output/result.json
```

---

## 7. 演示 E：波动率校准（`calibrate()`）

此前 demo 中 **22% 为手写假设**。现在可从行情序列或期权市场价校准：

```bash
# 历史波动率（CSV 样例数据）
python -c "
import derivkit as dk
r = dk.calibrate('examples/commodity/lh_calibrate_historical.yaml')
print('historical vol =', round(r.pv * 100, 2), '%')
print(r.meta['calibration'])
"

# 隐含波动率（给定期权市场价反解 BSM）
python -c "
import derivkit as dk
r = dk.calibrate('examples/commodity/lh_calibrate_implied.yaml')
print('implied vol =', round(r.pv * 100, 2), '%')
"

# 校准 → 定价 一条龙
python -c "
import derivkit as dk
sigma = dk.calibrate('examples/commodity/lh_calibrate_historical.yaml').pv
spec = {
  'task': 'price',
  'market': {
    'valuation_date': '2024-06-14',
    'underlyings': [{'id': 'LH2409', 'asset_class': 'commodity', 'spot': 15520.0}],
    'rates': [{'id': 'CNY_RF', 'kind': 'constant', 'value': 0.025}],
    'vols': [{'id': 'LH_IV', 'kind': 'constant', 'value': sigma, 'underlying_id': 'LH2409'}],
  },
  'product': {'type': 'vanilla.european', 'params': {'strike': 15500, 'maturity': '3m', 'call_put': 'call'}},
  'engine': {'method': 'analytic'},
}
print('pv with calibrated vol =', dk.price(spec).pv)
"
```

Agent 也可调用 `calibrate_volatility` 工具（`method=historical` 或 `implied`）。

- **历史波动率**：在 YAML 的 `calibration.data` 中设置 `source: tushare`（需 `TUSHARE_TOKEN`）。
- **隐含波动率（Tushare 自动取价）**：`calibrate_volatility(method=implied, strike=..., ...)` 省略 `market_price` 时，工具通过 `opt_basic` 匹配相近期权、从 `opt_daily` 取 `settle`（或 `close`）作为市场价反解 BSM。

---

## 8. 全量测试

```bash
source .venv/bin/activate
pytest -m "not perf" -q
```

---

## 9. 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `TUSHARE_TOKEN is not set` | 未配置 `.env` | 复制 `.env.example` 并填入 Token |
| Tushare 返回空数据 | 积分不足或日期无交易 | 换有权限的接口日期，或先用 `demo` 离线模式 |
| `No option contracts from opt_basic` | 期权接口权限不足、合约月无期权、或 `opt_code` 解析错误 | 确认 Token 积分 ≥2000；商品期权 `opt_code` 为 `OP`+期货 ts_code（如 `OPLH2609.DCE`），不是品种根 `LH` |
| 隐含波动率用了历史波动率 | Agent 未调用 implied 或未拉期权价 | 确认 prompt 要求 IV；检查 tool trace 是否含 `get_tushare_option_quote` |
| `DEEPSEEK_API_KEY` 报错 | Key 无效或未加载 | 确认 `.env` 在项目根目录，`pip install -e ".[agent]"` |
| DeepSeek 401 | Base URL 或 Key 错误 | 确认 `OPENAI_BASE_URL=https://api.deepseek.com` |
| `Cannot infer exchange` | 合约代码无法解析 | 使用完整 ts_code，如 `LH2409.DCE` |

---

## 10. 架构一览

```
用户自然语言
    │
    ▼
DeepSeek (deepseek-chat)  ← OPENAI_BASE_URL + DEEPSEEK_API_KEY
    │ function calling
    ▼
priceagent.tools
    ├── get_tushare_spot         ──► Tushare fut_daily ──► derivkit.data.alignment
    ├── get_tushare_option_quote ──► Tushare opt_basic + opt_daily
    ├── calibrate_volatility     ──► derivkit.calibrate() (historical / implied)
    ├── get_spot_quote           ──► 内置 CSV
    └── price_tushare_vanilla    ──► derivkit.price()
    │
    ▼
PricingResult (pv, greeks, meta)
```
