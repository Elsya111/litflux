# LitFlux UI Lab

[01-paper.html](01-paper.html) 现在是当前生产查看器的独立界面演示：面向 PC，以业务分解图和当前层完整内部流程图组织阅读；图为主体，侧栏与下方说明可折叠，选择对象只高亮说明，不过滤图。关系说明作为沿边可点击的轻量标记，主题与流动等选项集中到显示菜单；没有疏密调节或固定节点数量上限。

生产界面的唯一来源是 [semantic-viewer.html](../skills/litflux/assets/semantic-viewer.html)。本页演示数据来自 [demo.js](assets/demo.js) 中虚构的 Lumen 馆藏项目，已明确标注“演示”，不代表任何真实项目的源码事实或验收结果。演示页离线自包含，不依赖共享演示引擎。

其他四个方向仍可从 [index.html](index.html) 比较：

- [02-blueprint.html](02-blueprint.html)：蓝图方向。
- [03-editorial.html](03-editorial.html)：篇章方向。
- [04-terminal.html](04-terminal.html)：终端方向。
- [05-soft.html](05-soft.html)：柔和方向。

这些候选方向保留各自的演示表达，使用 [engine.js](assets/engine.js)，不作为当前生产查看器的实现。此前的截图也不能替代当前版本的实际视觉验收。

当前规则与验收见 [SKILL.md](../skills/litflux/SKILL.md)、[机制说明](../skills/litflux/references/mechanism.md) 和 [作者契约](../skills/litflux/references/semantic-authoring.md)。需要从真实项目候选重新构建页面，并分别核对源码语义、浏览器操作和人类视觉可读性。
