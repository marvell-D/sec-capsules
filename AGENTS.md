# AGENTS.md

本仓库实现的是 `sec-capsules`：面向 AI Agent 的安全工具调用层。自动化编码 Agent 在修改代码前，应先阅读 [v0.2.0a1 中文开发者手册](docs/zh-CN/V0.2.0a1_开发者手册.md)。

## 项目边界

- 只关注工具卡、语义参数协议、Scope、安全执行、artifact、parser、ObservationPacket、evidence 与独立 Eval。
- 不将仓库演化为自主渗透 Agent，不实现攻击规划、自动利用、多 Agent 编排或长期攻击记忆。
- 不添加绕过授权、默认扩大扫描范围或自动尝试 exploit 的功能。
- 原始工具输出默认只能写入 artifact，不能直接作为模型常规上下文返回。
- 所有真实外部工具执行前必须经过 ScopePolicy。

## 修改原则

- Core 不依赖 CLI、MCP 或特定 Agent 框架；接口层只能作为薄 adapter 调用 Core。
- 新 Capsule 必须同时提供 `capsule.yml`、parser、fixture、测试、artifact 映射与 Observation 策略。
- Agent 只能提交 `input_schema` 声明并由 profile 允许的语义参数；不得增加任意 `extra_args` 或 raw argv 通道。
- Eval Harness 可以消费模型输出，但 Core 和 PR CI 不依赖特定模型 SDK 或完整 Agent 框架。
- 修改命令 profile 时，先用 `sec-capsules plan` 审核 argv，再做真实本机验证。
- 失败、超时和缺工具必须产生终态审计记录，不能只抛 traceback。
- 不把“默认不展示 raw artifact”误写成“已经完成通用脱敏”；通用 redaction 尚未实现。

## 交付前检查

```bash
scripts/ci.sh
python -m build
```

涉及真实工具时，只能在已授权本机靶场执行 `scripts/e2e-local.sh`。CLI 和 MCP 的同一能力必须通过 Core 共享实现，避免两条安全策略分叉。
