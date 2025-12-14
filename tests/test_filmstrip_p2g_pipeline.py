"""测试 Film-Strip Bottom-Up Paper2Graph Pipeline

测试完整的 Film-Strip 级别绘制 pipeline：
1. node_graph_constructor - 构建节点图（nodes + edges）
2. render_method_classifier - 分类渲染方式（VLM vs PPTX）
3. vlm_group_planner - VLM 节点分组 + 连环画 prompt
4. pptx_spec_generator - PPTX 节点渲染规格
5. filmstrip_renderer - VLM 生成连环画 + 切图 + 去背景
6. layout_engine - 基于实际尺寸布局
7. pptx_composer - 组装 PPTX
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

# 避免导入时自动加载
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")
os.environ.setdefault("DF_SKIP_WORKFLOW_AUTOINIT", "1")

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.state import FilmStripP2GState, FilmStripP2GRequest

# 输出目录
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "filmstrip_p2g_pipeline"

# ============================================================================
# 各环节模型配置（可通过环境变量覆盖）
# ============================================================================
# Stage 1: Node Graph Constructor - 节点图构建模型
MODEL_NODE_GRAPH = os.getenv("MODEL_NODE_GRAPH", "gpt-5.2")
# Stage 2: Render Method Classifier - 渲染方式分类模型
MODEL_CLASSIFIER = os.getenv("MODEL_CLASSIFIER", "gpt-5.2")
# Stage 3: VLM Group Planner - VLM 分组规划模型
MODEL_VLM_PLANNER = os.getenv("MODEL_VLM_PLANNER", "gpt-5.2")
# Stage 4: PPTX Spec Generator - PPTX 规格生成模型
MODEL_PPTX_SPEC = os.getenv("MODEL_PPTX_SPEC", "gpt-5.2")
# Stage 5: Film-Strip Renderer - VLM 图像生成模型
MODEL_VLM_RENDER = os.getenv("MODEL_VLM_RENDER", "gemini-3-pro-image-preview")
# Stage 6: Layout Engine - 纯计算函数，不需要模型


# 测试用的 target 描述
TEST_TARGET = """
画一张英文的弱监督语义分割论文中的科研配图，图像级标签，单阶段方法，直接通过segformer的backbone提取特征图，这里首先有一个分类损失，然后是解码器生成预测的分割图，还有一路生成伪标签，对预测的分割图进行交叉熵损失的监督，创新点是像素级学习不足，输入层新增定位专用token，更小的patch聚类、Memory bank, Adapter

"""


def save_json(data: dict, filename: str):
    """保存 JSON 文件"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


async def test_stage1_node_graph_constructor():
    """测试 Stage 1: Node Graph Constructor"""
    from dataflow_agent.agentroles.p2g_filmstrip_node_graph_constructor_agent import (
        p2g_filmstrip_node_graph_constructor_agent,
    )

    print("=" * 60)
    print("Stage 1: Testing Node Graph Constructor")
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
    print(f"  Edges: {len(node_graph_json.get('edges', []))}")

    # 打印节点信息
    for node in node_graph_json.get("nodes", []):
        print(f"\n  {node['node_id']}: {node.get('label', 'N/A')}")
        print(f"    Role: {node.get('role', 'N/A')}")
        print(f"    Visual: {node.get('visual_desc', 'N/A')[:60]}...")

    # 打印边信息
    print(f"\nEdges:")
    for edge in node_graph_json.get("edges", []):
        print(f"  {edge['edge_id']}: {edge.get('from')} → {edge.get('to')} ({edge.get('edge_type')})")

    save_json(node_graph_json, "stage1_node_graph_json.json")

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

    return state


async def main():
    """主测试入口"""
    import argparse
    global MODEL_NODE_GRAPH, MODEL_CLASSIFIER, MODEL_VLM_PLANNER, MODEL_PPTX_SPEC, MODEL_VLM_RENDER

    parser = argparse.ArgumentParser(
        description="Test Film-Strip P2G Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_filmstrip_p2g_pipeline.py --stage 1
  python test_filmstrip_p2g_pipeline.py --stage 1 --model-node-graph gpt-4o
  python test_filmstrip_p2g_pipeline.py --stage full

Environment variables (alternative to command line args):
  MODEL_NODE_GRAPH   - Node graph constructor model (default: gpt-4o)
  MODEL_CLASSIFIER   - Render method classifier model (default: gpt-4o)
  MODEL_VLM_PLANNER  - VLM group planner model (default: gpt-4o)
  MODEL_PPTX_SPEC    - PPTX spec generator model (default: gpt-4o)
  MODEL_VLM_RENDER   - VLM image generation model (default: gemini-3-pro-image-preview)
        """
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="1",
        help="Which stage to test: 1-7 (single), 1-3 (range), full, or all"
    )
    parser.add_argument(
        "--model-node-graph",
        type=str,
        default=None,
        help=f"Model for node graph constructor (default: {MODEL_NODE_GRAPH})"
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
    if args.model_classifier:
        MODEL_CLASSIFIER = args.model_classifier
    if args.model_vlm_planner:
        MODEL_VLM_PLANNER = args.model_vlm_planner
    if args.model_pptx_spec:
        MODEL_PPTX_SPEC = args.model_pptx_spec
    if args.model_vlm:
        MODEL_VLM_RENDER = args.model_vlm

    # 打印当前模型配置
    print("Model Configuration:")
    print(f"  Node Graph: {MODEL_NODE_GRAPH}")
    print(f"  Classifier: {MODEL_CLASSIFIER}")
    print(f"  VLM Planner: {MODEL_VLM_PLANNER}")
    print(f"  PPTX Spec: {MODEL_PPTX_SPEC}")
    print(f"  VLM Render: {MODEL_VLM_RENDER}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.stage == "1":
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
        print("Valid options: 1, 2, 3, 4, 5, 6, 7, 1-3, 1-4, 1-5, 1-6, 1-7, 3-5, 5-6, 6-7, full, all")


if __name__ == "__main__":
    asyncio.run(main())
