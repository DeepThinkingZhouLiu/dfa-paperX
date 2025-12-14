我目前已经完成了所有的布局设计和vllm渲染的nodes的设计,并且测试也已经通过,参见tests/test_p2g_node_layout_pipeline.py和tests/test_p2g_vlm_node_renderer_agent.py,最后一步是:
根据布局信息和已使用vlm渲染的nodes,把内容都放入pptx中,该步骤同时需要处理pptx渲染的nodes和edges,请你给出一个设计方案 

● 我来分析现有的代码结构，了解布局和渲染的设计，然后给出将内容放入PPTX的设计方案。

● Explore(探索P2G相关代码结构)
  ⎿  Done (25 tool uses · 71.9k tokens · 2m 20s)                                                                                                                           

● 非常好，我已经对项目架构有了全面了解。现在让我查看一些关键文件的具体实现细节，以便给出更精确的设计方案。

● Read(tests/.tmp/layout_pipeline/layout_json.json)
  ⎿  Read 492 lines

● Read(tests/.tmp/render_design/node_render_design.json)
  ⎿  Read 373 lines

● Read(tests/.tmp/layout_pipeline/semantic_json.json)
  ⎿  Read 587 lines

● 现在我已经完全理解了数据结构。让我再查看一下现有的VLM渲染测试和State定义，以便给出完整的设计方案。

● Read(tests/test_p2g_vlm_node_renderer_agent.py)
  ⎿  Read 706 lines

● Read(dataflow_agent/state.py)
  ⎿  Read 255 lines

● 根据我对项目架构的全面分析，现在给出 PPTX Composer Agent 的设计方案。

  --- PPTX Composer Agent 设计方案

  1. 整体定位

  这是 Paper2Graph Pipeline 的最后一个阶段，负责将所有前序阶段的产出（布局信息、VLM渲染的节点图片、PPTX渲染规格）组装成最终的 PowerPoint 文件。

  Pipeline 流程:
  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
  │ layout_json     │    │ node_render_    │    │ vlm_rendered_   │
  │ (像素级bbox)    │ +  │ design│ +  │ nodes│
  │                 │    │ (pptx_desc/vlm) │    │ (图片路径)      │
  └────────┬────────┘    └────────┬────────┘    └────────┬────────│                      │
           └──────────────────────┼──────────────────────┘┌───────────────────────┐
                      │  p2g_pptx_composer    │
                      │       _agent          │
                      └───────────┬───────────┘
                                  ┌───────────────────────┐
                      │   final.pptx          │
                      │   (完整的PPT文件)      │
                      └───────────────────────┘

  2. 输入数据结构

  2.1 来自 layout_json

  {
      "canvas": {"width": 1920, "height": 1080, "unit": "px"},
      "layout_flow": "left-to-right",
      "positions": {
          "chunks": [{"chunk_id": "c1", "bbox": {"x": 519, "y": 60, "w": 817, "h": 238}}],
          "nodes": [{"node_id": "n1", "bbox": {"x": 582, "y": 84, "w": 690, "h": 30}}]
  }

  2.2 来自 node_render_design

  {
      "chunks": [{
          "chunk_id": "c1",
          "nodes": [
              {
                  "node_id": "n1",
                  "render_method": "pptx",  # 或 "vlm"
                  "pptx_desc": "A text box for the main title...",  # pptx 渲染描述
                  "vlm_prompt": "..."  # vlm 渲染提示词（如果是vlm）
              }
          ]
      }],
      "global_style": {...}
  }

  2.3 来自 vlm_rendered_nodes

  {
      "n3": "/tmp/vlm_nodes/chunk1_node3.png",
      "n4": "/tmp/vlm_nodes/chunk1_node4.png",
      ...
  }

  2.4 来自 semantic_json (edges)

  {
      "edges": [
          {"edge_id": "e1", "from": "n3", "to": "n4"},
          {"edge_id": "e2", "from": "n4", "to": "n5"},
          ...
      ]
  }

  3. State 扩展

  在 Paper2GraphState 中添加新字段：

  @dataclass
  class Paper2GraphState(MainState):
      # ... 现有字段 ...

      # VLM 渲染结果 (node_id -> image_path)
      vlm_rendered_nodes: Dict[str, str] = field(default_factory=dict)

      # 最终 PPTX 输出路径
      pptx_output_path: str = ""

  4. Agent 架构设计

  4.1 核心组件

  ├── __init__.py
  ├── pptx_composer_agent.py      # 主 Agent 入口
  ├── renderers/
  │   ├── __init__.py
  │   ├── base_renderer.py        # 渲染器基类
  │   ├── pptx_node_renderer.py   # PPTX 原生节点渲染器├── vlm_node_renderer.py    # VLM 图片节点渲染器
  │   └── edge_renderer.py        # 边/连接线渲染器── utils/
      ├── __init__.py
      ├── coordinate_converter.py  # 坐标转换 (px -> EMU)
      └── style_parser.py          # 样式解析器

  4.2 主流程

  async def p2g_pptx_composer_agent(
      state: Paper2GraphState,
      output_path: str = None,
      slide_width: int = 1920,
      slide_height: int = 1080,
  ) -> Paper2GraphState:
      """PPTX 组装 Agent
      理流程:
      1. 初始化 PPTX 文档，设置幻灯片尺寸
      2. 渲染所有 Nodes (按 chunk 分组处理)
         - pptx 类型: 调用 PPTXNodeRenderer
         - vlm 类型: 调用 VLMNodeRenderer (插入图片)
      3. 渲染所有 Edges (连接线)
      4. 保存 PPTX 文件
      """

  5. 详细模块设计

  5.1 坐标转换器 (coordinate_converter.py)

  PowerPoint 使用 EMU (English Metric Units) 作为坐标单位：
  - 1 inch = 914400 EMU
  - 1 px ≈ 9525 EMU (假设 96 DPI)

  class CoordinateConverter:
      """像素坐标到 PPTX EMU 坐标的转换器"""

      EMU_PER_INCH = 914400
      DEFAULT_DPI = 96

      def __init__(self, canvas_width: int, canvas_height: int, 
                   slide_width_inch: float = 13.333, slide_height_inch: float = 7.5):
          """
          Args:
              canvas_width: 画布宽度 (px)
              canvas_height: 画布高度 (px)
              slide_width_inch: 幻灯片宽度 (inch), 默认 16:9 宽屏
              slide_height_inch: 幻灯片高度 (inch)
          """
          self.canvas_width = canvas_width
          self.canvas_height = canvas_height
          self.slide_width_emu = int(slide_width_inch * self.EMU_PER_INCH)
          self.slide_height_emu = int(slide_height_inch * self.EMU_PER_INCH)

          # 计算缩放比例
          self.scale_x = self.slide_width_emu / canvas_width
          self.scale_y = self.slide_height_emu / canvas_height

      def px_to_emu(self, bbox: Dict) -> Dict:
          """将像素 bbox 转换为 EMU bbox"""
          return {
              "left": int(bbox["x"] * self.scale_x),
              "top": int(bbox["y"] * self.scale_y),
              "width": int(bbox["w"] * self.scale_x),
              "height": int(bbox["h"] * self.scale_y),
          }

      def get_center_point(self, bbox: Dict) -> Tuple[int, int]:
          """获取 bbox 中心点 (EMU)"""
          emu_bbox = self.px_to_emu(bbox)
          return (
              emu_bbox["left"] + emu_bbox["width"] // 2,
              emu_bbox["top"] + emu_bbox["height"] // 2,
          )

  5.2 PPTX 节点渲染器 (pptx_node_renderer.py)

  处理 render_method="pptx" 的节点，根据 pptx_desc 创建原生 PPTX 元素：

  from pptx import Presentation
  from pptx.util import Emu, Pt
  from pptx.dml.color import RgbColor
  from pptx.enum.shapes import MSO_SHAPE
  from pptx.enum.text import PP_ALIGN

  class PPTXNodeRenderer:
      """PPTX 原生节点渲染器"""

      def __init__(self, slide, converter: CoordinateConverter, global_style: Dict):
          self.slide = slide
          self.converter = converter
          self.global_style = global_style

      def render(self, node_id: str, bbox: Dict, pptx_desc: str) -> None:
          """据 pptx_desc 渲染节点
          持的元素类型:
          - text_box: 文本框
          - rectangle: 矩形
          - rounded_rectangle: 圆角矩形
          - arrow: 箭头形状
          - annotation: 注释文本
          """
          # 解析 pptx_desc 确定元素类型和样式
          element_type = self._parse_element_type(pptx_desc)
          style = self._parse_style(pptx_desc)
          emu_bbox = self.converter.px_to_emu(bbox
          if element_type == "text_box":
              self._render_text_box(emu_bbox, pptx_desc, style)
          elif element_type in ["rectangle", "rounded_rectangle"]:
              self._render_shape(emu_bbox, element_type, pptx_desc, style)
          elif element_type == "arrow":
              self._render_arrow(emu_bbox, pptx_desc, style)
          elif element_type == "annotation":
              self._render_annotation(emu_bbox, pptx_desc, style)

      def _render_text_box(self, emu_bbox: Dict, desc: str, style: Dict) -> None:
          """渲染文本框"""
          shape = self.slide.shapes.add_textboxEmu(emu_bbox["left"]),
              Emu(emu_bbox["top"]),
              Emu(emu_bbox["width"]),
              Emu(emu_bbox["height"]),
          )

          tf = shape.text_frame
          tf.word_wrap = True

          # 提取文本内容
          text = self._extract_text_from_desc(desc)
          p = tf.paragraphs[0]
          p.text = text

          # 应用样式
          if style.get("font_size"):
              p.font.size = Pt(style["font_size"])
          if style.get("font_bold"):
              p.font.bold = True
          if style.get("font_color"):
              p.font.color.rgb = RgbColor.from_string(style["font_color"])
          if style.get("alignment") == "center":
              p.alignment = PP_ALIGN.CENTER

      def _render_shape(self, emu_bbox: Dict, shape_type: str, desc: str, style: Dict) -> None:
          """渲染形状（矩形、圆角矩形等）"""
          shape_enum = MSO_SHAPE.ROUNDED_RECTANGLE if "rounded" in shape_type else MSO_SHAPE.RECTANGLE

          shape = self.slide.shapes.add_shape(
              shape_enum,
              Emu(emu_bbox["left"]),
              Emu(emu_bbox["top"]),
              Emu(emu_bbox["width"]),
              Emu(emu_bbox["height"]),
          )
           设置填充色
          if style.get("fill_color"):
              shape.fill.solid()
              shape.fill.fore_color.rgb = RgbColor.from_string(style["fill_color"])

          # 设置边框
          if style.get("border_color"):
              shape.line.color.rgb = RgbColor.from_string(style["border_color"])
          if style.get("border_width"):
              shape.line.width = Pt(style["border_width"])

          # 添加文本
          text = self._extract_text_from_desc(desc)
          if text:
              shape.text = text

  5.3 VLM 节点渲染器 (vlm_node_renderer.py)

  处理 render_method="vlm" 的节点，插入预渲染的图片：

  class VLMNodeRenderer:
      """VLM 图片节点渲染器"""

      def __init__(self, slide, converter: CoordinateConverter):
          self.slide = slide
          self.converter = converter

      def render(self, node_id: str, bbox: Dict, image_path: str) -> None:
          """
          插入 VLM 渲染的图片
          
          Args:
              node_id: 节点 ID
              bbox: 像素级 bbox
              image_path: 图片文件路径
          """
          if not Path(image_path).exists():
              raise FileNotFoundError(f"VLM image not found: {image_path}")emu_bbox = self.converter.px_to_emu(bbox)

          # 插入图片
          self.slide.shapes.add_picture(
              image_path,
              Emu(emu_bbox["left"]),
              Emu(emu_bbox["top"]),
              Emu(emu_bbox["width"]),
              Emu(emu_bbox["height"]),
          )

  5.4 边渲染器 (edge_renderer.py)

  处理节点之间的连接线：

  from pptx.enum.shapes import MSO_CONNECTOR

  class EdgeRenderer:
      """边/连接线渲染器"""

      def __init__(self, slide, converter: CoordinateConverter, 
                   node_bboxes: Dict[str, Dict], global_style: Dict):
          self.slide = slide
          self.converter = converter
          self.node_bboxes = node_bboxes  # node_id -> bbox
          self.global_style = global_style

      def render(self, edge: Dict) -> None:
          """
          渲染一条边
          
          Args:
              edge: {"edge_id": "e1", "from": "n3", "to": "n4"}
          """
          from_node = edge["from"]
          to_node = edge["to"]

          if from_node not in self.node_bboxes or to_node not in self.node_bboxes:
              return  # 跳过无效边

          # 计算连接点
          from_bbox = self.node_bboxes[from_node]
          to_bbox = self.node_bboxes[to_node]

          start_point, end_point = self._calculate_connection_points(from_bbox, to_bbox)

          # 添加连接线
          connector = self.slide.shapes.add_connector(
              MSO_CONNECTOR.STRAIGHT,  # 或 MSO_CONNECTOR.ELBOW 用于折Emu(start_point[0]),
              Emu(start_point[1]),
              Emu(end_point[0]),
              Emu(end_point[1]),
          )

          # 设置样式
          self._apply_edge_style(connector)
      def _calculate_connection_points(self, from_bbox: Dict, to_bbox: Dict) -> Tuple:
          """
          计算两个节点之间的最佳连接点
          略: 根据相对位置选择边的中点
          - 如果 to 在 from 右边: from 的右边中点 -> to 的左边中点
          - 如果 to 在 from 下边: from 的下边中点 -> to 的上边中点
          """
          from_center = self.converter.get_center_point(from_bbox)
          to_center = self.converter.get_center_point(to_bbox)

          from_emu = self.converter.px_to_emu(from_bbox)
          to_emu = self.converter.px_to_emu(to_bbox)

          dx = to_center[0] - from_center[0]
          dy = to_center[1] - from_center[1]

          if abs(dx) > abs(dy):
              # 水平方向为主
              if dx > 0:
                  # to 在 from 右边
                  start = (from_emu["left"] + from_emu["width"],from_emu["top"] + from_emu["height"] // 2)
                  end = (to_emu["left"],to_emu["top"] + to_emu["height"] // 2)
              else:
                  # to 在 from 左边
                  start = (from_emu["left"],
                          from_emu["top"] + from_emu["height"] // 2)
                  end = (to_emu["left"] + to_emu["width"],
                        to_emu["top"] + to_emu["height"] // 2)
          else:
              # 垂直方向为主
              if dy > 0:
                  # to 在 from 下边
                  start = (from_emu["left"] + from_emu["width"] // 2,
                          from_emu["top"] + from_emu["height"])
                  end = (to_emu["left"] + to_emu["width"] // 2,
                        to_emu["top"])
              else:
                  # to 在 from 上边
                  start = (from_emu["left"] + from_emu["width"] // 2,
                          from_emu["top"])
                  end = (to_emu["left"] + to_emu["width"] // 2,
                        to_emu["top"] + to_emu["height"])

          return start, end

      def _apply_edge_style(self, connector) -> None:
          """应用边的样式"""
          # 线条颜色
          line_color = self.global_style.get("color_guidance", {}).get("neutral", "#808080")
          connector.line.color.rgb = RgbColor.from_string(line_color.lstrip("#"))

          # 线条宽度
          connector.line.width = Pt(1.5)

          # 箭头 (终点)
          connector.line.end_arrowhead = True

  5.5 主 Agent 实现 (pptx_composer_agent.py)

  from pptx import Presentation
  from pptx.util import Inches, Emu

  async def p2g_pptx_composer_agent(
      state: Paper2GraphState,
      output_path: str = None,
  ) -> Paper2GraphState:
      """
      PPTX 组装 Agent - 将所有元素组装成最终的 PowerPoint 文件
      
      输入:
          - state.layout_json: 布局信息 (像素级 bbox)
          - state.node_render_design: 节点渲染设计
          - state.vlm_rendered_nodes: VLM 渲染的图片路- state.semantic_json: 语义信息 (包含 edges)
      
      输出:
          - state.pptx_output_path: 生成的 PPTX 文件路径
      """
      # 1. 提取输入数据
      layout_json = state.layout_json
      node_render_design = state.node_render_design
      vlm_rendered_nodes = state.vlm_rendered_nodes or {}
      semantic_json = state.semantic_json

      canvas = layout_json.get("canvas", {"width": 1920, "height": 1080})
      node_positions = {n["node_id"]: n["bbox"] for n in layout_json["positions"]["nodes"]}
      edges = semantic_json.get("edges", [])
      global_style = node_render_design.get("global_style", {})

      # 2. 创建 PPTX 文档
      prs = Presentation()
      prs.slide_width = Inches(13.333)  # 16:9 宽屏
      prs.slide_height = Inches(7.5)

      # 添加空白幻灯片
      blank_layout = prs.slide_layouts[6]  # 空白布局
      slide = prs.slides.add_slide(blank_layout)

      # 3. 初始化坐标转换器
      converter = CoordinateConverter(
          canvas_width=canvas["width"],
          canvas_height=canvas["height"],
      )

      # 4. 初始化渲染器
      pptx_renderer = PPTXNodeRenderer(slide, converter, global_style)
      vlm_renderer = VLMNodeRenderer(slide, converter)
      edge_renderer = EdgeRenderer(slide, converter, node_positions, global_style)

      # 5. 构建 node_id -> render_info 映射
      render_info_map = {}
      for chunk in node_render_design.get("chunks", []):
          for node in chunk.get("nodes", []):
              render_info_map[node["node_id"]] = node

      # 6. 渲染所有节点
      for node_id, bbox in node_positions.items():
          render_info = render_info_map.get(node_id, {})
          render_method = render_info.get("render_method", "pptx")

          if render_method == "vlm":
              # VLM 渲染的节点 - 插入图片
              image_path = vlm_rendered_nodes.get(node_id)
              if image_path and Path(image_path).exists():
                  vlm_renderer.render(node_id, bbox, image_path)else:
                  log.warning(f"VLM image not found for node {node_id}, skipping")
          else: PPTX 原生渲染
              pptx_desc = render_info.get("pptx_desc", "")
              if pptx_desc:
                  pptx_renderer.render(node_id, bbox, pptx_desc)

      # 7. 渲染所有边
      for edge in edges:
          edge_renderer.render(edge)

      # 8. 保存文件
      if output_path is None:
          output_path = "/tmp/paper2graph_output.pptx"

      prs.save(output_path)
      state.pptx_output_path = output_path

      log.info(f"PPTX saved to: {output_path}")
      return state

  6. 样式解析器设计

  由于 pptx_desc 是自然语言描述，需要一个解析器提取关键样式信息：

  class StyleParser:
      """从 pptx_desc 自然语言描述中提取样式信息""" 颜色映射
      COLOR_MAP = {
          "dark gray": "#333333",
          "dark navy blue": "#1a237e",
          "navy blue": "#1a237e",
          "light gray": "#f5f5f5",
          "gray": "#808080",
          "white": "#ffffff",
          "black": "#000000",
      }

      # 字体大小映射
      FONT_SIZE_PATTERN = re.compile(r'(\d+)\s*pt', re.IGNORECASE)

      def parse(self, pptx_desc: str) -> Dict:
          """解析 pptx_desc 提取样式"""
          style = {}
          desc_lower = pptx_desc.lower()

          # 提取字体大小
          size_match = self.FONT_SIZE_PATTERN.search(pptx_desc)
          if size_match:
              style["font_size"] = int(size_match.group(1))

          # 提取粗体
          if "bold" in desc_lower:
              style["font_bold"] = True

          # 提取斜体
          if "italic" in desc_lower:
              style["font_italic"] = True

          # 提取对齐方式
          if "center" in desc_lower:
              style["alignment"] = "center"
          elif "left" in desc_lower:
              style["alignment"] = "left"
          elif "right" in desc_lower:
              style["alignment"] = "right"

          # 提取颜色
          for color_name, color_hex in self.COLOR_MAP.items():
              if color_name in desc_lower:
                  style["font_color"] = color_hex
                  break

          # 提取十六进制颜色
          hex_match = re.search(r'#([0-9a-fA-F]{6})', pptx_desc)
          if hex_match:
              style["fill_color"] = hex_match.group(0)

          return style
      def extract_text(self, pptx_desc: str) -> str:
          """从描述中提取要显示的文本内容"""
          # 匹配 Text: "..." 或 content: "..."
          patterns = [
              r'Text:\s*["\']([^"\']+)["\']',
              r'content[:\s]+["\']([^"\']+)["\']',
              r'labeled?\s+["\']([^"\']+)["\']',
          ]

          for pattern in patterns:
              match = re.search(pattern, pptx_desc, re.IGNORECASE)
              if match:
                  return match.group(1)

          return ""

  7. 测试文件设计

  # tests/test_p2g_pptx_composer_agent.py

  async def test_pptx_composer_full():
      """完整的 PPTX 组装测试"""
      # 加载测试数据
      layout_json = load_json("layout_pipeline/layout_json.json")
      node_render_design = load_json("render_design/node_render_design.json")
      semantic_json = load_json("layout_pipeline/semantic_json.json")

      # 模拟 VLM 渲染结果
      vlm_rendered_nodes = {
          "n3": "/tmp/vlm_nodes/chunk1_node3.png",
          "n4": "/tmp/vlm_nodes/chunk1_node4.png",
          # ...
      }

      # 构建 state
      state = Paper2GraphState()
      state.layout_json = layout_json
      state.node_render_design = node_render_design
      state.semantic_json = semantic_json
      state.vlm_rendered_nodes = vlm_rendered_nodes

      # 执行
      output_path = "/tmp/test_paper2graph.pptx"
      result_state = await p2g_pptx_composer_agent(state, output_path=output_path)

      # 验证
      assert Path(output_path).exists()
      assert result_state.pptx_output_path == output_path

  8. 关键设计决策

  | 决策点      | 选择              | 理由                  |
  |----------|-----------------|---------------------|
  | PPTX 库   | python-pptx     | 成熟稳定，API 完善         |
  | 坐标系统     | 像素 → EMU 转换     | 保持与 layout_json 一致  |
  | 节点渲染     | 分离 PPTX/VLM 渲染器 | 职责单一，易于扩展           |
  | 边渲染      | 智能连接点计算         | 根据相对位置自动选择最佳连接点     |
  | 样式解析     | 正则 + 关键词匹配      | 处理自然语言描述的 pptx_desc |
  | 是否使用 LLM | 否               | 纯算法实现，无需 LLM 调用     |

  9. 后续扩展点

  1. 分组支持: 将同一 chunk 的元素分组，便于整体移动
  2. 动画支持: 为节点和边添加出现动画
  3. 多页支持: 当内容过多时自动分页
  4. 模板支持: 支持自定义 PPTX 模板
  5. 导出格式: 支持导出为 PDF、PNG 等格式

  ---个设计方案完整覆盖了从布局信息到最终 PPTX 文件的全流程，与现有的 Pipeline 架构无缝集成。