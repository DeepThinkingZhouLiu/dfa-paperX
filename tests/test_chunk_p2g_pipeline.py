"""测试 Chunk-Based Paper2Graph Pipeline

测试完整的 chunk 级别绘制 pipeline：
1. semantic_constructor
2. chunk_layout_planner
3. chunk_vlm_designer
4. chunk_renderer
5. chunk_pptx_composer
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

from dataflow_agent.state import ChunkP2GState, ChunkP2GRequest

# 输出目录
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "chunk_p2g_pipeline"

# ============================================================================
# 各环节模型配置（可通过环境变量覆盖）
# ============================================================================
# Step 1: Semantic Constructor - 语义理解模型
MODEL_SEMANTIC = os.getenv("MODEL_SEMANTIC", "gpt-5.2")
# Step 2: Layout Planner - 布局规划模型
MODEL_LAYOUT = os.getenv("MODEL_LAYOUT", "gpt-5.2")
# Step 3: VLM Designer - 纯计算函数，不需要模型
# Step 4: Chunk Renderer - VLM 图像生成模型
MODEL_VLM_RENDER = os.getenv("MODEL_VLM_RENDER", "gemini-3-pro-image-preview")


# 测试用的 target 描述
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


async def test_step1_semantic_constructor():
    """测试 Step 1: Semantic Constructor"""
    from dataflow_agent.agentroles.p2g_chunk_semantic_constructor_agent import (
        p2g_chunk_semantic_constructor_agent,
    )

    print("=" * 60)
    print("Step 1: Testing Semantic Constructor")
    print(f"  Model: {MODEL_SEMANTIC}")
    print("=" * 60)

    request = ChunkP2GRequest(
        target=TEST_TARGET,
        model=MODEL_SEMANTIC,
        max_chunks=6,
        min_nodes_per_chunk=3,
        max_nodes_per_chunk=6,
    )
    state = ChunkP2GState(request=request)

    state = await p2g_chunk_semantic_constructor_agent(
        state,
        model_name=MODEL_SEMANTIC,
    )

    semantic_json = getattr(state, "semantic_json", {})

    print(f"\nResult:")
    print(f"  Title: {semantic_json.get('title', 'N/A')}")
    print(f"  Chunks: {len(semantic_json.get('chunks', []))}")
    print(f"  Nodes: {len(semantic_json.get('nodes', []))}")
    print(f"  Edges: {len(semantic_json.get('edges', []))}")
    print(f"  Inter-chunk relations: {len(semantic_json.get('inter_chunk_relations', []))}")

    for chunk in semantic_json.get("chunks", []):
        print(f"\n  {chunk['chunk_id']}: {chunk.get('title', 'N/A')}")
        print(f"    Role: {chunk.get('semantic_role', 'N/A')}")
        print(f"    Nodes: {chunk.get('node_ids', [])}")

    save_json(semantic_json, "step1_semantic_json.json")

    return state


async def test_step2_layout_planner(state: ChunkP2GState = None):
    """测试 Step 2: Layout Planner"""
    from dataflow_agent.agentroles.p2g_chunk_layout_planner_agent import (
        p2g_chunk_layout_planner_agent,
    )

    print("\n" + "=" * 60)
    print("Step 2: Testing Layout Planner")
    print(f"  Model: {MODEL_LAYOUT}")
    print("=" * 60)

    if state is None:
        # 从文件加载
        semantic_path = OUTPUT_DIR / "step1_semantic_json.json"
        if not semantic_path.exists():
            print("ERROR: Run step1 first!")
            return None

        with open(semantic_path, "r") as f:
            semantic_json = json.load(f)

        request = ChunkP2GRequest(
            target=TEST_TARGET,
            model=MODEL_LAYOUT,
            canvas_width=1920,
            canvas_height=1080,
        )
        state = ChunkP2GState(request=request)
        state.semantic_json = semantic_json

    state = await p2g_chunk_layout_planner_agent(
        state,
        model_name=MODEL_LAYOUT,
    )

    chunk_layout_json = getattr(state, "chunk_layout_json", {})

    print(f"\nResult:")
    print(f"  Canvas: {chunk_layout_json.get('canvas', {})}")
    print(f"  Chunks: {len(chunk_layout_json.get('chunks', []))}")
    print(f"  Connectors: {len(chunk_layout_json.get('inter_chunk_connectors', []))}")

    for chunk in chunk_layout_json.get("chunks", []):
        bbox = chunk.get("bbox", {})
        print(f"\n  {chunk['chunk_id']}: ({bbox.get('x')}, {bbox.get('y')}) {bbox.get('w')}x{bbox.get('h')}")

    save_json(chunk_layout_json, "step2_chunk_layout_json.json")

    return state


async def test_step3_vlm_designer(state: ChunkP2GState = None):
    """测试 Step 3: VLM Designer"""
    from dataflow_agent.agentroles.p2g_chunk_vlm_designer_agent import (
        p2g_chunk_vlm_designer_agent,
    )

    print("\n" + "=" * 60)
    print("Step 3: Testing VLM Designer (pure computation, no LLM)")
    print("=" * 60)

    if state is None:
        # 从文件加载
        semantic_path = OUTPUT_DIR / "step1_semantic_json.json"
        layout_path = OUTPUT_DIR / "step2_chunk_layout_json.json"

        if not semantic_path.exists() or not layout_path.exists():
            print("ERROR: Run step1 and step2 first!")
            return None

        with open(semantic_path, "r") as f:
            semantic_json = json.load(f)
        with open(layout_path, "r") as f:
            chunk_layout_json = json.load(f)

        request = ChunkP2GRequest(target=TEST_TARGET)
        state = ChunkP2GState(request=request)
        state.semantic_json = semantic_json
        state.chunk_layout_json = chunk_layout_json

    # 注意：p2g_chunk_vlm_designer_agent 是纯计算函数，不调用 LLM
    state = await p2g_chunk_vlm_designer_agent(state)

    chunk_vlm_designs = getattr(state, "chunk_vlm_designs", {})

    print(f"\nResult: {len(chunk_vlm_designs)} VLM prompts generated")

    for chunk_id, design in chunk_vlm_designs.items():
        prompt = design.get("prompt", "")
        canvas = design.get("canvas_size", {})
        nodes = design.get("node_ids", [])
        print(f"\n  {chunk_id}: {canvas.get('width')}x{canvas.get('height')}, {len(nodes)} nodes")
        print(f"    Prompt length: {len(prompt)} chars")

    save_json(chunk_vlm_designs, "step3_chunk_vlm_designs.json")

    return state


async def test_step4_renderer(state: ChunkP2GState = None):
    """测试 Step 4: Chunk Renderer"""
    from dataflow_agent.agentroles.p2g_chunk_renderer_agent import (
        p2g_chunk_renderer_agent,
    )

    print("\n" + "=" * 60)
    print("Step 4: Testing Chunk Renderer")
    print(f"  Model: {MODEL_VLM_RENDER}")
    print("=" * 60)

    # 检查 API 配置
    api_url = os.getenv("DF_API_URL")
    api_key = os.getenv("DF_API_KEY")

    if not api_url or not api_key:
        print("WARNING: DF_API_URL or DF_API_KEY not set, skipping render")
        return state

    if state is None:
        # 从文件加载
        designs_path = OUTPUT_DIR / "step3_chunk_vlm_designs.json"

        if not designs_path.exists():
            print("ERROR: Run step3 first!")
            return None

        with open(designs_path, "r") as f:
            chunk_vlm_designs = json.load(f)

        request = ChunkP2GRequest(
            target=TEST_TARGET,
            vlm_model=MODEL_VLM_RENDER,
            output_dir=str(OUTPUT_DIR),
            vlm_concurrency=3,
            vlm_timeout=600,  # 10 分钟，图像生成需要较长时间
        )
        state = ChunkP2GState(request=request)
        state.chunk_vlm_designs = chunk_vlm_designs

    state = await p2g_chunk_renderer_agent(
        state,
        vlm_model=MODEL_VLM_RENDER,
        output_dir=str(OUTPUT_DIR / "chunks"),
        concurrency=6,
        timeout=600,  # 10 分钟，图像生成需要较长时间
    )

    chunk_images = getattr(state, "chunk_images", {})
    chunk_errors = getattr(state, "chunk_render_errors", {})

    print(f"\nResult:")
    print(f"  Success: {len(chunk_images)}")
    print(f"  Failed: {len(chunk_errors)}")

    for chunk_id, info in chunk_images.items():
        print(f"\n  {chunk_id}: {info.get('path')}")
        print(f"    Render time: {info.get('render_time_ms')} ms")

    if chunk_errors:
        print(f"\nErrors:")
        for chunk_id, error in chunk_errors.items():
            print(f"  {chunk_id}: {error}")

    save_json({
        "chunk_images": chunk_images,
        "chunk_errors": chunk_errors,
    }, "step4_render_result.json")

    return state


async def test_step5_pptx_composer(state: ChunkP2GState = None):
    """测试 Step 5: PPTX Composer"""
    from dataflow_agent.agentroles.p2g_chunk_pptx_composer_agent import (
        p2g_chunk_pptx_composer_for_chunk_pipeline,
    )

    print("\n" + "=" * 60)
    print("Step 5: Testing PPTX Composer")
    print("=" * 60)

    if state is None:
        # 从文件加载
        layout_path = OUTPUT_DIR / "step2_chunk_layout_json.json"
        render_path = OUTPUT_DIR / "step4_render_result.json"

        if not layout_path.exists() or not render_path.exists():
            print("ERROR: Run step2 and step4 first!")
            return None

        with open(layout_path, "r") as f:
            chunk_layout_json = json.load(f)
        with open(render_path, "r") as f:
            render_result = json.load(f)

        request = ChunkP2GRequest(
            target=TEST_TARGET,
            model="gpt-4o",
            output_dir=str(OUTPUT_DIR),
        )
        state = ChunkP2GState(request=request)
        state.chunk_layout_json = chunk_layout_json
        state.chunk_images = render_result.get("chunk_images", {})

    state = await p2g_chunk_pptx_composer_for_chunk_pipeline(
        state,
        output_path=str(OUTPUT_DIR / "paper2graph_chunk.pptx"),
    )

    pptx_path = getattr(state, "pptx_output_path", "")
    result = state.agent_results.get("p2g_chunk_pptx_composer_agent", {})

    print(f"\nResult:")
    print(f"  Status: {result.get('status')}")
    print(f"  Output: {pptx_path}")
    print(f"  Stats: {result.get('stats')}")

    if pptx_path and Path(pptx_path).exists():
        print(f"  File size: {Path(pptx_path).stat().st_size / 1024:.1f} KB")

    return state


async def test_full_pipeline():
    """测试完整 pipeline"""
    from dataflow_agent.workflow.wf_p2g_chunk_pipeline import run_chunk_p2g_pipeline

    print("=" * 60)
    print("Testing Full Chunk P2G Pipeline")
    print(f"  Semantic Model: {MODEL_SEMANTIC}")
    print(f"  Layout Model: {MODEL_LAYOUT}")
    print(f"  VLM Render Model: {MODEL_VLM_RENDER}")
    print("=" * 60)

    state = await run_chunk_p2g_pipeline(
        target=TEST_TARGET,
        model_name=MODEL_SEMANTIC,  # 用于 semantic 和 layout
        canvas_width=1920,
        canvas_height=1080,
        output_dir=str(OUTPUT_DIR),
        vlm_model=MODEL_VLM_RENDER,
        vlm_concurrency=3,
        vlm_timeout=600,  # 10 分钟，图像生成需要较长时间
    )

    print("\n" + "=" * 60)
    print("Final Results:")
    print("=" * 60)

    semantic_json = getattr(state, "semantic_json", {})
    chunk_layout_json = getattr(state, "chunk_layout_json", {})
    chunk_vlm_designs = getattr(state, "chunk_vlm_designs", {})
    chunk_images = getattr(state, "chunk_images", {})
    pptx_path = getattr(state, "pptx_output_path", "")

    print(f"Semantic: {len(semantic_json.get('chunks', []))} chunks, {len(semantic_json.get('nodes', []))} nodes")
    print(f"Layout: {len(chunk_layout_json.get('chunks', []))} chunks")
    print(f"VLM Designs: {len(chunk_vlm_designs)} prompts")
    print(f"Rendered: {len(chunk_images)} chunks")
    print(f"PPTX: {pptx_path}")

    return state


def parse_step_range(step_str: str) -> tuple[int, int] | None:
    """解析步骤范围，如 '1-3' 返回 (1, 3)，'2' 返回 None"""
    if "-" in step_str:
        parts = step_str.split("-")
        if len(parts) == 2:
            try:
                start, end = int(parts[0]), int(parts[1])
                if 1 <= start <= 5 and 1 <= end <= 5 and start <= end:
                    return (start, end)
            except ValueError:
                pass
    return None


async def run_steps_range(start: int, end: int):
    """运行指定范围的步骤"""
    step_funcs = {
        1: test_step1_semantic_constructor,
        2: test_step2_layout_planner,
        3: test_step3_vlm_designer,
        4: test_step4_renderer,
        5: test_step5_pptx_composer,
    }

    state = None
    for step in range(start, end + 1):
        if step == 1:
            state = await step_funcs[step]()
        else:
            state = await step_funcs[step](state)

    return state


async def main():
    """主测试入口"""
    import argparse
    global MODEL_SEMANTIC, MODEL_LAYOUT, MODEL_VLM_RENDER

    parser = argparse.ArgumentParser(
        description="Test Chunk P2G Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_chunk_p2g_pipeline.py --step full
  python test_chunk_p2g_pipeline.py --step 1-3 --model-semantic gpt-4o
  python test_chunk_p2g_pipeline.py --step 4 --model-vlm gemini-2.5-flash-image-preview

Environment variables (alternative to command line args):
  MODEL_SEMANTIC   - Semantic constructor model (default: gemini-2.5-pro)
  MODEL_LAYOUT     - Layout planner model (default: gpt-4o)
  MODEL_VLM_RENDER - VLM image generation model (default: gemini-3-pro-image-preview)
        """
    )
    parser.add_argument(
        "--step",
        type=str,
        default="full",
        help="Which step to test: 1-5 (single), 1-3 (range), full, or all"
    )
    parser.add_argument(
        "--model-semantic",
        type=str,
        default=None,
        help=f"Model for semantic constructor (default: {MODEL_SEMANTIC})"
    )
    parser.add_argument(
        "--model-layout",
        type=str,
        default=None,
        help=f"Model for layout planner (default: {MODEL_LAYOUT})"
    )
    parser.add_argument(
        "--model-vlm",
        type=str,
        default=None,
        help=f"Model for VLM image generation (default: {MODEL_VLM_RENDER})"
    )
    args = parser.parse_args()

    # 命令行参数覆盖环境变量/默认值
    if args.model_semantic:
        MODEL_SEMANTIC = args.model_semantic
    if args.model_layout:
        MODEL_LAYOUT = args.model_layout
    if args.model_vlm:
        MODEL_VLM_RENDER = args.model_vlm

    # 打印当前模型配置
    print("Model Configuration:")
    print(f"  Semantic: {MODEL_SEMANTIC}")
    print(f"  Layout: {MODEL_LAYOUT}")
    print(f"  VLM Render: {MODEL_VLM_RENDER}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 检查是否是范围格式 (如 "1-3")
    step_range = parse_step_range(args.step)
    if step_range:
        start, end = step_range
        print(f"Running steps {start} to {end}")
        await run_steps_range(start, end)
    elif args.step == "1":
        await test_step1_semantic_constructor()
    elif args.step == "2":
        await test_step2_layout_planner()
    elif args.step == "3":
        await test_step3_vlm_designer()
    elif args.step == "4":
        await test_step4_renderer()
    elif args.step == "5":
        await test_step5_pptx_composer()
    elif args.step == "full":
        await test_full_pipeline()
    elif args.step == "all":
        state = await test_step1_semantic_constructor()
        state = await test_step2_layout_planner(state)
        state = await test_step3_vlm_designer(state)
        state = await test_step4_renderer(state)
        state = await test_step5_pptx_composer(state)
    else:
        print(f"Unknown step: {args.step}")
        print("Valid options: 1, 2, 3, 4, 5, 1-3 (range), full, all")


if __name__ == "__main__":
    asyncio.run(main())
