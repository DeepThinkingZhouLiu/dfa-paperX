#!/usr/bin/env python
"""测试解析问题"""
import json
from dataflow_agent.parsers.parsers import JSONParser
from dataflow_agent.utils import robust_parse_json

# 从日志中提取的 LLM 原始输出
llm_output = """{
  "enriched_description": {
    "semantic_desc": "整体是一张展示 Early Experience 范式如何衔接模仿学习（IL）与强化学习（RL）的方法框架图",
    "layout_desc": "整体建议采用自左向右、辅以上下分层的流水线式布局"
  }
}"""

print("=" * 80)
print("测试 1: robust_parse_json 直接解析")
print("=" * 80)
try:
    result1 = robust_parse_json(llm_output)
    print(f"✓ 解析成功")
    print(f"  类型: {type(result1)}")
    print(f"  keys: {list(result1.keys())}")
    if 'enriched_description' in result1:
        ed = result1['enriched_description']
        print(f"  enriched_description 类型: {type(ed)}")
        print(f"  enriched_description keys: {list(ed.keys())}")
        print(f"  semantic_desc 存在: {'semantic_desc' in ed}")
        print(f"  semantic_desc 值: {ed.get('semantic_desc', 'NOT FOUND')[:50]}...")
except Exception as e:
    print(f"✗ 解析失败: {e}")

print("\n" + "=" * 80)
print("测试 2: JSONParser.parse()")
print("=" * 80)
parser = JSONParser()
try:
    result2 = parser.parse(llm_output)
    print(f"✓ 解析成功")
    print(f"  类型: {type(result2)}")
    print(f"  keys: {list(result2.keys())}")
    if 'enriched_description' in result2:
        ed = result2['enriched_description']
        print(f"  enriched_description 类型: {type(ed)}")
        print(f"  enriched_description keys: {list(ed.keys())}")
        print(f"  semantic_desc 存在: {'semantic_desc' in ed}")
        print(f"  semantic_desc 值: {ed.get('semantic_desc', 'NOT FOUND')[:50]}...")
    elif 'raw' in result2:
        print(f"  ⚠ 解析失败，返回了 raw 字段")
        print(f"  raw 内容前100字符: {result2['raw'][:100]}")
except Exception as e:
    print(f"✗ 解析失败: {e}")

print("\n" + "=" * 80)
print("测试 3: 模拟 update_state_result 的逻辑")
print("=" * 80)

# 模拟 p2g_target_analyst_agent.py 的 update_state_result 逻辑
result = result2  # 使用 JSONParser 的结果
enriched_obj = {}

if isinstance(result, dict):
    if "error" in result:
        enriched_obj = {"semantic_desc": "", "layout_desc": "", "error": result.get("error")}
        print("  分支: error 分支")
    elif "enriched_description" in result and isinstance(result.get("enriched_description"), dict):
        enriched_obj = result.get("enriched_description")
        print("  分支: enriched_description 分支 ✓")
    else:
        # 兼容直接输出两个字段在顶层
        sd = result.get("semantic_desc")
        ld = result.get("layout_desc")
        if isinstance(sd, str) or isinstance(ld, str):
            enriched_obj = {"semantic_desc": sd or "", "layout_desc": ld or ""}
            print("  分支: 顶层字段分支")
        else:
            print("  分支: 未匹配任何分支")
elif isinstance(result, str):
    enriched_obj = {"semantic_desc": result, "layout_desc": ""}
    print("  分支: 字符串分支")
else:
    enriched_obj = {"semantic_desc": str(result), "layout_desc": ""}
    print("  分支: 其他类型分支")

print(f"\n最终 enriched_obj:")
print(f"  类型: {type(enriched_obj)}")
print(f"  keys: {list(enriched_obj.keys())}")
print(f"  semantic_desc: {enriched_obj.get('semantic_desc', 'NOT FOUND')[:50]}...")
print(f"  layout_desc: {enriched_obj.get('layout_desc', 'NOT FOUND')[:50]}...")

print("\n" + "=" * 80)
print("测试 4: 模拟 p2g_semantic_constructor_agent 读取逻辑")
print("=" * 80)

# 模拟 state.enriched_description
enriched = enriched_obj
semantic_desc = ""

if isinstance(enriched, dict):
    sd = enriched.get("semantic_desc")
    if isinstance(sd, str) and sd.strip():
        semantic_desc = sd
        print(f"  ✓ 成功提取 semantic_desc")
        print(f"    长度: {len(semantic_desc)}")
        print(f"    前50字符: {semantic_desc[:50]}...")
    else:
        print(f"  ✗ semantic_desc 为空或不是字符串")
        print(f"    sd 类型: {type(sd)}")
        print(f"    sd 值: {sd}")
elif isinstance(enriched, str):
    semantic_desc = enriched
    print(f"  分支: enriched 是字符串")
else:
    print(f"  ✗ enriched 不是 dict 也不是 str")
    print(f"    enriched 类型: {type(enriched)}")

if not semantic_desc:
    print("\n  ❌ 最终结果: semantic_desc 为空，会触发错误！")
else:
    print("\n  ✅ 最终结果: semantic_desc 不为空，可以继续")
