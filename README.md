# sec-capsules

面向 AI 安全 Agent 的安全工具调用层：提供结构化输出、证据 artifact、范围安全检查与 token 受限的 ObservationPacket。

`sec-capsules` 不是自主渗透框架。它不规划攻击路径、不自动利用漏洞，也不取代 Nmap、Nuclei、ZAP、Burp 等安全工具。它只处理一次已被上层请求的工具调用生命周期：说明工具、校验范围、生成 argv、执行或回放、保存证据、解析输出、返回紧凑观察结果。

```text
工具卡渐进披露
  -> 模型提交语义 arguments（不是原始 argv）
  -> input_schema 校验 + profile 默认值合并
  -> Scope / approval 检查
  -> 安全 CommandPlan（argv，不经 shell）
  -> 真实执行、fixture 回放或 dry-run
  -> 原始输出 artifact
  -> 统一结构化对象与 evidence ref
  -> token 预算化 ObservationPacket
```

## 当前版本：v0.2.0a1

当前的 WebSec Capsule Pack 包含：

- `httpx`：HTTP 服务探测。
- `katana`：受限深度的端点收集。
- `nuclei`：模板化基线扫描；另有仅用于本机 Juice Shop E2E 的 `local_lab` profile。
- `nmap`：明确端口集合的 TCP connect/service 探测；不开放原始 argv、端口范围或 NSE 脚本。

v0.2.0a1 是 v0.2 的第一个预发布切片：新增 Nmap XML Capsule，把统一输出扩展到 asset/service，并把速率限制抽象为带单位的 `RateLimit`。本版还增加 SiliconFlow 两阶段模型评测 adapter 和仅手动触发的本机 crAPI Nmap E2E。FFUF、高基数压缩和 v0.2 的完整导出目标仍未完成，因此不宣称 v0.2 已完成。

当前实现的逐层讲解见 [v0.2.0a1 中文开发者手册](docs/zh-CN/V0.2.0a1_开发者手册.md)。参数协议的形成过程见 [v0.1.2 手册](docs/zh-CN/V0.1.2_开发者手册.md)。

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

sec-capsules list
sec-capsules doctor --require
sec-capsules describe nuclei --level usage
sec-capsules plan katana \
  --target https://example.com \
  --profile safe \
  --arguments-json '{"depth":1,"requests_per_second":3}'
```

使用 fixture 回放，不会启动外部工具：

```bash
sec-capsules run nuclei \
  --target http://localhost:3000 \
  --scope examples/juice-shop-local/scope.yml \
  --arguments-json '{"severity":["critical"],"requests_per_second":2}' \
  --fixture src/sec_capsules/capsules/nuclei/fixtures/sample.jsonl
```

真实执行只适用于明确授权目标，且必须显式添加 `--execute`：

```bash
sec-capsules run httpx \
  --target http://127.0.0.1:3000 \
  --scope examples/juice-shop-local/scope.yml \
  --execute
```

默认 runs 目录为 `runs/`。可以通过 `--runs-dir` 修改：

```bash
sec-capsules --runs-dir my-runs run httpx ...
sec-capsules artifact get artifact://run_xxx/artifacts/httpx.jsonl#L1
```

## 安全边界

- 真实执行前检查 Capsule profile、Scope、解析 DNS 后的地址、速率与审批记录。
- Agent 只能提交 `input_schema` 声明且被当前 profile 允许的参数；未知、越界、错误类型和额外参数会在执行前拒绝。
- `-jsonl`、`-silent`、目标 flag、本地模板路径等 Runtime 命令结构不暴露为 Agent 参数。
- 外部命令以 argv 执行，不通过 shell；stdin 被关闭，子进程按进程组超时终止。
- stdout、stderr 单独设置大小上限，截断状态写入 `run.json`。
- 原始输出保存为 artifact，默认不进入 ObservationPacket。
- MCP 的 `execute=true` 默认拒绝；只有 MCP host 显式设置 `SEC_CAPSULES_ALLOW_MCP_EXECUTE=1` 才会允许继续进行 Scope 检查。
- approval YAML 是可审计的人类确认，不是对目标所有权或法律授权的证明。

当前尚未提供通用 redaction engine；不要将 artifact 视为已经自动脱敏的数据。

## 本机 E2E

腾讯自托管 runner 上已验证下列受控流程：启动仅绑定 `127.0.0.1` 的 Juice Shop，执行 `httpx -> katana -> nuclei local_lab`，写入 artifact 后自动清理容器。

安装三个外部工具并确认只在自有靶场运行后，可执行：

```bash
scripts/e2e-local.sh
```

GitHub Actions 中的 `Local E2E` workflow 是手动触发的，不会随普通 push 自动扫描。

Nmap 跨协议切片使用本机 crAPI：

```bash
scripts/e2e-crapi-nmap.sh
```

该脚本会把官方 crAPI compose 固定到已审阅的源码提交、绑定 `127.0.0.1`、执行经审批的四端口 service profile，并在结束时删除本次容器和 volume。它需要 Docker Compose、Nmap 和较大的临时镜像空间，也只允许手动触发。

## 接口

- CLI：适合本机调试、脚本与 CI。
- Python Core：可被其他 Python 程序导入。
- MCP：薄 adapter，暴露以下元工具而非每个扫描器各一个 tool：

```text
search_capsules
get_capsule
run_capsule
run_recipe
get_observation
get_artifact
export_run
```

## 离线 Eval

Eval Harness 不是 Agent。它接收场景 YAML 和任意模型生成的候选 JSON，检查工具选择、参数约束、最小权限和 CommandPlan 可编译性：

```bash
python -m sec_capsules.evals.cli grade \
  --scenario evals/scenarios/katana-shallow.yml \
  --candidate evals/candidates/reference/katana-shallow.json

python -m sec_capsules.evals.cli benchmark \
  --capsule katana \
  --target https://example.com \
  --arguments-json '{"depth":1,"requests_per_second":3}' \
  --iterations 1000
```

Planner 时间基准只生成报告，不作为 CI 的固定毫秒阈值。PR CI 使用确定性契约测试；真实模型评估由外部调用者把候选 JSON 交给 Harness。

SiliconFlow adapter 位于 Eval 层而不是 Core。密钥只能由环境变量提供：

```bash
export SILICONFLOW_API_KEY='replace-with-a-rotated-secret'
python -m sec_capsules.evals.cli siliconflow-models
python -m sec_capsules.evals.cli siliconflow-grade \
  --scenario evals/scenarios/nmap-crapi-services.yml
```

adapter 先用 brief 卡选工具，再只披露被选中工具的 usage 卡生成参数，最后由本地 Harness 评分；模型不能提交原始命令。

## 文档导航

- [v0.2.0a1 中文开发者手册](docs/zh-CN/V0.2.0a1_开发者手册.md)
- [v0.1.2 中文开发者手册](docs/zh-CN/V0.1.2_开发者手册.md)
- [v0.1.1 中文开发者手册](docs/zh-CN/V0.1.1_开发者手册.md)
- [Capsule 格式规范](docs/CAPSULE_SPEC.md)
- [MCP 元工具说明](docs/MCP_META_TOOLS.md)
- [版本路线图](docs/ROADMAP.md)
- [自托管 Runner 运维说明](docs/SELF_HOSTED_RUNNER.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)
