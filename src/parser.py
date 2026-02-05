"""
Markdown 解析模块
负责解析 Markdown 文件，提取标题、段落、代码块等元素
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ElementType(Enum):
    """元素类型"""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    LIST = "list"
    QUOTE = "quote"
    HORIZONTAL_RULE = "horizontal_rule"
    TABLE = "table"
    EMPTY = "empty"


@dataclass
class MarkdownElement:
    """Markdown 元素"""
    type: ElementType
    content: str
    level: int = 0  # 标题层级
    position: int = 0  # 在原文中的位置
    raw_line: str = ""  # 原始行内容

    # 统计信息
    word_count: int = 0
    line_count: int = 0

    # 配图决策
    need_image: bool = False
    image_type: Optional[str] = None
    image_prompt: Optional[str] = None

    def __post_init__(self):
        """初始化后计算统计信息"""
        self.word_count = len(re.sub(r'\s+', '', self.content))

    @property
    def is_heading(self) -> bool:
        return self.type == ElementType.HEADING

    @property
    def is_paragraph(self) -> bool:
        return self.type == ElementType.PARAGRAPH

    @property
    def is_code_block(self) -> bool:
        return self.type == ElementType.CODE_BLOCK


@dataclass
class MarkdownDocument:
    """Markdown 文档"""
    elements: List[MarkdownElement] = field(default_factory=list)
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 分析结果
    theme: str = ""
    keywords: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.elements)

    def __getitem__(self, index: int) -> MarkdownElement:
        return self.elements[index]

    def add_element(self, element: MarkdownElement):
        """添加元素"""
        element.position = len(self.elements)
        self.elements.append(element)

    def get_headings(self, level: Optional[int] = None) -> List[MarkdownElement]:
        """获取所有标题"""
        headings = [e for e in self.elements if e.is_heading]
        if level is not None:
            headings = [e for e in headings if e.level == level]
        return headings

    def get_paragraphs(self) -> List[MarkdownElement]:
        """获取所有段落"""
        return [e for e in self.elements if e.is_paragraph]


class MarkdownParser:
    """Markdown 解析器"""

    # 正则表达式
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')
    CODE_BLOCK_PATTERN = re.compile(r'^```(\w*)\s*$')
    LIST_PATTERN = re.compile(r'^(\s*)([-*+]|\d+\.)\s+')
    QUOTE_PATTERN = re.compile(r'^>\s*(.*)$')
    EMPTY_PATTERN = re.compile(r'^\s*$')
    TABLE_PATTERN = re.compile(r'^\|.*\|$')
    HR_PATTERN = re.compile(r'^-{3,}$|^_{3,}$|\*{3,}$')

    def __init__(self):
        self.elements: List[MarkdownElement] = []

    def parse(self, content: str) -> MarkdownDocument:
        """
        解析 Markdown 内容

        Args:
            content: Markdown 文本内容

        Returns:
            MarkdownDocument: 解析后的文档对象
        """
        self.elements = []
        lines = content.split('\n')
        i = 0
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]
            element, lines_consumed = self._parse_line(lines, i)
            if element:
                element.position = len(self.elements)
                self.elements.append(element)
            i += lines_consumed

        # 构建文档对象
        doc = MarkdownDocument(elements=self.elements)
        doc.title = self._extract_title(doc)

        return doc

    def _parse_line(self, lines: List[str], index: int) -> tuple[Optional[MarkdownElement], int]:
        """
        解析单行（或多行，如代码块）

        Args:
            lines: 所有行
            index: 当前行索引

        Returns:
            (元素, 消耗的行数)
        """
        line = lines[index]

        # 空行
        if self.EMPTY_PATTERN.match(line):
            return None, 1

        # 标题
        heading_match = self.HEADING_PATTERN.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            element = MarkdownElement(
                type=ElementType.HEADING,
                content=content,
                level=level,
                raw_line=line
            )
            return element, 1

        # 代码块
        if self.CODE_BLOCK_PATTERN.match(line):
            return self._parse_code_block(lines, index)

        # 引用块
        quote_match = self.QUOTE_PATTERN.match(line)
        if quote_match:
            return self._parse_quote(lines, index)

        # 列表
        if self.LIST_PATTERN.match(line):
            return self._parse_list(lines, index)

        # 表格
        if self.TABLE_PATTERN.match(line):
            return self._parse_table(lines, index)

        # 分隔线
        if self.HR_PATTERN.match(line):
            element = MarkdownElement(
                type=ElementType.HORIZONTAL_RULE,
                content=line,
                raw_line=line
            )
            return element, 1

        # 普通段落
        return self._parse_paragraph(lines, index)

    def _parse_code_block(self, lines: List[str], index: int) -> tuple[MarkdownElement, int]:
        """解析代码块"""
        start_line = lines[index]
        lang_match = self.CODE_BLOCK_PATTERN.match(start_line)
        lang = lang_match.group(1) if lang_match else ""

        content_lines = []
        i = index + 1
        total_lines = len(lines)

        while i < total_lines:
            if self.CODE_BLOCK_PATTERN.match(lines[i]):
                # 找到结束标记
                break
            content_lines.append(lines[i])
            i += 1

        element = MarkdownElement(
            type=ElementType.CODE_BLOCK,
            content='\n'.join(content_lines),
            raw_line=start_line
        )
        return element, i - index + 1

    def _parse_paragraph(self, lines: List[str], index: int) -> tuple[MarkdownElement, int]:
        """解析段落"""
        content_lines = []
        i = index
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]

            # 遇到空行、标题、代码块等特殊元素时停止
            if (self.EMPTY_PATTERN.match(line) or
                self.HEADING_PATTERN.match(line) or
                self.CODE_BLOCK_PATTERN.match(line) or
                self.HR_PATTERN.match(line)):
                break

            # 遇到列表、引用等也停止
            if self.LIST_PATTERN.match(line) or self.QUOTE_PATTERN.match(line):
                break

            content_lines.append(line)
            i += 1

        content = ' '.join(content_lines)
        element = MarkdownElement(
            type=ElementType.PARAGRAPH,
            content=content,
            raw_line=lines[index]
        )
        return element, i - index

    def _parse_list(self, lines: List[str], index: int) -> tuple[MarkdownElement, int]:
        """解析列表"""
        content_lines = []
        i = index
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]
            if not self.LIST_PATTERN.match(line):
                break
            content_lines.append(line)
            i += 1

        element = MarkdownElement(
            type=ElementType.LIST,
            content='\n'.join(content_lines),
            raw_line=lines[index]
        )
        return element, i - index

    def _parse_quote(self, lines: List[str], index: int) -> tuple[MarkdownElement, int]:
        """解析引用块"""
        content_lines = []
        i = index
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]
            quote_match = self.QUOTE_PATTERN.match(line)
            if not quote_match:
                break
            content_lines.append(quote_match.group(1))
            i += 1

        element = MarkdownElement(
            type=ElementType.QUOTE,
            content=' '.join(content_lines),
            raw_line=lines[index]
        )
        return element, i - index

    def _parse_table(self, lines: List[str], index: int) -> tuple[MarkdownElement, int]:
        """解析表格"""
        content_lines = []
        i = index
        total_lines = len(lines)

        while i < total_lines:
            line = lines[i]
            if not self.TABLE_PATTERN.match(line):
                break
            content_lines.append(line)
            i += 1

        element = MarkdownElement(
            type=ElementType.TABLE,
            content='\n'.join(content_lines),
            raw_line=lines[index]
        )
        return element, i - index

    def _extract_title(self, doc: MarkdownDocument) -> str:
        """提取文档标题"""
        headings = doc.get_headings(level=1)
        if headings:
            return headings[0].content
        return "Untitled"


def parse_markdown(content: str) -> MarkdownDocument:
    """
    解析 Markdown 内容的便捷函数

    Args:
        content: Markdown 文本

    Returns:
        解析后的文档对象
    """
    parser = MarkdownParser()
    return parser.parse(content)


def parse_markdown_file(filepath: str) -> MarkdownDocument:
    """
    解析 Markdown 文件的便捷函数

    Args:
        filepath: Markdown 文件路径

    Returns:
        解析后的文档对象
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return parse_markdown(content)
