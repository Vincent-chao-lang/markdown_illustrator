"""
LLM 客户端模块
支持多种 LLM 提供商用于智能提示词生成
"""

import os
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM 提供商基类"""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 200) -> str:
        """生成文本"""
        pass


class ZhipuLLM(LLMProvider):
    """智谱 GLM LLM"""

    def __init__(self, api_key: str, model: str = "glm-4-flash"):
        self.api_key = api_key
        self.model = model

        try:
            from zhipuai import ZhipuAI
            self.client = ZhipuAI(api_key=api_key)
        except ImportError:
            raise ImportError("请安装 zhipuai 包: pip install zhipuai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 200) -> str:
        """生成文本"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()


class DeepSeekLLM(LLMProvider):
    """DeepSeek LLM (OpenAI 兼容)"""

    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("请安装 openai 包: pip install openai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 200) -> str:
        """生成文本"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()


class OpenAILLM(LLMProvider):
    """OpenAI LLM"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("请安装 openai 包: pip install openai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 200) -> str:
        """生成文本"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()


class PromptGenerator:
    """智能提示词生成器"""

    # 图片类型对应的生成指令
    IMAGE_TYPE_INSTRUCTIONS = {
        'cover': """生成文章封面图的描述。
要求：
1. 概括文章主题和核心内容
2. 突出文章的价值和亮点
3. 50字以内，简洁有力
4. 只返回描述，不要其他内容""",

        'section': """生成章节配图的描述。
要求：
1. 提取章节的核心概念或流程
2. 如果有操作步骤，总结为3-5个关键词
3. 如果是概念说明，提炼核心要点
4. 50字以内
5. 只返回描述，不要其他内容""",

        'concept': """生成概念图的描述。
要求：
1. 提炼核心概念和关系
2. 识别涉及的组件或实体
3. 描述它们之间的关联
4. 50字以内
5. 只返回描述，不要其他内容""",

        'atmospheric': """生成氛围图的描述。
要求：
1. 提炼内容的情感基调
2. 描述相关的视觉元素
3. 突出氛围特点
4. 40字以内
5. 只返回描述，不要其他内容""",

        'code_concept': """生成代码概念图的描述。
要求：
1. 提炼代码逻辑或结构
2. 识别关键的数据流或控制流
3. 描述核心算法或设计模式
4. 50字以内
5. 只返回描述，不要其他内容""",
    }

    def __init__(self, config: Dict[str, Any]):
        """
        初始化提示词生成器

        Args:
            config: 配置字典
        """
        self.llm_config = config.get('llm', {})
        self.enabled = self.llm_config.get('enabled', False)
        self.provider = None

        if self.enabled:
            self._init_llm()

    def _init_llm(self):
        """初始化 LLM 客户端"""
        provider_type = self.llm_config.get('provider', 'zhipu')

        if provider_type == 'zhipu':
            api_key = self.llm_config.get('api_key') or os.getenv('ZHIPUAI_API_KEY')
            if not api_key:
                raise ValueError("请设置智谱 API Key！配置 llm.api_key 或环境变量 ZHIPUAI_API_KEY")
            model = self.llm_config.get('model', 'glm-4-flash')
            self.provider = ZhipuLLM(api_key, model)

        elif provider_type == 'deepseek':
            api_key = self.llm_config.get('api_key') or os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                raise ValueError("请设置 DeepSeek API Key！配置 llm.api_key 或环境变量 DEEPSEEK_API_KEY")
            model = self.llm_config.get('model', 'deepseek-chat')
            base_url = self.llm_config.get('base_url', 'https://api.deepseek.com')
            self.provider = DeepSeekLLM(api_key, model, base_url)

        elif provider_type == 'openai':
            api_key = self.llm_config.get('api_key') or os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("请设置 OpenAI API Key！配置 llm.api_key 或环境变量 OPENAI_API_KEY")
            model = self.llm_config.get('model', 'gpt-4o-mini')
            self.provider = OpenAILLM(api_key, model)

        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider_type}")

    def generate_prompt(
        self,
        title: str,
        content: str,
        image_type: str,
        context: Optional[str] = None
    ) -> str:
        """
        使用 LLM 生成智能提示词

        Args:
            title: 标题
            content: 内容
            image_type: 图片类型
            context: 额外上下文

        Returns:
            生成的提示词
        """
        # 如果 LLM 未启用，使用简单回退
        if not self.enabled or self.provider is None:
            return self._fallback_prompt(title, content, image_type)

        # 构建提示词
        instruction = self.IMAGE_TYPE_INSTRUCTIONS.get(
            image_type,
            self.IMAGE_TYPE_INSTRUCTIONS['section']
        )

        user_prompt = f"""文章标题：{title}

当前内容：{content[:500]}

{f'相关上下文：{context[:300]}' if context else ''}

根据以上内容，{instruction}"""

        system_prompt = """你是一个专业的配图提示词生成助手。
你擅长理解文章内容，提炼核心要点，生成准确的图片描述。
你的描述会被用于生成配图或图表。

请确保：
1. 描述准确、简洁
2. 突出核心内容
3. 适合可视化展示"""

        try:
            # 调用 LLM 生成
            max_tokens = self.llm_config.get('max_tokens', 150)
            result = self.provider.generate(user_prompt, system_prompt, max_tokens)

            # 清理结果
            result = result.strip()
            # 移除可能的引号
            result = result.strip('"').strip("'").strip('""').strip("''")

            return result if result else self._fallback_prompt(title, content, image_type)

        except Exception as e:
            print(f"  LLM 生成失败，使用回退方案: {e}")
            return self._fallback_prompt(title, content, image_type)

    def _fallback_prompt(self, title: str, content: str, image_type: str) -> str:
        """回退方案：使用简单规则生成提示词"""
        if image_type == 'cover':
            return title[:50]
        elif image_type == 'section':
            return content[:50]
        elif image_type == 'concept':
            return f"{title[:30]}原理"
        else:
            return content[:40]

    def generate_batch(
        self,
        items: List[Dict[str, str]]
    ) -> List[str]:
        """
        批量生成提示词

        Args:
            items: 包含 title, content, image_type, context 的字典列表

        Returns:
            提示词列表
        """
        results = []
        for i, item in enumerate(items):
            try:
                prompt = self.generate_prompt(
                    title=item.get('title', ''),
                    content=item.get('content', ''),
                    image_type=item.get('image_type', 'section'),
                    context=item.get('context')
                )
                results.append(prompt)
                print(f"  LLM 生成进度: {i + 1}/{len(items)}")
            except Exception as e:
                print(f"  第 {i + 1} 个提示词生成失败: {e}")
                results.append(self._fallback_prompt(
                    item.get('title', ''),
                    item.get('content', ''),
                    item.get('image_type', 'section')
                ))
        return results


# 便捷函数
def create_prompt_generator(config: Dict[str, Any]) -> PromptGenerator:
    """
    创建提示词生成器

    Args:
        config: 配置字典

    Returns:
        PromptGenerator 实例
    """
    return PromptGenerator(config)
