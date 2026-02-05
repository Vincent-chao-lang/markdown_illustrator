"""
内容分析模块
负责分析 Markdown 内容，决定配图位置和生成图片提示词
支持多图片来源的提示词优化
支持 LLM 智能提示词生成
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from parser import MarkdownDocument, MarkdownElement, ElementType

# 导入智能组件
try:
    from classifier import DocumentClassifier, classify_document
    from prompt_generator import PromptGenerator, generate_prompt
    INTELLIGENT_AVAILABLE = True
except ImportError:
    INTELLIGENT_AVAILABLE = False


@dataclass
class ImageDecision:
    """配图决策"""
    element_index: int  # 对应的元素索引
    need_image: bool
    image_type: str  # cover, section, concept, atmospheric, diagram
    prompt: str
    reason: str  # 决策理由
    ab_variants: Optional[List[Dict[str, str]]] = None  # A/B 测试变体
    image_source: Optional[str] = None  # 新增：图片来源


class ContentAnalyzer:
    """内容分析器"""

    # 技术关键词（用于判断是否是技术类文章）
    TECH_KEYWORDS = [
        '代码', '编程', '函数', '算法', '数据结构', '架构', 'API',
        'JavaScript', 'Python', 'Java', 'React', 'Vue', '数据库',
        'code', 'function', 'algorithm', 'architecture', 'programming'
    ]

    # 概念类关键词（适合生成概念图）
    CONCEPT_KEYWORDS = [
        '原理', '机制', '概念', '流程', '工作原理', '是什么',
        'principle', 'mechanism', 'concept', 'how it works'
    ]

    # 数据类关键词（适合生成图表）
    DATA_KEYWORDS = [
        '数据', '统计', '分析', '增长', '占比', '趋势',
        'data', 'statistics', 'analysis', 'growth', 'percentage'
    ]

    def __init__(self, config: Dict[str, Any], image_source: Optional[str] = None):
        """
        初始化分析器

        Args:
            config: 配置字典
            image_source: 图片来源 (zhipu, dalle, doubao, flux, unsplash, pexels, mermaid, auto)
        """
        self.config = config
        self.rules = config.get('rules', {})
        self.image_source = image_source or config.get('image_source', 'zhipu')

        # 获取提示词模板
        self.prompts = self._get_prompts_for_source(self.image_source)

        # 文档分类结果（将在 analyze 时填充）
        self.doc_classification = None

        # 初始化智能组件
        self.prompt_generator = None
        self.classifier = None
        self.use_intelligent = INTELLIGENT_AVAILABLE and self.image_source == 'auto' or config.get('llm', {}).get('enabled', False)

        if self.use_intelligent:
            try:
                self.prompt_generator = PromptGenerator(config)
                self.classifier = DocumentClassifier(config)
                print("  智能配图模式已启用")
            except Exception as e:
                print(f"  警告: 智能组件初始化失败，使用传统模式: {e}")
                self.use_intelligent = False

    def _get_prompts_for_source(self, image_source: str) -> Dict[str, str]:
        """
        获取针对特定图片来源优化的提示词模板

        Args:
            image_source: 图片来源

        Returns:
            提示词模板字典
        """
        all_prompts = self.config.get('prompts', {})

        # 如果存在该来源的专属模板，使用它
        if image_source in all_prompts:
            return all_prompts[image_source]

        # 否则使用默认模板
        if 'default' in all_prompts:
            return all_prompts['default']

        # 如果连默认模板都没有，使用整个 prompts 字典（向后兼容）
        return all_prompts

    def _get_element_context(self, element: MarkdownElement, doc: MarkdownDocument) -> str:
        """
        获取元素的上下文内容（用于 LLM 生成）

        Args:
            element: 当前元素
            doc: 文档对象

        Returns:
            上下文字符串
        """
        context_parts = []

        # 获取后续的段落内容（最多500字）
        for elem in doc.elements:
            if elem == element:
                continue
            if elem.type == ElementType.PARAGRAPH and len(context_parts) < 3:
                context_parts.append(elem.content[:200])

        return ' '.join(context_parts)

    def _generate_prompt(
        self,
        element: MarkdownElement,
        doc: MarkdownDocument,
        image_type: str,
        image_source: str = None
    ) -> str:
        """
        生成图片提示词

        Args:
            element: 元素对象
            doc: 文档对象
            image_type: 图片类型
            image_source: 图片来源

        Returns:
            提示词字符串
        """
        # 如果启用了 LLM，使用智能生成
        if self.prompt_generator:
            try:
                context = self._get_element_context(element, doc)
                # 构建文档上下文
                doc_context = {
                    'title': doc.title or '',
                    'theme': doc.theme,
                    'keywords': doc.keywords or [],
                    'doc_type': getattr(doc, 'doc_type', 'normal')
                }
                prompt = self.prompt_generator.generate(
                    element_content=element.content,
                    image_type=image_type,
                    doc_context=doc_context,
                    image_source=image_source
                )
                if prompt:
                    return prompt
            except Exception as e:
                print(f"  LLM 生成失败，使用模板: {e}")

        # 回退到模板生成
        return self._generate_prompt_from_template(element, doc, image_type)

    def _classify_document(self, doc: MarkdownDocument) -> Dict[str, Any]:
        """
        对文档进行分类

        Args:
            doc: 文档对象

        Returns:
            分类结果字典
        """
        # 准备文档元数据
        meta = {
            'title': doc.title,
            'code_blocks': len([
                el for el in doc.elements
                if hasattr(el, 'type') and
                (el.type.value if hasattr(el.type, 'value') else str(el.type)) == 'code_block'
            ]),
            'headings': [
                el.content for el in doc.elements
                if hasattr(el, 'type') and
                (el.type.value if hasattr(el.type, 'value') else str(el.type)) == 'heading'
            ],
            'has_code_examples': any('```' in el.content for el in doc.elements if hasattr(el, 'content'))
        }

        # 获取文档内容
        content = '\n'.join(el.content for el in doc.elements if hasattr(el, 'content'))

        # 调用分类器
        return self.classifier.classify(content, meta)

    def _determine_image_source(self, image_type: str, doc_type: str) -> str:
        """
        决定图片来源

        Args:
            image_type: 图片类型 (cover, section, concept, atmospheric, diagram)
            doc_type: 文档类型 (technical, normal)

        Returns:
            图片来源字符串
        """
        # 封面图统一使用 AI
        if image_type == 'cover':
            return self.image_source

        # 技术文档优先使用 Mermaid
        if doc_type == 'technical' and image_type in ['section', 'concept', 'diagram']:
            return 'mermaid'

        # 普通文档使用 Unsplash（失败后会自动降级）
        if doc_type == 'normal':
            return 'unsplash'

        # 默认使用配置的来源
        return self.image_source

    def _generate_prompt_from_template(
        self,
        element: MarkdownElement,
        doc: MarkdownDocument,
        image_type: str
    ) -> str:
        """
        使用模板生成提示词（回退方案）

        Args:
            element: 元素对象
            doc: 文档对象
            image_type: 图片类型

        Returns:
            提示词字符串
        """
        template = self.prompts.get(image_type, self.prompts.get('section', '{topic}'))

        # 根据图片类型提取内容
        if image_type == 'cover':
            return template.format(title=element.content, theme=doc.theme)
        elif image_type == 'atmospheric':
            summary = element.content[:100]
            if len(element.content) > 100:
                summary += "..."
            return template.format(topic=summary)
        else:
            return template.format(
                topic=element.content,
                concept=element.content,
                title=element.content
            )

    def analyze(self, doc: MarkdownDocument) -> List[ImageDecision]:
        """
        分析文档，生成配图决策

        Args:
            doc: Markdown 文档对象

        Returns:
            配图决策列表
        """
        decisions = []

        # 分析文章主题
        doc.theme = self._analyze_theme(doc)
        doc.keywords = self._extract_keywords(doc)

        # 文档分类（如果启用智能模式）
        doc_type = 'normal'
        if self.use_intelligent and self.classifier:
            try:
                self.doc_classification = self._classify_document(doc)
                doc_type = self.doc_classification.get('type', 'normal')
                print(f"  文档类型: {doc_type} (置信度: {self.doc_classification.get('confidence', 0):.2f})")
            except Exception as e:
                print(f"  文档分类失败，使用默认类型: {e}")
                doc_type = 'normal'

        # 存储文档类型供后续使用
        doc.doc_type = doc_type

        # 检查是否启用 A/B 测试
        ab_test_config = self.config.get('ab_test', {})
        ab_test_enabled = ab_test_config.get('enabled', False)
        ab_variations = ab_test_config.get('variations', [])
        ab_test_size = ab_test_config.get('test_size', 2)

        # 遍历所有元素，决定是否配图
        last_image_index = -self.rules.get('min_gap_between_images', 3)
        image_count = 0
        max_images = self.rules.get('max_images_per_article', 10)

        # 检查是否有 H1 标题
        has_h1 = any(
            (el.type.value if hasattr(el.type, 'value') else str(el.type)) == 'heading' and el.level == 1
            for el in doc.elements
        )

        # 如果没有 H1 标题且配置要求配封面图，在文档开头添加封面图决策
        if not has_h1 and self.rules.get('h1_after', True):
            # 找到第一个非空内容元素作为标题来源
            title_element = None
            title_index = 0
            for i, el in enumerate(doc.elements):
                content = el.content if hasattr(el, 'content') else ''
                if content and content.strip():
                    title_element = el
                    title_index = i
                    break

            if title_element:
                # 决定图片来源（封面图统一使用 AI）
                cover_source = self._determine_image_source('cover', doc_type)
                # 创建虚拟封面图决策
                cover_prompt = self._generate_prompt(title_element, doc, 'cover', cover_source)
                decision = ImageDecision(
                    element_index=title_index,
                    need_image=True,
                    image_type='cover',
                    prompt=cover_prompt,
                    reason='无H1标题，自动在开头配封面图',
                    image_source=cover_source
                )
                decisions.append(decision)
                # 设置元素的 need_image 属性
                title_element.need_image = True
                title_element.image_type = 'cover'
                title_element.image_prompt = cover_prompt
                image_count += 1

        for i, element in enumerate(doc.elements):
            # 检查是否超过最大配图数
            if image_count >= max_images:
                break

            # 检查与上一张图片的距离
            if i - last_image_index < self.rules.get('min_gap_between_images', 3):
                continue

            decision = self._analyze_element(element, doc, i)
            if decision and decision.need_image:
                # 如果启用 A/B 测试，生成变体
                if ab_test_enabled and ab_variations:
                    decision.ab_variants = self._generate_ab_variants(
                        decision.prompt,
                        ab_variations,
                        ab_test_size
                    )

                decisions.append(decision)
                last_image_index = i
                image_count += 1
                element.need_image = True
                element.image_type = decision.image_type
                element.image_prompt = decision.prompt

        return decisions

    def _generate_ab_variants(
        self,
        base_prompt: str,
        variations: List[Dict[str, str]],
        test_size: int
    ) -> List[Dict[str, str]]:
        """
        生成 A/B 测试变体

        Args:
            base_prompt: 基础提示词
            variations: 变体定义列表
            test_size: 需要生成的变体数量

        Returns:
            变体列表 [{'name': 'minimal', 'prompt': '...'}, ...]
        """
        variants = []

        # 确保不超过可用变体数量
        actual_size = min(test_size, len(variations))

        for i in range(actual_size):
            variation = variations[i]
            name = variation.get('name', f'variant_{i}')
            description = variation.get('description', name)
            suffix = variation.get('prompt_suffix', '')

            # 组合基础提示词和变体后缀
            variant_prompt = base_prompt + suffix

            variants.append({
                'name': name,
                'description': description,
                'prompt': variant_prompt
            })

        return variants

    def _analyze_theme(self, doc: MarkdownDocument) -> str:
        """
        分析文章主题

        Args:
            doc: 文档对象

        Returns:
            主题描述
        """
        if doc.title:
            # 从标题提取主题
            theme = doc.title
            # 检查是否是技术类文章
            is_tech = any(kw in theme for kw in self.TECH_KEYWORDS)
            if is_tech:
                return f"技术文章：{theme}"
            return theme

        # 从第一段提取
        for element in doc.elements:
            if element.type == ElementType.PARAGRAPH and element.word_count > 20:
                return element.content[:50] + "..."

        return "通用文章"

    def _extract_keywords(self, doc: MarkdownDocument) -> List[str]:
        """
        提取文章关键词

        Args:
            doc: 文档对象

        Returns:
            关键词列表
        """
        keywords = set()

        # 从标题提取
        for heading in doc.get_headings():
            words = self._split_words(heading.content)
            keywords.update(words)

        # 从代码块语言提取
        for element in doc.elements:
            if element.type == ElementType.CODE_BLOCK:
                # 代码块第一行可能是语言标识
                first_line = element.content.split('\n')[0]
                if first_line.strip():
                    keywords.add(first_line.strip())

        return list(keywords)[:10]

    def _split_words(self, text: str) -> List[str]:
        """分词（简单实现）"""
        # 移除标点符号
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        # 分割
        words = text.split()
        # 过滤停用词
        stopwords = {'的', '是', '在', '和', '与', '或', '但', '而', 'the', 'a', 'an', 'is', 'are', 'in', 'on', 'at'}
        return [w for w in words if len(w) > 1 and w not in stopwords]

    def _analyze_element(self, element: MarkdownElement, doc: MarkdownDocument, index: int) -> Optional[ImageDecision]:
        """
        分析单个元素是否需要配图

        Args:
            element: 元素对象
            doc: 文档对象
            index: 元素索引

        Returns:
            配图决策或 None
        """
        # Use string comparison to avoid enum identity issues
        element_type_value = element.type.value if hasattr(element.type, 'value') else str(element.type)

        # H1 标题后配封面图
        if element_type_value == 'heading' and element.level == 1:
            if self.rules.get('h1_after', True):
                return self._create_cover_decision(element, doc, index)

        # H2 标题后配图
        if element_type_value == 'heading' and element.level == 2:
            h2_rule = self.rules.get('h2_after', 'smart')
            if h2_rule is True:
                return self._create_section_decision(element, doc, index)
            elif h2_rule == 'smart':
                # 智能判断：检查后续内容长度
                if self._should_add_section_image(doc, index):
                    return self._create_section_decision(element, doc, index)

        # 长段落配图
        if element_type_value == 'paragraph':
            threshold = self.rules.get('long_paragraph_threshold', 150)
            if element.word_count >= threshold:
                return self._create_atmospheric_decision(element, doc, index)

        return None

    def _should_add_section_image(self, doc: MarkdownDocument, heading_index: int) -> bool:
        """
        判断章节是否需要配图

        Args:
            doc: 文档对象
            heading_index: 标题索引

        Returns:
            是否需要配图
        """
        # 检查后续内容长度
        total_words = 0
        for i in range(heading_index + 1, len(doc.elements)):
            element = doc.elements[i]
            element_type_value = element.type.value if hasattr(element.type, 'value') else str(element.type)
            if element_type_value == 'heading':
                break
            if element_type_value == 'paragraph':
                total_words += element.word_count
            if total_words > 100:
                return True

        return False

    def _create_cover_decision(self, element: MarkdownElement, doc: MarkdownDocument, index: int) -> ImageDecision:
        """创建封面图决策"""
        doc_type = getattr(doc, 'doc_type', 'normal')
        image_source = self._determine_image_source('cover', doc_type)
        prompt = self._generate_prompt(element, doc, 'cover', image_source)

        return ImageDecision(
            element_index=index,
            need_image=True,
            image_type='cover',
            prompt=prompt,
            reason='H1 标题后配封面图',
            image_source=image_source
        )

    def _create_section_decision(self, element: MarkdownElement, doc: MarkdownDocument, index: int) -> ImageDecision:
        """创建章节配图决策"""
        # 判断图片类型
        image_type = 'section'

        # 检查是否是概念类内容
        if any(kw in element.content for kw in self.CONCEPT_KEYWORDS):
            image_type = 'concept'

        doc_type = getattr(doc, 'doc_type', 'normal')
        image_source = self._determine_image_source(image_type, doc_type)
        prompt = self._generate_prompt(element, doc, image_type, image_source)

        return ImageDecision(
            element_index=index,
            need_image=True,
            image_type=image_type,
            prompt=prompt,
            reason=f'H2 标题后配图 ({image_type})',
            image_source=image_source
        )

    def _create_atmospheric_decision(self, element: MarkdownElement, doc: MarkdownDocument, index: int) -> ImageDecision:
        """创建氛围图决策"""
        doc_type = getattr(doc, 'doc_type', 'normal')
        image_source = self._determine_image_source('atmospheric', doc_type)
        prompt = self._generate_prompt(element, doc, 'atmospheric', image_source)

        return ImageDecision(
            element_index=index,
            need_image=True,
            image_type='atmospheric',
            prompt=prompt,
            reason=f'长段落配图 ({element.word_count} 字)',
            image_source=image_source
        )


def analyze_content(doc: MarkdownDocument, config: Dict[str, Any], image_source: Optional[str] = None) -> List[ImageDecision]:
    """
    分析内容的便捷函数

    Args:
        doc: Markdown 文档对象
        config: 配置字典
        image_source: 图片来源 (zhipu, dalle, doubao, flux, unsplash, pexels, mermaid)

    Returns:
        配图决策列表
    """
    analyzer = ContentAnalyzer(config, image_source)
    return analyzer.analyze(doc)
