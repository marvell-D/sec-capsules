# sec-capsules 中文文档导航

`sec-capsules` 是面向 AI 安全 Agent 的工具调用 Runtime。它把安全工具的描述、受控执行、证据存储、结构化解析和 token 受限摘要组织为可复用 Capsule；它不是自主渗透框架，也不规划攻击或自动利用漏洞。

当前版本为 **v0.1.1**，内置 `httpx`、`katana`、`nuclei` 三个 WebSec Capsule，并已在仅绑定本机的 Juice Shop 靶场上完成真实 E2E 验证。

## 建议阅读顺序

1. [v0.1.1 开发者手册](V0.1.1_开发者手册.md)：项目地图、全部核心函数和数据结构、编程思想、测试、CI/CD、已知限制与 v0.2 计划。
2. [Capsule 格式规范](../CAPSULE_SPEC.md)：新增工具卡、profile、parser、fixture 时必须遵守的契约。
3. [v0.1.1 执行门槛](../V0.1.1_EXECUTION_GATE.md)：真实执行的 Scope、approval、进程、artifact 与 MCP 边界。
4. [MCP 元工具说明](../MCP_META_TOOLS.md)：为什么是七个 meta-tools，以及如何安全启动 MCP adapter。
5. [自托管 Runner 运维说明](../SELF_HOSTED_RUNNER.md)：腾讯云服务器上的 CI、持续交付与手动 E2E。
6. [版本路线图](../ROADMAP.md)：已完成的 v0.1/v0.1.1 与 v0.2、v0.3、v1.0 的完成条件。

根目录还提供：[README](../../README.md)、[贡献指南](../../CONTRIBUTING.md)、[安全策略](../../SECURITY.md) 和 [AGENTS 规则](../../AGENTS.md)。

## 一句话数据流

```text
Capsule 工具卡 -> argv CommandPlan -> Scope/approval -> 真实执行或 fixture 回放
  -> 原始 artifact -> 专属 parser -> 统一 structured objects -> ObservationPacket
```

上层 Agent 默认看到 ObservationPacket 和 evidence ref，需要时才读取受限的 artifact 片段。这个设计用于减少原始工具输出带来的 token 消耗与注意力牵引，同时保留证据可回溯性。
