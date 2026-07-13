# 离线 Eval Harness

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
