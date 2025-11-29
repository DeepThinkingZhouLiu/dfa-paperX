#!/usr/bin/env node
/* eslint-disable */
// ELK layout runner: reads JSON from stdin and outputs positions JSON to stdout
// Input JSON:
// {
//   semantic: {...},
//   header: {...},
//   step1: { positions: { groups:[], nodes:[], edges:[] } }
// }

// 兼容不同版本的 elkjs 导出形式
let ELKConstructor;
try {
  const elkModule = require('elkjs');
  ELKConstructor = elkModule.ELK || elkModule.default || elkModule;
} catch (e) {
  console.error('Failed to require elkjs:', e && e.message || e);
  process.exit(1);
}

function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => (data += chunk));
    process.stdin.on('end', () => resolve(data));
  });
}

function dirFromFlow(flow) {
  if (flow === 'top-to-bottom') return 'DOWN';
  if (flow === 'left-to-right') return 'RIGHT';
  if (flow === 'radial') return 'RIGHT';
  return 'RIGHT';
}

function toNumber(v, d) {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
}

function collectNodeGroupMap(step1Nodes) {
  const map = {};
  for (const n of (step1Nodes || [])) {
    const gid = n.group_id || null;
    if (!map[gid]) map[gid] = [];
    map[gid].push(n.node_id);
  }
  return map;
}

function buildElkGraph(input) {
  const semantic = input.semantic || {};
  const header = input.header || {};
  const step1 = input.step1 || {};
  const positions = step1.positions || {};
  const canvas = header.canvas || { width: 1920, height: 1080 };
  const flow = (header.layout && header.layout.flow) || 'left-to-right';
  const direction = dirFromFlow(flow);

  // ids from semantic
  const semGroups = semantic.groups || [];
  const groupChunks = {};
  for (const g of semGroups) {
    const chunks = g.chunks || [];
    if (!chunks || chunks.length === 0) {
      throw new Error(`group ${g.group_id} missing chunks in semantic layer`);
    }
    groupChunks[g.group_id] = chunks[0];
  }

  const elk = new ELKConstructor();
  const root = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.layered.nodePlacement.bk.fixedAlignment': 'BALANCED',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.edgeNode': '32',
      'elk.spacing.nodeNode': '48'
    },
    children: [],
    edges: []
  };

  const step1Nodes = positions.nodes || [];
  const step1Groups = positions.groups || [];
  const step1Edges = positions.edges || [];
  const nodeGroupMap = collectNodeGroupMap(step1Nodes);

  const groupChildren = {}; // elk compound children per group
  for (const g of step1Groups) {
    const gid = g.group_id;
    if (!gid) continue;
    groupChildren[gid] = {
      id: gid,
      children: [],
      layoutOptions: {
        'elk.padding': '[top=16,left=16,bottom=16,right=16]'
      }
    };
  }

  const elkNodesById = {};
  for (const n of step1Nodes) {
    const nid = n.node_id;
    const bbox = n.bbox || {};
    const w = toNumber(bbox.width, 160);
    const h = toNumber(bbox.height, 64);
    const elkNode = { id: nid, width: w, height: h };
    elkNodesById[nid] = elkNode;
    const gid = n.group_id || null;
    if (gid && groupChildren[gid]) {
      groupChildren[gid].children.push(elkNode);
    } else {
      root.children.push(elkNode);
    }
  }

  // push group compounds to root
  for (const gid of Object.keys(groupChildren)) {
    root.children.push(groupChildren[gid]);
  }

  // edges from semantic
  const semEdges = semantic.edges || [];
  for (const e of semEdges) {
    if (!elkNodesById[e.source] || !elkNodesById[e.target]) continue;
    root.edges.push({ id: e.edge_id || `${e.source}-${e.target}`, sources: [e.source], targets: [e.target] });
  }

  return { elk, root, canvas, flow, groupChunks };
}

async function main() {
  try {
    const raw = await readStdin();
    const input = JSON.parse(raw || '{}');
    const { elk, root, canvas, flow, groupChunks } = buildElkGraph(input);
    const result = await elk.layout(root);

    // collect abs positions
    function collect(node, absx, absy, out) {
      const x = toNumber(node.x, 0) + absx;
      const y = toNumber(node.y, 0) + absy;
      if (node.children && node.children.length) {
        // compound node treated as group
        out.groups.push({
          group_id: node.id,
          bbox: { left: Math.round(x), top: Math.round(y), width: Math.round(node.width || 400), height: Math.round(node.height || 200) },
          chunk_id: groupChunks[node.id] || '',
          title_bbox: { left: Math.round(x + 16), top: Math.round(y + 8), width: Math.round((node.width || 400) - 32), height: 40 }
        });
        for (const c of node.children) collect(c, x, y, out);
      } else {
        // simple node
        out.nodes.push({
          node_id: node.id,
          bbox: { left: Math.round(x), top: Math.round(y), width: Math.round(node.width || 160), height: Math.round(node.height || 64) },
          group_id: null,
          zindex: 1,
          ports: []
        });
      }
    }

    const out = { groups: [], nodes: [], edges: [] };
    for (const c of result.children || []) collect(c, 0, 0, out);

    // edges with orthogonal route points from elk sections
    const nodeMap = {};
    for (const n of out.nodes) nodeMap[n.node_id] = n.bbox;
    for (const e of result.edges || []) {
      const sections = e.sections || [];
      const pts = [];
      for (const s of sections) {
        if (s.startPoint) pts.push({ x: Math.round(s.startPoint.x), y: Math.round(s.startPoint.y) });
        for (const bp of (s.bendPoints || [])) pts.push({ x: Math.round(bp.x), y: Math.round(bp.y) });
        if (s.endPoint) pts.push({ x: Math.round(s.endPoint.x), y: Math.round(s.endPoint.y) });
      }
      out.edges.push({
        edge_id: e.id,
        route_points: pts,
        route_style: 'orthogonal',
        corner_radius: 0
      });
    }

    // clamp to canvas
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    const cw = toNumber(canvas.width, 1920), ch = toNumber(canvas.height, 1080);
    for (const g of out.groups) {
      const b = g.bbox; b.left = clamp(b.left, 0, cw - 1); b.top = clamp(b.top, 0, ch - 1);
      b.width = clamp(b.width, 1, cw - b.left); b.height = clamp(b.height, 1, ch - b.top);
      const tb = g.title_bbox; tb.left = clamp(tb.left, 0, cw - 1); tb.top = clamp(tb.top, 0, ch - 1);
      tb.width = clamp(tb.width, 1, cw - tb.left); tb.height = clamp(tb.height, 1, ch - tb.top);
    }
    for (const n of out.nodes) {
      const b = n.bbox; b.left = clamp(b.left, 0, cw - 1); b.top = clamp(b.top, 0, ch - 1);
      b.width = clamp(b.width, 1, cw - b.left); b.height = clamp(b.height, 1, ch - b.top);
    }
    for (const e of out.edges) {
      const pts = e.route_points || [];
      for (const p of pts) { p.x = clamp(p.x, 0, cw - 1); p.y = clamp(p.y, 0, ch - 1); }
    }

    process.stdout.write(JSON.stringify({ positions: out }));
  } catch (err) {
    console.error(String((err && err.stack) || err));
    process.exit(1);
  }
}

main();
