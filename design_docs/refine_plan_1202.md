# Q1:
我调用tests/test_p2g_pptx_composer_agent.py生成的最终的pptx,最终效果如图tests/.tmp/output/image.png所示,最主要的问题是:1.调用vlm绘制的图片的比例 和 设计阶段nodes的bbox比例
 不一致,导致nodes扭曲比较严重
2.对于pptx直接渲染的ndoes,通常是一些文本框,但是设计阶段,bbox的大小并没有考虑填充这些文字信息需要占据的空间大小,导致很多nodes的文本内容超出node甚至chunk1的bbox
3.vlm绘制的nodes效果也比较一般,prompt可能需要进一步优化. 请你分析思考这三个问题,给出优化的建议


# A1:
现在我已经全面了解了代码结构和问题。让我针对你提出的三个问题进行深入分析并给出优化建议。

  ---
  问题分析与优化建议

  问题 1: VLM 图片比例与 bbox 比例不一致导致 nodes 扭曲

  根本原因分析：

  从 node_renderer.py:104-136 的 render_vlm_image 方法可以看到：

  self.slide.shapes.add_picture(
      image_path,Emu(left), Emu(top),
      Emu(width), Emu(height)  # 强制拉伸到 bbox 尺寸
  )

  VLM 生成的图片有其原始宽高比（通常是 1:1 或其他固定比例），但 layout_json.json 中的 bbox 比例各不相同。例如：
  - n3: w=227, h=51 → 宽高比 4.45:1
  - n7: w=161, h=230 → 宽高比 0.7:1
  - n39: w=533, h=153 → 宽高比 3.48:1

  当把正方形图片强制拉伸到这些不同比例的 bbox 时，必然导致严重扭曲。

  优化建议：

  方案 A: 在 VLM 生图时指定目标宽高比（推荐）

  在 p2g_vlm_node_renderer_agent.py 中，修改 VLM prompt 生成逻辑，将目标 bbox 的宽高比信息传递给 VLM：

  在 _render_single_node 或上游获取 bbox 信息
  修改 vlm_prompt，添加宽高比约束
  aspect_ratio = bbox_w / bbox_h
  vlm_prompt = f"""
  {original_prompt}

  IMPORTANT: Generate the image with aspect ratio approximately {aspect_ratio:.2f}:1 
  (width:height = {bbox_w}:{bbox_h}). The image should fit naturally into a 
  {bbox_w}x{bbox_h} pixel container without distortion.
  """

  方案 B: 在渲染时保持原始比例（居中/适应）

  修改 node_renderer.py 的 render_vlm_image 方法：

  def render_vlm_image(self, node_id, bbox_emu, image_path) -> bool:
      from PIL import Image

      # 获取原始图片尺寸
      with Image.open(image_path) as img:
          img_w, img_h = img.size

      left, top, width, height = bbox_emu
      bbox_ratio = width / height
      img_ratio = img_w / img_h

      # 计算适应后的尺寸（保持比例，居中放置）
      if img_ratio > bbox_ratio:
          # 图片更宽，以宽度为准
          new_width = width
          new_height = int(width / img_ratio)new_left = left
          new_top = top + (height - new_height) // 2
      else:
          # 图片更高，以高度为准
          new_height = height
          new_width = int(height * img_ratio)
          new_left = left + (width - new_width) // 2
          new_top = top

      self.slide.shapes.add_picture(
          image_path,
          Emu(new_left), Emu(new_top),
          Emu(new_width), Emu(new_height)
      )

  方案 C: 在设计阶段就考虑 VLM 图片的固定比例

  在 p2g_node_layout_planner_agent 的 prompt 中，对 VLM 类型的 nodes 添加约束：

  对于 render_method="vlm" 的节点，bbox 的宽高比应接近 1:1 或 4:3，
  因为 VLM 生成的图片通常是这些比例。

  ---
  问题 2: PPTX 文本框 bbox 未考虑文字内容所需空间

  根本原因分析：

  从 layout_json.json 可以看到，很多文本节点的 bbox 非常小：
  - n1 (标题): w=690, h=30 — 高度只有 30px，对于 24pt 字体来说太小
  - n2 (描述): w=659, h=37 — 12pt 字体多行文本，高度不足
  - n22: w=645, h=54 — 长文本，宽度可能不够

  p2g_node_layout_planner_agent 在规划布局时，只考虑了空间利用率和重叠检测，没有考虑文本内容的实际渲染尺寸。

  优化建议：

  方案 A: 在布局规划阶段估算文本所需空间（推荐）

  在 p2g_node_layout_planner_agent.py 中添加文本尺寸估算验证器：

  def _validate_text_bbox_size(self, content: str, parsed_result: Dict) -> Tuple[bool, Optional[str]]:
      """验证 PPTX 文本节点的 bbox 是否足够容纳文本内容"""
      chunk_res = self._extract_chunk_result(parsed_result)
      if not chunk_res:
          return True, None

      errors = []
      for node in chunk_res.get("nodes", []):
          node_id = node.get("node_id")
          render_method = self._get_render_method(node_id)  # 从 node_render_design 获取

          if render_method != "pptx":
              continue

          bbox = node.get("rel_bbox", {})
          w, h = bbox.get("w", 0), bbox.get("h", 0)

          # 获取该节点的文本内容和字体大小
          pptx_desc = self._get_pptx_desc(node_id)
          text_length = len(pptx_desc.get("text", ""))
          font_size = pptx_desc.get("text_style", {}).get("font_size", 12)

          # 估算所需尺寸（简化公式）
          # 假设每个字符宽度约为 font_size * 0.6，行高约为 font_size * 1.5
          char_width = font_size * 0.6 / 1920  # 转换为相对坐标
          line_height = font_size * 1.5 / 1080

          # 估算需要的行数
          chars_per_line = w / char_width if char_width > 0 else 1
          lines_needed = max(1, text_length / chars_per_line)
          min_height = lines_needed * line_height

          if h < min_height * 0.8:  # 允许 20% 容差
              errors.append(f"{node_id}: bbox 高度 {h:.2f} 不足以容纳文本（估算需要 {min_height:.2f}）")

      if errors:
          return False, "\n".join(errors)
      return True, None

  方案 B: 在 PPTX 渲染时启用自动调整

  修改 node_renderer.py 的 _render_text_box 方法：

  def _render_text_box(self, bbox_emu, spec):
      from pptx.enum.text import MSO_AUTO_SIZE

      left, top, width, height = bbox_emu
      txBox = self.slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
      tf = txBox.text_frame
      tf.word_wrap = True

      # 启用自动缩小字体以适应框
      tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
      # 或者：tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT  # 自动扩展框

  方案 C: 在 node_render_design 阶段就计算推荐尺寸

  在 p2g_node_render_design_agent 中，为每个 PPTX 节点输出一个 recommended_min_size：

  {
    "node_id": "n1",
    "render_method": "pptx",
    "pptx_desc": "...",
    "recommended_min_size": {
      "min_width": 0.35,
      "min_height": 0.05
    }
  }

  然后在 p2g_node_layout_planner_agent 中使用这个约束。

  ---
  问题 3: VLM 生成图片效果一般，prompt 需要优化

  根本原因分析：

  查看 node_render_design.json 中的 VLM prompt，存在以下问题：

  1. Prompt 过于冗长和复杂：例如 n3 的 prompt 有 300+ 字符，包含太多细节
  2. 缺乏一致的风格锚定：每个 prompt 都重复描述风格，但措辞不一致
  3. 缺少负面提示（negative prompt）：没有明确排除不想要的元素
  4. 没有指定输出尺寸/比例：如问题 1 所述

  优化建议：

  方案 A: 重构 VLM Prompt 模板（推荐）

  创建一个标准化的 prompt 模板：

  VLM_PROMPT_TEMPLATE = """
  [STYLE]
  Flat 2D vector illustration for academic paper. Clean lines, no shadows, no 3D effects.
  Morandi-style muted colors. White/transparent background.

  [CONTENT]
  {content_description}

  [CONSTRAINTS]
  - Aspect ratio: {aspect_ratio}
  - Color palette: {color_hints}
  - Must include label: "{label_text}"

  [NEGATIVE]
  Do NOT include: photorealistic elements, gradients, complex textures, 3D effects, shadows.
  """

  方案 B: 分离内容描述和风格描述

  在 p2g_node_render_design_agent 中，将 prompt 拆分为结构化字段：

  {
    "node_id": "n3",
    "render_method": "vlm",
    "vlm_content": "A rounded rectangle module with two icons: 'Expert Data' (document stack) and 'Initial LLM Policy' (brain icon). Label: 'Expert Data + Initial LLM 
  Policy'",
    "vlm_style": "muted_teal_module",
    "vlm_aspect_ratio": "4:1"
  }

  然后在 p2g_vlm_node_renderer_agent 中组装最终 prompt。

  方案 C: 添加参考图片（few-shot）

  如果 VLM 支持图片输入，可以提供参考图片：

  vlm_prompt = f"""
  Create an image similar in style to the reference image, but with the following content:
  {content_description}

  Reference style: [attached reference image of academic diagram]
  """

  方案 D: 优化具体 prompt 的写法

  针对当前 prompt 的具体改进：

  | 原始问题                                           | 优化建议                             |
  |------------------------------------------------|----------------------------------|
  | "A single, clean, rounded rectangle module..." | 简化为 "Rounded rectangle module:"  |
  | 重复 "flat 2D vector style"                      | 移到全局 style 前缀                    |
  | "White background" vs "transparent background" | 统一为 "transparent background"     |
  | 缺少尺寸约束                                         | 添加 "Output size: 400x100 pixels" |

  示例优化后的 prompt：

  [GLOBAL STYLE: Flat 2D vector, academic diagram, Morandi colors, transparent bg]

  Module: "Expert Data + Initial LLM Policy"
  - Shape: Rounded rectangle, muted teal (#66c2a5)
  - Left icon: Document stack (Expert Data)
  - Right icon: Brain/neural network (LLM Policy)
  - Text: Dark gray, sans-serif
  - Size: 400x100px (4:1 ratio)

  ---
  总结：优先级建议

  | 优先级 | 问题            | 推荐方案                              | 改动范围                                               |
  |-----|---------------|-----------------------------------|----------------------------------------------------|
  | P0  | VLM 图片比例扭曲    | 方案 A（prompt 中指定比例）+ 方案 B（渲染时保持比例） | p2g_vlm_node_renderer_agent.py, node_renderer.py   |
  | P1  | 文本框尺寸不足       | 方案 A（布局验证器）+ 方案 B（自动调整）           | p2g_node_layout_planner_agent.py, node_renderer.py |
  | P2  | VLM prompt 效果 | 方案 A（模板化）+ 方案 D（具体优化）             | p2g_node_render_design_agent.py 的 prompt           |

  需要我帮你实现其中某个具体的优化方案吗？


# Q2:
我觉得问题一的三个解决方案可以同时优化:1.在设计阶段就需要考虑根据node内容和含义来设计bbox 2.在调用vlm时传入bbox换算的比例 
3.渲染时不强制拉伸,可根据noded的宽或高进行等比例缩放即可,在bbox中居中放置  问题2:我觉得除了个别内容较短的文本框,其余的nodes都可以调用vlm来绘制,比如title之类的,这样能在一定程
度上增加可控性,因为让pptx渲染文本框,llm也不太能准确估计文本框的bbox,很有可能造成错乱,而且有的nodes用vlm绘制效果可能更好;
此外,你提到的两个方法都可以尝试加入:设计bbox时需要考虑内容(同问题一) ; 渲染时,文本框应该支持自适应; 尽量避免在文本框中塞入大段文本内容,比较复杂的nodes尽量都使用vlm绘制;
问题3:综合使用方案A和方案B,简化prompt的同时,把内容和风格,以及比例分别进行描述. 请你根据我的反馈和现状,仔细分析思考,给出一个优化方案

# A2:
我来仔细分析你的反馈，并结合现有代码结构给出一个完整的优化方案。让我先进一步了解相关的 agent 和 prompt 模板。

● Read(dataflow_agent/agentroles/p2g_node_render_design_agent.py)
  ⎿  Read 419 lines

● Read(dataflow_agent/promptstemplates/prompts_repo.py)
  ⎿  Read 2055 lines

● 我已经全面了解了代码结构和你的反馈。现在让我给出一个完整的优化方案。

  ---
  Paper2Graph 渲染优化方案

  一、问题总结与优化目标

  | 问题              | 根因                                    | 优化目标                   |
  |-----------------|---------------------------------------|------------------------|
  | VLM 图片比例扭曲      | 设计阶段未考虑 bbox 比例；VLM 生图未指定比例；渲染时强制拉伸   | 三阶段协同：设计→生图→渲染         |
  | 文本框内容溢出         | bbox 未考虑文本内容；LLM 难以准确估计；复杂内容用 pptx 渲染 | 更多使用 VLM；文本框自适应；内容感知设计 |
  | VLM prompt 效果一般 | prompt 冗长；风格/内容/比例混杂                  | 结构化 prompt：内容+风格+比例分离  |

  ---
  二、整体架构优化

  2.1 数据流优化

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                          优化后的数据流                                   │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                         │
  │  semantic_json ──► node_layout_planner ──► node_render_design│
  │       │                    │
  │       │                    ▼                      ▼                     │
  │       │            layout_jsonrender_design│
  │       │           (含 bbox 信息)          (含 aspect_ratio)             │
  │       │                    │                      │                     │
  │       │                    └──────────┬───────────┘                     │
  │       │                               ▼                                 │
  │       │vlm_node_renderer│
  │       │                    (使用 aspect_ratio)                          │
  │       │                │                                 │
  │       │                               ▼                                 │
  │       │                    pptx_composer                                │
  │       │                    (等比缩放+居中)                               │
  │       │                               │                                 │
  │       └───────────────────────────────┴──► 最终 PPTX                    │
  │                                                                         │
  └─────────────────────────────────────────────────────────────────────────┘

  2.2 关键改动点

  | 阶段     | 文件                               | 改动内容                                        |
  |--------|----------------------------------|---------------------------------------------|
  | 设计阶段   | p2g_node_layout_planner_agent.py | 根据 node 内容和渲染方式设计合理的 bbox 比例                |
  | 设计阶段   | p2g_node_render_design_agent.py  | 输出结构化 vlm_prompt（内容+风格+比例分离）；更多 node 使用 VLM |
  | 生图阶段   | p2g_vlm_node_renderer_agent.py   | 接收 bbox 比例，组装最终 prompt                      |
  | 渲染阶段   | pptx_composer/node_renderer.py   | VLM 图片等比缩放+居中；文本框自适应                        |
  | Prompt | prompts_repo.py                  | 更新相关 prompt 模板                              |

  ---
  三、详细优化方案

  3.1 设计阶段优化：p2g_node_layout_planner_agent

  目标：根据 node 内容和渲染方式设计合理的 bbox 比例

  改动 1：在 _build_chunk_context 中传入 render_method 信息

  # p2g_node_layout_planner_agent.py

  def _build_chunk_context(...):
      """为单个 chunk 构建上下文信息，包含渲染方式"""
      # ... 现有代码 ...

      # 新增：从 node_render_design 获取渲染方式
      render_method_map = {}
      for chunk in node_render_design.get("chunks", []):
          for node in chunk.get("nodes", []):
              render_method_map[node.get("node_id")] = node.get("render_method", "pptx")

      # 构建 nodes_info，包含 render_method
      nodes_info = []
      for node in chunk_nodes:
          node_id = node.get("node_id", "")
          node_info = {
              "node_id": node_id,
              "node_type": node.get("node_type", ""),
              "desc": node.get("desc", ""),
              "role": role_map.get(node_id, ""),
              "render_method": render_method_map.get(node_id, "pptx"),  # 新增
          }
          nodes_info.append(node_info)

  改动 2：更新 prompt，添加内容感知和比例约束

  # prompts_repo.py - Paper2GraphNodeLayoutPlanner

  system_prompt_for_p2g_node_layout_planner_agent = """
  你是科研图中「chunk 内部布局」的规划专家。

  你的职责是：
  - 为当前 chunk 内的每个 node 规划相对位置 (rel_bbox)
  - rel_bbox 使用 0~1 的归一化坐标，表示相对于 chunk 内部区域的位置和尺寸

  [核心约束 - 内容感知布局]
  1. **根据 node 内容决定尺寸**：
     - 短标签（单词/符号）：紧凑尺寸，w=0.08~0.15, h=0.06~0.12
     - 简短文本（1-2 句）：中等尺寸，w=0.2~0.4, h=0.1~0.2
     - 复杂内容（公式/多行）：较大尺寸，w=0.3~0.6, h=0.2~0.4
     - 模块框/流程框：w=0.3~0.5, h=0.25~0.45

  2. **根据渲染方式约束比例**：
     - render_method="vlm" 的 node：
       * 宽高比应接近 1:1 ~ 4:3（避免极端比例导致图片扭曲）
       * 推荐比例：1:1, 4:3, 3:2, 16:9
     - render_method="pptx" 的 node：
       * 文本框可以较宽（适应文字横排）
       * 但高度需要足够容纳文字内容

  3. **禁止重叠**：任意两个 node 的 bbox 不能有交集
  4. **边距要求**：相邻 nodes 间距 ≥ 0.03
  5. **边界约束**：所有 bbox 必须在 [0.02, 0.98] 范围内

  [空间利用率]
  - 目标利用率: 50%~75%
  - 主要内容模块应占据视觉中心
  """

  task_prompt_for_p2g_node_layout_planner_agent = """
  [INPUT]
  chunk_id: {chunk_id}
  chunk_summary: {chunk_summary}
  chunk_nodes: {chunk_nodes}
  chunk_edges: {chunk_edges}
  semantic_desc: {semantic_desc}

  [TASK]
  为当前 chunk 内的每个 node 规划 rel_bbox。

  **特别注意**：
  1. 对于 render_method="vlm" 的 node，bbox 宽高比应接近 1:1 ~ 4:3
  2. 对于 render_method="pptx" 的文本 node，高度需要足够容纳文字

  [OUTPUT FORMAT]
  {{
    "chunk_id": "{chunk_id}",
    "nodes": [
      {{
        "node_id": "n1",
        "role": "main_block",
        "rel_bbox": {{"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.35}},
        "aspect_ratio": 1.14,  // 新增：w/h 比例
        "reasoning": "布局说明"
      }}
    ]
  }}

  仅输出 JSON，不要解释。
  """

  ---
  3.2 设计阶段优化：p2g_node_render_design_agent

  目标：
  1. 更多 node 使用 VLM 渲染（除了纯短文本）
  2. 输出结构化 vlm_prompt（内容+风格+比例分离）

  改动 1：更新 prompt，调整渲染方式决策规则

  # prompts_repo.py - Paper2GraphNodeRenderDesign

  system_prompt_for_p2g_node_render_design_agent = """
  You are an expert in scientific figure rendering design.

  **CRITICAL: Rendering Method Guidelines**

  **pptx rendering** is ONLY suitable for:
  - Very short text labels (1-5 words): "IL", "RL", "Input", "Output"
  - Simple section titles (single line, no special formatting)
  - Pure numeric labels or simple formulas displayed as text

  **vlm rendering** should be used for:
  - **ALL other cases**, including:
    - Titles with special styling or emphasis
    - Any text longer than 5 words
    - Any shape, module, or container
    - Any node with internal structure
    - Any node representing a concept, process, or data
    - Any node that would benefit from visual design

  **Decision Rule**: When in doubt, use vlm. It's better to have a rich visual than a plain text box that might overflow.

  **Expected ratio**: 70-85% of nodes should use vlm rendering.
  """

  task_prompt_for_p2g_node_render_design_agent = """
  [CHUNK CONTEXT]
  chunk_id: {chunk_id}
  chunk_summary: {chunk_summary}

  [NODES TO DESIGN]
  {nodes_info}

  [GLOBAL STYLE]
  {global_style}

  [TASK]
  For each node, determine rendering method and provide **structured** specifications.

  **For vlm nodes, output structured prompt components**:
  {{
    "node_id": "n1",
    "render_method": "vlm",
    "vlm_spec": {{
      "content": "具体内容描述（What to draw）",
      "style": "flat_2d_vector | scientific_diagram | icon | module_box",
      "color_scheme": "muted_teal | calm_blue | warm_accent | neutral_gray",
      "background": "white | transparent",
      "label_text": "需要显示的文字标签（如有）",
      "aspect_ratio_hint": "1:1 | 4:3 | 3:2 | 16:9 | auto"
    }},
    "reasoning": "..."
  }}

  **For pptx nodes (only short labels)**:
  {{
    "node_id": "n2",
    "render_method": "pptx",
    "pptx_desc": "Short label text, 12pt, dark gray, center aligned",
    "reasoning": "Very short label (2 words), suitable for native text"
  }}

  [OUTPUT FORMAT]
  {{
    "chunk_id": "{chunk_id}",
    "nodes": [...],
    "chunk_style_hints": {{
      "dominant_color": "#4A90D9",
      "visual_weight": "medium"
    }}
  }}
  """

  改动 2：在 agent 代码中处理结构化输出

  # p2g_node_render_design_agent.py

  def _get_default_global_style() -> Dict[str, Any]:
      """获取默认的全局样式配置 - 简化版"""
      return {
          "theme": "Top-tier CS conference scientific illustration",
          "style_presets": {
              "flat_2d_vector": "Flat 2D vector style, clean lines, no shadows, no 3D effects",
              "scientific_diagram": "Clean scientific diagram, minimalist, publication-ready",
              "icon": "Simple flat icon, single color, clear silhouette",
              "module_box": "Rounded rectangle module with label, professional look"
          },
          "color_presets": {
              "muted_teal": "#66c2a5 - for data inputs, datasets",
              "calm_blue": "#4A90D9 - for main modules, processing blocks",
              "warm_accent": "#fc8d62 - for highlights, special operations",
              "neutral_gray": "#808080 - for backgrounds, less important elements"
          },
          "background": "white or transparent",
          "font": "Sans-serif (Arial, Helvetica)"
      }

  ---
  3.3 生图阶段优化：p2g_vlm_node_renderer_agent

  目标：
  1. 接收 bbox 比例信息
  2. 组装最终 prompt（内容+风格+比例）

  改动 1：修改 _extract_vlm_nodes 函数，提取 bbox 比例

  # p2g_vlm_node_renderer_agent.py

  def _extract_vlm_nodes(
      node_render_design: Dict[str, Any],
      layout_json: Dict[str, Any]  # 新增参数
  ) -> List[Dict[str, Any]]:
      """从 node_render_design 中提取所有 vlm 类型的节点，并附加 bbox 比例信息"""
      # 构建 node_id -> bbox 映射
      bbox_map = {}
      for node_pos in layout_json.get("positions", {}).get("nodes", []):
          node_id = node_pos.get("node_id")
          bbox = node_pos.get("bbox", {})
          if node_id and bbox:
              w, h = bbox.get("w", 1), bbox.get("h", 1)
              aspect_ratio = w / h if h > 0 else 1.0
              bbox_map[node_id] = {
                  "w": w,
                  "h": h,
                  "aspect_ratio": round(aspect_ratio, 2)
              }

      vlm_nodes = []
      for chunk in node_render_design.get("chunks", []):
          for node in chunk.get("nodes", []):
              if node.get("render_method") == "vlm":
                  node_id = node.get("node_id", "")

                  # 获取结构化 vlm_spec 或原始 vlm_prompt
                  vlm_spec = node.get("vlm_spec", {})
                  vlm_prompt = node.get("vlm_prompt", "")

                  # 获取 bbox 信息
                  bbox_info = bbox_map.get(node_id, {"aspect_ratio": 1.0})

                  vlm_nodes.append({
                      "node_id": node_id,
                      "vlm_spec": vlm_spec,
                      "vlm_prompt": vlm_prompt,  # 兼容旧格式
                      "chunk_id": chunk.get("chunk_id", ""),
                      "aspect_ratio": bbox_info["aspect_ratio"],
                      "bbox_w": bbox_info.get("w", 200),
                      "bbox_h": bbox_info.get("h", 200),
                  })

      return vlm_nodes

  改动 2：新增 prompt 组装函数

  # p2g_vlm_node_renderer_agent.py

  # 全局样式模板
  GLOBAL_STYLE_TEMPLATE = """
  [STYLE REQUIREMENTS]
  - Flat 2D vector illustration for academic paper
  - Clean lines, no shadows, no 3D effects, no photorealism
  - Morandi-style muted, desaturated colors
  - {background} background
  - Sans-serif text labels if any
  """

  # 风格预设映射
  STYLE_PRESETS = {
      "flat_2d_vector": "Flat 2D vector style, clean geometric shapes",
      "scientific_diagram": "Clean scientific diagram, minimalist design, publication-ready",
      "icon": "Simple flat icon, single color, clear silhouette, centered",
      "module_box": "Rounded rectangle module box with clear label, professional look"
  }

  # 颜色预设映射
  COLOR_PRESETS = {
      "muted_teal": "muted teal (#66c2a5)",
      "calm_blue": "calm professional blue (#4A90D9)",
      "warm_accent": "soft warm coral (#fc8d62)",
      "neutral_gray": "neutral gray (#808080)"
  }


  def _assemble_vlm_prompt(
      vlm_spec: Dict[str, Any],
      vlm_prompt: str,
      aspect_ratio: float,
      bbox_w: int,
      bbox_h: int,
  ) -> str:
      """组装最终的 VLM prompt
      
      Args:
          vlm_spec: 结构化的 vlm 规格（新格式）
          vlm_prompt: 原始 vlm_prompt（旧格式，兼容）
          aspect_ratio: 目标宽高比
          bbox_w: 目标宽度（像素）
          bbox_h: 目标高度（像素）
      
      Returns:
          组装后的完整 prompt
      """
      # 如果有结构化 vlm_spec，使用新格式
      if vlm_spec and vlm_spec.get("content"):
          content = vlm_spec.get("content", "")
          style = STYLE_PRESETS.get(vlm_spec.get("style", "flat_2d_vector"), "Flat 2D vector style")
          color = COLOR_PRESETS.get(vlm_spec.get("color_scheme", "calm_blue"), "professional blue")
          background = vlm_spec.get("background", "white")
          label_text = vlm_spec.get("label_text", "")

          prompt_parts = [
              f"[CONTENT]\n{content}",
              f"\n[STYLE]\n{style}",
              f"Color scheme: {color}",
          ]

          if label_text:
              prompt_parts.append(f"Include text label: \"{label_text}\"")

          prompt_parts.append(f"\n[OUTPUT REQUIREMENTS]")
          prompt_parts.append(f"- {background.capitalize()} background")
          prompt_parts.append(f"- Aspect ratio: approximately {aspect_ratio:.1f}:1 (width:height = {bbox_w}:{bbox_h})")
          prompt_parts.append(f"- The image should fit naturally into a {bbox_w}x{bbox_h} pixel container")
          prompt_parts.append(f"\n[NEGATIVE]\nDo NOT include: photorealistic elements, gradients, complex textures, 3D effects, shadows, busy backgrounds")

          return "\n".join(prompt_parts)

      # 兼容旧格式：在原始 prompt 后追加比例约束
      elif vlm_prompt:
          ratio_hint = f"""

  [OUTPUT SIZE REQUIREMENT]
  Generate the image with aspect ratio approximately {aspect_ratio:.1f}:1 (width:height = {bbox_w}:{bbox_h}).
  The image should fit naturally into a {bbox_w}x{bbox_h} pixel container without distortion.
  """
          return vlm_prompt + ratio_hint

      else:
          return ""

  改动 3：修改 _render_single_node 使用组装后的 prompt

  # p2g_vlm_node_renderer_agent.py

  async def _render_single_node(
      node_id: str,
      vlm_spec: Dict[str, Any],
      vlm_prompt: str,
      aspect_ratio: float,
      bbox_w: int,
      bbox_h: int,
      output_dir: str,
      # ... 其他参数
  ) -> Tuple[str, str, Optional[str]]:
      """渲染单个 VLM 节点"""
      async with semaphore:
          try:
              # 组装最终 prompt
              final_prompt = _assemble_vlm_prompt(
                  vlm_spec=vlm_spec,
                  vlm_prompt=vlm_prompt,
                  aspect_ratio=aspect_ratio,
                  bbox_w=bbox_w,
                  bbox_h=bbox_h,
              )

              if not final_prompt:
                  return (node_id, "", "Empty prompt")

              log.info(f"[VLM Renderer] Rendering {node_id} with aspect_ratio={aspect_ratio:.2f}")

              # ... 后续生图逻辑不变 ...

  ---
  3.4 渲染阶段优化：node_renderer.py

  目标：
  1. VLM 图片等比缩放+居中放置
  2. 文本框支持自适应

  改动 1：修改 render_vlm_image 方法

  # pptx_composer/node_renderer.py

  def render_vlm_image(
      self,
      node_id: str,
      bbox_emu: Tuple[int, int, int, int],
      image_path: str,
      fit_mode: str = "contain",  # 新增参数: "contain" | "cover" | "stretch"
  ) -> bool:
      """插入 VLM 生成的图片，支持等比缩放
      
      Args:
          node_id: 节点 ID
          bbox_emu: (left, top, width, height) EMU 坐标
          image_path: 图片文件路径
          fit_mode: 适应模式- "contain": 等比缩放，完整显示，居中放置（推荐）
              - "cover": 等比缩放，填满区域，可能裁剪
              - "stretch": 强制拉伸（不推荐，会扭曲）
          
      Returns:
          是否插入成功
      """
      if not image_path or not Path(image_path).exists():
          log.error(f"Image not found for node {node_id}: {image_path}")
          return False

      try:
          from PIL import Image

          # 获取原始图片尺寸
          with Image.open(image_path) as img:
              img_w, img_h = img.size

          left, top, width, height = bbox_emu

          if fit_mode == "stretch":
              # 强制拉伸（不推荐）
              new_left, new_top = left, top
              new_width, new_height = width, height
          elif fit_mode == "contain":
              # 等比缩放，完整显示，居中放置
              bbox_ratio = width / height if height > 0 else 1
              img_ratio = img_w / img_h if img_h > 0 else 1

              if img_ratio > bbox_ratio:
                  # 图片更宽，以宽度为准
                  new_width = width
                  new_height = int(width / img_ratio)new_left = left
                  new_top = top + (height - new_height) // 2
              else:
                  # 图片更高，以高度为准
                  new_height = height
                  new_width = int(height * img_ratio)
                  new_left = left + (width - new_width) // 2
                  new_top = top

          elif fit_mode == "cover":
              # 等比缩放，填满区域
              bbox_ratio = width / height if height > 0 else 1
              img_ratio = img_w / img_h if img_h > 0 else 1

              if img_ratio > bbox_ratio:
                  # 图片更宽，以高度为准
                  new_height = height
                  new_width = int(height * img_ratio)
                  new_left = left + (width - new_width) // 2
                  new_top = top
              else:
                  # 图片更高，以宽度为准
                  new_width = width
                  new_height = int(width / img_ratio)
                  new_left = left
                  new_top = top + (height - new_height) // 2

          else:
              # 默认 contain
              new_left, new_top = left, top
              new_width, new_height = width, height

          self.slide.shapes.add_picture(
              image_path,
              Emu(new_left), Emu(new_top),
              Emu(new_width), Emu(new_height)
          )

          log.debug(f"Inserted VLM image for {node_id}: fit_mode={fit_mode}, "
                    f"original={img_w}x{img_h}, final={new_width}x{new_height}")
          return True

      except Exception as e:
          log.error(f"Failed to insert image for node {node_id}: {e}")
          return False

  改动 2：修改 _render_text_box 支持自适应

  # pptx_composer/node_renderer.py

  def _render_text_box(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
      """渲染文本框，支持自适应"""
      from pptx.enum.text import MSO_AUTO_SIZE

      left, top, width, height = bbox_emu

      txBox = self.slide.shapes.add_textbox(
          Emu(left), Emu(top), Emu(width), Emu(height)
      )
      tf = txBox.text_frame
      tf.word_wrap = True

      # 自适应模式
      auto_fit = spec.get("auto_fit", "shrink")  # "shrink" | "expand" | "none"

      if auto_fit == "shrink":
          # 自动缩小字体以适应框
          tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
      elif auto_fit == "expand":
          # 自动扩展框以适应文本
          tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
      else:
          tf.auto_size = None

      # 垂直居中
      tf.anchor = MSO_ANCHOR.MIDDLE
      # 设置文本
      text = spec.get("text", "")
      text_lines = spec.get("text_lines")
      text_style = spec.get("text_style", {})

      p = tf.paragraphs[0]
      p.text = text if not text_lines else "\n".join(text_lines)
      # 应用文本样式
      self._apply_text_style(p, text_style)

      # 设置形状样式
      shape_style = spec.get("shape_style", {})
      self._apply_shape_style(txBox, shape_style)

  ---
  3.5 更新 pptx_builder.py 调用

  # pptx_composer/pptx_builder.py

  def _render_all_nodes(
      self,
      node_bboxes: Dict[str, Dict],
      render_methods: Dict[str, str],
      pptx_render_specs: Dict[str, Any],
      vlm_rendered_nodes: Dict[str, str],
  ):
      """渲染所有节点"""
      for node_id, bbox in node_bboxes.items():
          method = render_methods.get(node_id, "pptx")
          bbox_emu = self.converter.bbox_to_emu(bbox)

          try:
              if method == "vlm":
                  image_path = vlm_rendered_nodes.get(node_id)
                  if image_path:
                      # 使用 contain 模式，等比缩放+居中
                      success = self.node_renderer.render_vlm_image(
                          node_id, bbox_emu, image_path,
                          fit_mode="contain"  # 新增参数
                      )
                      if success:
                          self.stats["vlm_nodes_rendered"] += 1
                  else:
                      log.warning(f"No VLM image for node {node_id}")
                      self.stats["errors"].append(f"Missing VLM image: {node_id}")

              else:
                  spec = pptx_render_specs.get(node_id)
                  if spec:
                      # 文本框默认启用自适应
                      if spec.get("element_type") == "text_box":
                          spec.setdefault("auto_fit", "shrink")

                      success = self.node_renderer.render_node(
                          node_id, bbox_emu, spec
                      )
                      if success:
                          self.stats["pptx_nodes_rendered"] += 1
                  else:
                      log.warning(f"No PPTX spec for node {node_id}")
                      self.stats["errors"].append(f"Missing PPTX spec: {node_id}")

          except Exception as e:
              log.error(f"Error rendering node {node_id}: {e}")
              self.stats["errors"].append(f"Render error {node_id}: {str(e)}")

  ---
  四、新增数据结构

  4.1 结构化 VLM Spec

  {
    "node_id": "n7",
    "render_method": "vlm",
    "vlm_spec": {
      "content": "A data module representing expert dataset with document stack icon",
      "style": "module_box",
      "color_scheme": "muted_teal",
      "background": "transparent",
      "label_text": "D_expert = {(s_i, a_i)}",
      "aspect_ratio_hint": "4:3"
    },
    "reasoning": "Dataset module with icon and formula label"
  }

  4.2 扩展的 Layout Node

  {
    "node_id": "n7",
    "role": "main_block",
    "rel_bbox": {"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.3},
    "aspect_ratio": 1.33,
    "render_method": "vlm",
    "reasoning": "VLM node, using 4:3 aspect ratio for better visual"
  }

  ---
五、实施步骤

  | 步骤  | 任务                                                | 涉及文件                            | 优先级 |
  |-----|---------------------------------------------------|---------------------------------|-----|
  | 1   | 修改 node_renderer.py，实现 VLM 图片等比缩放+居中              | pptx_composer/node_renderer.py  | P0  |
  | 2   | 修改 node_renderer.py，文本框支持自适应                      | pptx_composer/node_renderer.py  | P0  |
  | 3   | 修改 p2g_vlm_node_renderer_agent.py，添加 prompt 组装逻辑  | p2g_vlm_node_renderer_agent.py  | P0  |
  | 4   | 更新 prompts_repo.py 中 node_layout_planner 的 prompt | prompts_repo.py                 | P1  |
  | 5   | 更新 prompts_repo.py 中 node_render_design 的 prompt  | prompts_repo.py                 | P1  |
  | 6   | 修改 p2g_node_render_design_agent.py，输出结构化 vlm_spec | p2g_node_render_design_agent.py | P1  |
  | 7   | 修改 pptx_builder.py，传递 fit_mode 参数                 | pptx_composer/pptx_builder.py   | P0  |
  | 8   | 测试验证                                              | test_p2g_pptx_composer_agent.py | P0  |

  ---
  六、预期效果对比

  | 问题       | 优化前               | 优化后                   |
  |----------|-------------------|-----------------------|
  | VLM 图片扭曲 | 强制拉伸到 bbox，比例失真严重 | 等比缩放+居中，保持原始比例        |
  | 文本框溢出    | bbox 固定，文字超出边界    | 自动缩小字体适应；复杂内容改用 VLM   |
  | VLM 效果一般 | prompt 冗长混杂       | 结构化 prompt：内容+风格+比例分离 |
  | 渲染方式选择   | 较多使用 pptx         | 70-85% 使用 VLM，提高可控性   |

  ---
  七、代码实现示例

  让我给出关键代码的完整实现：

  7.1 node_renderer.py 完整改动

  # dataflow_agent/toolkits/pptx_composer/node_renderer.py

  """节点渲染器

  根据 PPTXRenderSpec 渲染 PPTX 原生节点，或插入 VLM 生成的图片。
  """

  from __future__ import annotations

  import os
  from pathlib import Path
  from typing import Any, Dict, Optional, Tuple

  from pptx.util import Pt, Emu
  from pptx.dml.color import RGBColor
  from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
  from pptx.enum.shapes import MSO_SHAPE

  from dataflow_agent.logger import get_logger

  log = get_logger(__name__)


  # 对齐方式映射
  ALIGNMENT_MAP = {
      "left": PP_ALIGN.LEFT,
      "center": PP_ALIGN.CENTER,
      "right": PP_ALIGN.RIGHT,
  }


  def hex_to_rgb(hex_color: str) -> Optional[RGBColor]:
      """将 hex 颜色转换为 RGBColor"""
      if not hex_color:
          return None
      try:
          hex_color = hex_color.lstrip("#")
          if len(hex_color) == 6:
              r = int(hex_color[0:2], 16)
              g = int(hex_color[2:4], 16)
              b = int(hex_color[4:6], 16)
              return RGBColor(r, g, b)
      except (ValueError, TypeError):
          pass
      return None


  class PPTXNodeRenderer:
      """PPTX 节点渲染器"""

      def __init__(self, slide):
          """
          Args:
              slide: python-pptx Slide 对象
          """
          self.slide = slide

      def render_node(
          self,
          node_id: str,
          bbox_emu: Tuple[int, int, int, int],
          spec: Dict[str, Any],
      ) -> bool:
          """根据 spec 渲染节点"""
          element_type = spec.get("element_type", "text_box")

          try:
              if element_type == "text_box":
                  self._render_text_box(bbox_emu, spec)
              elif element_type == "rectangle":
                  self._render_rectangle(bbox_emu, spec, rounded=False)
              elif element_type == "rounded_rectangle":
                  self._render_rectangle(bbox_emu, spec, rounded=True)
              elif element_type == "arrow":
                  self._render_arrow_annotation(bbox_emu, spec)
              elif element_type == "line":
                  self._render_line(bbox_emu, spec)
              else:
                  log.warning(f"Unknown element_type '{element_type}' for {node_id}, using text_box")
                  self._render_text_box(bbox_emu, spec)

              log.debug(f"Rendered node {node_id} as {element_type}")
              return True

          except Exception as e:
              log.error(f"Failed to render node {node_id}: {e}")
              return False

      def render_vlm_image(
          self,
          node_id: str,
          bbox_emu: Tuple[int, int, int, int],
          image_path: str,
          fit_mode: str = "contain",
      ) -> bool:
          """插入 VLM 生成的图片，支持等比缩放
          
          Args:
              node_id: 节点 ID
              bbox_emu: (left, top, width, height) EMU 坐标
              image_path: 图片文件路径
              fit_mode: 适应模式
                  - "contain": 等比缩放，完整显示，居中放置（推荐）
                  - "cover": 等比缩放，填满区域，可能裁剪
                  - "stretch": 强制拉伸（不推荐）
              
          Returns:
              是否插入成功
          """
          if not image_path or not Path(image_path).exists():
              log.error(f"Image not found for node {node_id}: {image_path}")
              return False

          try:
              from PIL import Image

              # 获取原始图片尺寸
              with Image.open(image_path) as img:
                  img_w, img_h = img.size
              left, top, width, height = bbox_emu

              if fit_mode == "stretch":
                  # 强制拉伸（不推荐）
                  new_left, new_top = left, top
                  new_width, new_height = width, height
              elif fit_mode == "contain":
                  # 等比缩放，完整显示，居中放置
                  bbox_ratio = width / height if height > 0 else 1
                  img_ratio = img_w / img_h if img_h > 0 else 1

                  if img_ratio > bbox_ratio:
                      # 图片更宽，以宽度为准
                      new_width = width
                      new_height = int(width / img_ratio)
                      new_left = left
                      new_top = top + (height - new_height) // 2
                  else:
                      # 图片更高，以高度为准
                      new_height = height
                      new_width = int(height * img_ratio)
                      new_left = left + (width - new_width) // 2
                      new_top = top

              elif fit_mode == "cover":
                  # 等比缩放，填满区域
                  bbox_ratio = width / height if height > 0 else 1
                  img_ratio = img_w / img_h if img_h > 0 else 1

                  if img_ratio > bbox_ratio:
                      new_height = height
                      new_width = int(height * img_ratio)
                      new_left = left + (width - new_width) // 2
                      new_top = top
                  else:
                      new_width = width
                      new_height = int(width / img_ratio)
                      new_left = left
                      new_top = top + (height - new_height) // 2
              else:
                  new_left, new_top = left, top
                  new_width, new_height = width, height

              self.slide.shapes.add_picture(
                  image_path,
                  Emu(new_left), Emu(new_top),
                  Emu(new_width), Emu(new_height)
              )

              log.debug(f"Inserted VLM image for {node_id}: fit_mode={fit_mode}, "
                        f"original={img_w}x{img_h}, bbox={width}x{height}, "
                        f"final={new_width}x{new_height}")
              return True

          except ImportError:
              # PIL 不可用时，回退到强制拉伸
              log.warning(f"PIL not available, using stretch mode for {node_id}")
              left, top, width, height = bbox_emu
              self.slide.shapes.add_picture(
                  image_path,
                  Emu(left), Emu(top),
                  Emu(width), Emu(height)
              )
              return True

          except Exception as e:
              log.error(f"Failed to insert image for node {node_id}: {e}")
              return False

      def _render_text_box(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
          """渲染文本框，支持自适应"""
          left, top, width, height = bbox_emu

          txBox = self.slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height)
          )
          tf = txBox.text_frame
          tf.word_wrap = True

          # 自适应模式
          auto_fit = spec.get("auto_fit", "shrink")

          if auto_fit == "shrink":
              tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
          elif auto_fit == "expand":
              tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
          else:
              tf.auto_size = None

          # 垂直居中
          tf.anchor = MSO_ANCHOR.MIDDLE

          # 设置文本
          text = spec.get("text", "")
          text_lines = spec.get("text_lines")
          text_style = spec.get("text_style", {})

          p = tf.paragraphs[0]
          p.text = text if not text_lines else "\n".join(text_lines)
          # 应用文本样式
          self._apply_text_style(p, text_style)

          # 设置形状样式
          shape_style = spec.get("shape_style", {})
          self._apply_shape_style(txBox, shape_style)

      def _render_rectangle(self, bbox_emu: Tuple[int, int, int, int], spec: Dict, rounded: bool = False):
          """渲染矩形"""
          left, top, width, height = bbox_emu

          shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
          shape = self.slide.shapes.add_shape(
              shape_type,
              Emu(left), Emu(top), Emu(width), Emu(height)
          )

          shape_style = spec.get("shape_style", {})
          self._apply_shape_style(shape, shape_style)

          text = spec.get("text", "")
          text_lines = spec.get("text_lines")
          if text or text_lines:
              tf = shape.text_frame
              tf.word_wrap = True
              tf.anchor = MSO_ANCHOR.MIDDLE

              p = tf.paragraphs[0]
              p.text = text if not text_lines else "\n".join(text_lines)

              text_style = spec.get("text_style", {})
              self._apply_text_style(p, text_style)

      def _render_arrow_annotation(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
          """渲染箭头注释"""
          self._render_text_box(bbox_emu, spec)

      def _render_line(self, bbox_emu: Tuple[int, int, int, int], spec: Dict):
          """渲染线条"""
          left, top, width, height = bbox_emu
          end_x = left + width
          end_y = top + height

          connector = self.slide.shapes.add_connector(
              1,
              Emu(left), Emu(top),
              Emu(end_x), Emu(end_y)
          )

          shape_style = spec.get("shape_style", {})
          border_color = hex_to_rgb(shape_style.get("border_color"))
          if border_color:
              connector.line.color.rgb = border_color

      def _apply_text_style(self, paragraph, text_style: Dict):
          """应用文本样式到段落"""
          font = paragraph.font

          font_family = text_style.get("font_family", "Arial")
          font.name = font_family

          font_size = text_style.get("font_size", 12)
          font.size = Pt(font_size)

          font.bold = text_style.get("bold", False)
          font.italic = text_style.get("italic", False)

          color = hex_to_rgb(text_style.get("color", "#333333"))
          if color:
              font.color.rgb = coloralignment = text_style.get("alignment", "left")
          paragraph.alignment = ALIGNMENT_MAP.get(alignment, PP_ALIGN.LEFT)

      def _apply_shape_style(self, shape, shape_style: Dict):
          """应用形状样式"""
          fill = shape.fill
          line = shape.line

          fill_color = shape_style.get("fill_color")
          if fill_color:
              rgb = hex_to_rgb(fill_color)
              if rgb:
                  fill.solid()
                  fill.fore_color.rgb = rgb
          else:
              fill.background()

          border_style = shape_style.get("border_style", "none")
          border_color = shape_style.get("border_color")
          border_width = shape_style.get("border_width", 1.0)

          if border_style == "none" or not border_color:
              line.fill.background()
          else:
              rgb = hex_to_rgb(border_color)
              if rgb:
                  line.color.rgb = rgb
                  line.width = Pt(border_width)

                  if border_style == "dashed":
                      from pptx.enum.dml import MSO_LINE_DASH_STYLE
                      line.dash_style = MSO_LINE_DASH_STYLE.DASH

  7.2 p2g_vlm_node_renderer_agent.py 关键改动

  # dataflow_agent/agentroles/p2g_vlm_node_renderer_agent.py

  # 在文件顶部添加常量定义

  # 全局样式模板
  GLOBAL_STYLE_SUFFIX = """
  [STYLE REQUIREMENTS]
  - Flat 2D vector illustration for academic paper
  - Clean lines, no shadows, no 3D effects, no photorealism
  - Morandi-style muted, desaturated colors
  - Professional scientific diagram style
  """

  # 风格预设映射
  STYLE_PRESETS = {
      "flat_2d_vector": "Flat 2D vector style, clean geometric shapes, minimalist design",
      "scientific_diagram": "Clean scientific diagram, minimalist design, publication-ready for top-tier CS conference",
      "icon": "Simple flat icon, single color, clear silhouette, centered composition",
      "module_box": "Rounded rectangle module box with clear label, professional look, suitable for flowchart"
  }

  # 颜色预设映射
  COLOR_PRESETS = {
      "muted_teal": "muted teal color (#66c2a5)",
      "calm_blue": "calm professional blue color (#4A90D9)",
      "warm_accent": "soft warm coral color (#fc8d62)",
      "neutral_gray": "neutral gray color (#808080)",
      "muted_green": "muted green color (#6BAA9B)"
  }


  def _assemble_vlm_prompt(
      vlm_spec: Dict[str, Any],
      vlm_prompt: str,
      aspect_ratio: float,
      bbox_w: int,
      bbox_h: int,
  ) -> str:
      """组装最终的 VLM prompt
      
      支持两种格式：
      1. 结构化 vlm_spec（新格式，推荐）
      2. 原始 vlm_prompt（旧格式，兼容）
      """
      # 如果有结构化 vlm_spec，使用新格式
      if vlm_spec and vlm_spec.get("content"):
          content = vlm_spec.get("content", "")
          style_key = vlm_spec.get("style", "flat_2d_vector")
          style = STYLE_PRESETS.get(style_key, STYLE_PRESETS["flat_2d_vector"])

          color_key = vlm_spec.get("color_scheme", "calm_blue")
          color = COLOR_PRESETS.get(color_key, COLOR_PRESETS["calm_blue"])

          background = vlm_spec.get("background", "white")
          label_text = vlm_spec.get("label_text", "")

          prompt_parts = [
              f"[CONTENT]",
              f"{content}",
              f"",
              f"[VISUAL STYLE]",
              f"{style}",
              f"Color: {color}",
          ]

          if label_text:
              prompt_parts.append(f"Text label to include: \"{label_text}\"")

          prompt_parts.extend([
              f"",
              f"[OUTPUT REQUIREMENTS]",
              f"- {background.capitalize()} background",
              f"- Aspect ratio: approximately {aspect_ratio:.2f}:1",
              f"- Target size: {bbox_w}x{bbox_h} pixels",
              f"- The image should fit naturally into this container without distortion",
              f"",
              f"[NEGATIVE - DO NOT INCLUDE]",
              f"Photorealistic elements, gradients, complex textures, 3D effects, shadows, busy backgrounds, watermarks"
          ])

          return "\n".join(prompt_parts)

      # 兼容旧格式：在原始 prompt 后追加比例约束
      elif vlm_prompt:
          ratio_hint = f"""

  [OUTPUT SIZE REQUIREMENT]
  - Aspect ratio: approximately {aspect_ratio:.2f}:1 (width:height = {bbox_w}:{bbox_h})
  - The image should fit naturally into a {bbox_w}x{bbox_h} pixel container
  - Avoid extreme aspect ratios that would cause distortion when scaled
  """
          return vlm_prompt.strip() + ratio_hint

      else:
          return ""


  def _extract_vlm_nodes(
      node_render_design: Dict[str, Any],
      layout_json: Optional[Dict[str, Any]] = None
  ) -> List[Dict[str, Any]]:
      """从 node_render_design 中提取所有 vlm 类型的节点
      
      Args:
          node_render_design: 渲染设计
          layout_json: 布局信息（可选，用于获取 bbox 比例）
      
      Returns:
          vlm 节点列表，每个元素包含 node_id、vlm_prompt/vlm_spec、aspect_ratio 等
      """
      # 构建 node_id -> bbox 映射
      bbox_map = {}
      if layout_json:
          for node_pos in layout_json.get("positions", {}).get("nodes", []):
              node_id = node_pos.get("node_id")
              bbox = node_pos.get("bbox", {})
              if node_id and bbox:
                  w = bbox.get("w", 200)
                  h = bbox.get("h", 200)
                  aspect_ratio = w / h if h > 0 else 1.0
                  bbox_map[node_id] = {
                      "w": w,
                      "h": h,
                      "aspect_ratio": round(aspect_ratio, 2)
                  }

      vlm_nodes = []

      chunks = node_render_design.get("chunks", [])
      for chunk in chunks:
          nodes = chunk.get("nodes", [])
          for node in nodes:
              if node.get("render_method") == "vlm":
                  node_id = node.get("node_id", "")

                  # 获取 vlm_spec（新格式）或 vlm_prompt（旧格式）
                  vlm_spec = node.get("vlm_spec", {})
                  vlm_prompt = node.get("vlm_prompt", "")

                  if not vlm_prompt and not vlm_spec:
                      log.warning(f"VLM node {node_id} has no vlm_prompt or vlm_spec, skipping")
                      continue

                  # 获取 bbox 信息
                  bbox_info = bbox_map.get(node_id, {
                      "w": 200,
                      "h": 200,
                      "aspect_ratio": 1.0
                  })

                  vlm_nodes.append({
                      "node_id": node_id,
                      "vlm_spec": vlm_spec,
                      "vlm_prompt": vlm_prompt,
                      "chunk_id": chunk.get("chunk_id", ""),
                      "aspect_ratio": bbox_info["aspect_ratio"],
                      "bbox_w": bbox_info["w"],
                      "bbox_h": bbox_info["h"],
                  })

      return vlm_nodes


  # 修改 p2g_vlm_node_renderer_agent 函数签名，添加 layout_json 参数
  async def p2g_vlm_node_renderer_agent(
      state: Paper2GraphState,
      output_dir: Optional[str] = None,
      concurrency: int = DEFAULT_CONCURRENCY,
      vlm_model: Optional[str] = None,
      skip_bg_remove: bool = False,
      bg_remove_method: str = "edge_floodfill",
      bg_threshold: int = 245,
      timeout: int = 120,
  ) -> Paper2GraphState:
      """VLM 节点渲染器入口函数"""
      # ... 现有的环境变量读取代码 ...

      # 获取 node_render_design 和 layout_json
      node_render_design = getattr(state, "node_render_design", {}) or {}
      layout_json = getattr(state, "layout_json", {}) or {}  # 新增

      if not node_render_design:
          log.warning("node_render_design is empty, skip VLM rendering")
          setattr(state, "vlm_rendered_nodes", {})
          return state

      # 提取 vlm 节点（传入 layout_json 以获取 bbox 比例）
      vlm_nodes = _extract_vlm_nodes(node_render_design, layout_json)  # 修改

      # ... 后续代码 ...

      # 并行渲染所有节点
      tasks = [
          _render_single_node(
              node_id=node["node_id"],
              vlm_spec=node["vlm_spec"],  # 新增
              vlm_prompt=node["vlm_prompt"],
              aspect_ratio=node["aspect_ratio"],  # 新增
              bbox_w=node["bbox_w"],  # 新增
              bbox_h=node["bbox_h"],  # 新增
              output_dir=output_dir,
              api_url=api_url,
              api_key=api_key,
              model=vlm_model,
              semaphore=semaphore,
              timeout=timeout,
              skip_bg_remove=skip_bg_remove,
              bg_remove_method=bg_remove_method,
              bg_threshold=bg_threshold,
          )
          for node in vlm_nodes
      ]

      # ... 后续代码不变 ...


  async def _render_single_node(
      node_id: str,
      vlm_spec: Dict[str, Any],  # 新增
      vlm_prompt: str,
      aspect_ratio: float,  # 新增
      bbox_w: int,  # 新增
      bbox_h: int,  # 新增
      output_dir: str,
      api_url: str,
      api_key: str,
      model: str,
      semaphore: asyncio.Semaphore,
      timeout: int = 120,
      skip_bg_remove: bool = False,
      bg_remove_method: str = "edge_floodfill",
      bg_threshold: int = 245,
  ) -> Tuple[str, str, Optional[str]]:
      """渲染单个 VLM 节点"""
      async with semaphore:
          try:
              log.info(f"[VLM Renderer] Starting render for node {node_id}, aspect_ratio={aspect_ratio:.2f}")

              # 确保输出目录存在
              Path(output_dir).mkdir(parents=True, exist_ok=True)

              # 组装最终 prompt
              final_prompt = _assemble_vlm_prompt(
                  vlm_spec=vlm_spec,
                  vlm_prompt=vlm_prompt,
                  aspect_ratio=aspect_ratio,
                  bbox_w=bbox_w,
                  bbox_h=bbox_h,
              )

              if not final_prompt:
                  return (node_id, "", "Empty prompt after assembly")

              log.debug(f"[VLM Renderer] Final prompt for {node_id}:\n{final_prompt[:200]}...")

              # 1. VLM 生图
              raw_path = os.path.join(output_dir, f"{node_id}_raw.png")
              await _generate_image(
                  prompt=final_prompt,
                  save_path=raw_path,
                  api_url=api_url,
                  api_key=api_key,
                  model=model,
                  timeout=timeout,
              )
              log.info(f"[VLM Renderer] Generated raw image for {node_id}: {raw_path}")

              # 2. 抠图（可选）
              if skip_bg_remove:
                  final_path = raw_path
              else:
                  try:
                      final_path = _remove_background(
                          raw_path,
                          output_dir,
                          method=bg_remove_method,
                          bg_threshold=bg_threshold,
                      )
                      log.info(f"[VLM Renderer] Background removed for {node_id}")
                  except Exception as bg_err:
                      log.warning(f"[VLM Renderer] Background removal failed for {node_id}: {bg_err}")
                      final_path = raw_path

              return (node_id, final_path, None)

          except Exception as e:
              log.error(f"[VLM Renderer] Failed to render node {node_id}: {e}")
              return (node_id, "", str(e))

  ---
  八、测试验证

  完成上述改动后，可以通过以下步骤验证：

  # 1. 运行测试
  pytest tests/test_p2g_pptx_composer_agent.py -v

  # 2. 检查输出
  # - 查看 tests/.tmp/output/paper2graph_test.pptx
  # - 检查 VLM 图片是否保持比例
  # - 检查文本框是否溢出

  ---
  九、总结

  本优化方案通过三阶段协同解决了你提出的三个问题：

  | 阶段   | 优化内容                        | 解决的问题  |
  |------|-----------------------------|--------|
  | 设计阶段 | bbox 比例约束 + 内容感知 + 更多使用 VLM | 问题 1、2 |
  | 生图阶段 | 结构化 prompt + 比例传递           | 问题 1、3 |
  | 渲染阶段 | 等比缩放+居中 + 文本框自适应            | 问题 1、2 |

  核心改动文件：
  1. pptx_composer/node_renderer.py - 渲染逻辑
  2. p2g_vlm_node_renderer_agent.py - prompt 组装
  3. prompts_repo.py - prompt 模板更新