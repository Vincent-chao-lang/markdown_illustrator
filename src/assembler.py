"""
Markdown 重组模块
将生成的图片插入到 Markdown 中，生成带配图的最终文档
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from parser import MarkdownDocument, MarkdownElement, ElementType

# 导入 Mermaid 相关函数
try:
    from mermaid_gen import is_mermaid_code, parse_mermaid_code
except ImportError:
    # 如果 mermaid_gen 不存在，提供默认实现
    def is_mermaid_code(image_path: str) -> bool:
        return isinstance(image_path, str) and image_path.startswith("MERMAID_CODE:")

    def parse_mermaid_code(image_path: str) -> tuple:
        if not is_mermaid_code(image_path):
            return None, None
        parts = image_path.split(":", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
        return None, None


class MarkdownAssembler:
    """Markdown 重组器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化重组器

        Args:
            config: 配置字典
        """
        self.config = config
        self.output_config = config.get('output', {})
        self.image_config = config.get('image', {})

        self.add_caption = self.output_config.get('add_image_caption', True)
        self.caption_format = self.output_config.get('caption_format', '*{description}*')

    def assemble(
        self,
        doc: MarkdownDocument,
        image_paths: List[Optional[str]],
        base_dir: Optional[Path] = None,
        batch_mode: bool = False
    ) -> str:
        """
        重组 Markdown，插入图片

        Args:
            doc: 解析后的文档对象
            image_paths: 图片路径列表（对应需要配图的元素）
            base_dir: 基础目录（用于计算相对路径）
            batch_mode: 批量模式（为每个位置生成了多张候选图）

        Returns:
            带配图的 Markdown 内容
        """
        lines = []
        image_index = 0

        for i, element in enumerate(doc.elements):
            # 输出原始元素内容
            lines.append(self._format_element(element))

            # 如果需要配图，插入图片
            if element.need_image and image_index < len(image_paths):
                image_path = image_paths[image_index]
                if image_path:
                    # 批量模式：image_path 是列表，需要将每个路径转换为相对路径
                    if batch_mode or isinstance(image_path, list):
                        # 转换列表中的每个路径
                        rel_path = []
                        for path in image_path:
                            if path is None:
                                rel_path.append(None)
                            elif base_dir:
                                rel_path.append(self._get_relative_path(path, base_dir))
                            else:
                                rel_path.append(path)
                    elif base_dir:
                        rel_path = self._get_relative_path(image_path, base_dir)
                    else:
                        rel_path = image_path

                    # 插入图片
                    img_lines = self._format_image(element, rel_path, batch_mode=batch_mode)
                    lines.extend(img_lines)

                image_index += 1

        return '\n\n'.join(lines)

    def _format_element(self, element: MarkdownElement) -> str:
        """
        格式化元素为 Markdown

        Args:
            element: 元素对象

        Returns:
            Markdown 格式字符串
        """
        if element.type == ElementType.HEADING:
            prefix = '#' * element.level
            return f"{prefix} {element.content}"

        elif element.type == ElementType.CODE_BLOCK:
            lines = element.content.split('\n')
            # 尝试检测语言
            lang = self._detect_language(lines[0] if lines else '')
            if lang and lang in lines[0]:
                # 第一行是语言标识
                return f"```{element.content}```"
            return f"```\n{element.content}\n```"

        elif element.type == ElementType.PARAGRAPH:
            return element.content

        elif element.type == ElementType.LIST:
            return element.content

        elif element.type == ElementType.QUOTE:
            lines = element.content.split('\n')
            return '\n'.join(f"> {line}" for line in lines)

        elif element.type == ElementType.TABLE:
            return element.content

        elif element.type == ElementType.HORIZONTAL_RULE:
            return "---"

        return element.content

    def _detect_language(self, first_line: str) -> Optional[str]:
        """检测代码块语言"""
        common_langs = [
            'python', 'javascript', 'java', 'cpp', 'c', 'go', 'rust',
            'typescript', 'jsx', 'tsx', 'html', 'css', 'json', 'yaml',
            'bash', 'shell', 'sql', 'markdown', 'latex'
        ]
        first_line = first_line.strip().lower()
        if first_line in common_langs:
            return first_line
        return None

    def _format_image(self, element: MarkdownElement, image_path: str, batch_mode: bool = False) -> List[str]:
        """
        格式化图片为 Markdown

        Args:
            element: 对应的元素
            image_path: 图片路径（或 Mermaid 代码块标记，或批量模式的候选图列表，或 A/B 测试变体列表）
            batch_mode: 批量模式标志

        Returns:
            Markdown 图片行列表
        """
        lines = []

        # A/B 测试模式：image_path 是变体字典列表
        if isinstance(image_path, list) and len(image_path) > 0 and isinstance(image_path[0], dict):
            return self._format_ab_variants(element, image_path)

        # 批量模式：image_path 可能是列表（候选图）
        if batch_mode and isinstance(image_path, list):
            return self._format_batch_candidates(element, image_path)

        # 检查是否是 Mermaid 代码块
        if is_mermaid_code(image_path):
            diagram_type, mermaid_code = parse_mermaid_code(image_path)
            if mermaid_code:
                # 格式化为 Mermaid 代码块
                lines.append("```mermaid")
                lines.append(mermaid_code)
                lines.append("```")

                # 添加说明
                if self.add_caption:
                    description = self._generate_caption(element)
                    if description:
                        lines.append(self.caption_format.format(description=description))

                return lines

        # 生成 alt 文本
        alt_text = self._generate_alt_text(element)

        # 图片语法
        lines.append(f"![{alt_text}]({image_path})")

        # 添加说明
        if self.add_caption:
            description = self._generate_caption(element)
            if description:
                lines.append(self.caption_format.format(description=description))

        return lines

    def _format_batch_candidates(self, element: MarkdownElement, candidates: List[Optional[str]]) -> List[str]:
        """
        格式化批量候选图为 Markdown

        Args:
            element: 对应的元素
            candidates: 候选图路径列表

        Returns:
            Markdown 图片行列表
        """
        lines = []

        # 找到第一个成功的候选图作为默认选择
        default_index = -1
        for i, path in enumerate(candidates):
            if path is not None:
                default_index = i
                break

        if default_index == -1:
            # 所有候选图都失败了
            return ["<!-- 所有候选图生成失败 -->"]

        # 使用第一个成功的候选图
        selected_path = candidates[default_index]
        alt_text = self._generate_alt_text(element)

        # 检查是否是 Mermaid 代码块
        if is_mermaid_code(selected_path):
            # Mermaid 代码块需要特殊处理
            diagram_type, mermaid_code = parse_mermaid_code(selected_path)
            if mermaid_code:
                lines.append(f"<!-- 候选图：从{len([c for c in candidates if c])}张中选择第{default_index + 1}张 -->")
                lines.append("```mermaid")
                lines.append(mermaid_code)
                lines.append("```")
                lines.append("")

                # 将其他候选图注释掉
                lines.append("<!-- 其他候选图已注释")
                for i, path in enumerate(candidates):
                    if path is not None and i != default_index and is_mermaid_code(path):
                        _, other_code = parse_mermaid_code(path)
                        lines.append(f"<!-- 候选{i + 1}:")
                        lines.append(f"```mermaid")
                        for line in other_code.split('\n'):
                            lines.append(f"<!-- {line} -->")
                        lines.append("```")
                        lines.append("-->")
                lines.append("-->")
        else:
            # 普通图片
            lines.append(f"<!-- 候选图：从{len([c for c in candidates if c])}张中选择第{default_index + 1}张 -->")
            lines.append(f"![{alt_text}]({selected_path}) ⭐")
            lines.append("")

            # 将其他候选图注释掉
            lines.append("<!-- 其他候选图已注释")
            for i, path in enumerate(candidates):
                if path is not None and i != default_index:
                    lines.append(f"<!-- 候选{i + 1}: ![{alt_text}]({path}) -->")
            lines.append("-->")

        # 添加说明
        if self.add_caption:
            description = self._generate_caption(element)
            if description:
                lines.append(self.caption_format.format(description=description))

        return lines

    def _format_ab_variants(self, element: MarkdownElement, variants: List[Dict[str, str]]) -> List[str]:
        """
        格式化 A/B 测试变体为 Markdown

        Args:
            element: 对应的元素
            variants: 变体列表 [{'name': 'minimal', 'description': '极简风格', 'path': '...'}]

        Returns:
            Markdown 图片行列表
        """
        lines = []

        # 找到第一个成功的变体作为默认选择
        default_index = -1
        for i, variant in enumerate(variants):
            if variant.get('path') is not None:
                default_index = i
                break

        if default_index == -1:
            # 所有变体都失败了
            return ["<!-- 所有 A/B 测试变体生成失败 -->"]

        # 使用第一个成功的变体
        selected_variant = variants[default_index]
        selected_path = selected_variant['path']
        alt_text = self._generate_alt_text(element)

        # 添加 A/B 测试注释头
        lines.append(f"<!-- A/B 测试：{len([v for v in variants if v.get('path')])} 个风格变体，选择: {selected_variant['name']} ({selected_variant['description']}) -->")

        # 检查是否是 Mermaid 代码块
        if is_mermaid_code(selected_path):
            # Mermaid 代码块需要特殊处理
            diagram_type, mermaid_code = parse_mermaid_code(selected_path)
            if mermaid_code:
                lines.append("```mermaid")
                lines.append(mermaid_code)
                lines.append("```")
                lines.append("")

                # 将其他变体注释掉
                lines.append("<!-- 其他变体已注释")
                for i, variant in enumerate(variants):
                    if i != default_index and variant.get('path') and is_mermaid_code(variant['path']):
                        _, other_code = parse_mermaid_code(variant['path'])
                        lines.append(f"<!-- 变体{i + 1}: {variant['name']} - {variant['description']}")
                        lines.append(f"```mermaid")
                        for line in other_code.split('\n'):
                            lines.append(f"<!-- {line} -->")
                        lines.append("```")
                        lines.append("-->")
                lines.append("-->")
        else:
            # 普通图片
            lines.append(f"![{alt_text} - {selected_variant['description']}]({selected_path}) ⭐")
            lines.append("")

            # 将其他变体注释掉
            lines.append("<!-- 其他变体已注释")
            for i, variant in enumerate(variants):
                if i != default_index and variant.get('path'):
                    lines.append(f"<!-- 变体{i + 1}: ![{alt_text} - {variant['description']}]({variant['path']}) -->")
            lines.append("-->")

        # 添加说明
        if self.add_caption:
            description = self._generate_caption(element)
            if description:
                lines.append(self.caption_format.format(description=description))

        return lines

    def _generate_alt_text(self, element: MarkdownElement) -> str:
        """生成图片 alt 文本"""
        if element.image_type:
            type_names = {
                'cover': '封面图',
                'section': '章节配图',
                'concept': '概念示意图',
                'atmospheric': '氛围插图',
                'diagram': '架构图'
            }
            base = type_names.get(element.image_type, '配图')

            if element.content:
                return f"{base} - {element.content[:30]}"

            return base

        return '图片'

    def _generate_caption(self, element: MarkdownElement) -> str:
        """生成图片说明"""
        if element.image_type == 'cover':
            return f"文章封面：{element.content}"
        elif element.image_type == 'section':
            return f"章节插图：{element.content}"
        elif element.image_type == 'concept':
            return f"概念示意图：{element.content}"
        elif element.image_type == 'atmospheric':
            return ""

        return ""

    def _get_relative_path(self, image_path: str, base_dir: Path) -> str:
        """
        计算相对路径

        Args:
            image_path: 图片绝对路径
            base_dir: 基础目录（Markdown 文件所在目录）

        Returns:
            相对路径字符串（相对于 base_dir）
        """
        abs_path = Path(image_path).resolve()
        base = base_dir.resolve()

        # 首先尝试计算相对于 Markdown 文件的路径
        try:
            rel_path = abs_path.relative_to(base)
            return str(rel_path).replace('\\', '/')
        except (ValueError, Exception):
            pass

        # 如果无法计算相对路径（跨磁盘或无共同父目录），
        # 使用绝对路径但标准化格式
        path_str = str(abs_path).replace('\\', '/')

        # 检查是否是 output/images 下的文件，尝试使用当前工作目录作为参考
        if 'output/images' in path_str:
            try:
                cwd = Path.cwd()
                cwd_path = cwd.resolve()
                # 尝试相对于当前工作目录
                rel_from_cwd = abs_path.relative_to(cwd_path)
                return str(rel_from_cwd).replace('\\', '/')
            except (ValueError, Exception):
                pass

        # 最后的回退：使用绝对路径
        return path_str

    def save(self, content: str, output_path: str, keep_original: bool = True):
        """
        保存 Markdown 文件

        Args:
            content: Markdown 内容
            output_path: 输出路径
            keep_original: 是否保留原始文件
        """
        output_path = Path(output_path)

        # 保留原始文件
        if keep_original and output_path.exists():
            original_path = output_path.with_suffix(
                self.output_config.get('original_suffix', '.original.md')
            )
            output_path.rename(original_path)
            print(f"原始文件已保存到: {original_path}")

        # 写入新文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"已生成带配图的文档: {output_path}")


def assemble_markdown(
    doc: MarkdownDocument,
    image_paths: List[Optional[str]],
    config: Dict[str, Any],
    output_path: Optional[str] = None,
    batch_mode: bool = False
) -> str:
    """
    重组 Markdown 的便捷函数

    Args:
        doc: 文档对象
        image_paths: 图片路径列表（或批量模式的候选图列表）
        config: 配置字典
        output_path: 输出文件路径
        batch_mode: 批量模式标志

    Returns:
        重组后的 Markdown 内容
    """
    assembler = MarkdownAssembler(config)
    base_dir = Path(output_path).parent if output_path else None

    content = assembler.assemble(doc, image_paths, base_dir, batch_mode=batch_mode)

    if output_path:
        keep_original = config.get('output', {}).get('keep_original', True)
        assembler.save(content, output_path, keep_original)

    return content
