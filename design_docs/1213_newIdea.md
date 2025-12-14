# 系统设计文档：基于自底向上策略的可编辑科研绘图生成器

**System Design Document: Bottom-Up Editable Scientific Figure Generator**

## 1. 项目概览 (Project Overview)

**目标：** 构建一个 Agent workflow，将用户的自然语言描述转化为完全可编辑的 PPTX 格式科研绘图。

**核心理念：** "Content-First, Bottom-Up"（内容优先，自底向上）。与传统"先定布局再填空"（容易导致图片拉伸变形）的方法不同，本系统采用以下流程：

1. 先生成或实例化所有素材（Visual Assets & Text）
2. 获取素材的固有尺寸 (Intrinsic Dimensions)
3. 基于固有尺寸和拓扑关系计算布局
4. 渲染为 PPTX，确保图像无变形、风格统一且全元素可编辑

## 2. 系统架构 (System Architecture)

系统由四个顺序执行的模块组成：

- **规划器 (The Planner)：** 基于 LLM，将自然语言解析为结构化的场景图 (Scene Graph)
- **资产工厂 (The Asset Factory)：**
  - VLM 流水线：使用"连环画策略 (Film Strip)"生成视觉素材
  - 图像处理：执行智能切片算法，并测量素材尺寸
- **布局引擎 (The Layout Engine)：** 基于拓扑排序计算所有节点的 $(x, y)$ 坐标
- **渲染器 (The Renderer)：** 使用 python-pptx 组装 Image Slices、Native Shapes 和 Connectors

## 3. 数据结构 (Data Structures)

全流程通过统一的 JSON Schema 进行状态传递。

```json
{
  "canvas": {
    "width_inches": 13.33,
    "height_inches": 7.5
  },
  "nodes": [
    {
      "id": "node_input_img",
      "type": "IMAGE_VLM",
      "group_id": "group_data_stream",
      "content_desc": "A street view input image",
      "visual_style": "photorealistic",
      "estimated_size": {"w": 0, "h": 0},
      "final_pos": {"x": 0, "y": 0}
    },
    {
      "id": "node_backbone",
      "type": "SHAPE_PPTX",
      "shape_type": "TRAPEZOID",
      "text_content": "SegFormer Backbone",
      "style": {"fill_color": "blue", "opacity": 0.5},
      "estimated_size": {"w": 2.5, "h": 3.5}
    }
  ],
  "edges": [
    {
      "source": "node_input_img",
      "target": "node_backbone",
      "label": "Patch Embedding",
      "connector_type": "ELBOW"
    }
  ],
  "groups": [
    {
      "id": "group_data_stream",
      "type": "FILM_STRIP",
      "members": ["node_input_img", "node_pred_map", "node_pseudo_label"],
      "prompt_instruction": "Generate 3 horizontal panels side-by-side with white spacing..."
    }
  ]
}
```

**字段说明：**
- `group_id`: 关键字段，用于 Film Strip 分组生成
- `estimated_size`: 由 Asset Factory 填充
- `final_pos`: 由 Layout Engine 填充

## 4. 模块详细设计 (Module Specifications)

### Module 1: 规划器 (The Planner)

**角色：** 大脑 (Brain)

**输入：** 用户 Prompt

**输出：** 完整的 JSON Scene Graph

**关键逻辑：**

- **节点分类：**
  - `IMAGE_VLM`：具体的视觉数据（如：输入图、分割掩码、特征热力图）
  - `SHAPE_PPTX`：抽象的架构组件（如：卷积层、Backbone、Loss 函数框）

- **分组策略 (Grouping)：**
  - 识别具有强语义关联的 VLM 节点（如 Input 和 Output），将其放入同一个 Group
  - 目的：确保通过一次 VLM 调用生成一张"并排图"，保证内容对齐（Consistency）

### Module 2: 资产工厂 (The Asset Factory)

**角色：** 制造商 (Manufacturer)

#### 任务 A: 组合生成 (The Film Strip Generation)

- 遍历所有 `type == "FILM_STRIP"` 的组
- **Prompt 构造：** 强制 VLM 生成 "Grid Layout" 或 "Horizontal Strip"，要求纯白背景，禁止包含文字

#### 任务 B: 智能切分 (Smart Slicing)

**输入：** VLM 生成的大图

**算法 (使用 numpy):**
- 检测全白像素列 `(np.all(col > 250))`
- 根据白/非白跳变点确定切分边界
- 裁剪出子图并保存为 PNG

**回写：** 将子图路径和实际像素尺寸 (转换英寸) 更新到 JSON 的 `node.estimated_size`

#### 任务 C: 文本测量

对于 `SHAPE_PPTX` 节点，根据字数预估文本框尺寸

### Module 3: 布局引擎 (The Layout Engine)

**角色：** 建筑师 (Architect)

**输入：** 带有尺寸信息的 JSON

**算法建议：分层图布局 (Layered Graph Drawing)**

- **层级分配 (Rank Assignment)：**
  - 构建 DAG（有向无环图）
  - 计算每个节点的 Rank（Input=0, Backbone=1, Decoder=2, Output=3）

- **坐标计算：**
  - X 轴：$X = Margin + (Rank \times ColumnWidth)$
  - Y 轴：在同一 Rank 内，计算所有节点的高度总和，进行垂直居中分布

- **约束：** 确保节点 bbox 不重叠

**输出：** 更新每个节点的 `final_pos`

### Module 4: 渲染器 (The Renderer)

**角色：** 施工队 (Builder)

**技术栈：** python-pptx

**执行步骤：**

1. **放置图片：** 读取 `IMAGE_VLM` 节点的路径，插入到 `final_pos`
2. **绘制形状：** 在 `final_pos` 绘制 `SHAPE_PPTX` (矩形、梯形等)，填充文本
3. **连接线 (Connectors)：** 使用 `shapes.add_connector`

**关键点：** 必须使用 `.begin_connect(shape_obj, idx)` 和 `.end_connect(shape_obj, idx)`。这确保生成的线条物理吸附在形状上，用户拖动形状时线条会自动跟随。

## 5. 开发提示 (Implementation Hints for AI)

### 关于切图算法

> 在实现 `processor.py` 时，请使用 numpy 向量化操作来检测白色列。不要使用慢速的 Python 循环。逻辑是寻找 diff 不为 0 的索引作为切分点。

### 关于 PPTX 连接器

> 在实现 `renderer.py` 时，注意 python-pptx 的连接器需要具体的 shape 对象引用。请建立一个 `id -> shape_object` 的字典映射，以便在绘制 Edge 时能找到 Source 和 Target。

### 关于布局计算

> 在 `layout.py` 中，不需要实现复杂的力导向算法。对于科研绘图，简单的基于列的布局 (Column-based Layout) 通常最整洁。Input 在左，Output 在右，处理模块在中间。

---------------------------------------------------------------------------------------------------------------------------------------------------------------------


我是需要搭建一个Agent workflow工作流，我期望有以下Agent节点：

1.根据target，分析需要绘制哪些nodes

2.分析nodes中，有哪些需要pptx渲染，哪些需要vlm渲染

3.在vlm渲染的nodes中，进一步分析哪些nodes之间存在明显的关联关系或需要保持一致性，对nodes进行分组，并给出各个nodes组的vlm绘图prompt，供下游vlm绘制“连环画”消费

4.在pptx渲染的nodes中，大多是文本框和基础形状，需要用一个字段说明文本框中的文字是什么，包括文本框的形状，以及基础形状的具体形状（例如梯形，也需要描述方向），供下游pptx渲染nodes消费

5.调用vlm绘制“连环画”，并进行去背景+抠图，保存到路径，但需要注意”连环画“中子图与nodes的对应关系需要正确

6.根据vlm绘制的nodes大小和pptx渲染的文本框、形状，设计整体布局

7.根据布局设计，渲染组装出最终的pptx。

------
> 我之前设计的科研绘图pipeline见tests/test_chunk_p2g_pipeline.py,但效果非常不理想.我现在有了新的idea:1.根据target，分析需要绘制哪些nodes

2.分析nodes中，有哪些需要pptx渲染，哪些需要vlm渲染

3.在vlm渲染的nodes中，进一步分析哪些nodes之间存在明显的关联关系或需要保持一致性，对nodes进行分组，并给出各个nodes组的vlm绘图prompt，供下游vlm绘制“连环画”消费

4.在pptx渲染的nodes中，大多是文本框和基础形状，需要用一个字段说明文本框中的文字是什么，包括文本框的形状，以及基础形状的具体形状（例如梯形，也需要描述方向），供下游pptx渲染nodes消费

5.调用vlm绘制“连环画”，并进行去背景+抠图，保存到路径，但需要注意”连环画“中子图与nodes的对应关系需要正确

6.根据vlm绘制的nodes大小和pptx渲染的文本框、形状，设计整体布局

7.根据布局设计，渲染组装出最终的pptx。  请你分析思考这个Agent workflow的可行性与优化建议 
  ⎿  ⧉ Selected 13 lines from design_docs/1213_newIdea.md in Visual Studio Code

● 我来分析你的新 pipeline 设计。首先让我看一下现有的实现，了解之前的问题所在。

● Read(tests/test_chunk_p2g_pipeline.py)
  ⎿  Read 496 lines

● Read(design_docs/chunk_based_pipeline_design.md)
  ⎿  Read 588 lines

● 我已经阅读了你现有的 chunk-based pipeline 设计和测试代码。现在让我分析你的新 idea 与现有方案的对比，并给出可行性分析和优化建议。

  ---
  新旧方案对比分析

  现有 Chunk-Based Pipeline 的问题

  从你的设计文档和测试代码来看，现有方案的核心流程是：

  target → semantic_json → chunk_layout → vlm_prompt → vlm_render → pptx_compose

  主要问题：

  1. "先布局后渲染"的顺序问题：在 VLM 渲染之前就确定了 chunk 的 bbox，但 VLM 生成的图像尺寸和内容是不可控的，导致最终需要拉伸/裁剪来适配预设布局
  2. VLM 渲染整个 chunk：每个 chunk 包含多个 nodes，VLM 一次性渲染整个 chunk，但：
    - VLM 对复杂布局的控制力弱
    - chunk 内部 nodes 的位置难以精确控制
    - 需要 SAM 后处理来提取 nodes（增加复杂度和失败点）
  3. PPTX 可编辑性差：最终 PPTX 中的元素是图片，不是原生形状/文本框

  ---
  你的新 Idea 分析

  你的新方案核心改变是 "Content-First, Bottom-Up"：

  1. 分析 nodes → 2. 分类(VLM/PPTX) → 3. VLM nodes 分组 → 4. 生成"连环画"
  → 5. 切图+去背景 → 6. 基于实际尺寸布局 → 7. PPTX 组装

  可行性评估

  | 步骤              | 可行性 | 风险点                                     |
  |-------------------|--------|--------------------------------------------|
  | 1. 分析 nodes     | ✅ 高  | LLM 理解能力足够                           |
  | 2. 分类 VLM/PPTX  | ✅ 高  | 规则明确：具象图像→VLM，抽象形状/文本→PPTX |
  | 3. VLM nodes 分组 | ⚠️ 中  | 分组策略需要精心设计                       |
  | 4. 连环画生成     | ⚠️ 中  | VLM 对"并排多图"的控制力有限               |
  | 5. 切图+去背景    | ⚠️ 中  | 白色分隔线检测可能不稳定                   |
  | 6. 基于尺寸布局   | ✅ 高  | 确定性算法，可控                           |
  | 7. PPTX 组装      | ✅ 高  | python-pptx 成熟                           |

  核心优势

  1. "先内容后布局" 解决了尺寸不匹配问题
  2. VLM/PPTX 分离 让文本框、基础形状用原生 PPTX 元素，真正可编辑
  3. 连环画策略 保证同组 nodes 风格一致

  ---
  优化建议

  1. 关于 VLM Nodes 分组（步骤 3）

  问题：如何判断哪些 nodes 需要"保持一致性"？

  建议：定义明确的分组规则：

  # 分组策略
  GROUP_RULES = {
      "same_data_flow": True,      # 同一数据流的 input/output 图像
      "same_visual_type": True,    # 同类型视觉元素（如多个特征图）
      "comparison_pair": True,     # 对比关系的元素
      "max_group_size": 4,         # 单组最多 4 个，避免连环画太长
  }

  2. 关于连环画生成（步骤 4）

  问题：VLM 对"并排多图"的控制力有限，可能生成的子图大小不一致。

  建议：

  方案 A（推荐）：强约束 Prompt
  - 明确指定 "Generate exactly N panels, each 512x512 pixels"
  - 要求 "Pure white (#FFFFFF) background, 20px white gap between panels"
  - 添加 "Each panel must be a complete, self-contained image"

  方案 B：单图生成 + 风格迁移
  - 先生成第一个 node 作为"风格锚点"
  - 后续 nodes 的 prompt 中引用第一个图的风格描述
  - 牺牲一致性换取可控性

  3. 关于切图算法（步骤 5）

  问题：白色分隔线检测可能因为：
  - VLM 生成的白色不是纯白
  - 图像内容本身有白色区域

  建议：

  def smart_slice(image: np.ndarray, expected_count: int) -> List[np.ndarray]:
      """
      改进的切图算法
      """
      # 1. 先尝试纯白列检测
      white_cols = detect_white_columns(image, threshold=250)

      # 2. 如果检测到的分隔数量不对，使用等分策略
      if len(white_cols) != expected_count - 1:
          # 回退到等分
          return equal_split(image, expected_count)

      # 3. 验证每个子图的有效性（非空、有内容）
      slices = split_by_columns(image, white_cols)
      valid_slices = [s for s in slices if has_content(s)]

      return valid_slices

  4. 关于 PPTX Nodes 的设计（步骤 4 补充）

  建议：为 PPTX 渲染的 nodes 定义更丰富的 schema：

  {
    "node_id": "n_backbone",
    "render_type": "PPTX",
    "pptx_spec": {
      "shape_type": "TRAPEZOID",
      "shape_params": {
        "direction": "right",  // 梯形方向
        "ratio": 0.7           // 上底/下底比例
      },
      "text": {
        "content": "SegFormer Backbone",
        "font_size": 14,
        "font_color": "#FFFFFF",
        "alignment": "center"
      },
      "style": {
        "fill_color": "#4A90D9",
        "fill_opacity": 0.9,
        "border_color": "#2E5A8C",
        "border_width": 2
      },
      "estimated_size": {
        "width_inches": 2.5,
        "height_inches": 1.2
      }
    }
  }

  5. 关于布局引擎（步骤 6）

  建议：采用分层图布局（Layered Graph Drawing）+ 约束求解：

  def compute_layout(nodes: List[Node], edges: List[Edge], canvas: Canvas) -> Layout:
      """
      基于实际尺寸的布局算法
      """
      # 1. 拓扑排序，确定层级
      ranks = topological_rank(nodes, edges)

      # 2. 计算每层的总高度
      layer_heights = {}
      for rank, layer_nodes in ranks.items():
          layer_heights[rank] = sum(n.actual_height for n in layer_nodes) + gaps

      # 3. X 坐标：基于层级
      max_width_per_layer = compute_max_widths(ranks)
      x_positions = cumulative_x(max_width_per_layer, margin=50, gap=80)

      # 4. Y 坐标：层内垂直居中
      for rank, layer_nodes in ranks.items():
          y_positions = center_distribute(layer_nodes, canvas.height)

      # 5. 检查重叠，必要时调整
      resolve_overlaps(nodes)

      return Layout(nodes)

  ---
  整体架构建议

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                    New Bottom-Up P2G Pipeline                                │
  └─────────────────────────────────────────────────────────────────────────────┘用户输入 (target)
             │
             ▼
      ┌─────────────────────────────┐
      │  1. Node Analyzer Agent     │  分析需要哪些 nodes
      │     (LLM)                   │  输出: nodes[], edges[]
      └─────────────────────────────┘
             │
             ▼
      ┌─────────────────────────────┐
      │  2. Node Classifier         │  分类: VLM_NODES vs PPTX_NODES
      │     (Rule-based)            │  输出: vlm_nodes[], pptx_nodes[]
      └─────────────────────────────┘
             │
             ├──────────────────────────────────┐
             ▼                                  ▼
      ┌─────────────────────────────┐    ┌─────────────────────────────┐
      │  3a. VLM Group Planner      │    │  3b. PPTX Spec Generator    │
      │     (LLM)                   │    │     (LLM)                   │
      │  - 分组 + 连环画 prompt      │    │  - 形状/文本框详细规格       │
      └─────────────────────────────┘    └─────────────────────────────┘
             │                                  │
             ▼                                  │
      ┌─────────────────────────────┐           │
      │  4. Film Strip Renderer     │           │
      │     (VLM API)               │           │
      │  - 生成连环画图像│           │
      └─────────────────────────────┘           │
             │                                  │
             ▼                                  │
      ┌─────────────────────────────┐           │
      │  5. Image Processor         │           │
      │     (numpy/PIL)             │           │
      │  - 切图 + 去背景 + 测尺寸    │           │
      └─────────────────────────────┘           │
             │                                  │
             ├──────────────────────────────────┘
             ▼
      ┌─────────────────────────────┐
      │  6. Layout Engine           │  基于所有 nodes 的实际尺寸
      │     (Algorithm)             │  计算最终布局
      └─────────────────────────────┘
             │
             ▼
      ┌─────────────────────────────┐
      │  7. PPTX Composer           │  组装最终 PPTX
      │     (python-pptx)           │  - VLM 图片 + PPTX 原生形状
      └─────────────────────────────┘│
             ▼
      最终输出: PPTX (图片+原生形状，全可编辑)

  ---
  总结

  你的新 idea 方向正确，核心改进点：

  1. "先内容后布局" - 解决尺寸不匹配的根本问题
  2. VLM/PPTX 分离 - 提升可编辑性
  3. 连环画策略 - 保证风格一致性

  主要风险点：
  - 连环画生成的可控性（建议用强约束 prompt + 回退策略）
  - 切图算法的鲁棒性（建议加入 expected_count 验证）

  建议优先实现：先做一个最小可行版本，验证"连环画生成 → 切图"这个核心环节的可行性，再扩展完整 pipeline。

> 我刚才测试过You are a scientific illustrator. Generate ONE single image composed of 3 sub-panels arranged horizontally (side-by-side) with white space in between. Subject: A street view 
scene (Cityscapes style). Panel 1 (Left): The raw photorealistic input image of a street with a car and road. Panel 2 (Middle): The 'Predicted Segmentation Map' of the EXACT SAME scene from 
Panel 1. Use solid flat colors (blue for background, pink for road, green for car). It should look somewhat coarse. Panel 3 (Right): The 'Pseudo-label Map' of the EXACT SAME scene. Similar to
 Panel 2 but with some noise or missing regions (black holes) to represent weak supervision artifacts. Constraint: Do not add any text or labels inside the image. Pure visual data 
only.这个prompt生成了连环画,效果非常不错 

● 太好了！这个测试结果验证了"连环画策略"的可行性。让我分析一下这个成功 prompt 的关键要素，并给出 pipeline 设计建议。

  ---
  成功 Prompt 的关键要素分析

  ✅ 明确的结构约束: "ONE single image composed of 3 sub-panels arranged horizontally"
  ✅ 空间关系描述: "side-by-side with white space in between"
  ✅ 内容一致性强调: "EXACT SAME scene from Panel 1"
  ✅ 每个 panel 的具体描述: Panel 1/2/3 分别是什么
  ✅ 视觉风格约束: "solid flat colors", "coarse", "black holes"
  ✅ 负面约束: "Do not add any text or labels"

  ---
  基于此的 Prompt 模板设计

  FILM_STRIP_PROMPT_TEMPLATE = """
  You are a scientific illustrator. Generate ONE single image composed of {panel_count} sub-panels arranged {arrangement} with white space in between.

  Subject: {subject_description}

  {panel_descriptions}

  Constraints:
  - All panels must depict the EXACT SAME scene/subject for visual consistency
  - Do not add any text, labels, or annotations inside the image
  - Pure visual data only
  - Use pure white (#FFFFFF) background between panels
  """

  def generate_film_strip_prompt(group: NodeGroup) -> str:
      """为一组 VLM nodes 生成连环画 prompt"""

      panel_descriptions = []
      for i, node in enumerate(group.nodes):
          position = ["Left", "Middle", "Right", "Far Right"][i]
          panel_descriptions.append(
              f"Panel {i+1} ({position}): {node.visual_description}"
          )

      return FILM_STRIP_PROMPT_TEMPLATE.format(
          panel_count=len(group.nodes),
          arrangement="horizontally (side-by-side)",
          subject_description=group.subject,
          panel_descriptions="\n".join(panel_descriptions)
      )

  ---