# sec-capsules 中文文档导航

`sec-capsules` 是面向 AI 安全 Agent 的工具调用 Runtime。它把安全工具的描述、受控执行、证据存储、结构化解析和 token 受限摘要组织为可复用 Capsule；它不是自主渗透框架，也不规划攻击或自动利用漏洞。

当前版本为 **v0.1.2**，内置 `httpx`、`katana`、`nuclei` 三个 WebSec Capsule。模型可以先读取参数 Schema，再提交语义 arguments；Runtime 负责验证和编译。真实执行仍沿用 v0.1.1 已验证的本机 Juice Shop 安全边界。

## 建议阅读顺序

1. [v0.1.2 开发者手册](V0.1.2_开发者手册.md)：参数协议、逐函数实现、接口数据流、测试分层、Eval Harness 和修改指南。
2. [v0.1.1 开发者手册](V0.1.1_开发者手册.md)：基础 Runtime、执行进程、artifact、parser、Observation、CI/CD。
3. [Capsule 格式规范](../CAPSULE_SPEC.md)：新增工具卡、参数 Schema、profile、parser、fixture 时必须遵守的契约。
4. [v0.1.1 执行门槛](../V0.1.1_EXECUTION_GATE.md)：真实执行的 Scope、approval、进程、artifact 与 MCP 边界。
5. [MCP 元工具说明](../MCP_META_TOOLS.md)：七个 meta-tools、参数披露与执行门槛。
6. [自托管 Runner 运维说明](../SELF_HOSTED_RUNNER.md)：腾讯云服务器上的 CI、持续交付与手动 E2E。
7. [版本路线图](../ROADMAP.md)：已完成版本与 v0.2、v0.3、v1.0 的完成条件。

根目录还提供：[README](../../README.md)、[贡献指南](../../CONTRIBUTING.md)、[安全策略](../../SECURITY.md) 和 [AGENTS 规则](../../AGENTS.md)。

## 一句话数据流

```text
Capsule 工具卡 -> input_schema -> Agent arguments -> 参数校验/默认值合并
  -> argv CommandPlan -> Scope/approval -> 真实执行或 fixture 回放
  -> 原始 artifact -> 专属 parser -> 统一 structured objects -> ObservationPacket
```

上层 Agent 默认看到 ObservationPacket 和 evidence ref，需要时才读取受限的 artifact 片段。这个设计用于减少原始工具输出带来的 token 消耗与注意力牵引，同时保留证据可回溯性。
