# Capsule 格式规范（v0.2.0a1）

Capsule 是 `sec-capsules` 的工具知识与调用契约。它同时回答四个问题：工具适合做什么、模型可以选择哪些语义参数、Runtime 如何把参数编译成 argv、工具输出如何转成统一对象。

v0.1.2 把“固定 profile 命令”拆成以下契约；v0.2.0a1 又增加了显式速率单位与五类统一输出：

```text
input_schema              模型能理解的参数知识和绝对边界
profiles.defaults         未提供参数时使用的安全默认值
profiles.allowed_arguments 当前 profile 允许模型修改的参数集合
profiles.command          Runtime 控制的 argv 模板
```

详细实现见[v0.1.2 中文开发者手册](zh-CN/V0.1.2_开发者手册.md)。本格式仍是 pre-1.0 契约，后续可以演进。

## 1. 目录约定

```text
src/sec_capsules/capsules/<tool-id>/
├── capsule.yml              # 必需：知识、参数和调用契约
├── parser.py                # 必需：原始输出到统一对象
├── fixtures/sample.<format> # 必需：离线回归样本
└── templates/               # 可选：随包分发的工具模板
```

目录名、`capsule.yml.id` 和 parser import 路径必须一致。包数据由 `pyproject.toml` 配置，不能依赖调用者当前工作目录。

## 2. 顶层字段

| 字段 | 含义 |
|---|---|
| `id`、`name`、`category`、`summary` | 唯一标识与能力概述。 |
| `stage`、`risk_level` | Agent 检索与风险判断使用。 |
| `best_for`、`avoid_when` | 渐进披露的使用知识。 |
| `input_schema` | 模型可以提交的语义参数 Schema。 |
| `profiles` | 安全预设、允许参数和 argv 模板。 |
| `runtime` | binary、版本探测和输出上限。 |
| `outputs`、`artifacts` | 结构化对象和原始产物声明。 |
| `model_exposure` | 默认上下文暴露策略。 |
| `next_actions` | 供上层考虑的后续动作标签，不自动执行。 |

`get_capsule(..., "brief")` 只返回发现信息；`usage` 额外返回 `input_schema`、profile 默认值和允许参数，但不返回 command；`full` 才返回完整 YAML。

## 3. `input_schema`：模型参数知识

`input_schema` 使用 JSON Schema Draft 2020-12 的一个有意缩小的子集：

```yaml
input_schema:
  type: object
  additionalProperties: false
  properties:
    depth:
      type: integer
      description: Maximum crawl depth from the scoped starting URL.
      minimum: 1
      maximum: 5
      x-agent-settable: true
    requests_per_second:
      type: integer
      description: Maximum crawl requests per second for this invocation.
      minimum: 1
      maximum: 10
      x-agent-settable: true
      x-rate-limit-unit: requests_per_second
```

### 3.1 支持的类型和约束

| 类型 | 支持约束 |
|---|---|
| `integer`、`number` | `minimum`、`maximum`、`enum`。 |
| `string` | `minLength`、`maxLength`、`enum`。 |
| `boolean` | 类型与 `enum`。 |
| `array` | `minItems`、`maxItems`、`uniqueItems`、`items`。 |

每个 property 必须有非空 `description`。`additionalProperties` 必须为 `false`，从协议层拒绝模型猜出的字段。扩展字段 `x-agent-settable: false` 表示即使 Schema 中有该字段，也只能由 Runtime/Operator 设置；当前内置 Capsule 直接不暴露锁定 flag，因此大多数 property 为 true。

`core.arguments.validate_input_schema()` 只实现上述子集，避免 Core 强制依赖大型 JSON Schema 库。新增 Schema 关键字前必须同步扩展验证器和测试，不能假装已经支持。

### 3.2 不应放入 `input_schema` 的内容

- `target`：由 `run_capsule` 顶层参数和 Scope 独立处理。
- `-jsonl`、`-silent`：parser 与上下文管理依赖的输出不变量。
- 输出文件路径：由 ArtifactStore 管理。
- `$capsule_root`：Runtime 资源定位变量。
- 任意 `extra_args`、原始 argv 或 shell 字符串。
- 明文 token、cookie、密码；未来应使用受控 credential reference。

## 4. `profiles`：默认值、开放面与锁定命令

```yaml
profiles:
  safe:
    description: Depth-limited JSONL crawl for one scoped target.
    active: true
    action: crawling
    requires_approval: false
    defaults:
      depth: 2
      requests_per_second: 10
    allowed_arguments:
      - depth
      - requests_per_second
    command:
      - katana
      - -jsonl
      - -silent
      - -depth
      - $depth
      - -fs
      - fqdn
      - -rate-limit
      - $requests_per_second
      - -u
      - $target
```

| 字段 | 责任 |
|---|---|
| `description` | 告诉模型这个预设适合什么。 |
| `active` | 参与 Scope 的 active scan 判定。 |
| `action` | 参与 policy 与 approval 匹配。 |
| `requires_approval` | 强制要求审批记录。 |
| `defaults` | 调用者未提供时使用的值。它们也必须通过 `input_schema`。 |
| `allowed_arguments` | 当前 profile 允许调用者覆盖的参数白名单。 |
| `command` | argv token 模板；固定 token 对模型不可修改。 |

一个参数即使存在于顶层 Schema，如果不在当前 profile 的 `allowed_arguments` 中，也会被拒绝。例如 Nuclei `severity` 可用于 `safe`，但不能用于只允许本地固定模板的 `local_lab`。

## 5. 参数解析和优先级

`resolve_arguments(capsule, profile, provided)` 执行：

1. 校验 Schema、profile defaults 和 allowed list 的基本形状。
2. 拒绝 Schema 未声明的 provided 字段。
3. 拒绝当前 profile 未允许或 `x-agent-settable: false` 的字段。
4. 深拷贝 profile defaults，再覆盖模型 provided values。
5. 对最终值执行类型、范围、枚举和数组约束。
6. 为每个生效值记录来源：`agent` 或 `profile_default`。

优先级可以写成：

```text
profile default < agent provided value < Schema/profile/Scope 拒绝边界
```

这里的“边界”不是更高优先级的静默覆盖。模型请求越界时 Runtime 会拒绝，而不是偷偷把 100 改成 10；这样上层能看到真实错误并修复计划。

## 6. argv 编译

`build_command_plan()` 只把四类变量交给 `string.Template.substitute()`：

| 变量 | 来源 |
|---|---|
| `$target` | 调用顶层 target。 |
| `$capsule_root` | Runtime 解析的 Capsule 绝对目录。 |
| `$<argument>` | `resolve_arguments()` 已验证的最终值。 |
| 数组参数 | 由 `template_value()` 以逗号连接。 |

使用严格 `substitute()` 而不是 `safe_substitute()`：command 引用了未定义变量时立即报错，不能把 `$unknown` 原样传给外部工具。

最终结果是 `CommandPlan`：

```json
{
  "capsule_id": "katana",
  "profile": "safe",
  "arguments": {"depth": 1, "requests_per_second": 3},
  "argument_sources": {"depth": "agent", "requests_per_second": "agent"},
  "command": ["katana", "-jsonl", "-silent", "-depth", "1", "-fs", "fqdn", "-rate-limit", "3", "-u", "https://example.com"]
}
```

它仍只是计划。真实执行继续经过 Scope、approval、DNS、binary preflight 和 MCP host gate。

## 7. 速率单位

速率参数必须通过 `x-rate-limit-unit` 声明物理含义。同一个 Capsule 最多声明一个速率参数。例如 HTTP 工具使用 `requests_per_second`，Nmap 使用 `packets_per_second`。Planner 生成通用结构：

```json
{"argument":"packets_per_second","value":20,"unit":"packets_per_second"}
```

Scope 使用按单位分组的上限：

```yaml
scope:
  max_rates:
    requests_per_second: 10
    packets_per_second: 30
```

Scope 未配置某个单位时会 fail closed，而不是猜测换算关系。`max_requests_per_second` 和 `max_requests_per_minute` 暂时兼容；RPM 会除以 60 后比较。通用字段与旧字段对同一单位给出冲突值时直接报错。

## 8. Parser 与输出契约

每个 `parser.py` 暴露：

```python
def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, object]:
    ...
```

返回字典始终含 `assets`、`services`、`endpoints`、`findings`、`evidence` 五个列表。Parser 不执行网络操作；应容忍坏行和截断尾行；每个可行动对象保留 `artifact://...#Lx` evidence ref。某类无结果时返回空列表，不省略键。

原始 stdout/stderr 属于 artifact；parser 结果属于 structured objects；模型默认消费 ObservationPacket。三层不能混在一起。

## 9. Conformance 要求

`tests/test_capsule_conformance.py` 会对每个内置 Capsule：

- 调用 `validate_input_schema()`。
- 验证每个 profile 的 defaults 与 allowed arguments。
- 用默认值编译每个 profile。
- 确保 argv 非空且没有残留 `$variable`。
- 验证 metadata/runtime/artifact 声明和对应 fixture。
- 动态导入 parser，离线解析 fixture，并检查五个顶层集合。

新增 Capsule 还必须补参数正向/负向测试、parser fixture 测试，并在必要时增加 Scope 和本地 E2E。提交前运行：

```bash
scripts/ci.sh
python -m build
```

更完整的贡献清单见[贡献指南](../CONTRIBUTING.md)。
