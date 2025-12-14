#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gemini 图片生成 - Python版本
支持非流式输出和自动保存base64图片到本地
"""

import requests
import json
import base64
import re
import os
import datetime
from typing import Optional, Tuple

class GeminiImageGenerator:
    def __init__(self, api_key: str, api_url: str = "https://api.apiyi.com/v1/chat/completions"):
        """
        初始化Gemini图片生成器
        
        Args:
            api_key: API密钥
            api_url: API地址
        """
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def generate_image(self, prompt: str, model: str = "gemini-2.5-flash-image",
                      output_dir: str = ".") -> Tuple[bool, str]:
        """
        生成图片并保存到本地
        
        Args:
            prompt: 图片描述提示词
            model: 使用的模型
            output_dir: 输出目录
            
        Returns:
            Tuple[是否成功, 结果消息]
        """
        print("🚀 开始生成图片...")
        print(f"提示词: {prompt}")
        print(f"模型: {model}")
        
        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"gemini_generated_{timestamp}.png")
        
        try:
            # 准备请求数据
            payload = {
                "model": model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            print("📡 发送API请求...")
            
            # 发送非流式请求
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=300
            )
            
            if response.status_code != 200:
                error_msg = f"API请求失败，状态码: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f", 错误详情: {error_detail}"
                except:
                    error_msg += f", 响应内容: {response.text[:500]}"
                return False, error_msg
            
            print("✅ API请求成功，正在解析响应...")
            
            # 解析非流式JSON响应
            try:
                result = response.json()
                print("✅ 成功解析JSON响应")
            except json.JSONDecodeError as e:
                return False, f"JSON解析失败: {str(e)}"
            
            # 提取消息内容
            full_content = ""
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    full_content = choice["message"]["content"]
            
            if not full_content:
                return False, "未找到消息内容"
            
            print(f"📝 获取到消息内容，长度: {len(full_content)} 字符")
            print("🔍 正在解析图片数据...")
            
            # 提取并保存图片（支持base64和URL两种方式）
            success, message = self._extract_and_save_images(full_content, output_file)
            
            if success:
                return True, message
            else:
                return False, f"图片保存失败: {message}"
                
        except requests.exceptions.Timeout:
            return False, "请求超时（300秒）"
        except requests.exceptions.ConnectionError as e:
            return False, f"连接错误: {str(e)}"
        except Exception as e:
            return False, f"未知错误: {str(e)}"
    
    def _extract_and_save_images(self, content: str, base_output_file: str) -> Tuple[bool, str]:
        """
        高效提取并保存base64图片数据
        
        Args:
            content: 包含图片数据的内容
            base_output_file: 基础输出文件路径
            
        Returns:
            Tuple[是否成功, 结果消息]
        """
        try:
            print(f"📄 内容预览（前200字符）: {content[:200]}")
            
            # 使用精确的正则表达式一次性提取base64图片数据
            base64_pattern = r'data:image/([^;]+);base64,([A-Za-z0-9+/=]+)'
            match = re.search(base64_pattern, content)
            
            if not match:
                print('⚠️  未找到base64图片数据')
                return False, "响应中未包含base64图片数据"
            
            image_format = match.group(1)  # png, jpg, etc.
            b64_data = match.group(2)
            
            print(f'🎨 图像格式: {image_format}')
            print(f'📏 Base64数据长度: {len(b64_data)} 字符')
            
            # 解码并保存图片
            image_data = base64.b64decode(b64_data)
            
            if len(image_data) < 100:
                return False, "解码后的图片数据太小，可能无效"
            
            # 根据检测到的格式设置文件扩展名
            output_file = base_output_file.replace('.png', f'.{image_format}')
            os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
            
            with open(output_file, 'wb') as f:
                f.write(image_data)
            
            print(f'🖼️  图片保存成功: {output_file}')
            print(f'📊 文件大小: {len(image_data)} 字节')
            
            return True, f"图片保存成功: {output_file}"
                
        except Exception as e:
            return False, f"处理图片时发生错误: {str(e)}"

def main():
    """
    主函数
    """
    # 配置参数
    API_KEY = "sk-6KMJ4eaW8Mqom0kcBe07673e7d2a400bBeE559C5A868F96b"  # 请替换为你的实际API密钥
    PROMPT = "画一张英文的弱监督语义分割论文中的科研配图，图像级标签，单阶段方法，直接通过segformer的backbone提取特征图，这里首先有一个分类损失，然后是解码器生成预测的分割图，还有一路生成伪标签，对预测的分割图进行交叉熵损失的监督，创新点是像素级学习不足，输入层新增定位专用token，更小的patch聚类、Memory bank, Adapter"
    
    print("="*60)
    print("Gemini 图片生成器 - Python版本")
    print("="*60)
    print(f"开始时间: {datetime.datetime.now()}")
    
    # 创建生成器实例
    generator = GeminiImageGenerator(API_KEY)
    
    # 生成图片
    success, message = generator.generate_image(PROMPT)
    
    print("\n" + "="*60)
    if success:
        print("🎉 执行成功！")
        print(f"✅ {message}")
    else:
        print("❌ 执行失败！")
        print(f"💥 {message}")
    
    print(f"结束时间: {datetime.datetime.now()}")
    print("="*60)

if __name__ == "__main__":
    main()