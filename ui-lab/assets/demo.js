/* LitFlux UI Lab — 演示数据（虚构项目，仅用于界面设计评审）。
   结构刻意与 litflux.semantic/1 对齐：workflow / flow / nodes / data / edges / links / uses。 */
window.LFD_DATA = {
  meta: {
    project: 'Lumen',
    title: 'Lumen 馆藏检索与推荐',
    kicker: '公共图书馆 · 检索 / 推荐 / 同步',
    summary: '把读者的一次检索、每日推荐和供应商增量同步，整理成可逐层阅读、可跳转源码的项目脉络。',
    scope: '检索、每日推荐、馆藏同步三条入口的读取路径与资源作用；不含管理后台、鉴权与计费。',
    author: 'UI Lab · 演示数据',
    revision: '2026-11',
    demo: true
  },
  workflows: [
    {
      id: 'search',
      title: '馆藏检索',
      code: 'A',
      trigger: 'GET /api/search?q=&page=',
      description: '从查询参数到响应体的一条完整读取路径。',
      flow: {
        title: '检索主流程',
        nodes: [
          {
            id: 'parse', title: '解析查询请求', kind: 'process',
            text: '读取 q、page、size，做全角与空白规范化，并补齐默认分页。空查询在这一步变成空字符串，交由后续判断处理。',
            sources: ['lumen/search/api.py:18-27', 'lumen/search/query.py:7-24'],
            detail: {
              title: '解析与分页',
              nodes: [
                { id: 'readParams', title: '读取查询参数', kind: 'process', text: '按白名单取出 q、page、size，忽略未知参数。', sources: ['lumen/search/query.py:7-11'] },
                { id: 'normalize', title: '规范化关键词', kind: 'process', text: 'NFKC 归一、合并空白、转小写；空串保持空串。', sources: ['lumen/search/query.py:13-19'] },
                { id: 'mergePaging', title: '合并默认分页', kind: 'process', text: 'page 至少为 1，size 上限 50，避免深分页拖垮检索。', sources: ['lumen/search/query.py:21-24'] }
              ],
              data: [
                { id: 'raw', title: '原始请求', text: '未校验的查询字符串与分页参数。', sources: ['lumen/search/api.py:18-19'] },
                { id: 'rawKeyword', title: '原始关键词', text: '仅去除首尾空白的 q。', sources: ['lumen/search/query.py:8-9'] },
                { id: 'keyword', title: '规范化查询', text: '归一后的检索文本。', sources: ['lumen/search/query.py:13-19'] },
                { id: 'paging', title: '分页参数', text: 'page 与 size 的有效值。', sources: ['lumen/search/query.py:21-24'] }
              ],
              edges: [
                { from: 'readParams', to: 'normalize', label: '参数已读取', sources: ['lumen/search/query.py:7-13'] },
                { from: 'readParams', to: 'mergePaging', label: '参数已读取', sources: ['lumen/search/query.py:7-21'] }
              ],
              links: [
                { from: 'raw', to: 'readParams', label: '请求参数', sources: ['lumen/search/query.py:8'] },
                { from: 'readParams', to: 'rawKeyword', label: '原始文本', sources: ['lumen/search/query.py:8-9'] },
                { from: 'rawKeyword', to: 'normalize', label: '待归一文本', sources: ['lumen/search/query.py:13-15'] },
                { from: 'normalize', to: 'keyword', label: '规范化文本', sources: ['lumen/search/query.py:15'] },
                { from: 'raw', to: 'mergePaging', label: '分页输入', sources: ['lumen/search/query.py:22-23'] },
                { from: 'mergePaging', to: 'paging', label: '有效分页', sources: ['lumen/search/query.py:22-23'] }
              ]
            }
          },
          {
            id: 'retrieve', title: '检索馆藏索引', kind: 'process',
            text: '用规范化查询构造 DSL，在馆藏索引里取回命中集合，过滤已下架与不可借书目，再合并分页信息。',
            sources: ['lumen/search/service.py:40-48'],
            detail: {
              title: '检索与过滤',
              nodes: [
                { id: 'buildDsl', title: '构建查询 DSL', kind: 'process', text: 'title 匹配 + shelf=on 过滤，带上 from/size。', sources: ['lumen/search/dsl.py:12-17'] },
                {
                  id: 'callEs', title: '调用检索接口', kind: 'process', text: '800ms 超时；超时或传输错误抛出检索不可用，由上层转 503。', sources: ['lumen/search/service.py:42-45'],
                  uses: [{ kind: 'provider', title: 'Elasticsearch 客户端', relation: '提供 search 调用', text: '默认由配置里的 es 客户端注入。', sources: ['lumen/search/service.py:43'] }]
                },
                { id: 'filter', title: '过滤下架书目', kind: 'process', text: '剔除 shelf=off 与不可借记录，保留可借集合。', sources: ['lumen/search/filter.py:9-15'] },
                { id: 'paginate', title: '合并分页信息', kind: 'process', text: '按 page/size 截取当前页，并记录总数。', sources: ['lumen/search/service.py:47-48'] },
                { id: 'failed', title: '返回 503 与降级提示', kind: 'boundary', text: '检索不可用时返回 503，前端展示稍后重试。', sources: ['lumen/search/service.py:44-45'] }
              ],
              data: [
                { id: 'keyword', title: '规范化查询', text: '上一层传入的检索文本。', sources: ['lumen/search/service.py:41'] },
                { id: 'dsl', title: '查询 DSL', text: '交给 ES 的请求体。', sources: ['lumen/search/dsl.py:15-17'] },
                { id: 'rawHits', title: '命中集合', text: 'ES 返回的原始命中。', sources: ['lumen/search/service.py:43-46'] },
                { id: 'available', title: '可借书目', text: '过滤下架后的记录。', sources: ['lumen/search/filter.py:9-15'] },
                { id: 'paged', title: '分页结果', text: '当前页记录与总数。', sources: ['lumen/search/service.py:47-48'] }
              ],
              edges: [
                { from: 'buildDsl', to: 'callEs', label: 'DSL 就绪', sources: ['lumen/search/service.py:41-43'] },
                { from: 'callEs', to: 'filter', label: '命中返回', sources: ['lumen/search/service.py:46-47'] },
                { from: 'filter', to: 'paginate', label: '可借集合', sources: ['lumen/search/service.py:47-48'] },
                { from: 'callEs', to: 'failed', label: '超时 / 5xx', kind: 'failure', sources: ['lumen/search/service.py:44-45'] }
              ],
              links: [
                { from: 'keyword', to: 'buildDsl', label: '检索文本', sources: ['lumen/search/dsl.py:12-13'] },
                { from: 'buildDsl', to: 'dsl', label: '请求体', sources: ['lumen/search/dsl.py:15-17'] },
                { from: 'dsl', to: 'callEs', label: '请求体', sources: ['lumen/search/service.py:43'] },
                { from: 'callEs', to: 'rawHits', label: '原始命中', sources: ['lumen/search/service.py:43-46'] },
                { from: 'rawHits', to: 'filter', label: '待过滤集合', sources: ['lumen/search/filter.py:9-15'] },
                { from: 'filter', to: 'available', label: '可借记录', sources: ['lumen/search/filter.py:13-15'] },
                { from: 'available', to: 'paginate', label: '可借集合', sources: ['lumen/search/service.py:47-48'] },
                { from: 'paginate', to: 'paged', label: '当前页', sources: ['lumen/search/service.py:47-48'] }
              ]
            }
          },
          {
            id: 'empty', title: '命中结果是否为空？', kind: 'decision',
            text: '只有非空命中才组装正常响应；空命中走独立提示，不写入缓存。',
            sources: ['lumen/search/api.py:25-27'],
            choices: [
              { id: 'hit', label: '有命中：组装响应' },
              { id: 'miss', label: '无命中：返回提示' }
            ]
          },
          { id: 'assemble', title: '组装检索响应', kind: 'process', text: '把可借书目、分页与查询回显拼成响应体，并写入 5 分钟缓存。', sources: ['lumen/search/response.py:6-10'], uses: [{ kind: 'resource', title: '响应缓存', relation: '写入 5 分钟缓存', mode: 'write', text: '缓存只缓存成功响应。', sources: ['lumen/search/response.py:9'] }] },
          { id: 'emptyResult', title: '返回空结果提示', kind: 'process', text: '返回空列表与拼写建议，不读取缓存。', sources: ['lumen/search/empty.py:20-22'] }
        ],
        data: [
          { id: 'q', title: '原始查询', text: '请求中的 q 参数。', sources: ['lumen/search/api.py:18-19'] },
          { id: 'keyword', title: '规范化查询', text: '归一后的检索文本。', sources: ['lumen/search/query.py:13-19'] },
          { id: 'paging', title: '分页参数', text: 'page 与 size 的有效值。', sources: ['lumen/search/query.py:21-24'] },
          { id: 'hits', title: '可借书目', text: '过滤后的当前页记录。', sources: ['lumen/search/service.py:47-48'] },
          { id: 'body', title: '检索响应', text: '成功的响应体。', sources: ['lumen/search/response.py:6-10'] },
          { id: 'emptyBody', title: '空结果响应', text: '带拼写建议的空响应。', sources: ['lumen/search/empty.py:20-22'] }
        ],
        edges: [
          { from: 'parse', to: 'retrieve', label: '查询规范化完成', sources: ['lumen/search/query.py:13-19', 'lumen/search/service.py:40-41'] },
          { from: 'retrieve', to: 'empty', label: '可借集合就绪', sources: ['lumen/search/service.py:47-48'] },
          { from: 'empty', to: 'assemble', label: '有命中', branch: 'hit', sources: ['lumen/search/api.py:25-27'] },
          { from: 'empty', to: 'emptyResult', label: '无命中', branch: 'miss', sources: ['lumen/search/api.py:25-26'] }
        ],
        links: [
          { from: 'q', to: 'parse', label: '查询文本', sources: ['lumen/search/api.py:20'] },
          { from: 'parse', to: 'keyword', label: '规范化文本', sources: ['lumen/search/query.py:13-19'] },
          { from: 'parse', to: 'paging', label: '有效分页', sources: ['lumen/search/query.py:21-24'] },
          { from: 'keyword', to: 'retrieve', label: '检索文本', sources: ['lumen/search/service.py:41'] },
          { from: 'retrieve', to: 'hits', label: '当前页记录', sources: ['lumen/search/service.py:47-48'] },
          { from: 'hits', to: 'empty', label: '判据', sources: ['lumen/search/api.py:25'] },
          { from: 'hits', to: 'assemble', label: '可借书目', sources: ['lumen/search/response.py:7-8'], guard: { empty: 'hit' } },
          { from: 'paging', to: 'assemble', label: '分页信息', sources: ['lumen/search/response.py:7-8'] },
          { from: 'assemble', to: 'body', label: '响应体', sources: ['lumen/search/response.py:6-10'] },
          { from: 'emptyResult', to: 'emptyBody', label: '空响应', sources: ['lumen/search/empty.py:20-22'] }
        ]
      }
    },
    {
      id: 'recommend',
      title: '每日推荐',
      code: 'B',
      trigger: 'cron 03:00 · 每日',
      description: '按读者画像生成候选池，打分后决定是否写卡片。',
      flow: {
        title: '推荐任务',
        nodes: [
          {
            id: 'profile', title: '读取读者画像', kind: 'process', text: '批量读取活跃读者与标签，跳过已退订账号。', sources: ['lumen/recommend/job.py:14-16'],
            uses: [{ kind: 'resource', title: '读者画像库', relation: '读取活跃读者', mode: 'read', text: '画像库提供标签与借阅偏好。', sources: ['lumen/recommend/job.py:15'] }]
          },
          { id: 'candidates', title: '生成候选池', kind: 'process', text: '按主题与可借状态取最多 200 条候选。', sources: ['lumen/recommend/job.py:17'] },
          { id: 'score', title: '计算倾向度', kind: 'process', text: '读者标签与书目向量做亲和度，再叠加新鲜度。', sources: ['lumen/recommend/score.py:8-12'] },
          {
            id: 'gate', title: '是否达到推荐阈值？', kind: 'decision', text: '最高分低于阈值时降级，不写卡片。', sources: ['lumen/recommend/job.py:18-19'],
            choices: [{ id: 'pass', label: '达到：写卡片' }, { id: 'fail', label: '未达到：降级' }]
          },
          {
            id: 'cards', title: '写入推荐卡片', kind: 'process', text: '取前 12 条写入读者首页卡片。', sources: ['lumen/recommend/job.py:21'],
            uses: [{ kind: 'resource', title: '推荐卡片', relation: '写入读者首页', mode: 'write', text: '卡片按读者分区。', sources: ['lumen/recommend/job.py:21'] }]
          },
          { id: 'degrade', title: '发送降级提示', kind: 'process', text: '不写卡片，记录一次降级通知供运营排查。', sources: ['lumen/recommend/job.py:19-20'] },
          {
            id: 'finish', title: '记录任务结果', kind: 'process', text: '把读者、卡片数量与耗时写入任务日志。', sources: ['lumen/recommend/job.py:22'],
            uses: [{ kind: 'resource', title: '任务日志', relation: '追加一条任务记录', mode: 'write', text: '日志用于次日对账。', sources: ['lumen/recommend/job.py:22'] }]
          }
        ],
        data: [
          { id: 'snapshot', title: '画像快照', text: '读者标签与偏好。', sources: ['lumen/recommend/job.py:15-16'] },
          { id: 'pool', title: '候选池', text: '最多 200 条可借书目。', sources: ['lumen/recommend/job.py:17'] },
          { id: 'ranked', title: '打分结果', text: '按分数降序的列表。', sources: ['lumen/recommend/score.py:8-12'] },
          { id: 'cardSet', title: '推荐卡片', text: '写入首页的前 12 条。', sources: ['lumen/recommend/job.py:21'] },
          { id: 'notice', title: '降级提示', text: '低分读者的一次通知。', sources: ['lumen/recommend/job.py:19-20'] },
          { id: 'record', title: '任务记录', text: '读者、卡片数与耗时。', sources: ['lumen/recommend/job.py:22'] }
        ],
        edges: [
          { from: 'profile', to: 'candidates', label: '画像就绪', sources: ['lumen/recommend/job.py:15-17'] },
          { from: 'candidates', to: 'score', label: '候选池就绪', sources: ['lumen/recommend/job.py:17-18'] },
          { from: 'score', to: 'gate', label: '最高分', sources: ['lumen/recommend/job.py:18-19'] },
          { from: 'gate', to: 'cards', label: '达到阈值', branch: 'pass', sources: ['lumen/recommend/job.py:18-21'] },
          { from: 'gate', to: 'degrade', label: '低于阈值', branch: 'fail', sources: ['lumen/recommend/job.py:19-20'] },
          { from: 'cards', to: 'finish', label: '卡片已写', sources: ['lumen/recommend/job.py:21-22'] },
          { from: 'degrade', to: 'finish', label: '已降级', sources: ['lumen/recommend/job.py:19-22'] }
        ],
        links: [
          { from: 'profile', to: 'snapshot', label: '标签与偏好', sources: ['lumen/recommend/job.py:15-16'] },
          { from: 'snapshot', to: 'candidates', label: '读者画像', sources: ['lumen/recommend/job.py:17'] },
          { from: 'candidates', to: 'pool', label: '候选集合', sources: ['lumen/recommend/job.py:17'] },
          { from: 'pool', to: 'score', label: '候选集合', sources: ['lumen/recommend/score.py:8-12'] },
          { from: 'score', to: 'ranked', label: '降序列表', sources: ['lumen/recommend/score.py:12'] },
          { from: 'ranked', to: 'gate', label: '最高分', sources: ['lumen/recommend/job.py:18'] },
          { from: 'ranked', to: 'cards', label: '前 12 条', sources: ['lumen/recommend/job.py:21'], guard: { gate: 'pass' } },
          { from: 'cards', to: 'cardSet', label: '卡片', sources: ['lumen/recommend/job.py:21'] },
          { from: 'degrade', to: 'notice', label: '降级通知', sources: ['lumen/recommend/job.py:19-20'] },
          { from: 'cardSet', to: 'finish', label: '卡片数', sources: ['lumen/recommend/job.py:22'] },
          { from: 'notice', to: 'finish', label: '降级原因', sources: ['lumen/recommend/job.py:19-22'] },
          { from: 'finish', to: 'record', label: '任务记录', sources: ['lumen/recommend/job.py:22'] }
        ]
      }
    },
    {
      id: 'sync',
      title: '馆藏同步',
      code: 'C',
      trigger: 'lumen sync --since=last',
      description: '从供应商拉增量，校验后合并入索引并记录水位。',
      flow: {
        title: '同步任务',
        nodes: [
          {
            id: 'pull', title: '拉取供应商增量', kind: 'process', text: '按上次水位向供应商拉取变更记录，失败直接抛出。', sources: ['lumen/sync/cli.py:12-14'],
            uses: [{ kind: 'provider', title: '供应商 OAI 客户端', relation: '提供 changes 调用', text: '基础地址与重试由配置装配。', sources: ['lumen/sync/oai.py:6-12'] }]
          },
          { id: 'validate', title: '校验 ISBN 与元数据', kind: 'process', text: 'ISBN 校验失败或必填字段缺失的记录被丢弃。', sources: ['lumen/sync/cli.py:15-17'] },
          {
            id: 'isNew', title: '是否新书？', kind: 'decision', text: '索引里已存在的 ISBN 不重复写入，只计数跳过。', sources: ['lumen/sync/cli.py:18-20'],
            choices: [{ id: 'new', label: '新书：写入' }, { id: 'dup', label: '已存在：跳过' }]
          },
          {
            id: 'upsert', title: '合并写入馆藏索引', kind: 'process', text: '按 ISBN upsert，保留已有借阅热度字段。', sources: ['lumen/sync/cli.py:21'],
            uses: [{ kind: 'resource', title: '馆藏索引', relation: 'upsert 书目记录', mode: 'write', text: '与检索共用同一索引。', sources: ['lumen/sync/cli.py:21'] }]
          },
          { id: 'skip', title: '跳过重复书目', kind: 'process', text: '只累加跳过计数，不修改索引。', sources: ['lumen/sync/cli.py:18-20'] },
          {
            id: 'mark', title: '记录同步水位', kind: 'process', text: '无论新增还是跳过，都把本次游标写入水位文件。', sources: ['lumen/sync/cli.py:22'],
            uses: [{ kind: 'resource', title: '水位文件', relation: '写入 since 游标', mode: 'write', text: '下次同步从这里继续。', sources: ['lumen/sync/cli.py:22'] }]
          }
        ],
        data: [
          { id: 'delta', title: '增量记录', text: '供应商返回的变更集与游标。', sources: ['lumen/sync/cli.py:13-14'] },
          { id: 'checked', title: '校验后记录', text: '通过 ISBN 与必填校验的记录。', sources: ['lumen/sync/cli.py:15-17'] },
          { id: 'indexed', title: '已写入记录', text: '本次 upsert 的书目。', sources: ['lumen/sync/cli.py:21'] },
          { id: 'skipped', title: '跳过计数', text: '已存在而跳过的条数。', sources: ['lumen/sync/cli.py:18-20'] },
          { id: 'watermark', title: '同步水位', text: '下次增量同步的起点。', sources: ['lumen/sync/cli.py:22'] }
        ],
        edges: [
          { from: 'pull', to: 'validate', label: '增量就绪', sources: ['lumen/sync/cli.py:13-15'] },
          { from: 'validate', to: 'isNew', label: '记录已校验', sources: ['lumen/sync/cli.py:15-18'] },
          { from: 'isNew', to: 'upsert', label: '新书', branch: 'new', sources: ['lumen/sync/cli.py:18-21'] },
          { from: 'isNew', to: 'skip', label: '已存在', branch: 'dup', sources: ['lumen/sync/cli.py:18-20'] },
          { from: 'upsert', to: 'mark', label: '写入完成', sources: ['lumen/sync/cli.py:21-22'] },
          { from: 'skip', to: 'mark', label: '跳过后继续', sources: ['lumen/sync/cli.py:19-22'] }
        ],
        links: [
          { from: 'pull', to: 'delta', label: '变更集', sources: ['lumen/sync/cli.py:13-14'] },
          { from: 'delta', to: 'validate', label: '待校验记录', sources: ['lumen/sync/cli.py:15-17'] },
          { from: 'validate', to: 'checked', label: '有效记录', sources: ['lumen/sync/cli.py:15-17'] },
          { from: 'checked', to: 'isNew', label: 'ISBN', sources: ['lumen/sync/cli.py:18'] },
          { from: 'checked', to: 'upsert', label: '新书详情', sources: ['lumen/sync/cli.py:21'], guard: { isNew: 'new' } },
          { from: 'upsert', to: 'indexed', label: '写入结果', sources: ['lumen/sync/cli.py:21'] },
          { from: 'checked', to: 'skip', label: '重复记录', sources: ['lumen/sync/cli.py:19'], guard: { isNew: 'dup' } },
          { from: 'skip', to: 'skipped', label: '跳过计数', sources: ['lumen/sync/cli.py:19-20'] },
          { from: 'delta', to: 'mark', label: '本次游标', sources: ['lumen/sync/cli.py:22'] },
          { from: 'mark', to: 'watermark', label: 'since', sources: ['lumen/sync/cli.py:22'] }
        ]
      }
    }
  ],
  capabilities: [
    { title: '关键词检索与分页', workflows: ['search'], status: 'covered', sources: ['lumen/search/service.py:40-48'] },
    { title: '判断与异常路径', workflows: ['search'], status: 'covered', sources: ['lumen/search/api.py:25-27'] },
    { title: '每日推荐', workflows: ['recommend'], status: 'covered', sources: ['lumen/recommend/job.py:14-22'] },
    { title: '馆藏增量同步', workflows: ['sync'], status: 'covered', sources: ['lumen/sync/cli.py:12-22'] },
    { title: '相似书目', workflows: ['search'], status: 'pending', reason: '向量召回尚未接入，当前只有关键词匹配。' },
    { title: '语义检索', workflows: ['search'], status: 'unavailable', reason: '未部署向量索引。' },
    { title: '多语言检索', workflows: ['search'], status: 'not-implemented', reason: '只有中英文分析器，缺少跨语言查询改写。' }
  ],
  sources: {
    'lumen/search/api.py:18-27': { path: 'lumen/search/api.py', start: 18, end: 27, lines: [
      "@router.get('/search')",
      "def search(q: str, page: int = 1, size: int = 20):",
      "    raw = {k: v for k, v in request.args.items()}",
      "    params = parse_query(raw)",
      "    if not params.text:",
      "        return empty_response(params)",
      "    hits = retrieve(params)",
      "    if not hits:",
      "        return empty_response(params)",
      "    return assemble_response(params, hits)"
    ] },
    'lumen/search/query.py:7-24': { path: 'lumen/search/query.py', start: 7, end: 24, lines: [
      "def parse_query(raw):",
      "    text = (raw.get('q') or '').strip()",
      "    return Query(text=text, page=int(raw.get('page', 1)),",
      "                 size=min(int(raw.get('size', 20)), 50))",
      "",
      "def normalize(text):",
      "    text = unicodedata.normalize('NFKC', text)",
      "    return re.sub(r'\\s+', ' ', text).strip().lower()",
      "",
      "def with_paging(params):",
      "    page = max(1, params.page)",
      "    size = min(max(1, params.size), 50)",
      "    return params._replace(page=page, size=size)"
    ] },
    'lumen/search/query.py:7-11': { path: 'lumen/search/query.py', start: 7, end: 11, lines: [
      "def parse_query(raw):",
      "    text = (raw.get('q') or '').strip()",
      "    return Query(text=text, page=int(raw.get('page', 1)),",
      "                 size=min(int(raw.get('size', 20)), 50))",
      ""
    ] },
    'lumen/search/query.py:13-19': { path: 'lumen/search/query.py', start: 13, end: 19, lines: [
      "def normalize(text):",
      "    text = unicodedata.normalize('NFKC', text)",
      "    text = re.sub(r'\\s+', ' ', text).strip().lower()",
      "    return text",
      "",
      "def is_blank(text):",
      "    return not text.strip()"
    ] },
    'lumen/search/query.py:21-24': { path: 'lumen/search/query.py', start: 21, end: 24, lines: [
      "def with_paging(params):",
      "    page = max(1, params.page)",
      "    size = min(max(1, params.size), 50)",
      "    return params._replace(page=page, size=size)"
    ] },
    'lumen/search/service.py:40-48': { path: 'lumen/search/service.py', start: 40, end: 48, lines: [
      "def retrieve(params):",
      "    dsl = build_dsl(params)",
      "    try:",
      "        raw = es.search(index='catalog', body=dsl, timeout='800ms')",
      "    except (TimeoutError, TransportError) as exc:",
      "        raise SearchUnavailable from exc",
      "    hits = [normalize_hit(h) for h in raw['hits']['hits']]",
      "    available = [h for h in hits if h.shelf != 'off']",
      "    return paginate(available, params)"
    ] },
    'lumen/search/service.py:42-45': { path: 'lumen/search/service.py', start: 42, end: 45, lines: [
      "    try:",
      "        raw = es.search(index='catalog', body=dsl, timeout='800ms')",
      "    except (TimeoutError, TransportError) as exc:",
      "        raise SearchUnavailable from exc"
    ] },
    'lumen/search/service.py:47-48': { path: 'lumen/search/service.py', start: 47, end: 48, lines: [
      "    available = [h for h in hits if h.shelf != 'off']",
      "    return paginate(available, params)"
    ] },
    'lumen/search/dsl.py:12-17': { path: 'lumen/search/dsl.py', start: 12, end: 17, lines: [
      "def build_dsl(params):",
      "    must = [{'match': {'title': params.text}}]",
      "    must.append({'term': {'shelf': 'on'}})",
      "    return {'query': {'bool': {'must': must}},",
      "            'from': (params.page - 1) * params.size,",
      "            'size': params.size}"
    ] },
    'lumen/search/filter.py:9-15': { path: 'lumen/search/filter.py', start: 9, end: 15, lines: [
      "def filter_off_shelf(hits):",
      "    kept = []",
      "    for hit in hits:",
      "        if hit.shelf == 'off' or hit.unavailable:",
      "            continue",
      "        kept.append(hit)",
      "    return kept"
    ] },
    'lumen/search/response.py:6-10': { path: 'lumen/search/response.py', start: 6, end: 10, lines: [
      "def assemble_response(params, hits):",
      "    body = {'query': params.text, 'page': params.page,",
      "            'total': hits.total, 'items': hits.items[:params.size]}",
      "    cache.set(cache_key(params), body, ttl=300)",
      "    return body"
    ] },
    'lumen/search/empty.py:20-22': { path: 'lumen/search/empty.py', start: 20, end: 22, lines: [
      "def empty_response(params):",
      "    return {'query': params.text, 'items': [],",
      "            'suggestions': spell_suggest(params.text)}"
    ] },
    'lumen/recommend/job.py:14-22': { path: 'lumen/recommend/job.py', start: 14, end: 22, lines: [
      "def daily_job(now):",
      "    readers = profile_repo.batch(active_only=True)",
      "    for reader in readers:",
      "        pool = candidates(reader, limit=200)",
      "        ranked = score(reader, pool)",
      "        if ranked[0].score < THRESHOLD:",
      "            notify_degrade(reader)",
      "            continue",
      "        cards = card_writer.write(reader, ranked[:12])"
    ] },
    'lumen/recommend/job.py:15-16': { path: 'lumen/recommend/job.py', start: 15, end: 16, lines: [
      "    readers = profile_repo.batch(active_only=True)",
      "    for reader in readers:"
    ] },
    'lumen/recommend/job.py:17': { path: 'lumen/recommend/job.py', start: 17, end: 17, lines: ["        pool = candidates(reader, limit=200)"] },
    'lumen/recommend/job.py:18-19': { path: 'lumen/recommend/job.py', start: 18, end: 19, lines: [
      "        ranked = score(reader, pool)",
      "        if ranked[0].score < THRESHOLD:"
    ] },
    'lumen/recommend/job.py:19-20': { path: 'lumen/recommend/job.py', start: 19, end: 20, lines: [
      "        if ranked[0].score < THRESHOLD:",
      "            notify_degrade(reader)"
    ] },
    'lumen/recommend/job.py:19-22': { path: 'lumen/recommend/job.py', start: 19, end: 22, lines: [
      "        if ranked[0].score < THRESHOLD:",
      "            notify_degrade(reader)",
      "            continue",
      "        cards = card_writer.write(reader, ranked[:12])"
    ] },
    'lumen/recommend/job.py:21': { path: 'lumen/recommend/job.py', start: 21, end: 21, lines: ["        cards = card_writer.write(reader, ranked[:12])"] },
    'lumen/recommend/job.py:21-22': { path: 'lumen/recommend/job.py', start: 21, end: 22, lines: [
      "        cards = card_writer.write(reader, ranked[:12])",
      "        job_log.record(reader.id, cards)"
    ] },
    'lumen/recommend/job.py:22': { path: 'lumen/recommend/job.py', start: 22, end: 22, lines: ["        job_log.record(reader.id, cards)"] },
    'lumen/recommend/score.py:8-12': { path: 'lumen/recommend/score.py', start: 8, end: 12, lines: [
      "def score(reader, pool):",
      "    ranked = []",
      "    for item in pool:",
      "        ranked.append((item, affinity(reader, item) + freshness(item)))",
      "    return sorted(ranked, key=lambda pair: pair[1], reverse=True)"
    ] },
    'lumen/recommend/score.py:12': { path: 'lumen/recommend/score.py', start: 12, end: 12, lines: ["    return sorted(ranked, key=lambda pair: pair[1], reverse=True)"] },
    'lumen/sync/cli.py:12-22': { path: 'lumen/sync/cli.py', start: 12, end: 22, lines: [
      "def sync(since):",
      "    client = OaiClient(base_url=config.OAI_URL)",
      "    records = client.changes(since=since)",
      "    for rec in records:",
      "        if not isbn_valid(rec.isbn):",
      "            continue",
      "        if index.exists(rec.isbn):",
      "            skipped += 1",
      "            continue",
      "        index.upsert(rec)",
      "    state.write({'since': records.cursor})"
    ] },
    'lumen/sync/cli.py:12-14': { path: 'lumen/sync/cli.py', start: 12, end: 14, lines: [
      "def sync(since):",
      "    client = OaiClient(base_url=config.OAI_URL)",
      "    records = client.changes(since=since)"
    ] },
    'lumen/sync/cli.py:13-14': { path: 'lumen/sync/cli.py', start: 13, end: 14, lines: [
      "    client = OaiClient(base_url=config.OAI_URL)",
      "    records = client.changes(since=since)"
    ] },
    'lumen/sync/cli.py:15-17': { path: 'lumen/sync/cli.py', start: 15, end: 17, lines: [
      "    for rec in records:",
      "        if not isbn_valid(rec.isbn):",
      "            continue"
    ] },
    'lumen/sync/cli.py:15-18': { path: 'lumen/sync/cli.py', start: 15, end: 18, lines: [
      "    for rec in records:",
      "        if not isbn_valid(rec.isbn):",
      "            continue",
      "        if index.exists(rec.isbn):"
    ] },
    'lumen/sync/cli.py:18-20': { path: 'lumen/sync/cli.py', start: 18, end: 20, lines: [
      "        if index.exists(rec.isbn):",
      "            skipped += 1",
      "            continue"
    ] },
    'lumen/sync/cli.py:18-21': { path: 'lumen/sync/cli.py', start: 18, end: 21, lines: [
      "        if index.exists(rec.isbn):",
      "            skipped += 1",
      "            continue",
      "        index.upsert(rec)"
    ] },
    'lumen/sync/cli.py:19-20': { path: 'lumen/sync/cli.py', start: 19, end: 20, lines: [
      "            skipped += 1",
      "            continue"
    ] },
    'lumen/sync/cli.py:19-22': { path: 'lumen/sync/cli.py', start: 19, end: 22, lines: [
      "            skipped += 1",
      "            continue",
      "        index.upsert(rec)",
      "    state.write({'since': records.cursor})"
    ] },
    'lumen/sync/cli.py:21': { path: 'lumen/sync/cli.py', start: 21, end: 21, lines: ["        index.upsert(rec)"] },
    'lumen/sync/cli.py:21-22': { path: 'lumen/sync/cli.py', start: 21, end: 22, lines: [
      "        index.upsert(rec)",
      "    state.write({'since': records.cursor})"
    ] },
    'lumen/sync/cli.py:22': { path: 'lumen/sync/cli.py', start: 22, end: 22, lines: ["    state.write({'since': records.cursor})"] },
    'lumen/sync/oai.py:6-12': { path: 'lumen/sync/oai.py', start: 6, end: 12, lines: [
      "class OaiClient:",
      "    def __init__(self, base_url):",
      "        self.session = Session(base_url, retries=3)",
      "",
      "    def changes(self, since):",
      "        return self.session.get('/changes', params={'since': since})"
    ] }
  }
};
