// Declaration checks plus objective geometry checks. Nothing here judges meaning or taste.
(() => {
  const round = (value) => Math.round(value * 10) / 10;
  const boxOverlap = (a, b) => {
    const w = Math.min(a.x + a.width / 2, b.x + b.width / 2) - Math.max(a.x - a.width / 2, b.x - b.width / 2);
    const h = Math.min(a.y + a.height / 2, b.y + b.height / 2) - Math.max(a.y - a.height / 2, b.y - b.height / 2);
    return w > 0 && h > 0 ? Math.min(w, h) : 0;
  };
  const insideBox = (point, box, pad = 0) => Math.abs(point[0] - box.x) < box.width / 2 - pad && Math.abs(point[1] - box.y) < box.height / 2 - pad;
  function segmentHitsBox(a, b, box, pad = 2) {
    const steps = Math.max(2, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 4));
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      if (insideBox([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], box, pad)) return true;
    }
    return false;
  }
  function pointToSegment(point, a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const length = dx * dx + dy * dy;
    const t = length ? Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) : 0;
    return Math.hypot(point[0] - (a[0] + dx * t), point[1] - (a[1] + dy * t));
  }
  function pointToPolyline(point, points) {
    let best = Infinity;
    for (let i = 1; i < points.length; i++) best = Math.min(best, pointToSegment(point, points[i - 1], points[i]));
    return best;
  }

  function geometryWarnings(diagram, flow) {
    if (!diagram?.geometry) return [{ code: 'G0', ids: [], detail: '没有几何数据：drawing 可能未完成' }];
    const warnings = [];
    const { nodes, notes, edges, width, height } = diagram.geometry;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const overlap = boxOverlap(nodes[i], nodes[j]);
        if (overlap > 0) warnings.push({ code: 'G1', ids: [nodes[i].id, nodes[j].id], detail: `节点重叠 ${round(overlap)}px` });
      }
    }
    for (const box of nodes) {
      if (box.x - box.width / 2 < 8 || box.y - box.height / 2 < 8 || box.x + box.width / 2 > width - 8 || box.y + box.height / 2 > height - 8) {
        warnings.push({ code: 'G2', ids: [box.id], detail: '节点越出画布' });
      }
    }
    for (const note of notes) {
      if (note.x - note.width / 2 < 8 || note.y - note.height / 2 < 8 || note.x + note.width / 2 > width - 8 || note.y + note.height / 2 > height - 8) {
        warnings.push({ code: 'G2', ids: [note.id], detail: '边注越出画布' });
      }
      for (const box of nodes) {
        if (boxOverlap(note, box) > 0) warnings.push({ code: 'G3', ids: [note.id, box.id], detail: '边注压在节点上' });
      }
      for (const other of notes) {
        if (other.id !== note.id && boxOverlap(note, other) > 0) warnings.push({ code: 'G4', ids: [note.id, other.id], detail: '边注互相重叠' });
      }
    }
    for (const edge of edges) {
      const note = notes.find((item) => item.id === edge.id);
      if (note) {
        const distance = pointToPolyline([note.x, note.y], edge.points);
        if (distance > 40) warnings.push({ code: 'G5', ids: [edge.id], detail: `边注离所属边 ${Math.round(distance)}px` });
      }
      const source = flow.relations.find((relation) => relation.id === edge.id);
      for (const box of nodes) {
        if (box.id === source?.from || box.id === source?.to) continue;
        for (let i = 1; i < edge.points.length; i++) {
          if (segmentHitsBox(edge.points[i - 1], edge.points[i], box, 2)) {
            warnings.push({ code: 'G6', ids: [edge.id, box.id], detail: '连线穿过其他对象' });
            break;
          }
        }
      }
    }
    // Fitting depends on the reviewer's window, so it is reported, never scored.
    const host = document.querySelector('#canvas');
    if (host) {
      const fit = Math.min(1, (host.clientWidth - 32) / width, (host.clientHeight - 32) / height);
      warnings.push({ code: 'I1', ids: [], detail: `全图适配约 ${Math.round(fit * 100)}%，正文按 100% 阅读`, info: true });
    }
    const ratio = width / Math.max(1, height);
    if (ratio > 4 || ratio < 0.25) warnings.push({ code: 'G8', ids: [], detail: `画布纵横比 ${round(ratio)}:1` });
    for (const box of nodes) {
      if (box.textWidth > box.width - 8 || box.textHeight > box.height - 8) {
        warnings.push({ code: 'G9', ids: [box.id], detail: '文字超出形状' });
      }
    }
    const seen = new Set();
    return warnings.filter((warning) => {
      const key = warning.code + warning.ids.join(',');
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function declarationFailures(flow) {
    const failures = [];
    const objects = [...document.querySelectorAll('#canvas [data-node]')];
    const relations = [...document.querySelectorAll('#canvas [data-relation]')];
    if (objects.length !== flow.objects.length) failures.push(`对象数量不符：绘制 ${objects.length}，声明 ${flow.objects.length}`);
    if (relations.length !== flow.relations.length) failures.push(`关系数量不符：绘制 ${relations.length}，声明 ${flow.relations.length}`);
    for (const object of flow.objects) {
      const node = objects.find((item) => item.dataset.node === object.id);
      if (!node) { failures.push(`缺少对象 ${object.id}`); continue; }
      if (node.dataset.role !== object.type) failures.push(`对象 ${object.id} 的角色与声明不符`);
    }
    for (const relation of flow.relations) {
      const drawn = currentDiagram?.drawn.get(relation.id);
      if (!drawn) { failures.push(`缺少关系 ${relation.id}`); continue; }
      const text = drawn.group.querySelector('.note-title')?.textContent.replace(/\s/g, '') || '';
      if (text !== (relation.label || '').replace(/\s/g, '')) failures.push(`关系 ${relation.id} 的边注被截断或改写`);
      const classes = drawn.line.classList;
      if (relation.type === 'data') {
        const expected = relation.timing;
        if (!classes.contains(expected)) failures.push(`关系 ${relation.id} 的线型与声明 ${expected} 不一致`);
        if (classes.contains(expected === 'immediate' ? 'deferred' : 'immediate')) failures.push(`关系 ${relation.id} 同时带有两种线型`);
      } else if (classes.contains('immediate') || classes.contains('deferred')) {
        failures.push(`关系 ${relation.id} 是非数据关系，却带了实虚语义`);
      }
    }
    return failures;
  }

  let job = null;
  const pause = () => new Promise((resolve) => setTimeout(resolve, 0));

  async function run() {
    const result = { status: 'running', revision: payload.revision, views: [], failures: [], geometry: { warnings: [] }, checks: {} };
    const started = current;
    const seenFlows = new Set();
    for (const [key, view] of businesses) {
      if (!view.flow || seenFlows.has(view.flow)) continue;
      seenFlows.add(view.flow);
      navigate(key);
      await pause();
      if (currentDiagram?.error) { result.failures.push(`${view.title}：绘图错误 ${currentDiagram.error}`); continue; }
      const failures = declarationFailures(view.flow);
      const all = geometryWarnings(currentDiagram, view.flow);
      const warnings = all.filter((warning) => !warning.info);
      result.views.push({ key, title: view.title, failures, warnings, info: all.filter((warning) => warning.info) });
      result.failures.push(...failures.map((message) => `${view.title}：${message}`));
      result.geometry.warnings.push(...warnings.map((warning) => `${view.title}：${warning.code} ${warning.detail} ${warning.ids.join('/')}`));
      result.geometry.info = (result.geometry.info || []).concat(
        all.filter((warning) => warning.info).map((warning) => `${view.title}：${warning.detail}`));
    }
    // Navigation: enter a nested business and come back.
    const nested = [...businesses.values()].find((view) => view.flow
      && [...businesses.values()].some((child) => child.parent === view.key && child.flow));
    if (nested) {
      navigate(nested.key);
      const before = current;
      const child = [...businesses.values()].find((view) => view.parent === before && view.flow);
      navigate(child.key);
      const entered = current === child.key;
      navigate(before);
      result.checks.navigation = { entered, returned: current === before, from: before, child: child?.key };
      if (!(entered && current === before)) result.failures.push('进入子业务后无法返回');
    } else {
      result.checks.navigation = 'not-applicable';
    }
    // Reading plan over the default scenario must cover every executable step.
    navigate(started);
    const view = businesses.get(current);
    const plan = readingPlan(view.flow, choices());
    const steps = view.flow.objects.filter((o) => plan.active.has(o.id) && !['resource', 'component', 'boundary'].includes(o.type));
    result.checks.reading = plan.blocked.length === 0 && plan.order.length === steps.length;
    if (!result.checks.reading) {
      result.failures.push('默认情境下的阅读计划受阻：' + (plan.blocked.join('、') || '数量不符'));
    }
    // Source drawer: open and close for a declared reference.
    const refs = view.flow.objects.flatMap((o) => (o.sources ? [o.sources].flat() : []));
    if (refs.length) {
      openSource(refs.slice(0, 1), '检查');
      result.checks.sources = document.querySelector('#drawer').hidden === false
        && document.querySelectorAll('#sources [data-ref]').length > 0;
      closeSource();
    } else {
      result.checks.sources = 'no-declared-source';
    }
    result.status = result.failures.length ? 'failed' : 'passed';
    result.geometry.status = result.geometry.warnings.length ? 'warnings' : 'passed';
    return result;
  }

  window.litflux = {
    startEntryAudit() {
      if (job) return 'running';
      job = { status: 'running' };
      run().then(
        (result) => { job = result; },
        (error) => { job = { status: 'failed', failures: [String(error.message || error)], geometry: { warnings: [] } }; },
      );
      return 'running';
    },
    entryAuditStatus() {
      return JSON.stringify({ status: job ? job.status : 'idle' });
    },
    entryAuditResult() {
      return JSON.stringify(job || { status: 'idle' });
    },
    geometry() {
      return JSON.stringify(currentDiagram?.geometry || null);
    },
  };
})();
