"""测试 p2g_vlm_node_renderer_agent

读取 tests/.tmp/render_design/node_render_design.json，
并行调用 VLM 生图 + 抠图，输出到 /tmp/vlm_nodes/

输出文件命名格式: chunk{chunk_id}_node{node_id}.png
例如: chunk1_node3.png, chunk2_node7.png
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

# 设置项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

import sys
sys.path.insert(0, str(PROJECT_ROOT))

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
from dataflow_agent.agentroles.p2g_vlm_node_renderer_agent import (
    _generate_image,
    _remove_background,
    _extract_vlm_nodes,
    _assemble_vlm_prompt,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_CONCURRENCY,
    DEFAULT_VLM_MODEL,
)
from dataflow_agent.logger import get_logger

log = get_logger(__name__)

# 数据目录
DATA_DIR = Path(__file__).parent / ".tmp" / "render_design"
# 输出到 /tmp 目录
OUTPUT_DIR = Path(__file__).parent / ".tmp" / "vlm_ndoes"


def load_json(filename: str) -> dict:
    """加载 JSON 文件"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_id(id_str: str) -> str:
    """规范化 ID，去掉前缀字母，只保留数字

    例如: "c1" -> "1", "n3" -> "3"
    """
    return ''.join(filter(str.isdigit, id_str)) or id_str


def get_output_filename(chunk_id: str, node_id: str) -> str:
    """生成规范化的输出文件名

    格式: chunk{chunk_num}_node{node_num}.png
    例如: chunk1_node3.png
    """
    chunk_num = normalize_id(chunk_id)
    node_num = normalize_id(node_id)
    return f"chunk{chunk_num}_node{node_num}.png"


async def render_single_node_parallel(
    node_info: Dict[str, Any],
    output_dir: Path,
    api_url: str,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
    timeout: int = 120,
    bg_remove_method: str = "edge_floodfill",
    bg_threshold: int = 245,
) -> Tuple[str, str, str, Optional[str]]:
    """并行渲染单个 VLM 节点

    Args:
        node_info: 节点信息，包含 node_id, chunk_id, vlm_prompt/vlm_spec
        output_dir: 输出目录
        api_url: API URL
        api_key: API Key
        model: VLM 模型名称
        semaphore: 并发控制信号量
        timeout: 请求超时时间
        bg_remove_method: 抠图方法
        bg_threshold: 背景色阈值

    Returns:
        (node_id, chunk_id, final_image_path, error_message)
    """
    node_id = node_info["node_id"]
    chunk_id = node_info["chunk_id"]
    vlm_spec = node_info.get("vlm_spec", {})
    vlm_prompt = node_info.get("vlm_prompt", "")
    aspect_ratio = node_info.get("aspect_ratio", 1.0)
    bbox_w = node_info.get("bbox_w", 200)
    bbox_h = node_info.get("bbox_h", 200)

    async with semaphore:
        try:
            log.info(f"[Parallel Render] Starting: chunk={chunk_id}, node={node_id}")

            # 确保输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True)

            # 生成规范化文件名
            final_filename = get_output_filename(chunk_id, node_id)
            raw_filename = f"raw_{final_filename}"

            raw_path = str(output_dir / raw_filename)
            final_path = str(output_dir / final_filename)

            # 组装最终 prompt（支持 vlm_spec 和 vlm_prompt 两种格式）
            final_prompt = _assemble_vlm_prompt(
                vlm_spec=vlm_spec,
                vlm_prompt=vlm_prompt,
                aspect_ratio=aspect_ratio,
                bbox_w=bbox_w,
                bbox_h=bbox_h,
            )

            if not final_prompt:
                return (node_id, chunk_id, "", "Empty prompt after assembly")

            # 1. VLM 生图
            await _generate_image(
                prompt=final_prompt,
                save_path=raw_path,
                api_url=api_url,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )
            log.info(f"[Parallel Render] Generated raw image: {raw_path}")

            # 2. 抠图处理
            try:
                bg_removed_path = _remove_background(
                    raw_path,
                    str(output_dir),
                    method=bg_remove_method,
                    bg_threshold=bg_threshold,
                )
                # 重命名为规范化文件名
                if bg_removed_path != final_path:
                    shutil.copy2(bg_removed_path, final_path)
                    # 可选：删除中间文件
                    if Path(bg_removed_path).exists() and bg_removed_path != raw_path:
                        Path(bg_removed_path).unlink()

                log.info(f"[Parallel Render] Background removed: {final_path}")
            except Exception as bg_err:
                log.warning(f"[Parallel Render] BG removal failed for {node_id}: {bg_err}, using raw image")
                shutil.copy2(raw_path, final_path)

            return (node_id, chunk_id, final_path, None)

        except Exception as e:
            log.error(f"[Parallel Render] Failed: chunk={chunk_id}, node={node_id}, error={e}")
            return (node_id, chunk_id, "", str(e))


async def render_all_vlm_nodes_parallel(
    node_render_design: Dict[str, Any],
    output_dir: Path,
    concurrency: int = 5,
    vlm_model: Optional[str] = None,
    timeout: int = 120,
    bg_remove_method: str = "edge_floodfill",
    bg_threshold: int = 245,
) -> Dict[str, Any]:
    """并行渲染所有 VLM 节点

    Args:
        node_render_design: 节点渲染设计数据
        output_dir: 输出目录
        concurrency: 并发数
        vlm_model: VLM 模型名称
        timeout: 请求超时时间
        bg_remove_method: 抠图方法
        bg_threshold: 背景色阈值

    Returns:
        渲染结果字典，包含 rendered_nodes, errors, stats
    """
    # 从环境变量读取 API 配置
    api_url = os.getenv("DF_API_URL")
    api_key = os.getenv("DF_API_KEY")

    if not api_url or not api_key:
        raise ValueError("请先设置环境变量 DF_API_URL 和 DF_API_KEY")

    # 设置 VLM 模型
    if vlm_model is None:
        vlm_model = os.getenv("DF_VLM_MODEL", DEFAULT_VLM_MODEL)

    # 提取 VLM 节点
    vlm_nodes = _extract_vlm_nodes(node_render_design)

    if not vlm_nodes:
        log.info("No VLM nodes found")
        return {"rendered_nodes": {}, "errors": {}, "stats": {"total": 0, "success": 0, "failed": 0}}

    log.info(f"[Parallel Render] Found {len(vlm_nodes)} VLM nodes")
    log.info(f"[Parallel Render] Output directory: {output_dir}")
    log.info(f"[Parallel Render] Concurrency: {concurrency}")
    log.info(f"[Parallel Render] VLM model: {vlm_model}")

    # 创建并发控制信号量
    semaphore = asyncio.Semaphore(concurrency)

    # 创建所有渲染任务
    tasks = [
        render_single_node_parallel(
            node_info=node,
            output_dir=output_dir,
            api_url=api_url,
            api_key=api_key,
            model=vlm_model,
            semaphore=semaphore,
            timeout=timeout,
            bg_remove_method=bg_remove_method,
            bg_threshold=bg_threshold,
        )
        for node in vlm_nodes
    ]

    # 并行执行所有任务
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 汇总结果
    rendered_nodes: Dict[str, Dict[str, str]] = {}
    errors: Dict[str, str] = {}

    for result in results:
        if isinstance(result, Exception):
            log.error(f"[Parallel Render] Task exception: {result}")
            continue

        node_id, chunk_id, image_path, error = result
        if error:
            errors[node_id] = error
        elif image_path:
            rendered_nodes[node_id] = {
                "chunk_id": chunk_id,
                "path": image_path,
                "filename": Path(image_path).name,
            }

    stats = {
        "total": len(vlm_nodes),
        "success": len(rendered_nodes),
        "failed": len(errors),
    }

    log.info(f"[Parallel Render] Completed: {stats['success']}/{stats['total']} succeeded, {stats['failed']} failed")

    return {
        "rendered_nodes": rendered_nodes,
        "errors": errors,
        "stats": stats,
    }


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

    # 按 chunk 分组显示
    chunks_map: Dict[str, List[Dict]] = {}
    for node in vlm_nodes:
        chunk_id = node["chunk_id"]
        if chunk_id not in chunks_map:
            chunks_map[chunk_id] = []
        chunks_map[chunk_id].append(node)

    for chunk_id, nodes in sorted(chunks_map.items()):
        print(f"\n  Chunk {chunk_id}: {len(nodes)} VLM nodes")
        for node in nodes:
            filename = get_output_filename(chunk_id, node["node_id"])
            print(f"    - {node['node_id']} -> {filename}")

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

    output_filename = get_output_filename(first_node["chunk_id"], first_node["node_id"])

    print(f"\n{'=' * 60}")
    print(f"Testing single node: {first_node['node_id']}")
    print(f"Output filename: {output_filename}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"{'=' * 60}")
    print(f"VLM Prompt: {first_node['vlm_prompt'][:200]}...")

    # 执行并行渲染（单个节点）
    result = await render_all_vlm_nodes_parallel(
        node_render_design=single_node_design,
        output_dir=OUTPUT_DIR,
        concurrency=1,
        timeout=180,
    )

    # 检查结果
    rendered_nodes = result["rendered_nodes"]
    errors = result["errors"]

    print(f"\n{'=' * 60}")
    print("Results")
    print(f"{'=' * 60}")

    if rendered_nodes:
        for node_id, info in rendered_nodes.items():
            path = info["path"]
            print(f"✓ {node_id}: {info['filename']}")
            print(f"  Full path: {path}")
            assert Path(path).exists(), f"Image file should exist: {path}"

    if errors:
        for node_id, error in errors.items():
            print(f"✗ {node_id}: {error}")

    assert len(rendered_nodes) == 1, "Should render exactly one node"
    print("\n✓ Single node test passed")


async def test_vlm_node_renderer_all():
    """并行渲染所有 VLM 节点

    输出目录: /tmp/vlm_nodes/
    文件命名: chunk{chunk_id}_node{node_id}.png
    保存的是抠图后的图片
    """
    node_render_design = load_json("node_render_design.json")

    if not node_render_design:
        print("Skipping test: node_render_design.json not found")
        return

    vlm_nodes = _extract_vlm_nodes(node_render_design)

    print(f"\n{'=' * 60}")
    print(f"Parallel Rendering All VLM Nodes")
    print(f"{'=' * 60}")
    print(f"Total VLM nodes: {len(vlm_nodes)}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Concurrency: {DEFAULT_CONCURRENCY}")

    # 显示预期输出文件
    print(f"\nExpected output files:")
    for node in vlm_nodes:
        filename = get_output_filename(node["chunk_id"], node["node_id"])
        print(f"  - {filename}")

    start_time = datetime.now()

    # 执行并行渲染
    result = await render_all_vlm_nodes_parallel(
        node_render_design=node_render_design,
        output_dir=OUTPUT_DIR,
        concurrency=DEFAULT_CONCURRENCY,
        timeout=180,
        bg_remove_method="edge_floodfill",
        bg_threshold=245,
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    # 检查结果
    rendered_nodes = result["rendered_nodes"]
    errors = result["errors"]
    stats = result["stats"]

    print(f"\n{'=' * 60}")
    print("Results Summary")
    print(f"{'=' * 60}")
    print(f"Total: {stats['total']}")
    print(f"Success: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Time elapsed: {elapsed:.2f}s")
    if stats['success'] > 0:
        print(f"Average time per node: {elapsed / stats['success']:.2f}s")

    if rendered_nodes:
        print(f"\nRendered nodes ({len(rendered_nodes)}):")
        # 按 chunk 分组显示
        by_chunk: Dict[str, List[Tuple[str, Dict]]] = {}
        for node_id, info in rendered_nodes.items():
            chunk_id = info["chunk_id"]
            if chunk_id not in by_chunk:
                by_chunk[chunk_id] = []
            by_chunk[chunk_id].append((node_id, info))

        for chunk_id, nodes in sorted(by_chunk.items()):
            print(f"\n  Chunk {chunk_id}:")
            for node_id, info in nodes:
                exists = "✓" if Path(info["path"]).exists() else "✗"
                print(f"    {exists} {info['filename']}")

    if errors:
        print(f"\nFailed nodes ({len(errors)}):")
        for node_id, error in errors.items():
            print(f"  ✗ {node_id}: {error}")

    # 保存结果 JSON
    result_path = OUTPUT_DIR / "vlm_rendered_nodes.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump({
            "rendered_nodes": {k: v for k, v in rendered_nodes.items()},
            "errors": errors,
            "stats": stats,
            "elapsed_seconds": elapsed,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {result_path}")

    # 断言
    assert len(rendered_nodes) > 0, "Should render at least one node"

    # 验证文件存在且命名正确
    for node_id, info in rendered_nodes.items():
        path = Path(info["path"])
        assert path.exists(), f"Image file should exist: {path}"
        # 验证文件名格式
        assert info["filename"].startswith("chunk"), f"Filename should start with 'chunk': {info['filename']}"
        assert "_node" in info["filename"], f"Filename should contain '_node': {info['filename']}"
        assert info["filename"].endswith(".png"), f"Filename should end with '.png': {info['filename']}"

    print(f"\n✓ All nodes test passed: {len(rendered_nodes)}/{len(vlm_nodes)} succeeded")


async def test_vlm_node_renderer_skip_bg_remove():
    """测试跳过抠图（保存原始 VLM 生成图片）"""
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

    print(f"\n{'=' * 60}")
    print(f"Testing skip background removal: {first_node['node_id']}")
    print(f"{'=' * 60}")

    # 使用不同的输出目录
    output_dir = OUTPUT_DIR / "no_bg_remove"

    # 注意：当前的并行渲染函数总是执行抠图
    # 如果需要跳过抠图，可以使用原始的 p2g_vlm_node_renderer_agent
    from dataflow_agent.agentroles.p2g_vlm_node_renderer_agent import p2g_vlm_node_renderer_agent

    state = Paper2GraphState()
    state.request = Paper2GraphRequest()
    state.node_render_design = single_node_design

    result_state = await p2g_vlm_node_renderer_agent(
        state,
        output_dir=str(output_dir),
        concurrency=1,
        skip_bg_remove=True,
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

    parser = argparse.ArgumentParser(
        description="Test p2g_vlm_node_renderer_agent - 并行渲染 VLM 节点",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看所有 VLM 节点（不渲染）
  python tests/test_p2g_vlm_node_renderer_agent.py --mode extract

  # 渲染单个节点（调试用）
  python tests/test_p2g_vlm_node_renderer_agent.py --mode single

  # 并行渲染所有节点（推荐）
  python tests/test_p2g_vlm_node_renderer_agent.py --mode all

  # 自定义并发数和输出目录
  python tests/test_p2g_vlm_node_renderer_agent.py --mode all --concurrency 10 --output /tmp/my_vlm_nodes

输出文件命名格式: chunk{chunk_id}_node{node_id}.png
例如: chunk1_node3.png, chunk2_node7.png
        """
    )
    parser.add_argument(
        "--mode",
        choices=["extract", "single", "all", "skip-bg"],
        default="all",
        help="测试模式: extract (仅提取节点), single (渲染单个节点), all (并行渲染所有节点), skip-bg (跳过抠图)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"并发数，默认 {DEFAULT_CONCURRENCY}"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_DIR),
        help=f"输出目录，默认 {OUTPUT_DIR}"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="单个节点渲染超时时间（秒），默认 180"
    )
    parser.add_argument(
        "--bg-method",
        choices=["edge_floodfill", "rmbg"],
        default="edge_floodfill",
        help="抠图方法: edge_floodfill (适合图表/图标) 或 rmbg (适合人物/产品)"
    )
    parser.add_argument(
        "--bg-threshold",
        type=int,
        default=245,
        help="背景色阈值（仅 edge_floodfill 方法使用），默认 245"
    )
    args = parser.parse_args()

    # 更新全局输出目录
    OUTPUT_DIR = Path(args.output)

    if args.mode == "extract":
        test_extract_vlm_nodes()
    elif args.mode == "single":
        asyncio.run(test_vlm_node_renderer_single())
    elif args.mode == "all":
        # 使用命令行参数覆盖默认值
        async def run_all_with_args():
            node_render_design = load_json("node_render_design.json")
            if not node_render_design:
                print("Error: node_render_design.json not found")
                return

            vlm_nodes = _extract_vlm_nodes(node_render_design)

            print(f"\n{'=' * 60}")
            print(f"Parallel Rendering All VLM Nodes")
            print(f"{'=' * 60}")
            print(f"Total VLM nodes: {len(vlm_nodes)}")
            print(f"Output directory: {OUTPUT_DIR}")
            print(f"Concurrency: {args.concurrency}")
            print(f"Timeout: {args.timeout}s")
            print(f"BG removal method: {args.bg_method}")

            # 显示预期输出文件
            print(f"\nExpected output files:")
            for node in vlm_nodes:
                filename = get_output_filename(node["chunk_id"], node["node_id"])
                print(f"  - {filename}")

            start_time = datetime.now()

            # 执行并行渲染
            result = await render_all_vlm_nodes_parallel(
                node_render_design=node_render_design,
                output_dir=OUTPUT_DIR,
                concurrency=args.concurrency,
                timeout=args.timeout,
                bg_remove_method=args.bg_method,
                bg_threshold=args.bg_threshold,
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            # 检查结果
            rendered_nodes = result["rendered_nodes"]
            errors = result["errors"]
            stats = result["stats"]

            print(f"\n{'=' * 60}")
            print("Results Summary")
            print(f"{'=' * 60}")
            print(f"Total: {stats['total']}")
            print(f"Success: {stats['success']}")
            print(f"Failed: {stats['failed']}")
            print(f"Time elapsed: {elapsed:.2f}s")
            if stats['success'] > 0:
                print(f"Average time per node: {elapsed / stats['success']:.2f}s")
                print(f"Effective parallelism: {elapsed / (stats['success'] * (elapsed / stats['total'])):.1f}x" if stats['total'] > 0 else "")

            if rendered_nodes:
                print(f"\nRendered nodes ({len(rendered_nodes)}):")
                by_chunk: Dict[str, List[Tuple[str, Dict]]] = {}
                for node_id, info in rendered_nodes.items():
                    chunk_id = info["chunk_id"]
                    if chunk_id not in by_chunk:
                        by_chunk[chunk_id] = []
                    by_chunk[chunk_id].append((node_id, info))

                for chunk_id, nodes in sorted(by_chunk.items()):
                    print(f"\n  Chunk {chunk_id}:")
                    for node_id, info in nodes:
                        exists = "✓" if Path(info["path"]).exists() else "✗"
                        print(f"    {exists} {info['filename']}")

            if errors:
                print(f"\nFailed nodes ({len(errors)}):")
                for node_id, error in errors.items():
                    print(f"  ✗ {node_id}: {error}")

            # 保存结果 JSON
            result_path = OUTPUT_DIR / "vlm_rendered_nodes.json"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump({
                    "rendered_nodes": {k: v for k, v in rendered_nodes.items()},
                    "errors": errors,
                    "stats": stats,
                    "elapsed_seconds": elapsed,
                    "config": {
                        "concurrency": args.concurrency,
                        "timeout": args.timeout,
                        "bg_method": args.bg_method,
                        "bg_threshold": args.bg_threshold,
                    }
                }, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to: {result_path}")
            print(f"\n✓ Completed: {len(rendered_nodes)}/{len(vlm_nodes)} nodes rendered successfully")

        asyncio.run(run_all_with_args())
    elif args.mode == "skip-bg":
        asyncio.run(test_vlm_node_renderer_skip_bg_remove())
