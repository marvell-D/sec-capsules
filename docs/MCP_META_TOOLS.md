# MCP 元工具说明（v0.1.2）

MCP（Model Context Protocol）是让模型宿主以结构化方式发现并调用外部能力的协议。`sec-capsules` 提供的是一个很薄的 MCP adapter：它把已经存在的 Python Core 暴露给 MCP host，而不是在 MCP 层重复实现 Scope、子进程、parser 或 artifact 逻辑。

本项目刻意不为每个扫描器创建一个 MCP tool，例如不直接暴露 `nuclei_scan`、`katana_crawl`。扫描器越多，工具定义、参数说明和原始结果越容易占据模型上下文；Capsule 的目标恰好是用稳定的元工具表面解决这个问题。

总体设计、逐函数代码导读与启动示例见[v0.1.2 中文开发者手册](zh-CN/V0.1.2_开发者手册.md)。

## 1. 已暴露的七个元工具

实现在 `src/sec_capsules/interfaces/mcp_server.py`。

| MCP 工具 | 目的 | 是否会真实执行外部工具 |
|---|---|---:|
| `search_capsules` | 按关键词、阶段、风险等级发现候选能力。 | 否 |
| `get_capsule` | 读取某个工具卡的 brief、usage 或 full 详情。 | 否 |
| `run_capsule` | 对一个 Capsule 进行 dry-run、fixture 回放或受控真实执行。 | 仅 `execute=true` 且通过多层门槛时 |
| `run_recipe` | 执行静态、确定性的多步 Recipe。 | 同上 |
| `get_observation` | 获取某次运行的 token 受限摘要。 | 否 |
| `get_artifact` | 读取明确 artifact ref 的有限行/字符片段。 | 否 |
| `export_run` | 获取一次运行的 Markdown 报告。 | 否 |

这七个工具对应一个自然的 Agent 交互顺序：

```text
search_capsules -> get_capsule(usage/full) -> run_capsule 或 run_recipe
    -> get_observation -> 有明确证据需求时 get_artifact -> export_run
```

它不是 Agent planner。MCP 层没有“根据 finding 自动选择下一步扫描器”的函数，也不会自动扩大目标范围。

## 2. 分层披露如何减少上下文负担

`get_capsule` 的 `detail_level` 使用 `CapsuleRegistry.capsule_to_public_dict()` 的三层视图：

| 级别 | 返回内容 | 使用时机 |
|---|---|---|
| `brief` | ID、名称、分类、摘要、stage、风险。 | 批量发现能力。 |
| `usage` | brief 加上适用/避免场景、`input_schema`、profile 默认值和允许参数。 | 选择工具并生成语义参数前。 |
| `full` | 原始工具卡完整内容。 | 已决定使用某个工具，需要核对参数和限制。 |

模型在读取 usage 后，通过 `run_capsule.arguments` 提交 JSON 对象。它不能提交原始 argv；Runtime 会先应用 profile 默认值，再校验类型、范围、枚举与 `allowed_arguments`，最后编译为 CommandPlan。执行完成后，默认返回的重点仍是 `ObservationPacket`：状态、计数、有限的服务/端点/finding、推荐下一步和 artifact reference。

典型调用请求：

```json
{
  "capsule_id": "katana",
  "target": "https://example.com",
  "scope": "scope.yml",
  "profile": "safe",
  "arguments": {
    "depth": 1,
    "requests_per_second": 3
  },
  "execute": false
}
```

`depth` 和 `requests_per_second` 是语义参数；`-depth`、`-rate-limit`、`-jsonl` 等工具 flag 由 Capsule 命令模板控制。

## 3. 真实执行的门槛

`run_capsule` 与 `run_recipe` 都接受 `execute` 参数，但默认值是 `false`。即使调用者传入 `execute=true`，仍须同时通过下列门槛：

1. **MCP host 门槛**：运行 MCP server 的进程必须显式设置 `SEC_CAPSULES_ALLOW_MCP_EXECUTE=1`。`_require_mcp_execution_enabled()` 否则直接拒绝。
2. **参数门槛**：参数必须由 `input_schema` 声明、由当前 profile 允许，并通过类型、范围和枚举校验。
3. **Capsule profile 门槛**：profile 必须存在；其 `active` 与 `action` 将进入 Scope 判定。
4. **Scope 门槛**：`ScopePolicy` 必须允许目标、解析后的 DNS 地址、活动类型和每秒请求速率。
5. **审批门槛**：Scope 的 `require_approval_for` 或 profile 的 `requires_approval` 要求时，approval 文件必须绑定当前 action 与 target。
6. **工具预检门槛**：`inspect_tool()` 必须能定位 binary 并运行 version command。

这些门槛只是工具调用层的控制，不能证明目标所有权，也不能替代书面授权、隔离网络或组织安全策略。

## 4. 启动方式

先安装 MCP optional extra：

```bash
python -m pip install -e '.[mcp]'
python -m sec_capsules.interfaces.mcp_server
```

默认不要设置 `SEC_CAPSULES_ALLOW_MCP_EXECUTE`。仅在明确授权、已配置 Scope 且运行环境可隔离时，才由 MCP host 进程设置：

```bash
export SEC_CAPSULES_RUNS_DIR=/var/lib/sec-capsules/runs
export SEC_CAPSULES_ALLOW_MCP_EXECUTE=1
python -m sec_capsules.interfaces.mcp_server
```

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| `SEC_CAPSULES_ALLOW_MCP_EXECUTE` | 未设置 / false | 是否允许 MCP 请求跨过第一层真实执行开关。 |
| `SEC_CAPSULES_RUNS_DIR` | `runs` | MCP 查询 `observation`、artifact 与 export 时使用的根目录。 |

`_runs_dir()` 读取后者；`_run_dir()` 只接受单一安全路径组件作为 run ID，从而防止 `../` 路径逃逸。

## 5. 参数与返回约定

| 工具 | 关键参数 |
|---|---|
| `search_capsules` | `query`、可选 `stage`、`risk_level`。 |
| `get_capsule` | `capsule_id`、`detail_level`。 |
| `run_capsule` | `capsule_id`、`target`、`scope`、`profile`、语义 `arguments`、`execute`、可选 `fixture`、`approval_file`、`timeout`、`budget`。 |
| `run_recipe` | `recipe_id`、`target`、`scope`、按 step ID 分组的 `arguments_by_step`，以及相同的执行控制参数。 |
| `get_observation` / `export_run` | `run_id`。 |
| `get_artifact` | `ref`，可选 `max_lines`、`max_chars`。 |

运行工具返回的 JSON 来自 `RunResult.to_dict()`；Recipe 返回的是逐步摘要而非每一步完整 structured payload。错误会由 MCP adapter 抛出为调用失败，不会伪装为成功结果。

## 6. MCP 层不负责什么

- 不决定扫描顺序，不生成攻击链，不利用漏洞。
- 不允许模型传任意 argv、shell 字符串或 `extra_args`；锁定 flag 仍属于 Capsule。
- 不跳过 Core 的 Scope、approval、工具预检和 artifact 边界。
- 不将 artifacts 自动发送给模型。
- 不提供网络级 egress proxy 或容器 sandbox。
- 不保证所有 Capsule 或工具参数都绝对无害；使用者仍须对授权与环境隔离负责。

这条“薄 adapter”边界让 CLI、Python API 与 MCP 使用相同的安全语义，也让未来替换 MCP host 时不必复制一套 Runtime。
