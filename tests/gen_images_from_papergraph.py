#!/usr/bin/env python3
"""
根据 PaperGraph(JSON v0.2) 生成示例图像，用于快速人工目检 JSON 的有效性。

功能
- 读取 JSON（默认: iconagent/dfa-paperX/tests/test_generated.json）
- 做基本字段校验并在控制台输出报告
- 调用 VLM 的生图能力（参考 dataflow_agent/llm_callers/image.py）
  - 为每个 group 生成一张“学术示意图”
  - 可选为若干个 node 生成“图标式示意图”（受 --limit-nodes 限制）

先决条件
- 需要可用的 OpenAI 兼容 /v1 接口，且支持 response_format=image
- 环境变量 DF_API_URL / DF_API_KEY，或通过参数 --api-url / --api-key 指定

示例
  export DF_API_URL=http://123.129.219.111:3000/v1
  export DF_API_KEY=sk-xxx
  python iconagent/dfa-paperX/tests/gen_images_from_papergraph.py \
      --json-path iconagent/dfa-paperX/tests/test_generated.json \
      --outdir    iconagent/dfa-paperX/tests/out/papergraph_images \
      --model     gemini-2.5-flash-image-preview \
      --mode      both --limit-nodes 6 --concurrency 2
"""

import os
import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Tuple

from langchain_core.messages import HumanMessage

# ----------------- 导入项目内模块（添加路径） -----------------
_script_dir = Path(__file__).parent.resolve()
_project_dir = _script_dir.parent  # tests -> dfa-paperX
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

try:
    from dataflow_agent.llm_callers.image import VisionLLMCaller
    from dataflow_agent.state import MainRequest, MainState
except ImportError:
    # 兜底：再尝试添加上级目录
    p = _project_dir.parent
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    from dataflow_agent.llm_callers.image import VisionLLMCaller
    from dataflow_agent.state import MainRequest, MainState


# ----------------- 基础工具函数 -----------------
def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_papergraph(pg: Dict[str, Any]) -> Dict[str, Any]:
    """对 v0.2 的关键字段做轻量校验，返回统计信息"""
    report = {
        "version": pg.get("version"),
        "has_canvas": "canvas" in pg,
        "has_grid": "grid" in pg,
        "has_layout": "layout" in pg,
        "groups": len(pg.get("groups", [])),
        "nodes": len(pg.get("nodes", [])),
        "edges": len(pg.get("edges", [])),
        "positions_groups": len(pg.get("positions", {}).get("groups", [])) if isinstance(pg.get("positions"), dict) else 0,
        "missing": {
            "group_description": 0,
            "node_description": 0,
            "edge_description": 0,
        }
    }

    for g in pg.get("groups", []):
        if not g.get("description"):
            report["missing"]["group_description"] += 1

    for n in pg.get("nodes", []):
        if not n.get("description"):
            report["missing"]["node_description"] += 1

    for e in pg.get("edges", []):
        if not e.get("description"):
            report["missing"]["edge_description"] += 1

    return report


def build_group_prompt(group: Dict[str, Any]) -> str:
    title = group.get("title") or group.get("label") or group.get("group_id")
    desc = group.get("description", "")
    prompt = (
        f"Academic-style schematic diagram for: {title}.\n"
        f"Content: {desc}\n"
        f"Style requirements: clean vector/flat style, white background, high contrast, minimal decorations, 16:9 aspect.\n"
        f"Avoid overlay text; use shapes/icons to convey the idea."
    )
    return prompt


def build_node_prompt(node: Dict[str, Any]) -> str:
    label = node.get("label") or node.get("node_id")
    ntype = node.get("type") or "object"
    desc = node.get("description", "")
    prompt = (
        f"Icon-like schematic for node '{label}' ({ntype}).\n"
        f"Content: {desc}\n"
        f"Style requirements: minimal icon/logo style, white background, high contrast, simple geometry, avoid text."
    )
    return prompt


async def generate_one_image(
    state: MainState,
    model_name: str,
    prompt: str,
    save_path: Path,
    timeout: int = 120,
) -> Tuple[Path, bool, str]:
    """调用 VLM 生成一张图片，返回 (路径, 是否成功, 备注)"""
    caller = VisionLLMCaller(
        state=state,
        vlm_config={
            "mode": "generation",
            "output_image": str(save_path),
            "timeout": timeout,
        },
        model_name=model_name,
    )
    try:
        await caller.call([HumanMessage(content=prompt)])
        return save_path, True, ""
    except Exception as e:
        return save_path, False, str(e)


async def bounded_gather(tasks: List[asyncio.Task], concurrency: int = 2):
    sem = asyncio.Semaphore(concurrency)

    async def _run(coro):
        async with sem:
            return await coro

    return await asyncio.gather(*[_run(t) for t in tasks])


async def async_main(args) -> int:
    # 1) 加载 JSON
    json_path = Path(args.json_path).expanduser().resolve()
    if not json_path.exists():
        print(f"❌ JSON 不存在: {json_path}")
        return 2
    pg = load_json(json_path)

    # 2) 轻量校验
    rep = validate_papergraph(pg)
    print("=== PaperGraph v0.2 简要校验 ===")
    print(f"version: {rep['version']}")
    print(f"canvas/layout/grid 存在性: {rep['has_canvas']}/{rep['has_layout']}/{rep['has_grid']}")
    print(f"groups/nodes/edges: {rep['groups']}/{rep['nodes']}/{rep['edges']}")
    print(f"positions.groups: {rep['positions_groups']}")
    miss = rep["missing"]
    print(f"缺失 description -> group:{miss['group_description']} node:{miss['node_description']} edge:{miss['edge_description']}")

    # 3) 组装 State
    api_url = (args.api_url or os.getenv("DF_API_URL") or "").rstrip("/")
    api_key = args.api_key or os.getenv("DF_API_KEY") or ""
    model_name = args.model
    if not api_url:
        api_url = MainRequest().chat_api_url  # 使用默认
        print(f"⚠️  未提供 --api-url/DF_API_URL，使用默认: {api_url}")
    if not api_key or api_key == "test":
        print("⚠️  未提供有效的 API Key（DF_API_KEY 或 --api-key）。生图很可能失败。")

    request = MainRequest(chat_api_url=api_url, api_key=api_key, model=model_name)
    state = MainState(request=request)

    # 4) 选择待生成目标
    outdir = Path(args.outdir).expanduser().resolve()
    groups_out = outdir / "groups"
    nodes_out = outdir / "nodes"
    groups_out.mkdir(parents=True, exist_ok=True)
    nodes_out.mkdir(parents=True, exist_ok=True)

    tasks: List[asyncio.Task] = []
    summary: List[Tuple[str, Path]] = []

    if args.mode in ("both", "group"):
        for idx, g in enumerate(pg.get("groups", [])[: args.limit_groups or 9999]):
            prompt = build_group_prompt(g)
            gid = g.get("group_id") or f"g{idx:02d}"
            save_path = groups_out / f"{idx:02d}_{gid}.png"
            tasks.append(asyncio.create_task(generate_one_image(state, model_name, prompt, save_path, args.timeout)))
            summary.append((f"group:{gid}", save_path))

    if args.mode in ("both", "node"):
        for idx, n in enumerate(pg.get("nodes", [])[: args.limit_nodes]):
            prompt = build_node_prompt(n)
            nid = n.get("node_id") or f"n{idx:03d}"
            save_path = nodes_out / f"{idx:03d}_{nid}.png"
            tasks.append(asyncio.create_task(generate_one_image(state, model_name, prompt, save_path, args.timeout)))
            summary.append((f"node:{nid}", save_path))

    if not tasks:
        print("ℹ️  没有可生成的目标（检查 --mode / --limit-* 参数）")
        return 0

    print(f"🚀 开始生成图像：共 {len(tasks)} 项，最大并发 {args.concurrency}")
    results = await bounded_gather(tasks, concurrency=args.concurrency)

    ok = 0
    for (tag, path), (save_path, success, err) in zip(summary, results):
        assert path == save_path
        if success:
            ok += 1
            print(f"✅ {tag} -> {save_path}")
        else:
            print(f"❌ {tag} -> {save_path} 失败: {err}")

    print(f"完成：成功 {ok}/{len(tasks)}。输出目录: {outdir}")
    return 0 if ok > 0 else 1


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 PaperGraph(JSON v0.2) 生成示例图像")
    parser.add_argument("--json-path", default=str(_script_dir / "test_generated_en.json"), help="输入 JSON 路径")
    parser.add_argument("--outdir", default=str(_script_dir / "out/papergraph_images"), help="输出目录")
    parser.add_argument("--model", default="gemini-2.5-flash-image-preview", help="用于生图的模型名")
    parser.add_argument("--api-url", default=os.getenv("DF_API_URL"), help="OpenAI 兼容 /v1 接口地址")
    parser.add_argument("--api-key", default=os.getenv("DF_API_KEY"), help="API Key")
    parser.add_argument("--mode", choices=["group", "node", "both"], default="both", help="生成对象范围")
    parser.add_argument("--limit-nodes", type=int, default=6, help="最多生成多少个 node 图像")
    parser.add_argument("--limit-groups", type=int, default=None, help="最多生成多少个 group 图像")
    parser.add_argument("--concurrency", type=int, default=2, help="并发请求数")
    parser.add_argument("--timeout", type=int, default=120, help="单次请求超时（秒）")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("^C 取消")
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

