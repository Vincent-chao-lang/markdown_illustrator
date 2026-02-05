"""
图片生成模块
使用智谱AI CogView 模型生成图片
"""

import os
import time
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime


class ImageGenerator:
    """图片生成器（使用智谱AI CogView）"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化图片生成器

        Args:
            config: 配置字典
        """
        self.api_config = config.get('api', {})
        self.image_config = config.get('image', {})

        self.api_key = self.api_config.get('api_key', '')
        self.model = self.api_config.get('model', 'cogview-4')
        self.base_url = self.api_config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4/images/generations')
        self.timeout = self.api_config.get('timeout', 60)
        self.max_retries = self.api_config.get('max_retries', 3)

        self.size = self.image_config.get('size', '1024x1024')
        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))
        self.use_cdn = self.image_config.get('use_cdn', False)
        self.cdn_url = self.image_config.get('cdn_url', '')

        # 确保保存目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 检查 API key
        if not self.api_key:
            raise ValueError("请设置智谱AI API Key！在 config/settings.yaml 中配置或通过环境变量 ZHIPUAI_API_KEY 设置")

    def generate(self, prompt: str, index: int = 0, image_type: str = 'image', candidate_index: int = 0) -> str:
        """
        生成图片

        Args:
            prompt: 图片生成提示词
            index: 图片索引（用于命名）
            image_type: 图片类型（用于命名）
            candidate_index: 候选图索引（批量模式下使用）

        Returns:
            图片URL或本地路径
        """
        # 构建请求
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': self.model,
            'prompt': prompt,
            'size': self.size
        }

        # 重试机制
        for attempt in range(self.max_retries):
            try:
                print(f"  正在生成图片 #{index + 1} (尝试 {attempt + 1}/{self.max_retries})...")
                print(f"  Prompt: {prompt[:100]}...")

                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )

                response.raise_for_status()
                result = response.json()

                # 提取图片URL
                if 'data' in result and len(result['data']) > 0:
                    image_url = result['data'][0].get('url', '')
                    if image_url:
                        print(f"  生成成功！URL: {image_url}")

                        # 下载并保存到本地
                        local_path = self._save_image(image_url, index, image_type, candidate_index)
                        return local_path

                raise Exception("API 返回数据格式异常")

            except requests.exceptions.RequestException as e:
                print(f"  请求失败: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"  等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"图片生成失败，已重试 {self.max_retries} 次") from e

            except Exception as e:
                print(f"  生成失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                else:
                    raise

    def _save_image(self, url: str, index: int, image_type: str, candidate_index: int = 0) -> str:
        """
        下载并保存图片

        Args:
            url: 图片URL
            index: 图片索引
            image_type: 图片类型
            candidate_index: 候选图索引（批量模式下使用）

        Returns:
            本地保存路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if candidate_index > 0:
            # 批量模式：在文件名中包含候选索引
            filename = f"{index}_{image_type}_{timestamp}_{candidate_index:03d}.png"
        else:
            filename = f"{index}_{image_type}_{timestamp}.png"
        filepath = self.save_dir / filename

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(filepath, 'wb') as f:
                f.write(response.content)

            print(f"  已保存到: {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"  保存图片失败: {e}")
            return url

    def generate_batch(self, prompts: list) -> list:
        """
        批量生成图片

        Args:
            prompts: 提示词列表

        Returns:
            图片路径列表
        """
        results = []
        total = len(prompts)

        for i, prompt in enumerate(prompts):
            print(f"\n[{i + 1}/{total}] 生成图片...")
            try:
                image_path = self.generate(prompt, i)
                results.append(image_path)
                # 避免请求过快
                if i < total - 1:
                    time.sleep(1)
            except Exception as e:
                print(f"  第 {i + 1} 张图片生成失败: {e}")
                results.append(None)

        return results


# 使用 zhipuai SDK 的实现（推荐）
class ZhipuImageGenerator:
    """使用官方 SDK 的图片生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.image_config = config.get('image', {})
        self.api_config = config.get('api', {})

        self.model = self.api_config.get('model', 'cogview-4')
        self.size = self.image_config.get('size', '1024x1024')
        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))

        # 确保保存目录存在
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 导入 SDK
        try:
            from zhipuai import ZhipuAI
        except ImportError:
            raise ImportError(
                "请安装 zhipuai 包: pip install zhipuai\n"
                "或使用 ImageGenerator 类（直接调用 API）"
            )

        api_key = self.api_config.get('api_key', '')
        if not api_key:
            raise ValueError("请设置智谱AI API Key！")

        self.client = ZhipuAI(api_key=api_key)

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
        print(f"  正在生成图片 #{index + 1}...")
        print(f"  Prompt: {prompt[:100]}...")

        try:
            response = self.client.images.generations(
                model=self.model,
                prompt=prompt,
                size=self.size
            )

            image_url = response.data[0].url
            print(f"  生成成功！URL: {image_url}")

            # 保存到本地
            return self._save_image(image_url, index, image_type, candidate_index)

        except Exception as e:
            print(f"  生成失败: {e}")
            raise

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

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"  已保存到: {filepath}")
        return str(filepath)

    def generate_batch(self, prompts: list) -> list:
        """批量生成图片"""
        results = []
        total = len(prompts)

        for i, prompt in enumerate(prompts):
            print(f"\n[{i + 1}/{total}] 生成图片...")
            try:
                image_path = self.generate(prompt, i)
                results.append(image_path)
            except Exception as e:
                print(f"  第 {i + 1} 张图片生成失败: {e}")
                results.append(None)

        return results


def get_image_generator(config: Dict[str, Any], use_sdk: bool = True, image_source: str = None) -> Any:
    """
    获取图片生成器实例

    Args:
        config: 配置字典
        use_sdk: 是否使用官方SDK（仅对 zhipu 有效）
        image_source: 图片来源 (zhipu, dalle, doubao, flux, unsplash, pexels, mermaid)

    Returns:
        图片生成器实例
    """
    if image_source is None:
        image_source = config.get('image_source', 'zhipu')

    # auto 使用默认来源
    if image_source == 'auto':
        image_source = config.get('image_source', 'zhipu')

    if image_source == 'zhipu':
        if use_sdk:
            return ZhipuImageGenerator(config)
        return ImageGenerator(config)
    elif image_source == 'dalle':
        from dalle_gen import DALLEImageGenerator
        return DALLEImageGenerator(config)
    elif image_source == 'doubao':
        from doubao_gen import DoubaoImageGenerator
        return DoubaoImageGenerator(config)
    elif image_source == 'flux':
        from doubao_gen import FluxImageGenerator
        return FluxImageGenerator(config)
    elif image_source == 'unsplash':
        from unsplash_gen import UnsplashImageGenerator
        return UnsplashImageGenerator(config)
    elif image_source == 'pexels':
        from unsplash_gen import PexelsImageGenerator
        return PexelsImageGenerator(config)
    elif image_source == 'mermaid':
        from mermaid_gen import MermaidDiagramGenerator
        return MermaidDiagramGenerator(config)
    else:
        raise ValueError(f"不支持的图片来源: {image_source}")
