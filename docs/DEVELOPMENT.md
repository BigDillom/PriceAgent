# DerivKit 开发环境

> 更新：2026-06-09  
> 目的：本地开发与 CI 使用一致、可复现的 Python 环境。

---

## 1. 环境约定

| 项目 | 约定 |
|------|------|
| Python 版本 | **≥ 3.10**（`pyproject.toml`）；本地推荐 **3.11** |
| 虚拟环境路径 | 项目根目录 **`.venv/`**（`venv` 标准布局） |
| 依赖声明 | `pyproject.toml`（运行时 + `[dev]` 可选依赖） |
| 锁定版本 | `requirements-lock.txt`（`pip freeze` 导出，供复现对照） |
| 包安装方式 | 可编辑安装 `pip install -e ".[dev]"` |
| 禁止 | 直接使用系统全局 `python` / `pip` 跑测试（易版本漂移） |

`.venv/` 已加入 `.gitignore`，**不提交**；协作者按下列步骤本地创建。

---

## 2. 首次搭建（macOS / Linux）

在项目根目录 `PriceAgent/` 执行：

```bash
# 1. 选择解释器（任选已安装的 3.10+）
python3.11 -m venv .venv
# 或: python3.10 -m venv .venv

# 2. 激活
source .venv/bin/activate

# 3. 升级 pip 并安装项目（含开发依赖）
pip install --upgrade pip
pip install -e ".[dev]"

# 4. 验证
python --version          # 应显示 3.10.x 或 3.11.x
pytest -m "not perf" -q     # 应 52 passed
```

Windows（PowerShell）：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
pytest -m "not perf" -q
```

---

## 3. 当前本地基准环境（2026-06-09 验证）

在 **macOS arm64** 上创建并验证通过的配置：

| 组件 | 版本 |
|------|------|
| Python | 3.11.15 |
| derivkit | 0.1.0（editable） |
| numpy | 2.4.6 |
| scipy | 1.17.1 |
| pandas | 3.0.3 |
| pydantic | 2.13.4 |
| numba | 0.65.1 |
| pytest | 9.0.3 |

完整包列表见仓库根目录 [`requirements-lock.txt`](../requirements-lock.txt)。

更新锁定文件（升级依赖后）：

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pip freeze > requirements-lock.txt
```

---

## 4. 日常开发命令

激活虚拟环境后：

```bash
source .venv/bin/activate   # 每次新终端需执行

pytest -m "not perf"        # 单元 + 集成测试
pytest -m "not perf" --cov=derivkit --cov-report=term-missing --cov-fail-under=85
python scripts/check_doc_links.py
ruff check .
mypy src
black --check .
```

不激活也可显式调用：

```bash
.venv/bin/pytest -m "not perf" -q
.venv/bin/python -c "import derivkit; print(derivkit.__file__)"
```

---

## 5. 与 CI 的关系

GitHub Actions（`.github/workflows/ci.yml`）使用 **Python 3.10** + `pip install -e ".[dev]"`，与本地 `.venv` 策略一致，仅次版本号可能不同。

| 环境 | Python | 依赖来源 |
|------|--------|----------|
| 本地 `.venv` | 3.10 / 3.11（推荐 3.11） | `pyproject.toml` |
| GitHub Actions | 3.10 | `pyproject.toml` |
| 版本对照 | — | `requirements-lock.txt` |

本地与 CI 均应通过 `pytest -m "not perf"`。若仅本地失败，先确认已激活 `.venv` 且已 `pip install -e ".[dev]"`。

---

## 6. 多窗口开发（MULTI_WINDOW_PLAN）

各 Cursor 窗口执行任务前，请先激活项目虚拟环境，避免误用系统 Python：

```bash
cd /path/to/PriceAgent
source .venv/bin/activate
pytest -m "not perf" -q   # 窗口结束前必须通过
```

窗口 Prompt 模板见 [`MULTI_WINDOW_PLAN.md`](MULTI_WINDOW_PLAN.md) §4。

---

## 7. 常见问题

**`ModuleNotFoundError: derivkit`**  
未安装可编辑包或未激活 venv → `source .venv/bin/activate && pip install -e ".[dev]"`。

**`python3` 为 3.9 或更旧**  
使用 `python3.11` 或 `python3.10` 显式创建 venv；项目要求 `>=3.10`。

**Cursor / Agent 终端**  
Agent 应使用 `.venv/bin/python` 与 `.venv/bin/pytest`，而非系统路径下的解释器。

**重建环境**

```bash
rm -rf .venv
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```
