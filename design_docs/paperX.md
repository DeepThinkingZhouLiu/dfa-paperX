## 项目总需求：输入自然语言描述的target，输出与target匹配的科研绘图。

## papergraph项目架构
| 层级 | Agent | 核心职责 | 主要技术 |
| ---- | ---- | ---- | ---- |
| 分析 | PAA | 生成论文层次大纲、提炼标题/子标题 | GPT + langchain-text-splitter |
| 分析 | CEA | 抽取模型组件、数据流、损失、关键符号 | 少样本 IE Prompt / spaCy + “模型句”模板 |
| 设计 | VOA | 生成模块层次关系(输入→处理→输出)，绘图的顶层设计 |  |
| 设计 | DSP | 将实体关系转成图规范(JSON)：节点、边、group | JSON Schema, 自定义 DSL |
| 设计 | MDA | 定义模块类型(数据、算法、网络、结果)，确定模块尺寸、形状需求，颜色，甚至图像的旋转角度等等； |  |
| 设计 | PTA | 为每类节点生成 可重构 的生图提示（英文） | Prompt-programming rules |
| 设计 | IGA | 调用图标生成模型→返回 SVG/Iconfont，抠图；二次图像编辑等； | Stable Diffusion XL / DALL-E 3 + “vector” 检索 |
| 设计 | LA | 自动布局 & 交互调整，得有一个画布系统提供二次编辑； | dagre, elkjs, fabric.js |
| 评估 | VQA | 检查元素可读性、对齐度；评估指标 = { "清晰度": "文字是否清晰可读", "逻辑性": "流程是否符合逻辑", "美观度": "配色和布局是否协调", "完整性": "是否遗漏关键信息", "专业性": "是否符合学术规范" } | VLM+GPT |


## json格式的papergraph对象描述：
 CEA 生成的 PaperGraph 对象，PaperGraph需要能结构化的描述整个模型图：

**Nodes:**
- [id: node1, label: 'Input Data']
- [id: node2, label: 'Tokenizer']
- [id: node3, label: 'Transformer Encoder']
- [id: node4, label: 'MLP Head']
- [id: node5, label: 'Softmax Output']
- [id: node6, label: 'Cross-Entropy Loss']

**Edges:**
- [source: node1, target: node2]
- [source: node2, target: node3]
- [source: node3, target: node4]
- [source: node4, target: node5]
- [source: node5, target: node6]

{
  "layout_flow": "left-to-right",
  "groups": [
    {"group_id": "grp_input", "label": "Input Processing", "node_ids": ["node1", "node2"]},
    {"group_id": "grp_model", "label": "Core Model", "node_ids": ["node3", "node4"]},
    {"group_id": "grp_output", "label": "Output & Loss", "node_ids": ["node5", "node6"]}
  ]
}


## agent规划
1. VOA (Visual Outline Agent) - 视觉规划
如何建立VOAagent？用来规划一个图的绘制方案？或者一个模型图的箭头指向？数据流动？或者说分成几个模块？每个模块什么内容？

确定宏观布局 (layout_flow)
 这是最简单的一步，可以基于上一步的分析制定规则：
- 规则： 如果图的主干路径是清晰的线性、有向无环结构，则默认设置为 "left-to-right"。对于像 U-Net 这样具有明显垂直对称性的结构，可以考虑 "top-to-bottom" 并结合后续更复杂的布局指令。对于绝大多数论文模型图，"left-to-right" 是最安全、最常见的选择。
- 关系定义 (Relationship Definition): 分析边的类型，区分是“数据流”（data flow）、“控制流”（control flow）还是“依赖关系”（dependency）。

---
2. MDA (Module Decomposition Agent) - 视觉细化
核心任务：为每个模块（Node）定义具体的视觉属性（尺寸、形状、颜色等）。

## 项目分工
@潘泽伟 （我负责的部分）
- 负责agent部分搭建，目前的想法如上：
  - 布局，树形结构，比如2x3 ->ppt划分成 6 块，每一个块内部9等分；
  - agent根据paper的内容，以及上述布局，做视觉plan，每一块放什么？箭头以及图标的内容（详细的text2img提示词），大小，层级，旋转角度，透明度，位置，等属性；
  - 输出一个完整的详细布局json；
  - 升级：用户自定义图像+描述，也可以被视觉planer设计进去；（VLM）
@张彤 
- 负责 AutoBench，目的：整个pipline的输入其实是paper的文字内容，内容然后输出图像；
- AutoBench - 需要提供
  - paper的研究内容（框架）文本
  - 对应的框架图；
  - 每个图内部的详细描述，如上：“每一块放什么？箭头以及图标的内容（详细的text2img提示词），大小，层级，旋转角度，透明度，位置，等属性；”
- 目标，自动化生成bench，通过检索arxiv自动下载paper - AutoBench - 然后输出结构化数据；
@刘洲 
- 渲染系统，接口对接布局json，完成img的渲染+拖拉拽二次编辑；
- 视觉Eval+Rerun逻辑；


## 参考工作与启示（paper2poster）
- 内容选择与层次化：paper2poster 将论文内容分为层次化面板与关键信息块，并基于“重要度预算”在有限空间表达。对我们而言，可转化为：节点/群组的“重要度评分（importance）”与层次分组（groups）来指导布局与缩放。
- 版面/布局约束：paper2poster 使用多目标优化（可读性、对齐、一致性）求解布局。我们可在 `layout` 中暴露“流向 + 约束提示（hints）”，交给 elk/dagre 或后续 LA 进行求解。
- 可读性评估闭环：paper2poster 强调字体、对齐、间距的可读性指标。我们可将其抽象为 `evaluation` 的指标，与 VQA 闭环调用。
- 可编辑与迭代：保留结构化对象，支持人工微调再回写。我们以 PaperGraph 为单一事实源（single source of truth），通过增量补丁维护。


## 总体优化建议（针对你的框架）
- 语义层与视觉层解耦：CEA/DSP 只产出“语义图”（节点/边/群组与少量布局提示），VOA/MDA/LA 再叠加视觉与坐标；避免早期绑定视觉属性。
- 引入端口（ports）但设为可选：支持复杂数据流（并行、残差、条件、参数/梯度/控制），在需要时升级表达力，不阻塞 MVP。
- 加入溯源与可信度：每个节点/边记录 `provenance` 与 `confidence`，支撑 VQA 与人工修订。
- 重要度与抽象层级：为节点/群组标注 `importance`（0-1）与 `level`（层级），指导自动折叠/展开与版面资源分配。
- 统一最小可用子集（MVP）与扩展字段：先执行 MVP 字段，保留扩展字段不强制，便于渐进落地。


## PaperGraph JSON Schema（建议 v0.1）
说明：这是便于实现的“设计规范”，非正式 JSON Schema 文件。分为“核心（MVP）”与“扩展（可选）”。

### 顶层对象（MVP）
- version: string（例如 "0.1"）
- paper: { title?: string, arxiv_id?: string, doi?: string }
- graph: 语义图，见下
- layout: { flow: "left-to-right" | "right-to-left" | "top-to-bottom" | "bottom-to-top", algorithm?: "dagre" | "elk" | "manual", hints?: object }
- groups: 组定义（也可放入 graph 下；为简洁保留顶层）

### graph.nodes（MVP）
- 节点基础字段
  - id: string（必填，唯一）
  - label: string（必填，展示名）
  - type: string（建议枚举："data" | "module" | "layer" | "loss" | "metric" | "op" | "dataset" | "preprocess" | "postprocess"）
  - role?: string（建议枚举："input" | "process" | "output" | "aux" | "param" | "note"）
  - attrs?: object（字典，形状/维度/超参/框架等语义属性，如 {shape:"[B,T,D]", dtype:"fp32"}）
  - importance?: number（0-1，重要度预算）
  - level?: number（层级，0为顶层）
  - provenance?: { section?: string, span_refs?: [{start:number,end:number}], confidence?: number }

### graph.edges（MVP）
- 边基础字段
  - id: string（必填，唯一）
  - source: string（必填，源节点id）
  - target: string（必填，目标节点id）
  - type?: string（建议枚举："data" | "control" | "grad" | "param" | "dependency"）
  - label?: string
  - attrs?: object（如 {transform:"concat"} 或 {condition:"if training"}）
  - provenance?: { section?: string, span_refs?: [{start:number,end:number}], confidence?: number }

### groups（MVP）
- 组/模块聚合
  - group_id: string（必填）
  - label?: string
  - type?: string（建议："stage" | "module" | "repeat" | "conditional"）
  - node_ids: string[]（必填）
  - importance?: number（0-1）
  - layout_hint?: { direction?: "left-to-right" | "top-to-bottom", grid?: {rows?:number, cols?:number}, collapse?: boolean, rank?: number }

### 扩展字段（可选，预留）
- nodes.ports: [{ id, name?, dir: "in"|"out", semantics?: "data"|"grad"|"param"|"control", dtype?: string, shape?: string }]
- edges.source/target_port_id: string（与 ports 配合）
- tags: 节点/边/组的标签数组
- render: { nodes:[{node_id, shape?, color?, icon_uri?, rotation?, opacity?, zindex?}], edges:[{edge_id, style?, curvature?, arrow?}] }
- evaluation: { readability?: number, logic?: number, aesthetics?: number, completeness?: number, professionalism?: number, issues?: [{target_type:"node|edge|group", target_id:string, message:string, severity:"low|med|high"}] }

### 最小可用子集（MVP模板）
```
{
  "version": "0.1",
  "paper": {"title": "...", "arxiv_id": "..."},
  "layout": {"flow": "left-to-right", "algorithm": "dagre"},
  "graph": {
    "nodes": [
      {"id": "node1", "label": "Input Data", "type": "data", "role": "input"},
      {"id": "node2", "label": "Tokenizer", "type": "preprocess"},
      {"id": "node3", "label": "Transformer Encoder", "type": "layer"},
      {"id": "node4", "label": "MLP Head", "type": "layer"},
      {"id": "node5", "label": "Softmax Output", "type": "op", "role": "output"},
      {"id": "node6", "label": "Cross-Entropy Loss", "type": "loss"}
    ],
    "edges": [    gemini-2.5-flash nanobanana
      {"id":"e1","source":"node1","target":"node2","type":"data"，description: nl ; 方向：right -> left / up -> down -> },
      {"id":"e2","source":"node2","target":"node3","type":"data"},
      {"id":"e3","source":"node3","target":"node4","type":"data"},
      {"id":"e4","source":"node4","target":"node5","type":"data"},
      {"id":"e5","source":"node5","target":"node6","type":"dependency","label":"supervision"}
    ]
  },
  "groups": [
    {"group_id": "grp_input", "label": "Input Processing", "type":"stage", "node_ids": ["node1", "node2"], "importance": 0.6},
    {"group_id": "grp_model", "label": "Core Model", "type":"module", "node_ids": ["node3", "node4"], "importance": 1.0},
    {"group_id": "grp_output", "label": "Output & Loss", "type":"stage", "node_ids": ["node5", "node6"], "importance": 0.8}
  ]
}
```

### 可选端口扩展示例（非MVP）
```
{
  "graph": {
    "nodes": [
      {
        "id": "node3",
        "label": "Transformer Encoder",
        "type": "layer",
        "ports": [
          {"id":"p_in","dir":"in","semantics":"data","dtype":"fp32","shape":"[B,T,D]"},
          {"id":"p_out","dir":"out","semantics":"data","dtype":"fp32","shape":"[B,T,D]"}
        ]
      }
    ],
    "edges": [
      {"id":"e2","source":"node2","target":"node3","type":"data","target_port_id":"p_in"}
    ]
  }
}
```


## 生成流程与 Agent 职责（优化版）
- PAA（段落/结构纲要）：输出章节→给 CEA 做范围限定；可选产生“重要度初值”。
- CEA（抽取语义图）：
  - 步骤1：节点候选 + 类型/角色 → 置信度/溯源
  - 步骤2：边候选 + 关系类型（data/control/param/grad）→ 置信度/溯源
  - 步骤3（可选）：端口推断（并行/残差/条件）
  - 产物：graph.nodes/edges（仅语义字段），不含视觉参数
- DSP（装配 PaperGraph）：
  - 依据 CEA 产物，去重/一致性校验（孤立节点、环、类型冲突、重复边）
  - 建立 groups（stage/module/repeat），计算 `importance` 与 `level`
  - 写入 MVP 顶层与 layout.flow（默认 left-to-right）
- VOA（布局规划）：
  - 仅产出 `layout.algorithm` 与 `hints`，以及 groups 的 `layout_hint`
- MDA（视觉样式）：
  - 在 render 节点维度提供形状/颜色（扩展层，可延后）
- LA（坐标求解与二次编辑对接）：
  - 将 `layout + graph + groups` 送入 dagre/elk 求解；返回坐标（如后续加入 render/positions）
- VQA（评估闭环）：
  - 读取 `graph + layout`，输出 `evaluation` 与可操作修订项清单


## 质量控制与一致性校验
- ID 唯一性：nodes/edges/groups 的 id 均需全局唯一。
- 必填字段完整：nodes 的 id/label/type，edges 的 id/source/target。
- 类型合理性：例如 loss/metric 不应作为数据流的中转；control 边不参与主干层次化布局。
- 孤立元素检测：无入出边节点或无节点的组需标注或剔除。
- 溯源覆盖率：建议 ≥80% 的节点/边具备 provenance 信息。


## 下一步建议（短期落地）
- 确认本 v0.1 Schema 作为 MVP 产出物，先不开启端口/渲染/多视图。
- CEA → DSP 输出严格遵循本 Schema 的最小子集；LA 仅依赖 `layout.flow` 与基础 `groups`。
- 等 MVP 跑通后，再逐步启用：ports（表达复杂连接）、render（视觉控制）、evaluation（闭环）。


## Agent 架构与设计细化（对齐 v0.1 Schema）

说明：以下每个 Agent 都围绕 PaperGraph 的“语义优先”原则进行设计。统一数据契约：输入/输出均为 JSON 片段或补丁，最终由 DSP 汇总为顶层 PaperGraph。

### PAA（Paper/Paragraph Analysis Agent）
- 目标：构建论文的层次结构纲要与主题地图，限定抽取范围并提供初始重要度。
- 输入：原文段落/章节文本、元数据（title/abstract/sections）。
- 输出：
  - outline: [{section_id, title, start, end, keypoints[]}]，用于 CEA 的范围限定
  - topic_map: 关键词→段落映射（如 {"loss": [p12,p36]}）
  - importance_seed: 节点/组的初始重要度建议（到 label 层面，后由 DSP 对齐到节点）
- 核心方法：
  - 结构化分段：使用规则/LLM 提示识别 Methods/Results/Architecture 等章节
  - 主题抽取：关键词/术语与句法模式（"we propose"、"consists of"、"encoder-decoder"）
  - 重要度估计：依据摘要/引言中的贡献句、出现频次、图表引用密度
- 质量控制：章节覆盖率、主题召回、重要度与摘要一致性（简单打分）
- 失败回退：若章节不清晰，降级为引言+方法段落的粗纲要；importance_seed 留空
- 下游依赖：CEA 使用 outline 限定抽取窗口；DSP 用 importance_seed 初始化 `importance`

### CEA（Component Extraction Agent）
- 目标：从文本抽取语义图的“节点/边/类型/关系”，不掺杂视觉属性。
- 输入：PAA 的 outline 与论文正文片段
- 输出（遵循 v0.1 最小子集）：
  - nodes: [{id,label,type,role?,attrs?,provenance}]（必填 id/label/type）
  - edges: [{id,source,target,type?,label?,attrs?,provenance}]（必填 id/source/target）
- 核心方法：
  - 模型句模板 + 规则：如“X feeds into Y”、“we pass features to ...”、“we minimize cross-entropy”
  - 类型判定策略：
    - loss/metric 从“optimize/minimize/evaluate”语句抽取
    - data/preprocess 从“input/data/tokenize/normalize”等术语抽取
    - layer/module 从“encoder/decoder/mlp/convolution/attention”等术语抽取
  - 边构建：主干流依从论述顺序；并行/残差由“skip/concat/add/branch”等触发词识别
  - 溯源与置信度：每项附带 section/span_refs/confidence
- 质量控制：去重、孤立节点检测、类型冲突检查、环检测（按 type 规则）
- 失败回退：只产出主干线性数据流（input→process→output→loss）
- 上游依赖：PAA 的 outline 指定抽取窗口；下游 DSP 进行装配与分组

### DSP（Diagram Spec Producer）
- 目标：将 CEA 的碎片化抽取装配为一致的 PaperGraph（MVP），并进行规范化与校验。
- 输入：CEA 的 nodes/edges（含 provenance）与 PAA 的 importance_seed
- 输出：PaperGraph MVP（顶层 version/paper/layout/graph/groups）
- 核心方法：
  - 规范化：
    - ID 生成：`node_<slug>`，`edge_<a>_<b>_<k>`（去重防碰撞）
    - Label 清洗：大小写、缩写展开（如 "CE"→"Cross-Entropy Loss"）
    - Type/Role 对齐：强制遵循枚举，无效类型回退为 "module"
  - 分组策略：
    - stage：按章节/语义阶段划分（Input/Model/Output）
    - module：按复合结构（如 Encoder/Decoder）
    - repeat/conditional：按出现的循环/条件触发词
  - 重要度与层级：融合 importance_seed 与出现频次→写入 nodes/groups 的 `importance` 与 `level`
  - 布局默认：`layout.flow = left-to-right`，`algorithm = dagre`
  - 校验：唯一性、必填项、孤立元素、类型合理性
- 失败回退：若分组不可靠，仅输出单组 `grp_main` 覆盖所有节点
- 上下游：向 VOA 提供 `graph + groups + layout`（无视觉属性）

### VOA（Visual Outline Agent）
- 目标：产出布局算法选择与约束提示，指导 LA 求解坐标。
- 输入：DSP 的 PaperGraph（MVP）
- 输出：
  - layout.algorithm（dagre/elk/manual）
  - layout.hints：
    - ranks: 同级集合，如 [ [node1,node2], [node3] ]
    - direction_overrides: 局部方向偏好（如某子图 top-to-bottom）
    - group.layout_hint: 每组的 direction/grid/collapse/rank
- 核心方法：
  - 结构模式识别：U-Net/Encoder-Decoder/ResNet 等模式，选择合适方向与 ranks
  - 通用规则：
    - 主干：线性 DAG → left-to-right
    - 对称结构：top-to-bottom 并设置对齐约束
  - 约束提炼：减少边交叉、拉直主干、将 loss/metric 放在末端/侧边
- 质量控制：
  - 约束冲突检查（ranks 与 group.layout_hint 一致性）
  - 覆盖率：对主干节点都提供 rank 或 direction 提示
- 失败回退：只输出 algorithm=dagre 与空 hints

### MDA（Module Decomposition Agent）
- 目标：为节点/组定义视觉样式建议（可后置执行），不在 MVP 中强制。
- 输入：DSP 的 PaperGraph + VOA 的 hints
- 输出（扩展层 render 建议）：
  - nodes: shape/color/icon_hint（不写入坐标）
  - groups: 背景框/边框样式建议
- 核心方法：类型到形状/颜色映射（如 data=parallelogram, layer=rounded-rect, loss=hexagon；颜色按语义分组）
- 质量控制：色彩对比度、形状一致性、符号语义一致性
- 失败回退：仅给出类型到形状的默认映射，不生成色彩

### PTA（Prompt Template Agent）
- 目标：为 IGA 生成一致风格的图标/装饰性素材提示词。
- 输入：MDA 的 icon_hint 与节点 label/type/attrs
- 输出：assets.prompts: [{node_id, prompt, negative_prompt?, style_guideline?, seed?}]
- 核心方法：
-  - 风格约束：矢量、极简、线稿、统一配色（避免风格混乱）
  - 语义压缩：节点标签 + 语义属性转为英文 prompt（需可复用模板）
  - 负向提示：避免文字、复杂背景、透视畸变
- 质量控制：提示一致性、长度控制、禁止敏感内容
- 失败回退：使用类型到通用 icon 的模板提示

### IGA（Icon Generation Agent）
- 目标：根据 PTA 的提示生成或检索 SVG/PNG 素材，并写入 assets（扩展层）。
- 输入：PTA 的 prompts，MDA 的样式建议
- 输出：render.assets.icons: [{node_id, prompt, uri, license?, attribution?}]
- 核心方法：
  - 生成/检索双通道：优先 SVG 库检索（Iconify/Feather 等），其次模型生成
  - 轻后处理：统一描边/线宽/色板；必要时去底、转矢量
  - 资源管理：去重、缓存、许可信息记录
- 质量控制：
  - 一致性：线宽/配色统一
  - 许可：避免版权风险，记录来源与许可
- 失败回退：无可用素材时标注占位符，交由前端替换

### LA（Layout Agent）
- 目标：将 `graph + groups + layout.hints` 输送至布局引擎，产出“绝对坐标 + 边路由”的详细布局，直接写入最终 JSON 的渲染层以供下游绘图使用。
- 输入：DSP/VOA 产物，及（可选）CDA 的尺寸/端口偏好与最小尺寸建议。
- 输出（写入 schema 的 render 层，供直接绘制）：
  - render.nodes: `[{id,bbox:{x,y,width,height},rotation?,ports?}]`
  - render.edges: `[{id,points:[{x,y}...],route:"orthogonal"|"polyline",source_port?,target_port?,arrow?}]`
  - render.groups: `[{group_id,bbox:{x,y,width,height},padding?}]`
  - render.labels/assets: 元素标签、图标等的绝对位置（可选）
  - metrics（可选）：交叉数、重叠惩罚、主干直线度等布局评分
- 核心方法：
  - 可插拔后端：dagre/elk/启发式。应用 ranks/direction/grid 等约束，支持两阶段（粗排→细排）
  - 路由优化：正交/折线优先，减少交叉，保持主干直线；跨 chunk 边在边界处设中转点
- 质量控制：
  - 几何合规：坐标在画布内、bbox 正数、端口侧向正确、无明显重叠
  - 布局评分：交叉数、主干曲率、层级一致性；输出 metrics 便于回归测试
- 失败回退：
  - 命中时限/预算时，退化为“拓扑顺序 + 等间距”的线性布置并产出合法坐标

### VQA（Visual QA Agent）
- 目标：基于 PaperGraph 与（可选）渲染结果评估质量并提出可操作修订。
- 输入：PaperGraph（MVP）与（可选）positions/渲染截图
- 输出：evaluation（扩展层）：
  - 指标：readability/logic/aesthetics/completeness/professionalism（0-1）
  - issues: [{target_type, target_id, message, severity}]
  - fixes: 建议补丁（如调整 group.layout_hint 或补充 provenance）
- 核心方法：
  - 文本一致性：label/type 与上下文是否匹配
  - 逻辑性：是否遗漏 loss/输入/输出；数据流是否闭合
  - 可读性：布局 hints 是否合理（如主干是否过度弯曲）
- 失败回退：只给出文本一致性与逻辑性检查

### 多 Agent 编排与数据契约
- 流程管道：PAA → CEA → DSP → VOA →（MDA/PTA/IGA 可并行/后置）→ LA → VQA
- 数据契约：
  - CEA→DSP：nodes/edges（MVP），JSON 片段
  - DSP→VOA：graph+groups+layout（无视觉属性）
  - VOA→LA：layout.algorithm+hints+groups.layout_hint
  - MDA/PTA/IGA：仅写扩展层 render/assets，不影响语义层
- 增量更新：使用补丁（patch）形式而非全量覆盖；DSP 作为单一事实源协调合并
- 版本与溯源：每次管道运行生成 run_id，PaperGraph.version 递增；provenance 记录 agent 名与时间戳

## IconAgent 子代理（Target→Layout 全流程）
本节定义以“自然语言 target + 网格布局”为输入，直接产出“包含绝对坐标的详细布局 JSON”的子代理编排。与上文 PAA/CEA/DSP/VOA/MDA/LA/VQA 保持数据契约一致，并强调 LA 独立、可替换。

### Input Normalizer（输入标准化）
- 目标：统一输入 target 与网格定义，计算 chunk 的绝对占位框（bbox）。
- 输入：
  - target：自然语言描述、约束与风格提示
  - canvas：`{width,height,unit,dpi?,origin:"top-left"}`
  - grid：`{rows,cols,margin:{l,t,r,b},gutter:{row,col},cell?}`
  - chunks：`[{chunk_id,grid_area:{row,col,rowspan?,colspan?}}]`
- 输出：
  - chunks：补全 `bbox:{x,y,width,height}` 与 `z?`
  - constraints：来自输入的硬/软约束（方向、必须包含/位置等）

### TAA（Target Analysis Agent）
- 目标：理解 target，给出简要语义纲要与实体/关系草图，形成“抽取就绪”的输入。
- 输入：target、Input Normalizer 的 constraints
- 输出：
  - target_summary：要点、主干流程与关键术语
  - entities：`[{id,label,type}]`
  - relations：`[{source,target,type}]`
  - style_cues?：风格/形状/颜色偏好（可选）
  - constraints（继承/细化）：方向/必须包含/对称性/数量等

### CPA（Chunk Planner Agent）
- 目标：将语义块映射到 chunk，给出“每个 chunk 放什么”的粗粒度计划与布局提示。
- 输入：TAA 输出、Input Normalizer 的 chunks
- 输出：
  - chunk_plan：`[{chunk_id,role,content_nl,priority}]`
  - group_plan：`[{group_id,label,node_hints?}]`
  - layout.hints（初稿）：`flow?,ranks?,direction_overrides?,group.layout_hint?`

### CCA（Chunk Content Agent）
- 目标：把 CPA 的 NL 粗计划装配为 PaperGraph MVP（语义层）。
- 输入：CPA 输出
- 输出（MVP）：
  - graph.nodes：`[{id,label,type,group_id?,importance?}]`
  - graph.edges：`[{id,source,target,type?,label?}]`
  - groups：`[{group_id,label,node_ids[]}]`
  - mapping（扩展层）：`chunk_nodes:{[chunk_id]: string[]}` 将节点归属到 chunk
  - layout（延续）：`{flow,hints}`（若 CPA 提供则继承/细化）

### CDA（Chunk Design Agent）
- 目标：对节点/组提供视觉风格与尺寸/端口偏好，为布局求解提供必要约束。
- 输入：CCA 输出、VOA 的方向/层级提示（如已存在）
- 输出：
  - style_suggestions：`nodes[{id,shape,color,opacity,rotation?,min_w?,min_h?,port_pref?}],groups[...]`
  - layout.hints（升级）：`ranks,group.layout_hint={direction|grid|collapse},direction_overrides`

### LA（独立布局求解 Agent）
- 目标：根据 `graph + groups + layout.hints + chunk.bbox + style_suggestions` 求解绝对坐标与边路由，写入 render 层。
- 输入：CCA/CDA/VOA 产出与 Input Normalizer 的 chunks（含 bbox）
- 输出：渲染层 `render.nodes/edges/groups/labels/assets` 与 `metrics`
- 说明：为保证可替换与可测，LA 为独立结点；支持“两阶段布局”（粗排→细排）。

### SCA（Schema Checker Agent）
- 目标：对语义与渲染层进行结构与几何校验，确保 JSON 可被下游绘制。
- 输入：LA 完整产物
- 输出：
  - pass/fail + issues：`[{target_type,target_id,message,severity}]`
  - geometry_checks：坐标在画布内、bbox 正数、端口/路由侧向正确、引用完整、无非法重叠（按阈值）

### TCA（Target Challenge Agent）
- 目标：将最终 JSON 与原始 target 对齐，检查一致性并输出差距（gap）。
- 输入：target、SCA 通过的 JSON
- 输出：
  - score（0-1）
  - gaps：`[{kind, target_id?, message, suggestion_patch?}]`（如缺失实体/关系、方向/位置/数量/风格不符等）

### SRA（Schema Rewriter Agent）
- 目标：根据 SCA 的 schema/几何错误，生成最小补丁修复。
- 输入：SCA 的 issues、当前 JSON
- 输出：补丁（patch）片段，交由 Orchestrator/DSP 合并

### CRA（Consistency Rewriter Agent）
- 目标：根据 TCA 的 gaps 优化 JSON（尽量保持语义不变，做布局/风格/轻量内容调整）。
- 输入：TCA 的 gaps、当前 JSON
- 输出：补丁（patch）片段；回流 SCA→TCA 复核，直到达成阈值或耗尽预算

### 编排与终止条件（IconAgent 流程）
- 主线：Input Normalizer → TAA → CPA → CCA → VOA → CDA → LA → SCA → TCA → 输出
- 回路：
  - SCA 失败 → SRA → SCA（N 次上限）
  - TCA 未达阈值 → CRA → SCA → TCA（M 次上限）
- 终止：SCA 通过且 TCA 得分≥阈值（或 gaps 全清），或到达重试预算选最佳候选

### 数据契约补充（面向绝对坐标）
- 语义层：沿用 PaperGraph MVP（`graph/nodes/edges/groups/layout`）作为单一事实源。
- 渲染层（由 LA 写入）：
  - nodes：`{id,bbox:{x,y,width,height},rotation?,ports?,style?}`
  - edges：`{id,points:[{x,y}],route,source_port?,target_port?,arrow?,style?}`
  - groups：`{group_id,bbox,padding?,style?}`
  - labels/assets/z_order（可选）
- 网格与 chunk：
  - canvas/grid：画布与网格参数
  - chunks：`{chunk_id,grid_area,bbox,z?}`；`mapping.chunk_nodes` 绑定节点归属
- 补丁与版本：补丁优先；记录 run_id、provenance、metrics 便于追踪

### 运行时与观察性
- 日志：每个 Agent 输出输入摘要、产出统计（节点/边数）、置信度分布、错误列表
- 指标：抽取召回/精度估计（启发式）、布局评分、评估分项
- 可复现性：保存 PAA outline 与 CEA 抽取窗口；记录 LLM 模型与提示摘要
