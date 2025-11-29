"""测试 p2g_vlm_node_renderer_agent

读取 tests/.tmp/layout_pipeline/node_render_design.json，
调用 VLM 生图 + 抠图，输出到 tests/.tmp/vlm_nodes/
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
from dataflow_agent.agentroles.p2g_vlm_node_renderer_agent import (
    p2g_vlm_node_renderer_agent,
    _extract_vlm_nodes,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_CONCURRENCY,
    DEFAULT_VLM_MODEL,
)


# 数据目录
DATA_DIR = Path(__file__).parent / ".tmp" / "layout_pipeline"
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "vlm_nodes"


def load_json(filename: str) -> dict:
    """加载 JSON 文件"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def test_extract_vlm_nodes():
    """测试提取 VLM 节点"""
    node_render_design = load_json("node_render_design.json")
    
    if not node_render_design:
        print("Skipping test: node_render_design.json not found")
        return
    
    vlm_nodes = _extract_vlm_nodes(node_render_design)
    
    print(f"\n{'=' * 60}")
    print("Extracted VLM Nodes")
    print(f"{'=' * 60}")
    print(f"Total VLM nodes: {len(vlm_nodes)}")
    
    for node in vlm_nodes:
        print(f"\n  Node ID: {node['node_id']}")
        print(f"  Chunk ID: {node['chunk_id']}")
        print(f"  VLM Prompt: {node['vlm_prompt'][:100]}...")
    
    # 断言
    assert len(vlm_nodes) > 0, "Should have at least one VLM node"
    
    for node in vlm_nodes:
        assert "node_id" in node, "Node should have node_id"
        assert "vlm_prompt" in node, "Node should have vlm_prompt"
        assert node["vlm_prompt"], "vlm_prompt should not be empty"
    
    print(f"\n✓ Test passed: {len(vlm_nodes)} VLM nodes extracted")


async def test_vlm_node_renderer_single():
    """测试单个节点渲染（用于调试）"""
    node_render_design = load_json("node_render_design.json")
    
    if not node_render_design:
        print("Skipping test: node_render_design.json not found")
        return
    
    # 只取第一个 VLM 节点测试
    vlm_nodes = _extract_vlm_nodes(node_render_design)
    if not vlm_nodes:
        print("No VLM nodes found")
        return
    
    first_node = vlm_nodes[0]
    
    # 构建只包含一个节点的 node_render_design
    single_node_design = {
        "chunks": [{
            "chunk_id": first_node["chunk_id"],
            "nodes": [{
                "node_id": first_node["node_id"],
                "render_method": "vlm",
                "vlm_prompt": first_node["vlm_prompt"],
            }]
        }],
        "global_style": node_render_design.get("global_style", {})
    }
    
    # 构建 state
    state = Paper2GraphState()
    state.request = Paper2GraphRequest()
    state.node_render_design = single_node_design
    
    print(f"\n{'=' * 60}")
    print(f"Testing single node: {first_node['node_id']}")
    print(f"{'=' * 60}")
    print(f"VLM Prompt: {first_node['vlm_prompt'][:200]}...")
    
    # 执行
    result_state = await p2g_vlm_node_renderer_agent(
        state,
        output_dir=str(OUTPUT_DIR),
        concurrency=1,
        skip_bg_remove=False,  # 测试抠图
        timeout=180,
    )
    
    # 检查结果
    vlm_rendered_nodes = getattr(result_state, "vlm_rendered_nodes", {})
    errors = getattr(result_state, "vlm_render_errors", {})
    
    print(f"\n{'=' * 60}")
    print("Results")
    print(f"{'=' * 60}")
    
    if vlm_rendered_nodes:
        for node_id, path in vlm_rendered_nodes.items():
            print(f"✓ {node_id}: {path}")
            assert Path(path).exists(), f"Image file should exist: {path}"
    
    if errors:
        for node_id, error in errors.items():
            print(f"✗ {node_id}: {error}")
    
    assert len(vlm_rendered_nodes) == 1, "Should render exactly one node"
    print("\n✓ Single node test passed")


async def test_vlm_node_renderer_all():
    """测试渲染所有 VLM 节点"""
    node_render_design = load_json("node_render_design.json")
    
    if not node_render_design:
        print("Skipping test: node_render_design.json not found")
        return
    
    # 构建 state
    state = Paper2GraphState()
    state.request = Paper2GraphRequest()
    state.node_render_design = node_render_design
    
    vlm_nodes = _extract_vlm_nodes(node_render_design)
    
    print(f"\n{'=' * 60}")
    print(f"Testing all VLM nodes: {len(vlm_nodes)} nodes")
    print(f"{'=' * 60}")
    
    # 执行
    result_state = await p2g_vlm_node_renderer_agent(
        state,
        output_dir=str(OUTPUT_DIR),
        concurrency=5,  # 并发 5
        skip_bg_remove=False,
        timeout=180,
    )
    
    # 检查结果
    vlm_rendered_nodes = getattr(result_state, "vlm_rendered_nodes", {})
    errors = getattr(result_state, "vlm_render_errors", {})
    stats = result_state.agent_results.get("p2g_vlm_node_renderer_agent", {}).get("stats", {})
    
    print(f"\n{'=' * 60}")
    print("Results Summary")
    print(f"{'=' * 60}")
    print(f"Total: {stats.get('total', 0)}")
    print(f"Success: {stats.get('success', 0)}")
    print(f"Failed: {stats.get('failed', 0)}")
    
    if vlm_rendered_nodes:
        print(f"\nRendered nodes ({len(vlm_rendered_nodes)}):")
        for node_id, path in vlm_rendered_nodes.items():
            exists = "✓" if Path(path).exists() else "✗"
            print(f"  {exists} {node_id}: {path}")
    
    if errors:
        print(f"\nFailed nodes ({len(errors)}):")
        for node_id, error in errors.items():
            print(f"  ✗ {node_id}: {error}")
    
    # 保存结果
    result_path = OUTPUT_DIR / "vlm_rendered_nodes.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "vlm_rendered_nodes": vlm_rendered_nodes,
            "errors": errors,
            "stats": stats,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {result_path}")
    
    # 断言
    assert len(vlm_rendered_nodes) > 0, "Should render at least one node"
    
    # 验证文件存在
    for node_id, path in vlm_rendered_nodes.items():
        assert Path(path).exists(), f"Image file should exist: {path}"
    
    print(f"\n✓ All nodes test passed: {len(vlm_rendered_nodes)}/{len(vlm_nodes)} succeeded")


async def test_vlm_node_renderer_skip_bg_remove():
    """测试跳过抠图"""
    node_render_design = load_json("node_render_design.json")
    
    if not node_render_design:
        print("Skipping test: node_render_design.json not found")
        return
    
    # 只取第一个 VLM 节点测试
    vlm_nodes = _extract_vlm_nodes(node_render_design)
    if not vlm_nodes:
        print("No VLM nodes found")
        return
    
    first_node = vlm_nodes[0]
    
    # 构建只包含一个节点的 node_render_design
    single_node_design = {
        "chunks": [{
            "chunk_id": first_node["chunk_id"],
            "nodes": [{
                "node_id": first_node["node_id"],
                "render_method": "vlm",
                "vlm_prompt": first_node["vlm_prompt"],
            }]
        }],
        "global_style": node_render_design.get("global_style", {})
    }
    
    # 构建 state
    state = Paper2GraphState()
    state.request = Paper2GraphRequest()
    state.node_render_design = single_node_design
    
    print(f"\n{'=' * 60}")
    print(f"Testing skip background removal: {first_node['node_id']}")
    print(f"{'=' * 60}")
    
    # 使用不同的输出目录
    output_dir = OUTPUT_DIR / "no_bg_remove"
    
    # 执行（跳过抠图）
    result_state = await p2g_vlm_node_renderer_agent(
        state,
        output_dir=str(output_dir),
        concurrency=1,
        skip_bg_remove=True,  # 跳过抠图
        timeout=180,
    )
    
    # 检查结果
    vlm_rendered_nodes = getattr(result_state, "vlm_rendered_nodes", {})
    
    if vlm_rendered_nodes:
        for node_id, path in vlm_rendered_nodes.items():
            print(f"✓ {node_id}: {path}")
            assert "_raw.png" in path, "Should use raw image when skip_bg_remove=True"
            assert Path(path).exists(), f"Image file should exist: {path}"
    
    print("\n✓ Skip background removal test passed")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test p2g_vlm_node_renderer_agent")
    parser.add_argument(
        "--mode",
        choices=["extract", "single", "all", "skip-bg"],
        default="single",
        help="Test mode: extract (only extract nodes), single (render one node), all (render all), skip-bg (skip background removal)"
    )
    args = parser.parse_args()
    
    if args.mode == "extract":
        test_extract_vlm_nodes()
    elif args.mode == "single":
        asyncio.run(test_vlm_node_renderer_single())
    elif args.mode == "all":
        asyncio.run(test_vlm_node_renderer_all())
    elif args.mode == "skip-bg":
        asyncio.run(test_vlm_node_renderer_skip_bg_remove())
