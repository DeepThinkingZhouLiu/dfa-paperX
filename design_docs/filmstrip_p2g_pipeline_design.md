# Film-Strip（连环画）Bottom-Up Paper2PPTX Pipeline 设计文档

本文档定义一个新的、可编辑的科研绘图生成工作流：先生成/实例化素材（VLM 连环画子图 + PPTX 原生形状/文本），再基于实际尺寸做布局，最后组装为 PPTX。设计目标是替代 `tests/test_chunk_p2g_pipeline.py` 中“先布局后生图 + chunk 整图渲染”的不稳定方案，并保持与现有 Agentrole 的实现范式一致（`state` 字段分阶段写入、`SYSTEM_PROMPT`/`TASK_PROMPT_TEMPLATE` 位置、`agent_results` 记录方式等）。

---

## 1. Pipeline 概览（7 个 Agent 节点）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Film-Strip Bottom-Up P2G Pipeline (Editable PPTX)           │
└─────────────────────────────────────────────────────────────────────────────┘

用户输入 (target: 论文方法描述/摘要)
        │
        ▼
┌───────────────────────────────────┐
│ 1) node_graph_constructor_agent   │  从 target 构建 nodes/edges（不做布局）
└───────────────────────────────────┘
        │  state.node_graph_json
        ▼
┌───────────────────────────────────┐
│ 2) render_method_classifier_agent │  将 nodes 分为 VLM / PPTX 两类
└───────────────────────────────────┘
        │  state.render_plan_json
        ├───────────────────────────────┐
        ▼                               ▼
┌───────────────────────────────────┐  ┌───────────────────────────────────┐
│ 3) vlm_group_planner_agent        │  │ 4) pptx_spec_generator_agent       │
│  VLM nodes 分组 + 生成连环画 prompt│  │  生成 PPTX 节点结构化渲染规格       │
└───────────────────────────────────┘  └───────────────────────────────────┘
        │  state.vlm_group_plan_json     │  state.pptx_render_specs
        └───────────────┬───────────────┘
                        ▼
┌───────────────────────────────────┐
│ 5) filmstrip_renderer_agent       │  VLM 生“连环画”→切图→去背景→抠图→保存
└───────────────────────────────────┘
        │  state.vlm_rendered_nodes + state.vlm_node_assets
        ▼
┌───────────────────────────────────┐
│ 6) layout_engine_agent            │  基于实际尺寸 + 拓扑关系计算最终布局
└───────────────────────────────────┘
        │  state.layout_json
        ▼
┌───────────────────────────────────┐
│ 7) pptx_composer_agent            │  组装 PPTX（图片 + 原生形状 + edges）
└───────────────────────────────────┘
        │  state.pptx_output_path
        ▼
最终输出：可编辑 PPTX
```

---

## 2. Request / State 设计（参考 `ChunkP2GRequest/State` 风格）

建议新增一套独立 Request/State（不影响原 `Paper2GraphState` 与 Chunk Pipeline）：
- 文件：`dataflow_agent/state.py`
- 类名：`FilmStripP2GRequest`、`FilmStripP2GState`

### 2.1 Request

```python
@dataclass
class FilmStripP2GRequest(MainRequest):
    target: str = ""

    # 画布配置（像素）
    canvas_width: int = 1920
    canvas_height: int = 1080

    # VLM 渲染配置
    vlm_model: str = "gemini-3-pro-image-preview"
    vlm_concurrency: int = 4
    vlm_timeout: int = 600

    # Film-Strip 约束
    max_vlm_group_size: int = 4          # 单组子图数上限
    panel_gap_px: int = 20              # 子图间白色间隔（期望值）
    panel_bg_hex: str = "#FFFFFF"       # 连环画背景/分隔主色

    # 输出目录
    output_dir: str = ".tmp/filmstrip_p2g"
```

### 2.2 State（分阶段字段）

```python
@dataclass
class FilmStripP2GState(MainState):
    request: FilmStripP2GRequest = field(default_factory=FilmStripP2GRequest)

    # ==================== Stage 1: Node Graph ====================
    node_graph_json: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "title": "...",
    #   "global_style": {...},
    #   "nodes": [{...}],
    #   "edges": [{...}]
    # }

    # ==================== Stage 2: Render Plan ====================
    render_plan_json: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "vlm_nodes": ["n1", "n2"],
    #   "pptx_nodes": ["n3", "n4"],
    #   "by_node": {
    #     "n1": {"render_method": "vlm", "vlm_desc": "...", "size_hint": {...}},
    #     "n3": {"render_method": "pptx", "pptx_intent": "...", "size_hint": {...}}
    #   }
    # }

    # ==================== Stage 3: VLM Groups ====================
    vlm_group_plan_json: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "groups": [
    #     {
    #       "group_id": "g1",
    #       "node_ids": ["n1", "n2", "n5"],  # panel 顺序必须稳定
    #       "subject": "...",
    #       "prompt": "..."
    #     }
    #   ]
    # }

    # ==================== Stage 4: PPTX Specs ====================
    # node_id -> PPTXRenderSpec（供 PPTXNodeRenderer / 扩展版 renderer 消费）
    pptx_render_specs: Dict[str, Any] = field(default_factory=dict)

    # ==================== Stage 5: Rendered Assets ====================
    # node_id -> image_path（抠图后的透明 PNG，供 PPTX 插图）
    vlm_rendered_nodes: Dict[str, str] = field(default_factory=dict)
    # node_id -> {path, width_px, height_px, source_group_id, panel_index, ...}
    vlm_node_assets: Dict[str, Any] = field(default_factory=dict)
    # group_id -> {path, render_time_ms, status, ...}
    filmstrip_images: Dict[str, Any] = field(default_factory=dict)
    filmstrip_render_errors: Dict[str, str] = field(default_factory=dict)

    # ==================== Stage 6: Layout ====================
    layout_json: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "canvas": {"width": 1920, "height": 1080, "unit": "px"},
    #   "nodes": [{"node_id": "n1", "bbox": {"x": 0, "y": 0, "w": 320, "h": 240}}],
    #   "edges": [{"edge_id": "e1", "from": "n1", "to": "n3", "route": "orthogonal"}]
    # }

    # ==================== Stage 7: Output ====================
    pptx_output_path: str = ""
```

> 说明：本 State 字段与现有 `Paper2GraphState` 的 `layout_json / pptx_render_specs / vlm_rendered_nodes` 命名保持一致，便于后续复用 `dataflow_agent/agentroles/p2g_pptx_composer_agent.py`（或轻量 wrapper）。

---

## 3. Stage 1：`node_graph_constructor_agent`（从 target 构建 nodes/edges）

### 3.1 职责

- 从 `state.request.target` 解析出要画的节点与连接关系（nodes/edges）。
- 不做布局、不做渲染方式决策。
- 输出必须足够“可渲染”：每个 node 至少包含 `label/desc`，每条 edge 给出方向与语义。

### 3.2 输入 / 输出

- 输入：`state.request.target`
- 输出：`state.node_graph_json`

### 3.3 输出 Schema（MVP）

```json
{
  "title": "Figure Title",
  "global_style": {
    "theme": "scientific_diagram",
    "palette": {"primary": "#4A90D9", "accent": "#fc8d62", "text": "#333333"}
  },
  "nodes": [
    {
      "node_id": "n1",
      "label": "Input Image",
      "role": "input|process|output|aux",
      "semantic_desc": "what it means",
      "visual_desc": "what it should look like (shape/icon/data)",
      "constraints": {"no_text_inside": false}
    }
  ],
  "edges": [
    {
      "edge_id": "e1",
      "from": "n1",
      "to": "n2",
      "edge_type": "data_flow|control_flow|annotation",
      "label": "optional label",
      "direction_hint": "left_to_right"
    }
  ]
}
```

### 3.4 Prompt 放置与模板（参考 Chunk Agent 的 inline 常量风格）

文件建议：`dataflow_agent/agentroles/p2g_filmstrip_node_graph_constructor_agent.py`

- `SYSTEM_PROMPT`: 角色能力 + 输出必须为 JSON
- `TASK_PROMPT_TEMPLATE`: 注入 `{target}` + 输出 schema

关键约束（写入 prompt）：
- node_id 必须是 `n1..nK` 连续编号
- edge_id 必须是 `e1..eM` 连续编号
- nodes 数量尽量控制在 8-20（MVP），避免过大图

---

## 4. Stage 2：`render_method_classifier_agent`（VLM vs PPTX）

### 4.1 职责

对 Stage 1 的 nodes 做渲染策略分类：
- `vlm`：具象视觉内容（输入图/分割图/热力图/示例图/小插画/图标等）
- `pptx`：文本框、基础形状、流程模块框、纯几何容器、简单箭头说明等（强调可编辑）

### 4.2 输入 / 输出

- 输入：`state.node_graph_json`
- 输出：`state.render_plan_json`

### 4.3 输出 Schema（按 node 汇总）

```json
{
  "vlm_nodes": ["n1", "n2"],
  "pptx_nodes": ["n3"],
  "by_node": {
    "n1": {
      "render_method": "vlm",
      "vlm_desc": "Pure visual description for VLM panel (no labels inside image).",
      "size_hint": {"w_px": 360, "h_px": 240, "aspect_ratio": "3:2"}
    },
    "n3": {
      "render_method": "pptx",
      "pptx_intent": "A rounded rectangle module box with centered text ...",
      "size_hint": {"w_px": 260, "h_px": 90}
    }
  }
}
```

实现建议：
- 优先规则化（减少 LLM 波动）：例如 `role in {input, output} and visual_desc contains 'image/map/heatmap' -> vlm`
- 规则不足时再让 LLM 补全（仍输出严格 JSON）

---

## 5. Stage 3：`vlm_group_planner_agent`（分组 + 连环画 prompt）

### 5.1 职责

对 `render_method="vlm"` 的 nodes 进行分组，并为每组生成单次 VLM 调用可消费的“连环画 prompt”。

分组目标：
- 需要保持一致性的 node 放入同一组（同一场景的输入/输出、对比组、同一数据流的多个视图）
- 每组 panel 数不要过多（建议 `<= state.request.max_vlm_group_size`）
- `node_ids` 的顺序即 panel 顺序（必须稳定，供切图映射）

### 5.2 输入 / 输出

- 输入：`state.node_graph_json` + `state.render_plan_json`
- 输出：`state.vlm_group_plan_json`

### 5.3 输出 Schema

```json
{
  "groups": [
    {
      "group_id": "g1",
      "node_ids": ["n1", "n2", "n4"],
      "subject": "A street scene (Cityscapes style), consistent across panels",
      "prompt": "You are a scientific illustrator. Generate ONE single image composed of 3 sub-panels ..."
    }
  ]
}
```

### 5.4 连环画 Prompt 模板（强约束，参考你的成功 prompt）

建议在 Agent 内置一个模板（由 LLM 只填 `{subject}` 与各 panel 描述），并将“Panel i 对应 node_id”写入 `vlm_group_plan_json.groups[*].node_ids`，而不是写在图里：

```text
You are a scientific illustrator. Generate ONE single image composed of {panel_count} sub-panels arranged horizontally (side-by-side) with white space in between.

Subject: {subject}

{panel_descriptions}

Constraints:
- All panels must depict the EXACT SAME scene/subject for visual consistency.
- Do not add any text, labels, legends, watermarks, or captions inside the image.
- Pure visual data only.
- Use solid pure white (#FFFFFF) background and pure white gaps between panels.
- Each panel must be a complete self-contained image with consistent style.
```

`panel_descriptions` 例子（按 `node_ids` 顺序生成）：
- `Panel 1 (Left): {node[n1].vlm_desc}`
- `Panel 2 (Middle): {node[n2].vlm_desc}`
- `Panel 3 (Right): {node[n4].vlm_desc}`

---

## 6. Stage 4：`pptx_spec_generator_agent`（PPTX 原生节点渲染规格）

### 6.1 职责

为 `render_method="pptx"` 的 nodes 生成结构化 `PPTXRenderSpec`，包含：
- 文本内容（`text` / `text_lines`）
- 形状类型（基础矩形、圆角矩形、梯形等）
- 形状样式（填充/边框/文字样式）
- （可选）方向/旋转参数（满足“梯形方向”等需求）

### 6.2 输入 / 输出

- 输入：`state.node_graph_json` + `state.render_plan_json`
- 输出：`state.pptx_render_specs`（`Dict[node_id, spec]`）

### 6.3 输出 Schema（兼容现有 `PPTXNodeRenderer` 的 MVP + 可扩展字段）

MVP（直接兼容 `dataflow_agent/toolkits/pptx_composer/node_renderer.py`）：

```json
{
  "n3": {
    "element_type": "rounded_rectangle",
    "text": "SegFormer Backbone",
    "text_style": {"font_family": "Arial", "font_size": 14, "color": "#FFFFFF", "alignment": "center", "bold": true},
    "shape_style": {"fill_color": "#4A90D9", "border_style": "solid", "border_color": "#2E5A8C", "border_width": 1.5},
    "auto_fit": "shrink"
  }
}
```

扩展（支持梯形/箭头等 MSO_SHAPE）：

```json
{
  "n7": {
    "element_type": "mso_shape",
    "mso_shape": "TRAPEZOID",
    "shape_params": {"direction": "right"},
    "text": "Fusion",
    "text_style": {"font_size": 12, "alignment": "center"},
    "shape_style": {"fill_color": "#66c2a5", "border_style": "solid", "border_color": "#3A7F73", "border_width": 1.0}
  }
}
```

> 说明：现有 `PPTXNodeRenderer` 尚未实现 `mso_shape` 分支；若要满足“梯形方向”，建议在 `dataflow_agent/toolkits/pptx_composer/node_renderer.py` 中新增一个 `_render_mso_shape(...)` 并支持 `shape.rotation` / `flip`（必要时用 rotation 近似方向）。

---

## 7. Stage 5：`filmstrip_renderer_agent`（VLM 生图 + 切图 + 去背景 + 映射校验）

### 7.1 职责

对每个 group：
1. 调用 VLM 生成一张连环画图（保存 `group_id.png`）
2. 将连环画切分为 `len(node_ids)` 个 panel（顺序必须与 `node_ids` 对齐）
3. 对每个 panel 做去背景/抠图（输出透明 PNG）
4. 写回：
   - `state.vlm_rendered_nodes[node_id] = /path/to/node.png`
   - `state.vlm_node_assets[node_id] = {width_px, height_px, source_group_id, panel_index}`

### 7.2 输入 / 输出

- 输入：`state.vlm_group_plan_json`
- 输出：`state.filmstrip_images`、`state.vlm_rendered_nodes`、`state.vlm_node_assets`、`state.filmstrip_render_errors`

### 7.3 切图算法建议（鲁棒回退）

优先策略：检测“几乎纯白”的竖向分隔带（基于像素列的白色比例/方差）。

回退策略：
- 若分隔检测失败或切片数量不等于 `expected_count`，使用等分切割；
- 切割后对每个 panel 做有效性校验（非空、非全白），否则仍回退等分或触发重试渲染（可选）。

### 7.4 去背景/抠图

复用现有工具链（参考 `p2g_vlm_node_renderer_agent.py`）：
- 首选 `EdgeFloodFillRemover`（图表/插画背景更稳定）
- 对需要复杂抠图的类目可切换 `BriaRMBG2Remover`

输出路径建议：
- `{output_dir}/filmstrips/{group_id}.png`
- `{output_dir}/vlm_nodes/{node_id}.png`（透明 PNG）

---

## 8. Stage 6：`layout_engine_agent`（基于实际尺寸布局）

### 8.1 职责

基于：
- `state.node_graph_json.edges`（拓扑/流程方向）
- VLM 节点真实尺寸（`state.vlm_node_assets[*].width_px/height_px`）
- PPTX 节点 size_hint（来自 Stage 2）或默认估计（来自 Stage 4 text/font）

计算最终 `state.layout_json`（像素级 bbox），保证：
- 不重叠、间距一致、主流程清晰
- 尽量满足 left-to-right（默认）或 top-to-bottom（可配置）

### 8.2 输出 Schema

```json
{
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "nodes": [
    {"node_id": "n1", "bbox": {"x": 80, "y": 200, "w": 360, "h": 240}},
    {"node_id": "n3", "bbox": {"x": 520, "y": 260, "w": 260, "h": 90}}
  ],
  "edges": [
    {"edge_id": "e1", "from": "n1", "to": "n3", "route": "orthogonal", "style": {"color": "#424242", "width": 2}}
  ]
}
```

### 8.3 MVP 布局算法（确定性）

建议采用 “分层（rank）+ 层内分配 + 冲突消解”：
1. DAG 拓扑排序得到 rank（主方向左→右）
2. 每个 rank 形成一列，列内按边关系/role 排序
3. X 坐标：按列宽累计 + 固定 gap
4. Y 坐标：列内居中分布 + 最小间距
5. 迭代消解重叠（轻量 nudging）

> 该 agent 不调用 LLM，保持可重复性（类似 `p2g_chunk_vlm_designer_agent` 的“纯计算”风格）。

---

## 9. Stage 7：`pptx_composer_agent`（组装 PPTX）

### 9.1 职责

将 `layout_json`（bbox）、`pptx_render_specs`（PPTX 节点规格）、`vlm_rendered_nodes`（图片）与 `node_graph_json.edges`（连接线）渲染为最终 PPTX。

### 9.2 实现建议（最大复用现有组件）

优先复用：
- `dataflow_agent/agentroles/p2g_pptx_composer_agent.py`
- `dataflow_agent/toolkits/pptx_composer/PPTXBuilder`

适配点：
- `FilmStripP2GState` 字段命名已与 composer 输入对齐（`layout_json / pptx_render_specs / vlm_rendered_nodes`）
- 若需要支持 `mso_shape`（梯形等），扩展 `PPTXNodeRenderer.render_node(...)` 分支即可

输出：
- `state.pptx_output_path = "{output_dir}/paper2graph_filmstrip.pptx"`

---

## 10. Workflow 入口（参考 `run_chunk_p2g_pipeline`）

建议新增：
- `dataflow_agent/workflow/wf_p2g_filmstrip_pipeline.py`
- 入口函数：`run_filmstrip_p2g_pipeline(...) -> FilmStripP2GState`

伪代码：

```python
async def run_filmstrip_p2g_pipeline(target: str, **kwargs) -> FilmStripP2GState:
    request = FilmStripP2GRequest(target=target, **kwargs)
    state = FilmStripP2GState(request=request)

    state = await p2g_filmstrip_node_graph_constructor_agent(state, model_name=request.model)
    state = await p2g_filmstrip_render_method_classifier_agent(state, model_name=request.model)
    state = await p2g_filmstrip_vlm_group_planner_agent(state, model_name=request.model)
    state = await p2g_filmstrip_pptx_spec_generator_agent(state, model_name=request.model)
    state = await p2g_filmstrip_renderer_agent(state, vlm_model=request.vlm_model, output_dir=request.output_dir)
    state = await p2g_filmstrip_layout_engine_agent(state)
    state = await p2g_pptx_composer_agent(state, output_path=..., render_edges=True)
    return state
```

测试建议：
- `tests/test_filmstrip_p2g_pipeline.py`（结构与 `tests/test_chunk_p2g_pipeline.py` 一致：Step1..Step7 可单测/可 full）

---

## 11. MVP 优先级与风控建议

1. MVP 先支持 `panel_count <= 3` 或 `<= 4`（可显著提升切图稳定性）
2. 强约束 prompt：禁止文字、纯白背景、强调 EXACT SAME scene
3. 切图必须“expected_count 校验 + 回退等分”
4. PPTX 形状先落地现有 `element_type`（text_box/rectangle/rounded_rectangle/line/arrow），再扩展 trapezoid
5. 版式先做确定性分层布局，后续再引入更复杂约束（对齐/分组容器/图例）

