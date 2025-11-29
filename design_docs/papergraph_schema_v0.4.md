# PaperGraph JSON Schema v0.4 — 字段说明

## 术语与核心定义
- `bbox`: 矩形区域 `{ left, top, width, height }`。
- `pos`: 二维点坐标 `{ x, y }`。
- `PortHint`（语义层）：`{ port_id, type?, semantics?, cardinality?, layout_hint? }` — 节点期望暴露的连接桩及其语义提示。
- `PortPose`（布局层）：`{ port_id, pos, normal? }` — 由布局 Agent（LA）计算出的、`PortHint` 对应的精确坐标。
- `Annotation`（语义层）：`{ id, type, content, layout_hint? }` — 依附于节点或边的轻量化标注（如 "x4"、"L_base"）。

## 顶层结构
- v0.4 的 JSON 由三层加辅助层构成：
- 语义层：`canvas`, `grid`, `layout`, `chunks`, `groups`, `nodes`, `edges`, `taxonomy` — 描述图表“是什么”。
- 布局层：`positions` — 描述图表“在哪里”，包含 LA 计算的几何坐标与路径。
- 美学层：`style_sheet` — 描述图表“长什么样”，定义 VLM 风格提示与 Compositor 渲染样式。
- 辅助层：`version`, `layout_runtime_meta` — 版本号与 LA 运行元信息。

### 设计取舍：`groups` 的层级归属
- 结论：`groups` 属于语义层；其几何信息（如 `bbox/title_bbox`）属于布局层 `positions.groups`。
- 理由：
  - `groups` 表达“语义分区/模块”的意图，会影响布局，但本质是语义，不是几何事实。
  - 布局层仅承载 LA 的计算结果（坐标、路径、包围盒），确保“是什么”与“在哪里”分离，便于复现与审计。
  - 这种分层也让样式（美学层）能针对语义元素（如 group）制定统一规则，而不污染语义结构。

## 语义层（Semantic Layer）
- `canvas`: `{ width: number, height: number, unit?: "px" | "pt" }` — 画布尺寸与单位（默认 `px`）。
- `grid`: `{ rows: number, cols: number, margin?: { top, right, bottom, left }, gutter?: { row, col } }` — 全局网格与边距/栅格间距。
- `layout`: `{ flow?: "left-to-right" | "top-to-bottom" | "radial", algorithm?: "elk" | "dagre" | string }` — 布局意图与算法名。
- `chunks[]`: `{ chunk_id: string, grid_area: { row: number, col: number } }` — 网格上的语义分区（用于大图分页/分块）。
- `groups[]`: `{ group_id: string, title?: string, type?: string, chunks?: string[], layout_hint?: object, description?: string }`
  - `layout_hint?`: `{ arrangement?: "horizontal" | "vertical", grid?: { rows?: number, cols?: number, gutter?: { row?: number, col?: number } }, weight?: number, area_hint?: number }`。
  - 说明：`groups` 是语义分区；几何包围盒见 `positions.groups`。
- `nodes[]`: `{ node_id: string, label: string, type?: string, role?: string, description?: string, img_path?: string, ports?: PortHint[], annotations?: Annotation[], pattern?: object }`
  - `ports`（PortHint）：`{ port_id: string, type?: "input" | "output", semantics?: string, cardinality?: "1" | "N", layout_hint?: { anchor?: "top"|"right"|"bottom"|"left" } }`
  - `pattern?`: `{ type: "repeat" | "conditional" | string }`。
- `edges[]`: `{ edge_id: string, source: string, target: string, type?: string, description?: string, img_path?: string, source_port?: string, target_port?: string, multiplicity?: "1:1"|"1:N"|"N:1"|"N:N", annotations?: Annotation[] }`
  - `img_path?`：如边使用 VLM 资产或贴图时的路径（由下游写入）。
  - `source_port`/`target_port`：指定连接到 `PortHint.port_id`，消除连接歧义。
  - `label`：不推荐；建议退役，使用 `annotations` 统一表达边上文本。
- `taxonomy`: `{ version: string, nodes: { types: string[], roles?: string[], enums?: object }, edges: { types: string[], enums?: { multiplicity?: string[] } } }` — 语义枚举定义与版本。

## 布局层（Layout Layer — positions）
- `groups[]`: `{ group_id, bbox, chunk_id?, title_bbox? }` — `title_bbox` 为分组标题精确绘制区域。
- `nodes[]`: `{ node_id, bbox, group_id?, zindex, ports? }` — `zindex` 为必填，用于渲染层叠与层级表达；`ports: PortPose[]` 含每个端口的精确坐标。
- `edges[]`: `{ edge_id, route_points[], route_style?, corner_radius?, avoid_meta? }`
- `route_points`：`pos[]`，LA 计算的包含所有拐点的边路径（几何事实）。
- `route_style`：`"orthogonal" | "polyline" | ...`，LA 使用的路由风格提示。
- `avoid_meta`：可选，LA 的避让决策审计信息。

## 美学层（Aesthetic Layer — style_sheet）
- `globals`：`{ theme_prompt?: string, font_family?: string, palette?: object, default_node_engine?: "vlm"|"compositor" }` — 主题、调色板、默认字体等。
- `rules[]`：`{ selector: { element: "node"|"edge"|"group"|"annotation", type?: string }, properties: object, priority?: number }`。
- `properties`：
  - VLM：`vlm_style_prompt?: string`, `node_render_engine?: "vlm"|"compositor"`。
  - Compositor 画笔：`font?`, `fill_color?`, `stroke_color?`, `stroke_width?`, `line_style?`, `arrow_head?`, `corner_radius?`。
  - 变量引用：支持 `@globals.*` 形式（如 `"@globals.palette.primary"`）。

## 核心 Agent 消费约定
- 语义 Agent：只写入语义层（`nodes`, `edges`, `groups` 等）。
- 布局 Agent（LA）：只读取语义层，写入 `positions` 与 `layout_runtime_meta`。
- 美学 Agent：只读取语义层，写入 `style_sheet`。
- 渲染工作流（Compositor）：
- 绘制 Groups：用 `positions.groups` 的 `bbox/title_bbox` 与 `style_sheet` 的 `font/fill_color`。
- 绘制 Edges：优先检查 `edges[].img_path`；存在则按路径贴图/纹理，否则用 `positions.edges.route_points` 与 `style_sheet` 的 `stroke_color/arrow_head`。
- 绘制 Nodes（按 `zindex` 排序）：依据 `style_sheet.node_render_engine`。
- `vlm`（默认）：若 `nodes[].img_path` 存在，直接加载该资产并贴到 `node.bbox`；否则调用 VLM 生成资产再贴图。
- `compositor`（如 "text_box"）：Compositor 绘制含 `node.label` 的方框到 `node.bbox`。
- 绘制 Annotations：按 `annotations.layout_hint` 与 `style_sheet.font`。

## 示例（整合片段，含样式表）
```
{
  "version": "0.4",
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "grid": { "rows": 1, "cols": 1,
    "margin": { "top": 24, "right": 24, "bottom": 24, "left": 24 },
    "gutter": { "row": 0, "col": 0 } },
  "layout": {"flow": "left-to-right", "algorithm": "elk"},
  "chunks": [ { "chunk_id": "chunk_0_0", "grid_area": { "row": 0, "col": 0 } } ],
  "groups": [
    { "group_id": "grp_model", "title": "Model Block", "type": "module", "chunks": ["chunk_0_0"],
      "layout_hint": { "arrangement": "vertical" },
      "description": "模型相关节点的语义分组" }
  ],
  "nodes": [
    { "node_id": "node3", "label": "Transformer Encoder", "type": "op", "role": "compute",
      "description": "编码器模块。", "img_path": "assets/node3.png", "ports": [
      {"port_id": "p_top", "type": "input",  "layout_hint": {"anchor": "top"}},
      {"port_id": "p_bottom", "type": "output", "layout_hint": {"anchor": "bottom"}}
    ]},
    { "node_id": "node4", "label": "MLP Head", "type": "op", "role": "compute",
      "description": "MLP 头部。", "img_path": "assets/node4.png", "ports": [
      {"port_id": "p_top", "type": "input"}
    ], "annotations": [
      {"id": "annot_n1", "type": "symbol", "content": "⊗", "layout_hint": {"position": "center"}}
    ]}
  ],
  "edges": [
    {
      "edge_id": "e3", "source": "node3", "target": "node4", "img_path": "assets/edge_e3.png",
      "type": "data", "source_port": "p_bottom", "target_port": "p_top",
      "description": "编码特征传入 MLP。", "multiplicity": "1:1",
      "annotations": [
        {"id": "annot_e1", "type": "text", "content": "x4",
         "layout_hint": {"position_relative_to_edge": "middle", "alignment": "above", "offset": {"x": 0, "y": -5}}}
      ]
    }
  ],
  "taxonomy": {
    "version": "0.4",
    "nodes": { "types": ["data", "op", "module"], "roles": ["input", "compute", "output"],
      "enums": { "port_semantics": ["data", "grad", "param", "control"], "port_cardinality": ["1", "N"] } },
    "edges": { "types": ["data", "control", "dependency"], "enums": { "multiplicity": ["1:1", "1:N", "N:1", "N:N"] } }
  },
  "positions": {
    "groups": [
      { "group_id": "grp_model", "bbox": {"left": 40, "top": 40, "width": 1840, "height": 1000}, "chunk_id": "chunk_0_0",
        "title_bbox": {"left": 56, "top": 56, "width": 1808, "height": 44} }
    ],
    "nodes": [
      { "node_id": "node3", "bbox": {"left": 500, "top": 400, "width": 200, "height": 80}, "group_id": "grp_model", "zindex": 1,
        "ports": [
          {"port_id": "p_top",    "pos": {"x": 600, "y": 400}},
          {"port_id": "p_bottom", "pos": {"x": 600, "y": 480}, "normal": {"x": 0, "y": 1}}
        ]
      },
      { "node_id": "node4", "bbox": {"left": 500, "top": 520, "width": 200, "height": 80}, "group_id": "grp_model", "zindex": 1,
        "ports": [ {"port_id": "p_top", "pos": {"x": 600, "y": 520}} ]
      }
    ],
    "edges": [
      { "edge_id": "e3", "route_points": [ {"x": 600, "y": 480}, {"x": 600, "y": 520} ], "route_style": "polyline", "corner_radius": 0 }
    ]
  },
  "style_sheet": {
    "version": "1.0",
    "globals": {
      "theme_prompt": "一个专业的、学术风格的、简约的图表",
      "font_family": "Inter, sans-serif",
      "palette": { "primary": "#0A74FF" },
      "default_node_engine": "vlm"
    },
    "rules": [
      { "selector": { "element": "node", "type": "data" },
        "properties": { "vlm_style_prompt": "一个蓝色的3D圆柱体，代表数据存储，高光，透明背景" },
        "priority": 10 },
      { "selector": { "element": "node", "type": "text_box" },
        "properties": { "node_render_engine": "compositor",
          "font": { "family": "@globals.font_family", "size": 14, "weight": "400", "color": "#111111" },
          "fill_color": "#FFFFFF", "stroke_color": "#AAAAAA", "stroke_width": 1, "corner_radius": 4 } },
      { "selector": { "element": "edge", "type": "data" },
        "properties": { "stroke_color": "@globals.palette.primary", "stroke_width": 2, "line_style": "solid", "arrow_head": "triangle_filled" } },
      { "selector": { "element": "group" },
        "properties": { "fill_color": "#F8F9FA80", "stroke_color": "#E0E0E0", "stroke_width": 1, "line_style": "dashed", "corner_radius": 8,
          "font": { "family": "@globals.font_family", "size": 16, "weight": "700", "color": "#111111" } } },
      { "selector": { "element": "annotation", "type": "text" },
        "properties": { "font": { "family": "@globals.font_family", "size": 12, "color": "#333333", "weight": "500" } } }
    ]
  },
  "layout_runtime_meta": { "algorithm": "elk", "version": "1.0", "timestamp": "2025-11-12T00:00:00Z" }
}
```

## 最小示例（完整结构）
```
{
  "version": "0.4",
  "canvas": { "width": 1280, "height": 720, "unit": "px" },
  "grid": {
    "rows": 1,
    "cols": 2,
    "margin": { "top": 20, "right": 20, "bottom": 20, "left": 20 },
    "gutter": { "row": 0, "col": 12 }
  },
  "layout": { "flow": "left-to-right", "algorithm": "dagre" },
  "chunks": [
    { "chunk_id": "chunk_0_0", "grid_area": { "row": 0, "col": 0 } },
    { "chunk_id": "chunk_0_1", "grid_area": { "row": 0, "col": 1 } }
  ],
  "groups": [
    { "group_id": "grp_input", "title": "(a) Input Area", "type": "module", "chunks": ["chunk_0_0"],
      "layout_hint": { "arrangement": "vertical", "weight": 0.5, "area_hint": 0.5 },
      "description": "左侧区域，包含输入节点。" },
    { "group_id": "grp_right", "title": "(b) Processing Area", "type": "module", "chunks": ["chunk_0_1"],
      "layout_hint": { "arrangement": "vertical", "weight": 0.5, "area_hint": 0.5 },
      "description": "右侧区域，包含处理节点。" }
  ],
  "nodes": [
    { "node_id": "node_a", "label": "Input", "type": "data", "role": "input", "description": "输入数据源。", "img_path": "assets/node_a.png",
      "ports": [ { "port_id": "p_right", "type": "output", "layout_hint": { "anchor": "right" } } ],
      "annotations": [ { "id": "annot_n1", "type": "text", "content": "source", "layout_hint": { "position": "top-right", "offset": {"x": -8, "y": -8} } } ] },
    { "node_id": "node_b", "label": "Process", "type": "op", "role": "compute", "description": "处理模块。", "img_path": "assets/node_b.png",
      "ports": [ { "port_id": "p_left", "type": "input", "layout_hint": { "anchor": "left" } } ] }
  ],
  "edges": [
    { "edge_id": "e1", "source": "node_a", "target": "node_b", "type": "data", "img_path": "assets/edge_e1.png",
      "description": "输入数据流向处理模块。", "source_port": "p_right", "target_port": "p_left",
      "multiplicity": "1:1",
      "annotations": [ { "id": "default_label", "type": "text", "content": "flow",
        "layout_hint": { "position_relative_to_edge": "middle", "alignment": "above" } } ] }
  ],
  "taxonomy": {
    "version": "0.4",
    "nodes": { "types": ["data", "op", "module"], "roles": ["input", "compute", "output"],
      "enums": { "port_semantics": ["data", "grad", "param", "control"], "port_cardinality": ["1", "N"] } },
    "edges": { "types": ["data", "control", "dependency"], "enums": { "multiplicity": ["1:1", "1:N", "N:1", "N:N"] } }
  },
  "positions": {
    "groups": [
      { "group_id": "grp_input",  "bbox": { "left": 20,  "top": 20, "width": 614, "height": 680 }, "chunk_id": "chunk_0_0",
        "title_bbox": { "left": 28, "top": 28, "width": 598, "height": 40 } },
      { "group_id": "grp_right", "bbox": { "left": 646, "top": 20, "width": 614, "height": 680 }, "chunk_id": "chunk_0_1",
        "title_bbox": { "left": 654, "top": 28, "width": 598, "height": 40 } }
    ],
    "nodes": [
      { "node_id": "node_a", "bbox": { "left": 60, "top": 280, "width": 220, "height": 120 }, "group_id": "grp_input", "zindex": 1,
        "ports": [ { "port_id": "p_right", "pos": { "x": 280, "y": 340 }, "normal": { "x": 1, "y": 0 } } ] },
      { "node_id": "node_b", "bbox": { "left": 720, "top": 280, "width": 220, "height": 120 }, "group_id": "grp_right", "zindex": 1,
        "ports": [ { "port_id": "p_left", "pos": { "x": 720, "y": 340 }, "normal": { "x": -1, "y": 0 } } ] }
    ],
    "edges": [
      { "edge_id": "e1", "route_points": [ { "x": 280, "y": 340 }, { "x": 720, "y": 340 } ],
        "route_style": "orthogonal", "corner_radius": 8 }
    ]
  },
  "style_sheet": {
    "version": "1.0",
    "globals": { "theme_prompt": "一个专业的、学术风格的、简约的图表样式", "font_family": "Inter, sans-serif", "palette": { "primary": "#0A74FF" }, "default_node_engine": "vlm" },
    "rules": [
      { "selector": { "element": "node", "type": "data" },
        "properties": { "vlm_style_prompt": "一个蓝色的3D圆柱体，代表数据存储，高光，透明背景" } },
      { "selector": { "element": "node", "type": "text_box" },
        "properties": { "node_render_engine": "compositor",
          "font": { "family": "@globals.font_family", "size": 14, "weight": "400", "color": "#111111" },
          "fill_color": "#FFFFFF", "stroke_color": "#AAAAAA", "stroke_width": 1, "corner_radius": 4 } },
      { "selector": { "element": "edge", "type": "data" },
        "properties": { "stroke_color": "@globals.palette.primary", "stroke_width": 2, "line_style": "solid", "arrow_head": "triangle_filled" } },
      { "selector": { "element": "group" },
        "properties": { "fill_color": "#F8F9FA80", "stroke_color": "#E0E0E0", "stroke_width": 1, "line_style": "dashed", "corner_radius": 8,
          "font": { "family": "@globals.font_family", "size": 16, "weight": "700", "color": "#111111" } } },
      { "selector": { "element": "annotation", "type": "text" },
        "properties": { "font": { "family": "@globals.font_family", "size": 12, "color": "#333333", "weight": "500" } } }
    ]
  },
  "layout_runtime_meta": { "algorithm": "dagre", "version": "1.0", "timestamp": "2025-11-12T00:00:00Z", "notes": "v0.4 adds style_sheet" }
}
```

## 语义统一与退役建议（edges.label）
- 为降低渲染复杂度与语义歧义，继续建议将 `edges.label` 视为“历史快捷方式”：
  - 在 v0.4 的工作流中，优先使用 `edges.annotations` 表达所有边上的文本/符号。
  - 加载器可在导入阶段自动规范化 `edges.label` → `annotations`。

## 与 v0.3 的兼容性
- 所有新增字段（如 `nodes[].img_path`, `edges[].img_path`）均为可选；未提供 `style_sheet` 时，行为等同 v0.3。
- 自 v0.4 起，`positions.nodes[].zindex` 为必填；为兼容旧数据，加载器可在导入阶段对缺省 `zindex` 回填默认值 `1`。
- 存在 `style_sheet` 时：样式优先从样式表解析，覆盖内联样式与默认。
- 兼容字段：`nodes[].vlm_prompt`、`edges[].vlm_prompt`、`edges[].style` 保留以兼容旧数据；不推荐在新产物中继续使用。

## 变更摘要（相对 v0.3）
- 新增：顶层 `style_sheet`（美学层），含 `globals` 与 `rules`、可选 `themes` 与 `priority`。
- 新增：样式优先级与变量引用约定，统一美学消费路径（PTA/IGA/Compositor）。
- 保留：v0.3 的语义与布局字段不变；所有几何仍由 `positions` 决定。
- 兼容与退役建议：保留内联美学字段但标注为兼容路径；推荐迁移至样式表。

---

## 变更日志
- 2025-11-12：新增顶层 `style_sheet`；对齐 v0.3 文档结构，补充渲染与回退约定与示例。
