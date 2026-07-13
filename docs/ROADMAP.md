# 版本路线图

本路线图强调“先验证一个窄而硬的工具调用 Runtime，再扩大 Capsule 覆盖面”。项目不以扫描器数量、自动化程度或攻击能力作为主要指标，而以可约束执行、可审计证据、可复现 parser 和低上下文负担作为质量标准。

完整的当前行为见 [v0.2.0a1 中文开发者手册](zh-CN/V0.2.0a1_开发者手册.md)。版本号表示开发计划，不代表安全认证或生产级承诺。

## 已完成：v0.1

v0.1 打通了最小 WebSec 垂直切片：

- Core Runtime：Capsule registry、CommandPlan、Scope、artifact、parser、ObservationPacket。
- 三个 WebSec Capsule：`httpx`、`katana`、`nuclei`。
- CLI 与薄 MCP adapter。
- JSONL golden fixture 和针对 parser/registry/observation 的基础单元测试。
- `web-recon-safe` 确定性 Recipe。

v0.1 的命题是：安全工具的调用结果可以从扫描器原始输出中分离出来，变成证据可回溯、模型可消费的统一数据层。

## 已完成：v0.1.1 执行门槛

v0.1.1 没有急着新增工具，而是补齐“真实执行时是否可信”的关键缺口：

- 预检外部 binary、记录解析路径和版本；缺工具成为 `preflight_failed`，而不是 traceback。
- argv 执行、关闭 stdin、环境变量 allowlist、进程组超时终止、stdout/stderr 分别限流。
- DNS 感知 Scope：检查目标规范化、include/exclude、private/link-local/metadata 地址、active 类型和速率上限。
- 可审计的 approval record，要求绑定 action 与 target。
- run manifest、SHA-256 artifact 元数据和受限 artifact ref 读取。
- 静态 Recipe DAG 校验；recipe 级摘要不堆积每一步的原始或结构化大对象。
- 七个完整 MCP 元工具，默认禁用 MCP live execution。
- 手动触发的 Juice Shop 本机 E2E，验证真实 `httpx -> katana -> nuclei local_lab` 闭环。

这版的意义是把“只解析 fixture 的 wrapper”提升为“可受控地执行自有靶场工具，并留下审计证据的 Runtime”。详细边界见[V0.1.1 执行门槛](V0.1.1_EXECUTION_GATE.md)。

## 已完成：v0.1.2 Agent 参数协议与可评估性

v0.1.2 修正了 profile-only 的关键缺口：模型不再只能选择整套固定命令，而是可以在安全边界内提交语义参数。

- Capsule 使用 JSON-Schema 风格 `input_schema` 披露参数类型、说明、范围和枚举。
- profile 使用 `defaults` 与 `allowed_arguments`，既保留安全预设，也明确该 profile 允许模型调整什么。
- `resolve_arguments()` 拒绝未知参数、类型错误、越界值、重复数组项和当前 profile 未开放的参数。
- Planner 严格替换模板变量；Agent 不接触原始 argv，固定输出格式、scope flag 和本地模板路径保持锁定。
- CLI/MCP `run_capsule` 接受 `arguments`；Recipe 接受按 step ID 分组的 `arguments_by_step`。
- `run.json` 保存生效参数及其 `agent` / `profile_default` 来源。
- Scope 统一使用 `max_requests_per_second`；旧 RPM 字段会换算后比较。
- Capsule conformance test 已进入 CI。
- Provider-neutral Eval Harness 可以给任意模型输出的候选 JSON 评分，并报告渐进披露上下文估算与 Planner 开销。

这版不引入模型 SDK、Agent loop 或动态攻击规划。Eval Harness 是测试消费者，不是产品框架。

## 进行中：v0.2 通用性证明

v0.2 的目标不是做成 Agent 框架，而是证明 Capsule 设计可以跨越三种明显不同的工具输出模式：主机/服务枚举、目录/参数 fuzz，以及现有 Web 发现/模板扫描。建议按以下顺序推进。

### 1. `nmap` Capsule：服务视角

**v0.2.0a1 已完成。** 当前实现只接受显式端口数组和每秒 packet 上限，使用 TCP connect scan；`service` profile 可做轻量版本识别，两个 profile 都要求 approval。原始 argv、端口范围、UDP、特权扫描和 NSE 均未开放给 Agent。

- 新增 `capsules/nmap/capsule.yml`、parser 和无敏感 fixture。
- 使用 machine-readable 输出（优先 XML 或可稳定解析的格式），映射为 `service.v1`、`asset.v1` 和 evidence。
- 初始 profile 保持保守：明确 scan type、端口范围、速率和审批语义；不默认启用 NSE 攻击脚本。
- 添加单元测试，验证 service 主键、版本字段、证据定位和失败输入容错。

它验证的是：统一 Schema 不仅能承载 HTTP，也能承载 host/port/service 世界。

### 2. `ffuf` Capsule：高基数结果与去重

- 新增 `capsules/ffuf/`、fixture、parser 与 profile。
- 默认 profile 应有受 Scope 约束的速率、明确 wordlist 来源和必要的 approval gate；不要将真实互联网字典爆破作为默认演示。
- parser 需要处理大量重复/近似结果，按 URL、方法、状态码、长度等定义明确的去重键。
- ObservationPacket 应先保留计数、代表性 endpoint、过滤说明和 evidence，而不是数千条命中。

它验证的是：本项目在“工具输出爆炸”场景下仍能做有效的上下文压缩，而不是只适合低量 JSONL。

### 3. 扩展 Capsule conformance tests

**v0.2.0a1 已完成第一阶段。** CI 已覆盖 metadata、runtime、全部 profile 默认计划、fixture 存在性、parser 可导入与五个顶层集合的离线解析。对象级完整 JSON Schema validator 仍待后续评估。

- 在 v0.1.2 参数 Schema/默认计划合规检查基础上，继续校验全部 metadata、runtime、命令 argv 类型和 parser 可导入性。
- 对 parser 返回值校验四个顶层集合以及对象对 JSON Schema 草案的基本符合性。
- 确保每个 Capsule 至少有一个 fixture，并能在不访问网络的情况下解析它。
- 将新增 Capsule 的质量门槛写入 `CONTRIBUTING.md`。

这一步避免项目随着工具增多而退化成“很多 YAML 文件，但运行时才发现坏掉”。

### 4. 统一 Schema 与导出改进

- 收紧 `service.v1`：定义 host、port、protocol、service name、版本信息和 evidence 的稳定最小集。
- 对 `endpoint.v1` 加入 fuzzer 需要的可选字段，如 method、status、content length、来源工具。
- 改进 Markdown export：按运行状态、资产/服务、端点、finding、证据分节，仍不默认嵌入 raw artifact。
- 增加 SARIF 导出原型，让 finding 可被代码扫描平台或 GitHub code scanning 接收；只输出映射明确的 finding，避免伪造精确位置。

### 5. 加强已知执行语义

- 使用带单位的 `max_rates` 支持 HTTP `requests_per_second` 与 Nmap `packets_per_second`。旧 RPS/RPM 字段在 pre-1.0 阶段暂时兼容，后续再移除。
- 为每个会派生 URL 的工具明确工具级 scope 参数与文档，清楚说明它不是网络代理级 egress control。
- 评估对 JSON Schema validator 的最小依赖，确保它不会破坏 Runtime 的轻量安装体验。

### v0.2 完成条件

1. `nmap` 和 `ffuf` 都具备 Capsule、parser、fixture、单元测试与至少一个清晰的低风险 profile。
2. `scripts/ci.sh` 能自动验证所有 Capsule 的基本合规性和 fixture 解析。
3. 在受控本机靶场中，至少一条 Recipe 可展示 service、endpoint、finding 三类结果被统一汇总。
4. Markdown 与 SARIF 出口都能从实际 fixture/run 生成，且不会泄露完整 raw artifact。
5. 速率单位的语义有代码与文档一致的定义。

## v0.3：可信性与可维护性

v0.3 关注“让团队能长期接入 Capsule”：

- 通用 redaction engine，并让 artifact metadata 如实记录是否、何时、按何策略脱敏。
- Capsule quality levels，区分实验性、fixture-verified、E2E-verified 等成熟度。
- 更细的 policy rules，例如工具可用性、环境策略和审批提供者接口。
- 从 fixture / run manifest 可复放的 replay，服务于 parser 回归与问题排查。
- 面向外部贡献者的模板、测试向导和版本兼容策略。

这仍不意味着自动攻击规划。任何会改变项目边界的功能都必须先讨论其授权、安全和上下文隔离影响。

## v1.0：稳定的公共契约

只有在经过真实贡献与使用验证后，才考虑声明稳定接口：

- Stable Capsule Spec v1。
- Stable ObservationPacket v1。
- Stable Finding/Evidence/Artifact/Service schema v1。
- 10 至 15 个有 fixture、conformance test、清晰风险 profile 的高质量 Capsule。
- 至少 3 个确定性、非自主规划的 Recipe。
- 稳定的 CLI、MCP 和 importable Python Core 兼容策略。

稳定不等于功能最多，而是新增 Capsule、升级工具版本或更换上层 Agent 时，用户能够预期数据和安全边界不会悄悄改变。
