"""
图片源管理器
智能选择图片来源，实现降级策略
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

# 导入各种图片生成器
sys.path.insert(0, str(Path(__file__).parent))
from image_gen import get_image_generator


class ImageSourceManager:
    """图片源管理器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化图片源管理器

        Args:
            config: 配置字典
        """
        self.config = config
        self.generators = {}  # 缓存已创建的生成器
        self.default_source = config.get('image_source', 'zhipu')

    def select_source_for_image(
        self,
        image_type: str,
        doc_type: str,
        element_content: str
    ) -> str:
        """
        为图片选择合适的图片来源

        Args:
            image_type: 图片类型 (cover, section, concept, atmospheric, diagram)
            doc_type: 文档类型 (technical, normal)
            element_content: 元素内容

        Returns:
            选择的图片来源
        """
        # 封面图统一使用 AI
        if image_type == 'cover':
            print(f"    [封面图] 选择 AI 生成")
            return self.default_source

        # 技术文档优先使用 Mermaid
        if doc_type == 'technical' and image_type in ['section', 'concept', 'diagram']:
            print(f"    [技术文档] 选择 Mermaid 图表")
            return 'mermaid'

        # 普通文档使用图库
        if doc_type == 'normal':
            print(f"    [普通文档] 选择图库 (Unsplash → Pexels → AI)")
            return 'auto_fallback'

        # 兜底：使用默认源
        return self.default_source

    def generate_with_fallback(
        self,
        prompt: str,
        index: int,
        image_type: str,
        doc_type: str,
        element_content: str = ''
    ) -> Dict[str, Any]:
        """
        使用降级策略生成图片

        Args:
            prompt: 图片提示词
            index: 图片索引
            image_type: 图片类型
            doc_type: 文档类型
            element_content: 元素内容

        Returns:
            生成结果 {
                'success': bool,
                'path': str or None,
                'source': str,
                'attempts': List[Dict]  # 尝试记录
            }
        """
        attempts = []

        # 封面图直接用 AI
        if image_type == 'cover':
            return self._try_single_source(prompt, index, image_type, self.default_source, attempts)

        # 技术文档用 Mermaid
        if doc_type == 'technical':
            result = self._try_single_source(prompt, index, image_type, 'mermaid', attempts)
            if result['success']:
                return result

        # 普通文档：按优先级尝试
        # 1. Unsplash
        result = self._try_single_source(prompt, index, image_type, 'unsplash', attempts)
        if result['success']:
            return result

        # 2. Pexels
        result = self._try_single_source(prompt, index, image_type, 'pexels', attempts)
        if result['success']:
            return result

        # 3. AI 兜底
        result = self._try_single_source(prompt, index, image_type, self.default_source, attempts)

        return result

    def _try_single_source(
        self,
        prompt: str,
        index: int,
        image_type: str,
        source: str,
        attempts: List[Dict]
    ) -> Dict[str, Any]:
        """
        尝试单个图片来源

        Args:
            prompt: 提示词
            index: 索引
            image_type: 图片类型
            source: 图片来源
            attempts: 尝试记录列表

        Returns:
            生成结果
        """
        attempt_record = {
            'source': source,
            'prompt': prompt[:100] + '...' if len(prompt) > 100 else prompt,
            'timestamp': None,
            'error': None
        }

        try:
            print(f"      尝试 {source}...", end=" ")

            # 获取或创建生成器
            if source not in self.generators:
                self.generators[source] = get_image_generator(
                    self.config,
                    use_sdk=(source == 'zhipu'),
                    image_source=source
                )

            generator = self.generators[source]

            # 生成图片
            image_path = generator.generate(prompt, index, image_type)

            attempt_record['timestamp'] = 'success'
            attempts.append(attempt_record)

            print(f"✓")
            return {
                'success': True,
                'path': image_path,
                'source': source,
                'attempts': attempts
            }

        except Exception as e:
            error_msg = str(e)
            attempt_record['error'] = error_msg
            attempts.append(attempt_record)

            print(f"✗ ({error_msg[:50]})")

            return {
                'success': False,
                'path': None,
                'source': source,
                'attempts': attempts,
                'last_error': error_msg
            }

    def get_generator(self, source: str):
        """
        获取指定源的生成器

        Args:
            source: 图片来源

        Returns:
            生成器实例
        """
        if source not in self.generators:
            self.generators[source] = get_image_generator(
                self.config,
                use_sdk=(source == 'zhipu'),
                image_source=source
            )
        return self.generators[source]

    def report_attempts(self, attempts: List[Dict]) -> str:
        """
        生成尝试记录报告

        Args:
            attempts: 尝试记录列表

        Returns:
            格式化的报告字符串
        """
        if not attempts:
            return "无尝试记录"

        lines = ["图片生成尝试记录:"]
        for i, attempt in enumerate(attempts, 1):
            status = "✓ 成功" if attempt.get('timestamp') == 'success' else f"✗ 失败: {attempt.get('error', 'unknown')[:50]}"
            lines.append(f"  {i}. {attempt['source']}: {status}")
            lines.append(f"     提示词: {attempt['prompt']}")

        return '\n'.join(lines)


# 便捷函数
def create_source_manager(config: Dict[str, Any]) -> ImageSourceManager:
    """
    创建图片源管理器

    Args:
        config: 配置字典

    Returns:
        图片源管理器实例
    """
    return ImageSourceManager(config)
