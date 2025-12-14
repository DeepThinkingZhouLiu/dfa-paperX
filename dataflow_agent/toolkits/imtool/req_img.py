import os
import base64
import re
from typing import Tuple, Optional

import httpx

from dataflow_agent.logger import get_logger

log = get_logger(__name__)

_B64_RE = re.compile(r"[A-Za-z0-9+/=]+")  # 匹配 Base64 字符

def extract_base64(s: str) -> str:
    """
    从任意字符串中提取最长连续 Base64 串
    """
    s = "".join(s.split())                # 去掉所有空白
    matches = _B64_RE.findall(s)          # 提取候选段
    return max(matches, key=len) if matches else ""

def _encode_image_to_base64(image_path: str) -> Tuple[str, str]:
    """
    读取本地图片并编码为 Base64，同时返回图片格式（jpeg / png）
    """
    with open(image_path, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("utf-8")

    ext = image_path.rsplit(".", 1)[-1].lower()
    if ext in {"jpg", "jpeg"}:
        fmt = "jpeg"
    elif ext == "png":
        fmt = "png"
    else:
        raise ValueError(f"Unsupported image format: {ext}")

    return b64, fmt

async def _post_chat_completions(
    api_url: str,
    api_key: str,
    payload: dict,
    timeout: int,
) -> dict:
    """
    统一的 /chat/completions POST
    """
    url = f"{api_url}/chat/completions".rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    log.info(f"POST {url}")
    log.debug(f"payload: {payload}")

    # 图像生成需要较长的 read 超时，因为模型推理可能很慢
    timeout_config = httpx.Timeout(
        connect=30.0,  # 连接超时 30 秒
        read=float(timeout),  # 读取超时使用配置的值
        write=60.0,  # 写入超时 60 秒
        pool=30.0,  # 连接池超时 30 秒
    )
    async with httpx.AsyncClient(timeout=timeout_config, http2=False) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            log.info(f"status={resp.status_code}")
            # 打印更多响应信息用于调试
            resp_text = resp.text
            log.info(f"resp.text length={len(resp_text)}")
            log.debug(f"resp.text[:1000]={resp_text[:1000]}")
            resp.raise_for_status()
            data = resp.json()
            # 打印响应结构
            log.info(f"response keys: {data.keys()}")
            if "choices" in data and data["choices"]:
                msg = data["choices"][0].get("message", {})
                log.info(f"message keys: {list(msg.keys())}")
                content = msg.get("content", "")
                log.info(f"content type: {type(content).__name__}, length: {len(str(content)) if content else 0}")
                # 打印 content 的实际内容（前500字符）- 用 WARNING 级别确保打印
                if content:
                    content_preview = str(content)[:500] if len(str(content)) > 500 else str(content)
                    log.warning(f"[DEBUG] content preview: {content_preview}")
                    # 如果 content 很短（小于 100 字符），很可能不是 base64 图片，打印警告
                    if len(str(content)) < 100:
                        log.warning(f"⚠️ content 太短，可能不是 base64 图片！实际内容: {content}")
                # 如果 content 是空的，打印完整的 message
                if not content:
                    log.warning(f"content is empty! Full message: {msg}")
                    log.warning(f"Full response: {data}")
            return data
        except httpx.HTTPStatusError as e:
            log.error(f"HTTPError {e}")
            log.error(f"Response body: {e.response.text}")
            raise


async def call_gemini_image_generation_async(
    api_url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout: int = 300,
) -> str:
    """
    纯文生图
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        # Gemini 系列要求显式指定返回图片
        "response_format": {"type": "image"},
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    data = await _post_chat_completions(api_url, api_key, payload, timeout)

    # 调试：打印完整响应结构
    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content", "")
    log.debug(f"[call_gemini_image_generation_async] message keys: {message.keys()}")
    log.debug(f"[call_gemini_image_generation_async] content length: {len(content)}, content[:100]: {content[:100] if content else '(empty)'}")

    # 检查是否有其他可能包含图像的字段
    if not content:
        log.warning(f"[call_gemini_image_generation_async] content is empty, checking other fields...")
        log.warning(f"[call_gemini_image_generation_async] Full message: {message}")
        log.warning(f"[call_gemini_image_generation_async] All response keys: {list(data.keys())}")

        # 尝试从其他可能的位置获取图像数据
        # 一些 API 可能使用 message.image 或 message.images
        if "image" in message:
            log.info(f"[call_gemini_image_generation_async] Found 'image' field in message")
            content = message["image"]
        elif "images" in message:
            log.info(f"[call_gemini_image_generation_async] Found 'images' field in message")
            content = message["images"][0] if message["images"] else ""
        # 一些 API 可能使用 content 数组格式（OpenAI vision 格式）
        elif isinstance(message.get("content"), list):
            log.info(f"[call_gemini_image_generation_async] Found list content in message")
            for item in message["content"]:
                if isinstance(item, dict):
                    if item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            # 提取 base64 部分
                            content = url.split(",", 1)[-1] if "," in url else ""
                            log.info(f"[call_gemini_image_generation_async] Extracted base64 from image_url")
                            break
                    elif item.get("type") == "image" and "data" in item:
                        content = item["data"]
                        log.info(f"[call_gemini_image_generation_async] Found image data in content item")
                        break
        # 一些 API 可能在 data 字段返回
        elif "data" in data:
            log.info(f"[call_gemini_image_generation_async] Found 'data' field in response")
            if isinstance(data["data"], list) and data["data"]:
                content = data["data"][0].get("b64_json", "") or data["data"][0].get("url", "")
        # 检查 choices[0] 是否有其他字段
        choice = data.get("choices", [{}])[0]
        if not content:
            log.warning(f"[call_gemini_image_generation_async] choice keys: {list(choice.keys())}")
            for key in ["image", "images", "b64_json", "url"]:
                if key in choice:
                    log.info(f"[call_gemini_image_generation_async] Found '{key}' in choice")
                    val = choice[key]
                    content = val[0] if isinstance(val, list) else val
                    break

    return content


async def call_gemini_image_edit_async(
    api_url: str,
    api_key: str,
    model: str,
    prompt: str,
    image_path: str,
    timeout: int = 300,
) -> str:
    """
    图像 Edit（输入文本 + 原图 -> 返回新图）
    """
    b64, fmt = _encode_image_to_base64(image_path)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/{fmt};base64,{b64}"}}
            ],
        }
    ]

    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "image"},
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    data = await _post_chat_completions(api_url, api_key, payload, timeout)
    return data["choices"][0]["message"]["content"]


# -------------------------------------------------
# 对外主接口
# -------------------------------------------------
async def generate_or_edit_and_save_image_async(
    prompt: str,
    save_path: str,
    api_url: str,
    api_key: str,
    model: str,
    *,
    image_path: Optional[str] = None,
    use_edit: bool = False,
    timeout: int = 300,
) -> str:
    """
    根据开关选择生图或编辑，并将返回的 Base64 图片保存到本地。

    参数说明
    ----------
    prompt      : 提示词
    save_path   : 保存生成图片的路径
    api_url     : OpenAI /v1 兼容地址
    api_key     : API Key
    model       : 模型名称（如 gemini-2.5-flash-image-preview）
    image_path  : 当进行 Edit 时传入原图路径
    use_edit    : True => Edit；False => 纯生图
    timeout     : 请求超时（秒）

    返回值
    ----------
    返回生成结果中的 Base64 字符串；若解析失败则抛异常
    """
    if use_edit or image_path:
        if not image_path:
            raise ValueError("use_edit=True 时必须提供 image_path")
        raw = await call_gemini_image_edit_async(
            api_url, api_key, model, prompt, image_path, timeout
        )
    else:
        raw = await call_gemini_image_generation_async(
            api_url, api_key, model, prompt, timeout
        )

    b64 = extract_base64(raw)
    if not b64:
        raise RuntimeError(f"未找到 Base64 字符串，原始响应前 200 字符: {raw[:200]}")

    # 确保保存目录存在
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(base64.b64decode(b64))

    log.info(f"图片已保存至 {save_path}")
    return b64


# -------------------------------------------------
# 当以脚本运行时做个简单示例
# -------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def _demo():
        API_URL = "http://123.129.219.111:3000/v1"
        API_KEY = os.getenv("DF_API_KEY")
        MODEL = "gemini-2.5-flash-image-preview"

        # 1) 纯文生图
        await generate_or_edit_and_save_image_async(
            prompt="一只霓虹风格的赛博朋克猫头像",
            save_path="./gen_cat.png",
            api_url=API_URL,
            api_key=API_KEY,
            model=MODEL,
            use_edit=False, 
        )

        # 2) Edit 模式
        await generate_or_edit_and_save_image_async(
            prompt="请把这只猫改成蒸汽朋克风格",
            image_path="./gen_cat.png",
            save_path="./edited_cat.png",
            api_url=API_URL,
            api_key=API_KEY,
            model=MODEL,
            use_edit=True, 
        )

    asyncio.run(_demo())