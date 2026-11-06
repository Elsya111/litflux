// LitFlux drawing primitives: place, measure, draw. This file never decides layout,
// line style or object roles — the project module passes everything in.
const LitFluxDrawing = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const FONT = '"Segoe UI","PingFang SC","Microsoft YaHei UI",system-ui,sans-serif';
  const LINE = { 15: 21, 14: 19 };
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const cache = new Map();

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
    return wrap(text, options.maxWidth ?? 260, options.fontSize ?? 14);
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
    if (pos.type === 'data') k = hw / Math.hypot(dx, dy);
    else if (pos.type === 'decision') k = 1 / (Math.abs(dx) / hw + Math.abs(dy) / hh);
    else k = Math.min(dx ? Math.abs(hw / dx) : Infinity, dy ? Math.abs(hh / dy) : Infinity);
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
      '.node .resource-cap{fill:none;stroke:var(--resource-line,#558c7a);stroke-width:1.1;pointer-events:none}',
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
    function shape(object) {
      if (object.type === 'data') return el('circle', { class: 'shape', r: 1 });
      if (object.type === 'decision') return el('polygon', { class: 'shape' });
      if (object.type === 'component') return el('polygon', { class: 'shape' });
      if (object.type === 'resource') return el('path', { class: 'shape' });
      return el('rect', { class: 'shape' });
    }
    function sizeOf(object, options) {
      const title = object.title || '';
      if (object.type === 'data') {
        const side = options.width ?? Math.max(96, Math.min(200, width(title, 15) + 36));
        return { width: side, height: side, text: side * 0.74 };
      }
      const box = options.width ?? Math.max(124, Math.min(248, width(title, 15) + 42));
      const rows = wrap(title, box - 24, 15);
      const height = options.height ?? Math.max(object.type === 'decision' ? 104 : 74, rows.height + 34);
      return { width: box, height, text: box - 24 };
    }

    const scene = {
      svg: out, positions, drawn, boxes, notes, polylines,
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
        if (object.type === 'data') {
          node.setAttribute('r', size.width / 2);
        } else if (object.type === 'decision') {
          node.setAttribute('points', `0,${-size.height / 2} ${size.width / 2},0 0,${size.height / 2} ${-size.width / 2},0`);
        } else if (object.type === 'component') {
          const w = size.width / 2, h = size.height / 2;
          node.setAttribute('points', `${-w + 14},${-h} ${w - 14},${-h} ${w},0 ${w - 14},${h} ${-w + 14},${h} ${-w},0`);
        } else if (object.type === 'resource') {
          const w = size.width / 2, h = size.height / 2, cap = Math.min(10, h / 3);
          node.setAttribute('d', `M${-w},${-h + cap} A${w},${cap} 0 0 1 ${w},${-h + cap} V${h - cap} A${w},${cap} 0 0 1 ${-w},${h - cap} Z`);
        } else {
          const w = size.width / 2, h = size.height / 2;
          node.setAttribute('x', -w); node.setAttribute('y', -h);
          node.setAttribute('width', size.width); node.setAttribute('height', size.height);
          node.setAttribute('rx', object.type === 'boundary' ? h : 8);
        }
        group.append(node);
        if (object.type === 'resource') {
          const w = size.width / 2, h = size.height / 2, cap = Math.min(10, h / 3);
          group.append(el('path', {
            class: 'resource-cap', d: `M${-w},${-h + cap} A${w},${cap} 0 0 0 ${w},${-h + cap}`,
          }));
        }
        const rows = wrap(object.title || '', size.text, 15);
        const text = el('text', {
          x: 0, y: -(rows.height - rows.lineHeight) / 2, 'text-anchor': 'middle',
          class: 'n-title', 'font-size': 15, 'font-family': FONT,
        });
        rows.lines.forEach((row, index) => {
          const span = el('tspan', { x: 0, dy: index ? rows.lineHeight : 0 });
          span.textContent = row;
          text.append(span);
        });
        group.append(text);
        activate(group, () => handlers.onObject?.(object, false));
        group.ondblclick = () => handlers.onObject?.(object, true);
        nodeLayer.append(group);
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
        if (!Array.isArray(options.noteAt) || options.noteAt.length !== 2) {
          throw Error(`${id}: provide noteAt:[x,y] for the relation note`);
        }
        finite(options.noteAt, id);
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
        if (relation.type === 'control') {
          edgeLayer.append(el('path', {
            class: 'control-mark',
            d: `M${points[0][0]} ${points[0][1] - 5} l5 5 -5 5 -5 -5 Z`,
          }));
        }
        const note = wrap(relation.label || '', options.noteWidth ?? 260, 14);
        const [nx, ny] = options.noteAt;
        const w = note.width + 10, h = note.height + 6;
        const group = el('g', {
          class: 'relation-note', 'data-relation': id, 'data-role': relation.type,
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
        drawn.set(id, { relation, line, group, noteAt: [nx, ny] });
        notes.push({ id, type: relation.type, label: relation.label || '', x: nx, y: ny, width: w, height: h, group });
        polylines.push({ id, type: relation.type, points });
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
            width: canvasWidth,
            height: canvasHeight,
            nodes: boxes.map((b) => ({
              id: b.id, role: b.type, x: b.x + dx, y: b.y + dy,
              width: b.width, height: b.height, textWidth: b.textWidth, textHeight: b.textHeight,
            })),
            notes: notes.map((n) => ({
              id: n.id, role: n.type, x: n.x + dx, y: n.y + dy,
              width: n.width, height: n.height,
            })),
            edges: polylines.map((p) => ({
              id: p.id, role: p.type,
              points: p.points.map(([x, y]) => [x + dx, y + dy]),
            })),
          },
        };
      },
    };
    return scene;
  }
  return { create, measure, wrap, el };
})();
