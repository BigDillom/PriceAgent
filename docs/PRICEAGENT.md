# PriceAgent — 数据接口与 LLM 调用

PriceAgent 在 DerivKit 之上提供**市场数据查询接口**和 **OpenAI 兼容的 LLM 工具调用**，用于端到端跑通定价结果。

## 安装

```bash
source .venv/bin/activate
pip install -e ".[dev,llm]"
```

复制环境变量模板并填入 API Key：

```bash
cp .env.example .env
# 编辑 OPENAI_API_KEY
```

## 无需 LLM：直接跑结果

```bash
# 数据 + 定价联调演示（生猪 LH2409 香草看涨）
python -m priceagent demo

# 仅定价
python -m priceagent direct examples/commodity/lh_vanilla_call.yaml

# 列出内置数据集与 YAML 样例
python -m priceagent list
```

## LLM Agent 模式

```bash
python -m priceagent run "用 lh2409 数据，对 2024-06-14 的生猪看涨期权做 analytic 定价，并说明对齐后的 spot"
```

Agent 可调用的工具：

| 工具 | 说明 |
|------|------|
| `list_market_datasets` | 内置 CSV 数据集（lh2409 / lc2409 等） |
| `list_pricing_examples` | DSL 与 QFbench 任务 YAML |
| `load_market_series` | 加载并汇总行情序列 |
| `get_spot_quote` | 按估值日对齐 spot（含夜盘 session_close） |
| `get_tushare_spot` | 从 Tushare 期货日线对齐 spot |
| `get_tushare_option_quote` | 匹配相近期权合约，从 `opt_daily` 取结算价/收盘价 |
| `load_tushare_series` | 拉取 Tushare 期货/股票日线序列 |
| `calibrate_volatility` | 历史波动率或隐含波动率（implied 可自动从 Tushare 取期权价） |
| `price_tushare_vanilla` | Tushare spot + 香草期权一步定价 |
| `price_from_yaml` | 从 YAML 文件定价 |
| `price_from_spec` | 从 inline DSL dict 定价 |

兼容 OpenAI、Azure OpenAI、OpenRouter 等（通过 `OPENAI_BASE_URL`）。

## Python API

```python
from priceagent import DataService, ToolRegistry
from priceagent.agent import run_demo_pricing, run_agent

# 数据接口
svc = DataService()
print(svc.get_spot("2024-06-14", dataset_id="lh2409"))
print(svc.get_tushare_option_quote("2026-06-08", "LH2609", strike=12200))

# 工具执行（无 LLM）
reg = ToolRegistry()
result = reg.execute("price_from_yaml", {
    "yaml_path": "examples/commodity/lh_vanilla_call.yaml",
})
print(result["pv"])

# LLM（需 OPENAI_API_KEY）
answer = run_agent("Price the LH2409 vanilla call example")
print(answer.answer)
```

## 架构

```
用户 / LLM
    │ tool calls
    ▼
priceagent.tools ──► priceagent.data_service ──► derivkit.data (adapters, alignment)
    │
    └──────────────────────────────────────────► derivkit.price() / DSL
```
