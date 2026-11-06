// 一份内容定义，每个视图自己安排坐标。这里的数字只服务于这张小图，不是通用排图规则。
const saved = {
  title: '写入文本', sources: 'app:9-11',
  objects: [
    { id: 'text', type: 'data', title: '清理后的文本', sources: 'app:18' },
    { id: 'path', type: 'data', title: '目标路径', sources: 'app:18' },
    { id: 'write', type: 'business', title: '写入文本', text: '通过当前 writer 写入；默认实现使用 UTF-8。' },
    { id: 'location', type: 'data', title: '保存位置' },
    { id: 'writer', type: 'component', title: '当前写入器', text: '默认 write_text，也可由调用者替换。', sources: ['app:14', 'app:18'] },
    { id: 'file', type: 'resource', title: '目标文本文件', sources: 'app:10' },
  ],
  relations: [
    { id: 'content', type: 'data', from: 'text', to: 'write', label: '待写文本', timing: 'immediate' },
    { id: 'destination', type: 'data', from: 'path', to: 'write', label: '目标路径', timing: 'immediate' },
    { id: 'call', type: 'capability', from: 'writer', to: 'write', label: '提供写入能力' },
    { id: 'change', type: 'effect', from: 'write', to: 'file', label: '写入 UTF-8 内容' },
    { id: 'returned', type: 'data', from: 'write', to: 'location', label: '返回保存位置', timing: 'immediate' },
  ],
  draw(s) {
    s.node('write', 420, 240)
      .node('text', 150, 140).node('path', 150, 340)
      .node('writer', 420, 80).node('file', 700, 340).node('location', 700, 140);
    s.edge('content', { sides: ['right', 'left'], via: [[280, 140], [280, 240]], noteAt: [280, 190] })
      .edge('destination', { sides: ['right', 'left'], via: [[330, 340], [330, 300]], noteAt: [330, 340] })
      .edge('call', { sides: ['bottom', 'top'], noteAt: [420, 160] })
      .edge('change', { sides: ['right', 'left'], via: [[580, 240], [580, 340]], noteAt: [580, 290], noteWidth: 120 })
      .edge('returned', { sides: ['right', 'left'], via: [[560, 240], [560, 140]], noteAt: [560, 190] });
  },
};

const submit = {
  title: '提交文本', sources: 'app:14-19',
  objects: [
    { id: 'raw', type: 'data', title: '原始文本', text: '调用者提交的内容。' },
    { id: 'normalize', type: 'business', title: '规范化文本', text: '去除首尾空白即可，无需为这一个库调用再造子图。', sources: ['app:5-6', 'app:15'] },
    { id: 'cleaned', type: 'data', title: '清理后的文本' },
    { id: 'nonempty', type: 'decision', title: '文本非空吗？', choices: [{ id: 'yes', label: '非空：保存' }, { id: 'no', label: '空：拒绝' }] },
    { id: 'path', type: 'data', title: '目标路径' },
    { id: 'save', type: 'business', title: '保存文本', text: '非空时调用选定 writer；进入内部可见组件与文件作用。', detail: saved },
    { id: 'location', type: 'data', title: '保存位置' },
    { id: 'accepted', type: 'business', title: '返回保存结果' },
    { id: 'result', type: 'data', title: '保存响应' },
    { id: 'rejected', type: 'business', title: '返回拒绝结果', text: '空内容返回 saved=False，不调用 writer。', sources: 'app:17' },
    { id: 'rejection', type: 'data', title: '拒绝响应', sources: 'app:17' },
  ],
  relations: [
    { id: 'request', type: 'data', from: 'raw', to: 'normalize', label: '原始文本', timing: 'immediate' },
    { id: 'normalized', type: 'data', from: 'normalize', to: 'cleaned', label: '清理后文本', timing: 'immediate' },
    { id: 'predicate', type: 'data', from: 'cleaned', to: 'nonempty', label: '非空判据', timing: 'immediate' },
    { id: 'yes', type: 'control', from: 'nonempty', to: 'save', label: '非空', branch: 'yes' },
    { id: 'no', type: 'control', from: 'nonempty', to: 'rejected', label: '空文本', branch: 'no' },
    // 作者判断：同一份文本先用于判断，跨过判断后保留给保存处理。
    { id: 'retained', type: 'data', from: 'cleaned', to: 'save', label: '保留到保存时使用', timing: 'deferred', when: { nonempty: 'yes' }, timingNote: '文本先交给非空判断；判断通过后，同一份文本才被保存处理使用，中间隔着判断这一步。' },
    { id: 'destination', type: 'data', from: 'path', to: 'save', label: '目标路径', timing: 'immediate', when: { nonempty: 'yes' } },
    { id: 'stored', type: 'data', from: 'save', to: 'location', label: '返回位置', timing: 'immediate' },
    { id: 'return-location', type: 'data', from: 'location', to: 'accepted', label: '保存位置', timing: 'immediate' },
    { id: 'public-result', type: 'data', from: 'accepted', to: 'result', label: '保存响应', timing: 'immediate' },
    { id: 'public-rejection', type: 'data', from: 'rejected', to: 'rejection', label: '拒绝响应', timing: 'immediate' },
  ],
  draw(s) {
    s.node('raw', 80, 140).node('normalize', 290, 140).node('cleaned', 500, 140)
      .node('nonempty', 710, 140).node('save', 930, 140).node('location', 1130, 140)
      .node('rejection', 80, 350).node('rejected', 290, 350).node('path', 930, 350)
      .node('accepted', 1130, 350).node('result', 1130, 480);
    s.edge('request', { sides: ['right', 'left'], noteAt: [178, 140] })
      .edge('normalized', { sides: ['right', 'left'], noteAt: [395, 140] })
      .edge('predicate', { sides: ['right', 'left'], noteAt: [604, 140] })
      .edge('yes', { sides: ['right', 'left'], noteAt: [822, 140] })
      .edge('retained', { sides: ['top', 'top'], via: [[500, 44], [930, 44]], noteAt: [715, 44] })
      .edge('no', { sides: ['bottom', 'top'], via: [[710, 270], [290, 270]], noteAt: [500, 270] })
      .edge('destination', { sides: ['top', 'bottom'], noteAt: [930, 240], noteWidth: 110 })
      .edge('stored', { sides: ['right', 'left'], noteAt: [1037, 140] })
      .edge('return-location', { sides: ['bottom', 'top'], noteAt: [1130, 250], noteWidth: 100 })
      .edge('public-result', { sides: ['bottom', 'top'], noteAt: [1130, 410] })
      .edge('public-rejection', { sides: ['left', 'right'], noteAt: [176, 350] });
  },
};

const batch = {
  title: '逐条提交并收集结果', sources: 'app:22-26',
  objects: [
    { id: 'texts', type: 'data', title: '文本集合' },
    { id: 'begin', type: 'business', title: '初始化批量处理' },
    { id: 'more', type: 'decision', title: '还有文本吗？', choices: [{ id: 'more', label: '有：处理下一条' }, { id: 'done', label: '无：返回累计结果' }] },
    { id: 'take', type: 'business', title: '读取下一条文本' },
    { id: 'text', type: 'data', title: '当前文本' },
    { id: 'submit', type: 'business', title: '提交一条文本', detail: submit, sources: 'app:25' },
    { id: 'one', type: 'data', title: '单条响应' },
    { id: 'collect', type: 'business', title: '收集本条结果', sources: 'app:25' },
    { id: 'results', type: 'resource', title: '累计结果列表', text: '循环中共享的可变状态：先初始化，再逐条追加。' },
    { id: 'finish', type: 'business', title: '返回累计结果', sources: 'app:26' },
    { id: 'reply', type: 'data', title: '批量响应', sources: 'app:26' },
  ],
  relations: [
    { id: 'input', type: 'data', from: 'texts', to: 'begin', label: '文本集合', timing: 'immediate' },
    { id: 'start', type: 'control', from: 'begin', to: 'more', label: '开始遍历' },
    { id: 'more', type: 'control', from: 'more', to: 'take', label: '还有文本', branch: 'more' },
    { id: 'done', type: 'control', from: 'more', to: 'finish', label: '已经遍历完', branch: 'done' },
    { id: 'item', type: 'data', from: 'take', to: 'text', label: '当前文本', timing: 'immediate' },
    { id: 'submit', type: 'data', from: 'text', to: 'submit', label: '提交内容', timing: 'immediate' },
    { id: 'response', type: 'data', from: 'submit', to: 'one', label: '单条响应', timing: 'immediate' },
    { id: 'collect', type: 'data', from: 'one', to: 'collect', label: '待收集响应', timing: 'immediate' },
    { id: 'init', type: 'effect', from: 'begin', to: 'results', label: '初始化空列表' },
    { id: 'append', type: 'effect', from: 'collect', to: 'results', label: '追加结果' },
    { id: 'read', type: 'effect', from: 'results', to: 'finish', label: '读取累计结果' },
    { id: 'repeat', type: 'loop', from: 'collect', to: 'more', label: '↺ 继续下一条' },
    { id: 'reply', type: 'data', from: 'finish', to: 'reply', label: '批量响应', timing: 'immediate' },
  ],
  draw(s) {
    s.node('texts', 80, 130).node('begin', 290, 130, { width: 140 }).node('more', 500, 130)
      .node('take', 720, 130).node('text', 940, 130).node('submit', 1140, 130)
      .node('one', 1150, 350).node('collect', 930, 350).node('results', 700, 350)
      .node('finish', 430, 520).node('reply', 700, 520);
    s.edge('input', { sides: ['right', 'left'], noteAt: [178, 130] })
      .edge('start', { sides: ['right', 'left'], noteAt: [397, 130] })
      .edge('more', { sides: ['right', 'left'], noteAt: [600, 130] })
      .edge('item', { sides: ['right', 'left'], noteAt: [830, 130] })
      .edge('submit', { sides: ['right', 'left'], noteAt: [1038, 130] })
      .edge('response', { sides: ['bottom', 'top'], noteAt: [1145, 235] })
      .edge('collect', { sides: ['left', 'right'], noteAt: [1049, 350] })
      .edge('init', { sides: ['bottom', 'top'], via: [[290, 270], [700, 270]], noteAt: [495, 270] })
      .edge('append', { sides: ['left', 'right'], noteAt: [815, 350] })
      .edge('read', { sides: ['bottom', 'top'], via: [[700, 440], [430, 440]], noteAt: [565, 440] })
      .edge('done', { sides: ['bottom', 'top'], via: [[500, 220], [430, 220]], noteAt: [465, 220], noteWidth: 110 })
      .edge('repeat', { sides: ['top', 'top'], via: [[930, 290], [1240, 290], [1240, 50], [500, 50]], noteAt: [800, 50], noteWidth: 120 })
      .edge('reply', { sides: ['right', 'left'], noteAt: [578, 520] });
  },
};

module.exports = {
  title: '文本保存 · 项目脉络',
  language: 'zh',
  author: 'litflux-example',
  summary: '以真实小型源码演示：先规范化并判断，再通过写入器保存；批量入口逐条提交并累计结果。',
  scope: '教学源码中的 submit、write_text 与 submit_many；不会执行这些函数。',
  files: { app: 'app.py' },
  workflows: [
    { id: 'submit', title: '提交并保存文本', entry: { trigger: '调用 submit(text, path, writer)', sources: 'app:14-19' }, flow: submit },
    { id: 'batch', title: '批量提交文本', entry: { trigger: '调用 submit_many(texts, path, writer)', sources: 'app:22-26' }, flow: batch },
  ],
};
