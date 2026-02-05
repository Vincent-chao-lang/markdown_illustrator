"""
豆包文生图模块
使用火山引擎 Ark API (OpenAI 兼容格式) 生成图片
"""

import os
import time
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("请安装 openai 包: pip install openai")


class DoubaoImageGenerator:
    """豆包文生图生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.image_config = config.get('image', {})
        self.doubao_config = config.get('doubao', {})

        # Ark API base URL
        self.base_url = self.doubao_config.get('base_url', 'https://ark.cn-beijing.volces.com/api/v3')
        self.model = self.doubao_config.get('model', 'ep-20260119181015-hv79s')  # endpoint ID
        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))

        # 确保保存目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 获取 API Key
        self.api_key = self.doubao_config.get('api_key', '') or os.getenv('ARK_API_KEY', '') or os.getenv('DOUBAO_API_KEY', '')

        if not self.api_key:
            raise ValueError("请设置豆包 API Key！设置环境变量 ARK_API_KEY 或 DOUBAO_API_KEY")

        # 初始化 OpenAI 客户端（指向 Ark）
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

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
        print(f"  正在生成图片 #{index + 1} (豆包)...")

        # 清理 prompt
        prompt = self._clean_prompt(prompt)
        print(f"  Prompt: {prompt[:100]}...")

        try:
            # 使用 OpenAI SDK 的 images.generate 方法
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=self.image_config.get('size', '1024x768'),
                response_format='url'
            )

            image_url = response.data[0].url
            print(f"  生成成功！URL: {image_url}")

            return self._save_image(image_url, index, image_type, candidate_index)

        except Exception as e:
            print(f"  豆包 API 调用失败: {e}")
            raise

    def _clean_prompt(self, prompt: str) -> str:
        """清理 prompt"""
        lines = prompt.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        return ' '.join(lines)

    def _save_image(self, url: str, index: int, image_type: str, candidate_index: int = 0) -> str:
        """下载并保存图片"""
        import requests

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if candidate_index > 0:
            # 批量模式：在文件名中包含候选索引
            filename = f"{index}_{image_type}_{timestamp}_{candidate_index:03d}.png"
        else:
            filename = f"{index}_{image_type}_{timestamp}.png"
        filepath = self.save_dir / filename

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
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
                time.sleep(0.5)
            except Exception as e:
                print(f"  第 {i + 1} 张图片生成失败: {e}")
                results.append(None)
        return results


# 简化版：使用 replicate 等平台接入 Flux.1
class FluxImageGenerator:
    """Flux.1 图片生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.image_config = config.get('image', {})
        self.flux_config = config.get('flux', {})

        self.model = self.flux_config.get('model', 'flux-1-pro')
        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 获取 API Key
        self.api_key = self.flux_config.get('api_key', '') or os.getenv('FLUX_API_KEY', '')
        self.api_base = self.flux_config.get('api_base', 'https://api.replicate.com/v1/predictions')

        if not self.api_key:
            raise ValueError("请设置 Flux API Key！可在 replicate.com 或其他平台获取")

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
        print(f"  正在生成图片 #{index + 1} (Flux.1)...")

        prompt = self._clean_prompt(prompt)
        print(f"  Prompt: {prompt[:100]}...")

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        # 创建预测
        data = {
            "version": "black-forest-labs/flux-1-pro",
            "input": {
                "prompt": prompt,
                "width": 1024,
                "height": 768
            }
        }

        try:
            # 提交任务
            response = requests.post(self.api_base, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            # 获取结果 URL
            get_url = result.get('urls', {}).get('get')
            if not get_url:
                raise Exception("API 返回格式异常")

            # 轮询获取结果
            image_url = self._wait_for_result(get_url, headers)
            print(f"  生成成功！URL: {image_url}")

            return self._save_image(image_url, index, image_type, candidate_index)

        except Exception as e:
            print(f"  生成失败: {e}")
            raise

    def _clean_prompt(self, prompt: str) -> str:
        """清理 prompt"""
        lines = prompt.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        return ' '.join(lines)

    def _wait_for_result(self, get_url: str, headers: Dict, max_wait: int = 120) -> str:
        """等待异步任务完成"""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = requests.get(get_url, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()

            status = result.get('status')
            if status == 'succeeded':
                return result.get('output', [])
            elif status == 'failed':
                raise Exception(f"Flux.1 生成失败: {result.get('error')}")

            print(f"  等待中... ({int(time.time() - start_time)}s)")
            time.sleep(2)

        raise Exception("生成超时")

    def _save_image(self, url: str, index: int, image_type: str, candidate_index: int = 0) -> str:
        """下载并保存图片"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if candidate_index > 0:
            # 批量模式：在文件名中包含候选索引
            filename = f"{index}_{image_type}_{timestamp}_{candidate_index:03d}.png"
        else:
            filename = f"{index}_{image_type}_{timestamp}.png"
        filepath = self.save_dir / filename

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
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
            except Exception as e:
                print(f"  第 {i + 1} 张图片生成失败: {e}")
                results.append(None)
        return results
