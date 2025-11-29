#!/usr/bin/env python3
"""
使用 VLM 根据图片生成 PaperGraph JSON（v0.2）描述

用法:
    python test_papergraph_vlm_gen.py [<image_path>] \
        --output <output.json> \
        --vision-model <vision_model_name> \
        --json-model <json_model_name> \
        [--schema <schema.md>] [--api-url <url>] [--api-key <key>]

说明:
    - <image_path> 可省略，默认使用 /mnt/DataFlow/lz/proj/agentgroup/zewei/iconagent/dfa-paperX/tests/test.png
    - 两阶段模型：
        1) 阶段1: 视觉理解（识图->详细文本描述），默认 gemini-2.5-flash-image-preview
        2) 阶段2: 文本到 JSON 结构化，默认 gpt-o3

示例:
    export DF_API_URL=http://123.129.219.111:3000/v1
    export DF_API_KEY=sk-xxx
    
    python iconagent/dfa-paperX/tests/test_papergraph_vlm_gen.py \
        /mnt/DataFlow/lz/proj/agentgroup/zewei/iconagent/dfa-paperX/tests/test.png \
        --schema iconagent/dfa-paperX/papergraph_schema_v0.2.md \
        --vision-model gemini-2.5-flash-image-preview \
        --json-model gpt-5 \
        --output /mnt/DataFlow/lz/proj/agentgroup/zewei/iconagent/dfa-paperX/tests/test_generated.json
"""

import os
import sys
import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from langchain_core.messages import HumanMessage

# 添加项目路径以便导入
_script_dir = Path(__file__).parent.resolve()
_project_dir = _script_dir.parent  # tests -> dfa-paperX
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))

try:
    from dataflow_agent.llm_callers.image import VisionLLMCaller
    from dataflow_agent.llm_callers.text import TextLLMCaller
except ImportError:
    # 如果导入失败，尝试添加父目录
    _parent_dir = _project_dir.parent
    if str(_parent_dir) not in sys.path:
        sys.path.insert(0, str(_parent_dir))
    from dataflow_agent.llm_callers.image import VisionLLMCaller
    from dataflow_agent.llm_callers.text import TextLLMCaller


def extract_json_template_from_schema(schema_path: str) -> tuple[str, str]:
    """
    从 schema markdown 文件中提取 JSON 模板与规范说明（v0.2）

    优先提取 ```json 代码块作为模板；
    其余文本（剔除代码块）作为规范说明，以便放入 Prompt。

    Returns:
        (json_template, field_descriptions)
    """
    schema_file = Path(schema_path)
    file_size = schema_file.stat().st_size
    print(f"   Schema 文件路径: {schema_path}")
    print(f"   Schema 文件大小: {file_size:,} 字节 ({file_size / 1024:.2f} KB)")

    with open(schema_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"   Schema 文件内容长度: {len(content):,} 字符")

    # 提取 JSON 模板（在 ```json 和 ``` 之间）
    json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    json_template = json_match.group(1) if json_match else ""

    if json_template:
        print(f"   ✅ JSON 模板提取成功，长度: {len(json_template):,} 字符")
    else:
        print(f"   ⚠️  警告: 未找到 JSON 模板")

    # 生成规范说明：移除所有 ```...``` 代码块后的纯文本
    cleaned = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    field_descriptions = cleaned.strip()
    print(f"   ✅ 规范说明提取成功，长度: {len(field_descriptions):,} 字符")

    return json_template, field_descriptions


def build_image_description_prompt() -> str:
    """
    构建第一步的 prompt：要求 VLM 详细描述图片内容
    """
    prompt = """你是一个科研绘图分析专家。请仔细分析给定的科研绘图图片，并提供详细、完整、结构化的文本描述。

## 任务要求

请从以下几个方面详细描述图片内容：

1. **整体布局**：
   - 图片的整体结构（行数、列数、主要区域划分）
   - 各个区域的位置关系和排列方式
   - 图片的主要视觉元素和组成

2. **模块和组件**：
   - 识别图片中的所有模块、组件、节点
   - 描述每个模块/组件的内容、功能和作用
   - 说明模块之间的层次关系

3. **连接关系**：
   - 识别所有连接线、箭头、数据流
   - 描述连接的方向、类型和含义
   - 说明数据流、控制流或依赖关系

4. **文本和标签**：
   - 识别图片中的所有文本、标签、标题
   - 描述文本的位置和含义
   - 说明文本与图形元素的对应关系

5. **视觉特征**：
   - 颜色、形状、大小等视觉特征
   - 特殊标记、图例、说明等

## 输出要求

- 描述要详细、完整、准确
- 使用结构化的方式组织描述（可以使用标题、列表等）
- 确保不遗漏任何重要的视觉元素
- 描述要清晰、有条理，便于后续转换为结构化数据

请开始详细描述这张科研绘图的内容："""
    
    return prompt


def build_json_generation_prompt(text_description: str, json_template: str, field_descriptions: str) -> str:
    """
    构建第二步的 prompt：根据文本描述生成符合 v0.2 Schema 的 JSON
    - 必须为 groups/nodes/edges 提供非空的 description 字段
    - 不保存 edges 的折线路径坐标（由求解器计算）
    - positions 为可选输出（承载 bbox），单位继承 canvas.unit
    """
    prompt = f"""你是一个数据转换专家。请根据以下详细的图片描述，生成符合 v0.2 JSON Schema 的结构化数据对象。

## 图片的详细描述

{text_description}

## JSON Schema 模板

```json
{json_template}
```

## 字段说明

{field_descriptions}

## 任务要求

1. 仔细分析上述图片描述，理解图片结构与内容。
2. 根据描述确定网格布局：填写 `grid.rows` 与 `grid.cols`。
3. 识别 Chunks：划分各区域为 chunk，填写 `chunks[].grid_area`（行列从 0 开始）。
4. 识别 Groups：组织语义分组，填写 `groups[].chunks` 与 `groups[].description`（必填），可选 `title`。
5. 识别 Nodes：每个最小可绘制元素作为一个 node，填写 `nodes[].group`、`nodes[].type/role` 与 `nodes[].description`（必填）。
6. 识别 Edges：填写 `edges[].source/target/type/route_hint/direction_hint` 与 `edges[].description`（必填）。不保存折线路径坐标。
7. 可选填写 `positions`：若可推断元素位置，提供 `positions.groups[].bbox` 与 `positions.nodes[].bbox`，单位继承 `canvas.unit`。

## 重要提示

1. groups/nodes/edges 的 `description` 字段为必填，用于下游 VLM 生图的提示词主体。
2. ID 命名规范：`chunk_r_c`、`grp_*`、`node*`、`e*` 等具有语义的标识。
3. grid_area 的 `row/col` 从 0 开始计数。
4. 避免编造不存在的元素，确保语义一致性。

请直接输出符合上述 Schema 的完整 JSON 对象，不要包含任何额外的解释文字。确保 JSON 格式正确且可以被解析。"""
    
    return prompt


def extract_json_from_response(response: str) -> Optional[dict]:
    """
    从 VLM 响应中提取 JSON 对象
    
    尝试多种方法：
    1. 查找 ```json ... ``` 代码块
    2. 查找第一个 { ... } 对象
    3. 直接解析整个响应
    """
    print(f"   响应内容长度: {len(response):,} 字符")
    
    # 方法1: 查找 ```json ... ``` 代码块
    print("   🔍 方法1: 尝试从 ```json ... ``` 代码块中提取...")
    json_block_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
    if json_block_match:
        json_str = json_block_match.group(1)
        print(f"      ✅ 找到 JSON 代码块，长度: {len(json_str):,} 字符")
        try:
            result = json.loads(json_str)
            print(f"      ✅ JSON 解析成功！")
            return result
        except json.JSONDecodeError as e:
            print(f"      ❌ JSON 解析失败: {e}")
            print(f"      错误位置: 第 {e.lineno} 行，第 {e.colno} 列")
    else:
        print(f"      ⚠️  未找到 ```json ... ``` 代码块")
    
    # 方法2: 查找第一个完整的 JSON 对象 { ... }
    print("   🔍 方法2: 尝试从响应中查找第一个 JSON 对象 { ... }...")
    json_obj_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_obj_match:
        json_str = json_obj_match.group(0)
        print(f"      ✅ 找到 JSON 对象，长度: {len(json_str):,} 字符")
        print(f"      对象预览: {json_str[:200]}...")
        try:
            result = json.loads(json_str)
            print(f"      ✅ JSON 解析成功！")
            return result
        except json.JSONDecodeError as e:
            print(f"      ❌ JSON 解析失败: {e}")
            print(f"      错误位置: 第 {e.lineno} 行，第 {e.colno} 列")
    else:
        print(f"      ⚠️  未找到 JSON 对象")
    
    # 方法3: 直接解析整个响应
    print("   🔍 方法3: 尝试直接解析整个响应...")
    try:
        result = json.loads(response)
        print(f"      ✅ JSON 解析成功！")
        return result
    except json.JSONDecodeError as e:
        print(f"      ❌ JSON 解析失败: {e}")
        print(f"      错误位置: 第 {e.lineno} 行，第 {e.colno} 列")
    
    print("   ❌ 所有方法都失败了，无法提取 JSON")
    return None


async def generate_image_description(
    image_path: str,
    model_name: str,
    api_url: str,
    api_key: str,
    timeout: int,
    max_tokens: Optional[int] = None
) -> str:
    """
    第一步：调用 VLM 生成图片的详细文本描述
    
    Args:
        image_path: 输入图片路径
        model_name: VLM 模型名称
        api_url: API URL
        api_key: API Key
        timeout: 请求超时时间（秒）
        max_tokens: 最大 token 数
    
    Returns:
        图片的详细文本描述
    """
    from types import SimpleNamespace
    
    print("\n" + "="*60)
    print("📋 步骤 1: 生成图片的详细文本描述")
    print("="*60)
    
    # 构建 prompt
    prompt = build_image_description_prompt()
    estimated_tokens = len(prompt) // 4
    print(f"   Prompt 长度: {len(prompt):,} 字符")
    print(f"   估算 token 数: ~{estimated_tokens:,} tokens")
    
    # 构造 MainState
    request = SimpleNamespace(
        chat_api_url=api_url.rstrip("/"),
        api_key=api_key,
        model=model_name
    )
    state = SimpleNamespace(request=request)
    
    # 实例化 VisionLLMCaller
    if max_tokens is None:
        max_tokens = 32768 if "gpt-5" in model_name.lower() or "qwen-max" in model_name.lower() else 8192
    
    caller = VisionLLMCaller(
        state=state,
        vlm_config={
            "mode": "understanding",
            "input_image": str(image_path),
            "timeout": timeout,
        },
        model_name=model_name,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    
    # 调用 VLM
    print(f"   模型: {model_name}")
    print(f"   最大 token 数: {max_tokens}")
    import datetime
    start_time = datetime.datetime.now()
    print(f"   开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ⏳ 正在分析图片并生成描述...")
    
    try:
        ai_msg = await caller.call([HumanMessage(content=prompt)])
        end_time = datetime.datetime.now()
        elapsed_seconds = (end_time - start_time).total_seconds()
        print(f"   结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   耗时: {elapsed_seconds:.2f} 秒 ({elapsed_seconds / 60:.2f} 分钟)")
        print(f"   ✅ 图片描述生成成功")
        
        description = ai_msg.content
        if not description or not description.strip():
            raise ValueError("生成的图片描述为空")
        
        print(f"   描述长度: {len(description):,} 字符")
        print(f"   描述预览（前300字符）: {description[:300]}...")
        
        return description
    except Exception as e:
        print(f"   ❌ 图片描述生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise


async def generate_json_from_description(
    text_description: str,
    json_template: str,
    field_descriptions: str,
    model_name: str,
    api_url: str,
    api_key: str,
    timeout: int,
    max_tokens: Optional[int] = None
) -> dict:
    """
    第二步：根据文本描述生成符合 schema 的 JSON
    
    Args:
        text_description: 第一步生成的图片文本描述
        json_template: JSON 模板
        field_descriptions: 字段说明
        model_name: VLM 模型名称
        api_url: API URL
        api_key: API Key
        timeout: 请求超时时间（秒）
        max_tokens: 最大 token 数
    
    Returns:
        生成的 JSON 字典
    """
    from types import SimpleNamespace
    
    print("\n" + "="*60)
    print("📋 步骤 2: 根据文本描述生成 JSON")
    print("="*60)
    
    # 构建 prompt
    prompt = build_json_generation_prompt(text_description, json_template, field_descriptions)
    estimated_tokens = len(prompt) // 4
    print(f"   Prompt 长度: {len(prompt):,} 字符")
    print(f"   估算 token 数: ~{estimated_tokens:,} tokens")
    print(f"   文本描述长度: {len(text_description):,} 字符")
    
    # 构造 MainState
    request = SimpleNamespace(
        chat_api_url=api_url.rstrip("/"),
        api_key=api_key,
        model=model_name
    )
    state = SimpleNamespace(request=request)
    
    # 实例化 VisionLLMCaller（这次不需要图片）
    if max_tokens is None:
        max_tokens = 32768 if "gpt-5" in model_name.lower() or "qwen-max" in model_name.lower() else 8192
    
    caller = TextLLMCaller(
        state=state,
        model_name=model_name,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    
    # 调用 VLM（这次只传文本，不传图片）
    print(f"   模型: {model_name}")
    print(f"   最大 token 数: {max_tokens}")
    import datetime
    start_time = datetime.datetime.now()
    print(f"   开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ⏳ 正在根据描述生成 JSON...")
    
    try:
        ai_msg = await caller.call([HumanMessage(content=prompt)])
        end_time = datetime.datetime.now()
        elapsed_seconds = (end_time - start_time).total_seconds()
        print(f"   结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   耗时: {elapsed_seconds:.2f} 秒 ({elapsed_seconds / 60:.2f} 分钟)")
        print(f"   ✅ JSON 生成成功")
        
        response_content = ai_msg.content
        if not response_content or not response_content.strip():
            raise ValueError("生成的 JSON 内容为空")
        
        # 提取 JSON
        print("\n" + "-"*60)
        print("💾 提取 JSON 数据")
        print("-"*60)
        json_data = extract_json_from_response(response_content)
        
        if json_data is None:
            print("\n" + "="*60)
            print("❌ JSON 提取失败")
            print("="*60)
            print("   响应内容预览（前500字符）:")
            print("   " + "\n   ".join(response_content[:500].split("\n")))
            print("\n   响应内容预览（后500字符）:")
            if len(response_content) > 500:
                print("   " + "\n   ".join(response_content[-500:].split("\n")))
            raise ValueError("无法解析 JSON，请检查 VLM 响应")
        
        return json_data
    except Exception as e:
        print(f"   ❌ JSON 生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise


async def generate_papergraph_json(
    image_path: str,
    schema_path: str,
    output_path: Optional[str] = None,
    vision_model_name: str = "gemini-2.5-flash-image-preview",
    json_model_name: str = "gpt-o3",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 300,
    max_tokens: Optional[int] = None,
    save_description: bool = True
) -> dict:
    """
    使用两步法根据图片生成 PaperGraph JSON：
    1. 第一步：调用 VLM 生成图片的详细文本描述
    2. 第二步：根据文本描述生成符合 schema 的 JSON
    
    Args:
        image_path: 输入图片路径
        schema_path: Schema 文件路径
        output_path: 输出 JSON 文件路径（可选）
        model_name: VLM 模型名称
        api_url: API URL（默认从环境变量读取）
        api_key: API Key（默认从环境变量读取）
        timeout: 请求超时时间（秒）
        max_tokens: 最大 token 数（默认: gpt-5 使用 32768，其他模型使用 8192）
        save_description: 是否保存中间结果（文本描述）
    
    Returns:
        生成的 JSON 字典
    """
    # 1. API 配置：从环境变量读取，如果没有则使用默认值
    print("="*60)
    print("📋 步骤 1: 配置 API 参数")
    print("="*60)
    
    # 默认 API URL
    DEFAULT_API_URL = "http://123.129.219.111:3000/v1"
    
    # 优先使用传入的参数，其次使用环境变量，最后使用默认值
    api_url = api_url or os.getenv("DF_API_URL", DEFAULT_API_URL)
    api_key = api_key or os.getenv("DF_API_KEY")
    
    print(f"   API URL: {api_url}")
    print(f"   API Key: {'已设置' if api_key else '未设置'} ({'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'N/A'})")
    print(f"   阶段1视觉模型: {vision_model_name}")
    print(f"   阶段2JSON模型: {json_model_name}")
    
    if not api_key:
        raise ValueError(
            "API Key 未设置。请通过以下方式之一设置：\n"
            "  1. 环境变量: export DF_API_KEY=your_api_key\n"
            "  2. 命令行参数: --api-key your_api_key"
        )
    
    # 2. 检查文件是否存在
    print("\n" + "="*60)
    print("📋 步骤 2: 检查输入文件")
    print("="*60)
    
    image_path = Path(image_path).expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")
    
    image_size = image_path.stat().st_size
    print(f"   ✅ 图片文件存在: {image_path}")
    print(f"   图片大小: {image_size:,} 字节 ({image_size / 1024:.2f} KB)")
    
    # 检查图片大小，给出建议
    if image_size > 5 * 1024 * 1024:  # 5MB
        print(f"   ⚠️  警告: 图片较大（>{image_size / 1024 / 1024:.2f} MB），可能导致请求超时")
        print(f"      建议: 压缩图片或增加超时时间（当前: {timeout}秒）")
    elif image_size > 2 * 1024 * 1024:  # 2MB
        print(f"   ⚠️  提示: 图片较大（{image_size / 1024 / 1024:.2f} MB），base64 编码后约为 {image_size * 1.37 / 1024 / 1024:.2f} MB")
        print(f"      如果遇到超时，建议增加 --timeout 参数（当前: {timeout}秒）")
    
    schema_path = Path(schema_path).expanduser().resolve()
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema 文件不存在: {schema_path}")
    
    print(f"   ✅ Schema 文件存在: {schema_path}")
    
    # 3. 提取 JSON 模板和字段说明
    print("\n" + "="*60)
    print("📋 步骤 3: 读取并解析 Schema 文件")
    print("="*60)
    json_template, field_descriptions = extract_json_template_from_schema(str(schema_path))
    
    # 4. 第一步：生成图片的详细文本描述
    text_description = await generate_image_description(
        image_path=str(image_path),
        model_name=vision_model_name,
        api_url=api_url,
        api_key=api_key,
        timeout=timeout,
        max_tokens=max_tokens
    )
    
    # 保存文本描述（如果启用）
    description_path = None
    if save_description and output_path:
        description_path = Path(str(output_path).replace('.json', '_description.txt'))
        try:
            description_path.parent.mkdir(parents=True, exist_ok=True)
            with open(description_path, 'w', encoding='utf-8') as f:
                f.write(text_description)
            print(f"\n💾 图片描述已保存到: {description_path}")
        except Exception as e:
            print(f"⚠️  保存图片描述失败: {e}")
    
    # 5. 第二步：根据文本描述生成 JSON
    json_data = await generate_json_from_description(
        text_description=text_description,
        json_template=json_template,
        field_descriptions=field_descriptions,
        model_name=json_model_name,
        api_url=api_url,
        api_key=api_key,
        timeout=timeout,
        max_tokens=max_tokens
    )
    
    # 9. 保存结果
    print("\n" + "="*60)
    print("📋 步骤 9: 保存结果")
    print("="*60)
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ JSON 已保存到: {output_path}")
        print(f"   文件大小: {output_path.stat().st_size:,} 字节")
    else:
        print("   ✅ JSON 解析成功（未指定输出路径，未保存文件）")
    
    # 统计信息
    print("\n" + "="*60)
    print("📊 生成结果统计")
    print("="*60)
    print(f"   节点数量: {len(json_data.get('nodes', []))}")
    print(f"   边数量: {len(json_data.get('edges', []))}")
    print(f"   Chunks 数量: {len(json_data.get('chunks', []))}")
    print(f"   Groups 数量: {len(json_data.get('groups', []))}")
    if 'grid' in json_data:
        grid = json_data['grid']
        print(f"   网格布局: {grid.get('rows', 'N/A')} 行 × {grid.get('cols', 'N/A')} 列")
    
    return json_data


async def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="使用 VLM 根据图片生成 PaperGraph JSON 格式描述"
    )
    parser.add_argument(
        "image_path",
        nargs='?',
        default="/mnt/DataFlow/lz/proj/agentgroup/zewei/iconagent/dfa-paperX/tests/test.png",
        type=str,
        help="输入图片路径（默认: /mnt/DataFlow/lz/proj/agentgroup/zewei/iconagent/dfa-paperX/tests/test.png）"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Schema 文件路径（默认: 自动查找 papergraph_schema_v0.2.md）"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出 JSON 文件路径（默认: <image_name>_papergraph.json）"
    )
    parser.add_argument(
        "--vision-model",
        type=str,
        default="gemini-2.5-flash-image-preview",
        help="阶段1视觉理解模型（默认: gemini-2.5-flash-image-preview）"
    )
    parser.add_argument(
        "--json-model",
        type=str,
        default="gpt-o3",
        help="阶段2 JSON 生成模型（默认: gpt-o3）"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help="API URL（默认从环境变量 DF_API_URL 读取，如果未设置则使用 http://123.129.219.111:3000/v1）"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API Key（默认从环境变量 DF_API_KEY 读取，必须设置）"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="请求超时时间（秒，默认: 300，gpt-5处理图像需要较长时间）"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="最大 token 数（默认: gpt-5/qwen-max-latest 使用 32768，其他模型使用 8192。如果遇到 token 耗尽错误，建议增加到 65536 或更大）"
    )
    
    args = parser.parse_args()
    
    # 打印启动信息
    print("="*60)
    print("🚀 PaperGraph VLM 生成工具")
    print("="*60)
    print(f"   输入图片: {args.image_path}")
    print(f"   阶段1视觉模型: {args.vision_model}")
    print(f"   阶段2JSON模型: {args.json_model}")
    if args.max_tokens:
        print(f"   最大 token 数: {args.max_tokens}")
    if args.timeout:
        print(f"   超时时间: {args.timeout}秒")
    print("="*60)
    print()
    
    # 如果没有指定输出路径，自动生成
    if not args.output:
        image_name = Path(args.image_path).stem
        args.output = f"{image_name}_papergraph.json"
        print(f"📝 未指定输出路径，自动生成: {args.output}")
        print()
    
    try:
        # 获取项目根目录（从 tests/ 目录向上两级到项目根）
        script_dir = Path(__file__).parent.resolve()
        project_root = script_dir.parent.parent  # tests -> dfa-paperX -> project_root
        
        # 处理 schema 路径
        print("🔍 查找 Schema 文件...")
        if args.schema:
            print(f"   使用指定的 schema 路径: {args.schema}")
            if Path(args.schema).is_absolute():
                schema_path = Path(args.schema)
            else:
                # 先尝试相对于项目根目录
                schema_path = project_root / args.schema
                if not schema_path.exists():
                    # 如果不存在，尝试相对于当前工作目录
                    schema_path = Path(args.schema).resolve()
        else:
            # 默认查找 schema 文件：先尝试 dfa-paperX 目录下，再尝试项目根目录
            print("   未指定 schema 路径，尝试自动查找...")
            schema_path = script_dir.parent / "papergraph_schema_v0.2.md"
            print(f"   尝试路径 1: {schema_path}")
            if not schema_path.exists():
                schema_path = project_root / "iconagent/dfa-paperX/papergraph_schema_v0.2.md"
                print(f"   尝试路径 2: {schema_path}")
            if not schema_path.exists():
                raise FileNotFoundError(
                    f"无法找到 schema 文件。请使用 --schema 参数指定路径。\n"
                    f"已尝试查找:\n"
                    f"  - {script_dir.parent / 'papergraph_schema_v0.2.md'}\n"
                    f"  - {project_root / 'iconagent/dfa-paperX/papergraph_schema_v0.2.md'}"
                )
        
        print(f"   ✅ Schema 文件: {schema_path}")
        print()
        
        # 处理输出路径
        if Path(args.output).is_absolute():
            output_path = Path(args.output)
        else:
            # 默认保存到 tests 目录
            output_path = script_dir / args.output
        
        json_data = await generate_papergraph_json(
            image_path=args.image_path,
            schema_path=str(schema_path),
            output_path=str(output_path),
            vision_model_name=args.vision_model,
            json_model_name=args.json_model,
            api_url=args.api_url,
            api_key=args.api_key,
            timeout=args.timeout,
            max_tokens=args.max_tokens
        )
        
        print("\n" + "="*60)
        print("✅ 任务完成！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
