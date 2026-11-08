// LitFlux drawing primitives: place, measure, draw. This file never decides layout,
// line style or object roles — the project module passes everything in.
const LitFluxDrawing = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const FONT = '"Segoe UI","PingFang SC","Microsoft YaHei UI",system-ui,sans-serif';
  const LINE = { 15: 21, 14: 19 };
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const cache = new Map();
  const resourceKinds = Object.freeze({database:'数据库',config:'运行配置',directory:'目录',file:'文件',memory:'共享状态',generic:'通用资源'});
  const resourceKind = kind => Object.hasOwn(resourceKinds,kind) ? kind : 'generic';
  function resourceIcon(kind) {
    kind=resourceKind(kind);
    const icon=el('svg',{viewBox:'0 0 24 24',width:24,height:24,fill:'none',stroke:'currentColor','stroke-width':1.5,'stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',class:'resource-icon','data-resource-icon':kind});
    const paths={
      database:'M4 6C4 2 20 2 20 6C20 10 4 10 4 6V18C4 22 20 22 20 18V6 M4 12C4 16 20 16 20 12',
      directory:'M3 7V5H9L12 8H21V20H3Z M3 8H12',
      file:'M6 2H14L20 8V22H6Z M14 2V8H20 M9 13H17 M9 17H15',
      memory:'M3 6L12 2L21 6L12 10Z M3 11L12 15L21 11 M3 16L12 20L21 16',
      generic:'M3 7L12 3L21 7V17L12 21L3 17Z M3 7L12 11L21 7 M12 11V21'
    };
    if(kind==='config'){
      const points=Array.from({length:32},(_,i)=>{const angle=i*Math.PI/16-Math.PI/2,r=i%4<2?10:8;return `${12+r*Math.cos(angle)},${12+r*Math.sin(angle)}`;});
      icon.append(el('polygon',{points:points.join(' ')}),el('circle',{cx:12,cy:12,r:3}));
    }else icon.append(el('path',{d:paths[kind]}));
    return icon;
  }

  const roleGlyphs = {
    business: 'M5 6.5 11 12l-6 5.5 M13 6.5 19 12l-6 5.5',
    decision: 'M8.4 9.6a3.6 3.6 0 1 1 6.1 2.7c-1.3 1-2 1.6-2 3.1',
    component: 'M7.5 7.5h9v9h-9Z M10 3v4.5 M14 3v4.5 M10 16.5V21 M14 16.5V21 M3 10h4.5 M3 14h4.5 M16.5 10H21 M16.5 14H21',
    boundary: 'M4 4.5h16v15H4Z M8 12h7 M12.5 9l3 3-3 3',
  };
  function roleIcon(type) {
    const shape = Object.hasOwn(roleGlyphs, type) ? type : 'business';
    const icon = el('svg', {
      viewBox: '0 0 24 24', width: 24, height: 24, fill: 'none', stroke: 'currentColor',
      'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      'aria-hidden': 'true', class: 'role-icon', 'data-role-icon': shape,
    });
    icon.append(el('path', { class: 'role-glyph', d: roleGlyphs[shape] }));
    if (shape === 'decision') icon.append(el('circle', { class: 'role-glyph-dot', cx: 12.4, cy: 18.9, r: 1.3, fill: 'currentColor' }));
    return icon;
  }

  function el(tag, attrs = {}) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  }
  function width(text, fontSize) {
    ctx.font = `${fontSize}px ${FONT}`;
    return ctx.measureText(String(text)).width;
  }
  function wrap(text, maxWidth, fontSize = 15) {
    const key = `${fontSize}|${maxWidth}|${text}`;
    if (cache.has(key)) return cache.get(key);
    const lines = [];
    for (const paragraph of String(text ?? '').split('\n')) {
      let line = '';
      for (const token of paragraph.match(/[A-Za-z0-9_./:#-]+|\s+|[^\x00-\xff]|./g) || []) {
        if (!line && !token.trim()) continue;
        if (width(line + token, fontSize) <= maxWidth) { line += token; continue; }
        if (line.trim()) lines.push(line.trim());
        line = '';
        if (width(token, fontSize) <= maxWidth) { if (token.trim()) line = token; continue; }
        for (const ch of token) {
          if (line && width(line + ch, fontSize) > maxWidth) { lines.push(line.trim()); line = ''; }
          line += ch;
        }
      }
      if (line.trim()) lines.push(line.trim());
    }
    if (!lines.length) lines.push('');
    const lineHeight = LINE[fontSize] || Math.round(fontSize * 1.4);
    const result = {
      lines,
      lineHeight,
      width: Math.ceil(Math.max(...lines.map((row) => width(row, fontSize)))),
      height: lines.length * lineHeight,
    };
    cache.set(key, result);
    return result;
  }
  function measure(text, options = {}) {
    const result = wrap(text, options.maxWidth ?? 260, options.fontSize ?? 14);
    return { ...result, lines: [...result.lines],
      boxWidth: result.width + 10, boxHeight: result.height + 6 };
  }

  const SIDES = { left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] };
  function inside(pos, toward, side) {
    let dx = toward[0] - pos.x, dy = toward[1] - pos.y;
    if (side) {
      const direction = SIDES[side];
      if (!direction) throw Error(`${pos.id}: sides must be left/right/top/bottom`);
      [dx, dy] = direction;
    }
    if (!dx && !dy) throw Error(`${pos.id}: coincident endpoints need an explicit side`);
    const hw = pos.width / 2, hh = pos.height / 2;
    let k;
    k = Math.min(dx ? Math.abs(hw / dx) : Infinity, dy ? Math.abs(hh / dy) : Infinity);
    return [pos.x + dx * k, pos.y + dy * k];
  }
  function rounded(points) {
    let d = `M${points[0][0]} ${points[0][1]}`;
    for (let i = 1; i < points.length - 1; i++) {
      const a = points[i - 1], b = points[i], c = points[i + 1];
      const u = Math.hypot(b[0] - a[0], b[1] - a[1]), v = Math.hypot(c[0] - b[0], c[1] - b[1]);
      const r = Math.min(10, u / 2, v / 2);
      if (!u || !v) continue;
      d += ` L${b[0] + (a[0] - b[0]) * r / u} ${b[1] + (a[1] - b[1]) * r / u}`;
      d += ` Q${b[0]} ${b[1]} ${b[0] + (c[0] - b[0]) * r / v} ${b[1] + (c[1] - b[1]) * r / v}`;
    }
    return d + ` L${points.at(-1)[0]} ${points.at(-1)[1]}`;
  }

  function create(flow, host, handlers = {}) {
    const objectById = new Map(flow.objects.map((o) => [o.id, o]));
    const relationById = new Map(flow.relations.map((r) => [r.id, r]));
    const out = el('svg', { role: 'img', 'aria-label': '当前业务的完整内部流程图' });
    const defs = el('defs');
    const style = el('style');
    style.textContent = [
      '.node .shape{fill:var(--process,#edf4ea);stroke:#91aa9c;stroke-width:1.3}',
      '.node.role-data .shape{fill:var(--data,#edf4f8);stroke:#88a4bb}',
      '.node.role-resource .shape{fill:var(--resource,#e8f1e9);stroke:#558c7a}',
      '.node.role-component .shape{fill:var(--provider,#eeeaf5);stroke:#6d86a9}',
      '.node.role-decision .shape{fill:var(--decision,#f3edf7);stroke:#aa95bd}',
      '.node.role-boundary .shape{fill:var(--soft,#eef1ed);stroke:#9aa8aa;stroke-dasharray:3 3}',
      '.node .n-title{fill:var(--ink,#263b34)}',
      '.node .resource-icon{color:var(--resource-line,#558c7a);pointer-events:none}',
      '.node .detail-hint{fill:var(--accent,#32674e);pointer-events:none}',
      '.node{cursor:pointer}',
      '.node.is-selected .shape{stroke:var(--accent,#32674e);stroke-width:2}',
      '.node.is-current .shape{stroke:var(--accent,#32674e);stroke-width:2.5}',
      '.node.is-done .shape{stroke:var(--accent,#32674e)}',
      '.node.is-dim{opacity:.45}',
      '.edge{fill:none;stroke:var(--accent,#32674e);stroke-width:1.5}',
      '.edge.deferred{stroke-dasharray:5 5}',
      '.edge.role-control{stroke:var(--control,#896e32)}',
      '.edge.role-failure{stroke:var(--failure,#a45d65);stroke-dasharray:2 3}',
      '.edge.role-loop{stroke:var(--loop,#7f6ca1);stroke-dasharray:2 5}',
      '.edge.role-effect{stroke:var(--resource-line,#558c7a)}',
      '.edge.role-capability{stroke:var(--provider-line,#6d86a9);stroke-dasharray:1 4}',
      '.edge.related{stroke-width:2.2}',
      '.edge-hit{fill:none;stroke:transparent;stroke-width:12;cursor:pointer}',
      '.edge-hit:focus-visible{stroke:var(--accent);stroke-opacity:.25;outline:none}',
      '.edge.is-dim{opacity:.3}',
      '.relation-note{cursor:pointer}',
      '.relation-note .note-hit{fill:var(--surface,#fffefa);opacity:.97}',
      '.relation-note .note-title{fill:var(--ink,#263b34)}',
      '.relation-note[data-role=control] .note-title{fill:var(--control,#896e32)}',
      '.relation-note[data-role=loop] .note-title{fill:var(--loop,#7f6ca1)}',
      '.relation-note:hover .note-title,.relation-note.is-selected .note-title{fill:var(--accent,#32674e)}',
      '.relation-note.is-selected .note-hit{stroke:var(--line,#dce3dc);stroke-width:.8}',
      '.control-mark{fill:var(--surface,#fffefa);stroke:var(--control,#896e32);stroke-width:1.2}',
      '.flow-particles{pointer-events:none}',
      '.flow-dot{fill:var(--input,#3e719b);stroke:var(--surface,#fffefa);stroke-width:.8}',
      '.flow-dot[data-direction=output]{fill:var(--output,#9a6746)}',
    ].join('\n');
    for (const role of ['data', 'control', 'failure', 'loop', 'effect', 'capability']) {
      const marker = el('marker', {
        id: `arrow-${role}`, markerWidth: 9, markerHeight: 9,
        refX: 8, refY: 4.5, orient: 'auto', markerUnits: 'userSpaceOnUse',
      });
      marker.append(el('path', {
        d: role === 'loop' ? 'M1 1 L8 4.5 L1 8' : 'M0 0 L9 4.5 L0 9 Z',
        fill: role === 'loop' ? 'none' : 'context-stroke',
        stroke: role === 'loop' ? 'context-stroke' : 'none',
        'stroke-width': 1.5,
      }));
      defs.append(marker);
    }
    defs.append(style);
    const content = el('g');
    const edgeLayer = el('g', { class: 'edges' });
    const noteLayer = el('g', { class: 'notes' });
    const nodeLayer = el('g', { class: 'nodes' });
    content.append(edgeLayer, noteLayer, nodeLayer);
    out.append(defs, content);
    host.replaceChildren(out);

    const positions = new Map(), drawn = new Map(), boxes = [], notes = [], polylines = [];
    let explicit = null;

    const finite = (values, where) => {
      if (values.some((v) => typeof v !== 'number' || !Number.isFinite(v))) {
        throw Error(`${where}: coordinates must be finite numbers`);
      }
    };
    const activate = (group, run) => {
      group.setAttribute('tabindex', '0');
      group.setAttribute('role', 'button');
      group.onclick = run;
      group.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); run(); }
      };
    };
    function shape(object) { return el('rect', {class:'shape'}); }
    function sizeOf(object, options) {
      const data=object.type==='data', extra=data?46:76;
      const box=options.width??Math.max(data?124:180,Math.min(280,width(object.title||'',15)+extra));
      const textWidth=Math.max(1,box-(data?40:66));
      const rows=wrap(object.title||'',textWidth,15);
      return {width:box,height:options.height??Math.max(data?48:78,rows.height+30),text:textWidth};
    }

    const scene = {
      svg: out, positions, drawn, boxes, notes, polylines, measure,
      nodeBox(id) {
        const p = positions.get(id);
        if (!p) throw Error(`${id}: place the node before calling nodeBox()`);
        const {x,y,width,height} = p;
        return Object.freeze({x,y,width,height,left:x-width/2,right:x+width/2,top:y-height/2,bottom:y+height/2});
      },
      node(id, x, y, options = {}) {
        const object = objectById.get(id);
        if (!object) throw Error(`Unknown object: ${id}`);
        if (positions.has(id)) throw Error(`Duplicate object: ${id}`);
        finite([x, y], id);
        const size = sizeOf(object, options);
        finite([size.width, size.height], id);
        if (size.width <= 0 || size.height <= 0) throw Error(`${id}: width and height must be positive`);
        const group = el('g', {
          class: `node role-${object.type}`, transform: `translate(${x},${y})`,
          'data-node': id, 'data-role': object.type, 'aria-label': object.title,
        });
        const node = shape(object);
        const w=size.width/2,h=size.height/2,data=object.type==='data';
        for(const [key,value] of Object.entries({x:-w,y:-h,width:size.width,height:size.height,rx:data?h:12}))node.setAttribute(key,value);
        group.append(node);
        if(data)group.append(el('circle',{class:'data-dot',cx:-w+20,cy:0,r:3.5}));
        else{
          group.append(el('rect',{class:'icon-tile',x:-w+12,y:-21,width:38,height:42,rx:8}));
          if(object.type==='resource'){
            group.dataset.resourceKind=resourceKind(object.resourceKind);
            const icon=resourceIcon(object.resourceKind);icon.setAttribute('x',-w+19);icon.setAttribute('y',-12);group.append(icon);
          }else{
            const icon=roleIcon(object.type);icon.setAttribute('x',-w+19);icon.setAttribute('y',-12);group.append(icon);
          }
        }
        if(object.detail){
          group.append(el('path',{class:'detail-hint',d:`M${size.width/2-15} ${size.height/2-18} l5 4 -5 4 Z`,'aria-hidden':'true'}));
        }
        const rows = wrap(object.title || '', size.text, 15);
        const text = el('text', {
          x: object.type==='data'?8:22, y: -(rows.height - rows.lineHeight) / 2, 'text-anchor': 'middle',
          class: 'n-title', 'font-size': 15, 'font-family': FONT,
        });
        rows.lines.forEach((row, index) => {
          const span = el('tspan', { x: object.type==='data'?8:22, dy: index ? rows.lineHeight : 0 });
          span.textContent = row;
          text.append(span);
        });
        group.append(text);
        activate(group, () => handlers.onObject?.(object, false));
        group.ondblclick = () => handlers.onObject?.(object, true);
        group.onpointerenter = event => { if(event.pointerType!=='touch')handlers.onPreview?.(object,group); };
        group.onpointerleave = () => handlers.onPreviewEnd?.();
        group.addEventListener('focus', () => handlers.onPreview?.(object,group,true));
        group.addEventListener('blur', () => handlers.onPreviewEnd?.());
        nodeLayer.append(group);
        const textBox=text.getBBox();
        text.setAttribute('y', Number(text.getAttribute('y'))-textBox.y-textBox.height/2);
        const record = {
          id, type: object.type, x, y, width: size.width, height: size.height,
          group, textWidth: rows.width, textHeight: rows.height,
        };
        positions.set(id, record);
        boxes.push(record);
        return scene;
      },
      edge(id, options = {}) {
        const relation = relationById.get(id);
        if (!relation) throw Error(`Unknown relation: ${id}`);
        if (drawn.has(id)) throw Error(`Duplicate relation: ${id}`);
        const from = positions.get(relation.from), to = positions.get(relation.to);
        if (!from || !to) throw Error(`${id}: place both endpoints before drawing the relation`);
        const sides = options.sides;
        if (!Array.isArray(sides) || sides.length !== 2) throw Error(`${id}: provide sides:[fromSide,toSide]`);
        const via = options.via || [];
        for (const point of via) {
          if (!Array.isArray(point) || point.length !== 2) throw Error(`${id}: via must be [x,y] points`);
          finite(point, id);
        }
        const hasNote = !!relation.label?.trim();
        if (hasNote && (!Array.isArray(options.noteAt) || options.noteAt.length !== 2)) {
          throw Error(`${id}: provide noteAt:[x,y] for the relation note`);
        }
        if (hasNote) finite(options.noteAt, id);
        const points = [
          inside(from, via[0] || [to.x, to.y], sides[0]),
          ...via,
          inside(to, via.at(-1) || [from.x, from.y], sides[1]),
        ];
        const line = el('path', {
          class: `edge role-${relation.type}${relation.type === 'data' ? ' ' + relation.timing : ''}`,
          'data-edge': id,
          d: options.path || rounded(points),
          'marker-end': `url(#arrow-${relation.type})`,
        });
        edgeLayer.append(line);
        for(const distance of [0,line.getTotalLength()]){const p=line.getPointAtLength(distance);edgeLayer.append(el('circle',{class:'edge-port',cx:p.x,cy:p.y,r:3}));}
        const hit = el('path', {class:'edge-hit', d:line.getAttribute('d'),
          'data-relation':id, 'aria-label':relation.label || `${from.id} → ${to.id} (${relation.type})`});
        activate(hit, () => handlers.onRelation?.(relation));
        edgeLayer.append(hit);
        if (relation.type === 'control') {
          const start=line.getPointAtLength(0);
          edgeLayer.append(el('path', {
            class: 'control-mark',
            d: `M${start.x} ${start.y - 5} l5 5 -5 5 -5 -5 Z`,
          }));
        }
        polylines.push({ id, type: relation.type, line, points });
        if (!hasNote) {
          drawn.set(id, {relation,line,group:hit,noteAt:null});
          return scene;
        }
        let maxWidth = options.noteWidth ?? 260;
        if (options.noteWidth === undefined && !options.path) {
          const [nx,ny] = options.noteAt;
          const segment = points.slice(1).map((b,i)=>[points[i],b]).find(([a,b])=>
            Math.abs(a[1]-b[1])<.01 && Math.abs(ny-a[1])<20 && nx>Math.min(a[0],b[0]) && nx<Math.max(a[0],b[0]));
          if (segment) {
            const [a,b] = segment;
            const available = 2*Math.min(nx-Math.min(a[0],b[0]),Math.max(a[0],b[0])-nx)-26;
            // Narrower than 56px usually means choosing another segment, not single-letter wrapping.
            if (available >= 56) maxWidth = Math.min(maxWidth, available);
          }
        }
        if (!Number.isFinite(maxWidth) || maxWidth <= 0) throw Error(`${id}: noteWidth must be positive`);
        const note = wrap(relation.label || '', maxWidth, 14);
        const [nx, ny] = options.noteAt;
        const w = note.width + 10, h = note.height + 6;
        const group = el('g', {
          class: 'relation-note', 'data-note': id, 'data-role': relation.type,
          transform: `translate(${nx},${ny})`, 'aria-label': relation.label,
        });
        group.append(el('rect', { class: 'note-hit', x: -w / 2, y: -h / 2, width: w, height: h, rx: 3 }));
        const text = el('text', {
          class: 'note-title', 'text-anchor': 'middle', 'font-size': 14, 'font-family': FONT,
          y: -(note.height - note.lineHeight) / 2,
        });
        note.lines.forEach((row, index) => {
          const span = el('tspan', { x: 0, dy: index ? note.lineHeight : 0 });
          span.textContent = row;
          text.append(span);
        });
        group.append(text);
        activate(group, () => handlers.onRelation?.(relation));
        group.onmouseenter = () => line.classList.add('related');
        group.onmouseleave = () => line.classList.remove('related');
        noteLayer.append(group);
        const textBox=text.getBBox();
        text.setAttribute('y', Number(text.getAttribute('y'))-textBox.y-textBox.height/2);
        drawn.set(id, { relation, line, group, noteAt: [nx, ny] });
        notes.push({ id, type: relation.type, label: relation.label || '', x: nx, y: ny, width: w, height: h, group });
        return scene;
      },
      size(w, h) {
        finite([w, h], 'size');
        if (w <= 0 || h <= 0) throw Error('size: canvas dimensions must be positive');
        explicit = [w, h];
        return scene;
      },
      finish() {
        const missing = [
          ...flow.objects.filter((o) => !positions.has(o.id)).map((o) => `object ${o.id}`),
          ...flow.relations.filter((r) => !drawn.has(r.id)).map((r) => `relation ${r.id}`),
        ];
        if (missing.length) throw Error(`drawing omitted ${missing.join(', ')}`);
        const box = content.getBBox();
        const dx = box.x < 16 ? 16 - box.x : 0, dy = box.y < 16 ? 16 - box.y : 0;
        content.setAttribute('transform', `translate(${dx},${dy})`);
        const canvasWidth = explicit?.[0] ?? Math.ceil(box.x + box.width + dx + 16);
        const canvasHeight = explicit?.[1] ?? Math.ceil(box.y + box.height + dy + 16);
        if (canvasWidth < box.x + box.width + dx || canvasHeight < box.y + box.height + dy) {
          throw Error('explicit size clips authored content');
        }
        out.setAttribute('viewBox', `0 0 ${canvasWidth} ${canvasHeight}`);
        out.setAttribute('width', canvasWidth);
        out.setAttribute('height', canvasHeight);
        return {
          svg: out,
          width: canvasWidth,
          height: canvasHeight,
          positions,
          drawn,
          geometry: {
            offset: {x:dx,y:dy},
            width: canvasWidth,
            height: canvasHeight,
            nodes: boxes.map((b) => ({
              id: b.id, kind:'node', role: b.type, x: b.x + dx, y: b.y + dy,
              width: b.width, height: b.height, textWidth: b.textWidth, textHeight: b.textHeight,
              textBoxes: [...b.group.querySelectorAll('tspan')].map(t=>{const r=t.getBBox();return {x:r.x,y:r.y,width:r.width,height:r.height};}),
              outline:'rect', iconBox: b.type!=='data'?{x:-b.width/2+12,y:-21,width:38,height:42}:null,
            })),
            notes: notes.map((n) => ({
              id: n.id, kind:'note', role: n.type, x: n.x + dx, y: n.y + dy,
              width: n.width, height: n.height,
            })),
            edges: polylines.map((p) => {
              const length=p.line.getTotalLength(), steps=Math.max(1,Math.ceil(length/4));
              const samples=Array.from({length:steps+1},(_,i)=>{
                const point=p.line.getPointAtLength(length*i/steps);return [point.x+dx,point.y+dy];
              });
              return {id:p.id,role:p.type,points:samples};
            }),
          },
        };
      },
    };
    return scene;
  }
  return { create, measure, wrap, el, resourceKinds, resourceKind, resourceIcon, roleIcon };
})();
