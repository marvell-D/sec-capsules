# sec-capsules 项目说明

`sec-capsules` 是面向 AI 安全 Agent 的安全工具调用层。

它不是 AI 渗透框架，也不负责自主攻击规划。它关注的是：

- 工具知识渐进披露
- scope-safe 执行
- 原始输出 artifact 保存
- parser 和结构化状态
- evidence ref
- 低 token ObservationPacket

第一版使用 `httpx`、`katana`、`nuclei` 打穿 WebSec 场景下的最小闭环。

