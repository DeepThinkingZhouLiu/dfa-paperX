"""测试 p2g_chunk_render workflow

测试 chunk 级别的 3-agent 子图工作流：
1. p2g_chunk_prompt_agent: 生成 chunk 级别的 VLM prompt
2. p2g_chunk_vlm_renderer_agent: 调用 VLM 渲染 chunk 图片
3. p2g_chunk_pptx_composer_agent: 组装 PPTX
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")
# 避免导入 workflow 包时自动导入全部 workflow 造成外部依赖错误
os.environ.setdefault("DF_SKIP_WORKFLOW_AUTOINIT", "1")

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest


# 数据目录
DATA_DIR = Path(__file__).parent / ".tmp"
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "chunk_output"


def load_json(relative_path: str) -> dict:
    """加载 JSON 文件"""
    filepath = DATA_DIR / relative_path
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def test_chunk_prompt_agent():
    """测试 chunk prompt 生成 agent（不需要 API）"""
    from dataflow_agent.agentroles.p2g_chunk_prompt_agent import p2g_chunk_prompt_agent

    print("=" * 60)
    print("Testing p2g_chunk_prompt_agent...")
    print("=" * 60)

    # 加载数据
    semantic_json = load_json("layout_pipeline/semantic_json.json")
    node_render_design = load_json("render_design/node_render_design.json")
    layout_json = load_json("layout_pipeline/layout_json.json")

    if not semantic_json:
        print("ERROR: semantic_json.json not found!")
        return None

    # 构建 state
    request = Paper2GraphRequest(
        target="Test chunk prompt generation",
        model="none",
    )

    state = Paper2GraphState(request=request)
    state.semantic_json = semantic_json
    state.node_render_design = node_render_design
    state.layout_json = layout_json

    # 执行
    state = await p2g_chunk_prompt_agent(state)

    # 验证结果
    chunk_prompts = getattr(state, "chunk_prompts", {})
    print(f"\nGenerated {len(chunk_prompts)} chunk prompts:")

    for chunk_id, chunk_data in chunk_prompts.items():
        prompt = chunk_data.get("prompt", "")
        bbox = chunk_data.get("bbox", {})
        node_ids = chunk_data.get("node_ids", [])
        title = chunk_data.get("title", "")

        print(f"\n  {chunk_id}: {title}")
        print(f"    - bbox: {bbox['w']}x{bbox['h']} at ({bbox['x']}, {bbox['y']})")
        print(f"    - nodes: {len(node_ids)} ({', '.join(node_ids[:3])}{'...' if len(node_ids) > 3 else ''})")
        print(f"    - prompt length: {len(prompt)} chars")

    # 保存 prompts 到文件
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prompts_path = OUTPUT_DIR / "chunk_prompts.json"
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(chunk_prompts, f, ensure_ascii=False, indent=2)
    print(f"\nChunk prompts saved to: {prompts_path}")

    return state


async def test_chunk_vlm_renderer_agent(state: Paper2GraphState = None):
    """测试 chunk VLM 渲染 agent（需要 API）"""
    from dataflow_agent.agentroles.p2g_chunk_vlm_renderer_agent import p2g_chunk_vlm_renderer_agent

    print("\n" + "=" * 60)
    print("Testing p2g_chunk_vlm_renderer_agent...")
    print("=" * 60)

    # 如果没有传入 state，从文件加载 chunk_prompts
    if state is None or not getattr(state, "chunk_prompts", None):
        prompts_path = OUTPUT_DIR / "chunk_prompts.json"
        if not prompts_path.exists():
            print("ERROR: chunk_prompts.json not found! Run test_chunk_prompt_agent first.")
            return None

        with open(prompts_path, "r", encoding="utf-8") as f:
            chunk_prompts = json.load(f)

        request = Paper2GraphRequest(
            target="Test chunk VLM rendering",
            model="none",
        )
        state = Paper2GraphState(request=request)
        state.chunk_prompts = chunk_prompts

    # 检查 API 配置
    api_url = os.getenv("DF_API_URL")
    api_key = os.getenv("DF_API_KEY")

    if not api_url or not api_key:
        print("WARNING: DF_API_URL or DF_API_KEY not set, skipping VLM rendering")
        return state

    chunk_prompts = getattr(state, "chunk_prompts", {})
    print(f"\nRendering {len(chunk_prompts)} chunks...")

    # 执行
    output_dir = str(OUTPUT_DIR / "chunk_images")
    state = await p2g_chunk_vlm_renderer_agent(
        state,
        output_dir=output_dir,
        concurrency=3,
        timeout=180,
    )

    # 验证结果
    chunk_images = getattr(state, "chunk_images", {})
    errors = getattr(state, "chunk_render_errors", {})

    print(f"\nRendered {len(chunk_images)} chunks successfully")
    if errors:
        print(f"Failed {len(errors)} chunks: {list(errors.keys())}")

    for chunk_id, chunk_data in chunk_images.items():
        path = chunk_data.get("path", "")
        bbox = chunk_data.get("bbox", {})
        print(f"  {chunk_id}: {path}")

    return state


async def test_chunk_pptx_composer_agent(state: Paper2GraphState = None):
    """测试 chunk PPTX 组装 agent"""
    from dataflow_agent.agentroles.p2g_chunk_pptx_composer_agent import p2g_chunk_pptx_composer_agent

    print("\n" + "=" * 60)
    print("Testing p2g_chunk_pptx_composer_agent...")
    print("=" * 60)

    # 如果没有传入 state，从文件加载 chunk_images
    if state is None or not getattr(state, "chunk_images", None):
        # 尝试从目录扫描已有的 chunk 图片
        chunk_images_dir = OUTPUT_DIR / "chunk_images"
        if not chunk_images_dir.exists():
            print("ERROR: chunk_images directory not found! Run test_chunk_vlm_renderer_agent first.")
            return None

        # 加载 layout_json 获取 bbox
        layout_json = load_json("layout_pipeline/layout_json.json")
        chunk_bboxes = {
            c["chunk_id"]: c["bbox"]
            for c in layout_json.get("positions", {}).get("chunks", [])
        }

        # 扫描图片
        chunk_images = {}
        for img_path in chunk_images_dir.glob("*.png"):
            chunk_id = img_path.stem  # e.g., "c1" from "c1.png"
            if chunk_id in chunk_bboxes:
                chunk_images[chunk_id] = {
                    "path": str(img_path),
                    "bbox": chunk_bboxes[chunk_id],
                }

        if not chunk_images:
            print("ERROR: No chunk images found!")
            return None

        request = Paper2GraphRequest(
            target="Test chunk PPTX composition",
            model="none",
        )
        state = Paper2GraphState(request=request)
        state.chunk_images = chunk_images
        state.layout_json = layout_json

    chunk_images = getattr(state, "chunk_images", {})
    print(f"\nComposing PPTX with {len(chunk_images)} chunks...")

    # 执行
    output_path = str(OUTPUT_DIR / "paper2graph_chunk.pptx")
    state = await p2g_chunk_pptx_composer_agent(
        state,
        output_path=output_path,
    )

    # 验证结果
    result = state.agent_results.get("p2g_chunk_pptx_composer_agent", {})
    print(f"\nStatus: {result.get('status', 'unknown')}")

    if result.get("status") == "ok":
        stats = result.get("stats", {})
        print(f"Chunks rendered: {stats.get('chunks_rendered', 0)}")

        output_file = Path(getattr(state, "pptx_output_path", ""))
        if output_file.exists():
            print(f"\nPPTX generated: {output_file}")
            print(f"File size: {output_file.stat().st_size / 1024:.1f} KB")
    else:
        print(f"Failed: {result.get('error', 'Unknown error')}")

    return state


async def test_full_workflow():
    """测试完整的 workflow（串行执行 3 个 agent）"""
    from dataflow_agent.agentroles.p2g_chunk_prompt_agent import p2g_chunk_prompt_agent
    from dataflow_agent.agentroles.p2g_chunk_vlm_renderer_agent import p2g_chunk_vlm_renderer_agent
    from dataflow_agent.agentroles.p2g_chunk_pptx_composer_agent import p2g_chunk_pptx_composer_agent

    print("=" * 60)
    print("Testing full p2g_chunk_render workflow...")
    print("=" * 60)

    # 加载数据
    semantic_json = load_json("layout_pipeline/semantic_json.json")
    node_render_design = load_json("render_design/node_render_design.json")
    layout_json = load_json("layout_pipeline/layout_json.json")

    if not semantic_json:
        print("ERROR: semantic_json.json not found!")
        return None

    # 构建 state
    request = Paper2GraphRequest(
        target="Test full chunk render workflow",
        model="none",
    )

    state = Paper2GraphState(request=request)
    state.semantic_json = semantic_json
    state.node_render_design = node_render_design
    state.layout_json = layout_json

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Chunk Prompt 生成
    print("\n[Step 1/3] Running p2g_chunk_prompt_agent...")
    state = await p2g_chunk_prompt_agent(state)
    chunk_prompts = getattr(state, "chunk_prompts", {})
    print(f"  Generated {len(chunk_prompts)} chunk prompts")

    # Step 2: Chunk VLM 渲染
    print("\n[Step 2/3] Running p2g_chunk_vlm_renderer_agent...")
    state = await p2g_chunk_vlm_renderer_agent(
        state,
        output_dir=str(OUTPUT_DIR / "chunk_images"),
        concurrency=3,
        timeout=180,
    )
    chunk_images = getattr(state, "chunk_images", {})
    print(f"  Rendered {len(chunk_images)} chunk images")

    # Step 3: Chunk PPTX 组装
    print("\n[Step 3/3] Running p2g_chunk_pptx_composer_agent...")
    state = await p2g_chunk_pptx_composer_agent(
        state,
        output_path=str(OUTPUT_DIR / "paper2graph_chunk_workflow.pptx"),
    )

    # 验证结果
    print("\n" + "=" * 60)
    print("Workflow Results:")
    print("=" * 60)

    # Chunk prompts
    print(f"\nChunk prompts: {len(chunk_prompts)}")

    # Chunk images
    print(f"Chunk images: {len(chunk_images)}")

    # PPTX
    pptx_path = getattr(state, "pptx_output_path", "")
    if pptx_path and Path(pptx_path).exists():
        print(f"\nPPTX generated: {pptx_path}")
        print(f"File size: {Path(pptx_path).stat().st_size / 1024:.1f} KB")
    else:
        print(f"\nPPTX not generated or not found: {pptx_path}")

    return state


async def main():
    """主测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Test p2g_chunk_render workflow")
    parser.add_argument(
        "--step",
        type=str,
        choices=["prompt", "vlm", "pptx", "full"],
        default="prompt",
        help="Which step to test: prompt, vlm, pptx, or full workflow"
    )

    args = parser.parse_args()

    if args.step == "prompt":
        await test_chunk_prompt_agent()
    elif args.step == "vlm":
        await test_chunk_vlm_renderer_agent()
    elif args.step == "pptx":
        await test_chunk_pptx_composer_agent()
    elif args.step == "full":
        await test_full_workflow()


if __name__ == "__main__":
    asyncio.run(main())
