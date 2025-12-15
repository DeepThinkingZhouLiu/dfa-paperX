from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, List
try:
    from dataflow.cli_funcs.paths import DataFlowPath
except Exception:
    class DataFlowPath:
        @staticmethod
        def get_dataflow_dir():
            return Path(__file__).resolve().parent

        @staticmethod
        def get_dataflow_statics_dir():
            return Path(__file__).resolve().parent.parent / "static"
current_file = Path(__file__).resolve()

BASE_DIR = DataFlowPath.get_dataflow_dir()
DATAFLOW_DIR = BASE_DIR.parent
STATICS_DIR = DataFlowPath.get_dataflow_statics_dir()
PROJDIR = current_file.parent.parent

from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# ==================== 最基础的 Request ====================
@dataclass
class MainRequest:
    """所有Request的基类，只包含核心字段"""
    # ① 用户偏好的自然语言
    language: str = "en"  # "en" | "zh" | ...

    # ② LLM 接口
    chat_api_url: str = "http://123.129.219.111:3000/v1"
    api_key: str = os.getenv("DF_API_KEY", "test")

    # ③ 选用的 LLM 名称
    model: str = "gpt-4o"

    # ④ 需求描述
    target: str = ""

    def get(self, key, default=None):
        return getattr(self, key, default)
    
    def __setitem__(self, key, value):
        setattr(self, key, value)


# ==================== 最基础的 State（所有State的祖先）====================
@dataclass
class MainState:
    """所有State的基类，只包含核心字段"""
    request: MainRequest = field(default_factory=MainRequest)
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
    # 通用字段
    agent_results: Dict[str, Any] = field(default_factory=dict)
    temp_data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __setitem__(self, key, value):
        setattr(self, key, value)


# ==================== 主流程 Request ====================
@dataclass
class DFRequest(MainRequest):
    """主流程的Request，继承自MainRequest"""
    # ⑤ 测试样例文件（仅 CLI 批量跑用）
    json_file: str = (
        f"{DATAFLOW_DIR}/dataflow/example/DataflowAgent/mq_test_data.jsonl"
    )

    # ⑥ Python 代码文件位置
    python_file_path: str = ""

    # ⑦ Debug 相关
    need_debug: bool = False
    max_debug_rounds: int = 3

    # ⑧ 本地模型相关
    use_local_model: bool = False
    local_model_path: str = ""

    # ⑨ 缓存和会话
    cache_dir: str = f"{PROJDIR}/cache_dir"
    session_id: str = "default_session"


# ==================== 主流程 State ====================
@dataclass
class DFState(MainState):
    """主流程的State，继承自MainState"""
    # 重写request类型为DFRequest
    request: DFRequest = field(default_factory=DFRequest)

    
    # 主流程特有字段
    category: Dict[str, Any] = field(default_factory=dict)
    recommendation: Dict[str, Any] = field(default_factory=dict)
    matched_ops: list[str] = field(default_factory=list)
    debug_mode: bool = False
    pipeline_structure_code: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    code_debug_result: Dict[str, Any] = field(default_factory=dict)
    debug_history: Dict[Any, Dict[str, Any]] = field(default_factory=dict)
    opname_and_params: List[Dict[str, Dict[str, Any]]] = field(default_factory=list)


# ==================== 数据采集 Request ====================
@dataclass
class DataCollectionRequest(MainRequest):
    """数据采集任务的Request，继承自MainRequest"""
    # 重写language默认值
    language: str = "English"
    
    # 数据采集特有的字段
    download_dir: str = os.path.join(STATICS_DIR, "data_collection")
    dataset_size_category: str = '1K<n<10K'
    dataset_num_limit: int = 5
    category: str = "PT"


# ==================== 数据采集 State ====================
@dataclass
class DataCollectionState(MainState):
    """数据采集任务的State，继承自MainState"""
    # 重写request类型为DataCollectionRequest
    request: DataCollectionRequest = field(default_factory=DataCollectionRequest)
    
    # 数据采集特有的字段
    keywords: list[str] = field(default_factory=list)
    datasets: Dict[str, list] = field(default_factory=dict)
    downloads: Dict[str, list] = field(default_factory=dict)
    sources: Dict[str, Dict] = field(default_factory=dict)


# Iconagent相关 State 和 Request 定义
# ==================== Icon 生成 Request ====================
@dataclass
class IconGenRequest(MainRequest):      
    keywords: str = ""
    style: str = ""

# ==================== Icon 生成 State ======================
@dataclass
class IconGenState(MainState):
    request: IconGenRequest = field(default_factory=IconGenRequest)

    # 下面是 icongen 自己的产物 / 临时数据
    icon_prompt: str = ""                                 # 生成的图标提示词
    img_save_path: str = ""                              # 生成的图标保存路径

    
# ==================== Web 爬取/研究 Request ====================
@dataclass
class WebCrawlRequest(MainRequest):
    """Web 爬取任务的 Request，继承自 MainRequest"""
    # 初始需求与下载目录
    initial_request: str = ""
    download_dir: str = os.path.join(STATICS_DIR, "web_crawl")

    # 爬取/研究配置
    search_engine: str = "tavily"     # 'tavily' | 'duckduckgo' | 'jina'
    use_jina_reader: bool = False
    enable_rag: bool = True


# ==================== Web 爬取/研究 State ====================
@dataclass
class WebCrawlState(MainState):
    """管理网络爬取与研究过程的状态"""
    # 重写 request 类型为 WebCrawlRequest
    request: WebCrawlRequest = field(default_factory=WebCrawlRequest)

    # 直通字段（为兼容调用方直接从 state 访问这些配置项）
    initial_request: str = ""
    download_dir: str = os.path.join(STATICS_DIR, "web_crawl")
    search_engine: str = "tavily"
    use_jina_reader: bool = False
    enable_rag: bool = True
    rag_manager: Any = None

    # 研究/爬取过程中的临时与产出数据
    sub_tasks: list[Dict[str, Any]] = field(default_factory=list)
    completed_sub_tasks: list[Dict[str, Any]] = field(default_factory=list)
    research_summary: Dict[str, Any] = field(default_factory=dict)
    search_results_text: str = ""
    filtered_urls: list[str] = field(default_factory=list)
    crawled_data: list[Dict[str, Any]] = field(default_factory=list)
    visited_urls: set[str] = field(default_factory=set)
    url_queue: list[str] = field(default_factory=list)
    is_finished: bool = False
    supervisor_feedback: str = "Process has not started."
    # 控制参数
    max_crawl_cycles_per_task: int = 5
    max_crawl_cycles_for_research: int = 15
    current_cycle: int = 0
    download_successful_for_current_task: bool = False

    def reset_for_new_task(self):
        self.search_results_text = ""
        self.filtered_urls = []
        self.visited_urls = set()
        self.url_queue = []
        self.current_cycle = 0
        self.download_successful_for_current_task = False


# ==================== Paper2Graph  Request ====================
@dataclass
class Paper2GraphRequest(MainRequest):      
    target: str = ""
    # 供下游 Agent 使用的约束与说明（若上游未提供，可为空，Agent 内置 fallback）
    header_json_desc: Dict[str, Any] = field(default_factory=dict)
    semantic_json_desc: Dict[str, Any] = field(default_factory=dict)
    layout_json_desc: Dict[str, Any] = field(default_factory=dict)
    design_json_desc: Dict[str, Any] = field(default_factory=dict)
    
    semantic_json_schema: Dict[str, Any] = field(default_factory=dict)
    layout_json_schema: Dict[str, Any] = field(default_factory=dict)
    design_json_schema: Dict[str, Any] = field(default_factory=dict)


# ==================== Paper2Graph State ====================
@dataclass
class Paper2GraphState(MainState):
    request: Paper2GraphRequest = field(default_factory=Paper2GraphRequest)

    # enriched_description 为结构化对象，包含 semantic_desc 与 layout_desc
    enriched_description: Dict[str, Any] = field(default_factory=dict)

    # 各阶段 JSON 的承载结构：语义/布局/美学设计及最终 PaperGraph JSON
    header_json: Dict[str, Any] = field(default_factory=dict)
    semantic_json: Dict[str, Any] = field(default_factory=dict)
    layout_plan: Dict[str, Any] = field(default_factory=dict)  # 布局规划（grid级别）
    # node 级布局规划结果，由 p2g_node_layout_planner_agent 生成
    node_layout_plan: Dict[str, Any] = field(default_factory=dict)
    # 最终的 layout_json，包含 chunks/nodes 的像素级 bbox
    layout_json: Dict[str, Any] = field(default_factory=dict)
    design_json: Dict[str, Any] = field(default_factory=dict)
    final_json: Dict[str, Any] = field(default_factory=dict)

    # Checker 相关字段
    layout_error_info: str = ""
    wireframe_url: str = ""
    semantic_gap: str = ""
    
    # Node 渲染设计结果，由 p2g_node_render_design_agent 生成
    node_render_design: Dict[str, Any] = field(default_factory=dict)

    # PPTX 节点的结构化渲染规格 (node_id -> PPTXRenderSpec)
    # 由 p2g_pptx_desc_parser_agent 生成
    pptx_render_specs: Dict[str, Any] = field(default_factory=dict)

    # VLM 渲染结果 (node_id -> image_path)
    # 由 p2g_vlm_node_renderer_agent 生成
    vlm_rendered_nodes: Dict[str, str] = field(default_factory=dict)

    # 最终 PPTX 输出路径
    # 由 p2g_pptx_composer_agent 生成
    pptx_output_path: str = ""

    # ==================== Chunk-Based Pipeline 字段 ====================

    # chunk_layout_constructor_agent 输出
    # 包含 canvas 尺寸、chunks bbox、内部布局、inter-chunk 连接
    chunk_layout_json: Dict[str, Any] = field(default_factory=dict)

    # chunk_vlm_design_agent 输出
    # chunk_id -> {prompt, style_config, elements, ...}
    chunk_vlm_designs: Dict[str, Any] = field(default_factory=dict)

    # chunk_render_agent 输出
    # chunk_id -> {path, bbox, render_status, ...}
    chunk_images: Dict[str, Any] = field(default_factory=dict)
    chunk_render_errors: Dict[str, str] = field(default_factory=dict)

    # pptx_composer_agent SAM 提取结果
    # node_id -> {chunk_id, bbox_in_chunk, bbox_in_canvas, cropped_path, ...}
    extracted_nodes: Dict[str, Any] = field(default_factory=dict)


# ==================== Chunk-Based P2G Pipeline (独立) ====================
# 这是一套独立的 chunk 级别绘制 pipeline，不影响原有的 node 级别绘制

@dataclass
class ChunkP2GRequest(MainRequest):
    """Chunk-Based Paper2Graph Pipeline 的 Request"""
    target: str = ""

    # 画布配置
    canvas_width: int = 1920
    canvas_height: int = 1080

    # Chunk 配置
    max_chunks: int = 6  # 最大 chunk 数量
    min_nodes_per_chunk: int = 2  # 每个 chunk 最小节点数
    max_nodes_per_chunk: int = 8  # 每个 chunk 最大节点数

    # 渲染配置
    vlm_model: str = "gemini-3-pro-image-preview"
    vlm_concurrency: int = 4
    vlm_timeout: int = 180

    # 输出配置
    output_dir: str = ".tmp/chunk_pipeline_output"


@dataclass
class ChunkP2GState(MainState):
    """Chunk-Based Paper2Graph Pipeline 的 State

    Pipeline 流程:
    1. semantic_constructor -> semantic_json
    2. chunk_layout_planner -> chunk_layout_json
    3. chunk_vlm_designer -> chunk_vlm_designs
    4. chunk_renderer -> chunk_images
    5. chunk_pptx_composer -> pptx_output_path
    """
    request: ChunkP2GRequest = field(default_factory=ChunkP2GRequest)

    # ==================== Stage 1: Semantic Constructor ====================
    # 语义结构，只包含 chunks 列表
    semantic_json: Dict[str, Any] = field(default_factory=dict)
    # 结构示例:
    # {
    #   "chunks": [
    #     {
    #       "chunk_id": "c1",
    #       "chunk_content": "详细描述该 chunk 要绘制的内容，包括所有视觉元素、布局、连接关系等"
    #     }
    #   ]
    # }

    # ==================== Stage 2: Chunk Layout Planner ====================
    # 布局信息，只包含 chunk_id 和 bbox
    chunk_layout_json: Dict[str, Any] = field(default_factory=dict)
    # 结构示例:
    # {
    #   "canvas": {"width": 1920, "height": 1080},
    #   "chunks": [
    #     {
    #       "chunk_id": "c1",
    #       "bbox": {"x": 100, "y": 50, "w": 600, "h": 400}
    #     }
    #   ]
    # }

    # ==================== Stage 3: Chunk VLM Designer ====================
    # VLM prompt 设计，chunk_id -> {prompt, ratio}
    chunk_vlm_designs: Dict[str, Any] = field(default_factory=dict)
    # 结构示例:
    # {
    #   "c1": {
    #     "prompt": "Create a scientific diagram...",
    #     "ratio": "4:3"  # 宽高比，如 "4:3", "16:9", "2:1", "1:1"
    #   }
    # }

    # ==================== Stage 4: Chunk Renderer ====================
    # 渲染结果，chunk_id -> {path, bbox, render_status, ...}
    chunk_images: Dict[str, Any] = field(default_factory=dict)
    # 结构示例:
    # {
    #   "c1": {
    #     "path": "/output/chunks/c1.png",
    #     "bbox": {"x": 100, "y": 50, "w": 600, "h": 400},
    #     "render_status": "success",
    #     "render_time_ms": 3500
    #   }
    # }

    # 渲染错误记录
    chunk_render_errors: Dict[str, str] = field(default_factory=dict)

    # ==================== Stage 5: PPTX Composer ====================
    # 最终 PPTX 输出路径
    pptx_output_path: str = ""

    # SAM 提取的元素（后续实现）
    extracted_elements: Dict[str, Any] = field(default_factory=dict)


# ==================== Film-Strip P2G Pipeline (Bottom-Up) ====================
# 这是一套新的 bottom-up pipeline：先生成素材（VLM连环画+PPTX原生形状），再基于实际尺寸布局

@dataclass
class FilmStripP2GRequest(MainRequest):
    """Film-Strip Bottom-Up Paper2Graph Pipeline 的 Request"""
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


@dataclass
class FilmStripP2GState(MainState):
    """Film-Strip Bottom-Up Paper2Graph Pipeline 的 State

    Pipeline 流程:
    1. node_graph_constructor -> node_graph_json
    2. render_method_classifier -> render_plan_json
    3. vlm_group_planner -> vlm_group_plan_json
    4. pptx_spec_generator -> pptx_render_specs
    5. filmstrip_renderer -> vlm_rendered_nodes + vlm_node_assets
    6. layout_engine -> layout_json
    7. pptx_composer -> pptx_output_path
    """
    request: FilmStripP2GRequest = field(default_factory=FilmStripP2GRequest)

    # ==================== Stage 1: Node Graph ====================
    # Stage 1A (node_graph_constructor): 生成 nodes，edges=[]
    # Stage 1B (edge_planner): 填充 edges，包含 from_anchor/to_anchor
    node_graph_json: Dict[str, Any] = field(default_factory=dict)
    # {
    #   "title": "...",
    #   "global_style": {...},
    #   "nodes": [{
    #     "node_id": "n1",
    #     "label": "...",
    #     "role": "input|process|output|aux",
    #     "semantic_desc": "...",
    #     "visual_desc": "...",
    #     "constraints": {"no_text_inside": false}
    #   }],
    #   "edges": [{
    #     "edge_id": "e1",
    #     "from": "n1",
    #     "from_anchor": "left|right|top|bottom",  # 可选，绘图提示
    #     "to": "n2",
    #     "to_anchor": "left|right|top|bottom",    # 可选，绘图提示
    #     "edge_type": "data_flow|control_flow|annotation",
    #     "label": "",
    #     "direction_hint": "left_to_right|top_to_bottom|..."
    #   }]
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
