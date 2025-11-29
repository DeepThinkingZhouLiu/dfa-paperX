0. json_schema 解析说明（基于 v0.5）
- 需要分别生成 header_json_desc, semantic_json_desc, layout_json_desc, design_json_desc，结构为对应 JSON 片段 + 字段中文说明。
- v0.5 中不再区分 header/semantic/layout/design 四个独立 JSON，而是一个统一的 PaperGraph 对象，可按以下方式拆解：
- 1. header_json: 顶层元信息相关字段
    - 包含：`version`, `canvas`, `layout_flow`。
- 2. semantic_json: 语义结构相关字段
  - 包含：`chunks`, `nodes`, `edges`。
- 3. layout_json: 布局结果相关字段
  - 包含：`positions`（含 `positions.chunks`, `positions.nodes`）。
- 4. design_json: 美学与渲染相关字段
    - 包含：`global_theme`, `node_render`。


1. target解析 (p2g_target_analyst) 

- 职责：将简洁的 target 扩展为详细、丰富的自然语言描述。
- 输入 (from Paper2GraphRequest)Paper2GraphRequest.get("target")
- 处理：这是一个纯 LLM 调用，通过prompt来强化target
 - 输出 (to Paper2GraphState)：return {"enriched_description": {"semantic_desc": "...", "layout_desc": "..."}}



2. 语义构建 (p2g_semantic_constructor)

- 职责：从 Paper2GraphState 读取 enriched_description.semantic_desc，分析并设计所有逻辑元素，并写入 Paper2GraphState.semantic_json
- 输入：Paper2GraphState.enriched_description.semantic_desc + semantic_json_schema + semantic_json_desc
- 处理逻辑：
  - 1. 根据 semantic_json.semantic_json_schema 与 semantic_json_desc，结合 enriched_description.semantic_desc, 调用 llm server 生成 Paper2GraphState.semantic_json；
  - 2. 辅助工具可在生成后进行语义一致性简单校验（可选）
- 输出：写入 Paper2GraphState.semantic_json。


3. 布局构建 (p2g_layout_constructor)

- 职责：读取 Paper2GraphState.semantic_json，并调用 llm server 先给出一版布局信息，再调用外部库求解具体布局；
- 输入：Paper2GraphState.enriched_description.schema_desc 和 enriched_description.layout_desc, Paper2GraphState.semantic_json, layout_json_schema 和 layout_json_desc
- 处理：
  1. 根据 Paper2GraphState.enriched_description.schema_desc 和 enriched_description.layout_desc, Paper2GraphState.semantic_json, layout_json_schema 和 layout_json_desc，调用 llm server，生成 Paper2GraphState.layout_json_step1
  2. 需要定义调用 elk 库求解布局的 tool，写入 dataflow_agent/toolkits/papergraphtool 路径
  3. 根据 layout_json_desc、Paper2GraphState.semantic_json 和 Paper2GraphState.layout_json_step1，调用布局求解 tool 执行精确布局求解，生成 Paper2GraphState.layout_json_step2
  4. 将结果 layout_json_schema_step2 写入 Paper2GraphState.layout_json.
  5. 若有 layout_error_info，则根据其报错信息，调用 llm server 重新执行 1-4
- 输出：写入 Paper2GraphState.layout_json。

4. 美学设计构建 (p2g_designer)

- 职责：读取 Paper2GraphState.enriched_description + Paper2GraphState.semantic_json + Paper2GraphState.layout_json，并调用 llm server 设计精细的 VLM prompt（重点）。
- 输入：Paper2GraphState.enriched_description + Paper2GraphState.semantic_json + Paper2GraphState.layout_json + design_json_schema + design_json_desc
- 处理：
  1. 将 Paper2GraphState.enriched_description + Paper2GraphState.semantic_json + Paper2GraphState.layout_json + design_json_schema + design_json_desc 作为参数插入 prompt，调用 llm server 生成各个 node 对应的 vlm prompt，写入 输入：Paper2GraphState.design_json.
  2. 将 Paper2GraphState.semantic_json、Paper2GraphState.layout_jso 和 Paper2GraphState.design_json 组装为 Paper2GraphState.desc_json（描述图像的完整 json，需要根据 json_schema 进行字段完备性检查）。
- 输出：写入 Paper2GraphState.design_json 和 Paper2GraphState.desc_json。

5. 布局Checker (p2g_layout_checker)

- 职责：对布局进行几何验证。
- 输入：读取 Paper2GraphState.layout_json.
- 处理：
  1. 检查 layout_json.positions 中的坐标和布局信息是否存在重叠或越界；若不通过，返回 p2g_layout_constructor，并将 layout_error_info(str) 写入 Paper2GraphState。
  2. 调用 Pillow 绘制线框图（节点用方框代替，绘制完整 edges/chunk），保存为 wireframe.png，图片路径写入 Paper2GraphState.wireframe_url
  3. 调用 VLM 对线框图进行布局检查；若存在问题，则生成 layout_error_info 写入 Paper2GraphState （流程同 1）。
 - 输出 (to State & Conditional Edge)：
  - return {"layout_error_info"（如有）: "...", "wireframe_url": "..."}
  - 路由逻辑：
    - if layout_error_info: -> 路由到 布局构建 (3)
    - else: -> 路由到 语义Checker (6)

6. 语义Checker (p2g_semantic_checker)
- 职责：验证线框图是否与用户的原始 target 一致。
- 输入：Paper2GraphState.enriched_description ， Paper2GraphState.wireframe_url
- 处理：
  - 1. 调用 vlm 读取线框图 wireframe_url ，同时 输入：enriched_description 作为参数塞入 vlm 的 prompt ，检查线框图与 enriched_description 是否具有一致性，
  - 2. 如果线框图的语义和 enriched_description 存在 gap ，则生成 semantic_gap 并写入 Paper2GraphState ，流转到 p2g_semantic_constructor 处理；
- 输出：
  - Paper2GraphState.semantic_gap (如有)
  - 路由逻辑:
    - if Paper2GraphState.semantic_gap : -> 路由到 语义构建 (2)
    - else -> end

workflow流程图：
graph TD
    A[target解析] --> B[语义构建]
    B --> C[布局构建]
    C --> D[美学设计构建]
    D --> E[布局checker\n用pillow库构建线框图，调用vlm进行布局检查]
    E -- no --> C
    E -- yes --> F[语义checker\n调用vlm分析线框稿，分析与target是否存在gap]
    F -- yes --> G[渲染]
    F -- no --> B


  - header_json
```json
{
  "header_json_schema": {
    "version": "0.5",
    "canvas": {"width": 1920, "height": 1080, "unit": "px"},
    "layout_flow": "left-to-right"
  },
  "header_json_desc": {
    "version": "json结构的版本信息，当前版本为0.5",
    "canvas": "画布的大小，由width和height两个参数控制，单位是px, 默认大小为 1920 x 1080",
    "layout_flow": "图中内容的方向，默认是 left-to-right, 比如 U-net 这样的架构可能取 up-to-down 或 down-to-up"
  }
}
```

- semantic_json
```json
{
  "semantic_json_schema": {
    "chunks": [
      {
        "chunk_id": "c1",
        "title": "Training Pipeline",
        "title_bbox": {"x": 672,  "y": 54, "w": 576, "h": 86},
        "summary": "Overall training pipeline for the proposed model.",
        "node_ids": ["n1", "n2", "n3", "n4", "n5"]
      }
    ],
    "nodes": [
      {"node_id": "n1", "node_type": "text_block",  "chunk_id": "c1", "desc": "Training Pipeline"},
      {"node_id": "n2", "node_type": "shape",       "chunk_id": "c1", "desc": "Raw Data"},
      {"node_id": "n3", "node_type": "shape",       "chunk_id": "c1", "desc": "Encoder"},
      {"node_id": "n4", "node_type": "shape",       "chunk_id": "c1", "desc": "Predictions"},
      {"node_id": "n5", "node_type": "annotation",  "chunk_id": "c1", "desc": "We freeze encoder weights."}
    ],
    "edges": [
      {"edge_id": "e1", "from": "n2", "to": "n3"},
      {"edge_id": "e2", "from": "n3", "to": "n4"}
    ]
  },
  "semantic_json_desc": {
    "chunks": "有5个参数：
    (1) chunk_id: chunk的唯一id，命名规则为 c1,c2...,; 
    (2) title: chunk的title名称，不存在时可置空; 
    (3)title_bbox: chunk title的bbox, 通过参数x,y,w,h这4个参数控制，单位是px;  
    (4) summary: 用于描述该chunk的内容和功能; 
    (5) node_ids: 该chunk包含的node的id列表。",
    "nodes": "有4个参数：
    (1) node_id: node 的唯一id，命名规则为 n1,n2...,; 
    (2) node_type: node 的类型，取值只能来自于以下列举的类型：  
        - text_block: 文本框（标题、正文、说明等）。
        - shape: 模块框/流程框等形状。
        - image_placeholder: 图片或子图占位。
        - table_placeholder: 表格占位。
        - annotation: 注释、备注、脚注等说明性元素。; 
    (3) chunk_id: 当前 node 所属的 chunk 的 id；
    (4) desc: 详细描述该 node 的内容和功能; ",
    "edges": "有3个参数：
    (1) edge_id: edge 的唯一id，命名规则为 e1,e2...,; 
    (2) from: 当前 edge 的起点对应的 node_id; 
    (3) to: 当前 edge 的止点对应的 node_id;",
  }
}
```

- layout_json
```json
{
  "layout_json_schema": {
    "positions": {
      "chunks": [
        {"chunk_id": "c1", "bbox": {"x": 96, "y": 36,  "w": 728, "h": 972}}
      ],
      "nodes": [
        {"node_id": "n1", "bbox": {"x": 672,  "y": 54,  "w": 576, "h": 86}},
        {"node_id": "n2", "bbox": {"x": 192,  "y": 324, "w": 384, "h": 129}},
      ]
    }
  },

  "layout_json_desc": {
    "positions": "有 2 个参数：
    (1) chunks: 格式为 {chunk_id, bbox}, 其中 chunk_id 为当前 chunk 的 id, bbox 为当前 chunk 的边界框范围, 由 x,y,w 和 h 这四个参数控制, (x, y) 表示矩形边界框左上角顶点坐标, w 和 h 分别表示矩形边界框框的宽度与高度; 
    (2) nodes: 格式为 {node_id, bbox}, 其中 node_id 为当前 node 的 id, bbox 为当前 node 的边界框范围, 由 x,y,w 和 h 这四个参数控制, (x, y) 表示矩形边界框左上角顶点坐标, w 和 h 分别表示矩形边界框框的宽度与高度; 
  }
}
```



- design_json
```json
{
  "design_json_schema": {
      "global_theme": "NeurIPS-style clean diagram with light background and minimal colors.",
      "node_render": {
        "n1": {"render_method": "pptx"},
        "n2": {"render_method": "vlm", "vlm_prompt": "Icon of raw dataset or CSV file."},
        "n3": {"render_method": "vlm", "vlm_prompt": "Neural network block representing encoder."},
        "n4": {"render_method": "vlm", "vlm_prompt": "Output predictions icon."},
        "n5": {"render_method": "pptx"}
    }
  },
  "design_json_desc": {
    "global_theme": "用于描述图像的全局风格特征，例如学术论文风格，卡通风格等。默认取值为学术论文模型图风格",
    "node_render": "格式为: node_id: {render_method, vlm_prompt?}, 每个 node_id 中含有 2 个参数：
    (1) render_method: 该 node 的渲染方式，有且仅有两种取值: pptx 和 vlm, pptx 表示下游直接使用 pptx 进行渲染，例如文本框、ppt中常见形状等；vlm 表示下游通过调用 vlm 生图模型来绘制该 node；
    (2) vlm_prompt: 当且仅当 render_method 为 vlm 时需要写入该字段，用于下游调用 vlm 生成当前节点内容的 prompt 。",
  }
  
}
```