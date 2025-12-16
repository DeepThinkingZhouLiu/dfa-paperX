# --------------------------------------------------------------------------- #
# 0. 通用数据清洗 / 分析                                                         #
# --------------------------------------------------------------------------- #
class GenericDataAnalysis:
    system_prompt_for_data_cleaning_and_analysis = """
[ROLE]
数据清洗与分析专家（Data Analysis Expert）
职责：
1. 严格遵循JSON格式规范
2. 保持历史数据结构一致性
3. 禁止任何形式的注释或解释性文字

[TASK]
1. 根据历史数据结构处理当前请求
2. 确保输出JSON包含且仅包含以下要素：
   - 与历史数据相同的键名
   - 无新增键值对
   - 无代码/文本注释
3. 使用指定语言({language})响应

[INPUT FORMAT]
{
  "history": {history_data},
  "question": "{user_question}",
  "language": "{target_language}"
}

[OUTPUT RULES]
1. 必须包含的要素：
   - 完全移除<!-- -->、//等注释标记
2. 严格禁止的要素：
   - 任何新增的JSON键（即使逻辑上合理）
   - 代码注释（包括#、//、/* */等形式）
   - 非请求语言的内容
3. 错误处理：
   - 如遇无法满足的请求，返回：{"error":"invalid_request"}
"""

# --------------------------------------------------------------------------- #
# 1. 知识库摘要                                                                 #
# --------------------------------------------------------------------------- #
class KnowledgeBaseSummary:
    task_prompt_for_summarize = """
Knowledge base content:
{content}

Tasks for summarizing the knowledge base:
- Generate a detailed summary of this knowledge base as much as possible.
- How many data records are there?
- What is the domain distribution of the data (such as computer, technology, medical, law, etc.)?
- What is the language type of the data (single language/multiple languages)?
- Is the data structured (such as tables, key-value pairs) or unstructured (pure text)? What are the respective proportions?
- Does the data contain sensitive information (such as personal privacy, business secrets)? What is the proportion?
- Could you provide the topic coherence score of the knowledge base content, the relationships and their intensities between different concepts or entities, and the sentiment distribution?
"""

    system_prompt_for_KBSummary = """
You are a professional data analyst. Please generate a structured JSON report according to the user's question.
The fields are as follows:
  - summary: Comprehensive analysis summary
  - total_records: Total number of records (with growth trend analysis)
  - domain_distribution: Dictionary of domain distribution (e.g., {{"Technology": 0.3, "Medical": 0.2}})
  - language_types: List of language types with proportions
  - data_structure: Data structuring type (e.g., {{"Structured": 40%, "Unstructured": 60%}})
  - has_sensitive_info: Whether contains sensitive information with risk level
  - content_analysis: {{
      "key_topics": ["topic1", "topic2"],
      "entity_linkage": {{"Python->AI": 15, "Java->Enterprise": 20}},
      "semantic_density": "high/medium/low"
    }}
"""

# --------------------------------------------------------------------------- #
# 2. 推理 / 推荐流水线                                                         #
# --------------------------------------------------------------------------- #
class RecommendationInferencePipeline:
    system_prompt_for_recommendation_inference_pipeline = """
You are a data processing expert. Please generate a structured JSON report according to the user's question.
Based on the user's knowledge base data, you will recommend a suitable data processing pipeline composed of multiple processing nodes.
You need to analyze the user's data types and content, then recommend an appropriate pipeline accordingly.
"""

    task_prompt_for_recommendation_inference_pipeline = """
[ROLE] You are a data governance workflow recommendation system.
You need to automatically select appropriate operator nodes and assemble a complete data processing pipeline based on contextual information.

[INPUT]
You will receive the following information:
The requirements that the pipeline must meet:
========
{target}
========
Sample data information:
========
{sample}
========
The list of available operators for each data type:
============================
{operator}
============================

[key rules]
1. Follow Execution Order:
  Data generation must occur before data extraction
  Data extraction must occur before data validation
  Correct order: Filter → Generate → Extract → Validate
  Incorrect order: Filter → Extract → Generate ❌
2 .Validate Data Availability:

  Check sample data to confirm which fields already exist
  If an operator requires field "X" but it's not present in the sample data, ensure a preceding operator creates it

[Common Error Patterns to Avoid]
❌ Incorrect Example: ["FilterData", "ExtractAnswer", "GenerateAnswer"]
Problem: Attempting to extract the answer before it is generated

✅ Correct Example: ["FilterData", "GenerateAnswer", "ExtractAnswer"]
Reason: Generate first, then extract

❌ Incorrect Example: ["ValidateAnswer", "GenerateAnswer"]
Problem: Validating an answer that does not exist yet

✅ Correct Example: ["GenerateAnswer", "ExtractAnswer", "ValidateAnswer"]
Reason: Complete data flow


[OUTPUT RULES]
1. Please select suitable operator nodes for each type and return them in the following JSON format:
{{
  "ops": ["OperatorA", "OperatorB", "OperatorC"],
  "reason": "State your reasoning here. For example: this process involves multi-level data preprocessing and quality filtering, sequentially performing language filtering, format standardization, noise removal, privacy protection, length and structure optimization, as well as symbol and special character handling to ensure the text content is standardized, rich, and compliant."
}}
2 Only the names of the operators are needed.
3. Please verify whether the selected operators and their order fully meet the requirements specified in {target}.
[Question]
Based on the above rules, what pipeline should be recommended???
"""

# --------------------------------------------------------------------------- #
# 3. 数据内容分类                                                               #
# --------------------------------------------------------------------------- #
class DataContentClassification:
    system_prompt_for_data_content_classification = """
You are a data content analysis expert. You can help me classify my sampled data content.
"""

    task_prompt_for_data_content_classification = """
Please categorize the sampled information below.
=====================================================
{local_tool_for_sample}
=====================================================
Return a content classification result.
These sampled contents can only belong to the following categories:
{local_tool_for_get_categories}

Return the result in JSON format, for example:
{{"category": "Default"}}
"""

# --------------------------------------------------------------------------- #
# 4. 任务规划器                                                                 #
# --------------------------------------------------------------------------- #
class Planer:
    system_prompt_for_planer = """
[ROLE] Task Decomposition Specialist
- You are an expert in breaking down complex queries into actionable subtasks
- You specialize in creating structured workflows for data governance pipelines

[TASK] Decompose User Query into Subtasks
1. Analyze the user's query to identify core objectives
2. Break down into logical subtasks with dependencies
3. Generate detailed JSON output with:
   - Task definitions
   - Associated prompts
   - Parameter requirements
   - Dependency relationships

[INPUT FORMAT] Natural language query about data governance pipelines

[OUTPUT RULES]
1. Return only a JSON object matching the exact specified structure
2. Prohibited elements:
   - Free-form text explanations
   - Markdown formatting
   - Any content outside the JSON structure

[EXAMPLE]
```json
{{
  "tasks": [
    {{
      "name": "data_content_analysis",
      "description": "Perform comprehensive analysis of dataset content characteristics including data types, patterns, and anomalies",
      "system_template": "system_prompt_data_analyst",
      "task_template": "task_prompt_content_analysis",
      "param_funcs": ["raw_dataset"],
      "depends_on": []
    }},
    {{
      "name": "pipeline_architecture_design",
      "description": "Design pipeline structure by extracting required fields from pre-processed data",
      "system_template": "system_prompt_pipeline_architect",
      "task_template": "task_prompt_pipeline_design",
      "param_funcs": ["content_analysis_result", "governance_rules"],
      "depends_on": [0],
      "is_result_process": true,
      "task_result_processor": "pipeline_assembler",
      "use_pre_task_result": true
    }}
  ],
  "prompts": [
    {{"system_prompt_data_analyst": "You are a data processing expert. Analyze the RAW dataset and return a full analysis report."}},
    {{"task_prompt_content_analysis": "Analyze the raw dataset: {{raw_dataset}} Generate a report including: 1. Data types 2. Quality metrics 3. Anomaly flags. Example output: {{\\\"data_types\\\": {{\\\"text\\\": 85%, \\\"numeric\\\": 15%}}, \\\"quality_score\\\": 0.92, \\\"anomalies\\\": []}}"}},
    {{"system_prompt_pipeline_architect": "You extract pipeline configuration parameters from pre-existing data objects."}},
    {{"task_prompt_pipeline_design": "From the complete analysis result: {{content_analysis_result}} and governance rules: {{governance_rules}}, extract ONLY the following: 1. Required operator types 2. Processing sequence 3. Compliance checkpoints. Example output: {{\\\"operators\\\": [\\\"text_cleaner\\\"], \\\"sequence\\\": [\\\"clean→validate\\\"], \\\"checks\\\": [\\\"GDPR\\\"]}}"}}
  ]
}}
"""
    task_prompt_for_planer = """
When designing the task chain, in addition to breaking down and arranging the tasks logically,
you must also carefully review the following available tool information: {tools_info}.

Please assess whether these tools (such as local_tool_for_get_weather) can help accomplish any of the tasks.
If a tool can support a particular task, include the tool's name in the "param_funcs" field of the corresponding task JSON definition, for example:
"param_funcs": ["local_tool_for_get_weather"].

For each task, the 'param_funcs' field should list the required input data objects for that task.
These can be:
 - Output objects produced by previous tasks (e.g., "content_analysis_result", which contains all the information generated by the content analysis step)
 - Results returned by invoked tools.

"param_funcs" are not parameter names or function names, but data objects or results containing extensive and structured information required for the current task.
For example:
{{ "task_prompt_for_pipeline_design": "根据天气信息：{{local_tool_for_get_weather}}中获取武汉的天气信息，返回json格式!!"] }}

Please ensure the task chain is structured logically, and each task utilizes the most appropriate tools whenever possible.
Tool parameters must be filled in accurately; do not overlook any available tools.
The generated JSON structure should be clear and easy to process.

User requirements: {query}.
"""

# --------------------------------------------------------------------------- #
# 5. 会话意图分析                                                               #
# --------------------------------------------------------------------------- #
class ChatIntent:
    system_prompt_for_chat = """
You are an intent analysis robot. You need to analyze the specified intent from the conversation.
"""

    task_prompt_for_chat = """
[ROLE] You are an intent analysis robot. You need to identify the user's explicit intent from the conversation
and analyze the user's data processing requirements based on the conversation content.

[TASK]
1. Only when the user explicitly mentions the need for a 'recommendation' in their request
   (such as using words like 'recommend', 'recommend a pipeline', 'I want to process this data with a dataflow pipeline', etc.),
   should you set need_recommendation to true.
2. Only when the user explicitly mentions the need to 'write an operator' in their request
   (such as using phrases like 'want an operator with xxx functionality/to accomplish xxx task', etc.),
   should you set need_write_operator to true.
3. You need to summarize the user's processing requirements in detail based on the conversation history,
   and in all cases, provide a natural language response as the value of 'assistant_reply'.

[INPUT CONTENT]
Conversation history:
{history}

Current user request:
{target}

[OUTPUT RULES]
1. Only reply in the specified JSON format.
2. Do not output anything except JSON.

[EXAMPLE]
{{
 "need_recommendation": true,
 "need_write_operator": true,
 "assistant_reply": "I will recommend a suitable data processing pipeline based on your needs.",
 "reason": "The user explicitly requested a recommendation, wants to process data related to mathematics, and hopes to generate pseudo-answers.",
 "purpose": "According to the conversation history, the user does not need a deduplication operator, hopes to generate pseudo-answers, and wants to keep the number of operators at 3."
}}
"""

# --------------------------------------------------------------------------- #
# 6. Pipeline Refine                                            #
# --------------------------------------------------------------------------- #
class PipelineRefinePrompts:
    # 步骤1：目标与现状分析
    system_prompt_for_refine_target_analyzer = """
    You are an intent analysis robot. You need to analyze the specified intent from the conversation.
"""
    task_prompt_for_refine_target_analyzer = """
[ROLE] 
You are an intent analysis robot. You need to identify the user's explicit intent from the conversation
and analyze the user's data processing pipeline refinement requirements based on the conversation content and current pipeline content.

[TASK] 
1. 识别用户需要进行的操作：操作集为： add|remove|replace, 用户需求可能是操作集中的一种或多种
2. Add :Only when the user explicitly mentions the need for 'add operator' in their request
(such as using words like 'add', 'increase', 'I need add xxx operator in my data operator pipeline', etc.),
add 操作包括多种情况, 例如在pipeline的开头/结尾新增节点，或在两个节点之间插入节点等
3. Remove: Only when the user explicitly mentions the need for 'remove operator' in their request
(such as using words like 'remove', 'delete', 'I need remove xxx operator in my data operator pipeline', etc.),
remove 操作包括多种情况, 例如删除pipeline中的某个节点或多个节点, 需要将被删除节点的前后节点连接起来
4. Replace: Only when the user explicitly mentions the need for 'exchange operator' in their request
(such as using words like 'exchange', 'replace', 'I need exchange xxx operator in my data operator pipeline', etc.),
exchange 操作包括多种情况, 例如将pipeline中的某个节点替换为另一个节点, 或交换现有pipeline中两个节点的位置
5. 你需要根据用户需求和当前pipeline内容, 结合上述操作集, 生成一个规范的意图JSON对象.

[INPUT]
User target: {purpose}
Current pipeline content: {pipeline_code}
Pipeline nodes summary: {pipeline_nodes_summary}

[OUTPUT]
1. You should output the refine needed based on the user target and current pipeline content as a JSON, including:
need_add: true|false
add_reasons: "Reasons for adding an operator"

need_remove: true|false
remove_reasons: "Reasons for removing an operator"

need_replace: true|false
replace_reasons: "Reasons for replacing an operator"

needed_operators_desc:describe in detail the operators needed for each operation based on user's purpose.


[OUTPUT RULES]
1. Only reply in the specified JSON format.
2. Do not output anything except JSON.

[EXAMPLE]
{{
"need_add": true,
"add_reasons": "The user explicitly requested to add an operator and an data augmentation opearator, and the current pipeline lacks a data cleaning step.",
"need_remove": false,
"need_replace": true,
"replace_reasons": "The user wants to replace the current data validation operator with a data translation operator.",
"needed_operators_desc": {
    "add_1": User need a data cleaning operator to ensure data quality before further processing.
    "add_2": User need add a data augmentaion operator.
    "replace": User want to replace the data validation operator with a data translation operator, so the User need a data translation operator.
}
}}
"""

    # 步骤2：修改计划
    system_prompt_for_refine_planner = """
You are a data processing pipeline modification planner. Based on user's intent and current pipeline information, design a precise modification plan.
"""

    task_prompt_for_refine_planner = """
[TASK]
1.你需要充分理解用户的intent和当前pipeline内容, 结合用户的意图和当前pipeline content, 设计一个精准的修改计划, pipeline为json格式.
2.你给出的修改计划需要包括：操作类型(操作类型必须属于操作集）、操作对象、操作位置等关键信息, 以便后续步骤进行具体的JSON修改.
3.操作集为: add|remove|replace, 用户需求可能是操作集中的一种或多种, 可能涉及一个或多个节点; add 操作包括多种情况, 例如在pipeline的开头/结尾新增节点，或在两个节点之间插入节点等；
remove 操作包括多种情况, 例如删除pipeline中的某个节点或多个节点, 需要将被删除节点的前后节点连接起来;
replace 操作包括多种情况, 例如将pipeline中的某个节点替换为另一个节点, 或交换现有pipeline中两个节点的位置;

[INPUT]
Intent: {intent}  #这里的intent是上一步骤1的json格式输出结果
Current pipeline content: {pipeline_code}
Pipeline nodes summary: {pipeline_nodes_summary}
matched_op: {matched_op}  
# matched_op的格式为：{
    "add_1": op_name (such as "data_cleaner")
    "add_2": "data_augmenter",
    "replace": "data_translator"
}

[OUTPUT RULES]
1. Only reply in the specified JSON format.
2. Do not output anything except JSON.

[EXAMPLE]
{{
"modification_plan": [
    {{
        "operation": "add",
        "operator_name": "data_cleaner",  # 新增节点名称
        "position": {{"before": "node_1"}}  # 在节点node_1之前添加
    }},
    {{
        "operation": "remove",
        "operator_id": "node_3"  # 删除节点node_3
    }},
    {{
        "operation": "replace",
        "old_operator_id": "node_5",  # 将节点node_5替换为新的节点
        "new_operator_name": "data_translator",
]
}}

"""

    # 步骤3：JSON 直接修改（LLM产出完整JSON）
    system_prompt_for_json_pipeline_refiner = """
You are a JSON data processing pipeline refiner. Modify the given pipeline JSON according to the plan and optional operator context.
"""
    task_prompt_for_json_pipeline_refiner = """

[TASK]
1.你需要先充分理解当前的pipeline content的格式和内容，和Modification plan.
2.你需要仔细阅读并理解每一个子操作对应的算子的code，分析算子中的一些config参数及其含义, 因为修改JSON pipeline时需要写入对应算子的config参数.
3.在修改pipeline content时，需要严格遵守JSON格式规范，保持历史数据结构一致性，禁止任何形式的注释或解释性文字.
4.你在修改pipeline content时, 需要特别注意图结构的正确性, 例如节点之间的连接关系, 确保修改后的pipeline是一个有效的有向无环图(DAG).增加算子节点或移除算子节点时，需要考虑其前后节点的连接关系.
5.在生成的pipeline content中，绝对不能存在孤立节点或断开的子图, 必须确保所有节点都正确连接, 并且整个图结构保持连贯和完整.


[INPUT]
Current pipeline JSON: {pipeline_json}
Modification plan: {modification_plan}
Operator context (op_context can be a list or dict keyed by step_id): {op_context}
Output the UPDATED pipeline JSON ONLY.
"""

# ---------------- Overrides: Harmonize prompts for multi-suboperation RAG and param names ---------------- #
# 1) Target analyzer: produce sub-operations list with step_id, compatible with downstream RAG per step
PipelineRefinePrompts.system_prompt_for_refine_target_analyzer = """
You are a pipeline intent analyzer. Based on the user target and current pipeline summary, extract a normalized intent JSON. Only output JSON.
"""
PipelineRefinePrompts.task_prompt_for_refine_target_analyzer = """
[ROLE]
Analyze the user's intent and the current pipeline. Decide whether add/remove/replace is needed and decompose into sub-operations.

[INPUT]
User target: {purpose}
Pipeline nodes summary: {pipeline_nodes_summary}
Current pipeline content: {pipeline_code}

[OUTPUT]
Return ONLY a JSON object with fields:
{
  "need_add": true|false,
  "add_reasons": "...",
  "need_remove": true|false,
  "remove_reasons": "...",
  "need_replace": true|false,
  "replace_reasons": "...",
  "needed_operators_desc": [
    {
      "step_id": "add_1|remove_1|replace_1|...",
      "action": "add|remove|replace",
      "desc": "Describe what the operator should do or which node to act on.",
      "position_hint": {"between": ["nodeA","nodeB"], "before": "nodeX", "after": "nodeY", "start": true, "end": true, "target": "nodeZ"}
    }
  ]
}

[RULES]
- step_id 必须唯一，用于后续逐步RAG与计划对齐。
- Only JSON. Do not output anything else.
"""

# 2) Planner: consume intent (with needed_operators_desc) and produce modification_plan aligning step_id
PipelineRefinePrompts.system_prompt_for_refine_planner = """
You are a pipeline modification planner. Design a precise modification_plan from the intent and current pipeline summary. Only output JSON.
"""
PipelineRefinePrompts.task_prompt_for_refine_planner = """
[TASK]
Using the intent.needed_operators_desc (each with step_id/action/desc/position_hint) and the current pipeline nodes summary, generate a normalized modification_plan.
If operator contexts are provided (per step_id), leverage them to decide precise node type, ports (input_key/output_key), and initial config.

[INPUT]
Intent: {intent}
Pipeline nodes summary: {pipeline_nodes_summary}
Operator context (optional): {op_context}

[OUTPUT]
Return ONLY a JSON object with field:
{
  "modification_plan": [
    {
      "step_id": "same as intent",
      "op": "add|remove|replace|insert_between|insert_before|insert_after|insert_at_start|insert_at_end",
      "position": {"a": "nodeX", "b": "nodeY", "target": "nodeZ", "before": "nodeA", "after": "nodeB", "start": false, "end": false},
      "new_node": {"name": "optional", "type": "optional", "config": {"run": {"input_key": "...", "output_key": "..."}, "init": {}}}
    }
  ]
}

[RULES]
- 保持 step_id 与 intent 对齐，便于后续使用逐步RAG匹配到的算子上下文。
- 位置说明必须明确（between/before/after/start/end/target 选其一或组合），以确保可执行。
- Only JSON.
"""

# 3) Refiner: align input names and allow op_context per step_id
PipelineRefinePrompts.system_prompt_for_json_pipeline_refiner = """
You are a JSON pipeline refiner. Modify the given pipeline JSON according to the modification_plan and optional operator contexts.
Only output the full updated pipeline JSON object with keys {"nodes","edges"}. No comments.
Rules:
- For remove: delete the node and its edges; then connect all predecessors to all successors to keep connectivity (DAG, no cycles).
- For insert_between(a,b): replace edge a→b with a→new and new→b.
- For insert_before/after/start/end: adjust edges accordingly and keep graph connected.
- For add without explicit position: append at end and wire all terminal nodes to the new node using provided ports.
- Edge fields: {"source","target","source_port","target_port"}.
- Node fields: {"id","name","type","config":{"run":{...},"init":{...}}}.
 - Always apply ALL steps in modification_plan sequentially. Do not skip steps.
 - When removing a node, reconnect every predecessor to every successor using the correct ports.
 - Ensure newly created node ids are unique.
"""
PipelineRefinePrompts.task_prompt_for_json_pipeline_refiner = """
[TASK]
1. 理解当前 pipeline_json 与 modification_plan。
2. 如 op_context 提供了针对某个 step_id 的 operator 代码/端口/配置提示，请据此填写新节点的 type、config.run(input_key/output_key) 与必要的 init。
3. 严格保持 JSON 结构、DAG 连通性与有向无环属性，禁止输出注释或解释性文字。

[INPUT]
Current pipeline JSON: {pipeline_json}
Modification plan: {modification_plan}
Operator context (op_context can be a list or a dict keyed by step_id): {op_context}

Output the UPDATED pipeline JSON ONLY.
"""


# --------------------------------------------------------------------------- #
# 6. 执行推荐流水线                                                             #
# --------------------------------------------------------------------------- #
class ExecuteRecommendedPipeline:
    system_prompt_for_execute_the_recommended_pipeline = """
[ROLE] You are a pipeline execution analysis robot.
You can analyze and summarize conclusions based on the shell information or pipeline processing results and operator information provided to you, and describe the entire process.

[output]
1. Only return the result in JSON format, for example: {{"result": xxxx}}
2. Do not provide any additional information, such as comments or extra keys.
"""

    task_prompt_for_execute_the_recommended_pipeline = """
local_tool_for_execute_the_recommended_pipeline: {local_tool_for_execute_the_recommended_pipeline}

Strictly return content in JSON format, without any comments or markdown information.
The result should contain two parts:
{{'result': xxx, 'code': directly return the content from local_tool_for_execute_the_recommended_pipeline.}}
"""

# --------------------------------------------------------------------------- #
# 7. 代码执行 / 生成 / 调试                                                     #
# --------------------------------------------------------------------------- #
class Executioner:
    system_prompt_for_executioner = "You are an expert in Python programming."

    task_prompt_for_executioner = """
[ROLE] You are a Python code expert.
[TASK] Based on the content of {task_info}, please write the function code named {function_name}, and return it in JSON format.

[OUTPUT RULES]
1. Only reply with the expected content;
2. Do not include any extra content, comments, or new keys;
3. Any missing data or information should be exposed as function parameters!
4. In the code section, include 'if __name__ == "__main__":' and provide function test cases for direct invocation;
5. Do not include code like print('') for exceptions or errors--I want errors and exceptions to be exposed directly;

[example]
{{
 'function_name': 'func1',
 'description': 'This function is used for...',
 'parameters': [
   {{ 'name': 'param1', 'type': 'int', 'description': 'Description for parameter 1' }},
   {{ 'name': 'param2', 'type': 'string', 'description': 'Description for parameter 2' }}
 ],
 'return': {{ 'type': 'str', 'description': 'Description of the return value' }},
 'code': 'def func1(param1, param2): ... '
}}
"""

    task_prompt_for_executioner_with_dep = """
[ROLE] 你是一个精通Python的代码专家
[TASK] 请根据下列任务需求与前置任务的输出，编写名为{function_name}的函数代码，并以Json的形式返回，
如果要用到前置任务的输出，
- 形参名字根据 {dep_param_funcs} 来定义；
- 如果需要额外参数，直接另外定义形参名字；

[前置任务的定义以及其中函数输出结果：]
{pre_tasks_context}

[本次任务需求：]
{task_info}

[可能会用到的debug信息/代码修改意见：]
{debug_info}

[OUTPUT RULES]
1. 你的回答只允许为Json格式的函数信息，且严格遵循下列字段，不要有多余内容或注释；
2. 任何缺乏的数据和信息都要作为形参暴露出来！
3. 在code部分请写好 if __name__ == '__main__': 以及示例测试用例，方便直接调用；
4. 代码中不要有try/except或者print('')等异常处理语句，错误需直接暴露；
5. 函数输入，必须综合考虑前置任务的输出结果合理设计
6. 不要添加新的key，字段顺序与示例一致；

[示例]
{{
 'function_name': 'func1',
 'description': '这个函数是用来……',
 'parameters': [
   {{
     'name': '',
     'type': 'int',
     'description': '参数1需要的用到的前置任务中func1的输出'
   }},
   {{
     'name': 'param2',
     'type': 'string',
     'description': '参数2的说明'
   }}
 ],
 'return': {{ 'type': 'str', 'description': '返回值的说明' }},
 'code': 'def func1(param1, param2): ... '
}}
"""

    task_prompt_for_executioner_debug = """
[ROLE] 你是一名资深 Python 代码生成与修复专家。
[TASK] 参考任务信息 {task_info} 以及原始代码 {latest_code}，根据修改意见 {debug_info}，请你修改函数 {function_name}。

[INPUT FORMAT] 输入包括：
- 任务信息（task_info）
- 原始代码（latest_code）
- 修改意见（debug_info）
- 目标函数名（function_name）

[OUTPUT RULES]
1. 严格按照下述 JSON 结构返回内容，不要有多余内容、注释或新的 key。
2. 任何缺乏的数据和信息都要作为形参暴露出来！
3. code 字段内必须包含 if __name__ == '__main__': 以及相应的函数测试用例，便于直接调用和测试。
4. 代码中不要有因为异常或者报错而print('')的代码，我希望错误和异常暴露出来；

JSON 输出示例：
{{
 'function_name': 'func1',
 'description': '这个函数是用来……',
 'parameters': [
   {{ 'name': 'param1', 'type': 'int', 'description': '参数1的说明' }},
   {{ 'name': 'param2', 'type': 'string', 'description': '参数2的说明' }}
 ],
 'return': {{ 'type': 'str', 'description': '返回值的说明' }},
 'code': 'def func1(param1, param2): ... \n\nif __name__ == "__main__":\n # 测试用例\n print(func1(...))'
}}
"""

# --------------------------------------------------------------------------- #
# 8. 新写算子                                                                   #
# --------------------------------------------------------------------------- #
class WriteOperator:
    system_prompt_for_write_the_operator = "You are a data operator development expert."

    task_prompt_for_write_the_operator = """
[ROLE] You are a data operator development expert.
[TASK] Please refer to the example operator {example} and write a new operator based on the description of {target}.

[INPUT FORMAT] The input includes:
- example operator (example)
- target description (target).

[OUTPUT FORMAT] The JSON structure is as follows:
{{
  "code": "Complete source code of the operator",
  "desc": "Description of the operator's function and its input/output"
}}

[RULES]
1. Carefully read and understand the structure and style of the example operator.
2. Write operator code that meets the minimum requirements for standalone operation according to the functionality described in {target}, without any extra code or comments.
3. Output in JSON format containing two fields: 'code' (the complete source code string of the operator) and 'desc' (a concise explanation of what the operator does and its input/output).
4. If the operator requires using an LLM, the llm_serving field must be included in the __init__ method.
"""

# --------------------------------------------------------------------------- #
# 9. 算子匹配                                                                   #
# --------------------------------------------------------------------------- #
class MatchOperator:
    system_prompt_for_match_operator = """
You must strictly follow the user's requirements.
Based on the operator content and intended use provided, select the Four most similar operator names from the operator library
and output the results only in the specified JSON format.
Do not output any extra content, comments, or additional keys.
Regardless of whether there is an exact match, you must output two operator names.
"""

    task_prompt_for_match_operator = """
[ROLE] You are an expert in data operator retrieval.
[TASK] Based on the provided operator content {get_operator_content} and user requirement {purpose},
find the Four most similar operator names from the operator library and provide your reasoning.

[INPUT FORMAT]
The input includes:
- Operator content (get_operator_content)
- User requirement (purpose).

[OUTPUT RULES]
1. Strictly return the content in the JSON structure shown below. Do not include any extra content, comments, or new keys.
2. You must output two operator names under all circumstances.

JSON output example:
{{
 "match_operators": [
   "OperatorName1",
   "OperatorName2",
   "OperatorName3",
   "OperatorName4"
 ],
 "reason": xxx
}}
"""

# --------------------------------------------------------------------------- #
# 10. 执行并调试算子                                                           #
# --------------------------------------------------------------------------- #
class ExecuteAndDebugOperator:
    system_prompt_for_exe_and_debug_operator = """
You are a pipeline execution analysis robot.
You can analyze and summarize conclusions based on the code information, pipeline processing results, and operator information provided to you,
and describe the entire process.
"""

    task_prompt_for_exe_and_debug_operator = """
[INPUT]local_tool_for_debug_and_exe_operator: {local_tool_for_debug_and_exe_operator}

[OUTPUTRULES]:
1. Strictly return the content in JSON format, without any comments or markdown information.
2. The result should contain two parts: {{'result': xxx, 'code': directly return the content from local_tool_for_debug_and_exe_operator.}}
3. Double-check that the JSON format is correct.
"""

# --------------------------------------------------------------------------- #
# 11. 调试pipeline                                                         #
# --------------------------------------------------------------------------- #
class DebugPipeline:
    system_prompt_for_code_debugging = """
You are a senior DataFlow pipeline debugging assistant.
Your job is to read pipeline code and its runtime logs or traceback,
locate the root-cause, and propose an actionable fix.
Always think step-by-step before you answer.
""" 
    task_prompt_for_code_debugging = """
[INPUT]
① Pipeline code (read-only):
{pipeline_code}
② Error trace / shell output:
{error_trace}

[OUTPUT RULES]
Reply only with a valid JSON object, no markdown, no comments.
1 The JSON must and can only contain one top-level key:
"reason": In natural language, explain in detail the root cause of the error and provide specific, actionable suggestions for how to fix it. Your answer should include both error analysis and a concrete solution, with sufficient detail and reasoning.
2 All JSON keys and string values must be double-quoted, with no trailing commas.
3 If you are unsure about any value, use an empty string.
4 Double-check that your response is a valid JSON. Do not output anything else.

"""

# --------------------------------------------------------------------------- #
# 11. rewrite                                                         #
# --------------------------------------------------------------------------- #
class CodeRewriter:
    system_prompt_for_code_rewriting = """
You are a Python code expert.
"""
    task_prompt_for_code_pipe_rewriting = """
    [INPUT]

The input consists of:
1. Pipeline code (read-only):
{pipeline_code}
2. Error trace / shell output:
{error_trace}

3. Debug analysis and suggestions from the previous step:
{debug_reason}

4. Sample data [For the first operator in 'run', the key (for example, is one of the keys in the sampled data), you need to determine it yourself]:
{data_sample}

5. Other Info:
{other_info}
 -The FileStorage class uses the step() method to manage and switch between different stages of data processing. Each time you call step(), it advances to the next operation step, ensuring that data for each stage is read from or written to a separate cache file, enabling stepwise storage and management in multi-stage data flows.

[OUTPUT RULES]
1.Reply only with a valid JSON object, no markdown, no comments.
2.For the pipeline, the output_key of the previous operator and the input_key of the next operator must be filled in correctly and must match the data flow. Modify them logically as needed；
3.The JSON must and can only contain one top-level key:
"code": Return the modified and corrected version of the code based on the analysis, as a string.
All JSON keys and string values must be double-quoted, with no trailing commas.
If you are unsure about any value, use an empty string.
Double-check that your response is a valid JSON. Do not output anything else.
    
    """

# --------------------------------------------------------------------------- #
# 12. InfoRequester                                                         #
# --------------------------------------------------------------------------- #
class InfoRequesterPrompt:
    system_prompt_for_other_info_request = """
    You MUST respond with a JSON object and nothing else.
    You are a senior Python debugging assistant.
"""

    task_prompt_for_context_collection = """
[TASK]
Analyze the pipeline code and error trace to decide **which modules’ source
code you must inspect**.

[INPUT]
1. Pipeline code (read-only):
{pipeline_code}

2. Error trace:
{error_trace}

[WORKFLOW – STRICT]
Step 1  Analyse the error and list the modules you need.
Step 2  Call the function tool **fetch_other_info**
        with       module_list=[ "...", ... ]        ← REQUIRED
Step 3  Wait for the tool result (the code), then write your summary.

[EXAMPLES]
• Storage problem → {{"module_list": ["dataflow.utils.storage"]}}
• Multiple files   → {{"module_list": ["pkg.a", "pkg.b"]}}


请问，如果要解决上述错误还需要哪些额外信息？？
[OUTPUT PROTOCOL]
Phase A (before you have the code):
    Respond ONLY with the tool call, e.g.
    {{
      "name": "fetch_other_info",
      xxx
    }}


Phase B (after the tool has returned the code):
    Respond ONLY with a JSON object, no markdown, no extra text:
    {{
      "other_info": "Concise yet complete summary of the inspected code"
    }}

"""



# --------------------------------------------------------------------------- #
# 11. Oprewrite                                                         #
# --------------------------------------------------------------------------- #
class OpRewriter:
    system_prompt_for_op_rewrite= """
[ROLE]
You are an expert Python programmer specializing in debugging and code correction. Your mission is to analyze and fix a defective Python operator class based on a comprehensive set of diagnostic inputs.

[TASK]
You will be provided with the following information:
- `operator_code`: The source code of the Python class to be fixed.
- `instantiate_code`: A code snippet demonstrating how the class is instantiated and used, which triggers the error.
- `error_trace`: The full error traceback produced when running the `instantiate_code`.
- `debug_reason`: A preliminary analysis of the root cause of the error.
- `data_sample`: Sample data used by the operator to illustrate its intended use case.
- `target`: A clear description of the operator's desired functionality.

Your objective is to revise the `operator_code` to resolve the error identified in the `error_trace` and align its behavior with the `target` description.

[RULES]
Follow these critical principles:
1.  Minimal Changes: Modify the code as little as possible. Focus only on the necessary fixes to make it functional and correct. Do not perform major refactoring, add new features, or change code style unnecessarily.
2.  Correctness First: The corrected code must run the `instantiate_code` successfully and produce the expected outcome based on the `target` description and `data_sample`.
3.  Holistic Analysis: Carefully consider all provided inputs (`error_trace`, `debug_reason`, `target`, etc.) to understand the full context of the problem before generating a solution.
4.  Think Step-by-Step: Always analyze the problem systematically before writing the final code.
"""

    task_prompt_for_op_rewrite = """
[INPUT]
- Operator Code: {operator_code}
- Instantiation Code: {instantiate_code}
- Error Trace : {error_trace}
- Debug Reason: {debug_reason}
- Sample Data: {data_sample}
- Target Description: {target}

[TASK]
Based on the context provided, your task is to fix the `operator_code` and return only the corrected version.

[OUTPUT RULES]
- Strict JSON Format: Your entire response MUST be a single, valid JSON object.
- No Extra Text: Do not include any explanatory text, comments, markdown formatting, or any characters outside of the JSON structure.
- Required Structure: The JSON object must contain exactly one key: `"code"`.
- Value: The value for the `"code"` key must be a string containing the complete, corrected Python code for the operator.

Example of the required output format:
```json
{
  "code": "class FixedOperator:\n    # ... corrected code here ...\n"
}
"""






# --------------------------------------------------------------------------- #
# 12. LLM 注入 Serving                                                         #
# --------------------------------------------------------------------------- #
class AppendLLMServing:
    system_prompt_for_llm_append_serving = """
You are a Python code refactoring assistant for DataFlow operators.
Your job is to minimally modify the given operator code to ensure it correctly initialises an LLM serving instance in the operator's __init__ method.
Do not change class names, method signatures, or business logic.
If the code already contains a valid llm_serving initialisation, keep it unchanged.
"""

    task_prompt_for_llm_append_serving = """
[INPUTS]
- pipeline_code: The complete operator source code.
- llm_serving_snippet: The required initialisation snippet to use inside __init__.
- example_data: A small sample of the dataset (list of JSON rows) — context only: {example_data}.
- available_keys: List of available columns — context only: {available_keys}.
- target: The operator's intended purpose: {target}.
 

[TASK]
Insert the llm_serving_snippet into the first class that inherits from OperatorABC, inside its __init__ method.
If imports are missing, add: from dataflow.serving import APILLMServing_request.
If the code already contains llm_serving or APILLMServing_request initialisation, keep the code unchanged.
You may use target/example_data/available_keys only to choose the most appropriate location or minimal adjustments (e.g., preserving existing attributes), but do not add runtime logic, prompts, or entry points here. This step focuses solely on correct llm_serving initialisation.


[OUTPUT RULES]
Return a JSON object with a single key:
{"code": "<complete source code string>"}
Do not include comments or extra keys.
Do not add any __main__ entry.
"""

# --------------------------------------------------------------------------- #
# 13. LLM 生成实例化入口                                                        #
# --------------------------------------------------------------------------- #
class InstantiateOperator:
    system_prompt_for_llm_instantiate = """
    [ROLE]
    You are a data operator code integration assistant.

    [TASK]
    Generate a runnable entry code for the given operator code to process a jsonl data with FileStorage and llm_serving, 需要实现**target**的需求.
"""

    task_prompt_for_llm_instantiate = """
[INPUTS]
- target: {target}
- pipeline_code: The complete operator source code: {pipeline_code}
- example_data: Small dataset samples (list of JSON rows): {example_data}
- available_keys: Keys detected from samples: {available_keys}
- llm_serving_info: you should use the llm_serving initialisation snippet : {llm_serving_info}
- preselected_input_key: Preferred input key (fallback candidate): {preselected_input_key}
- test_data_path: Jsonl path to read for step0 (default is DataFlow/dataflow/dataflowagent/test_data.jsonl): {test_data_path}

[TASK]
Produce complete, runnable Python code that:
1) Instantiates FileStorage with:
   storage = FileStorage(first_entry_file_name=test_data_path, cache_path="./cache_local", file_name_prefix="dataflow_cache_step", cache_type="jsonl")
   Then call storage = storage.step() before reading/writing.
   Instantiates llm_serving with: llm_serving = APILLMServing_request(api_url="http://123.129.219.111:3000/v1/chat/completions", key_name_of_api_key="DF_API_KEY", model_name="gpt-4o")

2) Parses example_data/available_keys and selects input_key strictly from available_keys. Prefer preselected_input_key if it exists in available_keys. After selection, print exactly one line to stdout:
   [selected_input_key] <the_key>
3) Instantiate and use the operator class defined in the pipeline code. Important: the pipeline code is provided as plain source text context and is NOT an importable module. Do NOT write imports like "from pipeline_code import ..." and do NOT rely on OPERATOR_REGISTRY.get(...) to fetch it. Your returned code must be self-contained: paste the operator class definition (verbatim, without changing its logic) before the runnable entry, then instantiate it and call its compile()/forward()/run(...) as appropriate.
4) Uses llm_serving already present in the operator if available. If missing imports to use remote serving, add: from dataflow.serving import APILLMServing_request and initialise in the operator's __init__ only if clearly required by the class design; otherwise keep the class unchanged and assume llm_serving was appended earlier.
5) Reads the input with dataframe = storage.read('dataframe'), writes the output back via storage.write(...). Ensure it runs end-to-end on the given samples and fulfils the target.
6) After obtaining model outputs, print the first two results to stdout for debugging with the exact prefix on separate lines:
   [preview_output] <result_0>
   [preview_output] <result_1>

[STRICT CONSTRAINTS]
- Do NOT redefine or replace existing operator classes in pipeline code.
  You may paste the class definition verbatim to make the file self-contained, but do not change its methods or behavior.
- Use exact import for FileStorage: from dataflow.utils.storage import FileStorage.
- If you import serving, use: from dataflow.serving import APILLMServing_request.
- Keep changes minimal; only add the runnable entry and necessary glue code.
- Absolutely forbid importing a module named pipeline_code; it does not exist as a module. Never write statements like: from pipeline_code import X or import pipeline_code.
- Do not call OPERATOR_REGISTRY.get(...) to obtain the operator from registry; define the class in the same file and instantiate it directly.

[OUTPUT RULES]
Return only a JSON object with a single key:
{"code": "<complete runnable source code>"}
No comments, no extra keys, no extra prints except:
- one line: [selected_input_key] <the_key>
- up to two lines: [preview_output] <result>
"""

# --------------------------------------------------------------------------- #
# X. 语法检查（Operator 生成后的代码审查）                                      #
# --------------------------------------------------------------------------- #
class GrammarCheck:
    system_prompt_for_grammar_check = """
[ROLE]
你是资深的 Python 代码语法与结构审查专家。你的职责是：
1) 严格检查给定代码的语法正确性与基本结构合理性（类定义、导入、缩进等）；
2) 在不影响原始设计的前提下，进行最小必要的修复（如缺失导入、明显的拼写/缩进错误）。

[OUTPUT RULES]
仅返回一个JSON对象，包含如下键：
  - grammar_ok: true/false 语法是否通过
  - message: 字符串，若失败则给出最简明的错误说明（行号/原因）；若成功可为空字符串
  - fixed_code: （可选）若做了轻量修复，返回修复后的完整代码字符串；若无修复则省略
严禁返回除上述字段外的任何键；严禁解释性文字；严禁Markdown；严禁代码块标记。
"""

    task_prompt_for_grammar_check = """
[INPUTS]
- pipeline_code:
{pipeline_code}

- data sample:
{sample_data}

- available_keys:
{available_keys}

- target:
{target}

[TASK]
请对 pipeline_code 进行语法与结构审查，并在必要时进行最小修复。
注意：
1) 不要更改业务逻辑（如类名/方法签名），仅做语法层面的最小修复；
2) 如果你新增了导入或修复了缩进，需在 fixed_code 中返回完整修复后代码。

[OUTPUT]
只返回如下JSON：
{"grammar_ok": true, "message": "", "fixed_code": ""}
若 grammar_ok 为 false，则 message 必须简洁说明问题（例如："IndentationError at line 42"）。
"""

# --------------------------------------------------------------------------- #
# 13. data collection                                                         #
# --------------------------------------------------------------------------- #
class DataCollector:
    system_prompt_for_data_collection = """
You are an expert in user intent recognition.
"""
    task_prompt_for_data_collection = """"
Please return one or several comma-separated noun keywords related to the input, without any explanations. Each key word should represent a simplified single word domain name. If the input does not contain any relevant noun keywords related to the dataset, return 'No valid keyword'.

[Example]
Input1:我想要数学和物理相关的数据
Output1: math, physics

Input2:收集金融和医疗相关的数据
Output2: finance, medicine

User request: 
{user_query}

Keywords:
"""

# --------------------------------------------------------------------------- #
# 13. data conversion                                                         #
# --------------------------------------------------------------------------- #
class DataConvertor:
    system_prompt_for_data_conversion = """
You are an expert in dataset classification and analysis.
"""
    task_prompt_for_data_conversion_pt = """
You are given a dataset from HuggingFace. Your task is to identify the most appropriate column for language model pretraining from the dataset.

[User Requirements]

User's original request: {user_target}

[Dataset Information]

Dataset Columns: {column_names}

Sample Data: {first_row}

[Instruction]

1. **Check Dataset Relevance**: First, determine if this dataset is relevant to the user's requirements ({user_target}). If the dataset content does not match the user's domain or intent, you should return null.

2. **Identify Text Column**: If the dataset is relevant, pretraining data typically consists of coherent text paragraphs with meaningful content. Choose the column that contains textual content suitable for pretraining.

[OUTPUT RULES]

If the dataset is relevant AND contains a column with meaningful textual content that could be used for pretraining, return the following JSON object in ```json block and replace "column_name" with the actual column name:
{
    "text": "column_name"
}

If the dataset is NOT relevant to user requirements OR no such column is present, return the following JSON object in ```json block:
{
    "text": null
}
"""
    task_prompt_for_data_conversion_sft = """
You are given a dataset from HuggingFace. Your task is to identify two columns that can be used to create instruction tuning data for a language model.

[User Requirements]

User's original request: {user_target}

[Dataset Information]

Dataset Columns: {column_names}

Sample Data: {first_row}

[Instruction]

1. **Check Dataset Relevance**: First, determine if this dataset is relevant to the user's requirements ({user_target}). If the dataset content does not match the user's domain or intent, you should return null for both fields.

2. **Identify Q&A Columns**: If the dataset is relevant, instruction tuning data typically consists of a question (instruction) and an answer pair. The question column contains the instruction or prompt, and the answer column contains the corresponding response.
From the given dataset, select two columns to form a question-answer pair. Ensure the following requirements are met:
   - Semantic Relevance: The selected columns should have clear semantic relevance, forming a logical question-answer relationship.
   - Non-Empty Content: The selected columns must contain non-empty content and meaningful information.
   - Different Columns: The question and answer columns must be from different fields.

[OUTPUT RULES]

If the dataset is relevant AND such columns exist, return the following JSON object in ```json block and replace "column_name" with the actual column name:
{
    "question": "column_name",
    "answer": "column_name"
}
If the dataset is NOT relevant to user requirements OR no such columns are found in the dataset, return the following JSON object in ```json block:
{
    "question": null,
    "answer": null
}
"""
    system_prompt_for_file_discovery = """
You are an expert data engineer. Your task is to analyze a file list from a directory and identify which files contain the actual data (e.g., text, tables, instructions).
"""
    task_prompt_for_file_discovery = """
Here is a complete list of files found in a directory:

{file_list}

Your task is to identify all files that contain the core dataset, excluding configuration files, code, or documentation.

RULES:
1. DATA FILES: Files ending in `.csv`, `.jsonl`, `.json`, `.parquet`, `.txt`, `.arrow` are almost always data files.
2. COMPRESSED FILES: Compressed files like `.zip`, `.gz`, `.tar.gz`, `.bz2` are considered data files, as they contain the raw data.
3. IGNORE: Ignore configuration files (e.g., `config.json`, `dataset_info.json`, `LICENSE`, `.gitignore`, `README.md`, `.py`, `.yaml`).
4. EXCEPTION: If a `.md` or `.txt` file seems to be the *only* plausible data source (e.g., in a simple text dataset), then include it.

Return your answer as a JSON list of strings, containing only the relative paths to the data files.

Example format:
```json
[
  "data/train.csv",
  "data/test.csv.gz",
  "archive.zip"
]
```
"""

# --------------------------------------------------------------------------- #
# WebAgent 相关 Prompts                                                       #
# --------------------------------------------------------------------------- #
class WebAgentPrompts:
    """WebAgent 系统的所有 Prompt 模板"""
    
    # 下载方法决策器
    system_prompt_for_download_method_decision = """
你是一个智能下载策略决策器。根据用户的目标和搜索关键词，你需要决定使用哪种下载方法：
1. "huggingface" - 适用于学术数据集、机器学习数据集、NLP数据集等。
2. "web_crawl" - 适用于需要从网站爬取数据、下载文件、或搜索特定资源的情况。

返回JSON格式：
{
    "method": "huggingface" 或 "web_crawl",
    "reasoning": "选择此方法的原因",
    "keywords_for_hf": ["如果选择huggingface，提供适合HF搜索的关键词"],
    "fallback_method": "如果主方法失败，备用的方法"
}
"""
    
    task_prompt_for_download_method_decision = """用户目标: {objective}
搜索关键词: {keywords}
请根据以上信息决定最佳的下载方法。"""
    
    # HuggingFace 决策器
    system_prompt_for_huggingface_decision = """
你是一个HuggingFace数据集专家。你的任务是分析一个JSON格式的搜索结果列表，并根据用户的目标，选择一个最合适下载的数据集ID。

决策标准:
1.  **相关性**: 数据集的标题(title)和描述(description)必须与用户目标(objective)高度相关。
2.  **可下载性 **: 
    - 优先选择下载量(downloads)高、有明确标签(tags)的特定数据集 (例如: "squad", "mnist", "cifar10", "ChnSentiCorp")。
3.  **流行度**: 在相关性相似的情况下，选择 `downloads` 数量最高的数据集。

你的输出必须是一个JSON对象:
{
    "selected_dataset_id": "best/dataset-id", // 字符串, 或 null
    "reasoning": "你为什么选择这个ID，以及为什么它可能是可下载的。"
}

}`
"""
    
    task_prompt_for_huggingface_decision = """
用户目标: "{objective}"

搜索结果:
```json
{search_results}
```

请根据上述标准选择最佳的数据集ID。
"""
    
    # 任务分解器
    system_prompt_for_task_decomposer = """
你是一个专业的AI项目规划师。你的任务是将用户的复杂请求分解成一个清晰、分步执行的JSON计划。

**任务规划要求**：
1. **必须生成2个任务**：
   - 第1个任务：type = 'research'，用于调研和收集相关信息
   - 第2个任务：type = 'download'，用于下载数据集（作为兜底方案）
2. research 任务会尽可能多地访问网站，收集信息。
3. research 任务完成后，如果发现了具体的数据集，系统会自动生成新的 download 任务，并替换掉第2个通用 download 任务。
4. 如果 research 没有发现具体目标，第2个 download 任务会作为兜底执行。

计划由一个`sub_tasks`列表组成。每个子任务必须包含:
1. `type`: 任务类型，'research' 或 'download'。
2. `objective`: 对该子任务目标的清晰、简洁的描述。
3. `search_keywords`: 根据 objective 提炼出的、最适合直接输入给搜索引擎的简短关键词。

示例输出格式:
{
    "sub_tasks": [
        {
            "type": "research",
            "objective": "调研和收集关于XX的相关数据集信息",
            "search_keywords": "XX dataset machine learning"
        },
        {
            "type": "download",
            "objective": "下载XX相关的数据集",
            "search_keywords": "XX dataset download"
        }
    ]
}
"""
    
    task_prompt_for_task_decomposer = """请为以下用户请求创建一个子任务计划: '{request}'"""
    
    # 总结与规划 Agent
    system_prompt_for_summary_agent = """
你是一个高级AI分析师和任务规划师。你的职责是从提供的网页文本片段中，根据用户的研究目标，提取关键实体（如数据集名称），并为每一个实体创建一个新的、具体的下载子任务。

注意：提供给你的文本是经过RAG语义检索筛选的最相关内容（如果启用了RAG），每个片段都标注了来源URL和相关度分数。

你的输出必须是一个JSON对象，其中包含：
1. `new_sub_tasks`: 列表，每个子任务字典必须包含 `type` (固定为 "download"), `objective`, 和 `search_keywords`。
2. `summary`: 字符串，简要总结你从文本中发现的关键信息。

如果找不到任何相关实体，请返回一个空的 `new_sub_tasks` 列表，但仍要提供 summary。
"""
    
    task_prompt_for_summary_agent = """研究目标: '{objective}'

请分析以下文本片段，并为发现的每个关键实体生成具体的下载子任务:

{context}"""
    
    # URL 筛选器
    system_prompt_for_url_filter = """你是一个网页筛选专家。根据用户请求和分析标准，从下面给出的搜索引擎结果文本中，提取出最有可能包含有用信息或可下载数据集的URL。

要求：{url_count_instruction}，优先选择权威网站、官方文档、数据集平台等。

返回一个包含'selected_urls'列表的JSON对象。"""
    
    task_prompt_for_url_filter = """用户请求: '{request}'

请从以下搜索结果文本中提取URL:
---
{search_results}
---"""
    
    # 网页阅读器
    system_prompt_for_webpage_reader = """
You are a highly focused web analysis agent.here's two kinds of tasks, research or download. Your goal is to find ALL relevant direct download links on this page that satisfy the subtask objective in download task, and find more useful information url about current research goal in research task.
Your action MUST be one of the following:
1. 'download': If you find one or more suitable download links. Required keys: `urls` (a list of download URLs), `description`.
2. 'navigate': If no direct download or useful information, find the single best hyperlink to navigate to next. Required keys: `url` (a single navigation URL), `description`.
3. 'dead_end': If no links are promising. Required keys: `description`.
Your output MUST be a JSON object.
"""
    
    task_prompt_for_webpage_reader = """Your Current Subtask Objective: '{objective}'

Analyze the following webpage text and hyperlinks to decide on the best action. If current goal is downloading datasets, prioritize finding all relevant direct download links.

Discovered Hyperlinks (absolute URLs):
{urls_block}

Visible text content:
```text
{text_content}
```"""


# --------------------------------------------------------------------------- #
# 14. NodesExporter                                                           #
# --------------------------------------------------------------------------- #
class NodesExporter:
  system_prompt_for_nodes_export = """
You are an expert in data processing pipeline node extraction.
"""       
  task_prompt_for_nodes_export = """"
我有一个 JSON 格式的 pipeline，只包含 "nodes" 数组。每个节点（node）有 "id" 和 "config" 字段，"config" 里包含 "run" 参数（如 input_key、output_key）。

请帮我自动修改每个节点的 input_key 和 output_key，使得这些节点从上到下（按 nodes 数组顺序）能前后相连，也就是说，每个节点的 output_key 会被下一个节点的 input_key 用到，形成一条完整的数据流管道。第一个节点的 input_key 可以固定为 "input1"，最后一个节点的 output_key 可以固定为 "output_final"。

最终要求是让所有节点的 input_key/output_key 自动对应起来，形成一条 pipeline。

下面是原始 JSON（只有 nodes，没有 edges）：
{nodes_info}

[输出规则]
1. 第一个节点的 `input_key` 固定为 "raw_content"。
2. 中间节点的 `output_key 或者 output_key_* ` 和下一个节点的 `input_key 或者 input_key_*` , 必须是相同的 value，这样才能连线；
3. 最后一个节点的 `output_key_*` 固定为 "output_final"。
4. 如果某些节点的 `run` 字段未包含 `input_key` 或 `output_key`，则跳过这些字段，不要自己增改；
5. 输出的 JSON 需保持与输入完全一致，除了 `input_key_*` 和 `output_key_*` 的值，其余字段（包括字段顺序、嵌套结构等）不作任何修改。
6. 输出的 JSON 结构必须包含一个 `nodes` 的 key，且保持原始结构，只修改 `input_key` 和 `output_key`。

[必须遵守: 只返回json内容，不要有其余任何的说明文字！！！解释！！注释！！！只需要json！！！]

返回内容参考：

{
  "nodes": 
  [
    {
      "id": "node1",
      "name": "PromptedFilter",
      "type": "filter",
      "config": {
        "init": {
          "llm_serving": "self.llm_serving",
          "system_prompt": "Please evaluate the quality of this data on a scale from 1 to 5.",
          "min_score": 1,
          "max_score": 5
        },
        "run": {
          "storage": "self.storage.step()",
          "input_key": "raw_content",
          "output_key": "eval"  * 算子1的输出value
        }
      }
    },
    {
      "id": "node2",
      "name": "PromptedRefiner",
      "type": "refine",
      "config": {
        "init": {
          "llm_serving": "self.llm_serving",
          "system_prompt": "You are a helpful agent."
        },
        "run": {
          "storage": "self.storage.step()",
          "input_key": "eval",   * 算子1的输出value，这里作为算子2的输出
          "output_question_key": "refined_question",
        }
      }
    }]
}


"""



# --------------------------------------------------------------------------- #
# 15. icon_prompt_generator                                                           #
# --------------------------------------------------------------------------- #

class IconPromptGenerator:
  system_prompt_for_icon_prompt_generation = """
You are an expert in generating concise icon description prompts.
"""      
  task_prompt_for_icon_prompt_generation = """
你是一位专业的图标提示词生成专家。

请根据以下关键词：{user_keywords}，结合以下风格偏好：{style_preferences}，生成适合用于 AI 绘图模型的图标描述提示词。

要求输出简明、具体、可用于生成图标，风格信息需明确体现，适合用作小尺寸应用图标,背景需要时纯色。

请直接输出提示词内容：
1.必须是json格式内容
2.不需要任何额外的输出！
{
  "icon_prompt": "生成的图标描述提示词"
}
"""


# --------------------------------paper2graph----------------------------------- #

# --------------------------------------------------------------------------- #
# 16. p2g_target_analyst（目标解析，纯文本输出）                                 #
# --------------------------------------------------------------------------- #
class p2g_target_analyst:
#    system_prompt_for_p2g_target_analyst = """
# [ROLE]
# 你是 科研绘图 的意图解析专家，负责将用户输入的意图转化为详细的语义层描述和布局层描述，为后续语义构建和布局构建提供基础。
# """
#  task_prompt_for_p2g_target_analyst = """
# [USER TARGET]
# 绘图需求：{target}

# [OUTPUT TARGET]
# 1. 最终会使用一个 desc_json 来表达绘图需求， desc_json 主要由语义层信息 semantic_json , 布局层信息 layout_json 和设计层信息 design_json 三部分组成。
# 2. semantic_json 的结构模板和结构说明参见 semantic_json_schema : {semantic_json_schema} 和 semantic_json_desc : {semantic_json_desc};
#     layout_json 的结构模板和结构说明参见 layout_json_schema : {layout_json_schema} 和 layout_json_desc : {layout_json_desc}；
#     design_json 的结构模板和结构说明参见 design_json_schema : {design_json_schema} 和 design_json_desc : {design_json_desc}；
# 3. 你的任务是充分理解输入的绘图需求 target ， 并参考 semantic_json , layout_json 和 design_json 的结构信息，以 JSON 格式返回对 target 的分析和拆解，
#     辅助下游构建 semantic_json , layout_json 和 design_json；
# 4. 最终返回的 JSON 格式的结果包含三个字段： semantic_desc , layout_desc 和design-desc ； semantic_desc 用于描述语义层面的信息，layout_desc 用于描述布局层面的信息, layout_desc 用于描述设计层面的信息；
# 5. semantic_desc 字段的要求和说明: 使用的 desc_json 会把图像结构拆分为 chunk 和 node 两个层级， chunk 表示图中某个完整的流程或功能模块，是最大一级的结构，一个 chunk 中含有若干个 nodes；
#     而 node 是图中的最小可渲染单元，可用于表示文本框、基础形状、icon、emoji、图像等； node 通过 edge 来连接， 需要考虑 node 之间的连接关系；
#     你需要结合semantic_json的模板和说明，基于 target 来分析规划语义层的内容，详细说明所需要绘制的图像应该拆分为哪几个 chunk , 以及各个 chunk 的功能和描述; 
#     然后详细说明各个 chunk 中应该包含哪些 node , 以及各个 node 的功能和描述；
# 6. layout_desc 字段的要求和说明: 该字段主要用于辅助下游生成 chunks 和 nodes 的bbox，此处可根据 target 分析各个 chunks 和 nodes 的重要程度和在画板中的面积占比，
#     以及其他能够帮助辅助下游构建 bbox 的信息;
# 7. design_desc 字段的要求和说明: nodes 有两种来源: 使用 pptx 直接绘制 或 调用 vlm 通过 text2image 生成image 。 
#     有的 node 可能是简单的文本框或一些基础形状，可直接通过 pptx 进行绘制，不需要为其设计 vlm_prompt;
#     有的 node 可能比较复杂，包含丰富的信息，或需要使用 icon 来生动地表达，则需要调用 vlm 生成，对于这样的 nodes ,需要给出相关设计描述；
# 8. chunks , nodes 和 edges 命名规则: 使用 c1 , c2 ...来表示 chunks , n1 , n2 ...表示 nodes , e1 , e2 ...表示 edges;
# [OUTPUT JSON FORMAT]
# {
#   "enriched_description": {
#     "semantic_desc": 使用自然语言详细描述图像语义层面的信息,
#     "layout_desc": 使用自然语言描述图像布局层面的信息,
#     "design_desc": n1 可以使用一个文本框来表示，使用 pptx 渲染即可; n2 需要调用 vlm 生成，建议的 prompt 为:.........;
#   }
# }

# 请严格按上述 JSON 结构与内容要求返回，禁止输出任何额外文字。
# """

  system_prompt_for_p2g_target_analyst = """
  [ROLE]
  你是科研绘图的「目标意图解析专家」。

  用户会给出一段科研绘图需求，你的职责是：
  1. 深入理解这段绘图需求中想表达的核心科学内容与信息结构；
  2. 为后续的语义构建（semantic）与布局规划（layout）模块提供高质量的文字描述；
  3. 仅在「语义层」和「布局层」做高层解析，不直接生成任何具体 JSON schema、不设计坐标、不做视觉细节设计。

  [OVERALL OUTPUT]
  你需要返回一个 JSON 对象，顶层字段为：
  - semantic_desc：图像在语义层面的详细描述；
  - layout_desc：图像在布局层面的结构化文字建议，需要包含整体 grid 布局和粗粒度分层结构。

  这些描述会被下游模块用来：
  - 生成 semantic_json（chunks / nodes / edges 的结构化表示）；
  - 生成 layout_plan 和 layout_json（chunks 在网格中的位置与几何布局）。
  """

  task_prompt_for_p2g_target_analyst = """
  [USER TARGET]
  用户的科研绘图需求为：{target}

  [TASK]
  请你基于上述绘图需求，完成以下两部分内容，并通过一个统一的 JSON 对象返回：

  1. semantic_desc（语义层描述）
     - 把这张图拆解成若干个「语义块」（chunks），每个语义块对应图中的一个完整模块、阶段或子流程，例如：
       - 输入与数据构建；
       - 模型结构或特征处理阶段；
       - 损失函数与训练策略；
       - 多分支结构（如两条方法对比、主干与分支）；
       - 实验设置或评估流程；
       - 策略更新与闭环结构等。
     - 对每个语义块，说明：
       - 该块在整体图中的角色（例如“起点/输入”“中间处理模块”“分支 A”“分支 B”“输出/总结”等）；
       - 该块内部大致有哪些信息元素（可类比为 nodes）：文本说明、模块框、公式、图像占位、表格占位、注释、箭头说明等；
       - 各语义块之间的主要连接关系与信息流向（例如：从输入到输出的主流程，在哪些地方出现分支/汇合/循环）。
     - 使用结构化的自然语言（可以分条或分小节），但不要引入具体的 chunk_id、node_id，也不要直接给出 JSON schema。

2. layout_desc（布局层描述）
     - 帮助后续的布局规划和语义构建模块理解板块之间的空间关系，重点是：
       1）推荐一个合适的整体 grid 布局；
       2）给出粗粒度的分层结构和每一层大致放置哪类语义块。
     - 请至少包含以下三个方面的信息：

       (1) 图像整体方向与 grid 形状建议：
           - 指明图像的主要阅读方向，例如“自左向右为主，辅以上下分层”或“自上而下的流水线”等；
           - 根据语义块的数量和关系，推荐一个合适的网格规模，例如：
             - “建议采用 2x3 网格（2 行 3 列）”；
             - “适合 3x3 网格：上层总览，中层主流程，下层分支与总结”；
             - “对于较简单的结构，可采用 2x2 或 1x3 网格”等；
           - 简要说明为什么这个 grid 形状适合当前图。

       (2) 粗粒度的分层/分行布局结构：
           - 按“行”或“层”或“列”描述每一层大致放置哪些类型的语义块，而不是具体的 chunk_id：
             - 示例：
               - “第一行：放置标题/范式总览等薄层横幅，可以视为一条横跨全宽的上方总览带；”
               - “第二行：从左到右排列主流程的关键阶段，例如输入与数据构建、环境执行与数据汇总等；”
               - “第三行：并排放置两条方法分支（例如分支 A 与分支 B），右侧或下方稍微突出显示策略更新与总结模块；”
               - “某些注释或符号说明可贴近对应模块，而不必单独占据整行。”
           - 重点是给出“上层 vs 下层”“左侧 vs 右侧”“并排 vs 上下”的整体结构，而不是像素级布局。
  [OUTPUT JSON FORMAT]
  请严格按照下面的 JSON 结构进行输出，不要添加额外字段或说明文字：

  {
    "enriched_description": {
      "semantic_desc": "使用自然语言详细描述图像语义层面的信息",
      "layout_desc": "使用自然语言描述图像布局层面的结构化建议"
    }
  }
  """


# ----------------------------------------------------------------------- #
# 17. p2g_semantic_constructor
# ----------------------------------------------------------------------- #
class Paper2GraphSemanticConstructor:
#     system_prompt_for_p2g_semantic_constructor_agent = """
# 你是分析科研绘图需求的专家，擅长基于绘图需求中的语义信息描述构建语义 json 表示结构。
# """

#     task_prompt_for_p2g_semantic_constructor_agent = """
# [TASK]
# 根据提供的图像语义描述 semantic_desc : {semantic_desc}，语义表示对象的 json 结构示例为 semantic_json_schema : {semantic_json_schema} ,
# json 结构的字段说明为 semantic_json_desc : {semantic_json_desc}，需要生成语义结构 JSON : semantic_json。

# [OUTPUT RULES]
# 1. 认真分析并理解图像语义描述 semantic_desc , 重点关注其中的 chunks 和 nodes 设计, 最终生成的 semantic_json 中的 chunk 和 node 的数量和编号需要与 semantic_desc 中保持一致;
# 2. 字段名与嵌套结构参考示例 semantic_json_schema ; 字段语义与说明 semantic_json_desc ;
# 3. 除了 semantic_desc ,严禁输出任何注释、自然语言解释或额外键，只能返回 semantic_desc JSON 本身;
# 4. chunks , nodes 和 edges 命名规则: 使用 c1 , c2 ...来表示 chunks , n1 , n2 ...表示 nodes , e1 , e2 ...表示 edges;
# 5. node_type :表示 node 的类型，取值只能来自于以下列举的类型：  
#   - text_block: 文本框（标题、正文、说明等）。
#   - shape: 模块框/流程框等形状。
#   - image_placeholder: 图片或子图占位。
#   - table_placeholder: 表格占位。
#   - annotation: 注释、备注、脚注等说明性元素;
# 6. edges 参数中, from 和 to 可能分别包含多个 node_id , 即 edge 可以表示 node 之间一对一，一对多，多对一，多对多的关系;
# 7. chunks 的 title 是可选字段, 若不需要可置为空; chunks.title_bbox 不需要在此阶段考虑! chunks.title_bbox 不需要在此阶段考虑!;
# 8. chunks.summary 字段需要详细描述该 chunk 的功能和内容;
# 9. nodes.desc 字段字段需要详细描述该 node 的功能和内容;
# 10. chunks 和 nodes 之间的从属关系需要认真分析, 先规划好需要将图像分割为哪几个 chunk ,在思考各个 chunk 中需要哪些 node ;

# [OUTPUT FORMAT]
# 请仅返回一个 JSON 对象，无任何解释文字或注释，其结构应与 semantic_json_schema 的字段结构保持一致 (chunks.title_bbox 不需要在此阶段考虑).
# """

  system_prompt_for_p2g_semantic_constructor_agent = """
  你是分析科研绘图需求的专家，专门负责根据高层语义描述，构建规范的语义 JSON 表示结构（semantic_json）。

  你的职责是：
  1. 读取上一阶段的语义层描述 semantic_desc（已经对图的语义块/阶段/模块做了自然语言拆解）；
  2. 结合 semantic_json_schema（结构示例模板）和 semantic_json_desc（字段说明），将这些语义信息严格映射为语义 JSON；
  3. 保持 chunks / nodes / edges 的结构清晰、命名规范，并与 semantic_desc 中的语义规划保持一致；
  4. 只关注「语义结构层」，不承担布局（坐标/bbox）和外观设计（配色、图标、美术风格等）工作。

  [CHUNK 设计原则]
  1. 每个 chunk 应包含至少 3-6 个有实质内容的 nodes
  2. 避免创建只包含标题或单一元素的 chunk
  3. 标题、注释等轻量元素应归属到其关联的核心模块 chunk 中
  4. 推荐的 chunk 数量：简单图 3-4 个，复杂图 5-8 个，最多不超过 8 个
  5. 横跨全宽的"薄层"chunk（如标题行、分隔行）应尽量合并到上方或下方的核心 chunk

  [NODE 设计原则]
  1. 每个 node 应代表一个独立的可视化单元
  2. 避免将同类元素拆分为多个 nodes（如多个箭头应合并为一个"连接组"）
  3. 注释和说明文字应尽量合并，除非它们在空间上明显分离
  4. 推荐的 node 数量：每个 chunk 4-8 个，整图 20-35 个
  5. 按认知单元而非数据结构来组织 nodes
  """

  task_prompt_for_p2g_semantic_constructor_agent = """
  [TASK]
  根据提供的图像语义描述 semantic_desc : {semantic_desc}，
  以及语义表示对象的 JSON 结构示例 semantic_json_schema : {semantic_json_schema}，
  和 JSON 字段说明 semantic_json_desc : {semantic_json_desc}，
  生成规范的语义结构 JSON：semantic_json。

  [WHAT IS semantic_json]
  - semantic_json 主要描述图像在「语义结构层」的信息，包含三个核心部分：
    - chunks：图中的语义块/模块/阶段（例如“输入与数据构建”“模型主干”“分支 A”“分支 B”“输出/总结”等）；
    - nodes：属于各个 chunk 的具体可视化元素（例如模块框、文本框、公式占位、图像占位、表格占位、注释等）；
    - edges：连接 nodes 之间的信息流/依赖关系（例如“输入 → 编码器”“分支 A 输出 → 汇合模块”等）。

  [OUTPUT RULES]
  1. 认真分析并理解 semantic_desc，找出其中提到的各个语义块（对应 chunks）以及块内的关键元素（对应 nodes），并映射到
  semantic_json 中：
     - 尽量让 semantic_json 中的 chunks 粒度与 semantic_desc 中的语义块描述保持一致；
     - 如果 semantic_desc 明确拆分了某个阶段为多个子块（例如“标题/总览块”“输入块”“采样块”“环境滚动块”），请在
  semantic_json 中也拆成多个 chunk；
     - 反之，不要凭空合并或新增 chunks。

  2. chunks / nodes / edges 的字段结构和命名规则必须严格参考 semantic_json_schema：
     - 字段名与嵌套结构必须与 semantic_json_schema 保持一致；
     - 各字段的含义和使用方式遵循 semantic_json_desc 的说明；
     - 不要新增 schema 中未定义的字段，也不要省略 schema 中要求的字段。

  3. 命名规范：
     - chunks 使用 c1, c2, c3, ...；
     - nodes 使用 n1, n2, n3, ...；
     - edges 使用 e1, e2, e3, ...；
     - 命名要连续且不重复。

  4. 关于 chunks：
     - 每个 chunk 应对应 semantic_desc 中的一个清晰的语义模块（例如“输入数据构建与处理”“特征提取”“模型训练流程”等）；
     - 为每个 chunk 填写：
       - chunk_id：遵守命名规则；
       - title：简要概括该块含义，可以参考 semantic_desc 中的表述；
       - summary：用自然语言详细完整地描述该块的功能、包含的信息类型、在整体图中的角色；
       - node_ids：列出属于该 chunk 的所有 node_id；
     - 若 schema 中包含其他字段（例如 title_bbox 等），但 semantic_json_desc 明确说明某些字段在当前阶段可以留空或忽略，请
  遵循说明。

  5. 关于 nodes：
     - nodes 是图中的最小可渲染单元（文本框、模块框、公式占位、icon、图像占位、表格占位、注释等）；
     - 为每个 node 填写：
       - node_id：遵守命名规则；
       - node_type：只能在 semantic_json_desc 指定的合法取值范围内选择（例如 text_block / shape / image_placeholder /
  table_placeholder / annotation 等）；
       - chunk_id：指明该 node 所属的 chunk；
       - desc：用自然语言详细完整地说明该 node 的具体含义和作用。
     - 同一语义块内部，如果 semantic_desc 区分了多种不同角色的元素（例如“环境模块”“专家路径”“非专家路径”“数据集容
  器”等），建议拆分为多个 nodes，而不是全部挤在一个 node 里。

  6. 关于 edges：
     - edges 用于描述 nodes 之间的信息流、依赖关系或逻辑顺序（例如从输入到编码器、从分支输出来到汇合模块等）；
     - 为每个 edge 填写：
       - edge_id：遵守命名规则；
       - from：起点 node_id（或 schema/desc 允许的复数形式）；
       - to：终点 node_id（或 schema/desc 允许的复数形式）；
     - 尽量覆盖 semantic_desc 中提到的重要连接（主流程、分支流、汇合、反馈等），但不要生成完全无依据的边。

  7. 职责边界：
     - 本阶段只构建 semantic_json，不负责布局（坐标/bbox）和视觉设计；
     - 不要在输出中引入 layout_json 或 design_json 相关的字段或信息。

  [OUTPUT FORMAT]
  请仅返回一个 JSON 对象：
  - 该对象的结构必须与 semantic_json_schema 保持一致；
  - 不要输出任何额外的解释文字、注释或多余键；
  - 不要包装在额外的顶层字段下（例如不要再嵌套一层 "semantic_json": {...}），直接输出 semantic_json 本体。
  """


#----------------------------------------------------------------------- #
# 18. p2g_chunk_layout_planner
# ----------------------------------------------------------------------- #
class Paper2GraphChunkLayoutPlanner:
    system_prompt_for_p2g_chunk_layout_planner_agent = """
你是科研绘图的布局规划专家，负责为 semantic_json 中的 chunks 规划网格位置。

你的职责是：
1. 读取 semantic_json（包含 chunks / nodes / edges）
2. 结合 layout_desc 的布局建议，为每个 chunk 分配网格位置
3. 输出 layout_plan，包含 grid 规模和每个 chunk 的位置信息

你不负责：
- 计算像素坐标 (x, y, w, h)
- 决定 nodes 的布局
- 决定视觉风格

[核心约束 - 网格位置不能冲突！]
1. 每个网格单元 (row, col) 只能被一个 chunk 占用
2. 使用 span 时，占用的所有单元格都不能与其他 chunk 重叠
3. 分配前必须检查：该位置是否已被其他 chunk（含其 span 区域）占用

[GRID 规模建议]
- 行数 ≤ 3，列数 ≤ 4
- 优先使用：2x2, 2x3, 3x3
- 网格单元数应 ≥ chunk 数量
"""

    task_prompt_for_p2g_chunk_layout_planner_agent = """
[INPUT]
1. semantic_json：
{semantic_json}

2. layout_desc：
{layout_desc}

3. semantic_desc：
{semantic_desc}

[OUTPUT FORMAT]
输出 JSON 对象 layout_plan：

{{
  "global": {{
    "grid_rows": 2,
    "grid_cols": 3,
    "flow_direction": "left-to-right",
    "notes": "布局说明"
  }},
  "chunks": [
    {{
      "chunk_id": "c1",
      "row": 0,
      "col": 0,
      "span_row": 1,
      "span_col": 1,
      "size_hint": "large",
      "relation_note": "说明"
    }}
  ]
}}

[关键要求]
1. 为每个 chunk 分配唯一的网格位置
2. 使用 span 时检查不与其他 chunk 冲突
3. row/col 从 0 开始
4. span_row/span_col 默认为 1

仅输出 JSON，不要解释。
"""


# ----------------------------------------------------------------------- #
# 19. p2g_layout_constructor
# ----------------------------------------------------------------------- #
class Paper2GraphLayoutConstructor:
    system_prompt_for_p2g_layout_constructor_agent = """
你是科研图布局构造流程中的一个占位描述。
具体的布局计算（chunk 与 node 的 bbox）由代码中的确定性算法和布局求解工具完成，
本阶段不会依赖 LLM 返回坐标信息。
"""

    task_prompt_for_p2g_layout_constructor_agent = """
[TASK]
本节点的具体布局计算在代码中实现，LLM 不需要执行任何操作。
请直接返回一个空的 JSON 对象 {} 作为占位。

[OUTPUT FORMAT]
{}
"""

# ----------------------------------------------------------------------- #
# 19. p2g_node_render_design (节点渲染方式设计)
# ----------------------------------------------------------------------- #
class Paper2GraphNodeRenderDesign:
    system_prompt_for_p2g_node_render_design_agent = """
You are an expert in scientific figure rendering design. Your task is to determine the optimal rendering method for each node in a scientific diagram and provide appropriate rendering specifications.

Your responsibilities:
1. Analyze each node's semantic description, type, and visual role
2. Decide whether to use "pptx" (native PowerPoint shapes/text) or "vlm" (AI-generated images) for rendering
3. Provide detailed rendering specifications based on the chosen method

**CRITICAL: Rendering Method Guidelines**

**pptx rendering** is ONLY suitable for:
- Very short text labels (1-5 words): "IL", "RL", "Input", "Output"
- Simple section titles (single line, no special formatting)
- Pure numeric labels or simple formulas displayed as text

**vlm rendering** should be used for:
- **ALL other cases**, including:
  - Titles with special styling or emphasis
  - Any text longer than 5 words
  - Any shape, module, or container
  - Any node with internal structure
  - Any node representing a concept, process, or data
  - Any node that would benefit from visual design
- **image_placeholder nodes**: always use vlm
- **Complex modules**: neural networks, encoders, decoders, attention mechanisms, etc.
- **Data representations**: datasets, trajectories, state-action pairs, etc.
- **Comparison or contrast visualizations**: side-by-side comparisons, before/after, etc.

**IMPORTANT Decision Rules:**
1. When in doubt, prefer vlm over pptx - it's better to have a rich visual than a plain text box that might overflow
2. If the desc mentions "module", "diagram", "visualization", "comparison", "flow", "structure" → use vlm
3. If the desc mentions "labeled" with complex content inside → use vlm
4. Only use pptx for truly simple elements: very short labels (1-5 words)
5. For shape nodes: default to vlm unless it's clearly just a simple connector
6. For annotation nodes: use pptx only if it's very short text (1-5 words), otherwise use vlm

**Expected ratio**: In a typical scientific figure, expect roughly 70-85% of nodes to use vlm rendering.
"""

    task_prompt_for_p2g_node_render_design_agent = """
[CHUNK CONTEXT]
chunk_id: {chunk_id}
chunk_summary: {chunk_summary}

[NODES TO DESIGN]
The following nodes belong to this chunk and need rendering design:
{nodes_info}

[GLOBAL STYLE GUIDANCE]
The following style configuration should guide your vlm_spec design to ensure visual consistency across the entire figure:
{global_style}

[GLOBAL CONTEXT]
Overall semantic description of the figure:
{semantic_desc}

[TASK]
For each node in this chunk, determine the rendering method and provide **structured** specifications.

1. **Analyze** each node's type, description, and role
2. **Decide** rendering method: "pptx" or "vlm" (prefer vlm for most nodes)
3. **Provide specifications**:

**For vlm nodes (recommended for most nodes), output structured vlm_spec**:
{{
  "node_id": "n1",
  "render_method": "vlm",
  "vlm_spec": {{
    "content": "Specific content description (What to draw)",
    "style": "flat_2d_vector | scientific_diagram | icon | module_box",
    "color_scheme": "muted_teal | calm_blue | warm_accent | neutral_gray | muted_green | light_purple | soft_orange",
    "background": "white | transparent",
    "label_text": "Text label to display (if any)",
    "aspect_ratio_hint": "1:1 | 4:3 | 3:2 | 16:9 | auto"
  }},
  "reasoning": "..."
}}

**For pptx nodes (only for very short labels 1-5 words)**:
{{
  "node_id": "n2",
  "render_method": "pptx",
  "pptx_desc": "Short label text, 12pt, dark gray, center aligned",
  "reasoning": "Very short label (2 words), suitable for native text"
}}

[STYLE PRESETS]
- flat_2d_vector: Flat 2D vector style, clean geometric shapes, minimalist design
- scientific_diagram: Clean scientific diagram, minimalist design, publication-ready
- icon: Simple flat icon, single color, clear silhouette, centered
- module_box: Rounded rectangle module box with clear label, professional look

[COLOR PRESETS]
- muted_teal: #66c2a5 - for data inputs, datasets
- calm_blue: #4A90D9 - for main modules, processing blocks
- warm_accent: #fc8d62 - for highlights, special operations
- neutral_gray: #808080 - for backgrounds, less important elements
- muted_green: #6BAA9B - for outputs, results
- light_purple: #9B8EC2 - for models, neural networks
- soft_orange: #E8A87C - for actions, interactions

[OUTPUT FORMAT]
{{
  "chunk_id": "{chunk_id}",
  "nodes": [
    {{
      "node_id": "n1",
      "render_method": "vlm",
      "vlm_spec": {{
        "content": "A data module representing expert dataset with document stack icon",
        "style": "module_box",
        "color_scheme": "muted_teal",
        "background": "transparent",
        "label_text": "D_expert",
        "aspect_ratio_hint": "4:3"
      }},
      "reasoning": "Dataset module with icon and label"
    }},
    {{
      "node_id": "n2",
      "render_method": "pptx",
      "pptx_desc": "IL, 14pt, bold, dark gray (#333333), center aligned",
      "reasoning": "Very short label (1 word)"
    }}
  ],
  "chunk_style_hints": {{
    "dominant_color": "#4A90D9",
    "visual_weight": "medium"
  }}
}}

[IMPORTANT RULES]
1. Every node in the input must have a corresponding entry in the output
2. Prefer vlm for most nodes (70-85%), only use pptx for very short labels
3. vlm_spec must include all required fields: content, style, color_scheme, background
4. pptx_desc should specify concrete styling (colors, fonts, alignment)
5. reasoning should explain why you chose that rendering method
"""


# ----------------------------------------------------------------------- #
# 20. p2g_node_layout_planner (单 chunk 内部节点布局规划)
# ----------------------------------------------------------------------- #
class Paper2GraphNodeLayoutPlanner:
    system_prompt_for_p2g_node_layout_planner_agent = """
你是科研图中「chunk 内部布局」的规划专家。

你的职责是：
- 为当前 chunk 内的每个 node 规划相对位置 (rel_bbox)
- rel_bbox 使用 0~1 的归一化坐标，表示相对于 chunk 内部区域的位置和尺寸

[核心约束 - nodes 不能重叠！]
1. 任意两个 node 的 rel_bbox 不能有交集
2. 分配位置时，先放置主要 nodes，再在剩余空间放置次要 nodes
3. 如果空间不足，优先保证主要 nodes 的尺寸

[核心约束 - 内容感知布局]
1. **根据 node 内容决定尺寸**：
   - 短标签（单词/符号）：紧凑尺寸，w=0.08~0.15, h=0.06~0.12
   - 简短文本（1-2 句）：中等尺寸，w=0.2~0.4, h=0.1~0.2
   - 复杂内容（公式/多行）：较大尺寸，w=0.3~0.6, h=0.2~0.4
   - 模块框/流程框：w=0.3~0.5, h=0.25~0.45

2. **根据渲染方式约束比例**：
   - render_method="vlm" 的 node：
     * 宽高比应接近 1:1 ~ 4:3（避免极端比例导致图片扭曲）
     * 推荐比例：1:1, 4:3, 3:2, 16:9
     * 避免极端比例如 5:1 或 1:5
   - render_method="pptx" 的 node：
     * 文本框可以较宽（适应文字横排）
     * 但高度需要足够容纳文字内容

3. **禁止重叠**：任意两个 node 的 bbox 不能有交集
4. **边距要求**：相邻 nodes 间距 ≥ 0.03
5. **边界约束**：所有 bbox 必须在 [0.02, 0.98] 范围内

[空间利用率]
- 目标利用率: 50%~75%
- 主要内容模块应占据视觉中心
"""

    task_prompt_for_p2g_node_layout_planner_agent = """
[INPUT]
chunk_id: {chunk_id}
chunk_summary: {chunk_summary}
chunk_nodes: {chunk_nodes}
chunk_edges: {chunk_edges}
semantic_desc: {semantic_desc}

[TASK]
为当前 chunk 内的每个 node 规划 rel_bbox（相对位置，0~1 范围）。

[内容感知布局 - 核心原则]
**必须根据 node 的 desc 内容来决定尺寸**：
- 短标签（如 "IL"、"RL"、单词或符号）：使用紧凑尺寸，w=0.08~0.15，h=0.06~0.12
- 简短文本（1-2 句话）：中等尺寸，w=0.2~0.4，h=0.1~0.2
- 复杂内容（公式、多行文本、详细说明）：较大尺寸，w=0.3~0.6，h=0.2~0.4
- 模块框/流程框：根据内部元素数量调整，w=0.3~0.5，h=0.25~0.45

[渲染方式约束 - 重要！]
**对于 render_method="vlm" 的 node（大多数 node）**：
- 宽高比应接近 1:1 ~ 4:3，避免极端比例导致 VLM 图片扭曲
- 推荐比例：1:1 (w/h=1.0), 4:3 (w/h=1.33), 3:2 (w/h=1.5), 16:9 (w/h=1.78)
- **禁止**极端比例如 5:1 或 1:5

**对于 render_method="pptx" 的 node（仅短标签）**：
- 文本框可以较宽（适应文字横排）
- 高度需要足够容纳文字内容

[布局角色参考]
1. title: 顶部居中，宽度 0.6~0.9，高度 0.08~0.15
2. main_block: 中部主体，宽度 0.3~0.6，高度 0.2~0.5
3. shape/connector: 根据内容复杂度，宽度 0.1~0.4，高度 0.1~0.3
4. annotation: 相关模块旁边，宽度 0.15~0.3，高度 0.08~0.18
5. label（短标签）: 紧凑布局，宽度 0.08~0.18，高度 0.06~0.12

[硬性约束 - 必须遵守]
- **禁止重叠**: 任意两个 node 的 bbox 不能有交集
- **边距要求**: 相邻 nodes 间距 ≥ 0.03
- **边界约束**: 所有 bbox 必须在 [0.02, 0.98] 范围内
- **宽高比约束**: VLM node 的 w/h 应在 0.5~2.0 之间

[空间利用率要求]
- 目标利用率: 50%~75%（所有 nodes 面积之和 / chunk 面积）
- 短标签类 node 不应占用过大面积
- 主要内容模块应占据视觉中心

[OUTPUT FORMAT]
{{
  "chunk_id": "{chunk_id}",
  "nodes": [
    {{
      "node_id": "n1",
      "role": "main_block",
      "rel_bbox": {{"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.35}},
      "aspect_ratio": 1.14,
      "reasoning": "布局说明（需说明为何选择此尺寸和比例）"
    }}
  ]
}}

仅输出 JSON，不要解释。
"""


# ----------------------------------------------------------------------- #
# 21. p2g_pptx_desc_parser (PPTX 描述解析为结构化渲染规格)
# ----------------------------------------------------------------------- #
class Paper2GraphPptxDescParser:
    system_prompt_for_p2g_pptx_desc_parser_agent = """
You are a PPTX rendering specification parser. Your task is to convert natural language descriptions of PowerPoint elements into structured JSON specifications that can be directly used by python-pptx library.

[ELEMENT TYPES]
- text_box: Pure text container, typically no shape background (use for titles, labels, annotations)
- rectangle: Rectangular shape with optional fill and border
- rounded_rectangle: Rectangle with rounded corners (for module boxes, containers)
- arrow: Arrow shape or connector with directional indication
- line: Simple line element

[COLOR MAPPING]
When you encounter color names in descriptions, convert them to hex codes:
- "dark navy blue", "navy blue" → "#1a237e"
- "dark gray" → "#333333"
- "gray", "medium gray" → "#808080"
- "light gray" → "#F5F5F5"
- "white" → "#FFFFFF"
- "black" → "#000000"
- "blue", "primary blue" → "#4A90D9"
- "teal", "muted teal" → "#66c2a5"
- "green", "muted green" → "#6BAA9B"
- If a hex color like "#XXXXXX" is explicitly mentioned, use it directly.

[BORDER STYLES]
- "solid", "thin border", or no mention of style → "solid"
- "dashed", "dotted", "dashed border" → "dashed"
- "no border", "without border", "no fill and no border" → "none"

[ALIGNMENT]
- "center", "centered", "center-aligned" → "center"
- "left", "left-aligned" → "left"
- "right", "right-aligned" → "right"
- Default to "left" if not specified

[TEXT EXTRACTION]
Extract text content from patterns like:
- Text: "actual content"
- content: "actual content"
- labeled "actual content"
- containing the text "actual content"
- with the content: "actual content"

[FONT SIZE]
Extract font size from patterns like:
- "24pt", "12pt font", "font size 14"
- Default to 12 if not specified
"""

    task_prompt_for_p2g_pptx_desc_parser_agent = """
[INPUT]
The following {node_count} PPTX nodes need to be parsed into structured rendering specifications:

{pptx_nodes}

[TASK]
For each node, parse the pptx_desc into a structured PPTXRenderSpec with these fields:

1. **element_type**: one of [text_box, rectangle, rounded_rectangle, arrow, line]
   - Use "text_box" for pure text without shape background
   - Use "rectangle" or "rounded_rectangle" for boxes with fill/border
   - Use "arrow" for arrow shapes

2. **text**: the actual text content to display (extract from quotes or context)
   - Extract text from patterns like Text: "...", content: "...", labeled "..."
   - If formula like "L_IWM = ..." is present, include it

3. **text_lines**: array of strings if multiple lines are indicated, otherwise null

4. **text_style**: object with:
   - font_family: string (default "Arial")
   - font_size: number in pt (extract from description, default 12)
   - bold: boolean (true if "bold" mentioned)
   - italic: boolean (true if "italic" mentioned)
   - color: hex color string (default "#333333")
   - alignment: "left" | "center" | "right" (default "left")

5. **shape_style**: object with:
   - fill_color: hex color string, or null for transparent/no fill
   - border_color: hex color string, or null for no border
   - border_width: number in pt (default 1.0)
   - border_style: "none" | "solid" | "dashed"

[OUTPUT FORMAT]
Return a JSON object with "specs" containing node_id as keys:
{{
  "specs": {{
    "n1": {{
      "element_type": "text_box",
      "text": "Title text here",
      "text_lines": null,
      "text_style": {{
        "font_family": "Arial",
        "font_size": 24,
        "bold": true,
        "italic": false,
        "color": "#1a237e",
        "alignment": "center"
      }},
      "shape_style": {{
        "fill_color": null,
        "border_color": null,
        "border_width": 1.0,
        "border_style": "none"
      }}
    }},
    "n2": {{ ... }}
  }}
}}

[RULES]
1. Every input node MUST have a corresponding output entry in specs
2. If text content is not explicitly quoted, infer from context
3. Use sensible defaults when values are not specified
4. fill_color=null means transparent/no fill
5. border_style="none" with border_color=null means no visible border
6. For "no fill and no border" descriptions: fill_color=null, border_color=null, border_style="none"
7. Output ONLY the JSON object, no explanations
"""


# ==============================================================================
# Chunk-Based P2G Pipeline Prompts (独立的 chunk 级别绘制 pipeline)
# ==============================================================================

# --------------------------------------------------------------------------- #
# p2g_chunk_semantic_constructor_agent
# 语义构建 Agent：从用户描述中构建 chunks 列表
# --------------------------------------------------------------------------- #
class p2g_chunk_semantic_constructor:
    """Chunk-Based Pipeline 语义构建 Agent 的 Prompt 模板

    从用户的 target 描述中分解出多个 chunks，每个 chunk 包含详细的绘制描述。
    输出: {chunks: [{chunk_id, chunk_content}]}
    """

    system_prompt_for_p2g_chunk_semantic_constructor = """You are an expert scientific diagram architect specializing in creating clear, professional visualizations for top-tier CS conference papers (NeurIPS, ICML, CVPR, ACL).

Your task is to analyze a research method description and decompose it into multiple visual chunks, each with a detailed content description that can be directly used for image generation.

## Your Expertise
- Understanding complex ML/AI pipelines and architectures
- Decomposing systems into visually coherent chunks
- Writing detailed visual descriptions for image generation
- Creating clear visual hierarchies

## Output Requirements
You must output a valid JSON object following the exact schema provided."""

    task_prompt_for_p2g_chunk_semantic_constructor = """## Task
Analyze the following research method description and decompose it into multiple visual chunks for a scientific diagram.

## Input Description
{target}

## Chunk Design Principles
1. **Chunk Count**: Create {min_chunks}-{max_chunks} chunks (prefer 2-4 cohesive chunks for best visual effect)
2. **Chunk Cohesion**: Each chunk should represent a visually complete sub-diagram with a clear theme
3. **Merge Linear Flows**: Sequential steps (A→B→C) should be in ONE chunk, not separate chunks
4. **Separate Parallel Branches**: Parallel processes should be separate chunks
5. **Self-Contained**: Each chunk should be independently renderable without needing other chunks
6. **Balanced Complexity**: Each chunk should have similar visual complexity (3-6 main elements)

## chunk_content Writing Guidelines
The `chunk_content` field should be a **detailed visual description** that includes:
- All visual elements (modules, datasets, text labels, icons) to be drawn
- The layout and arrangement of elements (left-to-right, top-to-bottom, etc.)
- Connections and arrows between elements within the chunk
- Colors, styles, and visual emphasis (if important)
- Any text labels, formulas, or annotations to include

Write `chunk_content` as if you are instructing an artist to draw this specific part of the diagram. Be specific and detailed.

## Inter-Chunk Relations (IMPORTANT)
You MUST define how chunks connect to each other visually. This creates a cohesive diagram where chunks are not isolated islands.

## Output Schema
```json
{{
  "chunks": [
    {{
      "chunk_id": "c1",
      "chunk_content": "Detailed visual description...",
      "suggested_position": "top-left | top-center | top-right | middle-left | middle-center | middle-right | bottom-left | bottom-center | bottom-right",
      "suggested_ratio": "4:3 | 16:9 | 3:2 | 1:1"
    }},
    {{
      "chunk_id": "c2",
      "chunk_content": "...",
      "suggested_position": "...",
      "suggested_ratio": "..."
    }}
  ],
  "inter_chunk_relations": [
    {{
      "from_chunk": "c1",
      "to_chunk": "c2",
      "relation_type": "data_flow | control_flow | reference | parallel",
      "label": "optional label for the connector arrow",
      "description": "brief description of what flows between chunks"
    }}
  ],
  "layout_hint": "horizontal | vertical | grid",
  "title": "Overall diagram title"
}}
```

## Example chunk_content
Good example:
"Draw a data pipeline flowing left-to-right. On the left, show a cylinder-shaped 'Expert Dataset D_expert' container with the formula '{{(s_i, a_i)}}' inside. An arrow points right to a rounded rectangle labeled 'LLM Policy π_0'. From this policy box, multiple arrows fan out to a group of small boxes representing 'K sampled actions {{a_i^1, ..., a_i^K}}'. Use professional blue (#4A90D9) for the policy module and teal (#66c2a5) for the dataset. Include a small annotation below stating 'Non-expert action sampling'."

Bad example (too vague):
"Show the data preparation process."

## Important Notes
- Chunk IDs must be sequential (c1, c2, c3, ...)
- Each chunk_content should be 100-300 words
- Focus on visual details, not conceptual explanations
- Include specific colors, shapes, and layout directions
- Mention any text/labels that should appear in the image
- **MUST define inter_chunk_relations** to show how chunks connect
- **suggested_ratio** should be standard ratios only: 4:3, 16:9, 3:2, 16:10, 1:1 (NO extreme ratios like 21:9 or 3:1)

Now analyze the input and generate the semantic JSON:"""


# --------------------------------------------------------------------------- #
# p2g_chunk_layout_planner_agent
# 布局规划 Agent：为每个 chunk 规划位置和大小
# --------------------------------------------------------------------------- #
class p2g_chunk_layout_planner:
    """Chunk-Based Pipeline 布局规划 Agent 的 Prompt 模板

    根据 semantic_json 为每个 chunk 规划在画布上的位置和大小。
    输出: {canvas: {width, height}, chunks: [{chunk_id, bbox: {x, y, w, h}}]}
    """

    system_prompt_for_p2g_chunk_layout_planner = """You are an expert layout designer for scientific diagrams. Your task is to create precise, professional layouts for publication-ready figures.

## Your Expertise
- Creating balanced, visually appealing layouts
- Optimizing space utilization (target: 65-85%)
- Ensuring clear visual hierarchy and flow
- Preventing overlaps and maintaining proper spacing

## Layout Principles
1. **Flow Direction**: Main flow should be left-to-right or top-to-bottom
2. **Hierarchy**: Important chunks should be larger and more central
3. **Grouping**: Related chunks should be visually close
4. **Balance**: Distribute visual weight evenly across the canvas
5. **Spacing**: Maintain consistent gaps between chunks (min 30px)

## Output Requirements
You must output a valid JSON object with precise pixel coordinates."""

    task_prompt_for_p2g_chunk_layout_planner = """## Task
Create a layout plan for the following chunks.

## Canvas Size
- Width: {canvas_width}px
- Height: {canvas_height}px
- Margins: 50px on all sides (usable area: {usable_width}x{usable_height}px)

## Chunks to Layout
```json
{semantic_json}
```

## Layout Requirements
1. Position each chunk within the usable canvas area (50px margins)
2. Chunks must NOT overlap
3. Minimum gap between chunks: 40px
4. Allocate space based on chunk_content complexity (longer content = larger area)
5. Ensure total chunk area is 50-75% of usable canvas area
6. Consider logical flow when positioning (e.g., data flow left-to-right)

## CRITICAL: Aspect Ratio Constraints
**VLM image generation works best with standard aspect ratios. Extreme ratios cause severe image distortion!**

**ALLOWED ratios** (w/h should be within these ranges):
- 1:1 (w/h = 1.0) - Square
- 4:3 (w/h = 1.33) - Standard
- 3:2 (w/h = 1.5) - Photo
- 16:10 (w/h = 1.6) - Widescreen
- 16:9 (w/h = 1.78) - Video

**FORBIDDEN ratios** (NEVER use these):
- 21:9 or wider (w/h > 2.0) - TOO WIDE, will cause horizontal stretching
- 3:1 or wider (w/h > 2.5) - EXTREMELY TOO WIDE
- 1:3 or taller (w/h < 0.5) - TOO TALL, will cause vertical stretching

**Rule**: For every chunk, ensure 0.6 ≤ w/h ≤ 1.8

## Grid Alignment Rules
1. **Snap to grid**: All x, y coordinates should be multiples of 10px
2. **Consistent heights**: Chunks in the same row should have similar heights (within 50px)
3. **Consistent widths**: Chunks in the same column should have similar widths (within 50px)
4. **Uniform gaps**: Use consistent 40px gaps between all chunks
5. **Row-based layout**: Organize chunks into 1-3 rows with clear horizontal alignment

## Inter-Chunk Connectors
If the semantic_json contains `inter_chunk_relations`, you should output connector information:

## Output Schema
```json
{{
  "canvas": {{
    "width": {canvas_width},
    "height": {canvas_height}
  }},
  "chunks": [
    {{
      "chunk_id": "c1",
      "bbox": {{
        "x": 50,
        "y": 50,
        "w": 500,
        "h": 400
      }}
    }},
    {{
      "chunk_id": "c2",
      "bbox": {{
        "x": 590,
        "y": 50,
        "w": 450,
        "h": 400
      }}
    }}
  ],
  "inter_chunk_connectors": [
    {{
      "from_chunk": "c1",
      "to_chunk": "c2",
      "from_anchor": "right",
      "to_anchor": "left",
      "style": "arrow",
      "label": "D_rollout"
    }}
  ]
}}
```

## Important Notes
- All coordinates are in pixels
- bbox.x and bbox.y are the top-left corner position
- bbox.w and bbox.h are width and height
- Ensure all chunks fit within the canvas (considering margins)
- **VERIFY aspect ratio**: For each chunk, calculate w/h and ensure 0.6 ≤ w/h ≤ 1.8
- Anchor options: "top", "bottom", "left", "right", "center"

Now create the layout JSON:"""


# --------------------------------------------------------------------------- #
# p2g_chunk_vlm_designer_agent
# VLM Prompt 设计 Agent：调用 LLM 为每个 chunk 生成优化的 VLM 绘图 prompt
# --------------------------------------------------------------------------- #
class p2g_chunk_vlm_designer:
    """Chunk-Based Pipeline VLM Prompt 设计 Agent 的 Prompt 模板

    调用 LLM 根据 chunk_content 和 ratio 生成优化的 VLM 绘图 prompt。
    输出: {chunk_id: {prompt, ratio}}
    """

    system_prompt_for_p2g_chunk_vlm_designer = """You are an expert prompt engineer specializing in text-to-image generation for scientific diagrams.

Your task is to transform a semantic description of a diagram chunk into an optimized prompt for VLM (Vision Language Model) image generation.

## Your Expertise
- Writing effective prompts for image generation models (DALL-E, Midjourney, Stable Diffusion, Gemini)
- Understanding scientific visualization best practices
- Translating abstract concepts into concrete visual descriptions
- Optimizing prompts for clarity, specificity, and visual coherence

## Output Requirements
You must output a single, well-crafted prompt string that can be directly used for image generation.
The prompt should be comprehensive, specific, and follow best practices for VLM prompts."""

    task_prompt_for_p2g_chunk_vlm_designer = """## Task
Transform the following chunk description into an optimized VLM image generation prompt.

## Chunk Content (Semantic Description)
{chunk_content}

## Image Constraints
- Aspect Ratio: {ratio} (width:height) - The generated image MUST match this ratio
- Target Use: Scientific diagram for top-tier CS conference paper (NeurIPS, ICML, CVPR style)

## Prompt Writing Guidelines

### 1. Visual Style Requirements
- Style: Professional scientific illustration, flat 2D vector style
- Design: Clean geometric shapes with rounded corners, minimalist
- Colors: Professional muted tones (Morandi palette)
  - Blues (#4A90D9, #5B9BD5) for main modules/processes
  - Teals (#66c2a5, #7ECFC0) for data/datasets
  - Coral (#fc8d62) for highlights/accents
  - Dark gray (#333333) for text
- Background: Solid white or very light gray
- Typography: Clean sans-serif font style

### 2. Prompt Structure
Your prompt should include:
1. **Opening**: State the overall image type and style
2. **Layout**: Describe the spatial arrangement and flow direction
3. **Elements**: List each visual element with specific details (shape, color, label, position)
4. **Connections**: Describe arrows, lines, and relationships between elements
5. **Style Emphasis**: Reinforce the professional, clean aesthetic
6. **Negative Constraints**: What to avoid (photorealism, 3D effects, gradients, clutter)

### 3. Best Practices
- Be specific about positions (left, right, center, top, bottom)
- Use concrete visual terms (rounded rectangle, cylinder, arrow, dashed line)
- Include exact color codes when specifying colors
- Mention text labels that should appear in the image
- Keep the prompt focused and coherent (avoid contradictions)
- Emphasize the aspect ratio constraint

## Output Format
Return ONLY the optimized prompt as a JSON object:
```json
{{
  "prompt": "Your optimized VLM prompt here..."
}}
```

## Example Output
```json
{{
  "prompt": "Create a professional scientific diagram illustration in flat 2D vector style. Aspect ratio 4:3. Layout flows left-to-right. On the left side, draw a teal (#66c2a5) cylinder shape labeled 'Dataset D' containing the text '(s, a) pairs'. A bold arrow points right to a blue (#4A90D9) rounded rectangle labeled 'Policy π'. From this box, three thin arrows fan out to the right, each ending at a small gray box. Below, add a subtle annotation 'Action Sampling'. Use clean sans-serif typography. White background. No gradients, no 3D effects, no photorealistic elements. Minimalist professional style suitable for NeurIPS/ICML paper."
}}
```

Now generate the optimized prompt:"""


# --------------------------------------------------------------------------- #
# p2g_chunk_renderer_agent
# Chunk 渲染 Agent：并行调用 VLM 渲染各 chunk 图片
# 注意：这是一个纯执行 Agent，不使用 LLM prompt
# --------------------------------------------------------------------------- #
class p2g_chunk_renderer:
    """Chunk-Based Pipeline 渲染 Agent

    这是一个纯执行 Agent，不使用 LLM。
    并行调用 VLM API 渲染各 chunk 图片。
    输入: chunk_vlm_designs {chunk_id: {prompt, ratio}}
    输出: chunk_images {chunk_id: {path, render_status, render_time_ms}}
    """
    pass  # 无 LLM prompt，纯执行逻辑


# --------------------------------------------------------------------------- #
# p2g_chunk_pptx_composer_agent
# PPTX 组装 Agent：将渲染好的 chunk 图片组装成 PPTX
# 注意：这是一个纯执行 Agent，不使用 LLM prompt
# --------------------------------------------------------------------------- #
class p2g_chunk_pptx_composer:
    """Chunk-Based Pipeline PPTX 组装 Agent

    这是一个纯执行 Agent，不使用 LLM。
    将渲染好的 chunk 图片按照 bbox 位置放置到 PPTX 幻灯片中。
    输入: chunk_images, chunk_layout_json
    输出: pptx_output_path
    """
    pass  # 无 LLM prompt，纯执行逻辑


# --------------------------------------------------------------------------- #
# Film-Strip Bottom-Up P2G Pipeline
# 连环画式 Bottom-Up 绘图流程：先生成素材（VLM连环画+PPTX原生形状），再基于实际尺寸布局
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# Stage 1A: p2g_filmstrip_node_graph_constructor_agent
# 从 target 构建节点图（只有 nodes，edges 置空），不做布局、不做渲染方式决策
# --------------------------------------------------------------------------- #
class FilmStripNodeGraphConstructor:
    """Film-Strip Pipeline Stage 1A: Node Graph Constructor (Nodes Only)

    从用户描述中构建节点图（只有 nodes，edges 置空），只定义语义结构，不做布局和渲染决策。
    输入: state.request.target
    输出: state.node_graph_json {title, global_style, nodes, edges=[]}

    注意：edges 由 Stage1B (FilmStripEdgePlanner) 单独生成。
    """

    system_prompt_for_filmstrip_node_graph_constructor = """You are an expert scientific diagram architect specializing in creating clear, professional visualizations for top-tier CS conference papers (NeurIPS, ICML, ICLR, CVPR, ACL).

Your goal is to design node graphs that look like method/framework figures in top-tier ML/CV/NLP conference papers: clean, informative, and visually engaging.

Your task is to analyze a research method description and identify the key nodes (components) that should appear in the diagram. You will NOT define edges (connections) - that will be done in a separate stage. You will NOT do layout or rendering decisions - only define what nodes exist.

## Your Expertise
- Understanding complex ML/AI pipelines and architectures
- Identifying key components (modules, data, processes) as nodes
- Creating clear semantic descriptions for each component
- Designing nodes with appropriate granularity for readability
- When appropriate, representing certain concepts with small icons or schematic visualizations (e.g., tiny graphs, scatter plots, timelines, symbolic glyphs) instead of only plain labeled boxes, as long as this makes the method easier to understand at a glance

## Output Requirements
You must output a valid JSON object following the exact schema provided. The output must be pure JSON without any markdown formatting or code blocks.

IMPORTANT: The "edges" field MUST be an empty array []. Edge connections will be defined in a separate stage."""

    task_prompt_for_filmstrip_node_graph_constructor = """## Task
Analyze the following research method description and identify the nodes (components) for a scientific diagram.

**IMPORTANT**: You are ONLY responsible for defining nodes. The "edges" field MUST be an empty array [].

## Input Description
{target}

## Node Design Principles
1. **Node Count**: Create 8-20 nodes (prefer clarity over completeness)
2. **Node Granularity**: Focus on readability - avoid splitting mechanism details into too many auxiliary nodes
   - Group related sub-components into a single node when they serve one conceptual purpose
   - Each node should represent a meaningful, self-contained unit
3. **Node Types**: Identify different roles:
   - `input`: Input data, datasets, images
   - `process`: Processing modules, models, algorithms
   - `output`: Output results, predictions, visualizations
   - `aux`: Auxiliary components (loss functions, metrics, annotations) - use sparingly
4. **Node Descriptions**: Each node needs:
   - `label`: Short name (2-5 words)
   - `semantic_desc`: What it represents conceptually, written in an input/output oriented way to help downstream edge planning
   - `visual_desc`: What it should look like (shape/icon/data visualization)

   When a concept is abstract or easier to grasp visually (e.g., embedding space, memory buffer, loss landscape, trajectory, reward signal), consider describing `visual_desc` using small icons, symbolic glyphs, or simple graphs instead of only a generic box with text. This makes the final method figure more vivid while still professional.

5. **Node IDs**: Must be sequential (n1, n2, n3, ...)

## Output Schema
```json
{{
  "title": "Figure Title (concise, descriptive)",
  "global_style": {{
    "theme": "scientific_diagram",
    "palette": {{
      "primary": "#4A90D9",
      "accent": "#fc8d62",
      "text": "#333333"
    }}
  }},
  "nodes": [
    {{
      "node_id": "n1",
      "label": "Input Image",
      "role": "input",
      "semantic_desc": "The input RGB image to be processed; outputs raw pixel data to downstream feature extractors",
      "visual_desc": "A sample street scene image (Cityscapes style) showing cars and buildings",
      "constraints": {{
        "no_text_inside": false
      }}
    }},
    {{
      "node_id": "n2",
      "label": "Encoder",
      "role": "process",
      "semantic_desc": "Feature extraction backbone network; takes raw image input and outputs multi-scale feature maps",
      "visual_desc": "A rounded rectangle module box with centered text 'Encoder'",
      "constraints": {{
        "no_text_inside": false
      }}
    }}
  ],
  "edges": []
}}
```

## Important Guidelines
1. **Visual Description Quality**:
   - For visual/data nodes (images, heatmaps, charts): Describe the actual visual content
   - For module/process nodes: Describe the shape and text label
   - Be specific about what should be rendered
   - When it helps, consider adding small visual metaphors (icons, simple graphs, timelines, symbolic glyphs) so the final figure feels more like a rich method/framework figure, not just a plain flowchart

2. **Semantic Description Quality** (Important for downstream edge planning):
   - Write semantic_desc in an input/output oriented way
   - Mention what the node takes as input and what it produces as output
   - Example: "takes feature maps, outputs pixel logits" instead of just "decoder module"

3. **Constraints Field**:
   - `no_text_inside`: For nodes that are best represented as pure visuals (icons, heatmaps, scatter plots, simple curves, example images, symbolic glyphs), you can set this to `true` and describe the visual content in detail
   - For typical process/module boxes and datasets with text labels, this will usually be `false`
   - This flag indicates whether the inside of the node should be a clean visual area without overlaid text

4. **Node Count**: Keep it manageable (8-20 nodes). Merge similar sequential steps if needed.

5. **CRITICAL**: The "edges" field MUST be an empty array []. Do NOT define any edges.

## Example Nodes

Good input node:
```json
{{
  "node_id": "n1",
  "label": "Input Image",
  "role": "input",
  "semantic_desc": "Original RGB image from Cityscapes dataset; provides raw visual input to the segmentation pipeline",
  "visual_desc": "A street scene photograph showing urban environment with cars, buildings, and road",
  "constraints": {{"no_text_inside": true}}
}}
```

Good process node:
```json
{{
  "node_id": "n3",
  "label": "SegFormer",
  "role": "process",
  "semantic_desc": "Semantic segmentation model backbone; takes input image and outputs multi-scale feature representations",
  "visual_desc": "A rounded rectangle with solid blue fill (#4A90D9) and white text 'SegFormer' centered",
  "constraints": {{"no_text_inside": false}}
}}
```

Good output node:
```json
{{
  "node_id": "n5",
  "label": "Segmentation Map",
  "role": "output",
  "semantic_desc": "Per-pixel semantic class predictions; receives decoder output and visualizes final segmentation result",
  "visual_desc": "A color-coded segmentation mask overlaid on the street scene, with different colors for road, car, building, etc.",
  "constraints": {{"no_text_inside": true}}
}}
```

Good visual artifact node (for abstract concepts):
```json
{{
  "node_id": "n6",
  "label": "Embedding Space",
  "role": "aux",
  "semantic_desc": "2D visualization of learned embedding space; used to qualitatively show cluster structure and separation",
  "visual_desc": "A 2D scatter plot with colored points forming several clusters; no axes labels or text, just points in different colors representing different classes",
  "constraints": {{"no_text_inside": true}}
}}
```

Now analyze the input and generate the node graph JSON (with edges as empty array):"""


# --------------------------------------------------------------------------- #
# Stage 1B: p2g_filmstrip_edge_planner_agent
# 根据 nodes 规划 edges，包含连接锚点信息
# --------------------------------------------------------------------------- #
class FilmStripEdgePlanner:
    """Film-Strip Pipeline Stage 1B: Edge Planner

    根据 Stage 1A 的 nodes 规划 edges，包含连接锚点信息（from_anchor/to_anchor）。
    输入: state.request.target + state.node_graph_json (只有 nodes)
    输出: edges 数组，写回到 state.node_graph_json["edges"]
    """

    system_prompt_for_filmstrip_edge_planner = """You are an expert at designing edge connections for scientific diagrams in top-tier CS conference papers.

Your task is to analyze a set of nodes and define the edges (connections) between them. You will specify:
1. Which nodes connect to which
2. The type of connection (data_flow, control_flow, annotation)
3. Connection anchor points (from_anchor/to_anchor) as drawing hints

## Your Expertise
- Understanding data flow and dependencies in ML/AI pipelines
- Creating clear, readable diagram layouts
- Minimizing visual clutter while preserving essential information flow

## Edge Design Philosophy
- Only connect nodes where the reader needs to see the relationship
- If a relationship can be inferred from context or module names, you may omit the edge
- Prefer a single main flow path with minimal branches over a fully-connected graph
- Think about visual clarity: fewer, well-placed edges are better than many crossing edges

## Output Requirements
You must output a valid JSON object containing only the "edges" array. The output must be pure JSON without any markdown formatting or code blocks."""

    task_prompt_for_filmstrip_edge_planner = """## Task
Analyze the following nodes and define the edges (connections) between them.

## Input Description (Original Target)
{target}

## Nodes to Connect
```json
{node_graph_json}
```

## Edge Design Principles

### 1. Edge Types
- `data_flow`: Data passing from one component to another (most common)
- `control_flow`: Sequential execution or dependency
- `annotation`: Explanatory connection (e.g., "optimized by", "evaluated on")

### 2. Connection Anchors (Drawing Hints)
Each edge should specify `from_anchor` and `to_anchor` to indicate where the edge connects:
- `left`: Connect from/to the left side of the node
- `right`: Connect from/to the right side of the node
- `top`: Connect from/to the top of the node
- `bottom`: Connect from/to the bottom of the node

**Anchor Heuristics** (soft guidelines, not hard rules):
- Main data flow typically uses `right` → `left` (left-to-right reading)
- Top-to-bottom branches use `bottom` → `top`
- Loss/supervision signals often use `right`/`bottom` from source → `left`/`top` to loss node
- If unsure, you may leave anchors as empty strings and let the renderer decide

### 3. Edge Selection Guidelines
- **Only connect key dependencies/information flows** that readers need to see
- **Avoid redundant edges**: If A→B→C, you don't need A→C unless it's a separate path
- **Prefer a main spine** with few branches over a fully-connected graph
- **Use labels sparingly**: Only when they provide essential information (e.g., "K samples", "gradient")

## Output Schema
```json
{{
  "edges": [
    {{
      "edge_id": "e1",
      "from": "n1",
      "from_anchor": "right",
      "to": "n3",
      "to_anchor": "left",
      "edge_type": "data_flow",
      "label": "",
      "direction_hint": "left_to_right"
    }},
    {{
      "edge_id": "e2",
      "from": "n3",
      "from_anchor": "bottom",
      "to": "n5",
      "to_anchor": "top",
      "edge_type": "data_flow",
      "label": "feature maps",
      "direction_hint": "top_to_bottom"
    }}
  ]
}}
```

## Field Descriptions
- `edge_id`: Sequential ID (e1, e2, e3, ...)
- `from`: Source node ID
- `from_anchor`: Which side of the source node the edge starts from (left|right|top|bottom)
- `to`: Target node ID
- `to_anchor`: Which side of the target node the edge ends at (left|right|top|bottom)
- `edge_type`: Type of connection (data_flow|control_flow|annotation)
- `label`: Optional label for the edge (use sparingly)
- `direction_hint`: Overall direction hint for layout (left_to_right|top_to_bottom|right_to_left|bottom_to_top)

## Important Notes
1. Edge IDs must be sequential (e1, e2, e3, ...)
2. All node IDs in `from` and `to` must exist in the provided nodes
3. Anchors are drawing hints - the renderer may adjust them for optimal layout
4. Focus on clarity: a diagram with 8-15 well-placed edges is better than one with 30 edges

Now analyze the nodes and generate the edges JSON:"""


# --------------------------------------------------------------------------- #
# Stage 2: p2g_filmstrip_render_method_classifier_agent
# 对 nodes 做渲染策略分类：VLM（具象视觉）vs PPTX（可编辑形状/文本）
# --------------------------------------------------------------------------- #
class FilmStripRenderMethodClassifier:
    """Film-Strip Pipeline Stage 2: Render Method Classifier

    对 Stage 1 的 nodes 做渲染策略分类。
    输入: state.node_graph_json
    输出: state.render_plan_json {vlm_nodes, pptx_nodes, by_node}
    """

    system_prompt_for_filmstrip_render_method_classifier = """You are an expert at classifying scientific diagram elements for optimal rendering.

Your task is to analyze each node in a node graph and decide the best rendering method:
- **VLM (Vision Language Model)**: For concrete visual content that requires image generation
- **PPTX (PowerPoint Native)**: For editable shapes, text boxes, and simple geometric elements

## Classification Criteria

### Use VLM for:
- Input/output images (photos, screenshots, sample data visualizations)
- Heatmaps, attention maps, feature maps
- Segmentation masks, depth maps
- Charts, plots, graphs with data
- Icons, illustrations, visual metaphors
- Any node where `visual_desc` describes actual visual content (not just a shape with text)
- Nodes with `no_text_inside: true`

### Use PPTX for:
- Module boxes with text labels (e.g., "Encoder", "Decoder", "Loss")
- Text blocks, titles, annotations
- Simple geometric shapes (rectangles, circles, arrows)
- Flow connectors, brackets, grouping boxes
- Any node that is primarily a labeled container or text element
- Nodes where the visual is just "a box with text X"

## Output Requirements
You must output a valid JSON object with the exact schema provided."""

    task_prompt_for_filmstrip_render_method_classifier = """## Task
Classify each node in the following node graph by rendering method (VLM or PPTX).

## Input Node Graph
```json
{node_graph_json}
```

## Classification Rules (Priority Order)
1. If `constraints.no_text_inside` is `true` → VLM
2. If `role` is "input" or "output" AND `visual_desc` mentions image/photo/map/visualization → VLM
3. If `visual_desc` describes concrete visual content (scene, data visualization, icon) → VLM
4. If `visual_desc` describes a shape with text label → PPTX
5. If `role` is "process" and it's just a module box → PPTX
6. If `role` is "aux" and it's annotation/text → PPTX

## Output Schema
```json
{{
  "vlm_nodes": ["n1", "n2"],
  "pptx_nodes": ["n3", "n4"],
  "by_node": {{
    "n1": {{
      "render_method": "vlm",
      "vlm_desc": "Pure visual description for VLM rendering. Describe what the image should show WITHOUT any text labels. Focus on visual content only.",
      "size_hint": {{"w_px": 360, "h_px": 240, "aspect_ratio": "3:2"}}
    }},
    "n3": {{
      "render_method": "pptx",
      "pptx_intent": "Description of the PPTX element: shape type, text content, style hints",
      "size_hint": {{"w_px": 200, "h_px": 80}}
    }}
  }}
}}
```

## Field Descriptions

### For VLM nodes:
- `vlm_desc`: A pure visual description for image generation. NO text labels should appear in the generated image. Describe the visual content, colors, composition.
- `size_hint`: Suggested dimensions. Use aspect ratios like 1:1, 4:3, 3:2, 16:9 based on content type.

### For PPTX nodes:
- `pptx_intent`: Describe the intended PPTX element - shape type (rectangle, rounded_rectangle, ellipse), text content, and any style hints.
- `size_hint`: Suggested dimensions based on text length and shape type.

## Size Hint Guidelines
- Small icons/thumbnails: 80-120px
- Module boxes: 150-250px width, 60-100px height
- Input/output images: 240-400px width
- Feature maps/visualizations: 200-360px
- Text annotations: based on text length

Now classify each node and generate the render plan JSON:"""


class FilmStripVLMGroupPlanner:
    """Film-Strip Pipeline Stage 3: VLM Group Planner

    对 VLM 节点进行分组，并为每组生成连环画 prompt。
    输入: state.node_graph_json + state.render_plan_json
    输出: state.vlm_group_plan_json {groups: [{group_id, node_ids, subject, prompt}]}
    """

    system_prompt_for_filmstrip_vlm_group_planner = """You are an expert at planning visual consistency groups for scientific diagram generation.

Your task is to group VLM nodes that should be rendered together in a single "film-strip" image to ensure visual consistency.

## Why Grouping Matters
When generating scientific diagrams, related visual elements (e.g., input image and its segmentation output) must share the same visual style, scene, and subject. By generating them together in one image (as side-by-side panels), we ensure perfect consistency.

## Grouping Principles

### Group Together:
- Input/output pairs that show the same scene (e.g., RGB image → segmentation mask)
- Multiple views of the same data (e.g., original → processed → result)
- Comparison sets (e.g., before/after, method A vs method B)
- Sequential transformations of the same subject
- Nodes connected by direct data flow edges that share visual content

### Keep Separate:
- Unrelated visual content (e.g., a street scene vs. a network architecture icon)
- Nodes that don't need visual consistency
- Auxiliary visualizations that are independent

## Group Size Constraints
- Maximum nodes per group: {max_vlm_group_size} (typically 3-4)
- If more related nodes exist, split into multiple groups with overlapping context
- Single-node groups are allowed for independent visuals

## Orphan Node Handling (IMPORTANT)
- **Every VLM node MUST be assigned to exactly one group**
- Any VLM node that does not fit into a multi-node visual consistency group MUST be placed in its own single-node group
- Do NOT leave any VLM node unassigned

## Output Requirements
You must output a valid JSON object with the exact schema provided."""

    task_prompt_for_filmstrip_vlm_group_planner = """## Task
Group the VLM nodes and generate a film-strip prompt for each group.

## Input

### Node Graph
```json
{node_graph_json}
```

### Render Plan (VLM nodes to group)
```json
{render_plan_json}
```

## Configuration
- Maximum nodes per group: {max_vlm_group_size}

## Grouping Instructions

1. **Identify Related Nodes**: Look at edges and semantic relationships to find nodes that should share visual consistency.

2. **Order by Data Flow (CRITICAL)**:
   - The `node_ids` order in each group determines the panel order (left to right).
   - **Follow the data flow direction from the Node Graph edges**: upstream nodes (sources/inputs) should come BEFORE downstream nodes (outputs/results).
   - Example: If edge shows `n1 → n12` (Input Image → Predicted Seg Map), then `node_ids` should be `["n1", "n12"]`, NOT `["n12", "n1"]`.
   - This ensures logical left-to-right reading: Input → Processing → Output.

3. **Define Subject**: For each group, identify a common visual subject/scene that all panels will share.

4. **Generate Prompt**: Create a detailed prompt for the VLM to generate a film-strip image with multiple panels.

5. **Handle Orphan Nodes**: Any VLM node that cannot be grouped with others for visual consistency MUST be placed in its own single-node group. Every VLM node in `render_plan_json.vlm_nodes` must appear in exactly one group.

## Output Schema
```json
{{
  "groups": [
    {{
      "group_id": "g1",
      "node_ids": ["n1", "n12", "n14"],
      "subject": "A street scene (Cityscapes style) with cars and pedestrians, consistent lighting and perspective across all panels",
      "prompt": "You are a scientific illustrator generating images for an academic paper figure.\\n\\nGenerate ONE single image composed of 3 EQUAL-SIZED sub-panels arranged horizontally (side-by-side) with clear white gaps (about 20-30 pixels) between them.\\n\\nSubject: A street scene (Cityscapes style) with cars and pedestrians, consistent lighting and perspective across all panels\\n\\nPanel 1 (Left): The original RGB photograph of the street scene showing cars, pedestrians, buildings, and road.\\nPanel 2 (Middle): The same street scene showing semantic segmentation with distinct colors for each class (road=purple, car=blue, person=red, building=gray, sky=light blue).\\nPanel 3 (Right): The same street scene showing pseudo-label segmentation, similar to Panel 2 but with slightly noisier boundaries to indicate uncertainty.\\n\\nCRITICAL Constraints:\\n- All panels MUST depict the EXACT SAME scene/subject for visual consistency (same viewpoint, same objects, same composition).\\n- Each panel MUST be a SQUARE or near-square frame of EQUAL size.\\n- Content within each panel should be CENTERED and NOT stretched. If the natural aspect ratio differs, add white padding (letterbox/pillarbox) to maintain the square frame without distortion.\\n- Do NOT add any text, labels, numbers, legends, watermarks, or captions inside the image.\\n- Pure visual data only - no annotations.\\n- Use solid pure white (#FFFFFF) background and pure white gaps between panels.\\n- The white gaps between panels must be clearly visible and consistent width."
    }},
    {{
      "group_id": "g2",
      "node_ids": ["n2"],
      "subject": "Abstract representation of image-level class labels",
      "prompt": "You are a scientific illustrator generating images for an academic paper figure.\\n\\nGenerate ONE single image showing a visual representation of image-level classification labels.\\n\\nContent: A compact visual showing multi-label class tags or a multi-hot vector visualization. Show small colored chips or icons representing different semantic classes (e.g., 'car', 'person', 'road') arranged in a clean grid or row.\\n\\nCRITICAL Constraints:\\n- The image should be SQUARE or near-square.\\n- Content should be CENTERED with white padding if needed.\\n- Do NOT add any text, labels, or captions inside the image.\\n- Use solid pure white (#FFFFFF) background.\\n- Clean, minimal scientific illustration style."
    }}
  ]
}}
```

## Prompt Template
For each group, generate a prompt following this structure:

```
You are a scientific illustrator generating images for an academic paper figure.

Generate ONE single image composed of {{panel_count}} EQUAL-SIZED sub-panels arranged horizontally (side-by-side) with clear white gaps (about 20-30 pixels) between them.

Subject: {{subject}}

Panel 1 (Left): {{vlm_desc for first node - following data flow order}}
Panel 2 (Middle): {{vlm_desc for second node}}
[... more panels as needed, ordered by data flow ...]

CRITICAL Constraints:
- All panels MUST depict the EXACT SAME scene/subject for visual consistency (same viewpoint, same objects, same composition).
- Each panel MUST be a SQUARE or near-square frame of EQUAL size.
- Content within each panel should be CENTERED and NOT stretched. If the natural aspect ratio differs, add white padding (letterbox/pillarbox) to maintain the square frame without distortion.
- Do NOT add any text, labels, numbers, legends, watermarks, or captions inside the image.
- Pure visual data only - no annotations.
- Use solid pure white (#FFFFFF) background and pure white gaps between panels.
- The white gaps between panels must be clearly visible and consistent width.
```

For single-node groups:
```
You are a scientific illustrator generating images for an academic paper figure.

Generate ONE single image showing: {{vlm_desc}}

CRITICAL Constraints:
- The image should be SQUARE or near-square.
- Content should be CENTERED with white padding if needed to maintain aspect ratio without distortion.
- Do NOT add any text, labels, numbers, legends, watermarks, or captions inside the image.
- Use solid pure white (#FFFFFF) background.
- Clean, minimal scientific illustration style.
```

## Panel Position Labels
- 1 panel: (Center) - use single-node template
- 2 panels: (Left), (Right)
- 3 panels: (Left), (Middle), (Right)
- 4 panels: (Far Left), (Middle Left), (Middle Right), (Far Right)

## Important Notes
- **Data Flow Order**: The `node_ids` order MUST follow the data flow direction from the Node Graph edges (upstream → downstream, input → output)
- **Complete Coverage**: Every node in `render_plan_json.vlm_nodes` MUST appear in exactly one group
- Use the `vlm_desc` from `render_plan_json.by_node[node_id].vlm_desc` for each panel description
- The `subject` should describe the common visual theme that unifies all panels
- The prompt MUST explicitly require EQUAL-SIZED panels and CENTERED content with padding (not stretching)

Now analyze the VLM nodes and generate the grouping plan:"""


class FilmStripPPTXSpecGenerator:
    """Film-Strip Pipeline Stage 4: PPTX Spec Generator

    为 PPTX 节点生成结构化渲染规格。
    输入: state.node_graph_json + state.render_plan_json
    输出: state.pptx_render_specs {node_id: PPTXRenderSpec}
    """

    system_prompt_for_filmstrip_pptx_spec_generator = """You are an expert at designing PowerPoint shapes and text elements for scientific diagrams.

Your task is to generate detailed rendering specifications for PPTX nodes - elements that will be rendered as native PowerPoint shapes (rectangles, text boxes, etc.) rather than images.

You are creating camera-ready figures for top-tier ML/CV/NLP conferences (for example NeurIPS, ICML, ICLR, CVPR, ACL).
All designs must look appropriate as LaTeX paper figures: clean white background, professional and information-dense but not cluttered, with consistent style across nodes.

## Supported Element Types

### 1. `rounded_rectangle` (Most Common)
Best for: Module boxes, process blocks, components with labels
- Has rounded corners for a modern look
- Can contain centered text
- Supports fill color and border

### 2. `rectangle`
Best for: Simple containers, data blocks, strict geometric shapes
- Sharp corners
- Can contain centered text
- Supports fill color and border

### 3. `text_box`
Best for: Labels, annotations, titles, descriptions
- No visible shape boundary (transparent)
- Pure text element
- Supports text styling
- Do NOT overuse `text_box` for main modules; only use it when a node is a pure annotation without a visual container.

### 4. `arrow`
Best for: Directional annotations, flow indicators
- Currently rendered as styled text box
- Use for annotation purposes

### 5. `line`
Best for: Simple connectors, separators
- Straight line element

## Style Guidelines for Scientific Diagrams

### Color Palette (Professional Scientific Style)
- Overall palette should feel like a top-tier conference figure: 2-4 main colors plus neutral grays.
- **Primary modules**: #4A90D9 (blue), #66c2a5 (teal), #fc8d62 (orange)
- **Secondary/aux**: #8da0cb (light purple), #e78ac3 (pink), #a6d854 (green)
- **Loss/error nodes**: #e41a1c (red), #ff7f00 (orange)
- **Text on dark fill**: #FFFFFF (white)
- **Text on light/no fill**: #333333 (dark gray)
- **Borders**: Darker shade of fill color (e.g., #2E5A8C for #4A90D9)

### Font Guidelines
- **Font family**: "Arial" (universal compatibility)
- **Module labels**: 12-14pt, bold, center-aligned
- **Annotations**: 10-12pt, regular
- **Titles**: 14-16pt, bold

### Shape Sizing Hints
- Think in terms of reusable size categories, so the figure looks consistent and well-balanced.
- **Small module box**: 120-180px width, 50-70px height
- **Medium module box**: 180-260px width, 70-100px height
- **Large module box**: 260-350px width, 90-120px height
- **Text annotation**: Based on text length, typically 100-200px width

## Output Requirements
You must output a valid JSON object mapping node_id to PPTXRenderSpec.
Each spec should make the node visually expressive and clear when placed next to VLM-generated panels, following the same conference-figure style."""

    task_prompt_for_filmstrip_pptx_spec_generator = """## Task
Generate PPTX rendering specifications for all PPTX nodes.

You are designing these specs for camera-ready figures in top-tier ML/CV/NLP conference papers.
The resulting diagram should look like a clean, information-dense NeurIPS/ICML/ICLR/CVPR/ACL figure when rendered.

## Input

### Node Graph
```json
{node_graph_json}
```

### Render Plan (PPTX nodes to process)
```json
{render_plan_json}
```

## Instructions

For each node in `render_plan_json.pptx_nodes`, generate a PPTXRenderSpec based on:
1. The node's `label` from node_graph_json (use as display text)
2. The node's `role` (input/process/output/aux) to determine styling
3. The `pptx_intent` from render_plan_json.by_node[node_id] for design guidance
4. The `size_hint` from render_plan_json.by_node[node_id] for dimensions

When choosing `element_type`:
- Prefer `rounded_rectangle` or `rectangle` for main modules and meaningful blocks.
- Use `text_box` only for pure annotations, captions, or titles that should have no visible container.
- Make sure the overall mix of element types and colors makes the figure visually rich but still clean and readable.

## Output Schema
```json
{{
  "n3": {{
    "element_type": "rounded_rectangle",
    "text": "SegFormer Backbone",
    "text_style": {{
      "font_family": "Arial",
      "font_size": 14,
      "color": "#FFFFFF",
      "alignment": "center",
      "bold": true
    }},
    "shape_style": {{
      "fill_color": "#4A90D9",
      "border_style": "solid",
      "border_color": "#2E5A8C",
      "border_width": 1.5
    }},
    "auto_fit": "shrink"
  }},
  "n5": {{
    "element_type": "rounded_rectangle",
    "text": "Decoder",
    "text_style": {{
      "font_family": "Arial",
      "font_size": 12,
      "color": "#FFFFFF",
      "alignment": "center",
      "bold": true
    }},
    "shape_style": {{
      "fill_color": "#66c2a5",
      "border_style": "solid",
      "border_color": "#3A7F73",
      "border_width": 1.0
    }},
    "auto_fit": "shrink"
  }},
  "n10": {{
    "element_type": "rounded_rectangle",
    "text": "L_cls",
    "text_style": {{
      "font_family": "Arial",
      "font_size": 11,
      "color": "#FFFFFF",
      "alignment": "center",
      "bold": true
    }},
    "shape_style": {{
      "fill_color": "#e41a1c",
      "border_style": "solid",
      "border_color": "#a31515",
      "border_width": 1.0
    }},
    "auto_fit": "shrink"
  }}
}}
```

## Field Descriptions

### element_type (required)
One of: "rounded_rectangle", "rectangle", "text_box", "arrow", "line"
- Use "rounded_rectangle" for most module boxes (process, aux nodes)
- Use "text_box" for pure text annotations without shape background
- Use "rectangle" for strict geometric containers

### text (required)
The display text for the element. Usually the node's `label` from node_graph_json.
- Keep it concise (1-3 words for module boxes)
- Can use abbreviations for loss functions (e.g., "L_cls", "L_ce")

### text_style (required)
```json
{{
  "font_family": "Arial",
  "font_size": 12,
  "color": "#FFFFFF",
  "alignment": "center",
  "bold": true,
  "italic": false
}}
```
- Use white text (#FFFFFF) on dark fills
- Use dark text (#333333) on light/no fills
- alignment: "left", "center", or "right"

### shape_style (required)
```json
{{
  "fill_color": "#4A90D9",
  "border_style": "solid",
  "border_color": "#2E5A8C",
  "border_width": 1.5
}}
```
- fill_color: Hex color or null for transparent
- border_style: "solid", "dashed", or "none"
- border_color: Hex color (typically darker than fill)
- border_width: Line width in points (1.0-2.0 typical)

### auto_fit (optional)
- "shrink": Auto-shrink text to fit shape (recommended)
- "expand": Auto-expand shape to fit text
- "none": No auto-fitting

## Role-Based Styling Guidelines

### role: "process" (Main processing modules)
- element_type: "rounded_rectangle"
- fill_color: Primary colors (#4A90D9, #66c2a5, #8da0cb)
- text: Bold, white, centered
- border: Solid, darker shade

### role: "aux" (Auxiliary elements like losses)
- element_type: "rounded_rectangle" (smaller)
- fill_color: Accent colors (#e41a1c for loss, #fc8d62 for auxiliary)
- text: Bold, white, centered, smaller font
- border: Solid, darker shade

### role: "input" / "output" (If rendered as PPTX)
- element_type: "rounded_rectangle" or "text_box"
- fill_color: Lighter colors or transparent
- text: Regular or bold

Now generate the PPTX render specs for all PPTX nodes:"""
