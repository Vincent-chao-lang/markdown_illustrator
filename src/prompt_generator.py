"""
智能提示词生成器
使用 LLM 生成图片提示词，并优化长度和格式
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class PromptGenerator:
    """提示词生成器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化提示词生成器

        Args:
            config: 配置字典
        """
        self.config = config
        self.llm_config = config.get('llm', {})
        self.enabled = self.llm_config.get('enabled', True)
        self.provider = self.llm_config.get('provider', 'zhipu')
        self.model = self.llm_config.get('model', 'glm-4-flash')
        self.max_tokens = self.llm_config.get('max_tokens', 300)

        # 提示词模板配置
        self.prompts_config = config.get('prompts', {})

    def generate(
        self,
        element_content: str,
        image_type: str,
        doc_context: Dict[str, Any],
        image_source: str = None
    ) -> str:
        """
        生成图片提示词

        Args:
            element_content: 元素内容（标题、段落等）
            image_type: 图片类型 (cover, section, concept, atmospheric, diagram)
            doc_context: 文档上下文 {
                'title': str,
                'theme': str,
                'keywords': List[str],
                'doc_type': str  # 'technical' or 'normal'
            }
            image_source: 图片来源（用于选择合适的模板）

        Returns:
            生成的提示词
        """
        # 1. 使用 LLM 生成基础提示词
        if self.enabled:
            base_prompt = self._llm_generate(element_content, image_type, doc_context)
        else:
            base_prompt = self._rule_generate(element_content, image_type, doc_context)

        # 2. 根据图片来源选择模板
        template = self._get_template(image_type, image_source, doc_context.get('doc_type', 'normal'))

        # 3. 结合模板和基础提示词
        final_prompt = self._combine_with_template(base_prompt, template, image_type, element_content)

        # 4. 长度控制
        final_prompt = self._truncate_prompt(final_prompt, self.max_tokens)

        return final_prompt

    def _llm_generate(self, content: str, image_type: str, context: Dict[str, Any]) -> str:
        """
        使用 LLM 生成提示词

        Args:
            content: 元素内容
            image_type: 图片类型
            context: 文档上下文

        Returns:
            LLM 生成的提示词
        """
        try:
            # 动态导入 LLM 客户端
            if self.provider == 'zhipu':
                from zhipuai import ZhipuAI
                api_key = self.llm_config.get('api_key') or self.config.get('api', {}).get('api_key', '')
                if not api_key:
                    return self._rule_generate(content, image_type, context)
                client = ZhipuAI(api_key=api_key)
            else:
                return self._rule_generate(content, image_type, context)

            # 构建提示词
            llm_prompt = self._build_generation_prompt(content, image_type, context)

            # 调用 LLM
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的AI图片提示词生成专家，擅长创作简洁准确的图片描述。"},
                    {"role": "user", "content": llm_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.7
            )

            result = response.choices[0].message.content.strip()

            print(f"    LLM 生成提示词: {result[:80]}...")
            return result

        except Exception as e:
            print(f"    LLM 生成失败，使用规则生成: {e}")
            return self._rule_generate(content, image_type, context)

    def _rule_generate(self, content: str, image_type: str, context: Dict[str, Any]) -> str:
        """
        使用规则生成提示词（兜底方案）

        Args:
            content: 元素内容
            image_type: 图片类型
            context: 文档上下文

        Returns:
            规则生成的提示词
        """
        # 简化版：直接使用内容作为提示词
        if image_type == 'cover':
            return f"{context.get('title', content)}，专业封面设计"
        elif image_type == 'section':
            return f"{content}，示意图"
        elif image_type == 'concept':
            return f"{content}，原理图"
        elif image_type == 'atmospheric':
            return f"{content}，氛围插图"
        else:
            return content

    def _build_generation_prompt(self, content: str, image_type: str, context: Dict[str, Any]) -> str:
        """构建 LLM 生成提示词"""
        type_names = {
            'cover': '封面图',
            'section': '章节配图',
            'concept': '概念示意图',
            'atmospheric': '氛围插图',
            'diagram': '架构图',
        }

        doc_type = context.get('doc_type', 'normal')
        doc_type_desc = "技术文档" if doc_type == 'technical' else "普通文章"

        prompt = f"""请为以下内容生成简洁的图片提示词（{self.max_tokens}字以内）：

文档类型: {doc_type_desc}
图片类型: {type_names.get(image_type, image_type)}
文章标题: {context.get('title', '无标题')}
关键词: {', '.join(context.get('keywords', []))[:5]}
内容: {content[:200]}

要求:
1. 简洁准确，{self.max_tokens}字以内
2. 突出核心内容
3. 适合作为图片生成提示词

请直接输出提示词，不要解释。"""
        return prompt

    def _get_template(self, image_type: str, image_source: str, doc_type: str) -> str:
        """
        获取提示词模板

        Args:
            image_type: 图片类型
            image_source: 图片来源
            doc_type: 文档类型

        Returns:
            模板字符串
        """
        # 根据图片来源选择对应的模板配置
        source_key = image_source or self.config.get('image_source', 'zhipu')
        source_prompts = self.prompts_config.get(source_key, {})
        default_prompts = self.prompts_config.get('default', {})

        # 优先使用来源特定模板，否则使用默认模板
        template = source_prompts.get(image_type, default_prompts.get(image_type, '{title}'))

        # 如果是技术文档且使用 Mermaid，添加特殊处理
        if doc_type == 'technical' and image_source == 'mermaid':
            mermaid_templates = {
                'cover': '{title}思维导图',
                'section': '{topic}流程图',
                'concept': '{concept}状态图',
                'diagram': '{concept}架构图',
            }
            template = mermaid_templates.get(image_type, template)

        return template

    def _combine_with_template(
        self,
        base_prompt: str,
        template: str,
        image_type: str,
        element_content: str
    ) -> str:
        """
        结合基础提示词和模板

        Args:
            base_prompt: LLM 生成的基础提示词
            template: 模板字符串
            image_type: 图片类型
            element_content: 元素内容

        Returns:
            最终提示词
        """
        # 模板变量替换
        try:
            # 提取可能的变量
            title = element_content if element_content else base_prompt

            # 处理不同的模板变量
            if '{title}' in template:
                result = template.replace('{title}', title)
            elif '{topic}' in template:
                result = template.replace('{topic}', base_prompt)
            elif '{concept}' in template:
                result = template.replace('{concept}', base_prompt)
            else:
                # 模板就是固定文本，直接拼接
                result = f"{base_prompt}，{template}"

            return result
        except Exception as e:
            # 如果模板处理失败，直接返回基础提示词
            print(f"    模板处理失败: {e}")
            return base_prompt

    def _truncate_prompt(self, prompt: str, max_length: int) -> str:
        """
        截断超长提示词

        Args:
            prompt: 原始提示词
            max_length: 最大长度

        Returns:
            截断后的提示词
        """
        # 如果已经是简短提示词，直接返回
        if len(prompt) <= max_length:
            return prompt

        # 尝试在合适的位置截断（逗号、句号等）
        truncated = prompt[:max_length]

        # 寻找最后一个标点符号
        for i in range(len(truncated) - 1, -1, -1):
            if truncated[i] in '，。、,.':
                return truncated[:i + 1]

        # 如果没有标点，直接截断
        return truncated


def generate_prompt(
    element,
    image_type: str,
    doc_context: Dict[str, Any],
    config: Dict[str, Any],
    image_source: str = None
) -> str:
    """
    生成提示词的便捷函数

    Args:
        element: MarkdownElement 对象
        image_type: 图片类型
        doc_context: 文档上下文
        config: 配置字典
        image_source: 图片来源

    Returns:
        生成的提示词
    """
    generator = PromptGenerator(config)
    return generator.generate(
        element.content if hasattr(element, 'content') else '',
        image_type,
        doc_context,
        image_source
    )
