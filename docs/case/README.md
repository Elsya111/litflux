# LitFlux 完整案例

[litflux-case.html](litflux-case.html) 是 LitFlux 生成的一份完整产物，单文件、可离线打开。英文版页面是 [litflux-case-en.html](litflux-case-en.html)，英文说明见 [README.en.md](README.en.md)。

## 打开方式

- 下载仓库后双击 `litflux-case.html`。
- 在 GitHub 上打开时看到的是源码页，点右上角 **Download** 下载后再双击。
- 文件自包含：图、节点说明和源码摘录都内联，不需要 Python、Node.js，也不需要目标项目在场。

## 这份产物讲了什么

被解释的源码是一个小型「文本保存」程序（与 [app.py](../../skills/litflux/examples/semantic-source/app.py) 同一份示例源码）：文本归一化后判空，非空则写入；批量入口逐条提交并累计结果。

页面包含 3 个工作流、6 个视图、51 个对象、45 条关系（业务 15、数据 22、资源 9、组件 2、判断 3）。

- **提交并保存文本**：原始文本 → 规范化文本 → 清理后的文本 → 非空判断 → 保存；空文本走拒绝分支。
- **批量提交文本**：循环读取集合、逐条提交、累计结果。
- **资源类别与源码对应**：数据、资源、组件、判断四类对象在图上的画法。

## 构建状态

本次构建报告记录的交付状态是 `checked`：

| 检查项 | 结果 |
| --- | --- |
| 声明与来源校验 | 通过 |
| 语义审计 | 0 错误；4 条「业务缺少说明」警告，属作者取舍 |
| 浏览器检查（6 个视图） | 通过，阅读推进、进入/返回子业务、源码引用均在真实浏览器中操作过 |
| 几何检查 | 通过，无阻断告警 |
| 独立复核 | 未申请，因此不是 `reviewed` |

`checked` 覆盖的是声明、几何和已实现的交互；它不证明每条解释都与源码相符，也不等于视觉可读性已经有人看过。这两件事需要读者自己核对，或另做独立复核。

## 第二个案例：Flask 的请求生命周期

[flask-request.html](flask-request.html) 跑在真实仓库 [pallets/flask](https://github.com/pallets/flask) 上：从 `app(environ, start_response)` 进入，经 URL 匹配、before_request、视图分发、响应生成，最后在 `finally` 里 `ctx.pop(error)`。12 个对象、13 条关系，构建状态 `checked`。

范围是 `src/flask/app.py` 的 `wsgi_app`、`full_dispatch_request`、`preprocess_request`、`dispatch_request`、`finalize_request`、`process_response`，以及 `ctx.py` 的 `push` 与 `match_request`；不覆盖蓝图内部、模板渲染和 CLI。

作者模块随页面提供：[flask-request.module.js](flask-request.module.js)。复现：

```sh
git clone --depth 1 https://github.com/pallets/flask .litflux/work/flask
python skills/litflux/scripts/build_graph.py docs/case/flask-request.module.js .litflux/flask-case --source-root .litflux/work/flask
```

页面内摘录来自 Flask，版权归 Pallets 项目，BSD-3-Clause 许可；摘录只用于解释被引用的函数。

## 说明

- 页面标题里的「枪灰与琥珀」是这份构建采用的主题名（圆角节点、图标底座、胶囊数据）。发布包中的查看器与它共用同一套布局、交互和读图规则，主题细节不完全相同。
- 英文版内容与结构相同，只是文字换成英文；英文标签更长，因此横向间距更宽，节点与边注的位置和中文版不完全一致。
- 生成中英文产物的项目模块和构建脚本保留在本地工作目录 `.litflux/work/industrial-rounded/` 与 `.litflux/work/case-en/`，没有随仓库发布。
- 目标源码只被静态读取，案例里的教学函数没有被执行。
