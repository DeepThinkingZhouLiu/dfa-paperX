"""
wf_p2g_chunk_render workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Paper2Graph Chunk 级别渲染工作流。

包含 3 个 agent 节点：
1. p2g_chunk_prompt_agent: 生成 chunk 级别的 VLM prompt
2. p2g_chunk_vlm_renderer_agent: 调用 VLM 渲染 chunk 图片
3. p2g_chunk_pptx_composer_agent: 组装 PPTX

输入 state 需要包含：
- semantic_json: 语义信息
- node_render_design: 节点渲染设计
- layout_json: 布局信息

输出：
- chunk_prompts: chunk 级别的 prompt
- chunk_images: chunk 图片路径
- pptx_output_path: 生成的 PPTX 路径
"""

from __future__ import annotations

from dataflow_agent.state import Paper2GraphState
from dataflow_agent.graghbuilder.gragh_builder import GenericGraphBuilder
from dataflow_agent.workflow.registry import register
from dataflow_agent.logger import get_logger

log = get_logger(__name__)


@register("p2g_chunk_render")
def create_p2g_chunk_render_graph() -> GenericGraphBuilder:
    """
    Workflow factory: dfa run --wf p2g_chunk_render

    3-agent 子图：
    chunk_prompt -> chunk_vlm_render -> chunk_pptx_compose -> _end_
    """
    builder = GenericGraphBuilder(
        state_model=Paper2GraphState,
        entry_point="chunk_prompt"
    )

    # ==============================================================
    # NODES
    # ==============================================================

    async def chunk_prompt_node(state: Paper2GraphState) -> Paper2GraphState:
        """Chunk Prompt 生成节点"""
        from dataflow_agent.agentroles.p2g_chunk_prompt_agent import p2g_chunk_prompt_agent

        log.info("[Workflow] Running chunk_prompt_node...")
        state = await p2g_chunk_prompt_agent(state)
        return state

    async def chunk_vlm_render_node(state: Paper2GraphState) -> Paper2GraphState:
        """Chunk VLM 渲染节点"""
        from dataflow_agent.agentroles.p2g_chunk_vlm_renderer_agent import p2g_chunk_vlm_renderer_agent

        log.info("[Workflow] Running chunk_vlm_render_node...")

        # 从 state 获取配置参数（如果有）
        output_dir = getattr(state, "chunk_output_dir", None)
        concurrency = getattr(state, "chunk_concurrency", 3)
        vlm_model = getattr(state, "chunk_vlm_model", None)
        timeout = getattr(state, "chunk_timeout", 180)

        state = await p2g_chunk_vlm_renderer_agent(
            state,
            output_dir=output_dir,
            concurrency=concurrency,
            vlm_model=vlm_model,
            timeout=timeout,
        )
        return state

    async def chunk_pptx_compose_node(state: Paper2GraphState) -> Paper2GraphState:
        """Chunk PPTX 组装节点"""
        from dataflow_agent.agentroles.p2g_chunk_pptx_composer_agent import p2g_chunk_pptx_composer_agent

        log.info("[Workflow] Running chunk_pptx_compose_node...")

        # 从 state 获取配置参数（如果有）
        output_path = getattr(state, "pptx_output_path_config", None)

        state = await p2g_chunk_pptx_composer_agent(
            state,
            output_path=output_path,
        )
        return state

    # ==============================================================
    # 注册 nodes / edges
    # ==============================================================
    nodes = {
        "chunk_prompt": chunk_prompt_node,
        "chunk_vlm_render": chunk_vlm_render_node,
        "chunk_pptx_compose": chunk_pptx_compose_node,
        "_end_": lambda state: state,
    }

    # ------------------------------------------------------------------
    # EDGES (从节点 A 指向节点 B)
    # ------------------------------------------------------------------
    edges = [
        ("chunk_prompt", "chunk_vlm_render"),
        ("chunk_vlm_render", "chunk_pptx_compose"),
        ("chunk_pptx_compose", "_end_"),
    ]

    builder.add_nodes(nodes).add_edges(edges)
    return builder


# 便捷函数：直接运行 workflow
async def run_p2g_chunk_render_workflow(
    state: Paper2GraphState,
    output_dir: str = None,
    output_path: str = None,
    concurrency: int = 3,
    vlm_model: str = None,
    timeout: int = 180,
) -> Paper2GraphState:
    """运行 Paper2Graph Chunk 渲染工作流

    Args:
        state: Paper2GraphState，需包含 semantic_json, node_render_design, layout_json
        output_dir: chunk 图片输出目录
        output_path: PPTX 输出路径
        concurrency: VLM 并发数
        vlm_model: VLM 模型名称
        timeout: VLM 请求超时时间

    Returns:
        更新后的 Paper2GraphState
    """
    # 设置配置参数到 state
    if output_dir:
        setattr(state, "chunk_output_dir", output_dir)
    if output_path:
        setattr(state, "pptx_output_path_config", output_path)
    setattr(state, "chunk_concurrency", concurrency)
    if vlm_model:
        setattr(state, "chunk_vlm_model", vlm_model)
    setattr(state, "chunk_timeout", timeout)

    # 创建并运行 workflow
    builder = create_p2g_chunk_render_graph()
    graph = builder.compile()

    # 运行
    result = await graph.ainvoke(state)

    return result
