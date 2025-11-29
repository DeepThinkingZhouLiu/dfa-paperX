**总体目标与范围**
- 目标：实现从自然语言 target 到规范化 PaperGraph v0.4 并最终渲染科研绘图的 p2g 工作流（paper-to-graph）。
- 依据：设计文档 `design_docs/workflow_design.md`, `design_docs/papergraph_schema_v0.4.md`, `design_docs/paperX.md`。
- 输出：符合 v0.4 三层结构（语义层/布局层/美学层）与辅助层的 `papergraph` 对象，以及可视化产物（wireframe 与最终图）。

**工作流拓扑与职责**
- 节点顺序与路由：
  - p2g_target_analyst → p2g_semantic_constructor → p2g_layout_constructor → p2g_designer → p2g_layout_checker → p2g_semantic_checker → 渲染
  - 条件返回：
    - p2g_layout_checker 有反馈则回到 p2g_layout_constructor；无反馈则进入 p2g_semantic_checker。
    - p2g_semantic_checker 不一致则回到 p2g_semantic_constructor；一致则进入渲染。

**数据结构与状态扩展**
- 使用单个字典 `description_json` 承载 v0.4 的多层结构（JSON 对象支持多层嵌套）：
  - 语义层：`description_json.canvas`, `description_json.grid`, `description_json.layout`, `description_json.chunks`, `description_json.groups`, `description_json.nodes`, `description_json.edges`, `description_json.taxonomy`
  - 布局层：`description_json.positions`
  - 美学层：`description_json.style_sheet`
  - 辅助层：`description_json.version`, `description_json.layout_runtime_meta`
  - 资产与中间产物：`description_json.assets = { out_dir, wireframe_path, final_image_path }`
- 在 `dataflow_agent/state.py` 中为 `DFState` 增加 `description_json: Dict[str, Any] = field(default_factory=dict)`；入口脚本负责设置输出目录并写入 `state`（如 `state.temp_data["out_dir"]` 同步到 `description_json.assets.out_dir`）。
- 新增 Pydantic 模型（规范工具参数与校验）：文件 `dataflow_agent/papergraph/schema_v0_4.py`
  - 核心模型：`BBox`, `Pos`, `PortHint`, `PortPose`, `Annotation`
  - 语义层：`GroupSpec`, `NodeSpec`, `EdgeSpec`, `LayoutSpec`
  - 布局层：`GroupPos`, `NodePos`, `EdgeRoute`, `Positions`
  - 美学层：`Globals`, `StyleRule`, `StyleSheet`
  - 顶层：`PaperGraphV04`
  - 作用：供 LLM 工具调用（如 save_semantic_layer/save_style_sheet）使用参数 schema，确保输出稳定与可解析。

**工具函数与计算节点（Python）**
- 目录 `dataflow_agent/toolkits/papergraphtool/`：
  - `semantic.py`：`save_semantic_layer(nodes, edges, groups, canvas, grid, layout, chunks, taxonomy)`
    - 将 LLM 产出的语义对象转换/校验为 Pydantic 模型，合并写入 `state.description_json`。
  - `style.py`：`save_style_sheet(globals, rules)`
    - 校验/归一化风格规则，写入 `state.description_json.style_sheet`。
  - `layout.py`：`solve_layout(state) -> {"positions": ..., "layout_runtime_meta": ...}`
    - 输入：`state.description_json` 的语义层。
    - 实现：优先调用 dagre/elk（若依赖不可用则提供 fallback 的 L-R 排布 + 网格/正交折线路由）。
    - 输出：节点/组 bbox、端口坐标 `PortPose`、边路径 `route_points` 等。
  - `wireframe.py`：`draw_wireframe(positions, style_sheet, save_path) -> save_path`
    - 使用 Pillow 绘制线框图（节点矩形/端口/边路径），并输出 `wireframe.png`。
  - `validators.py`：`check_geometry(positions, canvas) -> list[str]`
    - 检查重叠、越界、边路由穿越组边界等，返回问题列表。

**代理节点开发清单**
- 通用要求：每个代理在 `dataflow_agent/promptstemplates/prompts_repo.py` 中增加对应的 `system_prompt_*` 与 `task_prompt_*` 模板；`agentroles/p2g_*` 实现 `get_task_prompt_params` 与 `update_state_result`；必要时绑定工具。

- 1) p2g_target_analyst（目标解析）
  - 输入：`state.request.target`
  - 处理：LLM 扩展为详细自然语言 `enriched_description`。
  - 输出：写入 `state.temp_data["enriched_description"]` 与 `state.agent_results["p2g_target_analyst"].results`。
  - 修改文件：
    - `dataflow_agent/agentroles/p2g_target_analyst_agent.py`：完善 `system/task` 模板名；实现参数提取与结果写回。
    - `dataflow_agent/promptstemplates/prompts_repo.py`：添加 `system_prompt_for_p2g_target_analyst`、`task_prompt_for_p2g_target_analyst`。

- 2) p2g_semantic_constructor（语义构建）
  - 输入：`state.temp_data.enriched_description`
  - 处理：LLM 调用工具 `save_semantic_layer(...)`（使用 Pydantic 参数），将 nodes/edges/groups 等规范化并写入 state。
  - 输出：更新 `state.papergraph` 的语义层字段。
  - 修改文件：
    - `dataflow_agent/agentroles/p2g_semantic_constructor_agent.py`：绑定工具，设置解析器 `json`，实现写回。
    - `dataflow_agent/toolkits/papergraphtool/semantic.py`：实现保存逻辑与校验。
    - `dataflow_agent/promptstemplates/prompts_repo.py`：添加 `system_prompt_for_p2g_semantic_constructor`、`task_prompt_for_p2g_semantic_constructor`（明确工具参数 schema）。

- 3) p2g_layout_constructor（布局构建/纯 Python）
  - 输入：`state.papergraph` 的语义层（nodes/edges/groups/layout 等）。
  - 处理：调用 `solve_layout(...)` 计算坐标与路径，附带运行元信息。
  - 输出：写入 `state.description_json.positions` 与 `state.description_json.layout_runtime_meta`。
  - 修改文件：
    - `dataflow_agent/agentroles/p2g_layout_constructor_agent.py`：转为 Python 计算节点（不走 LLM），调用工具并写回。
    - `dataflow_agent/toolkits/papergraphtool/layout.py`：实现布局求解（dagre/elk 优先，fallback 算法保证可用）。

- 4) p2g_designer（美学设计构建）
  - 输入：语义标签（type、role、groups 等）。
  - 处理：LLM 产出风格规则并调用 `save_style_sheet(...)` 保存。
  - 输出：写入 `state.description_json.style_sheet`。
  - 修改文件：
    - `dataflow_agent/agentroles/p2g_designer_agent.py`：绑定工具与写回逻辑。
    - `dataflow_agent/toolkits/papergraphtool/style.py`：实现风格保存与规范化。
    - `dataflow_agent/promptstemplates/prompts_repo.py`：添加 `system_prompt_for_p2g_designer`、`task_prompt_for_p2g_designer`（声明 StyleSheet 模型字段）。

- 5) p2g_layout_checker（几何+美学验证/纯 Python + VLM审计）
  - 输入：`description_json.positions`, `description_json.canvas`, `description_json.style_sheet`。
  - 处理：
    - 程序化检查：调用 `validators.check_geometry(...)`。
    - 线框图：调用 `wireframe.draw_wireframe(...)`，保存 `wireframe.png` 到 `description_json.assets.out_dir`。
    - VLM 审计：使用 `VisionLLMCaller`（默认模型 `gemini-2.5-flash-image-preview`，输入 `wireframe.png`，参考 `dataflow_agent/llm_callers/image.py`）给出美学反馈（清晰度、对齐度等）。
  - 输出：写入 `state.agent_results["p2g_layout_checker"].results = {feedback, wireframe_url, is_layout_ok}`；根据反馈路由回布局或前进。
  - 修改文件：
    - `dataflow_agent/agentroles/p2g_layout_checker_agent.py`：改为 Python 节点封装上述流程。
    - `dataflow_agent/toolkits/papergraphtool/wireframe.py`、`validators.py`：实现绘制与校验。

- 6) p2g_semantic_checker（语义一致性验证/LLM）
  - 输入：`state.request.target`, `wireframe_url`。
  - 处理：LLM 对比 target 与线框图（多模态理解），调用 `submit_semantic_feedback(is_correct: bool, feedback_text: str)` 工具。
  - 输出：写入 `state.agent_results["p2g_semantic_checker"].results = {is_correct, feedback}`；路由回语义构建或进入渲染。
  - 修改文件：
    - `dataflow_agent/agentroles/p2g_semantic_checker_agent.py`：绑定工具与写回。
    - `dataflow_agent/promptstemplates/prompts_repo.py`：添加 `system_prompt_for_p2g_semantic_checker`、`task_prompt_for_p2g_semantic_checker`。

**新增工作流文件与注册**
- 新增 `dataflow_agent/workflow/wf_p2g_papergraph.py`：
  - 构建上述节点与条件边；为各节点准备 `pre_tool` 注入（如 enriched_description、semantic-layer JSON、op计数与分组摘要等）。
  - 集成 VLM 审计作为子流程（在 layout_checker 内部调用，默认模型 `gemini-2.5-flash-image-preview`）。
  - 在 `dataflow_agent/workflow/registry.py` 中 `register("p2g_papergraph", create_p2g_graph)`。

**Prompt 模板规划（prompts_repo.py）**
- 每个代理定义 `system_prompt_for_*` 与 `task_prompt_for_*`：
  - p2g_target_analyst：严格输出 `{ "enriched_description": "..." }`。
  - p2g_semantic_constructor：明确工具参数的 JSON Schema（引用 Pydantic 字段名），指导 LLM 仅调用 `save_semantic_layer`。
  - p2g_designer：声明 `StyleSheet` 的字段，指导生成 `globals` 与 `rules`；支持 `vlm_style_prompt` 与 `node_render_engine`。
  - p2g_semantic_checker：提供对比任务与 `submit_semantic_feedback` 工具格式，返回布尔与文字反馈。
  - 注：布局构建/布局检查为 Python 节点，不需要 LLM prompt，但可保留占位模板（防止引用报错）。

**脚本入口与使用**
- 新增 `script/run_p2g_papergraph.py`：
  - 读取 `--target`、`--language`、`--model`、`--api_url`、`--api_key`、`--out_dir`。
  - 构造 `DFState`，设置 `out_dir` 并写入 `state`；调用 `registry.get("p2g_papergraph")()`，执行工作流。
  - 输出：保存 `description_json_v0.4.json`（同 PaperGraph 结构）、`wireframe.png`、`final.png` 到 `out_dir`。

**渲染与输出（MVP）**
- 新增 `dataflow_agent/toolkits/papergraphtool/render.py`：
  - MVP：基于 `positions + style_sheet` 将线框增强（文本标注/颜色/线型），保存 `final.png`。
  - 后续：支持 `node_render_engine == vlm` 的资产拼合与字形处理。

**测试与验证计划**
- 单元测试：
  - `validators.py` 的几何检查（重叠/越界/端口连线校验）。
  - `layout.py` 的 fallback 布局生成（节点位置合理、边路径正交）。
  - `semantic.py`/`style.py` 的 schema 校验与写入。
- 集成测试：
  - 新增 `tests/test_p2g_papergraph_workflow.py`：输入若干 target（中文优先），验证生成的 `description_json` 含必要键，图像文件存在。
  - 复用现有 `tests/test_papergraph_vlm_gen.py` 的模式，检查 VLM 调用的基本通路（如配置正确、返回字符串）。

**涉及文件改动清单**
- 新增：
  - `dataflow_agent/papergraph/schema_v0_4.py`（Pydantic 模型）
  - `dataflow_agent/toolkits/papergraphtool/semantic.py`
  - `dataflow_agent/toolkits/papergraphtool/style.py`
  - `dataflow_agent/toolkits/papergraphtool/layout.py`
  - `dataflow_agent/toolkits/papergraphtool/wireframe.py`
  - `dataflow_agent/toolkits/papergraphtool/validators.py`
  - `dataflow_agent/toolkits/papergraphtool/render.py`
  - `dataflow_agent/workflow/wf_p2g_papergraph.py`
  - `script/run_p2g_papergraph.py`
- 更新：
  - `dataflow_agent/state.py`（增加 `papergraph` 相关字段）
  - `dataflow_agent/promptstemplates/prompts_repo.py`（新增 p2g 系列 prompt 模板）
  - `dataflow_agent/agentroles/p2g_target_analyst_agent.py`（完善实现）
  - `dataflow_agent/agentroles/p2g_semantic_constructor_agent.py`（绑定工具与实现）
  - `dataflow_agent/agentroles/p2g_layout_constructor_agent.py`（调用 Python 工具实现）
  - `dataflow_agent/agentroles/p2g_designer_agent.py`（绑定工具与实现）
  - `dataflow_agent/agentroles/p2g_layout_checker_agent.py`（程序化检查+线框绘制+VLM 审计）
  - `dataflow_agent/agentroles/p2g_semantic_checker_agent.py`（绑定工具与实现）
  - `dataflow_agent/workflow/registry.py`（注册新工作流）
  - `README.md`/`docs/guides/architecture.md`（补充使用说明，必要时）

**里程碑与时间安排（建议）**
- M1（基础链路畅通，2-3 天）：
  - 完成 State 扩展、Pydantic 模型与 semantic/style 工具；实现 target→semantic→designer 基本链路；编写 prompts。
- M2（布局与校验，2-3 天）：
  - 完成布局工具 fallback 算法、线框绘制与几何检查；集成 VLM 审计；实现 layout_checker 条件路由。
- M3（一致性与渲染，2 天）：
  - 完成 semantic_checker、MVP 渲染器；打通完整工作流与脚本入口；增加集成测试。
- M4（优化与扩展，持续）：
  - 接入 dagre/elk 正式库，完善风格规则与 VLM 资产融合；增强错误处理与可视化质量。

**已确认事项**
 - 1) 采用单个字典 `description_json`，其内部可嵌套多层字段以承载 v0.4 结构。
 - 2) 输出目录由入口脚本控制，并写入 `state`（同步至 `description_json.assets.out_dir`）。
 - 3) VLM 审计默认模型为 `gemini-2.5-flash-image-preview`，具体调用参考 `dataflow_agent/llm_callers/image.py`。
 - 4) 可使用 elk 与 dagre 进行自动布局（同时保留 fallback 算法）。
 - 5) 开发阶段统一使用中文提示词，便于调试与测试。

以上为详细的开发计划与文件改动清单，若有不确定处请先确认，我再据此开展实现。
