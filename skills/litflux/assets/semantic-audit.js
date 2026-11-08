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
    if (ratio > 4 || ratio < 0.25) warnings.push({ code: 'G8', ids: [], detail: `画布纵横比 ${round(ratio)}:1；可按阅读需要考虑折返`, info:true });
    for (const box of nodes) {
      const inside=(x,y)=>{
        const w=box.width/2-2,h=box.height/2-2;
        if(box.role==='data')return x*x+y*y<=w*w;
        if(box.role==='decision')return Math.abs(x)/w+Math.abs(y)/h<=1;
        return Math.abs(x)<=w&&Math.abs(y)<=h;
      };
      if ((box.textBoxes||[]).some(r=>[[r.x,r.y],[r.x+r.width,r.y],[r.x,r.y+r.height],[r.x+r.width,r.y+r.height]].some(([x,y])=>!inside(x,y)))) {
        warnings.push({ code: 'G9', ids: [box.id], detail: '文字超出形状' });
      }
      if(box.iconBox){
        const icon=box.iconBox;
        if(!inside(icon.x,icon.y)||!inside(icon.x+icon.width,icon.y+icon.height))warnings.push({code:'G9',ids:[box.id],detail:'资源图标超出形状'});
        if((box.textBoxes||[]).some(t=>t.x<icon.x+icon.width+4&&t.x+t.width>icon.x&&t.y<icon.y+icon.height&&t.y+t.height>icon.y))warnings.push({code:'G9',ids:[box.id],detail:'文字与资源图标重叠'});
      }
    }
    const offset=diagram.geometry.offset||{x:0,y:0};
    for(const warning of warnings){
      warning.coordinateSpace='author';
      warning.boxes=[...nodes,...notes].filter(b=>warning.ids.includes(b.id)).map(b=>({...b,x:b.x-offset.x,y:b.y-offset.y}));
      const note=notes.find(n=>n.id===warning.ids[0]),edge=edges.find(e=>e.id===note?.id);
      if(!note||!edge||!['G2','G3','G4','G5'].includes(warning.code))continue;
      const candidates=edge.points.map(([x,y])=>({x,y,width:note.width,height:note.height})).filter(b=>
        b.x-b.width/2>=8&&b.y-b.height/2>=8&&b.x+b.width/2<=width-8&&b.y+b.height/2<=height-8&&
        !nodes.some(n=>boxOverlap(b,n)>0)&&!notes.some(n=>n.id!==note.id&&boxOverlap(b,n)>0));
      candidates.sort((a,b)=>Math.hypot(a.x-note.x,a.y-note.y)-Math.hypot(b.x-note.x,b.y-note.y));
      warning.suggestion=candidates.length?{noteAt:[round(candidates[0].x-offset.x),round(candidates[0].y-offset.y)],reason:'同一实际路径上的局部可放位置；供作者选择'}:{noteAt:null,reason:'当前路径未找到足够空间，可调整走线、位置或 noteWidth'};
      const nearest=[...edge.points].sort((a,b)=>Math.hypot(a[0]-note.x,a[1]-note.y)-Math.hypot(b[0]-note.x,b[1]-note.y))[0];
      warning.nearestPathPoint=nearest.map((v,i)=>round(v-(i?offset.y:offset.x)));
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
      if(object.type==='resource'&&node.dataset.resourceKind!==LitFluxDrawing.resourceKind(object.resourceKind))failures.push(`资源 ${object.id} 的图标与声明不符`);
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
  const pause = async () => { await document.fonts.ready; await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))); };

  function scenarios(flow,limit=32){
    const owners=flow.objects.filter(o=>o.choices),total=owners.reduce((n,o)=>n*o.choices.length,1),values=[];
    function visit(i,state){if(values.length>=limit)return;if(i===owners.length){values.push(state);return;}for(const c of owners[i].choices)visit(i+1,{...state,[owners[i].id]:c.id});}
    visit(0,{});return {values,total,complete:values.length===total};
  }

  async function run({geometryOnly=false}={}) {
    const clock=performance.now();
    const result = { status: 'running', mode:geometryOnly?'geometry-only':'full', revision: payload.revision, views: [], failures: [], geometry: { warnings: [], diagnostics:[] }, checks: {navigation:'not-run',reading:'not-run',sources:'not-run'}, timingsMs:{} };
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
      result.geometry.diagnostics.push(...all.map(w=>({view:key,...w})));
      result.geometry.info = (result.geometry.info || []).concat(
        all.filter((warning) => warning.info).map((warning) => `${view.title}：${warning.detail}`));
    }
    result.timingsMs.geometry=round(performance.now()-clock);
    result.viewport={width:document.querySelector('#canvas').clientWidth,height:document.querySelector('#canvas').clientHeight};
    if(geometryOnly){navigate(started);result.status=result.failures.length?'failed':'passed';result.geometry.status=result.geometry.warnings.length?'warnings':'passed';return result;}
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
    result.checks.reading=[];result.checks.sources=[];
    for(const checked of result.views){
      const view=businesses.get(checked.key);navigate(checked.key);await pause();
      const cases=scenarios(view.flow),failures=[],advisories=[];
      for(const values of cases.values){
        const plan=readingPlan(view.flow,values);
        if(plan.blocked.length)failures.push({values,blocked:plan.blocked,conflicts:plan.conflicts});
        if(plan.conflicts.length)advisories.push({values,objects:plan.conflicts,detail:'输入可能绕过未选条件；核对是否是独立入口或需要 when，不自动改写'});
      }
      result.checks.reading.push({view:checked.key,checked:cases.values.length,total:cases.total,complete:cases.complete,failures,advisories});
      for(const failure of failures)result.failures.push(`${view.title}：阅读依赖受阻 ${JSON.stringify(failure)}`);
      let tested=0;
      for(const [kind,items] of [['object',view.flow.objects],['relation',view.flow.relations]])for(const item of items){
        if(!item.sources)continue;
        if(kind==='object')select(item);else selectRelation(item);
        document.querySelector('#show-source').click();
        const expected=[...new Set([item.sources].flat())];
        const found=[...document.querySelectorAll('#sources [data-ref]')].map(n=>n.dataset.ref);
        const passed=!document.querySelector('#drawer').hidden&&expected.every(ref=>found.includes(ref));
        if(!passed)result.failures.push(`${view.title}/${item.id}：源码点击未显示声明引用`);
        closeSource();tested++;
      }
      result.checks.sources.push({view:checked.key,tested,status:tested?'tested':'no-declared-source'});
      await pause();
      const panelWarnings=geometryWarnings(currentDiagram,view.flow).filter(w=>!w.info);
      result.geometry.diagnostics.push(...panelWarnings.map(w=>({view:checked.key,context:'details-open',...w})));
      result.geometry.warnings.push(...panelWarnings.map(w=>`${view.title}（详情打开）：${w.code} ${w.detail} ${w.ids.join('/')}`));
    }
    navigate(started);
    result.timingsMs.interactions=round(performance.now()-clock-result.timingsMs.geometry);
    result.status = result.failures.length ? 'failed' : 'passed';
    result.geometry.status = result.geometry.warnings.length ? 'warnings' : 'passed';
    return result;
  }

  window.litflux = {
    startEntryAudit(options={}) {
      if (job?.status==='running') return 'running';
      job = { status: 'running' };
      run(options).then(
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
