"""
Unsplash 图库搜索模块
从 Unsplash 免费图库搜索高质量照片
"""

import os
import time
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import urllib.parse


class UnsplashImageGenerator:
    """Unsplash 图库图片生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.image_config = config.get('image', {})
        self.unsplash_config = config.get('unsplash', {})

        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Unsplash API 配置
        self.access_key = self.unsplash_config.get('access_key', '') or os.getenv('UNSPLASH_ACCESS_KEY', '')
        self.api_base = "https://api.unsplash.com"

        # 图片尺寸配置
        self.width = self.unsplash_config.get('width', 1024)
        self.height = self.unsplash_config.get('height', 768)

        # 是否需要 API Key（无 API Key 时使用公开接口）
        self.need_api_key = self.unsplash_config.get('require_api_key', False)

        if self.need_api_key and not self.access_key:
            print("  警告: 未设置 Unsplash API Key，将使用公开接口（可能不稳定）")

    def _extract_keywords(self, prompt: str) -> str:
        """
        从 prompt 中提取关键词

        Args:
            prompt: 原始 prompt

        Returns:
            提取的关键词
        """
        # 移除常见的 prompt 前缀
        prompt = prompt.lower()
        for prefix in ['create a', 'an illustration of', 'diagram showing', 'simple']:
            prompt = prompt.replace(prefix, '')

        # 提取主要关键词（简单实现）
        # 取前几个有意义的词
        words = prompt.split()
        keywords = []

        # 常见停用词
        stopwords = {'the', 'a', 'an', 'for', 'about', 'with', 'and', 'or', 'in', 'on', 'at'}

        for word in words:
            word = word.strip('.,;:!?').strip('"\'')
            if len(word) > 2 and word not in stopwords:
                keywords.append(word)
                if len(keywords) >= 3:  # 最多取3个关键词
                    break

        return ' '.join(keywords)

    def generate(self, prompt: str, index: int = 0, image_type: str = 'image', candidate_index: int = 0) -> str:
        """
        搜索并下载图片

        Args:
            prompt: 搜索提示词
            index: 图片索引
            image_type: 图片类型
            candidate_index: 候选图索引（批量模式下使用）

        Returns:
            图片路径
        """
        print(f"  正在搜索 Unsplash 图片 #{index + 1}...")

        # 提取关键词
        keywords = self._extract_keywords(prompt)
        print(f"  搜索关键词: {keywords}")

        try:
            image_url = self._search_image(keywords)
            if image_url:
                print(f"  找到图片: {image_url}")
                return self._save_image(image_url, index, image_type, candidate_index)
            else:
                raise Exception("未找到合适的图片")

        except Exception as e:
            print(f"  搜索失败: {e}")
            raise

    def _search_image(self, keywords: str) -> Optional[str]:
        """
        搜索图片

        Args:
            keywords: 搜索关键词

        Returns:
            图片 URL 或 None
        """
        # 方案1: 使用 Unsplash API（需要 Access Key）
        if self.access_key:
            return self._search_via_api(keywords)

        # 方案2: 使用 Unsplash Source（公开接口，但可能不稳定）
        return self._search_via_source(keywords)

    def _search_via_api(self, keywords: str) -> Optional[str]:
        """通过 Unsplash API 搜索"""
        url = f"{self.api_base}/search/photos"
        params = {
            'query': keywords,
            'per_page': 1,
            'orientation': 'landscape'
        }
        headers = {
            'Authorization': f'Client-ID {self.access_key}'
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('results') and len(data['results']) > 0:
                # 获取图片 URL（指定尺寸）
                photo = data['results'][0]
                return f"{photo['urls']['raw']}&w={self.width}&h={self.height}&fit=crop"

            return None

        except Exception as e:
            print(f"  API 搜索失败: {e}")
            return None

    def _search_via_source(self, keywords: str) -> str:
        """
        使用免费图库接口（无需 API Key）

        使用 LoremFlickr 作为替代方案，这是一个可靠的免费图片服务
        """
        # URL 编码关键词
        encoded_keywords = urllib.parse.quote(keywords)

        # 方案1: LoremFlickr (可靠的免费图库)
        # https://loremflickr.com/
        url = f"https://loremflickr.com/{self.width}/{self.height}/{encoded_keywords}"

        return url

    def _save_image(self, url: str, index: int, image_type: str, candidate_index: int = 0) -> str:
        """下载并保存图片"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if candidate_index > 0:
            # 批量模式：在文件名中包含候选索引
            filename = f"{index}_{image_type}_{timestamp}_{candidate_index:03d}.jpg"
        else:
            filename = f"{index}_{image_type}_{timestamp}.jpg"
        filepath = self.save_dir / filename

        # 添加请求头，避免被拒绝
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.google.com/'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"  已保存到: {filepath}")
        return str(filepath)

    def generate_batch(self, prompts: list) -> list:
        """批量搜索图片"""
        results = []
        for i, prompt in enumerate(prompts):
            try:
                image_path = self.generate(prompt, i)
                results.append(image_path)
                time.sleep(0.5)  # 避免请求过快
            except Exception as e:
                print(f"  第 {i + 1} 张图片搜索失败: {e}")
                results.append(None)
        return results


class PexelsImageGenerator:
    """Pexels 图库图片生成器（替代方案）"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.image_config = config.get('image', {})
        self.pexels_config = config.get('pexels', {})

        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Pexels API 配置
        self.api_key = self.pexels_config.get('api_key', '') or os.getenv('PEXELS_API_KEY', '')
        self.api_base = "https://api.pexels.com/v1"

        if not self.api_key:
            raise ValueError("请设置 Pexels API Key！在配置文件中设置或通过环境变量 PEXELS_API_KEY 设置")

    def _extract_keywords(self, prompt: str) -> str:
        """提取关键词"""
        # 简单实现：取前几个词
        words = prompt.split()
        keywords = []
        stopwords = {'the', 'a', 'an', 'for', 'about', 'with', 'and', 'or', 'in', 'on', 'at'}

        for word in words:
            word = word.strip('.,;:!?').strip('"\'')
            if len(word) > 2 and word not in stopwords:
                keywords.append(word)
                if len(keywords) >= 3:
                    break

        return ' '.join(keywords)

    def generate(self, prompt: str, index: int = 0, image_type: str = 'image', candidate_index: int = 0) -> str:
        """搜索并下载图片"""
        print(f"  正在搜索 Pexels 图片 #{index + 1}...")

        # 提取关键词
        keywords = self._extract_keywords(prompt)
        print(f"  搜索关键词: {keywords}")

        url = f"{self.api_base}/search"
        params = {
            'query': keywords,
            'per_page': 1,
            'orientation': 'landscape'
        }
        headers = {
            'Authorization': self.api_key
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('photos') and len(data['photos']) > 0:
                photo = data['photos'][0]
                image_url = photo['src']['large']

                print(f"  找到图片: {image_url}")
                return self._save_image(image_url, index, image_type, candidate_index)
            else:
                raise Exception("未找到合适的图片")

        except Exception as e:
            print(f"  搜索失败: {e}")
            raise

    def _save_image(self, url: str, index: int, image_type: str, candidate_index: int = 0) -> str:
        """下载并保存图片"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if candidate_index > 0:
            # 批量模式：在文件名中包含候选索引
            filename = f"{index}_{image_type}_{timestamp}_{candidate_index:03d}.jpg"
        else:
            filename = f"{index}_{image_type}_{timestamp}.jpg"
        filepath = self.save_dir / filename

        # 添加请求头
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
        """批量搜索图片"""
        results = []
        for i, prompt in enumerate(prompts):
            try:
                image_path = self.generate(prompt, i)
                results.append(image_path)
                time.sleep(0.5)
            except Exception as e:
                print(f"  第 {i + 1} 张图片搜索失败: {e}")
                results.append(None)
        return results
