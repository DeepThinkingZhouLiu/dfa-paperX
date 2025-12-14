# Stage 6 设计文档：`layout_engine_agent`（Film-Strip Bottom-Up）

目标：在已获得 **真实素材尺寸**（VLM 子图）与 **可编辑元素规格**（PPTX shapes/text specs）的前提下，结合 **语义图（nodes/edges/roles）** 输出一个稳定、可复用、论文风格的 `layout_json`（像素级 bbox），供 Stage7 `pptx_composer` 直接渲染。

> 关键原则：Stage6 **不让 LLM 直接产出坐标**。LLM 的波动会导致重叠/越界/逻辑反直觉。Stage6 应为 **纯计算**（deterministic）+ 少量可配置参数。

---

## 1. 输入 / 输出

### 1.1 输入（来自 FilmStripP2GState）

- `state.node_graph_json`（Stage1）
  - `nodes[]`: `{node_id, label, role, semantic_desc, visual_desc, constraints}`
  - `edges[]`: `{edge_id, from, to, edge_type, label, direction_hint}`
- `state.render_plan_json`（Stage2）
  - `by_node[node_id]`: `{render_method, size_hint, ...}`
- `state.vlm_group_plan_json`（Stage3）
  - `groups[]`: `{group_id, node_ids, subject, prompt}`
- `state.pptx_render_specs`（Stage4）
  - `node_id -> PPTXRenderSpec`（含 `text_style`、`shape_style`、`extras.size_hint_px` 等）
- `state.vlm_node_assets`（Stage5）
  - `node_id -> {path, width_px, height_px, source_group_id, panel_index}`
- `state.request.canvas_width / canvas_height`

### 1.2 输出（写回 FilmStripP2GState）

必须输出 **与现有 `PPTXBuilder` 兼容** 的结构（注意 `positions.nodes`）：

```json
{
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "positions": {
    "nodes": [
      {"node_id": "n1", "bbox": {"x": 50, "y": 200, "w": 320, "h": 240}}
    ],
    "chunks": []
  },
  "meta": {
    "flow_direction": "left_to_right",
    "lane_count": 3
  }
}
```

> Stage7 目前的 `PPTXBuilder` 从 `layout_json["positions"]["nodes"]` 读取 bbox（不是 `layout_json["nodes"]`）。

---

## 2. Stage6 的职责拆解（建议分 5 个子步骤）

1. **Build Graph Index**：建立 node/edge 索引，区分 `data_flow` 与 `aux/control/annotation`。
2. **Size Solver**：为每个 node 求一个“理想显示尺寸”（w/h px）。
3. **Structure Planner**：从语义图抽取“主干 + 分支”结构，得到 rank（列）与 lane（泳道）等离散布局约束。
4. **Box Layout Solver**：在 rank/lane 约束下放置 bbox（坐标求解 + 碰撞消解 + 画布自适配）。
5. **Emit layout_json**：输出最终 bbox + 可选 debug/meta。

---

## 3. Size Solver（尺寸求解）

### 3.1 VLM 节点尺寸（真实比例来源）

VLM 节点有真实内容外接框尺寸：
- `intrinsic_w/h = state.vlm_node_assets[node_id].width_px/height_px`

推荐：不要直接使用 intrinsic px 做最终 bbox（会导致整体比例不稳定），而是分档统一展示尺度：

**默认目标高度（可配置）**
- `role=input`: `target_h = 240`
- `role=output`: `target_h = 240`
- 其他 VLM：`target_h = 160`

**同一 VLM group 的尺度一致**
- `group_id = vlm_node_assets[node_id].source_group_id`
- 对 group 内所有节点，使用相同 `target_h`（取 max 或 median 的档位）

最终：
- `h = target_h`
- `w = round(intrinsic_w * target_h / intrinsic_h)`

> 这与 Stage3 的“panel 内不拉伸 + 可留白”配合：Stage5 已裁剪白边，intrinsic_w/h 近似为内容真实比例。

### 3.2 PPTX 节点尺寸（优先 size_hint，其次测量文字）

PPTX 节点建议采用“强约束优先”的策略：

优先级：
1. `pptx_render_specs[node_id].extras.size_hint_px`（你目前已经生成，最稳定）
2. `render_plan_json.by_node[node_id].size_hint`（Stage2 产物）
3. **文本测量 fallback**（当 1/2 缺失或明显不合理时）

**文本测量 fallback（建议 PIL 实现）**
- 字体：优先使用系统字体（如 `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` 或 `Lato`/`Noto`）
- 取 `font_size = spec.text_style.font_size`（默认 14）
- 取 `max_width_px`：模块框默认 260~320；token 小块默认 140~180
- 按 `max_width_px` 做自动换行（英文按空格切词；中文按字符）
- 用 `ImageFont.getbbox()`/`getlength()` 估算每行宽度与总高度
- bbox = `text_bbox + padding`（左右 16~22，上下 10~14）
- 最小高度：rounded_rectangle 模块框建议 `>= 60`

输出：
`node_size_map[node_id] = (w_px, h_px)`（所有节点都必须有）

---

## 4. Structure Planner（离散结构：rank / lane / anchor）

### 4.1 Edge 处理策略

布局只使用 `edge_type == "data_flow"` 作为主约束。
- `control_flow` / `annotation` 可在后续版本加入（比如虚线/弱约束），但不要参与 rank 计算，否则容易引入环与噪声。

### 4.2 Anchor（锚点）——用于放置 VLM / aux

对 “不是主干流程模块” 的节点（尤其 VLM、aux），给一个锚点 process 节点，避免漂移：

**VLM nodes**
- `role=input`：anchor = 它的直接下游（第一条 data_flow 的 `to`）
- `role=output`：anchor = 它的直接上游（第一条 data_flow 的 `from`）
- 其他：选择与其 data_flow 直接相连的 process 节点（若多条，选度最高或 label 更像模块的）

**aux nodes（loss/memory bank 等）**
- anchor = 与其相连的最近 process 节点（优先 data_flow 相邻，其次 control_flow）

输出：
`anchor_map[node_id] = anchor_node_id | None`

### 4.3 主干（spine）识别

目的：得到“论文图常见的中间主干流程”，其余分支围绕主干布置。

算法（确定性、无需 LLM）：
1. 仅用 `data_flow` 构建有向图
2. 输入候选：`role == "input"`，若为空则 `in_degree==0`
3. 输出候选：`role == "output"`，若为空则 `out_degree==0`
4. 在 DAG 上做 longest-path DP（若检测到环：忽略造成环的最弱边，或降级为拓扑排序顺序）
5. 路径得分建议加权：
   - `role=process`: +2
   - `role=output`: +1
   - `role=aux`: -1
6. 取最高分路径为 spine：`spine_nodes = [..]`

### 4.4 rank（列）分配

rank 的目标是让边尽可能“左→右”，且与论文图直觉一致。

基础 rank：
- 对 data_flow 图做拓扑 DP：`rank[v] = max(rank[u]+1)`（u->v）

再做 anchor 修正（重要）：
- 对 `role=input` 的 VLM：`rank[node] = rank[anchor]-1`
- 对 `role=output` 的 VLM：`rank[node] = rank[anchor]+1`
- 对 aux 节点：默认 `rank[node] = rank[anchor]+1`（让它出现在右侧或右上/右下，边更短）

并对所有 rank 做归一化（最小 rank 平移到 0）。

### 4.5 lane（泳道）分配（不依赖 VLM group）

你提供的论文图结构非常典型：主干在中间，分类/监督在上，伪标签/聚类在下。建议 Stage6 默认支持 3 lane：

- `lane=mid`：spine + 与 spine 强耦合的主流程模块
- `lane=top`：classification / label / loss / supervision
- `lane=bottom`：pseudo / cluster / memory / bank / prototype

lane 决策建议采用“关键词 + 继承”：
- 关键词来自：`node.label + node.semantic_desc`
- top_score 关键词：`class`, `classification`, `label`, `supervision`, `loss`, `logit`, `token`（可配置）
- bottom_score 关键词：`pseudo`, `cluster`, `clustering`, `memory`, `bank`, `prototype`, `update`（可配置）
- 若节点在 spine：强制 `mid`
- 否则：
  - `top_score > bottom_score` => `top`
  - `bottom_score > top_score` => `bottom`
  - tie：继承 `lane[anchor]`（若无 anchor 则 mid）

> VLM group 只影响“尺度一致”，不决定 lane。例：`g1=[input, pred, pseudo]`，它们会分别出现在左侧输入、右侧输出、下方伪标签，而不是同一行。

---

## 5. Box Layout Solver（坐标求解：从离散到 bbox）

### 5.1 x 坐标：按 rank 列宽累计

输入：`rank[node]` 与 `node_size_map[node]=(w,h)`

参数（可配置）：
- `margin_x = 60`
- `col_gap = 90`

计算：
- 每列宽度 `col_w[r] = max(w of nodes in rank r)`
- 列起始 x：`x0 = margin_x`，`x[r+1] = x[r] + col_w[r] + col_gap`
- 节点 x：`node_x = x[rank[node]] + (col_w[rank]-w)/2`（列内居中）

### 5.2 y 坐标：lane 基线 + 附着规则

参数（可配置）：
- `margin_y = 60`
- `lane_gap = 90`（lane 之间的垂直间隔）
- `node_gap_y = 30`

建议 lane 基线：
- `mid_y = canvas_h * 0.52`
- `top_y = mid_y - lane_gap - avg_h(top_lane)`
- `bottom_y = mid_y + lane_gap + avg_h(bottom_lane)`

初始 y 放置：
- spine 节点：`y = mid_y - h/2`（主干尽量水平对齐）
- top lane：`y = top_y - h/2`
- bottom lane：`y = bottom_y - h/2`

附着（attachment）规则（使边更短、结构更像论文图）：
- 对 aux 节点（role=aux）：
  - 若文本/语义包含 `loss`：放在 anchor 的右侧上方（优先 top lane），`y = anchor_y - (anchor_h/2 + h/2 + node_gap_y)`
  - 若包含 `memory/bank/prototype`：放在 anchor 附近（同 lane），可右侧上方或右侧
- 对 VLM output（role=output）：放在 anchor 右侧同 lane 或略下（如果它还有 downstream 到 pseudo 分支）
- 对 pseudo label（通常 aux 或 output-like）：放在 pseudo generator 下方（bottom lane）并与 pred map 做近邻（可通过 `edge pred -> pseudo_generator` 推导）

### 5.3 碰撞消解（必须有）

因为 node 尺寸来自真实素材+文本估算，必然存在重叠风险。建议实现一个简单、可重复的 resolver：

1. 遍历所有 bbox，检测重叠（AABB overlap）
2. 若重叠：
   - 优先移动“非 spine 且非 input/output”的节点
   - 按 lane 方向移动（top 向上推、bottom 向下推、mid 尽量少动）
   - 每次移动最小距离：`overlap_y + node_gap_y`
3. 迭代最多 N 次（如 80 次），否则扩大 `lane_gap` 再重试

### 5.4 画布自适配（fit-to-canvas）

计算所有节点 bbox 的整体包围盒 `B`：
- 若 `B` 超出可用区域（canvas - margin）：
  - 做统一缩放 `s = min(usable_w/B.w, usable_h/B.h)`（s<1）
  - 对所有节点的 `(x,y,w,h)` 同步缩放，并整体平移到居中
- 若 `B` 太小（利用率 < 0.45）：
  - 优先增大 `col_gap` / `lane_gap`（而不是拉伸节点）

输出建议在 `layout_json.meta` 记录：
- `scale_factor`
- `utilization`
- `iterations`

---

## 6. 与当前仓库的对接建议（实现落地）

### 6.1 agent 形态

新增 `dataflow_agent/agentroles/p2g_filmstrip_layout_engine_agent.py`：
- 不调用 LLM（类似 `p2g_chunk_vlm_designer_agent`）
- 输入 `FilmStripP2GState`，写回 `state.layout_json`
- 记录 `state.agent_results["p2g_filmstrip_layout_engine_agent"] = {"status":"ok","stats":...}`

### 6.2 依赖与实现细节

- 文本测量：PIL 已存在（repo 当前环境 `PIL 12.0.0`）。
- 字体选择：在实现中提供 fallback 列表（DejaVuSans/Noto/Lato）。
- 不要引入重依赖（networkx/ortools）作为 MVP；先用确定性 DP + 简易碰撞消解即可。

### 6.3 输出兼容性

Stage7 如复用 `PPTXBuilder`：
- 需要 `layout_json.positions.nodes`
- edges 来源：`PPTXBuilder` 当前从 `semantic_json.edges` 读取。Filmstrip pipeline 只有 `node_graph_json.edges`，建议 Stage7 wrapper 将其映射为 `semantic_json={"edges": node_graph_json["edges"]}` 传入 composer。

---

## 7. 针对当前示例（`tests/.tmp/filmstrip_p2g_pipeline`）的期望布局特征

从输入图可推导的结构（示例 ids）：
- 主干：`n1 -> n3 -> n5 -> n6 -> n9 -> n10`
- 上分支：`n6 -> n7 -> n8` 且 `n2 -> n8`
- 下分支：`n6 -> n11 -> n13 -> n14` 且 `n11 -> n12 -> n13` 且 `n10 -> n13`
- loss：`n10/n14 -> n15`
- VLM group：`g1=[n1,n10,n14]` 只保证风格一致与尺度一致，不要求同一行

对应布局应自然呈现：
- `n1` 在左侧输入区（anchor `n3` 左边）
- `n10` 在 decoder 右侧输出区（anchor `n9` 右边）
- `n14` 在 pseudo generator 下方或右下（anchor `n13` 下方）
- `n8` 与 `n15` 作为 loss，贴附在各自监督来源附近（top/right）

