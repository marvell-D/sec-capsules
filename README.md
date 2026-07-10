# sec-capsules

面向 AI 安全 Agent 的安全工具调用层：提供结构化输出、证据 artifact、范围安全检查与 token 受限的 ObservationPacket。

`sec-capsules` 不是自主渗透框架。它不规划攻击路径、不自动利用漏洞，也不取代 Nmap、Nuclei、ZAP、Burp 等安全工具。它只处理一次已被上层请求的工具调用生命周期：说明工具、校验范围、生成 argv、执行或回放、保存证据、解析输出、返回紧凑观察结果。

```text
工具卡渐进披露
  -> Scope / approval 检查
  -> 安全 CommandPlan（argv，不经 shell）
  -> 真实执行、fixture 回放或 dry-run
  -> 原始输出 artifact
  -> 统一结构化对象与 evidence ref
  -> token 预算化 ObservationPacket
```

## 当前版本：v0.1.1

当前的 WebSec Capsule Pack 包含：

- `httpx`：HTTP 服务探测。
- `katana`：受限深度的端点收集。
- `nuclei`：模板化基线扫描；另有仅用于本机 Juice Shop E2E 的 `local_lab` profile。

v0.1.1 新增了工具健康检查、DNS 感知 Scope、审批记录、进程组超时终止、输出上限、artifact 受限读取、静态 Recipe DAG、完整 MCP 元工具和本机靶场 E2E。

完整的架构、逐文件函数说明、数据结构、CI/CD 与 v0.2 计划，请阅读：[中文开发者手册](docs/zh-CN/V0.1.1_开发者手册.md)。

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

sec-capsules list
sec-capsules doctor --require
sec-capsules describe nuclei --level usage
sec-capsules plan nuclei --target http://localhost:3000 --profile safe
```

使用 fixture 回放，不会启动外部工具：

```bash
sec-capsules run nuclei \
  --target http://localhost:3000 \
  --scope examples/juice-shop-local/scope.yml \
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

## 文档导航

- [中文开发者手册](docs/zh-CN/V0.1.1_开发者手册.md)
- [Capsule 格式规范](docs/CAPSULE_SPEC.md)
- [MCP 元工具说明](docs/MCP_META_TOOLS.md)
- [版本路线图](docs/ROADMAP.md)
- [自托管 Runner 运维说明](docs/SELF_HOSTED_RUNNER.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)
