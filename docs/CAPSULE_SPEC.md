# Capsule 格式规范（v0.1.1）

Capsule 是 `sec-capsules` 的工具卡。它把某个外部安全工具的知识、可执行 profile、输出约定和模型暴露策略放在一个可发现的目录中。Core Runtime 不需要为每种工具硬编码命令行知识，只需要读取 Capsule、生成 argv、执行、存证和调用该工具自己的 parser。

本文描述当前已经实现的格式；它不是未来稳定 v1 规范的承诺。需要从零理解整体架构、函数和数据流时，先阅读[中文开发者手册](zh-CN/V0.1.1_开发者手册.md)。

## 1. 目录约定

每个内置工具位于 `src/sec_capsules/capsules/<tool-id>/`：

```text
capsules/<tool-id>/
├── capsule.yml              # 必需：工具卡
├── parser.py                # 必需：原始输出到统一对象的转换器
├── fixtures/                # 建议：可复现的 JSONL/文本样本
│   └── sample.jsonl
└── templates/               # 可选：随包分发的工具专用模板
```

`pyproject.toml` 的 `package-data` 已包含上述 YAML、fixture 与 template，因此 editable install 和 wheel 安装后均可被 `CapsuleRegistry` 找到。不要在运行时依赖当前 shell 的工作目录来查找这些文件。

## 2. 工具卡字段

`CapsuleRegistry.load()` 使用 `yaml.safe_load()` 读取 `capsule.yml`，并包装为不可变的 `Capsule(id, raw, root)` 数据类。下表列出当前工具卡应具备的字段。

| 字段 | 类型 | 用途 |
|---|---|---|
| `id` | string | 全局唯一、与目录名及 parser 模块名一致的标识，例如 `httpx`。 |
| `name` | string | 给人看的工具名称。 |
| `category` | string | 能力分类，例如 `web-discovery`。 |
| `summary` | string | 一句话说明工具产生什么信息。 |
| `stage` | string | 在确定性流程中的阶段，例如 `discover`、`crawl`、`validate`。 |
| `risk_level` | string | 工具整体风险标签，供渐进检索和 UI/Agent 判断。 |
| `best_for` | string/list | 合适的使用场景。 |
| `avoid_when` | string/list | 不适合使用的场景与限制。 |
| `runtime` | mapping | 外部二进制和预检信息。 |
| `profiles` | mapping | 不同受控调用方式；至少应有 `safe`。 |
| `outputs` | list | 此工具声称会产生的标准对象类型。 |
| `artifacts` | list | 原始产物说明，通常包括 stdout JSONL。 |
| `model_exposure` | mapping | 面向模型的默认暴露策略说明。 |
| `next_actions` | list | 观察到输出后可由上层考虑的下一步标签。 |

当前 Registry 没有在加载时用 JSON Schema 强制验证全部字段；错误字段可能在计划或解析时才暴露。v0.2 会补 Capsule conformance test，贡献者现在应主动保持字段齐全、一致。

## 3. `runtime`：二进制预检声明

推荐结构如下：

```yaml
runtime:
  binary: httpx
  version_command: [httpx, -version]
  max_output_bytes: 1048576
```

| 子字段 | Runtime 行为 |
|---|---|
| `binary` | `inspect_tool()` 用 `shutil.which()` 定位它；找不到时运行终态为 `preflight_failed`。 |
| `version_command` | 预检执行的 argv。版本输出会写入 `RunResult.tool`，供审计和复现。 |
| `max_output_bytes` | stdout 和 stderr 各自的内存保留上限。超过上限仍会继续排空 pipe，但记录 `output_truncated=true`。 |

版本命令也必须是 argv 列表，不能写成 `"httpx -version"` 这样的 shell 字符串。Runtime 从不使用 `shell=True`。

## 4. `profiles`：同一工具的受控调用面

一个 profile 是工具卡中真正能被 Planner 选中的调用方案。当前 profile 使用的字段如下：

```yaml
profiles:
  safe:
    description: 低风险 HTTP 存活探测。
    active: false
    action: discovery
    requires_approval: false
    rate_limit: 20
    command:
      - httpx
      - -json
      - -silent
      - -rl
      - "$rate_limit"
      - -u
      - "$target"
```

| 子字段 | 类型 | 含义 |
|---|---|---|
| profile 名 | string | 命令行中的 `--profile` 值，例如 `safe`、`local_lab`。 |
| `description` | string | 人和 Agent 在 `get_capsule(..., "usage")` 中看到的用途说明。 |
| `active` | bool | 是否会主动发起更具侵入性的请求；Scope 的 `allow_active_scan` 会据此判定。 |
| `action` | string | 审批与策略使用的动作标签，例如 `discovery`、`fuzzing`。 |
| `requires_approval` | bool | 为真时，必须提供覆盖本次目标与 action 的审批记录。 |
| `rate_limit` | int | 声明请求速率，Planner 会放入模板变量，Scope 会做上限比较。 |
| `severity` | list[string]，可选 | Nuclei 之类工具需要的严重程度过滤；会作为 `$severity` 变量提供。 |
| `vars` | mapping，可选 | Capsule 自定义的模板变量。 |
| `command` | list[string] | 实际 argv 模板。每一个列表元素是一个参数，不是整段 shell。 |

### 4.1 模板变量

`core/planner.py` 的 `build_command_plan()` 使用 `string.Template` 展开如下变量：

| 变量 | 值来自 |
|---|---|
| `$target` | 调用者传入的目标字符串。 |
| `$rate_limit` | 当前 profile 的 `rate_limit`。 |
| `$severity` | profile `severity` 用逗号连接后的字符串。 |
| `$capsule_root` | 当前 Capsule 目录的绝对路径。 |
| `$<vars 中的键>` | profile 自定义变量。 |

`$capsule_root` 的存在是为了支持随包分发的局部模板。例如 Nuclei 的 `local_lab` profile 指向 `templates/local-juice-shop.yaml`，而不是依赖调用者机器上的相对路径。

### 4.2 速率字段的现有限制

Scope 配置当前把上限字段命名为 `max_requests_per_minute`，但 ProjectDiscovery 当前常用的 `-rl` 参数是每秒请求数。v0.1.1 仅比较数值，未完成单位转换。贡献者不得把它描述为精确 RPM 限流；v0.2 会统一单位或更名字段。

## 5. Parser 契约

每个 Capsule 必须提供 `parser.py`，暴露下面完全一致的函数签名：

```python
def parse(raw_text: str, *, run_id: str, artifact_name: str) -> dict[str, object]:
    ...
```

`core.parsers.parse_capsule_output()` 会动态导入 `sec_capsules.capsules.<id>.parser` 并调用它。返回的字典必须始终含有以下四个列表，即使其中某类没有结果：

```python
{
    "services": [],
    "endpoints": [],
    "findings": [],
    "evidence": [],
}
```

当前三个 parser 均把 JSONL 按行解析，跳过无效行，并使用 `artifact://<run>/artifacts/<name>#L<line>` 作为 evidence reference。这样一条 finding 可以回到原始证据，而不会把整份原始输出复制到模型上下文。

| Capsule | 主输出 |
|---|---|
| `httpx` | HTTP `service`、`endpoint`、`evidence`。 |
| `katana` | 去重后的 `endpoint`、`evidence`。 |
| `nuclei` | `finding`、`evidence`。 |

新 parser 应满足：不执行网络操作；不依赖环境状态；对 banner、坏行和截断尾行尽量容错；为每个可行动对象保留 evidence ref；以 fixture 配套单元测试。

## 6. `outputs`、`artifacts` 与模型暴露

Capsule 不直接把原始扫描结果交给 Agent。数据按三层分离：

1. `artifacts`：stdout/stderr 等原始证据，`ArtifactStore` 保存文件、SHA-256 与元数据。
2. `outputs`：parser 生成的 `service`、`endpoint`、`finding`、`evidence` 等统一对象。
3. `ObservationPacket`：`build_observation_packet()` 依据 token budget 从结构化结果中生成摘要。

`model_exposure` 和 `next_actions` 是工具卡中的知识层说明，帮助上层先理解能力再决定是否请求完整详情。这是本项目“渐进披露”的基础：先检索 Capsule，再看 usage，再看 full，执行后默认只看 Observation，需要时才经 `get_artifact` 读取受限证据片段。

## 7. 新增 Capsule 的最小检查单

- 选择稳定、合法场景明确的外部工具；不要把自动化利用或目标扩张包装成默认 profile。
- 创建目录、`capsule.yml`、`parser.py` 和至少一份无敏感数据 fixture。
- 所有命令必须是 argv 列表，并提供合理的输出 JSON/JSONL 模式。
- 为 `runtime` 写真实的 binary 与 version command；不要假设工具总在 PATH。
- 声明 profile 的 `active`、`action`、`requires_approval` 和速率。
- 为 parser 增加 `tests/test_parsers.py` 覆盖，必要时增加 Scope/Runner 测试。
- 执行 `scripts/ci.sh`；涉及真实执行时，只对自有本机靶场运行 `scripts/e2e-local.sh`。

详细贡献要求见仓库根目录的[贡献指南](../CONTRIBUTING.md)。
