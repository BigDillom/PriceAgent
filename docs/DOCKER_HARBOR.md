# Docker / Harbor Dependency Manifest

> 更新：2026-06-09 | 对齐 QFbench/Harbor 沙箱运行 DerivKit 定价任务

## 镜像构建

```bash
docker build -f docker/Dockerfile -t derivkit:0.1.0 .
```

本地冒烟（vanilla QFbench 任务）：

```bash
docker run --rm -v "$(pwd)/src/derivkit/integ/tasks/vanilla_european:/task:ro" \
  derivkit:0.1.0 \
  python -m derivkit.integ.sandbox_runner /task/task.yaml /app/output
```

## 基础镜像

| 组件 | 版本 |
|------|------|
| Base | `python:3.11-slim-bookworm` |
| Python | ≥ 3.10（镜像固定 3.11） |
| derivkit | `0.1.0`（wheel / editable 安装） |

## 运行时依赖（`docker/requirements-harbor.txt`）

| 包 | 锁定版本 | 用途 |
|----|---------|------|
| numpy | 2.4.6 | 数值计算 |
| scipy | 1.17.1 | 统计 / 插值 |
| pandas | 3.0.3 | 市场数据 CSV |
| pydantic | 2.13.4 | DSL 校验 |
| PyYAML | 6.0.3 | YAML 加载 |
| numba | 0.65.1 | MC/PDE/Quad JIT 热点 |

完整锁定列表见 [`docker/requirements-harbor.txt`](../docker/requirements-harbor.txt) 与根目录 [`requirements-lock.txt`](../requirements-lock.txt)。

## 容器约定

| 路径 | 说明 |
|------|------|
| `/app` | 工作目录；derivkit 已安装 |
| `/app/output` | QFbench 默认输出目录（`result.json`） |
| `/task` | 挂载任务 YAML（可选） |

环境变量（可选）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `PYTHONHASHSEED` | `0` | 增强可复现性 |
| `OMP_NUM_THREADS` | `1` | 避免沙箱内过度并行 |

## Harbor 集成要点

1. 使用 `python -m derivkit.integ.sandbox_runner` 作为评测入口（非 `dk.price` 直接调用）
2. 输出写入 `/app/output/result.json`（见 `docs/API.md` § QFbench sandbox）
3. 任务实例：`src/derivkit/integ/tasks/{vanilla_european,snowball_standard,barrier_up_and_out}/`
4. 评分：`derivkit.integ.grade_result` + `expected.json` 字段级容差

## 不包含在运行时镜像中

- 开发工具：pytest, ruff, mypy, black, hypothesis
- PriceLib 源码或运行时包（算法已内化至 `derivkit`）

## 安全与许可证

- 基础镜像：Debian bookworm-slim（定期更新基础镜像 tag）
- 项目：MIT
- 移植算法：Apache 2.0（PriceLib 归属见 `THIRD_PARTY_NOTICES.md`）
