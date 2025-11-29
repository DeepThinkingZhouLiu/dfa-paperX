"""
P2gLayoutCheckerAgent agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
生成时间: 2025-11-16 00:20:23

本文件由 `dfa create --agent_name p2g_layout_checker_agent` 自动生成。
1. 填写 prompt-template 名称
2. 根据需要完成 get_task_prompt_params / update_state_result
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont

from dataflow_agent.state import MainState, Paper2GraphState
from dataflow_agent.toolkits.tool_manager import ToolManager
from dataflow_agent.logger import get_logger
from dataflow_agent.agentroles.base_agent import BaseAgent
from dataflow_agent.agentroles.registry import register

log = get_logger(__name__)

# ----------------------------------------------------------------------
# Agent Definition
# ----------------------------------------------------------------------
@register("p2g_layout_checker_agent")
class P2gLayoutCheckerAgent(BaseAgent):
    """根据 layout_json 绘制简单线框图并保存到 .tmp/draft.png。

    当前版本不调用 LLM，仅作为工具节点：
    - 从 tests/.tmp/layout_json.json 读取布局 JSON；
    - 以 layout_json.canvas 为优先，否则使用默认画布 1920x1080；
    - 绘制 chunks 与 nodes 的 bbox 矩形以及简单标签；
    - 将结果保存为 tests/.tmp/draft.png，供人工快速查看布局效果。
    """

    # ---------- 工厂 ----------
    @classmethod
    def create(cls, tool_manager: Optional[ToolManager] = None, **kwargs):
        return cls(tool_manager=tool_manager, **kwargs)

    # ---------- 基本配置 ----------
    @property
    def role_name(self) -> str:  # noqa: D401
        return "p2g_layout_checker_agent"

    @property
    def system_prompt_template_name(self) -> str:
        # TODO: 修改为真实的模板 id
        return "system_prompt_for_p2g_layout_checker_agent"

    @property
    def task_prompt_template_name(self) -> str:
        # TODO: 修改为真实的模板 id
        return "task_prompt_for_p2g_layout_checker_agent"

    # ---------- Prompt 参数 ----------
    def get_task_prompt_params(self, pre_tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """根据前置工具结果构造 prompt 参数
        提示词中的占位符：
        return {
            'text2img_prompt': pre_tool_results.get('prompt', ''),
            'image_size': pre_tool_results.get('size', '512x512'),
            'num_images': pre_tool_results.get('num_images', 1),
        }
        """
        # 本 checker 节点当前不依赖 LLM，直接在 update_state_result 中完成绘图逻辑。
        # 这里返回空参数，避免触发不必要的 prompt 占位符。
        return {}

    def get_default_pre_tool_results(self) -> Dict[str, Any]:
        """若调用方未显式传入，返回默认前置工具结果"""
        return {}

    # ---------- 结果写回 ----------
    def update_state_result(
        self,
        state: MainState,
        result: Dict[str, Any],
        pre_tool_results: Dict[str, Any],
    ):
        """根据前置 layout_json 在 .tmp 下绘制线框草图 draft.png。

        约定：
        - layout_json 已由前序 agent 写入 `state.layout_json` 或 tests/.tmp/layout_json.json；
        - 画布尺寸优先使用 layout_json["canvas"], 否则使用 1920x1080；
        - 输出文件固定为 tests/.tmp/draft.png（与测试脚本约定的 .tmp 目录保持一致）。
        """

        # 仅在 Paper2GraphState 场景下执行绘图逻辑，避免影响其他流水线
        if not isinstance(state, Paper2GraphState):
            log.warning("p2g_layout_checker_agent: state is not Paper2GraphState, skip drawing")
            return

        # 推断 tests/.tmp 目录路径：使用当前文件所在项目下的 tests 目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        tests_tmp_dir = os.path.join(project_root, "tests", ".tmp")
        os.makedirs(tests_tmp_dir, exist_ok=True)

        # 优先从状态中拿 layout_json，其次从 tests/.tmp/layout_json.json 读取
        layout = getattr(state, "layout_json", None)
        if not isinstance(layout, dict) or not layout:
            layout_json_path = os.path.join(tests_tmp_dir, "layout_json.json")
            if os.path.exists(layout_json_path):
                try:
                    with open(layout_json_path, "r", encoding="utf-8") as f:
                        layout = json.load(f)
                except Exception as exc:  # pragma: no cover - 防御性
                    log.error("Failed to load layout_json from %s: %s", layout_json_path, exc)
                    return
            else:
                log.warning("p2g_layout_checker_agent: no layout_json available, skip drawing")
                return

        # 画布尺寸：优先 canvas，否则默认 1920x1080
        canvas = layout.get("canvas", {}) if isinstance(layout, dict) else {}
        width = int(canvas.get("width", 1920) or 1920)
        height = int(canvas.get("height", 1080) or 1080)

        # 创建白底画布
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        positions = layout.get("positions", {}) if isinstance(layout, dict) else {}
        chunks = positions.get("chunks", []) or []
        nodes = positions.get("nodes", []) or []

        # 尝试加载默认字体；失败则使用 ImageFont.load_default()
        try:
            font = ImageFont.load_default()
        except Exception:  # pragma: no cover - 理论上不会触发
            font = None

        # 绘制 chunk 边框（粗线 + 浅色）
        for chunk in chunks:
            bbox = (chunk or {}).get("bbox", {})
            x = int(bbox.get("x", 0) or 0)
            y = int(bbox.get("y", 0) or 0)
            w = int(bbox.get("w", 0) or 0)
            h = int(bbox.get("h", 0) or 0)
            if w <= 0 or h <= 0:
                continue
            draw.rectangle([x, y, x + w, y + h], outline=(200, 200, 200), width=3)
            title = (chunk or {}).get("title") or (chunk or {}).get("chunk_id") or "chunk"
            if font is not None:
                draw.text((x + 4, y + 4), str(title), fill=(80, 80, 80), font=font)

        # 绘制 node 边框（深色）
        for node in nodes:
            bbox = (node or {}).get("bbox", {})

            # 兼容两种 bbox 表达：
            # 1) {x, y, w, h}
            # 2) {left, top, width, height}
            if all(k in bbox for k in ("x", "y", "w", "h")):
                x = int(bbox.get("x", 0) or 0)
                y = int(bbox.get("y", 0) or 0)
                w = int(bbox.get("w", 0) or 0)
                h = int(bbox.get("h", 0) or 0)
            else:
                x = int(bbox.get("left", 0) or 0)
                y = int(bbox.get("top", 0) or 0)
                w = int(bbox.get("width", 0) or 0)
                h = int(bbox.get("height", 0) or 0)
            if w <= 0 or h <= 0:
                continue
            draw.rectangle([x, y, x + w, y + h], outline=(0, 0, 0), width=2)
            label = (node or {}).get("node_id") or (node or {}).get("desc") or "node"
            if font is not None:
                draw.text((x + 4, y + 4), str(label), fill=(0, 0, 0), font=font)

        # 保存到固定路径 draft.png
        out_path = os.path.join(tests_tmp_dir, "draft.png")
        try:
            img.save(out_path)
            log.info("p2g_layout_checker_agent: draft wireframe saved to %s", out_path)
        except Exception as exc:  # pragma: no cover - 防御性
            log.error("Failed to save draft wireframe to %s: %s", out_path, exc)

        # 当前阶段不修改 state 中的额外字段，仅生成文件供测试使用
        return


# ----------------------------------------------------------------------
# Helper APIs
# ----------------------------------------------------------------------
async def p2g_layout_checker_agent(
    state: MainState,
    model_name: Optional[str] = None,
    tool_manager: Optional[ToolManager] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_mode: str = "auto",
    react_mode: bool = False,
    react_max_retries: int = 3,
    parser_type: str = "json",
    parser_config: Optional[Dict[str, Any]] = None,
    use_vlm: bool = False,
    vlm_config: Optional[Dict[str, Any]] = None,
    use_agent: bool = False,
    **kwargs,
) -> MainState:
    """p2g_layout_checker_agent 的异步入口
    
    Args:
        state: 主状态对象
        model_name: 模型名称，如 "gpt-4"
        tool_manager: 工具管理器实例
        temperature: 采样温度，控制随机性 (0.0-1.0)
        max_tokens: 最大生成token数
        tool_mode: 工具调用模式 ("auto", "none", "required")
        react_mode: 是否启用ReAct推理模式
        react_max_retries: ReAct模式下最大重试次数
        parser_type: 解析器类型 ("json", "xml", "text")，这个允许你在提示词中定义LLM不同的返回，xml还是json，还是直出；
        parser_config: 解析器配置字典（如XML的root_tag）
        use_vlm: 是否使用视觉语言模型，使用了视觉模型，其余的参数失效；
        vlm_config: VLM配置字典
        use_agent: 是否使用agent模式
        **kwargs: 其他传递给execute的参数
        
    Returns:
        更新后的MainState对象
    """
    agent = P2gLayoutCheckerAgent(
        tool_manager=tool_manager,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        tool_mode=tool_mode,
        react_mode=react_mode,
        react_max_retries=react_max_retries,
        parser_type=parser_type,
        parser_config=parser_config,
        use_vlm=use_vlm,
        vlm_config=vlm_config,
    )
    return await agent.execute(state, use_agent=use_agent, **kwargs)


def create_p2g_layout_checker_agent(
    tool_manager: Optional[ToolManager] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_mode: str = "auto",
    react_mode: bool = False,
    react_max_retries: int = 3,
    parser_type: str = "json",
    parser_config: Optional[Dict[str, Any]] = None,
    use_vlm: bool = False,
    vlm_config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> P2gLayoutCheckerAgent:
    return P2gLayoutCheckerAgent.create(
        tool_manager=tool_manager,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        tool_mode=tool_mode,
        react_mode=react_mode,
        react_max_retries=react_max_retries,
        parser_type=parser_type,
        parser_config=parser_config,
        use_vlm=use_vlm,
        vlm_config=vlm_config,
        **kwargs,
    )
