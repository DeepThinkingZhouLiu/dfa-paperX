import base64
from typing import Any, Dict, List
from dataflow_agent.state import MainState
from langchain_core.messages import AIMessage, BaseMessage
import aiohttp

from dataflow_agent.llm_callers.base import BaseLLMCaller
from dataflow_agent.logger import get_logger

log = get_logger(__name__)

class VisionLLMCaller(BaseLLMCaller):
    """视觉LLM调用器 - 支持图像输入/输出"""
    
    def __init__(self, 
                 state: MainState,
                 vlm_config: Dict[str, Any],
                 **kwargs):
        """
        Args:
            vlm_config: VLM配置，包含：
                - mode: "generation" | "edit" | "understanding"
                - input_image: 输入图像路径（edit/understanding模式）
                - output_image: 输出图像保存路径（generation/edit模式）
                - response_format: "image" | "text" (默认根据mode自动判断)
        """
        super().__init__(state, **kwargs)
        self.vlm_config = vlm_config
        self.mode = vlm_config.get("mode", "understanding")
    
    async def call(self, messages: List[BaseMessage], bind_post_tools: bool = False) -> AIMessage:
        """调用VLM"""
        log.info(f"VisionLLM调用，模型: {self.model_name}, 模式: {self.mode}")
        
        if self.mode in ["generation", "edit"]:
            return await self._call_image_output(messages)
        else:
            return await self._call_image_understanding(messages)
        
    async def _call_image_understanding(self, messages: List[BaseMessage]) -> AIMessage:
        """图像理解模式 - 输入图像，输出文本"""

        ROLE_MAP = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
            "tool": "tool",
        }

        processed_messages: List[Dict[str, Any]] = []
        for msg in messages:
            lc_role = getattr(msg, "type", "human")     # human / ai / system / tool
            role     = ROLE_MAP.get(lc_role, "user")    # 兜底用 "user"

            processed_messages.append({
                "role": role,
                "content": msg.content                  # str 或 multimodal list 都行
            })

        # --------  如有 input_image，把图贴到最后一条 user 消息里 --------
        if "input_image" in self.vlm_config and processed_messages:
            b64, fmt = self._encode_image(self.vlm_config["input_image"])
            last_msg = processed_messages[-1]
            if last_msg["role"] == "user":
                last_msg["content"] = [
                    {"type": "text",  "text": last_msg["content"]},
                    {"type": "image_url",
                    "image_url": {"url": f"data:image/{fmt};base64,{b64}"}}
                ]

        payload = {
            "model": self.model_name,
            "messages": processed_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        response_data = await self._post_chat_completions(payload)
        
        # 调试：记录响应结构
        log.debug(f"API响应结构: {type(response_data)}, keys: {response_data.keys() if isinstance(response_data, dict) else 'N/A'}")
        
        # 提取内容，添加错误处理
        if "choices" not in response_data:
            log.error(f"API响应缺少 'choices' 字段。响应内容: {response_data}")
            raise ValueError(f"API响应格式错误: 缺少 'choices' 字段。响应: {response_data}")
        
        if not response_data["choices"]:
            log.error(f"API响应中 'choices' 为空。响应内容: {response_data}")
            raise ValueError(f"API响应格式错误: 'choices' 为空。响应: {response_data}")
        
        message = response_data["choices"][0].get("message", {})
        content = message.get("content")
        
        if content is None:
            log.error(f"API响应中 'content' 为 None。响应内容: {response_data}")
            raise ValueError(f"API响应格式错误: 'content' 为 None。响应: {response_data}")
        
        if not content.strip():
            log.warning(f"API响应中 'content' 为空字符串。响应内容: {response_data}")
        
        return AIMessage(content=content)
    
    # async def _call_image_understanding(self, messages: List[BaseMessage]) -> AIMessage:
    #     """图像理解模式 - 输入图像，输出文本"""
    #     # 这个还有bug！！！


    #     import httpx
        
    #     # 构建包含图像的消息
    #     processed_messages = []
    #     for msg in messages:
    #         if hasattr(msg, 'content') and isinstance(msg.content, str):
    #             processed_messages.append({
    #                 "role": msg.type if hasattr(msg, 'type') else "user",
    #                 "content": msg.content
    #             })
        
    #     # 如果配置了输入图像，添加到最后一条消息
    #     if "input_image" in self.vlm_config:
    #         b64, fmt = self._encode_image(self.vlm_config["input_image"])
            
    #         # 修改最后一条用户消息为多模态格式
    #         last_msg = processed_messages[-1]
    #         if last_msg["role"] == "user":
    #             last_msg["content"] = [
    #                 {"type": "text", "text": last_msg["content"]},
    #                 {"type": "image_url", 
    #                  "image_url": {"url": f"data:image/{fmt};base64,{b64}"}}
    #             ]
        
    #     # 调用API
    #     payload = {
    #         "model": self.model_name,
    #         "messages": processed_messages,
    #         "temperature": self.temperature,
    #         "max_tokens": self.max_tokens,
    #     }
        
    #     response_data = await self._post_chat_completions(payload)
    #     content = response_data["choices"][0]["message"]["content"]
        
    #     return AIMessage(content=content)
    
    async def _call_image_output(self, messages: List[BaseMessage]) -> AIMessage:
        """图像生成/编辑模式 - 输出图像"""
        from dataflow_agent.toolkits.imtool.req_img import generate_or_edit_and_save_image_async

        # 提取prompt（最后一条用户消息）
        prompt = ""
        for msg in reversed(messages):
            if hasattr(msg, 'content'):
                prompt = msg.content
                break

        # 调用图像生成函数
        save_path = self.vlm_config.get("output_image", "./generated_image.png")
        image_path = self.vlm_config.get("input_image") if self.mode == "edit" else None

        # VLM 生图优先使用 VLM_API_URL 和 VLM_API_KEY，如果没有设置则回退到 state 中的配置
        api_url = os.getenv("VLM_API_URL") or self.state.request.chat_api_url
        api_key = os.getenv("VLM_API_KEY") or self.state.request.api_key

        # 记录使用的 API 配置来源
        vlm_url_source = "VLM_API_URL" if os.getenv("VLM_API_URL") else "state.request"
        vlm_key_source = "VLM_API_KEY" if os.getenv("VLM_API_KEY") else "state.request"
        log.debug(f"VLM image generation using: url from {vlm_url_source}, key from {vlm_key_source}")

        b64 = await generate_or_edit_and_save_image_async(
            prompt=prompt,
            save_path=save_path,
            api_url=api_url,
            api_key=api_key,
            model=self.model_name,
            image_path=image_path,
            use_edit=(self.mode == "edit"),
            timeout=self.vlm_config.get("timeout", 120),
        )
        
        # 返回图像路径作为内容
        content = f"图像已生成并保存至: {save_path}"
        
        return AIMessage(content=content, additional_kwargs={
            "image_path": save_path,
            "image_base64": b64,
        })
    
    def _encode_image(self, image_path: str) -> tuple:
        """编码图像为base64"""
        with open(image_path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("utf-8")
        
        ext = image_path.rsplit(".", 1)[-1].lower()
        if ext in {"jpg", "jpeg"}:
            fmt = "jpeg"
        elif ext == "png":
            fmt = "png"
        else:
            raise ValueError(f"不支持的图像格式: {ext}")
        
        return b64, fmt
    
    async def _post_chat_completions(self, payload: dict) -> dict:
        """调用chat completions API"""
        import httpx

        # VLM 优先使用 VLM_API_URL 和 VLM_API_KEY，如果没有设置则回退到 state 中的配置
        chat_api_url = os.getenv("VLM_API_URL") or self.state.request.chat_api_url
        api_key = os.getenv("VLM_API_KEY") or self.state.request.api_key

        base_url = chat_api_url.rstrip("/")

        # 检查是否是 Google AI Studio API（generativelanguage.googleapis.com）
        # 如果是，URL 已经是完整端点，不需要添加 /chat/completions
        if "generativelanguage.googleapis.com" in base_url:
            url = base_url
        elif base_url.endswith("/v1") or base_url.endswith("/v1beta"):
            # OpenAI 兼容格式，需要添加 /chat/completions
            url = f"{base_url}/chat/completions"
        else:
            # URL 已经是完整端点，直接使用
            url = base_url

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        timeout = self.vlm_config.get("timeout", 120)
        # 对于大图片和长时间处理，需要设置更详细的超时参数
        # connect: 连接超时（较短）
        # read: 读取超时（最重要，需要足够长以处理大图片和推理）
        # write: 写入超时（发送大图片时需要较长）
        # pool: 连接池超时
        timeout_config = httpx.Timeout(
            connect=30.0,  # 连接超时 30 秒
            read=float(timeout),  # 读取超时使用配置的值
            write=float(timeout),  # 写入超时（发送大图片需要时间）
            pool=30.0  # 连接池超时 30 秒
        )
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        

# ======================================================================
# CLI：支持生图 / 编辑 / 图像理解
# ======================================================================
if __name__ == "__main__":
    import os
    import sys
    import asyncio
    import argparse
    from types import SimpleNamespace
    from pathlib import Path
    from langchain_core.messages import HumanMessage

    def _build_parser() -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            description="VisionLLMCaller: generation | edit | understanding"
        )
        p.add_argument(
            "--mode",
            choices=["generation", "edit", "understanding"],
            default="generation",
            help="模式：生图(generation)、编辑(edit)、图像理解(understanding)"
        )
        p.add_argument(
            "--prompt",
            type=str,
            default=None,
            help="提示词；generation/edit 推荐必填，understanding 可选"
        )
        p.add_argument(
            "--prompt-file",
            type=str,
            default=None,
            help="从文件读取提示词，优先于 --prompt，支持 .txt 等纯文本文件"
        )
        p.add_argument(
            "--input-image",
            type=str,
            default=None,
            help="输入图像路径（edit/understanding 需要）"
        )
        p.add_argument(
            "--output-image",
            type=str,
            default="./out/generated_image.png",
            help="输出图像保存路径（generation/edit 有效)"
        )
        p.add_argument(
            "--model",
            type=str,
            default=None,
            help="模型名称，默认读取环境变量 DF_MODEL 或使用内置默认"
        )
        p.add_argument(
            "--timeout",
            type=int,
            default=120,
            help="请求超时（秒）"
        )
        return p

    async def _run_with_args(args: argparse.Namespace) -> int:
        api_url = os.getenv("DF_API_URL")
        api_key = os.getenv("DF_API_KEY")
        if not api_url or not api_key:
            print("❌ 请先设置环境变量 DF_API_URL / DF_API_KEY")
            return 2

        model = args.model or os.getenv("DF_MODEL", "gemini-2.5-flash-image-preview")

        # 参数校验
        if args.mode in ("edit", "understanding"):
            if not args.input_image:
                print("❌ 该模式需要 --input-image")
                return 2
            img_path = Path(args.input_image).expanduser().resolve()
            if not img_path.exists():
                print(f"❌ 图片不存在: {img_path}")
                return 2
            input_image = str(img_path)
        else:
            input_image = None

        # 读取提示词：优先使用 --prompt-file，其次使用 --prompt，最后使用模式默认占位词
        prompt = None
        if args.prompt_file:
            pf = Path(args.prompt_file).expanduser().resolve()
            if not pf.exists() or not pf.is_file():
                print(f"❌ 提示词文件不存在或不是文件: {pf}")
                return 2
            try:
                prompt_text = pf.read_text(encoding="utf-8")
            except Exception as e:
                print(f"❌ 读取提示词文件失败: {e}")
                return 2
            prompt = prompt_text.rstrip('\n')
            print(f"ℹ️ 已从文件读取提示词: {pf}")
        elif args.prompt:
            prompt = args.prompt
        else:
            if args.mode in ("generation", "edit"):
                print("ℹ️ 未提供 --prompt 或 --prompt-file，将使用一个占位提示词。")
            prompt = ("描述这个图像" if args.mode == "understanding" else "请生成一张图像")

        # 构造 state
        state = SimpleNamespace(request=SimpleNamespace(
            chat_api_url=api_url.rstrip("/"),
            api_key=api_key,
            model=model,
        ))

        # 组装配置
        vlm_cfg = {
            "mode": args.mode,
            "timeout": args.timeout,
        }
        if args.mode in ("generation", "edit"):
            vlm_cfg["output_image"] = args.output_image
        if args.mode in ("edit", "understanding") and input_image:
            vlm_cfg["input_image"] = input_image

        caller = VisionLLMCaller(state=state, vlm_config=vlm_cfg)

        print("🚀 正在请求模型，请稍候 …")
        ai_msg = await caller.call([HumanMessage(content=prompt)])

        # 输出结果
        if args.mode in ("generation", "edit"):
            print(ai_msg.content)
            print("image_path=", ai_msg.additional_kwargs.get("image_path"))
        else:
            print("\n================  文本结果  ================")
            print(ai_msg.content)
            print("==========================================")
        return 0

    parser = _build_parser()
    ns = parser.parse_args()
    try:
        exit_code = asyncio.run(_run_with_args(ns))
    except KeyboardInterrupt:
        exit_code = 130
    sys.exit(exit_code)
