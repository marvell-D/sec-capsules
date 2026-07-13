# 贡献指南

欢迎贡献，但本项目优先接受能提高 Capsule 质量、执行可信度和上下文质量的改动，而不是单纯增加工具数量。

## 适合的早期贡献

- 改进 `capsule.yml` 的适用范围、风险说明、profile 与运行时 metadata。
- 提供已授权、可公开的 JSONL / XML fixture，并补 parser 边界测试。
- 修复 Scope、artifact 引用、超时、输出截断和 MCP adapter 的安全回归。
- 改进 ObservationPacket 的去重、排序、预算与推荐动作质量。
- 完善本机靶场 E2E、文档与 schema conformance test。

## 新增 Capsule 的最低清单

```text
src/sec_capsules/capsules/<tool-id>/
├── capsule.yml
├── parser.py
├── fixtures/sample.<format>
└── templates/                 # 仅当工具需要随包模板时添加

tests/test_<tool-or-area>.py
```

新 Capsule 还必须具备：

1. 明确的 `best_for`、`avoid_when`、风险等级和 safe profile。
2. argv 形式的 command，不得拼接 shell 字符串。
3. `input_schema`：每个 Agent 参数的类型、说明、范围/枚举，且 `additionalProperties: false`。
4. 每个 profile 的 `defaults` 与 `allowed_arguments`；不要提供任意 `extra_args` 后门。
5. `runtime.binary`、版本探测命令和输出大小上限。
6. 原始 artifact 名称与 content type。
7. parser 产生的统一 `service`、`endpoint`、`finding`、`evidence` 对象。
8. 参数校验、fixture、错误行、重复结果、Scope 和 Observation 测试。
9. 已授权的本机 E2E 方案；不要把第三方目标放进 CI。

提交前运行：

```bash
scripts/ci.sh
python -m build
```

`tests/test_capsule_conformance.py` 会自动检查所有 profile 的默认参数能否通过 Schema 并编译为不含残留模板变量的 CommandPlan。模型行为场景放在 `evals/`，不得把模型 SDK 加入 Core Runtime。

更详细的结构与设计理由见 [v0.1.2 中文开发者手册](docs/zh-CN/V0.1.2_开发者手册.md)。
