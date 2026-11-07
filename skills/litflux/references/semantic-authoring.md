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
| sources | 引用格式为 `别名:起始行-结束行`；校验器接受字符串或数组，页面兼容字符串和数组，多处引用可写数组，如 `['app:14-19']` |
| detail | business 的子 flow；按解释尺度决定，不按函数数机械展开 |
| choices | 条件选择：`[{id, label}]` |

| 关系字段 | 用法 |
| --- | --- |
| id / from / to / label | 层内唯一 ID；label 是完整边注文字，可省略或留空以不显示重复边注 |
| type | data、control、failure、loop、effect、capability |
| timing | **data 必填**：immediate 或 deferred；其他类型写了就是错误 |
| timingNote | 可选的简短解释；条件相容的中间路径只触发参考提示 |
| branch | 条件出口引用源对象的 choice id |
| when | 条件数据边：`{判断ID: 选择ID}`，或这些对象的数组（OR） |

`when` 对象内各条件同时成立（AND），数组表示任一对象成立（OR）；`branch` 表示源判断对象的一条条件出口。普通外部数据边不会自动继承另一条控制边的条件：若只在 `usable=yes` 时交给后续处理，可给该数据边写 `when: {usable:'yes'}`。工具会提示外部输入可能绕过未选中的条件出口，供作者核对；已选分支绕行后汇合属于合法情形。提示不阻断构建，其他条件含义仍由作者组织；不会按标签猜条件。并行输入需要共同到齐，互斥输入按所选情景参与。

`files` 把别名映射到仓库相对路径，如 `{app: 'app.py'}`。位置、摘录和哈希由工具处理。

当前查看源码的页面逻辑直接读取选中对象或关系的 `sources`，不会自动继承 flow 或 entry 的引用。需要点击查看的对象和关系应显式填写引用；flow、entry 的来源可作为范围依据，但不能替代这些字段。`unknowns`、`coverage` 可保存在模块中，交付说明仍需直接告诉用户未知项和覆盖范围，不依赖页面展示这些可选字段。

## 绘图原语

```js
draw(s, {width, height}) {
  // 本片段假设本层定义了 raw、save，以及连接它们的 retained。
  s.node('raw', 100, 140).node('save', 440, 140);
  const a = s.nodeBox('raw'), b = s.nodeBox('save');
  const noteWidth = b.left - a.right - 26;
  const note = s.measure('保留到保存时使用', {maxWidth: noteWidth});
  s.edge('retained', {sides: ['right', 'left'], noteWidth,
                      noteAt: [(a.right + b.left) / 2, 140]});
  // note.boxHeight 可用于安排上下相邻内容。
}
```

- `s.node(id, x, y, {width, height})`：中心点。尺寸省略时按文字实测给出；business 是圆角矩形，data 是圆（width 即直径），resource 是圆柱形，component 是六边形；decision 用菱形，boundary 用胶囊形虚线框。资源轮廓表示稳定载体或共享状态，不限定为数据库。
- `s.edge(id, {sides, via, noteAt, noteWidth, path})`：`sides` 是两端锚点边（left/right/top/bottom，必填）；`via` 是折点数组；`noteAt` 是可见边注中心（有 label 时填写）；`path` 可直接给 SVG 路径。
- `s.nodeBox(id)`：放置节点后返回只读 `{x,y,width,height,left,right,top,bottom}`，使用 draw 的作者坐标；外接框不是圆/菱形任意方向的锚点。`s.node()` 仍返回 scene，支持链式调用。
- `s.measure(text, {fontSize, maxWidth})`：返回 `{lines,width,height,lineHeight,boxWidth,boxHeight}`；最后两个字段含边注背景留白，与渲染使用同一套换行。`maxWidth` 是文本宽度。
- `s.size(width, height)`：可选，指定逻辑画布；默认按内容外接框。

默认节点按实际文字测量；data 直径目前为文字宽 +36 限制在 96–200，普通业务宽为文字宽 +42 限制在 124–248，高度随换行调整。作者优先查询 `nodeBox()`，无需复制公式。显式节点尺寸由作者控制。

边注省略 `noteWidth` 时，明确的水平线段会按 `noteAt` 两侧空间收窄文本换行宽度；复杂走线保留 260px 上限。显式数值始终优先，过窄空间会交给几何反馈，不强制压成单字列。宽度收窄也会增加高度，需要一起考虑；无可见边注的边仍能选择并查看关系。

命名避开冲突：关系的端点叫 `from/to`，锚点边叫 `sides`；关系的 `label` 是文字，边注位置叫 `noteAt`。

`finish()` 检查每个对象和关系都恰好画了一次，漏画直接报错；不补默认位置。

## 检查

构建时检查：ID 唯一、引用完整、data 边已声明 timing、非 data 边不带 timing、`branch` 指向真实 choice、来源范围可读。条件相容的中间路径给出可选说明提示；不据此改变线型。

预检的 `warnings` 保留作者提示，`timingNotes` 列出已声明依据的位置；旧 `requiredNotes` 字段为兼容保留为空，不再要求补注。

浏览器自动检查：遍历内部 flow（复用的同一 flow 去重），核对对象与关系数量、对象角色、边注文字（忽略空白）和声明的线型；检查节点重叠、越界、边注压节点、边注互压、边注离边 >40px、连线穿节点、文字溢出；纵横比极端只作提示。实际 SVG 路径用于穿线与距离检查。

完整检查抽取一组父子业务检查进入与返回；每个去重内部 flow 检查最多 32 个声明情景的阅读计划，报告总数和实际覆盖；通过实际选择/点击检查对象及关系声明的源码引用，失败计入失败列表。无引用记为 `no-declared-source`。仍需按任务检查重要操作和截图，不能把采样通过当成所有情景通过。

报告保留 ID、文字及结构化框坐标；边注问题在可确定时附最近路径点和候选 `noteAt`，均换算为作者坐标。候选只表示局部几何可放，不保证整体最佳；没有空间时明确报告。作者选择如何改 `draw()`。工具不自动挪、不自动缩、不自动删。

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
| `--geometry-only` | 真实浏览器渲染与几何检查，跳过交互验收；仍为 draft。另写 geometry-report，当前 build-report 也记录此次范围，避免沿用旧状态。不可与 preflight/check-only/no-browser/review 同用 |
| `--preflight` | 只检查模块与来源，不渲染 |
| `--check-only` | 当前实现校验模块与来源并在内存中组装页面，不写产物、不运行浏览器，也不检查独立复核材料；返回 draft，不能替代完整构建 |
| `--no-browser` | 跳过浏览器检查；几何状态记为未检查 |
| `--draft` | 草稿构建的调用标记；当前不跳过浏览器或锁定 draft，实际状态仍由检查结果决定 |
| `--review` | 独立的 `review.json` |

输出离线 HTML、`litflux.graph.json`、`litflux.build-report.json`。它们不是需要作者重复编写的输入。

几何模式另写 `litflux.geometry-report.json`；报告的 mode、revision、views、viewport 与未运行检查说明实际覆盖。CLI 的声明错误、浏览器失败及阻断几何问题返回非零退出码；自愿跳过浏览器的草稿可以成功退出，仍需读取交付状态。

已生成页面的三态：`draft`（浏览器或几何检查尚未通过）、`checked`（声明校验通过、浏览器报告 passed、几何无阻断缺陷）、`reviewed`（`checked` 且独立复核材料检查通过）。交互覆盖限于上面的实现范围，语义与视觉自查结果另行报告。单会话自治的上限是 `checked`；构建失败且没有页面时不能把工作材料称为可打开的草稿图。

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

证据文件放在 `review.json` 同目录，并在顶层 `evidence` 中列出供工具核对存在性。复核针对当前产物；修改模块或引擎后重新构建，并对新产物重新复核。工具要求非空的证据文件列表，多个检查可共用一份报告；检查未单列 evidence 时使用顶层列表。工具核对复核声明、文件存在性及 `revision` 是否匹配（包含引用源码的文件哈希、模块与引擎）；它无法证明复核者身份或证据内容，也不代替业务理解。没有复核时，已通过检查的产物保持 `checked`；检查未过仍为 `draft`，报告写清缺什么。
