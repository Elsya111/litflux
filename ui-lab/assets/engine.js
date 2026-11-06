/* LitFlux UI Lab — 共享引擎：视图索引、语义图、阅读调度、分区布局与 SVG 渲染。
   演示数据在 demo.js；本文件不含任何目标项目事实。 */
(function () {
  'use strict';

  var DATA = window.LFD_DATA;
  var NS = 'http://www.w3.org/2000/svg';
  var UID = 0;

  var SIZE = {
    process: { w: 188, h: 70 },
    decision: { w: 168, h: 96 },
    boundary: { w: 176, h: 62 },
    data: { w: 138, h: 48 },
    resource: { w: 168, h: 60 },
    provider: { w: 168, h: 60 }
  };

  var ROLE_LABEL = {
    process: '业务处理', decision: '判断', boundary: '边界',
    data: '数据', resource: '资源', provider: '组件'
  };

  var views = new Map();
  var childMap = new Map();

  function register(flow, key, title, parent, owner, wfId) {
    views.set(key, { key: key, title: title, flow: flow, parent: parent, owner: owner || null, wfId: wfId });
    if (!childMap.has(key)) childMap.set(key, []);
    (flow.nodes || []).forEach(function (n) {
      if ((n.kind || 'process') !== 'process') return;
      var childKey = key + '/' + n.id;
      childMap.get(key).push(childKey);
      if (n.detail) {
        register(n.detail, childKey, n.title, key, n, wfId);
      } else {
        views.set(childKey, { key: childKey, title: n.title, flow: null, parent: key, owner: n, wfId: wfId });
      }
    });
  }

  DATA.workflows.forEach(function (w) {
    register(w.flow, 'workflow:' + w.id, w.title, null, null, w.id);
  });

  function view(key) { return views.get(key) || null; }
  function children(key) { return (childMap.get(key) || []).slice(); }
  function crumbs(key) {
    var out = [], v = view(key);
    while (v) { out.unshift(v); v = v.parent ? view(v.parent) : null; }
    return out;
  }
  function workflowOf(key) {
    var v = view(key);
    if (!v) return null;
    for (var i = 0; i < DATA.workflows.length; i++) if (DATA.workflows[i].id === v.wfId) return DATA.workflows[i];
    return null;
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function diagram(flow) {
    var nodes = [], edges = [];
    (flow.nodes || []).forEach(function (n) {
      var role = n.kind === 'decision' ? 'decision' : n.kind === 'boundary' ? 'boundary' : 'process';
      nodes.push(Object.assign({}, n, { role: role }));
    });
    (flow.data || []).forEach(function (d) {
      nodes.push(Object.assign({}, d, { role: 'data', kind: 'data' }));
    });
    (flow.nodes || []).forEach(function (n) {
      (n.uses || []).forEach(function (u, i) {
        nodes.push(Object.assign({}, u, {
          id: '@' + n.id + '/use/' + i, role: u.kind, owner: n.id, title: u.title, text: u.text
        }));
      });
    });
    (flow.edges || []).forEach(function (e) {
      edges.push(Object.assign({}, e, { role: e.kind === 'failure' ? 'failure' : 'control' }));
    });
    (flow.links || []).forEach(function (l) {
      edges.push(Object.assign({}, l, { role: 'data' }));
    });
    (flow.nodes || []).forEach(function (n) {
      (n.uses || []).forEach(function (u, i) {
        var id = '@' + n.id + '/use/' + i;
        var resourceWrite = u.kind === 'resource' && u.mode !== 'read';
        edges.push({
          from: resourceWrite ? n.id : id,
          to: resourceWrite ? id : n.id,
          role: u.kind === 'provider' ? 'provider-edge' : 'resource-edge',
          label: u.relation, mode: u.mode, sources: u.sources
        });
      });
    });
    edges.forEach(function (e, i) { e.readKey = 'r' + i; });
    var byId = new Map();
    nodes.forEach(function (n) { byId.set(n.id, n); });
    return { nodes: nodes, edges: edges, byId: byId };
  }

  function guardOK(guard, choices) {
    if (!guard) return true;
    if (Array.isArray(guard)) return guard.some(function (g) { return guardOK(g, choices); });
    return Object.keys(guard).every(function (id) { return choices[id] === guard[id]; });
  }

  function defaults(flow) {
    var out = {};
    (flow.nodes || []).forEach(function (n) { if (n.choices && n.choices.length) out[n.id] = n.choices[0].id; });
    return out;
  }

  function plan(flow, dia, choices) {
    choices = Object.assign(defaults(flow), choices || {});
    var byId = dia.byId;
    var controls = (flow.edges || []).filter(function (e) { return !e.branch || choices[e.from] === e.branch; });
    var roots = (flow.nodes || []).filter(function (n) {
      return !(flow.edges || []).some(function (e) { return e.to === n.id; });
    });
    var controlActive = new Set(roots.map(function (n) { return n.id; }));
    var queue = Array.from(controlActive);
    for (var i = 0; i < queue.length; i++) {
      controls.forEach(function (e) {
        if (e.from === queue[i] && !controlActive.has(e.to)) { controlActive.add(e.to); queue.push(e.to); }
      });
    }

    var dataActive = new Set((flow.data || []).filter(function (d) {
      var producers = dia.edges.filter(function (e) { return e.role === 'data' && e.to === d.id; });
      return !producers.length || producers.some(function (e) {
        return controlActive.has(e.from) && guardOK(e.guard, choices);
      });
    }).map(function (d) { return d.id; }));

    var activeEdges = dia.edges.filter(function (e) {
      if (!guardOK(e.guard, choices)) return false;
      var from = byId.get(e.from), to = byId.get(e.to);
      if (e.role === 'control' || e.role === 'failure') {
        return controlActive.has(e.from) && controlActive.has(e.to) && (!e.branch || choices[e.from] === e.branch);
      }
      if (e.role === 'provider-edge' || e.role === 'resource-edge') {
        var businessSide = e.role === 'resource-edge' && e.mode !== 'read' ? e.from : e.to;
        return controlActive.has(businessSide);
      }
      return (from.role === 'data' ? dataActive.has(e.from) : controlActive.has(e.from)) &&
        (to.role === 'data' ? dataActive.has(e.to) : controlActive.has(e.to));
    });

    var active = new Set(Array.from(controlActive));
    activeEdges.forEach(function (e) { active.add(e.from); active.add(e.to); });
    var available = new Set(dia.nodes.filter(function (n) {
      return active.has(n.id) && (n.role === 'provider' || n.role === 'resource');
    }).map(function (n) { return n.id; }));
    var steps = dia.nodes.filter(function (n) { return active.has(n.id) && !available.has(n.id); });

    var dependencies = {};
    steps.forEach(function (n) {
      dependencies[n.id] = Array.from(new Set(activeEdges.filter(function (e) { return e.to === n.id; }).map(function (e) { return e.from; })));
    });

    var primary = new Map();
    activeEdges.forEach(function (e) {
      if ((e.role === 'data' || e.role === 'resource-edge') && !primary.has(e.to)) primary.set(e.to, e);
    });
    var solidKeys = new Set(Array.from(primary.values()).map(function (e) { return e.readKey; }));

    var done = new Set(available), order = [], reasons = [], last = null;
    while (order.length < steps.length) {
      var ready = steps.filter(function (n) {
        return !done.has(n.id) && dependencies[n.id].every(function (id) { return done.has(id); });
      });
      if (!ready.length) break;
      var pick = null, reason = '回溯补齐其他有效前驱', seen = new Set();
      for (var ancestor = last; ancestor && !seen.has(ancestor); ancestor = primary.get(ancestor) ? primary.get(ancestor).from : null) {
        seen.add(ancestor);
        pick = ready.filter(function (n) { return primary.has(n.id) && primary.get(n.id).from === ancestor; })[0];
        if (pick) { reason = ancestor === last ? '沿实线继续' : '回溯后沿实线继续'; break; }
      }
      if (!pick) pick = ready[0];
      done.add(pick.id); order.push(pick.id); reasons.push(reason); last = pick.id;
    }
    var blocked = steps.filter(function (n) { return !done.has(n.id); }).map(function (n) {
      return { id: n.id, missing: dependencies[n.id].filter(function (id) { return !done.has(id); }) };
    });

    return {
      active: active, available: available, controlActive: controlActive,
      edges: activeEdges, dependencies: dependencies, primary: primary, solidKeys: solidKeys,
      order: order, reasons: reasons, blocked: blocked, choices: choices
    };
  }

  function sizeOf(node) { return SIZE[node.role] || SIZE.process; }

  function layout(dia, options) {
    options = options || {};
    var dir = options.dir || 'LR';
    var pad = options.pad == null ? 32 : options.pad;
    var gapX = options.gapX == null ? 108 : options.gapX;
    var gapY = options.gapY == null ? 30 : options.gapY;
    var nodes = dia.nodes;

    var stepNodes = nodes.filter(function (n) { return n.role !== 'data' && n.role !== 'provider' && n.role !== 'resource'; });
    var rank = new Map();
    stepNodes.forEach(function (n) { rank.set(n.id, 0); });
    var controlEdges = dia.edges.filter(function (e) { return e.role === 'control' || e.role === 'failure'; });
    for (var pass = 0; pass < nodes.length + 2; pass++) {
      var changed = false;
      controlEdges.forEach(function (e) {
        if (!rank.has(e.from) || !rank.has(e.to)) return;
        if (rank.get(e.to) < rank.get(e.from) + 1) { rank.set(e.to, rank.get(e.from) + 1); changed = true; }
      });
      if (!changed) break;
    }

    nodes.forEach(function (n) {
      if (n.role === 'provider' || n.role === 'resource') { rank.set(n.id, rank.get(n.owner) || 0); return; }
      if (n.role !== 'data') return;
      var producers = dia.edges.filter(function (e) { return e.role === 'data' && e.to === n.id; });
      if (producers.length) {
        rank.set(n.id, Math.max.apply(null, producers.map(function (e) { return rank.get(e.from) || 0; })));
      } else {
        var consumers = dia.edges.filter(function (e) { return e.role === 'data' && e.from === n.id; });
        rank.set(n.id, consumers.length ? (rank.get(consumers[0].to) || 0) : 0);
      }
    });

    var index = new Map();
    nodes.forEach(function (n, i) { index.set(n.id, i); });
    var produced = new Set((dia.edges || []).filter(function (e) { return e.role === 'data'; })
      .map(function (e) { return e.to; }));
    function weight(n) {
      if (n.role === 'provider' || n.role === 'resource') return 3;
      if (n.role !== 'data') return 1;
      return produced.has(n.id) ? 2 : 0;
    }
    var columns = [];
    nodes.forEach(function (n) {
      var r = rank.get(n.id) || 0;
      if (!columns[r]) columns[r] = [];
      columns[r].push(n);
    });
    for (var r = 0; r < columns.length; r++) {
      if (!columns[r]) continue;
      columns[r].sort(function (a, b) {
        return (weight(a) - weight(b)) || ((index.get(a.id) || 0) - (index.get(b.id) || 0));
      });
    }

    var colWidths = columns.map(function (col) {
      return col ? Math.max.apply(null, col.map(function (n) { return sizeOf(n).w; })) : 0;
    });
    var colHeights = columns.map(function (col) {
      if (!col) return 0;
      return col.reduce(function (sum, n) { return sum + sizeOf(n).h; }, 0) + Math.max(0, col.length - 1) * gapY;
    });
    var maxH = Math.max.apply(null, colHeights.concat([0]));
    var totalWidth = pad * 2 + colWidths.reduce(function (a, b) { return a + b; }, 0) + Math.max(0, colWidths.length - 1) * gapX;
    var totalHeight = pad * 2 + maxH;

    var positions = new Map();
    var cursorX = pad;
    colWidths.forEach(function (w, r) {
      if (!columns[r]) { cursorX += w + gapX; return; }
      var y = pad + (maxH - colHeights[r]) / 2;
      columns[r].forEach(function (n) {
        var s = sizeOf(n);
        positions.set(n.id, { x: cursorX + w / 2, y: y + s.h / 2, w: s.w, h: s.h, column: r, node: n });
        y += s.h + gapY;
      });
      cursorX += w + gapX;
    });

    var placed = nodes.map(function (n) { return Object.assign({}, n, positions.get(n.id)); });
    var placedById = new Map(placed.map(function (n) { return [n.id, n]; }));

    var geoms = [];
    dia.edges.forEach(function (e) {
      var a = placedById.get(e.from), b = placedById.get(e.to);
      if (!a || !b) return;
      var kind = b.column > a.column ? 'forward' : b.column < a.column ? 'back' : 'same';
      var aSide, bSide;
      if (kind === 'same') {
        var down = b.y >= a.y;
        aSide = down ? 'bottom' : 'top';
        bSide = down ? 'top' : 'bottom';
      } else {
        aSide = 'right';
        bSide = kind === 'back' ? 'right' : 'left';
      }
      geoms.push({ e: e, a: a, b: b, kind: kind, aSide: aSide, bSide: bSide, so: 0, to: 0 });
    });

    var graphTop = Infinity, graphBottom = -Infinity;
    placed.forEach(function (n) {
      graphTop = Math.min(graphTop, n.y - n.h / 2);
      graphBottom = Math.max(graphBottom, n.y + n.h / 2);
    });

    geoms.forEach(function (g) {
      if (g.b.column - g.a.column <= 1) return;
      var y = g.a.y;
      var x1 = g.a.x + g.a.w / 2;
      var x2 = g.b.x - g.b.w / 2;
      var blocked = placed.some(function (n) {
        return n.column > g.a.column && n.column < g.b.column &&
          y > n.y - n.h / 2 && y < n.y + n.h / 2 &&
          n.x + n.w / 2 > x1 && n.x - n.w / 2 < x2;
      });
      if (!blocked) return;
      g.kind = 'long';
      g.side = (y < (graphTop + graphBottom) / 2) ? 'top' : 'bottom';
      g.aSide = 'right';
      g.bSide = 'right';
    });

    geoms.forEach(function (g) {
      if (g.kind !== 'same') return;
      var lo = Math.min(g.a.y, g.b.y), hi = Math.max(g.a.y, g.b.y);
      var blocked = placed.some(function (n) {
        return n.column === g.a.column && n.id !== g.a.id && n.id !== g.b.id && n.y > lo + 6 && n.y < hi - 6;
      });
      if (blocked) {
        g.kind = 'around';
        g.aSide = 'right';
        g.bSide = 'right';
      }
    });

    var sideGroups = {};
    geoms.forEach(function (g) {
      (sideGroups[g.a.id + '|' + g.aSide] = sideGroups[g.a.id + '|' + g.aSide] || []).push({ g: g, source: true, side: g.aSide });
      (sideGroups[g.b.id + '|' + g.bSide] = sideGroups[g.b.id + '|' + g.bSide] || []).push({ g: g, source: false, side: g.bSide });
    });
    Object.keys(sideGroups).forEach(function (key) {
      var list = sideGroups[key];
      var horizontalSide = list[0].side === 'left' || list[0].side === 'right';
      list.forEach(function (item, i) {
        var node = item.source ? item.g.a : item.g.b;
        var limit = horizontalSide ? node.h / 2 - 11 : node.w / 2 - 11;
        var offset = (i - (list.length - 1) / 2) * 10;
        offset = Math.max(-limit, Math.min(limit, offset));
        if (item.source) item.g.so = offset; else item.g.to = offset;
      });
    });

    var colBounds = [];
    placed.forEach(function (n) {
      var c = n.column;
      var b = colBounds[c] || (colBounds[c] = { left: Infinity, right: -Infinity });
      b.left = Math.min(b.left, n.x - n.w / 2);
      b.right = Math.max(b.right, n.x + n.w / 2);
    });

    var gapMap = {};
    var aroundCount = {};
    var sameByCol = {};
    var longTop = 0, longBottom = 0, longLane = {}, longApproach = {};
    geoms.forEach(function (g) {
      if (g.kind === 'around') {
        aroundCount[g.a.column] = (aroundCount[g.a.column] || 0) + 1;
        g.laneIndex = aroundCount[g.a.column];
      }
      if (g.kind === 'long') {
        if (g.side === 'top') g.busY = graphTop - 18 - (longTop++) * 10;
        else g.busY = graphBottom + 18 + (longBottom++) * 10;
        longLane[g.a.column] = (longLane[g.a.column] || 0) + 1;
        g.laneIndex = longLane[g.a.column];
        longApproach[g.b.column] = (longApproach[g.b.column] || 0) + 1;
        g.approachIndex = longApproach[g.b.column];
      }
      if (g.kind === 'same') {
        (sameByCol[g.a.column] = sameByCol[g.a.column] || []).push(g);
      }
      if (g.kind !== 'forward') return;
      var gap = g.b.column - 1;
      (gapMap[gap] = gapMap[gap] || []).push(g);
    });
    geoms.forEach(function (g) {
      if (g.kind === 'around') g.laneX = colBounds[g.a.column].right + 20 + (g.laneIndex - 1) * 9;
      if (g.kind === 'long') {
        g.laneX = colBounds[g.a.column].right + 16 + (g.laneIndex - 1) * 9;
        g.approachX = colBounds[g.b.column].right + 18 + (g.approachIndex - 1) * 9;
      }
    });
    Object.keys(sameByCol).forEach(function (col) {
      var list = sameByCol[col];
      var b = colBounds[col];
      var center = (b.left + b.right) / 2;
      list.forEach(function (g, i) {
        g.vx = center + (i - (list.length - 1) / 2) * 14;
      });
    });
    Object.keys(gapMap).forEach(function (gap) {
      var list = gapMap[gap];
      var left = colBounds[gap] ? colBounds[gap].right + 14 : 0;
      var right = colBounds[Number(gap) + 1] ? colBounds[Number(gap) + 1].left - 14 : left + 80;
      if (right < left + 8) right = left + 8;
      list.sort(function (x, y) { return x.a.y - y.a.y || x.b.y - y.b.y; });
      list.forEach(function (g, i) {
        g.channelX = list.length === 1 ? (left + right) / 2 : left + (i + 1) * (right - left) / (list.length + 1);
      });
    });

    var routed = geoms.map(function (g) {
      var a = g.a, b = g.b;
      if (options.ortho) {
        var ortho = orthogonal(g);
        return Object.assign({}, g.e, {
          fromNode: a, toNode: b,
          d: ortho.d, labelX: ortho.lx, labelY: ortho.ly
        });
      }
      var p0 = anchor(a, b), p1 = anchor(b, a);
      var geo = curve(p0, p1);
      var labelX = geo.mx, labelY = geo.my - 8;
      if (Math.abs(p1.x - p0.x) < 34) labelX += 54;
      return Object.assign({}, g.e, {
        fromNode: a, toNode: b,
        d: geo.d, labelX: labelX, labelY: labelY
      });
    });

    return {
      nodes: placed, byId: placedById, edges: routed,
      width: Math.round(totalWidth), height: Math.round(totalHeight),
      dir: dir, cols: colWidths.length
    };
  }

  function boundaryX(node, side, offset) {
    if (node.role !== 'decision') return side === 'left' ? node.x - node.w / 2 : node.x + node.w / 2;
    var half = node.h / 2;
    var k = Math.min(Math.abs(offset || 0), half - 8) / half;
    var inset = (node.w / 2) * k;
    return side === 'left' ? node.x - node.w / 2 + inset : node.x + node.w / 2 - inset;
  }

  function clampOffset(node, offset, vertical) {
    var limit = vertical ? node.h / 2 - 11 : node.w / 2 - 11;
    return Math.max(-limit, Math.min(limit, offset || 0));
  }

  function orthogonal(g) {
    var a = g.a, b = g.b;
    if (g.kind === 'same') {
      var down = b.y >= a.y;
      var sy = a.y + (down ? a.h / 2 : -a.h / 2);
      var ey = b.y + (down ? -b.h / 2 : b.h / 2);
      var sx = a.x + clampOffset(a, g.so, false);
      var ex = b.x + clampOffset(b, g.to, false);
      var vx = g.vx == null ? (sx + ex) / 2 : g.vx;
      return {
        d: 'M ' + r(sx) + ' ' + r(sy) + ' H ' + r(vx) + ' V ' + r(ey) + ' H ' + r(ex),
        lx: vx + 44, ly: (sy + ey) / 2 - 8
      };
    }
    if (g.kind === 'long') {
      var lsy = a.y + clampOffset(a, g.so, true);
      var lsx = a.x + a.w / 2;
      var lty = b.y + clampOffset(b, g.to, true);
      var ltr = b.x + b.w / 2;
      var topSide = g.side === 'top';
      return {
        d: 'M ' + r(lsx) + ' ' + r(lsy) + ' H ' + r(g.laneX) + ' V ' + r(g.busY) + ' H ' + r(g.approachX) + ' V ' + r(lty) + ' H ' + r(ltr),
        lx: ltr + 26, ly: lty - 8
      };
    }
    if (g.kind === 'around') {
      var asy = a.y + clampOffset(a, g.so, true);
      var aty = b.y + clampOffset(b, g.to, true);
      var asx = a.x + a.w / 2;
      var atx = b.x + b.w / 2;
      var lane = g.laneX;
      return {
        d: 'M ' + r(asx) + ' ' + r(asy) + ' H ' + r(lane) + ' V ' + r(aty) + ' H ' + r(atx),
        lx: lane + 8, ly: (asy + aty) / 2 - 8
      };
    }
    if (g.kind === 'back') {
      var bsx = a.x + a.w / 2, bsy = a.y + clampOffset(a, g.so, true);
      var bex = b.x + b.w / 2, bey = b.y + clampOffset(b, g.to, true);
      var bcx = Math.max(a.x + a.w / 2, b.x + b.w / 2) + 40;
      return {
        d: 'M ' + r(bsx) + ' ' + r(bsy) + ' H ' + r(bcx) + ' V ' + r(bey) + ' H ' + r(bex),
        lx: bcx + 8, ly: (bsy + bey) / 2
      };
    }
    var fsx = boundaryX(a, 'right', g.so);
    var fsy = a.y + clampOffset(a, g.so, true);
    var fex = boundaryX(b, 'left', g.to);
    var fey = b.y + clampOffset(b, g.to, true);
    var cx = g.channelX == null ? (fsx + fex) / 2 : g.channelX;
    if (cx < fsx + 8) cx = fsx + 8;
    if (cx > fex - 8) cx = Math.max(fsx + 8, fex - 8);
    var lx = Math.max(fsx + 24, Math.min(fex - 24, cx));
    return {
      d: 'M ' + r(fsx) + ' ' + r(fsy) + ' H ' + r(cx) + ' V ' + r(fey) + ' H ' + r(fex),
      lx: lx, ly: fey - 9
    };
  }

  function anchor(node, toward) {
    var dx = toward.x - node.x, dy = toward.y - node.y;
    if (node.role === 'decision') {
      var s = Math.min(1 / (Math.abs(dx) / (node.w / 2) + Math.abs(dy) / (node.h / 2)), 1);
      return { x: node.x + dx * s, y: node.y + dy * s };
    }
    var hw = node.w / 2, hh = node.h / 2;
    var sx = dx ? Math.abs(hw / dx) : Infinity;
    var sy = dy ? Math.abs(hh / dy) : Infinity;
    var k = Math.min(sx, sy, 1);
    return { x: node.x + dx * k, y: node.y + dy * k };
  }

  function curve(a, b) {
    var dx = b.x - a.x, dy = b.y - a.y;
    var c1, c2;
    if (Math.abs(dx) >= Math.abs(dy)) {
      c1 = { x: a.x + dx * 0.45, y: a.y };
      c2 = { x: b.x - dx * 0.45, y: b.y };
    } else {
      c1 = { x: a.x, y: a.y + dy * 0.45 };
      c2 = { x: b.x, y: b.y - dy * 0.45 };
    }
    return {
      d: 'M ' + r(a.x) + ' ' + r(a.y) + ' C ' + r(c1.x) + ' ' + r(c1.y) + ' ' + r(c2.x) + ' ' + r(c2.y) + ' ' + r(b.x) + ' ' + r(b.y),
      mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2
    };
  }

  function r(v) { return Math.round(v * 10) / 10; }

  function textWidth(text, size) {
    return Array.from(String(text)).reduce(function (sum, ch) {
      return sum + (/[\u0000-\u00ff]/.test(ch) ? size * 0.56 : size);
    }, 0);
  }

  function wrap(text, max) {
    var rows = [], row = '', units = 0;
    Array.from(String(text)).forEach(function (ch) {
      var u = /[\u0000-\u00ff]/.test(ch) ? 0.55 : 1;
      if (units + u > max && row) { rows.push(row); row = ''; units = 0; }
      row += ch; units += u;
    });
    if (row) rows.push(row);
    return rows;
  }

  function render(host, opts) {
    var dia = opts.dia, lay = opts.lay, planState = opts.plan;
    var mode = opts.mode || 'boxes';
    var radius = opts.radius == null ? 10 : opts.radius;
    var showTags = !!opts.roleTag;
    var selected = opts.selected || null;
    var cursor = opts.cursor || 0;
    var done = new Set();
    if (planState && cursor) planState.order.slice(0, cursor).forEach(function (id) { done.add(id); });
    var current = planState && cursor ? planState.order[cursor - 1] : null;
    var uid = 'g' + (++UID);

    host.textContent = '';
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + lay.width + ' ' + lay.height);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.setAttribute('class', 'lf-graph');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', '业务内部流程图');

    var defs = document.createElementNS(NS, 'defs');
    ['data', 'control', 'failure', 'provider-edge', 'resource-edge'].forEach(function (role) {
      var marker = document.createElementNS(NS, 'marker');
      marker.setAttribute('id', uid + '-' + role);
      marker.setAttribute('markerWidth', '9');
      marker.setAttribute('markerHeight', '9');
      marker.setAttribute('refX', '7');
      marker.setAttribute('refY', '4.5');
      marker.setAttribute('orient', 'auto');
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d', 'M 0 0 L 9 4.5 L 0 9 z');
      p.setAttribute('class', 'marker-fill marker-' + role);
      marker.appendChild(p);
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    lay.edges.forEach(function (e) {
      var active = planState ? planState.edges.some(function (x) { return x.readKey === e.readKey; }) : true;
      var primary = planState ? planState.solidKeys.has(e.readKey) : false;
      var path = document.createElementNS(NS, 'path');
      path.setAttribute('d', e.d);
      path.setAttribute('class', 'edge role-' + e.role + (active ? '' : ' is-dim') + (primary ? ' is-primary' : ''));
      path.setAttribute('data-edge', e.readKey);
      path.setAttribute('marker-end', 'url(#' + uid + '-' + e.role + ')');
      if (e.label) {
        var et = document.createElementNS(NS, 'title');
        et.textContent = e.label;
        path.appendChild(et);
      }
      svg.appendChild(path);

      var showLabel = e.label && opts.edgeLabels !== false &&
        (opts.edgeLabels !== 'control' || e.role === 'control' || e.role === 'failure');
      if (showLabel) {
        var tx = e.labelX, ty = e.labelY;
        var w = textWidth(e.label, 10.5) + 12;
        var g = document.createElementNS(NS, 'g');
        g.setAttribute('class', 'edge-label' + (active ? '' : ' is-dim'));
        var bg = document.createElementNS(NS, 'rect');
        bg.setAttribute('x', r(tx - w / 2));
        bg.setAttribute('y', r(ty - 10));
        bg.setAttribute('width', r(w));
        bg.setAttribute('height', '16');
        bg.setAttribute('rx', '4');
        bg.setAttribute('class', 'edge-label-bg');
        var t = document.createElementNS(NS, 'text');
        t.setAttribute('x', r(tx));
        t.setAttribute('y', r(ty + 2));
        t.setAttribute('text-anchor', 'middle');
        t.textContent = e.label;
        g.appendChild(bg); g.appendChild(t);
        svg.appendChild(g);
      }
    });

    lay.nodes.forEach(function (n) {
      var active = planState ? planState.active.has(n.id) : true;
      var isCurrent = n.id === current;
      var isDone = done.has(n.id);
      var g = document.createElementNS(NS, 'g');
      var cls = 'node role-' + n.role + (active ? '' : ' is-dim') + (isDone ? ' is-done' : '') +
        (isCurrent ? ' is-current' : '') + (n.id === selected ? ' is-selected' : '');
      g.setAttribute('class', cls);
      g.setAttribute('transform', 'translate(' + r(n.x) + ' ' + r(n.y) + ')');
      g.setAttribute('data-id', n.id);
      g.setAttribute('data-role', n.role);
      g.setAttribute('tabindex', '0');
      g.setAttribute('role', 'button');

      var title = document.createElementNS(NS, 'title');
      title.textContent = n.title + (n.text ? ' — ' + n.text : '');
      g.appendChild(title);

      var shape;
      if (n.role === 'decision') {
        shape = document.createElementNS(NS, 'polygon');
        shape.setAttribute('points', '0,' + (-n.h / 2) + ' ' + (n.w / 2) + ',0 0,' + (n.h / 2) + ' ' + (-n.w / 2) + ',0');
      } else {
        shape = document.createElementNS(NS, 'rect');
        shape.setAttribute('x', -n.w / 2);
        shape.setAttribute('y', -n.h / 2);
        shape.setAttribute('width', n.w);
        shape.setAttribute('height', n.h);
        shape.setAttribute('rx', n.role === 'data' ? n.h / 2 : radius);
      }
      shape.setAttribute('class', 'shape');
      g.appendChild(shape);

      if (n.role === 'resource') {
        var cyl = document.createElementNS(NS, 'ellipse');
        cyl.setAttribute('cx', '0');
        cyl.setAttribute('cy', r(-n.h / 2 + 7));
        cyl.setAttribute('rx', n.w / 2 - 6);
        cyl.setAttribute('ry', '6');
        cyl.setAttribute('fill', 'none');
        cyl.setAttribute('class', 'cyl');
        g.appendChild(cyl);
      }

      if (opts.corners && n.role !== 'decision') {
        var c = 9, hw = n.w / 2, hh = n.h / 2;
        var corners = document.createElementNS(NS, 'path');
        corners.setAttribute('class', 'n-corners');
        corners.setAttribute('d',
          'M ' + (-hw + c) + ' ' + (-hh) + ' H ' + (-hw) + ' V ' + (-hh + c) + ' ' +
          'M ' + (hw - c) + ' ' + (-hh) + ' H ' + hw + ' V ' + (-hh + c) + ' ' +
          'M ' + (-hw + c) + ' ' + hh + ' H ' + (-hw) + ' V ' + (hh - c) + ' ' +
          'M ' + (hw - c) + ' ' + hh + ' H ' + hw + ' V ' + (hh - c));
        g.appendChild(corners);
      }

      var size = (n.role === 'data' ? 11 : n.role === 'decision' ? 12.5 : 13) * (opts.fontScale || 1);
      var rows = wrap(n.title, Math.max(4, Math.floor((n.w - 26) / size)));
      var lineH = size + 4;
      var text = document.createElementNS(NS, 'text');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('class', 'n-title');
      text.setAttribute('font-size', size);
      rows.forEach(function (row, i) {
        var span = document.createElementNS(NS, 'tspan');
        span.setAttribute('x', '0');
        span.setAttribute('y', r((i - (rows.length - 1) / 2) * lineH + size * 0.35));
        span.textContent = row;
        text.appendChild(span);
      });
      g.appendChild(text);

      if (n.role === 'process' || n.role === 'boundary') {
        var rule = document.createElementNS(NS, 'line');
        rule.setAttribute('x1', -n.w / 2 + 14);
        rule.setAttribute('y1', r(n.h / 2 - 7));
        rule.setAttribute('x2', n.w / 2 - 14);
        rule.setAttribute('y2', r(n.h / 2 - 7));
        rule.setAttribute('class', 'n-rule');
        g.appendChild(rule);
      }

      if (showTags) {
        var tag = document.createElementNS(NS, 'text');
        tag.setAttribute('x', r(-n.w / 2 + 10));
        tag.setAttribute('y', r(-n.h / 2 + 14));
        tag.setAttribute('class', 'n-tag');
        var tags = opts.tagLabels || {};
        tag.textContent = tags[n.role] || ROLE_LABEL[n.role] || n.role;
        g.appendChild(tag);
      }

      if (n.sources && n.sources.length) {
        var dot = document.createElementNS(NS, 'circle');
        dot.setAttribute('cx', r(n.w / 2 - 9));
        dot.setAttribute('cy', r(n.h / 2 - 9));
        dot.setAttribute('r', '3');
        dot.setAttribute('class', 'source-dot');
        g.appendChild(dot);
      }

      svg.appendChild(g);
    });

    host.appendChild(svg);
    return svg;
  }

  function stats(flow) {
    var dia = diagram(flow);
    return {
      business: (flow.nodes || []).filter(function (n) { return (n.kind || 'process') === 'process'; }).length,
      decisions: (flow.nodes || []).filter(function (n) { return n.kind === 'decision'; }).length,
      data: (flow.data || []).length,
      uses: dia.nodes.filter(function (n) { return n.role === 'resource' || n.role === 'provider'; }).length,
      relations: dia.edges.length
    };
  }

  function source(refs) {
    return (refs || []).map(function (ref) { return Object.assign({ ref: ref }, DATA.sources[ref] || { lines: [], path: ref, start: 0 }); });
  }

  function fmtTime() { return new Date().toTimeString().slice(0, 5); }

  window.LFD = {
    data: DATA, meta: DATA.meta, workflows: DATA.workflows, capabilities: DATA.capabilities,
    view: view, children: children, crumbs: crumbs, workflowOf: workflowOf,
    diagram: diagram, plan: plan, layout: layout, render: render, defaults: defaults,
    stats: stats, source: source, esc: esc, roleLabel: ROLE_LABEL, fmtTime: fmtTime
  };
})();
