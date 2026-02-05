"""
增量更新模块
解析现有 Markdown 文件，支持只重新生成指定的图片
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExistingImage:
    """已存在的图片信息"""
    index: int
    image_type: str
    image_path: str
    line_number: int
    is_failed: bool = False
    prompt: str = ""


class MarkdownRegenerateParser:
    """Markdown 增量更新解析器"""

    # 图片类型到中文的映射
    TYPE_NAMES = {
        'cover': '封面图',
        'section': '章节配图',
        'concept': '概念示意图',
        'atmospheric': '氛围插图',
        'diagram': '架构图',
        'code_concept': '代码结构图',
    }

    def __init__(self, config: Dict[str, Any]):
        """
        初始化解析器

        Args:
            config: 配置字典
        """
        self.config = config

    def parse_existing_images(self, markdown_path: str) -> Tuple[List[ExistingImage], List[str]]:
        """
        解析现有 Markdown 文件，提取已生成的图片信息

        Args:
            markdown_path: Markdown 文件路径

        Returns:
            (已存在的图片列表, Markdown 按行分割的内容)
        """
        markdown_path = Path(markdown_path)
        if not markdown_path.exists():
            return [], []

        with open(markdown_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        existing_images = []

        # 正则模式匹配图片
        # 格式1: ![alt](path)
        # 格式2: ![alt](path) ⭐
        # 格式3: Mermaid 代码块
        image_pattern = re.compile(r'!\[([^\]]+)\]\(([^)]+)\)')
        mermaid_start_pattern = re.compile(r'^```mermaid')

        in_mermaid_block = False
        mermaid_lines = []
        mermaid_start_line = 0

        # 统计每种类型的图片数量
        type_counters = {img_type: 0 for img_type in self.TYPE_NAMES.keys()}

        for line_num, line in enumerate(lines):
            line_stripped = line.strip()

            # 检查 Mermaid 代码块开始（支持多种格式）
            # 格式1: ```mermaid
            # 格式2: ``` (后面跟 mermaid 代码)
            # 格式3: ``` 后面跟空行，再跟 mermaid 关键字
            if line_stripped.startswith('```'):
                next_line = lines[line_num + 1].strip() if line_num + 1 < len(lines) else ''
                next_next_line = lines[line_num + 2].strip() if line_num + 2 < len(lines) else ''

                # 检查下一行是否包含 Mermaid 关键字
                has_mermaid_keywords = any(keyword in next_next_line.lower()
                                             for keyword in ['statediagram', 'sequencediagram',
                                                           'flowchart', 'flowchart TD',
                                                           'classdiagram', 'mindmap',
                                                           'gantt', 'erdiagram'])

                if 'mermaid' in line_stripped.lower() or has_mermaid_keywords:
                    in_mermaid_block = True
                    mermaid_start_line = line_num
                    mermaid_lines = []
                    continue

            if in_mermaid_block:
                if line.strip().startswith('```') and 'mermaid' not in line:
                    # Mermaid 代码块结束
                    in_mermaid_block = False

                    # 解析图片类型和索引
                    image_type = self._parse_image_type_from_context(
                        lines, mermaid_start_line, line_num
                    )

                    if image_type:
                        index = type_counters[image_type]
                        type_counters[image_type] += 1

                        # 构建 Mermaid 代码
                        mermaid_code = '\n'.join(mermaid_lines)

                        existing_images.append(ExistingImage(
                            index=index,
                            image_type=image_type,
                            image_path=f"MERMAID_CODE:{image_type}:{mermaid_code}",
                            line_number=mermaid_start_line,
                            is_failed=False
                        ))
                    mermaid_lines = []
                else:
                    # 收集代码块内容（排除第一行的 ```mermaid）
                    if not line.strip().startswith('```mermaid'):
                        mermaid_lines.append(line.rstrip())
                continue

            # 检查失败的图片标记
            if '<!-- 所有候选图生成失败 -->' in line:
                # 尝试解析失败图片的信息
                image_type, index = self._parse_image_info_from_context(lines, line_num)
                if image_type and index is not None:
                    existing_images.append(ExistingImage(
                        index=index,
                        image_type=image_type,
                        image_path="",
                        line_number=line_num,
                        is_failed=True
                    ))
                continue

            # 检查普通图片
            match = image_pattern.search(line)
            if match:
                alt_text = match.group(1)
                image_path = match.group(2)

                # 跳过非自动生成的图片（没有特定标记的）
                if not self._is_auto_generated_image(alt_text):
                    continue

                # 跳过 Mermaid 代码块标记
                if image_path.startswith("MERMAID_CODE:"):
                    continue

                image_type, index = self._parse_image_info_from_alt_text(alt_text)

                if image_type and index is not None:
                    existing_images.append(ExistingImage(
                        index=index,
                        image_type=image_type,
                        image_path=image_path,
                        line_number=line_num,
                        is_failed=False
                    ))

        return existing_images, lines

    def _parse_image_type_from_context(self, lines: List[str], start_line: int, end_line: int) -> Optional[str]:
        """
        从上下文中解析图片类型

        Args:
            lines: 所有行
            start_line: Mermaid 代码块开始行
            end_line: Mermaid 代码块结束行

        Returns:
            图片类型
        """
        # 检查前后的注释和说明
        context_start = max(0, start_line - 10)
        context_end = min(len(lines), end_line + 5)
        context = '\n'.join(lines[context_start:context_end])

        # 检查候选图注释
        if '<!-- 候选图：从' in context:
            # 尝试从注释行推断类型
            for img_type, cn_name in self.TYPE_NAMES.items():
                if cn_name in context:
                    return img_type

        # 检查图片说明
        for img_type, cn_name in self.TYPE_NAMES.items():
            # 匹配 "文章封面"、"章节插图" 等
            if f"文章{cn_name.replace('图', '')}" in context:
                return 'cover' if img_type == 'cover' else img_type
            # 匹配 "章节插图"、"概念示意图" 等
            if cn_name in context:
                return img_type

        # 根据 Mermaid 代码内容推断类型
        mermaid_code = '\n'.join(lines[start_line:end_line])
        if 'stateDiagram' in mermaid_code:
            return 'concept'  # 状态图通常用于概念说明
        elif 'sequenceDiagram' in mermaid_code:
            return 'section'  # 时序图通常用于章节说明
        elif 'flowchart' in mermaid_code:
            return 'code_concept'  # 流程图通常用于代码结构说明
        elif 'classDiagram' in mermaid_code:
            return 'concept'
        elif 'mindmap' in mermaid_code:
            return 'cover'  # 思维导图通常用于封面

        return None

    def _parse_image_info_from_context(self, lines: List[str], line_num: int) -> Tuple[Optional[str], Optional[int]]:
        """
        从上下文中解析图片信息（索引和类型）

        Args:
            lines: 所有行
            line_num: 当前行号

        Returns:
            (图片类型, 索引)
        """
        # 向上查找候选图标记
        for i in range(max(0, line_num - 10), line_num):
            line = lines[i].strip()
            if '<!-- 候选图：从' in line:
                # 格式: <!-- 候选图：从3张中选择第1张 -->
                # 这说明是一个批量生成的图片，但没有明确的索引
                # 尝试从前面的内容推断
                continue

            if line.startswith('<!-- 候选') and '选择第' in line:
                # 尝试提取索引
                match = re.search(r'选择第(\d+)张', line)
                if match:
                    index = int(match.group(1)) - 1  # 转换为0-based
                else:
                    index = 0

                # 从文件名推断类型
                for img_type, cn_name in self.TYPE_NAMES.items():
                    if cn_name in line or img_type in line.lower():
                        return img_type, index

        # 从 alt text 推断
        if line_num > 0:
            prev_lines = '\n'.join(lines[max(0, line_num - 5):line_num])
            for img_type, cn_name in self.TYPE_NAMES.items():
                if cn_name in prev_lines:
                    # 查找这个类型第几张图
                    pattern = f"{cn_name}"
                    count = prev_lines.count(pattern)
                    return img_type, count - 1

        return None, None

    def _parse_image_info_from_alt_text(self, alt_text: str) -> Tuple[Optional[str], Optional[int]]:
        """
        从 alt text 解析图片信息

        Args:
            alt_text: 图片 alt 文本

        Returns:
            (图片类型, 索引)
        """
        for img_type, cn_name in self.TYPE_NAMES.items():
            if cn_name in alt_text:
                return img_type, None

        return None, None

    def _is_auto_generated_image(self, alt_text: str) -> bool:
        """
        判断是否是自动生成的图片

        Args:
            alt_text: 图片 alt 文本

        Returns:
            是否是自动生成的
        """
        # 检查是否包含我们的类型标记
        for cn_name in self.TYPE_NAMES.values():
            if cn_name in alt_text:
                return True

        return False

    def filter_images_to_regenerate(
        self,
        existing_images: List[ExistingImage],
        decisions: List[Any],
        regenerate_index: Optional[int] = None,
        regenerate_type: Optional[str] = None,
        regenerate_failed: bool = False
    ) -> List[int]:
        """
        根据过滤条件找出需要重新生成的图片索引

        Args:
            existing_images: 已存在的图片列表
            decisions: 当前的配图决策列表
            regenerate_index: 指定要重新生成的索引
            regenerate_type: 指定要重新生成的类型
            regenerate_failed: 是否只重新生成失败的图片

        Returns:
            需要重新生成的决策索引列表
        """
        to_regenerate = []

        if regenerate_index is not None:
            # 按索引过滤
            if 0 <= regenerate_index < len(decisions):
                to_regenerate.append(regenerate_index)

        elif regenerate_type:
            # 按类型过滤
            for i, decision in enumerate(decisions):
                if decision.image_type == regenerate_type:
                    to_regenerate.append(i)

        elif regenerate_failed:
            # 只重新生成失败的图片
            for img in existing_images:
                if img.is_failed:
                    # 找到对应的决策索引
                    if img.index < len(decisions):
                        to_regenerate.append(img.index)

        else:
            # 如果没有指定任何条件，返回空列表（不重新生成）
            pass

        return sorted(set(to_regenerate))

    def create_regenerate_plan(
        self,
        existing_images: List[ExistingImage],
        decisions: List[Any],
        regenerate_indices: List[int]
    ) -> Dict[str, Any]:
        """
        创建重新生成计划

        Args:
            existing_images: 已存在的图片列表
            decisions: 当前的配图决策列表
            regenerate_indices: 需要重新生成的索引

        Returns:
            重新生成计划
        """
        plan = {
            'keep': [],  # 保留的图片
            'regenerate': [],  # 需要重新生成的
            'missing': []  # 新增的（原有文件中不存在）
        }

        existing_indices = {img.index for img in existing_images}

        for i, decision in enumerate(decisions):
            if i in regenerate_indices:
                plan['regenerate'].append({
                    'index': i,
                    'image_type': decision.image_type,
                    'prompt': decision.prompt,
                    'reason': decision.reason
                })
            elif i in existing_indices:
                # 保留现有图片
                existing_img = next(img for img in existing_images if img.index == i)
                plan['keep'].append({
                    'index': i,
                    'image_path': existing_img.image_path,
                    'image_type': existing_img.image_type
                })
            else:
                # 新增的图片位置
                plan['missing'].append({
                    'index': i,
                    'image_type': decision.image_type,
                    'prompt': decision.prompt,
                    'reason': decision.reason
                })

        return plan


def parse_for_regeneration(
    markdown_path: str,
    config: Dict[str, Any],
    decisions: List[Any],
    regenerate_index: Optional[int] = None,
    regenerate_type: Optional[str] = None,
    regenerate_failed: bool = False
) -> Dict[str, Any]:
    """
    解析 Markdown 文件并生成重新生成计划的便捷函数

    Args:
        markdown_path: Markdown 文件路径
        config: 配置字典
        decisions: 当前的配图决策列表
        regenerate_index: 指定要重新生成的索引
        regenerate_type: 指定要重新生成的类型
        regenerate_failed: 是否只重新生成失败的图片

    Returns:
        重新生成计划
    """
    parser = MarkdownRegenerateParser(config)

    # 解析现有图片
    existing_images, _ = parser.parse_existing_images(markdown_path)

    print(f"  现有图片数量: {len(existing_images)}")
    for img in existing_images:
        status = "失败" if img.is_failed else "成功"
        print(f"    #{img.index}: {img.image_type} - {status}")

    # 过滤出需要重新生成的
    regenerate_indices = parser.filter_images_to_regenerate(
        existing_images,
        decisions,
        regenerate_index,
        regenerate_type,
        regenerate_failed
    )

    print(f"  需要重新生成: {len(regenerate_indices)} 个位置")
    for idx in regenerate_indices:
        print(f"    位置 #{idx}")

    # 创建计划
    plan = parser.create_regenerate_plan(existing_images, decisions, regenerate_indices)

    return plan
