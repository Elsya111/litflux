// Flask: one HTTP request, from WSGI entry to a response object.
// Coordinates serve this single diagram; they are not a general layout rule.
module.exports = {
  title: 'Flask · 一个请求的一生',
  language: 'zh',
  author: 'litflux-case',
  summary: '从 WSGI 入口出发，看 Flask 如何建立请求上下文、匹配 URL、执行 before_request、调用视图函数，最后把返回值变成 Response 并清理上下文。',
  scope: 'src/flask/app.py 的 wsgi_app、full_dispatch_request、preprocess_request、dispatch_request、finalize_request、process_response，以及 src/flask/ctx.py 的 push 与 match_request；不覆盖蓝图内部、模板渲染和 CLI。',
  files: { app: 'src/flask/app.py', ctx: 'src/flask/ctx.py' },
  workflows: [
    {
      id: 'request',
      title: '处理一个 HTTP 请求',
      entry: { trigger: 'WSGI 服务器调用 app(environ, start_response)', sources: 'app:1679-1686' },
      flow: {
        objects: [
          { id: 'environ', type: 'data', title: 'WSGI 请求', text: '服务器传入的 WSGI environ（请求方法、路径、请求头、body 流）以及 start_response 回调。Flask 不自己读 socket，它只消费这一层。', sources: 'app:1627-1629' },
          { id: 'wsgi', type: 'business', title: 'wsgi_app', text: '真正处理一次请求的方法。建请求上下文 → 分发 → 异常兜底，最后把 Response 交给服务器；不管成功失败，finally 里都会弹栈。__call__ 只是转调它，方便中间件包住 wsgi_app。', sources: ['app:1627-1677', 'app:1679-1686'] },
          { id: 'push', type: 'business', title: '压入上下文', text: '把 RequestContext 设为当前上下文，打开 session，然后在上下文可用的状态下执行 URL 匹配——这样自定义 URL 转换器里也能读到 session。', sources: ['app:1653', 'app:1657', 'ctx:416-444'] },
          { id: 'match', type: 'business', title: 'URL 匹配', text: 'match_request() 调 url_adapter.match(return_rule=True)。成功就把 rule 和 view_args 写回 request；失败则把 HTTPException 存进 routing_exception，不在这里抛。', sources: 'ctx:405-414' },
          { id: 'routing', type: 'decision', title: '匹配成功？', text: 'dispatch_request() 检查 request.routing_exception：有异常就抛出去，交给上层错误处理；没有才继续找视图函数。', sources: ['app:1009-1010', 'ctx:409-414'], choices: [{ id: 'ok', label: '成功：继续分发' }, { id: 'no', label: '异常：转错误处理' }] },
          { id: 'error', type: 'business', title: '错误处理', text: '没有匹配到路由、视图抛异常，都走 handle_user_exception()：先找注册的 errorhandler，找到就调用；处理不了再交给 handle_exception()，由 500 处理器兜底或重新抛出。', sources: ['app:880-914', 'app:916-991'] },
          { id: 'pre', type: 'decision', title: '有早退吗？', text: 'preprocess_request() 先跑 URL 预处理器，再按应用→蓝图的顺序跑 before_request。任何一处返回非 None，就把这个值当作视图返回值，直接跳过分发。', sources: 'app:1409-1439', choices: [{ id: 'none', label: '无：调用视图' }, { id: 'early', label: '有：直接收尾' }] },
          { id: 'dispatch', type: 'business', title: '调用视图', text: '按匹配到的规则取出 view_functions[rule.endpoint]，把 view_args 作为关键字参数调用它。自动 OPTIONS 请求在这里直接返回默认响应，不进入视图。', sources: 'app:993-1021' },
          { id: 'view', type: 'component', title: '视图函数', text: '由 @app.route 注册的业务函数。它可以返回字符串、字典、Response 或 (body, status, headers) 元组——统一由 make_response() 归一化。返回值本身不是 Response。', sources: ['app:1021', 'app:1267-1407'] },
          { id: 'finalize', type: 'business', title: '生成响应', text: 'make_response() 把返回值转成 Response（字典→JSON、字符串→HTML、元组→状态码与响应头），process_response() 再执行 after_request 并按需保存 session。', sources: ['app:1056-1090', 'app:1267-1407', 'app:1441-1470'] },
          { id: 'response', type: 'data', title: 'Response', text: '最终交给 WSGI 服务器，由服务器写出状态行、响应头和响应体。到这一步 Flask 的工作基本结束，剩下的清理在 finally 里。', sources: ['app:1078', 'app:1665'] },
          { id: 'teardown', type: 'business', title: '弹出上下文', text: 'wsgi_app() 的 finally 调用 ctx.pop(error)：触发 teardown_request 与 teardown_appcontext 回调，即使前面抛了异常也会执行。', sources: ['app:1666-1677', 'ctx:446'] },
        ],
        relations: [
          { id: 'environ', type: 'data', from: 'environ', to: 'wsgi', label: 'environ', timing: 'immediate' },
          { id: 'context', type: 'data', from: 'wsgi', to: 'push', label: '建立上下文', timing: 'immediate' },
          { id: 'stamped', type: 'data', from: 'push', to: 'match', label: '待匹配', timing: 'immediate' },
          { id: 'matched', type: 'data', from: 'match', to: 'routing', label: '匹配结果', timing: 'immediate' },
          { id: 'ok', type: 'control', from: 'routing', to: 'pre', label: '成功', branch: 'ok' },
          { id: 'no', type: 'control', from: 'routing', to: 'error', label: '异常', branch: 'no' },
          { id: 'none', type: 'control', from: 'pre', to: 'dispatch', label: '无早退', branch: 'none' },
          { id: 'early', type: 'control', from: 'pre', to: 'finalize', label: '提前返回', branch: 'early' },
          { id: 'failed', type: 'data', from: 'error', to: 'finalize', label: '错误响应', timing: 'immediate' },
          { id: 'args', type: 'data', from: 'dispatch', to: 'view', label: '参数', timing: 'immediate' },
          { id: 'returned', type: 'data', from: 'view', to: 'finalize', label: '返回值', timing: 'immediate' },
          { id: 'built', type: 'data', from: 'finalize', to: 'response', label: 'Response', timing: 'immediate' },
          { id: 'closed', type: 'data', from: 'response', to: 'teardown', label: '结束', timing: 'immediate' },
        ],
        draw(s) {
          s.node('environ', 100, 140).node('wsgi', 380, 140).node('push', 660, 140)
            .node('match', 940, 140).node('routing', 1220, 140)
            .node('error', 940, 400).node('pre', 1220, 400)
            .node('dispatch', 1500, 400).node('view', 1780, 400)
            .node('finalize', 1360, 660).node('response', 1640, 660).node('teardown', 1920, 660);

          const between = (a, b, y) => {
            const left = s.nodeBox(a), right = s.nodeBox(b);
            return {
              noteWidth: Math.max(44, right.left - left.right - 24),
              noteAt: [(left.right + right.left) / 2, y],
            };
          };
          const routingBox = s.nodeBox('routing');
          const errorBox = s.nodeBox('error');

          s.edge('environ', { sides: ['right', 'left'], ...between('environ', 'wsgi', 140) })
            .edge('context', { sides: ['right', 'left'], ...between('wsgi', 'push', 140) })
            .edge('stamped', { sides: ['right', 'left'], ...between('push', 'match', 140) })
            .edge('matched', { sides: ['right', 'left'], ...between('match', 'routing', 140) })
            .edge('ok', { sides: ['bottom', 'top'], noteAt: [1220, 270] })
            .edge('no', { sides: ['left', 'top'], noteAt: [(routingBox.left + errorBox.x) / 2, (routingBox.y + errorBox.top) / 2] })
            .edge('none', { sides: ['right', 'left'], ...between('pre', 'dispatch', 400) })
            .edge('early', { sides: ['bottom', 'top'], noteAt: [1290, 530] })
            .edge('failed', { sides: ['right', 'left'], via: [[1090, 400], [1090, 660]], noteAt: [1090, 530] })
            .edge('args', { sides: ['right', 'left'], ...between('dispatch', 'view', 400) })
            .edge('returned', { sides: ['bottom', 'top'], via: [[1780, 530], [1360, 530]], noteAt: [1570, 530] })
            .edge('built', { sides: ['right', 'left'], ...between('finalize', 'response', 660) })
            .edge('closed', { sides: ['right', 'left'], ...between('response', 'teardown', 660) });
        },
      },
    },
  ],
};
