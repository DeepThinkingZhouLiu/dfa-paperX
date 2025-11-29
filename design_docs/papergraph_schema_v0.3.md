# 新增细化版本（对齐 v0.2 的章节格式与详细度）
# PaperGraph JSON Schema v0.3 — 端口与标注的非破坏性增强（对齐 v0.2 风格）

## 设计目标
- 在保持 v0.2 字段与语义不变的前提下，引入两项增强能力：
  - ports（连接桩）：让边连接到节点的明确桩位，提升连线控制力与渲染一致性。
  - annotations（附属标注）：为节点/边添加小型文本/符号/图标，不污染主体结构。
- 非破坏性升级：所有新增字段为可选；既有 v0.2 JSON 文档无需修改即可继续使用。

## 术语约定
- `bbox`：Bounding Box，矩形区域，结构：`{ left:number, top:number, width:number, height:number }`；单位继承自 `canvas.unit`。
- `pos`：二维点坐标，结构：`{ x:number, y:number }`；单位继承自 `canvas.unit`。
- 语义层：`nodes`/`edges`/`groups`/`chunks`/`canvas`/`grid`/`layout` 等；面向描述，不含像素级路径。
- 布局产物层：`positions`；由布局 Agent（LA）产生的几何结果，供渲染消费。

## 顶层结构
- `version`: "0.3"（建议值；若缺省，渲染/工具可按 v0.2 回退）
- 复用 v0.2 的以下字段且含义不变：
  - `canvas`, `grid`, `layout`（含 `flow`, `algorithm`）, `chunks`, `groups`, `nodes`, `edges`, `taxonomy`
- 新增/增强：
  - `nodes[].ports`（可选，布局提示）
  - `nodes[].annotations`（可选）
  - `nodes[].vlm_prompt`（可选，VLM 生图提示）
  - `edges[].source_port`, `edges[].target_port`（可选，渲染硬指令）
  - `edges[].annotations`（可选）
  - `edges[].vlm_prompt`（可选，VLM 生图提示）
  - `edges[].style`（可选，边的内联样式）
  - `positions.nodes[].ports`（可选，端口绝对坐标）
  - `layout_runtime_meta`（保持 v0.2 含义不变）

## 名词定义（继承 v0.2 并补充）
- Node（最小可绘制元素）：同 v0.2；本版本允许声明连接桩与附属标注。
- Group（语义聚合容器）：同 v0.2。
- Edge（关系连线）：同 v0.2；可引用源/目标节点的具体连接桩。
- Port（连接桩）：节点上的连接点；语义层用于期望表达，产物层提供精确坐标。
- Annotation（附属标注）：依附于节点或边的轻量标注元素（文本/符号/图标）。

## 字段新增与约定（相对 v0.2）
- 在下列对象上保留 v0.2 对 `description:string` 的要求：`groups[]`, `nodes[]`, `edges[]`。
- 新增：
  - `nodes[].ports?: PortHint[]`
  - `nodes[].annotations?: Annotation[]`
  - `nodes[].vlm_prompt?: string`
  - `edges[].source_port?: string`
  - `edges[].target_port?: string`
  - `edges[].annotations?: Annotation[]`
  - `edges[].vlm_prompt?: string`
  - `edges[].style?: EdgeInlineStyle`
  - `positions.nodes[].ports?: PortPose[]`

### PortHint（语义层提示）
- 结构：
  - `port_id: string`（必填；节点内唯一）
  - `type?: "input" | "output" | "inout"`（可选）
  - `semantics?: "data" | "grad" | "param" | "control"`（可选；与边类型语义对齐）
  - `cardinality?: "1" | "N"`（可选；端口连接基数提示，用于 LA 布局决策与边捆绑）
  - `layout_hint?: { anchor?: "top" | "bottom" | "left" | "right" | "center", offset?: { x?:number, y?:number } }`
    - `anchor`：首选锚点；软约束，LA 可根据整体路由调整。
    - `offset`：相对该锚点的小偏移；软约束。

推荐锚点的默认几何定义（供 LA/渲染器参考）：
- 设节点 `bbox = {L,T,W,H}`，`cx = L + W/2`，`cy = T + H/2`
  - `top`: `(cx, T)`
  - `bottom`: `(cx, T+H)`
  - `left`: `(L, cy)`
  - `right`: `(L+W, cy)`
  - `center`: `(cx, cy)`

### PortPose（布局产物层结果）
- 结构：
  - `port_id: string`（必填；与语义层对应）
  - `pos: { x:number, y:number }`（必填；端口绝对坐标）
  - `normal?: { x:number, y:number }`（可选；单位向量，建议指向连线出入方向）
- 要求：`pos` 应位于节点 `bbox` 的边界或内部；`normal` 不参与硬校验。

### Annotation（附属标注）
- 结构：
  - `id: string`（必填；在宿主内唯一）
  - `type: "text" | "symbol" | "icon"`（必填）
  - `content: string`（必填；当 `type="icon"` 时可为资源名/URI）
  - `layout_hint?: object`（可选；相对宿主）
    - 依附节点时建议：
      - `{ position?: "center" | "top" | "bottom" | "left" | "right" | "top-left" | "top-right" | "bottom-left" | "bottom-right", offset?: { x?:number, y?:number } }`
    - 依附边时建议：
      - `{ position_relative_to_edge?: "start" | "middle" | "end", alignment?: "above" | "below" | "left" | "right", offset?: { x?:number, y?:number } }`

## 语义层（详细规范）

### nodes（扩展）
- 基础字段同 v0.2（`node_id`, `label`, `type`, `role`, `description`, …）。
- 新增可选字段：`ports`, `annotations`, `vlm_prompt`，见上文定义。
 - 新增可选字段：`pattern?: { type: "repeat" | "conditional" | "residual" | "parallel", params?: { count?: number, expr?: string } }`
   - 用途：表达常见结构模式，便于 LA/Renderer 采取特定布局与视觉风格（如 repeat 堆叠、conditional 分支标识）。
   - 说明：`params.count` 用于重复次数提示；`params.expr` 可用于条件表达式提示（软约束）。

### edges（扩展）
- 基础字段同 v0.2（`edge_id`, `source`, `target`, `type`, `label`, `description`, …）。
- 新增可选字段：`source_port`, `target_port`, `annotations`, `vlm_prompt`, `style`。
  - 若提供 `source_port/target_port`，渲染器应优先使用；若无法从 `positions.nodes` 找到对应端口坐标，则回退到默认锚点并记录告警。
  - `style` 用于内联画笔配置，详见 EdgeInlineStyle；不改变路径几何。
 - 新增可选字段：`multiplicity?: "1:1" | "1:N" | "N:1" | "N:N"`（关系基数，用于 LA 做汇聚/广播/捆绑等布局决策）

### groups（保持）
- 同 v0.2；继续推荐提供 `title`、`layout_hint`、`description`，并允许跨 `chunks` 聚合。
 - 组内局部网格（可选增强）：`groups[].layout_hint.grid?: { rows?: number, cols?: number, gutter?: { row?: number, col?: number } }`
   - 用途：提供组内排版的行列与间距提示，支持嵌套布局需求。

## 布局产物层（LA 输出契约）
- `positions`：承载布局结果（供渲染消费）。
- `positions.groups[]`：同 v0.2
  - `{ group_id, bbox, chunk_id? }`
  - 可选扩展：`title_bbox?: bbox`（分组标题的硬坐标区域，LA 负责与节点避让；渲染器按此区域绘制标题）
- `positions.nodes[]`：v0.3 扩展
  - `{ node_id, bbox, group_id, zindex?, ports? }`
    - `ports?: PortPose[]`（当需要精确连线时建议提供）
- `positions.edges[]`：v0.3 新增（可选，边路由“传递智慧”）
  - `{ edge_id: string, route_points: Pos[] }`
    - `edge_id`：对应语义层的边 ID。
    - `route_points: Pos[]`：包含起点、所有拐点、终点的折线路径坐标（绝对坐标，单位继承自 `canvas.unit`）。
    - 要求与建议：
      - 至少包含 2 个点（起点与终点）；通常为 3 个及以上（含拐点）。
      - 起点应与源端口坐标一致（或在容差内），终点应与目标端口坐标一致（或在容差内）。
      - LA 负责避让节点 `bbox` 与分组边界；渲染器不再重复寻路，仅按点序连线。
      - 点序按路径方向依次排列；渲染器可按折线绘制，或应用平滑插值（可选）。
   - 可选补充：
     - `route_style?: "orthogonal" | "polyline" | "spline"`（路由风格提示）
     - `corner_radius?: number`（px，拐角圆角半径，适用于正交/折线风格）
     - `avoid_meta?: { avoided_nodes?: string[], avoided_groups?: string[], padding?: number }`（避让审计信息）

## 渲染与回退约定
- 未提供 `edges.source_port/target_port`：连线连接到节点默认锚点（例如依据 `layout.flow` 选择 `right/left/top/bottom`）。
- 提供端口但缺失 `positions.nodes[].ports`：
  - 渲染器回退到默认锚点；建议记录 `missing-port-pose` 告警。
- `normal` 的使用建议：
  - 当存在 `normal` 时，以其作为连线出/入方向的优先法向；否则按默认规则或路径求解器选择。
- 边路由的优先级：
  - 若提供 `positions.edges[].route_points`，渲染器应直接采用该折线路径连线（不再重新寻路）。
  - 若缺失 `route_points`，渲染器可基于端口坐标与 `normal`、`layout.flow` 简化连线；必要时自行避让（低保真）。
 - 样式与提示：
   - `edges.style` 仅用于渲染画笔与箭头配置，不改变几何路径与端口出入方向。
   - `nodes/edges` 的 `vlm_prompt` 可被下游 VLM 使用；缺省时由下游采用默认提示，不影响几何与连线逻辑。

## 校验与质量建议（非强制）
- 端口坐标校验：`positions.nodes[].ports[].pos` 位于 `bbox` 边界或内部，超出则警告。
- 端口引用校验：`edges.source_port/target_port` 能在对应 `positions.nodes[].ports` 找到；否则回退并告警。
- 边路由校验：
  - `positions.edges[].route_points.length >= 2`；首末点与端口坐标一致（容差内）。
  - 路径段应避免穿越其他节点/分组 `bbox`；如检测到交叠，提示 LA 重新求解或记录告警。
- ID 唯一性：
  - `PortHint.port_id` 在同一节点内唯一。
  - `Annotation.id` 在同一宿主（节点或边）内唯一。
- 单位一致性：`pos/bbox` 使用 `canvas.unit`。
- 数值容差建议：端口/节点/分组的几何校验建议采用默认容差 2px（工具可配置），以规避浮点与取整误差。

## 示例（整合片段）
```
{
  "version": "0.3",
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "layout": {"flow": "left-to-right", "algorithm": "elk"},
  "nodes": [
    {
      "node_id": "node3",
      "label": "Transformer Encoder",
      "description": "…",
      "ports": [
        {"port_id": "p_top",    "type": "input",  "layout_hint": {"anchor": "top"}},
        {"port_id": "p_bottom", "type": "output", "layout_hint": {"anchor": "bottom"}}
      ]
    },
    {
      "node_id": "node4",
      "label": "MLP Head",
      "description": "…",
      "ports": [{"port_id": "p_top", "type": "input"}],
      "annotations": [
        {"id": "annot_n1", "type": "symbol", "content": "⊗", "layout_hint": {"position": "center"}}
      ]
    }
  ],
  "edges": [
    {
      "edge_id": "e3",
      "source": "node3",
      "target": "node4",
      "source_port": "p_bottom",
      "target_port": "p_top",
      "description": "Encoded features pass to…",
      "annotations": [
        {
          "id": "annot_e1",
          "type": "text",
          "content": "x4",
          "layout_hint": {"position_relative_to_edge": "middle", "alignment": "above", "offset": {"x": 0, "y": -5}}
        }
      ]
    }
  ],
  "positions": {
    "nodes": [
      {
        "node_id": "node3",
        "bbox": {"left": 500, "top": 400, "width": 200, "height": 80},
        "group_id": "grp_model",
        "ports": [
          {"port_id": "p_top",    "pos": {"x": 600, "y": 400}},
          {"port_id": "p_bottom", "pos": {"x": 600, "y": 480}, "normal": {"x": 0, "y": 1}}
        ]
      },
      {
        "node_id": "node4",
        "bbox": {"left": 500, "top": 520, "width": 200, "height": 80},
        "group_id": "grp_model",
        "ports": [
          {"port_id": "p_top", "pos": {"x": 600, "y": 520}}
        ]
      }
    ]
  }
}
```

## 最小示例（完整结构）
```
{
  "version": "0.3",
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
    {
      "group_id": "grp_left",
      "title": "(a) Input Area",
      "type": "module",
      "chunks": ["chunk_0_0"],
      "layout_hint": { "arrangement": "vertical", "weight": 0.5, "area_hint": 0.5 },
      "description": "左侧区域，包含输入节点与跨组边的起点。"
    },
    {
      "group_id": "grp_right",
      "title": "(b) Processing Area",
      "type": "module",
      "chunks": ["chunk_0_1"],
      "layout_hint": {
        "arrangement": "vertical",
        "weight": 0.5,
        "area_hint": 0.5,
        "grid": { "rows": 2, "cols": 2, "gutter": { "row": 8, "col": 8 } }
      },
      "description": "右侧区域，包含处理与后续步骤两个节点。"
    }
  ],
  "nodes": [
    {
      "node_id": "node_a",
      "label": "Input",
      "type": "data",
      "role": "input",
      "description": "输入数据源。",
      "ports": [ { "port_id": "p_right", "type": "output", "layout_hint": { "anchor": "right" } } ],
      "annotations": [ { "id": "annot_n1", "type": "text", "content": "source", "layout_hint": { "position": "top-right", "offset": {"x": -8, "y": -8} } } ]
    },
    {
      "node_id": "node_b",
      "label": "Process",
      "type": "op",
      "role": "compute",
      "description": "处理模块。",
      "ports": [
        { "port_id": "p_left",   "type": "input",  "layout_hint": { "anchor": "left" } },
        { "port_id": "p_bottom", "type": "output", "layout_hint": { "anchor": "bottom" } }
      ],
      "annotations": [ { "id": "annot_n2", "type": "icon", "content": "gear", "layout_hint": { "position": "top-right", "offset": {"x": -6, "y": -6} } } ]
    },
    {
      "node_id": "node_c",
      "label": "Next",
      "type": "op",
      "role": "compute",
      "description": "后续步骤。",
      "pattern": { "type": "repeat", "params": { "count": 3 } },
      "ports": [ { "port_id": "p_top", "type": "input", "layout_hint": { "anchor": "top" } } ]
    }
  ],
  "edges": [
    {
      "edge_id": "e1",
      "source": "node_a",
      "target": "node_b",
      "type": "data",
      "description": "输入数据流向处理模块。",
      "source_port": "p_right",
      "target_port": "p_left",
      "multiplicity": "1:1",
      "annotations": [
        {
          "id": "default_label",
          "type": "text",
          "content": "flow",
          "layout_hint": { "position_relative_to_edge": "middle", "alignment": "above" }
        }
      ]
    },
    {
      "edge_id": "e2",
      "source": "node_b",
      "target": "node_c",
      "type": "data",
      "description": "处理结果进入下一步骤。",
      "source_port": "p_bottom",
      "target_port": "p_top",
      "multiplicity": "1:N"
    }
  ],
  "taxonomy": {
    "version": "0.3",
    "nodes": {
      "types": ["data", "op", "module"],
      "roles": ["input", "compute", "output"],
      "enums": { "port_semantics": ["data", "grad", "param", "control"], "port_cardinality": ["1", "N"] }
    },
    "edges": {
      "types": ["data", "control", "dependency"],
      "enums": { "multiplicity": ["1:1", "1:N", "N:1", "N:N"] }
    }
  },
  "positions": {
    "groups": [
      { "group_id": "grp_left",  "bbox": { "left": 20,  "top": 20, "width": 614, "height": 680 }, "chunk_id": "chunk_0_0", "title_bbox": { "left": 28, "top": 28, "width": 598, "height": 40 } },
      { "group_id": "grp_right", "bbox": { "left": 646, "top": 20, "width": 614, "height": 680 }, "chunk_id": "chunk_0_1", "title_bbox": { "left": 654, "top": 28, "width": 598, "height": 40 } }
    ],
    "nodes": [
      {
        "node_id": "node_a",
        "bbox": { "left": 60, "top": 280, "width": 220, "height": 120 },
        "group_id": "grp_left",
        "zindex": 1,
        "ports": [ { "port_id": "p_right", "pos": { "x": 280, "y": 340 }, "normal": { "x": 1, "y": 0 } } ]
      },
      {
        "node_id": "node_b",
        "bbox": { "left": 720, "top": 280, "width": 220, "height": 120 },
        "group_id": "grp_right",
        "zindex": 1,
        "ports": [
          { "port_id": "p_left",   "pos": { "x": 720, "y": 340 }, "normal": { "x": -1, "y": 0 } },
          { "port_id": "p_bottom", "pos": { "x": 830, "y": 400 }, "normal": { "x": 0,  "y": 1 } }
        ]
      },
      {
        "node_id": "node_c",
        "bbox": { "left": 720, "top": 460, "width": 220, "height": 120 },
        "group_id": "grp_right",
        "zindex": 1,
        "ports": [ { "port_id": "p_top", "pos": { "x": 830, "y": 460 }, "normal": { "x": 0, "y": -1 } } ]
      }
    ],
    "edges": [
      {
        "edge_id": "e1",
        "route_points": [
          { "x": 280, "y": 340 },
          { "x": 350, "y": 340 },
          { "x": 650, "y": 340 },
          { "x": 720, "y": 340 }
        ],
        "route_style": "orthogonal",
        "corner_radius": 8,
        "avoid_meta": { "avoided_nodes": ["node_a"], "avoided_groups": [], "padding": 12 }
      },
      {
        "edge_id": "e2",
        "route_points": [
          { "x": 830, "y": 400 },
          { "x": 830, "y": 430 },
          { "x": 830, "y": 460 }
        ],
        "route_style": "polyline",
        "corner_radius": 0
      }
    ]
  },
  "layout_runtime_meta": { "algorithm": "dagre", "version": "1.0", "timestamp": "2025-11-10T00:00:00Z", "notes": "v0.3 minimal but complete" }
}
```

## 语义统一与退役建议（edges.label）
- 为降低渲染复杂度与语义歧义，建议将 `edges.label` 视为“历史快捷方式”：
  - 在 v0.3 的工作流中，优先使用 `edges.annotations` 表达所有边上的文本/符号。
  - 若需要中点文本 `label: "flow"`，应规范化为：
```
{
  "edges": [
    {
      "edge_id": "e1",
      "annotations": [
        {
          "id": "default_label",
          "type": "text",
          "content": "flow",
          "layout_hint": { "position_relative_to_edge": "middle", "alignment": "above" }
        }
      ]
    }
  ]
}
```
- 兼容性：
  - `edges.label` 仍允许存在以兼容旧数据，但渲染器可选择忽略或将其在导入阶段自动规范化为 `annotations`。
  - 统一职责：渲染器只解析 `annotations` 来绘制边上的文本/符号，减少双路径逻辑。

## 与 v0.2 的兼容性
- 所有新增字段均为可选；未使用时，行为等同 v0.2。
- 端口/标注缺失不影响 LA 与渲染的主流程；仅在提供端口而缺失端口坐标时触发回退与告警。

## 变更摘要（相对 v0.2）
- 新增：`nodes[].ports`（语义提示）、`edges[].source_port/target_port`（连接到具体桩位）。
- 新增：`positions.nodes[].ports`（端口绝对坐标）。
- 新增：`positions.edges[].route_points`（边折线路径坐标；可选，用于高保真渲染）。
- 新增：`nodes[].annotations`、`edges[].annotations`（附属标注）。
- 新增：`nodes[].vlm_prompt`、`edges[].vlm_prompt`（可选，VLM 生图与风格提示）。
- 新增：`edges[].style`（可选，内联画笔样式）。
- 兼容与退役建议：`edges.label` 作为历史字段保留但不推荐；应规范化到 `annotations`。
- 顶层与既有键保持不变；非破坏性升级。

---

## 变更日志
- 2025-11-11：新增 `nodes[].vlm_prompt`、`edges[].vlm_prompt` 与 `edges[].style` 作为 v1.0 简化美学接口；不改变 v0.3 主体结构。
