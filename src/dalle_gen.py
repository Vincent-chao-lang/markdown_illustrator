"""
DALL-E 3 图片生成模块
使用 OpenAI API 生成高质量图片
"""

import os
import time
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime


class DALLEImageGenerator:
    """DALL-E 3 图片生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.image_config = config.get('image', {})
        self.api_config = config.get('dalle', {})

        self.model = self.api_config.get('model', 'dall-e-3')
        self.size = self.api_config.get('size', '1024x1024')
        self.quality = self.api_config.get('quality', 'standard')  # standard or hd
        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))

        # 确保保存目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 获取 API Key
        self.api_key = self.api_config.get('api_key', '') or os.getenv('OPENAI_API_KEY', '')
        if not self.api_key:
            raise ValueError("请设置 OpenAI API Key！在配置文件中设置或通过环境变量 OPENAI_API_KEY 设置")

    def generate(self, prompt: str, index: int = 0, image_type: str = 'image', candidate_index: int = 0) -> str:
        """
        生成图片

        Args:
            prompt: 图片生成提示词
            index: 图片索引
            image_type: 图片类型
            candidate_index: 候选图索引（批量模式下使用）

        Returns:
            图片路径
        """
        print(f"  正在生成图片 #{index + 1} (DALL-E 3)...")

        # 清理 prompt - 移除多余空白和换行
        prompt = self._clean_prompt(prompt)

        # DALL-E 3 有 4000 字符限制
        max_length = 3800  # 留一些余量
        if len(prompt) > max_length:
            prompt = prompt[:max_length]
            print(f"  Prompt 过长，已截断到 {max_length} 字符")

        print(f"  Prompt: {prompt[:150]}...")

        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": self.size,
            "quality": self.quality
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)

            # 打印详细错误信息
            if response.status_code != 200:
                print(f"  API 错误 ({response.status_code}): {response.text}")

            response.raise_for_status()
            result = response.json()

            image_url = result['data'][0]['url']
            print(f"  生成成功！URL: {image_url}")

            return self._save_image(image_url, index, image_type, candidate_index)

        except Exception as e:
            print(f"  生成失败: {e}")
            raise

    def _clean_prompt(self, prompt: str) -> str:
        """
        清理 prompt

        Args:
            prompt: 原始 prompt

        Returns:
            清理后的 prompt
        """
        # 移除多余的空白和换行
        lines = prompt.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        cleaned = ' '.join(lines)

        # 移除引号（可能导致 API 解析问题）
        cleaned = cleaned.replace('"', '').replace("'", "")

        return cleaned

    def _save_image(self, url: str, index: int, image_type: str, candidate_index: int = 0) -> str:
        """下载并保存图片"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if candidate_index > 0:
            # 批量模式：在文件名中包含候选索引
            filename = f"{index}_{image_type}_{timestamp}_{candidate_index:03d}.png"
        else:
            filename = f"{index}_{image_type}_{timestamp}.png"
        filepath = self.save_dir / filename

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"  已保存到: {filepath}")
        return str(filepath)

    def generate_batch(self, prompts: list) -> list:
        """批量生成图片"""
        results = []
        for i, prompt in enumerate(prompts):
            try:
                image_path = self.generate(prompt, i)
                results.append(image_path)
                time.sleep(1)  # 避免请求过快
            except Exception as e:
                print(f"  第 {i + 1} 张图片生成失败: {e}")
                results.append(None)
        return results
