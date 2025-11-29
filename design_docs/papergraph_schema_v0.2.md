# PaperGraph JSON Schema v0.2 — 布局产物层与语义层增强（不含渲染层）

## 设计目标
- 在保持 v0.1 语义与布局提示不变的前提下，引入“布局产物层”以承载坐标信息（由 LA 产生），并增强组级提示字段（权重/面积/顺序）。
- 不引入容器树细化；不考虑渲染层、溯源、评估与质量字段。
- 边的折线路径坐标不落盘，交由求解器在渲染时计算。

## 术语约定
- `bbox`：Bounding Box，表示一个矩形区域的坐标与尺寸，统一结构为：
  - `{ "left": number, "top": number, "width": number, "height": number }`
  - 所有数值单位继承自 `canvas.unit`（例如 `px` 或 `inch`）。

## 名词定义（v0.2）
- Node（最小可绘制元素）：
  - 每个 node 对应下游 VLM 需要生成的一个独立图形/图标/形状（可包含文字标签）。
  - node 不作为容器使用；模块/阶段的聚合由 group 表达。
- Group（语义聚合容器）：
  - 作为节点的语义与空间聚合单元，可跨一个或多个 chunk（按 v0.1 定义）。
  - 负责宏观分区与阅读组织；不直接决定节点的具体形状/配色（渲染层不在本版本范围）。
- Edge（关系连线）：
  - 描述节点间的数据/控制/依赖/梯度等关系，供渲染端选取合适箭头与线型；折线路径坐标不落盘。
- Positions（布局产物层，可选）：
  - 由布局求解（LA）输出，提供 groups/nodes 的 `bbox`；缺失时可回退到 v0.1 的布局提示再求解。

## 顶层结构
- `version`: "0.2"
- 复用 v0.1 的以下字段且含义不变：
  - `canvas`, `grid`, `layout`（含 `flow`, `algorithm`）, `chunks`, `groups`, `nodes`, `edges`, `taxonomy`
- 新增：`positions`（布局产物层，LA 输出）与 `layout_runtime_meta`（可选元信息）

### 字段新增与约定（v0.2 相对 v0.1）
- 在下列对象上新增并要求提供 `description: string`（用于构成 VLM 生图的 prompt 主体）：
  - `groups[].description`（必填）
  - `nodes[].description`（必填）
  - `edges[].description`（必填）
- 在分组上新增可选标题：
  - `groups[].title`（可选）：用于区块标题文案（便于下游在该区域渲染标题文字）。

## 布局产物层（LA 输出契约）
- `positions`: 承载布局结果，供后续渲染器消费；不作为 v0.1 的输入。
  - `groups`: 数组。每项：
    - `{ "group_id": string, "bbox": bbox, "chunk_id"?: string }`
  - `nodes`: 数组（可选）。每项：
    - `{ "node_id": string, "bbox": bbox, "group_id": string, "zindex"?: number }`
  - 注：不包含 `edges` 的折线路径（`route_points`）；由渲染侧或求解器在使用时计算。
- `layout_runtime_meta`（可选）：
  - `{ "algorithm": string, "version"?: string, "timestamp"?: string, "notes"?: string }`

## 组级布局提示增强（软约束）
- 在 v0.1 的 `groups[].layout_hint` 基础上，新增可选字段（均为软约束）：
  - `weight`: 0–1，表示该组的相对权重（综合文本/图像的抽象提示；不直接绑定面积）。
  - `area_hint`: 0–1，期望占用面积比例的提示（LA 可参考，但不作为硬校验）。
- `nodes` 层面不新增 `weight`；保留 v0.1 的 `size_hint` 作为组内轻量大小提示。

## 说明与建议
- `weight/area_hint` 为提示字段，不参与硬校验。
- `chunk_id` 用于校验 `bbox` 是否位于对应块的几何范围内，推荐提供；也可由布局求解器在输出阶段补齐。
- `description` 为三类对象的必填字段，但本版本不提供校验规则与默认生成策略；后续会由专门的 Agent 强化生成。

## 校验建议（当 `positions` 存在时）
- `bbox.width > 0` 且 `bbox.height > 0`，所有数值为有限正数。
- 若提供 `chunk_id`，`bbox` 应落在该 `chunk` 所覆盖的几何范围内（允许边界微小浮动）。
- 组与组、节点与节点之间应避免大面积重叠；允许细微边界重叠用于对齐与视觉微调。
- `weight/area_hint/rank` 为提示字段，不参与硬校验。

## 兼容性策略
- v0.1 的 JSON 仍然有效；v0.2 的新增字段均为可选。
- 渲染层、溯源（`provenance`）、评估与质量（`evaluation`）、`nodes.ports` 暂不纳入 v0.2。

## 最小示例（含布局产物层）
```json
{
  "version": "0.2",
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "grid": {"rows": 3, "cols": 2, "margin": {"top": 20, "right": 20, "bottom": 20, "left": 20}, "gutter": {"row": 10, "col": 10}},
  "layout": {"flow": "left-to-right", "algorithm": "dagre"},
  "chunks": [
    {"chunk_id": "chunk_0_0", "grid_area": {"row": 0, "col": 0}},
    {"chunk_id": "chunk_1_0", "grid_area": {"row": 1, "col": 0, "colspan": 2}},
    {"chunk_id": "chunk_2_0", "grid_area": {"row": 2, "col": 0}}
  ],
  "groups": [
    {"group_id": "grp_input", "label": "Input Processing", "title": "Input & Preprocess", "type": "stage", "chunks": ["chunk_0_0"], "layout_hint": {"arrangement": "horizontal"}, "description": "Input preprocessing section containing data ingestion and tokenization."},
    {"group_id": "grp_model", "label": "Core Model", "type": "module", "chunks": ["chunk_1_0"], "layout_hint": {"arrangement": "horizontal", "weight": 0.6, "area_hint": 0.5}, "description": "Core encoder and head modules for main processing."},
    {"group_id": "grp_output", "label": "Output & Loss", "type": "stage", "chunks": ["chunk_2_0"], "layout_hint": {"arrangement": "horizontal"}, "description": "Output probabilities and supervision signals (loss)."}
  ],
  "nodes": [
    {"node_id": "node1", "label": "Input Data", "type": "data", "group": "grp_input", "role": "input", "description": "Raw input data element entering the pipeline."},
    {"node_id": "node2", "label": "Tokenizer", "type": "preprocess", "group": "grp_input", "role": "process", "description": "Tokenization step converting raw text into token IDs."},
    {"node_id": "node3", "label": "Transformer Encoder", "type": "layer", "group": "grp_model", "role": "process", "size_hint": "large", "description": "Multi-layer encoder producing contextual representations."},
    {"node_id": "node4", "label": "MLP Head", "type": "layer", "group": "grp_model", "role": "process", "description": "Projection head mapping features to logits."},
    {"node_id": "node5", "label": "Softmax Output", "type": "op", "group": "grp_output", "role": "output", "description": "Softmax operation turning logits into probabilities."},
    {"node_id": "node6", "label": "Cross-Entropy Loss", "type": "loss", "group": "grp_output", "role": "output", "description": "Supervision signal computed with cross-entropy criterion."}
  ],
  "edges": [
    {"edge_id": "e1", "source": "node1", "target": "node2", "type": "data", "route_hint": "straight", "description": "Data flows from raw input to tokenization."},
    {"edge_id": "e2", "source": "node2", "target": "node3", "type": "data", "route_hint": "straight", "description": "Token IDs are fed into the encoder."},
    {"edge_id": "e3", "source": "node3", "target": "node4", "type": "data", "route_hint": "straight", "description": "Encoded features pass to the projection head."},
    {"edge_id": "e4", "source": "node4", "target": "node5", "type": "data", "route_hint": "orthogonal", "direction_hint": "down", "description": "Logits are converted to probabilities."},
    {"edge_id": "e5", "source": "node5", "target": "node6", "type": "dependency", "route_hint": "straight", "description": "Predictions are supervised by cross-entropy loss."}
  ],
  "positions": {
    "groups": [
      {"group_id": "grp_input", "bbox": {"left": 40, "top": 40, "width": 440, "height": 280}, "chunk_id": "chunk_0_0"},
      {"group_id": "grp_model", "bbox": {"left": 40, "top": 380, "width": 1840, "height": 320}, "chunk_id": "chunk_1_0"},
      {"group_id": "grp_output", "bbox": {"left": 40, "top": 740, "width": 440, "height": 280}, "chunk_id": "chunk_2_0"}
    ],
    "nodes": [
      {"node_id": "node1", "bbox": {"left": 60, "top": 60, "width": 200, "height": 120}, "group_id": "grp_input"},
      {"node_id": "node2", "bbox": {"left": 280, "top": 60, "width": 180, "height": 120}, "group_id": "grp_input"}
    ]
  },
  "layout_runtime_meta": {"algorithm": "dagre", "version": "1.0"}
}
```

## 说明
- 本 v0.2 仅定义新增字段的数据契约与校验建议；不规定具体布局求解算法或实现细节。
- 若未提供 `positions`，消费方可退化为使用 v0.1 的布局提示进行默认渲染或后续求解。
