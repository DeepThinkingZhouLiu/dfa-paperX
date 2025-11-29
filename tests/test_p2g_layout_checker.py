from __future__ import annotations

import asyncio
import json
import os

import sys

# 避免导入 agentroles 包时自动导入全部 agent 造成外部依赖错误
os.environ.setdefault("DF_SKIP_AGENTROLE_AUTOINIT", "1")

# 修复导入路径问题，保证可以从项目根目录导入 dataflow_agent
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dataflow_agent.state import Paper2GraphState
from dataflow_agent.agentroles.p2g_layout_checker_agent import p2g_layout_checker_agent


def test_p2g_layout_checker_draws_wireframe() -> None:
    """读取 .tmp 下的 layout_json，调用 checker 生成 draft.png。

    该测试依赖于 tests/.tmp/layout_json.json 已由前置流水线脚本生成。
    若文件缺失，则直接跳过（不视为失败），以便在 CI 中独立运行。
    """

    tmp_dir = os.path.join(CURRENT_DIR, ".tmp")
    layout_path = os.path.join(tmp_dir, "layout_pipeline","layout_json.json")

    if not os.path.exists(layout_path):
        # 前置生成脚本未运行，跳过本测试
        import pytest  # type: ignore

        pytest.skip("tests/.tmp/layout_json.json not found, skip wireframe test")

    print(f"[layout_checker_test] Using tmp_dir: {tmp_dir}")
    print(f"[layout_checker_test] Loading layout_json from: {layout_path}")

    with open(layout_path, "r", encoding="utf-8") as f:
        layout_json = json.load(f)

    positions = (layout_json or {}).get("positions", {}) if isinstance(layout_json, dict) else {}
    chunks = positions.get("chunks", []) or []
    nodes = positions.get("nodes", []) or []
    print(f"[layout_checker_test] layout_json loaded. chunks={len(chunks)}, nodes={len(nodes)}")

    state = Paper2GraphState()
    state.layout_json = layout_json

    print("[layout_checker_test] Calling p2g_layout_checker_agent to draw wireframe...")

    # 调用异步的 checker agent
    asyncio.run(p2g_layout_checker_agent(state))

    # 断言 draft.png 已经生成
    draft_path = os.path.join(tmp_dir, "draft.png")
    print(f"[layout_checker_test] Checking draft image at: {draft_path}")
    assert os.path.exists(draft_path), f"draft.png should be generated at {draft_path}"
    print("[layout_checker_test] draft.png generated successfully.")


if __name__ == "__main__":
    # 允许直接 python tests/test_p2g_layout_checker.py 运行进行快速验证
    test_p2g_layout_checker_draws_wireframe()
    print("draft.png generated under tests/.tmp (if layout_json.json existed).")
