# 作者方式：一个项目 JS 模块

图语言见 [机制说明](mechanism.md)，可运行的小例是 [project-example.js](../examples/project-example.js)。对象、关系、层级和来源定义一次；`draw()` 只按 ID 引用，不重复抄一份模型。旧 JSON 候选不再支持。

完整工作顺序与阶段完成条件以 [SKILL.md](../SKILL.md) 为准。本文件在组织好业务解释后用于编写模块、构建检查和需要时的独立复核。

## 模块

`module.exports = {title, summary, scope, language, files, workflows}`，可加 `author`、`unknowns`、`coverage`。

每个 workflow 有 `id`、`title`、`entry{trigger, sources}` 和 `flow`。每个 flow 有 `objects`、`relations`、`draw`，可加 `title`、`sources`、`reading`。

| 对象字段 | 用法 |
| --- | --- |
| id / type / title | 层内唯一 ID；类型见下；名称 |
| type | business、data、resource、component，控制结构用 decision，入口/结束可用 boundary |
| text | 有帮助的具体解释；不要为了填字段重复标题 |
| sources | 引用格式为 `别名:起始行-结束行`；校验器接受字符串或数组，供页面查看时显式写数组，如 `['app:14-19']` |
| detail | business 的子 flow；按解释尺度决定，不按函数数机械展开 |
| choices | 条件选择：`[{id, label}]` |

| 关系字段 | 用法 |
| --- | --- |
| id / from / to / label | 层内唯一 ID；完整边注文字，会原样渲染 |
| type | data、control、failure、loop、effect、capability |
| timing | **data 必填**：immediate 或 deferred；其他类型写了就是错误 |
| timingNote | 存在中间路径时必填：为什么是即时/保留 |
| branch | 条件出口引用源对象的 choice id |
| when | 条件数据边：`{判断ID: 选择ID}`，或这些对象的数组（OR） |

`files` 把别名映射到仓库相对路径，如 `{app: 'app.py'}`。位置、摘录和哈希由工具处理。

当前查看源码的页面逻辑直接读取选中对象或关系的 `sources`，不会自动继承 flow 或 entry 的引用。需要点击查看的对象和关系应显式填写引用数组；flow、entry 的来源可作为范围依据，但不能替代这些字段。`unknowns`、`coverage` 可保存在模块中，交付说明仍需直接告诉用户未知项和覆盖范围，不依赖页面展示这些可选字段。

## 绘图原语

```js
draw(s, {width, height}) {
  s.node('raw', 80, 140);
  const note = s.measure('保留到保存时使用', {maxWidth: 180});
  s.edge('retained', {sides: ['top', 'top'], via: [[500, 44], [930, 44]],
                      noteAt: [715, 44 - note.height / 2]});
}
```

- `s.node(id, x, y, {width, height})`：中心点。尺寸省略时按文字实测给出；business 是圆角矩形，data 是圆（width 即直径），resource 是圆柱形，component 是六边形；decision 用菱形，boundary 用胶囊形虚线框。资源轮廓表示稳定载体或共享状态，不限定为数据库。
- `s.edge(id, {sides, via, noteAt, noteWidth, path})`：`sides` 是两端锚点边（left/right/top/bottom，必填）；`via` 是折点数组；`noteAt` 是边注中心（必填）；`path` 可直接给 SVG 路径。
- `s.measure(text, {fontSize, maxWidth})`：返回 `{lines, width, height, lineHeight}`，与渲染使用同一套换行。边注文字宽度不靠猜。
- `s.size(width, height)`：可选，指定逻辑画布；默认按内容外接框。

命名避开冲突：关系的端点叫 `from/to`，锚点边叫 `sides`；关系的 `label` 是文字，边注位置叫 `noteAt`。

`finish()` 检查每个对象和关系都恰好画了一次，漏画直接报错；不补默认位置。

## 检查

构建时检查：ID 唯一、引用完整、data 边已声明 timing、非 data 边不带 timing、`branch` 指向真实 choice、`timingNote` 覆盖有中间路径的数据边、来源范围可读。

浏览器自动检查：遍历内部 flow（复用的同一 flow 去重），核对对象与关系数量、对象角色、边注文字（忽略空白）和声明的线型；检查节点重叠、越界、边注压节点、边注互压、边注离边 >40px、连线穿节点、文字溢出及纵横比极端。

交互自动检查只抽取一组父子业务检查进入与返回，并检查起始视图默认情景的阅读计划；源码抽屉尝试打开起始视图对象声明的一处引用。当前源码抽屉检查结果记在 `checks.sources` 中，失败不会自动加入失败列表；无引用时记为 `no-declared-source`。因此报告通过不能代替作者逐工作流、关键情景的实际操作与截图查看，业务分解图也需要目视检查。

报告给出具体 ID 和像素，作者按报告改 `draw()`。工具不自动挪、不自动缩、不自动删。

`全图适配` 只是定位手段：正文按 100% 阅读，不靠缩小冒充可读。

## 构建与状态

```sh
python scripts/build_graph.py PROJECT.js --source-root ROOT --preflight
python scripts/build_graph.py PROJECT.js OUTPUT --source-root ROOT --draft
python scripts/build_graph.py PROJECT.js OUTPUT --source-root ROOT --review REVIEW.json
```

先预检，再构建；预检检查模块声明和来源，不执行视图的 `draw()`。构建后读取输出目录中的 `litflux.build-report.json`，按失败与几何告警修正，再构建取得新报告。仅有命令退出成功或 `valid: true` 不代表已经达到 `checked`，还需查看 `deliveryStatus` 和具体检查结果。

| 参数 | 作用 |
| --- | --- |
| `--preflight` | 只检查模块与来源，不渲染 |
| `--check-only` | 当前实现校验模块与来源并在内存中组装页面，不写产物、不运行浏览器，也不检查独立复核材料；返回 draft，不能替代完整构建 |
| `--no-browser` | 跳过浏览器检查；几何状态记为未检查 |
| `--draft` | 草稿构建的调用标记；当前不跳过浏览器或锁定 draft，实际状态仍由检查结果决定 |
| `--review` | 独立的 `review.json` |

输出离线 HTML、`litflux.graph.json`、`litflux.build-report.json`。它们不是需要作者重复编写的输入。

已生成页面的三态：`draft`（浏览器或几何检查尚未通过）、`checked`（声明校验通过、浏览器报告 passed、几何零告警）、`reviewed`（`checked` 且独立复核材料检查通过）。交互覆盖限于上面的实现范围，语义与视觉自查结果另行报告。单会话自治的上限是 `checked`；构建失败且没有页面时不能把工作材料称为可打开的草稿图。

## 复核

`review.json` 由**另一上下文的 agent** 写：它只拿到项目路径和产物路径，独立读源码、看图、看截图。写图的 agent 不能给自己签。

```json
{
  "revision": "构建报告里的 qualityRevision",
  "reviewer": "review-agent-20261105",
  "checks": {
    "coverage": {"status": "passed", "evidence": ["review.md"]},
    "semantics": {"status": "passed", "evidence": ["review.md"]},
    "visuals": {"status": "passed", "evidence": ["shot-submit.png"]}
  },
  "evidence": ["review.md", "shot-submit.png"]
}
```

证据文件放在 `review.json` 同目录，并在顶层 `evidence` 中列出供工具核对存在性。复核针对当前产物；修改模块或引擎后重新构建，并对新产物重新复核。工具核对复核声明、顶层证据文件是否存在及 `revision` 是否匹配；它无法证明复核者身份或证据内容，也不代替业务理解。没有复核时，已通过检查的产物保持 `checked`；检查未过仍为 `draft`，报告写清缺什么。
