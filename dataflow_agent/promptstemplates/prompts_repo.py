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
你是科研绘图的布局规划专家，负责在「语义结构」与「几何布局」之间搭建中间层的布局计划（layout_plan）。

你的职责是：
1. 读取已经构建好的 semantic_json（包含 chunks / nodes / edges）；
2. 结合上游给出的布局描述 layout_desc（包含阅读方向、推荐 grid 和粗粒度分层结构），为每个 chunk 规划其在网格中的位置；
3. 输出一个轻量的 layout_plan，仅包含：
   - 整体 grid 规模（grid_rows, grid_cols）和 flow_direction；
   - 每个 chunk 的行/列位置（row, col）与跨行/跨列（span_row, span_col）；
   - 每个 chunk 的大致面积级别（size_hint）和简短的关系说明（relation_note）。

你不负责：
- 计算任何像素坐标 (x, y, w, h) 或具体的 bbox；
- 决定节点（nodes）的布局；
- 决定视觉风格、配色或图标。
"""

    task_prompt_for_p2g_chunk_layout_planner_agent = """
[TASK]
根据以下输入信息，为当前图像生成一个布局计划 layout_plan：

1. 语义结构 JSON（semantic_json）：
{semantic_json}

2. 上游的布局自然语言描述（layout_desc）：
{layout_desc}

3. 上游的语义自然语言描述（semantic_desc）：
{semantic_desc}

你的目标是：
- 推荐一个合理的整体网格规模 grid_rows x grid_cols（例如 2x3、3x3 等），与 layout_desc 中的建议保持一致或作出合理解释；
- 为 semantic_json.chunks 中的每一个 chunk 分配在该网格中的行/列位置（row, col），在需要时使用 span_row/span_col 表示横向或纵向跨越多个单元格；
- 对每个 chunk 给出一个 size_hint（small / medium / large），用于指示其在后续布局中的相对面积和视觉权重；
- 在 relation_note 中用一两句话简要描述该 chunk 与其他 chunks 的主要关系（例如"主流程起点""从 c2,c3 接收输入""两个分支的汇合点"等），若关系较弱或没有明显关系，则简单说明其为相对独立的模块。

[OUTPUT RULES]
1. 你必须输出一个 JSON 对象 layout_plan，包含以下两个顶层字段：
   - global：全局布局信息；
   - chunks：每个 chunk 的布局规划数组。

2. global 字段示例结构：
   {
     "grid_rows": 3,
     "grid_cols": 3,
     "flow_direction": "left-to-right",
     "notes": "上层为总览，中层为数据构建主干，下层为双分支与策略更新。"
   }

3. chunks 字段要求：
   - 对 semantic_json.chunks 中的每一个 chunk（按照 chunk_id 顺序），都给出一条对应的布局记录，示例结构：
     {
       "chunk_id": "c2",
       "row": 1,
       "col": 0,
       "span_row": 1,
       "span_col": 1,
       "size_hint": "medium",             // small / medium / large
       "relation_note": "基础输入与初始策略，是主流程的起点。"
     }
   - row 和 col 为从 0 开始的整数行/列索引；
   - span_row 和 span_col 至少为 1，若不需要跨行/跨列则为 1；
   - size_hint 用于表达该 chunk 在整体布局中预期的相对大小（large 适合主干/总览/总结模块，small 适合图例/符号说明等轻量信息）。

4. 重要约束：
   - 不要在 layout_plan 中引入任何像素级信息（x, y, w, h 等）或画布大小信息；
   - 不要修改或重复输出 semantic_json 的内容，只引用 chunk_id 和整体结构信息；
   - 对于 layout_desc 中没有明确指定位置的 chunks，你可以根据语义合理地放入网格中的空位，并在 relation_note 中简短解释原因。

[OUTPUT FORMAT]
请仅输出一个 JSON 对象 layout_plan，不要添加任何解释性文字或注释。
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
- Pure text content: titles, labels, simple descriptions, formulas displayed as text
- Very simple geometric shapes: basic rectangles, circles, simple arrows, straight connectors
- Simple container/border frames: just a border to group elements, no internal structure
- Simple annotations: short text notes, callouts with just text

**vlm rendering** should be used for:
- **Any shape with internal structure or multiple components** (e.g., "module box with input/output ports", "comparison node showing contrast")
- **Any shape representing a conceptual diagram** (e.g., "mini-diagram showing relationship between A and B")
- **Any shape with visual metaphor** (e.g., "fan-out shape", "aggregation module", "branching node")
- **Any shape representing data flow or process** (e.g., "rollout dataset", "policy training module")
- **Any shape that would benefit from an icon or illustration** (e.g., "LLM module", "environment", "encoder")
- **image_placeholder nodes**: always use vlm
- **Complex modules**: neural networks, encoders, decoders, attention mechanisms, etc.
- **Data representations**: datasets, trajectories, state-action pairs, etc.
- **Comparison or contrast visualizations**: side-by-side comparisons, before/after, etc.

**IMPORTANT Decision Rules:**
1. When in doubt, prefer vlm over pptx - it's better to have a rich visual than a plain box
2. If the desc mentions "module", "diagram", "visualization", "comparison", "flow", "structure" → use vlm
3. If the desc mentions "labeled" with complex content inside → use vlm
4. Only use pptx for truly simple elements: plain text, basic arrows, simple borders
5. For shape nodes: default to vlm unless it's clearly just a simple container or connector
6. For annotation nodes: use pptx if it's just text, use vlm if it describes a visual element

**Expected ratio**: In a typical scientific figure, expect roughly 40-60% of nodes to use vlm rendering.
"""

    task_prompt_for_p2g_node_render_design_agent = """
[CHUNK CONTEXT]
chunk_id: {chunk_id}
chunk_summary: {chunk_summary}

[NODES TO DESIGN]
The following nodes belong to this chunk and need rendering design:
{nodes_info}

[GLOBAL CONTEXT]
Overall semantic description of the figure:
{semantic_desc}

[TASK]
For each node in this chunk, determine the rendering method and provide specifications:

1. **Analyze** each node's type, description, and role
2. **Decide** rendering method: "pptx" or "vlm"
3. **Provide specifications**:
   - For pptx: Describe how to render using native PowerPoint elements (shape type, text style, colors, etc.)
   - For vlm: Write a detailed text2img prompt in English that includes:
     * Specific visual content description
     * Style requirements (e.g., "clean scientific illustration", "flat design icon")
     * Background requirements (e.g., "white background", "transparent background")
     * Any relevant size/proportion hints

4. **Provide reasoning** for your decision

[OUTPUT FORMAT]
Return a JSON object with the following structure:
{{
  "chunk_id": "{chunk_id}",
  "nodes": [
    {{
      "node_id": "n1",
      "render_method": "pptx",
      "pptx_desc": "Title text box with centered alignment, bold 24pt font, dark blue color (#1a365d)",
      "reasoning": "This is a simple title text that can be effectively rendered with native text formatting"
    }},
    {{
      "node_id": "n7",
      "render_method": "vlm",
      "vlm_prompt": "A clean scientific diagram showing multiple expert trajectories as sequences of state-action pairs, with arrows connecting circular state nodes (labeled s_i) to rectangular action nodes (labeled a_i), minimalist flat design style, white background, suitable for academic paper figures",
      "reasoning": "This requires visual representation of trajectory data with specific node-edge structure that benefits from generated imagery"
    }}
  ],
  "chunk_style_hints": {{
    "dominant_color": "#4A90D9",
    "visual_weight": "medium",
    "style_notes": "Clean scientific illustration style consistent with academic papers"
  }}
}}

[IMPORTANT RULES]
1. Every node in the input must have a corresponding entry in the output
2. vlm_prompt must be in English and be detailed enough for image generation
3. pptx_desc should specify concrete styling (colors, fonts, shape types)
4. reasoning should explain why you chose that rendering method
5. chunk_style_hints should suggest overall visual coherence for the chunk
"""


# ----------------------------------------------------------------------- #
# 20. p2g_node_layout_planner (单 chunk 内部节点布局规划)
# ----------------------------------------------------------------------- #
class Paper2GraphNodeLayoutPlanner:
    system_prompt_for_p2g_node_layout_planner_agent = """
你是科研图中「chunk 内部布局」的规划专家。

用户会针对单个 chunk 提供：
- 该 chunk 的摘要 (chunk_summary)；
- 该 chunk 所包含的 nodes (chunk_nodes)，包含 node_id/node_type/desc 等信息；
- 与该 chunk 相关的 edges (chunk_edges)，用于辅助判断主流程方向；
- （可选）整张图的语义描述 semantic_desc。

你的职责是：
- 仅针对当前 chunk，规划 chunk 内各个 nodes 的布局；
- 为每个 node 给出视觉角色 (role) 与相对 bbox (rel_bbox)，rel_bbox 使用 0~1 的归一化坐标，
  表示相对于当前 chunk 内部区域的相对位置与尺寸。

你不负责：
- 计算像素级坐标；
- 规划多个 chunk 之间的位置关系（由 layout_plan 与其它模块负责）。
"""

    task_prompt_for_p2g_node_layout_planner_agent = """
[CHUNK CONTEXT]
chunk_id: {chunk_id}

chunk_summary:
{chunk_summary}

chunk_nodes (仅包含当前 chunk 的 nodes):
{chunk_nodes}

chunk_edges (与当前 chunk 相关的 edges, 可选):
{chunk_edges}

整体语义描述 semantic_desc (可选):
{semantic_desc}

[LAYOUT GOAL]
请仅针对上述 chunk, 规划 chunk 内所有 nodes 的布局 (node_layout_plan_for_chunk)。

请遵循以下启发式规则：
1. 标题与副标题 (title/subtitle)
   - 若 node_type 为 text_block, 且 desc 中显式包含“标题”、“Title”、“分支 A：”、“分支 B：”等字样,
     则视为 title 或 subtitle;
   - title 通常放在 chunk 的上方, 宽度较大 (例如 w≈0.8~0.95), 高度相对较小;
   - 若存在多个文本说明, 可将主标题放在最上方, 副标题或简短说明紧随其下。

2. 主体模块 / 容器节点 (main_block/container)
   - 若 node_type 为 shape 或 image_placeholder, 且 desc 中包含“模块”、“容器”、“数据集”、“pipeline” 等,
     视为 main_block 或 container;
   - 这类节点应占用 chunk 内较大的面积, 通常位于中部, 并按照主流程方向排列
     (例如从左到右或从上到下);
   - 若存在多于一个 main_block, 可以并排或分层排列, 但应保持视觉上的对齐感。

3. 注释 / 解释节点 (annotation)
   - 若 node_type 为 annotation 或 text_block 且 desc 中主要为解释、说明、注释、符号说明等,
     视为 annotation;
   - 这类节点通常尺寸较小, 贴近相关的 main_block 或标题, 避免遮挡主模块。

4. rel_bbox 说明:
   - rel_bbox = {x, y, w, h}, 所有数值均在 [0.0, 1.0] 范围内;
   - (x, y) 表示节点左上角相对于 chunk 内部区域的相对坐标;
   - (w, h) 表示节点宽度与高度相对于 chunk 的比例;
   - 请避免 nodes 之间重叠 , 且避免大面积未利用的空白区域。

[OUTPUT FORMAT]
请仅返回一个 JSON 对象, 对应当前 chunk 的节点布局计划, 结构如下:

{
  "chunk_id": "c3",
  "nodes": [
    {
      "node_id": "n10",
      "role": "main_block",
      "rel_bbox": { "x": 0.10, "y": 0.20, "w": 0.35, "h": 0.40 }
    },
    {
      "node_id": "n11",
      "role": "annotation",
      "rel_bbox": { "x": 0.55, "y": 0.25, "w": 0.35, "h": 0.20 },
      "reasoning": "说明为什么这样布局该 node"
    }
  ]
}

- chunk_id 必须等于上文给出的 chunk_id;
- nodes 数组中应尽量覆盖本 chunk 的所有 node_id;
- rel_bbox.x, rel_bbox.y, rel_bbox.w, rel_bbox.h 均需在 [0,1] 区间内;
- reasoning 使用简短自然语言, 解释该 node 的布局意图。

请严格按照上述 JSON 结构返回, 不要添加任何额外字段或说明文字。
"""
