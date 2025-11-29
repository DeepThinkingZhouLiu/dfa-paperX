from __future__ import annotations

import asyncio
import json
import os
import sys

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

# 修复导入路径问题
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataflow_agent.state import Paper2GraphState, Paper2GraphRequest
from dataflow_agent.agentroles.p2g_node_layout_planner_agent import plan_node_layout_for_all_chunks


def _load_json_from_tmp(name: str) -> dict:
    """从 tests/.tmp/node_layout 目录加载指定 JSON 文件。"""
    base_dir = os.path.join(os.path.dirname(__file__), ".tmp","node_layout")
    path = os.path.join(base_dir, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _run_debug() -> Paper2GraphState:
    # 构造最小的 Paper2GraphState, 直接复用已有的 semantic_json / enriched_description
    state = Paper2GraphState()
    state.request = Paper2GraphRequest()

    state.semantic_json = _load_json_from_tmp("semantic_json.json")
    # enriched_description 可能包含 semantic_desc, 用于 node 布局规划
    state.enriched_description = _load_json_from_tmp("enriched_description.json")

    # 仅运行节点级布局规划
    state = await plan_node_layout_for_all_chunks(
        state,
        model_name="gpt-4o",
        parser_type="json",
    )
    return state


def test_debug_node_layout_planner() -> None:
    """使用已有的 semantic_json/enriched_description 调试 node_layout_planner。

    输出:
    - agent_results["p2g_node_layout_planner_agent"] 原始结果
    - state.node_layout_plan 汇总结果
    """
    state = asyncio.run(_run_debug())

    ar = state.agent_results.get("p2g_node_layout_planner_agent", {})
    print("=== agent_results[p2g_node_layout_planner_agent] ===")
    print(json.dumps(ar, ensure_ascii=False, indent=2))

    print("=== state.node_layout_plan ===")
    print(json.dumps(getattr(state, "node_layout_plan", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    test_debug_node_layout_planner()
