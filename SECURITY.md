# 安全策略

`sec-capsules` 仅用于已授权的安全工作。请不要基于未获许可的第三方扫描来报告“问题”或提交复现数据。

若发现本项目自身存在漏洞，请优先使用 GitHub Private Security Advisory；若仓库尚未开放该渠道，请通过维护者公布的私密方式联系。提交时不要附上真实凭据、未脱敏扫描结果或第三方原始响应。

## v0.1.1 的默认保守策略

- 真实执行前执行 Scope、DNS 地址、动作、速率与审批检查。
- 真实子进程必须显式传 `--execute`；普通 CLI 默认 dry-run 或 fixture 回放。
- MCP 默认拒绝 `execute=true`，需要 host 级环境变量开启。
- 原始 stdout/stderr 保存为 artifact，默认 ObservationPacket 不包含它们。
- artifact 读取仅接受受限 `artifact://` 引用，并限制行数和字符数。
- 子进程无 stdin、使用最小环境变量、按进程组超时终止、记录截断状态。

## 需要注意的当前限制

- v0.1.1 尚未实现通用 redaction engine。artifact 默认不进模型，不等于内容已经自动脱敏。
- approval YAML 是审计确认，尚不具备签名、过期或组织授权校验能力。
- Scope 不是网络代理，无法拦截工具内部的全部后续请求；只能在明确授权范围内运行工具。

完整边界说明见 [中文开发者手册](docs/zh-CN/V0.1.1_开发者手册.md)。
