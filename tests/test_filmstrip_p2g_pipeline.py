"""测试 Film-Strip Bottom-Up Paper2Graph Pipeline

测试完整的 Film-Strip 级别绘制 pipeline：
1A. node_graph_constructor - 构建节点图（只有 nodes，edges=[]）
1B. edge_planner - 规划 edges（包含 from_anchor/to_anchor）
2. render_method_classifier - 分类渲染方式（VLM vs PPTX）
3. vlm_group_planner - VLM 节点分组 + 连环画 prompt
4. pptx_spec_generator - PPTX 节点渲染规格
5. filmstrip_renderer - VLM 生成连环画 + 切图 + 去背景
6. layout_engine - 基于实际尺寸布局
7. pptx_composer - 组装 PPTX
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

# 避免导入时自动加载
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")
os.environ.setdefault("DF_SKIP_WORKFLOW_AUTOINIT", "1")

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.state import FilmStripP2GState, FilmStripP2GRequest

# 输出根目录
OUTPUT_ROOT = Path(__file__).parent / ".tmp" / "filmstrip_p2g_pipeline"

# 当前运行的输出目录（在 main 中初始化）
OUTPUT_DIR: Path = OUTPUT_ROOT


class TeeLogger:
    """同时输出到控制台和文件的日志记录器"""

    def __init__(self, log_file: Path):
        self.terminal = sys.stdout
        self.log_file = log_file
        self.log_buffer = StringIO()

    def write(self, message):
        self.terminal.write(message)
        self.log_buffer.write(message)

    def flush(self):
        self.terminal.flush()
        # 每次 flush 时写入文件
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(self.log_buffer.getvalue())
        self.log_buffer = StringIO()

    def close(self):
        # 确保最后的内容被写入
        if self.log_buffer.getvalue():
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(self.log_buffer.getvalue())


def generate_target_hash(target: str, length: int = 8) -> str:
    """生成 TEST_TARGET 的短哈希"""
    return hashlib.md5(target.strip().encode()).hexdigest()[:length]


def create_run_directory(target: str, run_id: str | None = None) -> Path:
    """创建本次运行的输出目录

    目录格式: {target_hash}_{timestamp}_{run_id}
    """
    target_hash = generate_target_hash(target)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if run_id:
        dir_name = f"{target_hash}_{timestamp}_{run_id}"
    else:
        dir_name = f"{target_hash}_{timestamp}"

    run_dir = OUTPUT_ROOT / dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # 创建/更新 latest 符号链接
    latest_link = OUTPUT_ROOT / "latest"
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(run_dir.name)

    return run_dir


def save_run_config(
    output_dir: Path,
    target: str,
    stage: str,
    models: dict,
    extra_info: dict | None = None,
):
    """保存运行配置"""
    config = {
        "run_time": datetime.now().isoformat(),
        "test_target": target,
        "test_target_hash": generate_target_hash(target),
        "stage": stage,
        "models": models,
    }
    if extra_info:
        config.update(extra_info)

    config_path = output_dir / "run_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Saved run config: {config_path}")

# ============================================================================
# 各环节模型配置（可通过环境变量覆盖）
# ============================================================================
# Stage 1A: Node Graph Constructor - 节点图构建模型（只生成 nodes）
MODEL_NODE_GRAPH = os.getenv("MODEL_NODE_GRAPH", "gpt-5.2")
# Stage 1B: Edge Planner - 边规划模型（生成 edges，包含 anchors）
MODEL_EDGE_PLANNER = os.getenv("MODEL_EDGE_PLANNER", "gpt-4o")
# Stage 2: Render Method Classifier - 渲染方式分类模型
MODEL_CLASSIFIER = os.getenv("MODEL_CLASSIFIER", "gpt-5.2")
# Stage 3: VLM Group Planner - VLM 分组规划模型
MODEL_VLM_PLANNER = os.getenv("MODEL_VLM_PLANNER", "gpt-4o")
# Stage 4: PPTX Spec Generator - PPTX 规格生成模型
MODEL_PPTX_SPEC = os.getenv("MODEL_PPTX_SPEC", "gpt-5.2")
# Stage 5: Film-Strip Renderer - VLM 图像生成模型
MODEL_VLM_RENDER = os.getenv("MODEL_VLM_RENDER", "gemini-3-pro-image-preview")
# Stage 6: Layout Engine - 纯计算函数，不需要模型


# 测试用的 target 描述
# TEST_TARGET = """
# 画一张英文的弱监督语义分割论文中的科研配图，图像级标签，单阶段方法，直接通过segformer的backbone提取特征图，这里首先有一个分类损失，然后是解码器生成预测的分割图，还有一路生成伪标签，对预测的分割图进行交叉熵损失的监督，创新点是像素级学习不足，输入层新增定位专用token，更小的patch聚类、Memory bank, Adapter
# """

TEST_TARGET = """
论文提出的 Early Experience（早期经验）范式，是衔接模仿学习（IL）与强化学习（RL）的核心框架，模型图需突出‘数据构建 - 双方法训练’核心流程：1. 基础输入与数据构建：以专家数据集 D_expert = {(s_i, a_i)}（s_i 为专家状态，a_i 为对应专家动作）为起点，对每个 s_i，从初始 LLM 策略中采样 K 个非专家备选动作 {a_i^1, a_i^2, ..., a_i^K}；在环境中分别执行 a_i（得到未来状态 s_{i+1}）与各 a_i^j（得到未来状态 s_i^j），构建 rollout 三元组数据集 D_rollout = {(s_i, a_i^j, s_i^j)}，以未来状态作为无奖励监督信号。2. 双核心方法分支：① 隐式世界建模（IWM）：输入 D_rollout 中的 (s_i, a_i^j)，让 LLM 策略学习预测对应未来状态 s_i^j，转化为 LLM 的下 token 预测任务，通过负对数似然损失使策略内化环境动态；② 自我反思（SR）：对每个 s_i，对比 a_i 对应的 s_{i+1} 与 a_i^j 对应的 s_i^j，引导 LLM 生成‘专家动作更优’的自然语言解释 c_i^j，构建反思数据集 D_refl = {(s_i, a_i^j, c_i^j)}，联合 D_expert 训练策略，使模型同时预测 c_i^j 与专家动作 a_i。
"""

def save_json(data: dict, filename: str):
    """保存 JSON 文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


async def test_stage1a_node_graph_constructor():
    """测试 Stage 1A: Node Graph Constructor (Nodes Only)"""
    from dataflow_agent.agentroles.p2g_filmstrip_node_graph_constructor_agent import (
        p2g_filmstrip_node_graph_constructor_agent,
    )

    print("=" * 60)
    print("Stage 1A: Testing Node Graph Constructor (Nodes Only)")
    print(f"  Model: {MODEL_NODE_GRAPH}")
    print("=" * 60)

    request = FilmStripP2GRequest(
        target=TEST_TARGET,
        model=MODEL_NODE_GRAPH,
        canvas_width=1920,
        canvas_height=1080,
        output_dir=str(OUTPUT_DIR),
    )
    state = FilmStripP2GState(request=request)

    state = await p2g_filmstrip_node_graph_constructor_agent(
        state,
        model_name=MODEL_NODE_GRAPH,
    )

    node_graph_json = getattr(state, "node_graph_json", {})

    print(f"\nResult:")
    print(f"  Title: {node_graph_json.get('title', 'N/A')}")
    print(f"  Nodes: {len(node_graph_json.get('nodes', []))}")
    print(f"  Edges: {len(node_graph_json.get('edges', []))} (should be 0 for Stage 1A)")

    # 打印节点信息
    for node in node_graph_json.get("nodes", []):
        print(f"\n  {node['node_id']}: {node.get('label', 'N/A')}")
        print(f"    Role: {node.get('role', 'N/A')}")
        print(f"    Semantic: {node.get('semantic_desc', 'N/A')[:80]}...")

    save_json(node_graph_json, "stage1a_node_graph_json.json")

    return state


async def test_stage1b_edge_planner(state: FilmStripP2GState = None):
    """测试 Stage 1B: Edge Planner"""
    from dataflow_agent.agentroles.p2g_filmstrip_edge_planner_agent import (
        p2g_filmstrip_edge_planner_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 1B: Testing Edge Planner")
    print(f"  Model: {MODEL_EDGE_PLANNER}")
    print("=" * 60)

    if state is None:
        # 从文件加载
        node_graph_path = OUTPUT_DIR / "stage1a_node_graph_json.json"
        if not node_graph_path.exists():
            print("ERROR: Run stage1a first!")
            return None

        with open(node_graph_path, "r") as f:
            node_graph_json = json.load(f)

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            model=MODEL_EDGE_PLANNER,
            output_dir=str(OUTPUT_DIR),
        )
        state = FilmStripP2GState(request=request)
        state.node_graph_json = node_graph_json

    state = await p2g_filmstrip_edge_planner_agent(
        state,
        model_name=MODEL_EDGE_PLANNER,
    )

    node_graph_json = getattr(state, "node_graph_json", {})
    edges = node_graph_json.get("edges", [])

    print(f"\nResult:")
    print(f"  Edges: {len(edges)}")

    # 打印边信息（包含 anchors）
    print(f"\nEdge Details:")
    for edge in edges:
        edge_id = edge.get('edge_id', 'N/A')
        from_node = edge.get('from', 'N/A')
        to_node = edge.get('to', 'N/A')
        from_anchor = edge.get('from_anchor', '')
        to_anchor = edge.get('to_anchor', '')
        edge_type = edge.get('edge_type', 'N/A')
        label = edge.get('label', '')

        anchor_info = ""
        if from_anchor or to_anchor:
            anchor_info = f" [{from_anchor or '?'} → {to_anchor or '?'}]"

        label_info = f" '{label}'" if label else ""
        print(f"  {edge_id}: {from_node} → {to_node}{anchor_info} ({edge_type}){label_info}")

    # 保存完整的 node_graph_json（包含 edges）
    save_json(node_graph_json, "stage1_node_graph_json.json")
    # 单独保存 edges 方便调试
    save_json({"edges": edges}, "stage1b_edges_json.json")

    return state


# 保留旧的函数名作为别名，兼容旧的调用方式
async def test_stage1_node_graph_constructor():
    """测试 Stage 1: Node Graph Constructor (完整流程：1A + 1B)"""
    state = await test_stage1a_node_graph_constructor()
    state = await test_stage1b_edge_planner(state)
    return state


async def test_stage2_render_method_classifier(state: FilmStripP2GState = None):
    """测试 Stage 2: Render Method Classifier"""
    from dataflow_agent.agentroles.p2g_filmstrip_render_method_classifier_agent import (
        p2g_filmstrip_render_method_classifier_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 2: Testing Render Method Classifier")
    print(f"  Model: {MODEL_CLASSIFIER}")
    print("=" * 60)

    if state is None:
        # 从文件加载
        node_graph_path = OUTPUT_DIR / "stage1_node_graph_json.json"
        if not node_graph_path.exists():
            print("ERROR: Run stage1 first!")
            return None

        with open(node_graph_path, "r") as f:
            node_graph_json = json.load(f)

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            model=MODEL_CLASSIFIER,
            output_dir=str(OUTPUT_DIR),
        )
        state = FilmStripP2GState(request=request)
        state.node_graph_json = node_graph_json

    state = await p2g_filmstrip_render_method_classifier_agent(
        state,
        model_name=MODEL_CLASSIFIER,
    )

    render_plan_json = getattr(state, "render_plan_json", {})

    print(f"\nResult:")
    print(f"  VLM Nodes: {render_plan_json.get('vlm_nodes', [])}")
    print(f"  PPTX Nodes: {render_plan_json.get('pptx_nodes', [])}")

    # 打印每个节点的分类详情
    by_node = render_plan_json.get("by_node", {})
    print(f"\nNode Details ({len(by_node)} nodes):")
    for node_id, info in by_node.items():
        method = info.get("render_method", "N/A")
        size_hint = info.get("size_hint", {})
        if method == "vlm":
            desc = info.get("vlm_desc", "N/A")[:50]
            print(f"  {node_id} [VLM]: {desc}...")
        else:
            intent = info.get("pptx_intent", "N/A")[:50]
            print(f"  {node_id} [PPTX]: {intent}...")
        print(f"    Size hint: {size_hint}")

    save_json(render_plan_json, "stage2_render_plan_json.json")

    return state


async def test_stage3_vlm_group_planner(state: FilmStripP2GState = None):
    """测试 Stage 3: VLM Group Planner"""
    from dataflow_agent.agentroles.p2g_filmstrip_vlm_group_planner_agent import (
        p2g_filmstrip_vlm_group_planner_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 3: Testing VLM Group Planner")
    print(f"  Model: {MODEL_VLM_PLANNER}")
    print("=" * 60)

    if state is None:
        # 从文件加载
        node_graph_path = OUTPUT_DIR / "stage1_node_graph_json.json"
        render_plan_path = OUTPUT_DIR / "stage2_render_plan_json.json"

        if not node_graph_path.exists() or not render_plan_path.exists():
            print("ERROR: Run stage1 and stage2 first!")
            return None

        with open(node_graph_path, "r") as f:
            node_graph_json = json.load(f)
        with open(render_plan_path, "r") as f:
            render_plan_json = json.load(f)

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            model=MODEL_VLM_PLANNER,
            output_dir=str(OUTPUT_DIR),
        )
        state = FilmStripP2GState(request=request)
        state.node_graph_json = node_graph_json
        state.render_plan_json = render_plan_json

    state = await p2g_filmstrip_vlm_group_planner_agent(
        state,
        model_name=MODEL_VLM_PLANNER,
    )

    vlm_group_plan_json = getattr(state, "vlm_group_plan_json", {})
    groups = vlm_group_plan_json.get("groups", [])

    print(f"\nResult:")
    print(f"  Total Groups: {len(groups)}")

    # 打印每个分组的详情
    for group in groups:
        group_id = group.get("group_id", "N/A")
        node_ids = group.get("node_ids", [])
        subject = group.get("subject", "N/A")
        prompt = group.get("prompt", "")

        print(f"\n  Group {group_id}:")
        print(f"    Node IDs: {node_ids}")
        print(f"    Subject: {subject[:80]}...")
        print(f"    Prompt length: {len(prompt)} chars")
        # 打印 prompt 的前几行
        prompt_lines = prompt.split("\n")[:5]
        for line in prompt_lines:
            if line.strip():
                print(f"      {line[:70]}...")

    save_json(vlm_group_plan_json, "stage3_vlm_group_plan_json.json")

    return state


async def test_stage4_pptx_spec_generator(state: FilmStripP2GState = None):
    """测试 Stage 4: PPTX Spec Generator"""
    from dataflow_agent.agentroles.p2g_filmstrip_pptx_spec_generator_agent import (
        p2g_filmstrip_pptx_spec_generator_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 4: Testing PPTX Spec Generator")
    print(f"  Model: {MODEL_PPTX_SPEC}")
    print("=" * 60)

    if state is None:
        # 从文件加载
        node_graph_path = OUTPUT_DIR / "stage1_node_graph_json.json"
        render_plan_path = OUTPUT_DIR / "stage2_render_plan_json.json"

        if not node_graph_path.exists() or not render_plan_path.exists():
            print("ERROR: Run stage1 and stage2 first!")
            return None

        with open(node_graph_path, "r") as f:
            node_graph_json = json.load(f)
        with open(render_plan_path, "r") as f:
            render_plan_json = json.load(f)

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            model=MODEL_PPTX_SPEC,
            output_dir=str(OUTPUT_DIR),
        )
        state = FilmStripP2GState(request=request)
        state.node_graph_json = node_graph_json
        state.render_plan_json = render_plan_json

    state = await p2g_filmstrip_pptx_spec_generator_agent(
        state,
        model_name=MODEL_PPTX_SPEC,
    )

    pptx_render_specs = getattr(state, "pptx_render_specs", {})

    print(f"\nResult:")
    print(f"  Total Specs: {len(pptx_render_specs)}")

    # 打印每个 spec 的详情
    for node_id, spec in pptx_render_specs.items():
        element_type = spec.get("element_type", "N/A")
        text = spec.get("text", "N/A")
        fill_color = spec.get("shape_style", {}).get("fill_color", "N/A")
        font_size = spec.get("text_style", {}).get("font_size", "N/A")

        print(f"\n  {node_id}:")
        print(f"    Type: {element_type}")
        print(f"    Text: {text}")
        print(f"    Fill: {fill_color}")
        print(f"    Font Size: {font_size}pt")

    save_json(pptx_render_specs, "stage4_pptx_render_specs.json")

    return state


async def test_stage5_filmstrip_renderer(state: FilmStripP2GState = None):
    """测试 Stage 5: Filmstrip Renderer"""
    from dataflow_agent.agentroles.p2g_filmstrip_renderer_agent import (
        p2g_filmstrip_renderer_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 5: Testing Filmstrip Renderer")
    print(f"  VLM Model: {MODEL_VLM_RENDER}")
    print("=" * 60)

    if state is None:
        # 从文件加载
        vlm_group_plan_path = OUTPUT_DIR / "stage3_vlm_group_plan_json.json"

        if not vlm_group_plan_path.exists():
            print("ERROR: Run stage3 first!")
            return None

        with open(vlm_group_plan_path, "r") as f:
            vlm_group_plan_json = json.load(f)

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            vlm_model=MODEL_VLM_RENDER,
            output_dir=str(OUTPUT_DIR),
        )
        state = FilmStripP2GState(request=request)
        state.vlm_group_plan_json = vlm_group_plan_json

    state = await p2g_filmstrip_renderer_agent(
        state,
        vlm_model=MODEL_VLM_RENDER,
        vlm_timeout=600,
        concurrency=2,
    )

    filmstrip_images = getattr(state, "filmstrip_images", {})
    vlm_rendered_nodes = getattr(state, "vlm_rendered_nodes", {})
    vlm_node_assets = getattr(state, "vlm_node_assets", {})
    filmstrip_render_errors = getattr(state, "filmstrip_render_errors", {})

    print(f"\nResult:")
    print(f"  Filmstrips: {len(filmstrip_images)}")
    print(f"  Rendered Nodes: {len(vlm_rendered_nodes)}")
    print(f"  Errors: {len(filmstrip_render_errors)}")

    # 打印 filmstrip 详情
    print(f"\nFilmstrip Details:")
    for group_id, info in filmstrip_images.items():
        status = info.get("status", "N/A")
        render_time = info.get("render_time_ms", 0)
        if status == "ok":
            print(f"  {group_id}: OK ({render_time}ms)")
            print(f"    Path: {info.get('path', 'N/A')}")
        else:
            print(f"  {group_id}: ERROR - {info.get('error', 'N/A')}")

    # 打印节点资产详情
    print(f"\nNode Assets:")
    for node_id, asset in vlm_node_assets.items():
        w = asset.get("width_px", 0)
        h = asset.get("height_px", 0)
        group_id = asset.get("source_group_id", "N/A")
        panel_idx = asset.get("panel_index", -1)
        print(f"  {node_id}: {w}x{h}px (group={group_id}, panel={panel_idx})")

    # 保存结果
    save_json(filmstrip_images, "stage5_filmstrip_images.json")
    save_json(vlm_node_assets, "stage5_vlm_node_assets.json")

    if filmstrip_render_errors:
        save_json(filmstrip_render_errors, "stage5_render_errors.json")

    return state


async def test_stage6_layout_engine(state: FilmStripP2GState = None):
    """测试 Stage 6: Layout Engine"""
    from dataflow_agent.agentroles.p2g_filmstrip_layout_engine_agent import (
        p2g_filmstrip_layout_engine_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 6: Testing Layout Engine")
    print("  (Pure computation, no LLM)")
    print("=" * 60)

    if state is None:
        # 从文件加载
        node_graph_path = OUTPUT_DIR / "stage1_node_graph_json.json"
        render_plan_path = OUTPUT_DIR / "stage2_render_plan_json.json"
        vlm_node_assets_path = OUTPUT_DIR / "stage5_vlm_node_assets.json"
        pptx_render_specs_path = OUTPUT_DIR / "stage4_pptx_render_specs.json"

        missing_files = []
        if not node_graph_path.exists():
            missing_files.append("stage1")
        if not render_plan_path.exists():
            missing_files.append("stage2")
        if not vlm_node_assets_path.exists():
            missing_files.append("stage5")
        if not pptx_render_specs_path.exists():
            missing_files.append("stage4")

        if missing_files:
            print(f"ERROR: Run {', '.join(missing_files)} first!")
            return None

        with open(node_graph_path, "r") as f:
            node_graph_json = json.load(f)
        with open(render_plan_path, "r") as f:
            render_plan_json = json.load(f)
        with open(vlm_node_assets_path, "r") as f:
            vlm_node_assets = json.load(f)
        with open(pptx_render_specs_path, "r") as f:
            pptx_render_specs = json.load(f)

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            output_dir=str(OUTPUT_DIR),
            canvas_width=1920,
            canvas_height=1080,
        )
        state = FilmStripP2GState(request=request)
        state.node_graph_json = node_graph_json
        state.render_plan_json = render_plan_json
        state.vlm_node_assets = vlm_node_assets
        state.pptx_render_specs = pptx_render_specs

    state = await p2g_filmstrip_layout_engine_agent(state)

    layout_json = getattr(state, "layout_json", {})
    positions = layout_json.get("positions", {})
    nodes = positions.get("nodes", [])
    meta = layout_json.get("meta", {})

    print(f"\nResult:")
    print(f"  Canvas: {layout_json.get('canvas', {})}")
    print(f"  Nodes positioned: {len(nodes)}")
    print(f"  Spine: {meta.get('spine', [])}")
    print(f"  Scale factor: {meta.get('scale_factor', 1.0):.2f}")

    # 打印每个节点的位置
    print(f"\nNode Positions:")
    for node in nodes:
        node_id = node.get("node_id", "N/A")
        bbox = node.get("bbox", {})
        x, y = bbox.get("x", 0), bbox.get("y", 0)
        w, h = bbox.get("w", 0), bbox.get("h", 0)
        print(f"  {node_id}: ({x}, {y}) {w}x{h}")

    save_json(layout_json, "stage6_layout_json.json")

    return state


async def test_stage7_pptx_composer(state: FilmStripP2GState = None):
    """测试 Stage 7: PPTX Composer"""
    from dataflow_agent.agentroles.p2g_filmstrip_pptx_composer_agent import (
        p2g_filmstrip_pptx_composer_agent,
    )

    print("\n" + "=" * 60)
    print("Stage 7: Testing PPTX Composer")
    print("  (Pure computation, no LLM)")
    print("=" * 60)

    if state is None:
        # 从文件加载
        node_graph_path = OUTPUT_DIR / "stage1_node_graph_json.json"
        render_plan_path = OUTPUT_DIR / "stage2_render_plan_json.json"
        pptx_render_specs_path = OUTPUT_DIR / "stage4_pptx_render_specs.json"
        vlm_node_assets_path = OUTPUT_DIR / "stage5_vlm_node_assets.json"
        layout_json_path = OUTPUT_DIR / "stage6_layout_json.json"

        missing_files = []
        if not node_graph_path.exists():
            missing_files.append("stage1")
        if not render_plan_path.exists():
            missing_files.append("stage2")
        if not pptx_render_specs_path.exists():
            missing_files.append("stage4")
        if not vlm_node_assets_path.exists():
            missing_files.append("stage5")
        if not layout_json_path.exists():
            missing_files.append("stage6")

        if missing_files:
            print(f"ERROR: Run {', '.join(missing_files)} first!")
            return None

        with open(node_graph_path, "r") as f:
            node_graph_json = json.load(f)
        with open(render_plan_path, "r") as f:
            render_plan_json = json.load(f)
        with open(pptx_render_specs_path, "r") as f:
            pptx_render_specs = json.load(f)
        with open(vlm_node_assets_path, "r") as f:
            vlm_node_assets = json.load(f)
        with open(layout_json_path, "r") as f:
            layout_json = json.load(f)

        # 构建 vlm_rendered_nodes（从 vlm_node_assets 提取路径）
        vlm_rendered_nodes = {
            node_id: asset.get("path", "")
            for node_id, asset in vlm_node_assets.items()
        }

        request = FilmStripP2GRequest(
            target=TEST_TARGET,
            output_dir=str(OUTPUT_DIR),
            canvas_width=1920,
            canvas_height=1080,
        )
        state = FilmStripP2GState(request=request)
        state.node_graph_json = node_graph_json
        state.render_plan_json = render_plan_json
        state.pptx_render_specs = pptx_render_specs
        state.vlm_rendered_nodes = vlm_rendered_nodes
        state.layout_json = layout_json

    output_path = str(OUTPUT_DIR / "filmstrip_output.pptx")

    state = await p2g_filmstrip_pptx_composer_agent(
        state,
        output_path=output_path,
        render_edges=True,
    )

    pptx_output_path = getattr(state, "pptx_output_path", "")
    agent_result = state.agent_results.get("p2g_filmstrip_pptx_composer_agent", {})

    print(f"\nResult:")
    print(f"  Status: {agent_result.get('status', 'N/A')}")
    print(f"  Output Path: {pptx_output_path}")

    stats = agent_result.get("stats", {})
    if stats:
        print(f"  PPTX Nodes: {stats.get('pptx_nodes_rendered', 0)}")
        print(f"  VLM Nodes: {stats.get('vlm_nodes_rendered', 0)}")
        print(f"  Edges: {stats.get('edges_rendered', 0)}")
        if stats.get("errors"):
            print(f"  Errors: {stats['errors']}")

    # 自动将 PPTX 转换为预览图片
    if pptx_output_path and os.path.exists(pptx_output_path):
        print("\n--- Generating PPTX preview image ---")
        try:
            from dataflow_agent.toolkits.pptx_composer.pptx_to_image import convert_pptx_to_images

            success, image_paths = convert_pptx_to_images(
                pptx_path=pptx_output_path,
                output_dir=str(OUTPUT_DIR),
                output_format="png",
                dpi=150,
            )

            if success and image_paths:
                print(f"  Preview image(s) generated:")
                for img_path in image_paths:
                    print(f"    - {img_path}")
                # 保存预览图路径到 state
                state.agent_results["pptx_preview_images"] = image_paths
            else:
                print("  Warning: Failed to generate preview image")
                print("  Make sure LibreOffice and pdftoppm (poppler-utils) are installed:")
                print("    sudo apt-get install libreoffice poppler-utils")
        except Exception as e:
            print(f"  Warning: Failed to generate preview image: {e}")
            print("  Make sure LibreOffice and pdftoppm (poppler-utils) are installed:")
            print("    sudo apt-get install libreoffice poppler-utils")

    return state


async def main():
    """主测试入口"""
    import argparse
    global MODEL_NODE_GRAPH, MODEL_EDGE_PLANNER, MODEL_CLASSIFIER, MODEL_VLM_PLANNER, MODEL_PPTX_SPEC, MODEL_VLM_RENDER, OUTPUT_DIR

    parser = argparse.ArgumentParser(
        description="Test Film-Strip P2G Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_filmstrip_p2g_pipeline.py --stage 1a
  python test_filmstrip_p2g_pipeline.py --stage 1b
  python test_filmstrip_p2g_pipeline.py --stage 1    # runs 1a + 1b
  python test_filmstrip_p2g_pipeline.py --stage 1a-1b
  python test_filmstrip_p2g_pipeline.py --stage full
  python test_filmstrip_p2g_pipeline.py --stage 1 --run-id my_exp_v1
  python test_filmstrip_p2g_pipeline.py --stage 2 --continue-from latest
  python test_filmstrip_p2g_pipeline.py --stage 3-5 --continue-from abc12345_20231215_143000

Output structure:
  tests/.tmp/filmstrip_p2g_pipeline/
    ├── {target_hash}_{timestamp}_{run_id}/  # Each run creates a unique directory
    │   ├── run_config.json      # TEST_TARGET, models, stage, etc.
    │   ├── run.log              # Complete console output
    │   └── stage*.json          # Stage outputs
    └── latest -> {most_recent_run}/         # Symlink to latest run

Environment variables (alternative to command line args):
  MODEL_NODE_GRAPH   - Node graph constructor model (default: gpt-5.2)
  MODEL_EDGE_PLANNER - Edge planner model (default: gpt-4o)
  MODEL_CLASSIFIER   - Render method classifier model (default: gpt-5.2)
  MODEL_VLM_PLANNER  - VLM group planner model (default: gpt-4o)
  MODEL_PPTX_SPEC    - PPTX spec generator model (default: gpt-5.2)
  MODEL_VLM_RENDER   - VLM image generation model (default: gemini-3-pro-image-preview)
        """
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="1",
        help="Which stage to test: 1a, 1b, 1 (=1a+1b), 2-7 (single), 1-3 (range), full, or all"
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Custom run identifier (appended to output directory name)"
    )
    parser.add_argument(
        "--continue-from",
        type=str,
        default=None,
        help="Continue from existing run directory (use 'latest' for most recent, or full dir name)"
    )
    parser.add_argument(
        "--model-node-graph",
        type=str,
        default=None,
        help=f"Model for node graph constructor (default: {MODEL_NODE_GRAPH})"
    )
    parser.add_argument(
        "--model-edge-planner",
        type=str,
        default=None,
        help=f"Model for edge planner (default: {MODEL_EDGE_PLANNER})"
    )
    parser.add_argument(
        "--model-classifier",
        type=str,
        default=None,
        help=f"Model for render method classifier (default: {MODEL_CLASSIFIER})"
    )
    parser.add_argument(
        "--model-vlm-planner",
        type=str,
        default=None,
        help=f"Model for VLM group planner (default: {MODEL_VLM_PLANNER})"
    )
    parser.add_argument(
        "--model-pptx-spec",
        type=str,
        default=None,
        help=f"Model for PPTX spec generator (default: {MODEL_PPTX_SPEC})"
    )
    parser.add_argument(
        "--model-vlm",
        type=str,
        default=None,
        help=f"Model for VLM image generation (default: {MODEL_VLM_RENDER})"
    )
    args = parser.parse_args()

    # 命令行参数覆盖环境变量/默认值
    if args.model_node_graph:
        MODEL_NODE_GRAPH = args.model_node_graph
    if args.model_edge_planner:
        MODEL_EDGE_PLANNER = args.model_edge_planner
    if args.model_classifier:
        MODEL_CLASSIFIER = args.model_classifier
    if args.model_vlm_planner:
        MODEL_VLM_PLANNER = args.model_vlm_planner
    if args.model_pptx_spec:
        MODEL_PPTX_SPEC = args.model_pptx_spec
    if args.model_vlm:
        MODEL_VLM_RENDER = args.model_vlm

    # 创建或使用已有的输出目录
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    if args.continue_from:
        # 从已有目录继续
        if args.continue_from == "latest":
            latest_link = OUTPUT_ROOT / "latest"
            if not latest_link.exists():
                print("ERROR: No 'latest' directory found. Run a stage first.")
                return
            OUTPUT_DIR = latest_link.resolve()
        else:
            # 尝试作为完整路径或目录名
            continue_path = Path(args.continue_from)
            if continue_path.is_absolute():
                OUTPUT_DIR = continue_path
            else:
                OUTPUT_DIR = OUTPUT_ROOT / args.continue_from

            if not OUTPUT_DIR.exists():
                print(f"ERROR: Directory not found: {OUTPUT_DIR}")
                return

        print(f"Continuing from existing run: {OUTPUT_DIR}")
    else:
        # 创建新的运行目录
        OUTPUT_DIR = create_run_directory(TEST_TARGET, args.run_id)

    # 设置日志记录
    log_file = OUTPUT_DIR / "run.log"
    tee_logger = TeeLogger(log_file)
    original_stdout = sys.stdout
    sys.stdout = tee_logger

    try:
        # 打印运行信息头
        print("=" * 70)
        print(f"Film-Strip P2G Pipeline Test Run")
        print(f"=" * 70)
        print(f"Run Time: {datetime.now().isoformat()}")
        print(f"Output Dir: {OUTPUT_DIR}")
        print(f"Stage: {args.stage}")
        if args.run_id:
            print(f"Run ID: {args.run_id}")
        if args.continue_from:
            print(f"Continue From: {args.continue_from}")
        print()

        # 打印 TEST_TARGET
        print("TEST_TARGET:")
        print("-" * 40)
        print(TEST_TARGET.strip())
        print("-" * 40)
        print(f"Target Hash: {generate_target_hash(TEST_TARGET)}")
        print()

        # 打印当前模型配置
        print("Model Configuration:")
        print(f"  Node Graph (1A): {MODEL_NODE_GRAPH}")
        print(f"  Edge Planner (1B): {MODEL_EDGE_PLANNER}")
        print(f"  Classifier: {MODEL_CLASSIFIER}")
        print(f"  VLM Planner: {MODEL_VLM_PLANNER}")
        print(f"  PPTX Spec: {MODEL_PPTX_SPEC}")
        print(f"  VLM Render: {MODEL_VLM_RENDER}")
        print()

        # 打印 API 配置
        vlm_api_url = os.getenv("VLM_API_URL")
        df_api_url = os.getenv("DF_API_URL")
        print("API Configuration:")
        print(f"  DF_API_URL: {df_api_url or '(not set)'}")
        print(f"  VLM_API_URL: {vlm_api_url or '(not set, using DF_API_URL)'}")
        if vlm_api_url:
            print(f"  -> VLM image generation will use VLM_API_URL")
        else:
            print(f"  -> VLM image generation will use DF_API_URL")
        print()

        # 保存运行配置
        models_config = {
            "node_graph": MODEL_NODE_GRAPH,
            "edge_planner": MODEL_EDGE_PLANNER,
            "classifier": MODEL_CLASSIFIER,
            "vlm_planner": MODEL_VLM_PLANNER,
            "pptx_spec": MODEL_PPTX_SPEC,
            "vlm_render": MODEL_VLM_RENDER,
        }
        api_config = {
            "df_api_url": df_api_url,
            "vlm_api_url": vlm_api_url,
            "vlm_api_source": "VLM_API_URL" if vlm_api_url else "DF_API_URL",
        }
        save_run_config(OUTPUT_DIR, TEST_TARGET, args.stage, models_config, {
            "run_id": args.run_id,
            "api_config": api_config,
        })
        print()

        # 执行测试
        if args.stage == "1a":
            await test_stage1a_node_graph_constructor()
        elif args.stage == "1b":
            await test_stage1b_edge_planner()
        elif args.stage == "1" or args.stage == "1a-1b":
            # Stage 1 = 1A + 1B
            await test_stage1_node_graph_constructor()
        elif args.stage == "2":
            await test_stage2_render_method_classifier()
        elif args.stage == "3":
            await test_stage3_vlm_group_planner()
        elif args.stage == "4":
            await test_stage4_pptx_spec_generator()
        elif args.stage == "5":
            await test_stage5_filmstrip_renderer()
        elif args.stage == "6":
            await test_stage6_layout_engine()
        elif args.stage == "1-3":
            state = await test_stage1_node_graph_constructor()
            state = await test_stage2_render_method_classifier(state)
            state = await test_stage3_vlm_group_planner(state)
        elif args.stage == "1-4":
            state = await test_stage1_node_graph_constructor()
            state = await test_stage2_render_method_classifier(state)
            state = await test_stage3_vlm_group_planner(state)
            state = await test_stage4_pptx_spec_generator(state)
        elif args.stage == "1-5":
            state = await test_stage1_node_graph_constructor()
            state = await test_stage2_render_method_classifier(state)
            state = await test_stage3_vlm_group_planner(state)
            state = await test_stage4_pptx_spec_generator(state)
            state = await test_stage5_filmstrip_renderer(state)
        elif args.stage == "1-6":
            state = await test_stage1_node_graph_constructor()
            state = await test_stage2_render_method_classifier(state)
            state = await test_stage3_vlm_group_planner(state)
            state = await test_stage4_pptx_spec_generator(state)
            state = await test_stage5_filmstrip_renderer(state)
            state = await test_stage6_layout_engine(state)
        elif args.stage == "3-5":
            # Stage 3-5: VLM 分组 -> PPTX 规格 -> 渲染
            state = await test_stage3_vlm_group_planner()
            state = await test_stage4_pptx_spec_generator(state)
            state = await test_stage5_filmstrip_renderer(state)
        elif args.stage == "5-6":
            # Stage 5-6: 渲染 -> 布局
            state = await test_stage5_filmstrip_renderer()
            state = await test_stage6_layout_engine(state)
        elif args.stage == "6-7":
            # Stage 6-7: 布局 -> PPTX 组装
            state = await test_stage6_layout_engine()
            state = await test_stage7_pptx_composer(state)
        elif args.stage == "7":
            await test_stage7_pptx_composer()
        elif args.stage == "1-7" or args.stage == "full":
            # 完整流水线
            state = await test_stage1_node_graph_constructor()
            state = await test_stage2_render_method_classifier(state)
            state = await test_stage3_vlm_group_planner(state)
            state = await test_stage4_pptx_spec_generator(state)
            state = await test_stage5_filmstrip_renderer(state)
            state = await test_stage6_layout_engine(state)
            state = await test_stage7_pptx_composer(state)
        elif args.stage == "all":
            state = await test_stage1_node_graph_constructor()
            state = await test_stage2_render_method_classifier(state)
            state = await test_stage3_vlm_group_planner(state)
            state = await test_stage4_pptx_spec_generator(state)
            state = await test_stage5_filmstrip_renderer(state)
            state = await test_stage6_layout_engine(state)
            state = await test_stage7_pptx_composer(state)
        else:
            print(f"Unknown stage: {args.stage}")
            print("Valid options: 1a, 1b, 1 (=1a+1b), 2, 3, 4, 5, 6, 7, 1-3, 1-4, 1-5, 1-6, 1-7, 3-5, 5-6, 6-7, full, all")

        # 打印完成信息
        print()
        print("=" * 70)
        print(f"Run completed at: {datetime.now().isoformat()}")
        print(f"Output saved to: {OUTPUT_DIR}")
        print(f"Log file: {log_file}")
        print("=" * 70)

    finally:
        # 恢复标准输出并关闭日志
        sys.stdout = original_stdout
        tee_logger.close()


if __name__ == "__main__":
    asyncio.run(main())
