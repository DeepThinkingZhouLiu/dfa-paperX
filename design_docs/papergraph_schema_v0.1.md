# PaperGraph JSON Schema v0.1 - 粃粒度最小版（去冗余）

## 设计原则
1. 单一事实源：
   - 节点归属只以 `nodes[].group` 为准。
   - 组与空间关系只以 `groups[].chunks` 为准（组跨多个 chunk）。
   - 所有索引（如 group→nodes、chunk→nodes、node→edges）均为运行时派生，不落盘。
2. 约束性布局：只提供语义化流向与提示，不给绝对坐标。
3. 渐进式细化：当前为粗粒度；v0.2 扩展视觉描述与渲染层。
4. 简化一致：移除会造成双重来源的字段，避免状态漂移。

## JSON Schema v0.1（建议结构）

```json
{
  "version": "0.1",
  "canvas": {
    "width": 1920,
    "height": 1080,
    "unit": "px"
  },
  "grid": {
    "rows": 3,
    "cols": 2,
    "margin": {"top": 20, "right": 20, "bottom": 20, "left": 20},
    "gutter": {"row": 10, "col": 10}
  },
  "layout": {
    "flow": "left-to-right",
    "algorithm": "dagre",
    "hints": {
      "direction_overrides": {}
    }
  },
  "chunks": [
    {"chunk_id": "chunk_0_0", "grid_area": {"row": 0, "col": 0, "rowspan": 1, "colspan": 1}, "description": "左上角区域"},
    {"chunk_id": "chunk_1_0", "grid_area": {"row": 1, "col": 0, "rowspan": 1, "colspan": 2}, "description": "中部横向区域"},
    {"chunk_id": "chunk_2_0", "grid_area": {"row": 2, "col": 0, "rowspan": 1, "colspan": 1}, "description": "左下角区域"}
  ],
  "groups": [
    {
      "group_id": "grp_input",
      "label": "Input Processing",
      "type": "stage",
      "chunks": ["chunk_0_0"],
      "layout_hint": {"arrangement": "horizontal", "order": ["node1", "node2"]},
      "description": "输入处理阶段"
    },
    {
      "group_id": "grp_middle",
      "label": "Core Model",
      "type": "module",
      "chunks": ["chunk_1_0"],
      "layout_hint": {"arrangement": "horizontal", "order": ["node3", "node4"]},
      "description": "核心模型，占据第二行整行"
    },
    {
      "group_id": "grp_output",
      "label": "Output & Loss",
      "type": "stage",
      "chunks": ["chunk_2_0"],
      "layout_hint": {"arrangement": "horizontal", "order": ["node5", "node6"]},
      "description": "输出和损失计算"
    }
  ],
  "nodes": [
    {"node_id": "node1", "label": "Input Data", "type": "data", "group": "grp_input", "role": "input", "size_hint": "medium", "description": "原始输入数据"},
    {"node_id": "node2", "label": "Tokenizer", "type": "preprocess", "group": "grp_input", "role": "process", "description": "分词与编码"},
    {"node_id": "node3", "label": "Transformer Encoder", "type": "layer", "group": "grp_middle", "role": "process", "size_hint": "large", "ports": [{"id": "p_left", "side": "left"}, {"id": "p_right", "side": "right"}], "description": "编码器主干网络"},
    {"node_id": "node4", "label": "MLP Head", "type": "layer", "group": "grp_middle", "role": "process", "description": "输出头部"},
    {"node_id": "node5", "label": "Softmax Output", "type": "op", "group": "grp_output", "role": "output", "description": "概率输出"},
    {"node_id": "node6", "label": "Cross-Entropy Loss", "type": "loss", "group": "grp_output", "role": "output", "placement_hint": {"align": "right"}, "description": "交叉熵损失"}
  ],
  "edges": [
    {"edge_id": "e1", "source": "node1", "target": "node2", "type": "data", "route_hint": "straight", "direction_hint": "right", "description": "数据流"},
    {"edge_id": "e2", "source": "node2", "target": "node3", "type": "data", "route_hint": "straight", "target_port": "p_left", "description": "进入编码器左侧"},
    {"edge_id": "e3", "source": "node3", "target": "node4", "type": "data", "route_hint": "straight", "source_port": "p_right", "description": "编码器到MLP"},
    {"edge_id": "e4", "source": "node4", "target": "node5", "type": "data", "route_hint": "orthogonal", "direction_hint": "down", "description": "输出箭头正交下移"},
    {"edge_id": "e5", "source": "node5", "target": "node6", "type": "dependency", "route_hint": "straight", "description": "输出到损失"}
  ],
  "taxonomy": {
    "node_type": ["data", "module", "layer", "loss", "metric", "op", "dataset", "preprocess", "postprocess"],
    "node_role": ["input", "process", "output", "aux", "param", "note"],
    "edge_type": ["data", "control", "grad", "param", "dependency"],
    "group_type": ["stage", "module", "repeat", "conditional"],
    "edges_route_hint": ["straight", "orthogonal", "curve"],
    "edges_direction_hint": ["left", "right", "up", "down"],
    "groups_layout_arrangement": ["horizontal", "vertical"],
    "nodes_size_hint": ["small", "medium", "large"],
    "ports_side": ["left", "right", "top", "bottom"]
  }
}
```

## 后续迭代计划（v0.2 预告）

- 引入权重/重要度/面积提示（软约束，不含坐标）
  - 在 `groups[].layout_hint` 中增加：
    - `weight`: 0–1，表示该组在版面中的相对权重（文本/图像综合的抽象提示）。
    - `area_hint`: 0–1，表示期望占用面积比例的软提示，用于布局分配。
  - 保留 `nodes[].size_hint` 作为组内元素的轻量大小提示，但不对应绝对尺寸。

- 引入布局产物层（LA 输出，非 v0.1 字段）
  - 约定布局求解（LA）产物以“安排列表”形式输出，例如：
    - `positions` 或 `arrangements`: `[{id, x, y, width, height, type}]`。
  - 单位继承 `canvas.unit`；v0.1 不落盘坐标信息，坐标在 v0.2 再考虑并以 LA 输出为准。

- 引入渲染指针（非 v0.1 字段）
  - 增加 `render.theme_id` 指向外部主题配置（YAML/样式库）。
  - 颜色/字体/配色等风格信息在外部维护，实现语义/布局/渲染的三层解耦。

- 暂不纳入的项（当前阶段不考虑，后续评估）
  - 容器树的进一步细化（如多层 Panel/子块）暂不采纳。
  - 布局求解器的具体策略与可视化调试（如边框可视化）暂不考虑。
  - `nodes.ports`（端口/侧向布线提示）暂不纳入最小集。
  - `chunk`/`block` 等命名不强制统一，由具体实现层映射处理。

- 坐标信息规划
  - v0.1 不包含绝对坐标信息；
  - v0.2 再评估并通过 LA 的“安排列表”统一输出坐标，供渲染器消费。

## 字段说明（v0.1 最小集，含取值含义）

### 顶层字段

#### `version`
- 含义: Schema 的版本号，用于区分不同迭代版本。
- 类型: string，必填。
- 取值: 当前为 "0.1"。

#### `canvas`
- 含义: 画布的整体尺寸与单位设定。
- 类型: object，必填。
- 字段及取值:
  - `width`: number，画布宽度，单位由 `unit` 指定（推荐使用像素）。
  - `height`: number，画布高度，单位由 `unit` 指定。
  - `unit`: string，单位。当前阶段推荐 "px"；将来可扩展为 "mm"、"pt" 等。

#### `grid`
- 含义: 画布上的栅格系统，用于 chunk 的定位与跨度。
- 类型: object，必填。
- 字段及取值:
  - `rows`: number，总行数（正整数，0-based 索引到 `row`）。
  - `cols`: number，总列数（正整数，0-based 索引到 `col`）。
  - `margin`: object，画布四周外边距，单位同 `canvas.unit`。
    - `{top, right, bottom, left}` 各为 number。
  - `gutter`: object，栅格之间的行/列间距，单位同 `canvas.unit`。
    - `{row, col}` 各为 number。

#### `layout`
- 含义: 全局布局流向与算法选择，以及少量覆盖提示。
- 类型: object，必填。
- 字段及取值:
  - `flow`: string，主流向。
    - `left-to-right`: 从左到右（默认，科研图常用）。
    - `right-to-left`: 从右到左（较少使用）。
    - `top-to-bottom`: 从上到下（如 U-Net、层级树）。
    - `bottom-to-top`: 从下到上（极少使用）。
  - `algorithm`: string，布局算法。
    - `dagre`: 基于层级的有向图布局（稳定、常用）。
    - `elk`: 更灵活的图布局（复杂图更优）。
    - `manual`: 手动/交互式布局（由后续编辑器控制）。
  - `hints`: object，可选，轻量覆盖。
    - `direction_overrides`: object，针对特定 group 或节点子集的局部流向覆盖。
      - 键: `group_id` 或一个子集标识（实现可约定为特殊字符串）。
      - 值: 与 `flow` 同枚举，例如 `{"grp_decoder": "top-to-bottom"}` 表示解码器组内部按上下方向排。

### Chunks（网格块）

#### `chunks[]`
- 含义: 空间容器（不携带语义），定义在栅格上的位置/跨度。
- 类型: array，必填。
- 字段及取值:
  - `chunk_id`: string，唯一标识。
  - `grid_area`: object，定位与跨度。
    - `row`: number，起始行（0-based）。
    - `col`: number，起始列（0-based）。
    - `rowspan`: number，跨越的行数（默认 1）。
    - `colspan`: number，跨越的列数（默认 1）。
  - `description`: string，可选；该空间区域的简单说明。用于人读与未来 VLM。
- 说明: chunk 仅作为“空间容器”，不再定义 `role`。

### Groups（语义分组）

#### `groups[]`
- 含义: 语义容器（阶段/模块/等），限定节点的可放置范围与组内排列规则。
- 类型: array，必填。
- 字段及取值:
  - `group_id`: string，唯一标识。
  - `label`: string，组标签，简短可读。
  - `type`: string，组类型枚举。
    - `stage`: 阶段（如 Input/Process/Output）。
    - `module`: 模块（如 Encoder/Decoder）。
    - `repeat`: 重复结构（当前阶段不展开配置，可保留类型）。
    - `conditional`: 条件分支（当前阶段不展开配置，可保留类型）。
  - `chunks`: array of string，引用的 chunk_id 列表（组可跨多个 chunk）。
  - `layout_hint`: object，可选，组内排列提示。
    - `arrangement`: `horizontal` | `vertical`。
      - `horizontal`: 组内节点按左→右排列。
      - `vertical`: 组内节点按上→下排列。
    - `order`: array of string，可选，指定组内节点的视觉顺序（按 `arrangement`）。
      - 例: `{"arrangement":"horizontal","order":["enc","mlp","norm"]}` → 左到右依次为 enc、mlp、norm。
      - 例: `{"arrangement":"vertical","order":["raw","token"]}` → 上到下依次为 raw、token。
    - `collapse`: boolean，可选，表示该组在粗粒度图中是否折叠为容器（节点隐藏、仅展示标签）。
  - `description`: string，可选；组的简要语义说明。
- 说明: 为避免双重来源，组不再定义 `grid_area`，空间关系仅通过 `chunks` 表达。

### Nodes（节点）

#### `nodes[]`
- 含义: 图中的实体元素（数据/层/损失等）。归属唯一组，并参与布局与连线。
- 类型: array，必填。
- 字段及取值:
  - `node_id`: string，唯一标识。
  - `label`: string，节点标签，简短可读。
  - `type`: string，实体类别枚举，见 `taxonomy.node_type`。
    - 语义：用于样式/图例/理解。例如 `data`（数据张量）、`layer`（网络层）、`loss`（损失）。
  - `group`: string，节点所属组的 `group_id`（唯一归属，必填）。
  - `role`: string，流程阶段枚举，见 `taxonomy.node_role`。
    - 语义：用于宏观布局与阶段划分。例如 `input`（输入端）、`process`（处理中）、`output`（输出端）。
  - `size_hint`: `small` | `medium` | `large`，可选；相对尺寸提示（影响自动布局时的箱体大小或权重）。
    - 例：`large` 可用于主干模块，`small` 用于辅助节点。
  - `placement_hint`: object，可选；在跨 chunk 组内的放置偏好与对齐。
    - `preferred_chunk`: string，可选；若组跨多个 chunk，优先放置的 chunk_id。
    - `align`: `left` | `center` | `right` | `top` | `bottom`，可选；在所属 chunk 内的对齐偏好。
  - `ports`: array，可选；定义进/出线的侧边端口，提高布线稳定性。
    - 每项: `{id: string, side: 'left'|'right'|'top'|'bottom'}`。
    - 语义：约束边从该侧进入或离开节点，避免自动布局出现“绕背部”。
  - `description`: string，可选；节点的简要语义说明。

### Edges（连接边）

#### `edges[]`
- 含义: 节点之间的连接（数据流/控制流/依赖等）。
- 类型: array，必填。
- 字段及取值:
  - `edge_id`: string，唯一标识。
  - `source`: string，起点节点 id。
  - `target`: string，终点节点 id。
  - `type`: string，边类型枚举，见 `taxonomy.edge_type`。
    - 语义：影响样式与布局优先级。例如 `data`（主干数据流），`control`（控制信号），`dependency`（依赖关系箭头）。
  - `label`: string，可选；边标签（如张量形状、注释）。
  - `route_hint`: `straight` | `orthogonal` | `curve`，可选；布线偏好。
    - `straight`: 直线连接（最简洁）。
    - `orthogonal`: 直角折线（适合跨层或避让）。
    - `curve`: 曲线（适合强调或绕行）。
  - `direction_hint`: `left` | `right` | `up` | `down`，可选；期望的连接方向（相对布局流向）。
    - 例：在 `left-to-right` 下，`down` 常用于同列内的竖向连接。
  - `source_port`/`target_port`: string，可选；端口 id，对应 `nodes[].ports[].id`。
    - 语义：指定从哪侧进出，提高线条整洁。
  - `description`: string，可选；边的简要语义说明。

### Taxonomy（枚举清单与含义）

#### `taxonomy`
- 含义: 当前阶段统一的枚举取值清单，便于各 Agent 对齐（非强校验）。
- 字段及取值含义：
  - `node_type`: ["data", "module", "layer", "loss", "metric", "op", "dataset", "preprocess", "postprocess"]
    - data: 数据张量或中间结果
    - module: 复合模块（包含多层）
    - layer: 单一网络层/算子
    - loss: 损失函数模块
    - metric: 评估指标模块
    - op: 通用操作/算子
    - dataset: 数据集来源或块
    - preprocess: 预处理步骤
    - postprocess: 后处理步骤
  - `node_role`: ["input", "process", "output", "aux", "param", "note"]
    - input: 输入端元素
    - process: 主干处理阶段元素
    - output: 输出端元素
    - aux: 辅助元素（如注解、辅助模块）
    - param: 参数/超参元素（如学习率等）
    - note: 说明性节点（仅文本或图例）
  - `edge_type`: ["data", "control", "grad", "param", "dependency"]
    - data: 数据流边（主干）
    - control: 控制信号边（开关/触发）
    - grad: 反向梯度流边
    - param: 参数传递边
    - dependency: 依赖/引用关系边（非数据流）
  - `group_type`: ["stage", "module", "repeat", "conditional"]
    - stage: 阶段容器（输入/处理/输出）
    - module: 模块容器（功能性）
    - repeat: 重复容器（当前不展开配置）
    - conditional: 条件容器（当前不展开配置）
  - `edges_route_hint`: ["straight", "orthogonal", "curve"]（见上）
  - `edges_direction_hint`: ["left", "right", "up", "down"]（见上）
  - `groups_layout_arrangement`: ["horizontal", "vertical"]（见上）
  - `nodes_size_hint`: ["small", "medium", "large"]（见上）
  - `ports_side`: ["left", "right", "top", "bottom"]（见上）

## 端到端示例（最小、可渲染）

```json
{
  "version": "0.1",
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "grid": {"rows": 3, "cols": 2, "margin": {"top": 20, "right": 20, "bottom": 20, "left": 20}, "gutter": {"row": 10, "col": 10}},
  "layout": {"flow": "left-to-right", "algorithm": "dagre"},
  "chunks": [
    {"chunk_id": "chunk_0_0", "grid_area": {"row": 0, "col": 0}},
    {"chunk_id": "chunk_1_0", "grid_area": {"row": 1, "col": 0, "colspan": 2}},
    {"chunk_id": "chunk_2_0", "grid_area": {"row": 2, "col": 0}}
  ],
  "groups": [
    {"group_id": "grp_input", "label": "Input Processing", "type": "stage", "chunks": ["chunk_0_0"], "layout_hint": {"arrangement": "horizontal"}},
    {"group_id": "grp_model", "label": "Core Model", "type": "module", "chunks": ["chunk_1_0"], "layout_hint": {"arrangement": "horizontal"}},
    {"group_id": "grp_output", "label": "Output & Loss", "type": "stage", "chunks": ["chunk_2_0"], "layout_hint": {"arrangement": "horizontal"}}
  ],
  "nodes": [
    {"node_id": "node1", "label": "Input Data", "type": "data", "group": "grp_input", "role": "input"},
    {"node_id": "node2", "label": "Tokenizer", "type": "preprocess", "group": "grp_input", "role": "process"},
    {"node_id": "node3", "label": "Transformer Encoder", "type": "layer", "group": "grp_model", "role": "process", "ports": [{"id": "p_left", "side": "left"}, {"id": "p_right", "side": "right"}]},
    {"node_id": "node4", "label": "MLP Head", "type": "layer", "group": "grp_model", "role": "process"},
    {"node_id": "node5", "label": "Softmax Output", "type": "op", "group": "grp_output", "role": "output"},
    {"node_id": "node6", "label": "Cross-Entropy Loss", "type": "loss", "group": "grp_output", "role": "output"}
  ],
  "edges": [
    {"edge_id": "e1", "source": "node1", "target": "node2", "type": "data", "route_hint": "straight"},
    {"edge_id": "e2", "source": "node2", "target": "node3", "type": "data", "route_hint": "straight", "target_port": "p_left"},
    {"edge_id": "e3", "source": "node3", "target": "node4", "type": "data", "route_hint": "straight", "source_port": "p_right"},
    {"edge_id": "e4", "source": "node4", "target": "node5", "type": "data", "route_hint": "orthogonal", "direction_hint": "down"},
    {"edge_id": "e5", "source": "node5", "target": "node6", "type": "dependency", "route_hint": "straight"}
  ],
  "taxonomy": {
    "node_type": ["data", "module", "layer", "loss", "metric", "op", "dataset", "preprocess", "postprocess"],
    "node_role": ["input", "process", "output", "aux", "param", "note"],
    "edge_type": ["data", "control", "grad", "param", "dependency"],
    "group_type": ["stage", "module", "repeat", "conditional"],
    "edges_route_hint": ["straight", "orthogonal", "curve"],
    "edges_direction_hint": ["left", "right", "up", "down"],
    "groups_layout_arrangement": ["horizontal", "vertical"],
    "nodes_size_hint": ["small", "medium", "large"],
    "ports_side": ["left", "right", "top", "bottom"]
  }
}
```
