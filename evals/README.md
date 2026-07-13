# Eval Harness

这里测试的是“某个 Agent/模型能否正确使用 sec-capsules 的一次调用契约”，不是实现 Agent 框架。

外部模型只需根据场景生成 provider-neutral JSON：

```json
{
  "capsule_id": "katana",
  "target": "https://example.com",
  "profile": "safe",
  "arguments": {"depth": 1, "requests_per_second": 3}
}
```

把 JSON 保存为 candidate 后运行：

```bash
python -m sec_capsules.evals.cli grade \
  --scenario evals/scenarios/katana-shallow.yml \
  --candidate evals/candidates/reference/katana-shallow.json
```

评分项包括：候选 Capsule 是否可用、工具/profile 是否选对、参数是否为对象、能否生成合法 CommandPlan、是否满足语义约束、是否包含禁止参数、是否遵守最小权限。

Harness 还估算“全部 full 工具卡”与“brief 搜索结果 + 选中工具 usage”的上下文差异。估算器是字符数除以四，只用于版本间趋势比较，不代表任何供应商的精确 token 账单。

Planner 基准：

```bash
python -m sec_capsules.evals.cli benchmark \
  --capsule katana \
  --target https://example.com \
  --arguments-json '{"depth":1,"requests_per_second":3}' \
  --iterations 1000
```

墙钟时间受机器负载影响，因此 CI 只验证报告结构，不设置固定毫秒门槛。真实模型成功率、token 和重试次数应在手动或 nightly 任务中记录；模型 SDK 不进入 Core Runtime。

## SiliconFlow 两阶段评测

该 provider adapter 是 Harness 的测试消费者，不是 Core 依赖。它实时读取账户可用 chat 模型列表；未指定模型时按维护的优先顺序选择，显式指定但账户不可用时拒绝运行。

```bash
export SILICONFLOW_API_KEY='replace-with-a-rotated-secret'
python -m sec_capsules.evals.cli siliconflow-models
python -m sec_capsules.evals.cli siliconflow-grade \
  --scenario evals/scenarios/nmap-crapi-services.yml
```

第一阶段只提供所有候选 Capsule 的 brief 卡并要求选择 `capsule_id`；第二阶段只提供选中 Capsule 的 usage 卡与 `input_schema`，要求生成 target/profile/arguments。最终 JSON 仍由本地 `grade_candidate()` 验证，因此 provider 输出不会绕过 Runtime 契约。

密钥没有 CLI 参数，也没有默认文件回退，只读取当前进程的 `SILICONFLOW_API_KEY`。不要把密钥写入 scenario、candidate、shell history、GitHub 日志或仓库；发现曾公开粘贴的密钥应先吊销并轮换。
