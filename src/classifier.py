"""
文档分类器
使用 LLM 判断文档类型，决定配图策略
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path


class DocumentClassifier:
    """文档分类器"""

    # 技术关键词列表
    TECH_KEYWORDS = [
        '代码', '编程', '函数', '算法', '数据结构', '架构', 'API',
        '框架', '库', '模块', '类', '对象', '变量', '方法',
        '数据库', '服务器', '客户端', '前端', '后端', '全栈',
        '部署', '配置', '环境', '依赖', '安装',
        # 英文技术词汇
        'code', 'function', 'algorithm', 'data structure', 'API',
        'framework', 'library', 'module', 'class', 'object', 'variable',
        'database', 'server', 'client', 'frontend', 'backend', 'fullstack',
        'deploy', 'config', 'environment', 'dependency', 'install',
        'git', 'commit', 'push', 'pull', 'clone', 'branch', 'merge',
        'http', 'https', 'url', 'endpoint', 'request', 'response',
        'json', 'xml', 'html', 'css', 'javascript', 'python', 'java',
        'react', 'vue', 'angular', 'node', 'express', 'django', 'flask',
        'docker', 'kubernetes', 'linux', 'ubuntu', 'windows', 'mac',
    ]

    # 流程相关关键词
    PROCESS_KEYWORDS = [
        '流程', '步骤', '阶段', '过程', '循环', '判断', '条件',
        '输入', '输出', '开始', '结束', '返回', '调用',
        'flow', 'process', 'step', 'stage', 'loop', 'condition',
        'input', 'output', 'start', 'end', 'return', 'call',
    ]

    def __init__(self, config: Dict[str, Any]):
        """
        初始化分类器

        Args:
            config: 配置字典
        """
        self.config = config
        self.llm_config = config.get('llm', {})
        self.enabled = self.llm_config.get('enabled', True)
        self.provider = self.llm_config.get('provider', 'zhipu')
        self.model = self.llm_config.get('model', 'glm-4-flash')
        self.max_tokens = self.llm_config.get('max_tokens', 300)

    def classify(self, doc_content: str, doc_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        分类文档类型

        Args:
            doc_content: 文档内容
            doc_meta: 文档元数据 {
                'title': str,
                'code_blocks': int,
                'headings': List[str],
                'has_code_examples': bool
            }

        Returns:
            分类结果 {
                'type': 'technical' | 'normal',
                'confidence': float (0-1),
                'reason': str,
                'indicators': Dict[str, Any]
            }
        """
        # 先进行规则分类（快速）
        rule_result = self._rule_based_classification(doc_content, doc_meta)

        # 如果启用 LLM 且规则分类不确定，使用 LLM 验证
        if self.enabled and rule_result['confidence'] < 0.8:
            llm_result = self._llm_classification(doc_content, doc_meta)
            # LLM 结果优先
            return llm_result

        return rule_result

    def _rule_based_classification(self, content: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于规则的分类（快速分类）

        Args:
            content: 文档内容
            meta: 文档元数据

        Returns:
            分类结果
        """
        indicators = {
            'code_block_count': meta.get('code_blocks', 0),
            'tech_keyword_count': 0,
            'process_keyword_count': 0,
            'has_code_example': False,
            'structure_score': 0,
        }

        content_lower = content.lower()

        # 统计技术关键词
        for keyword in self.TECH_KEYWORDS:
            count = content_lower.count(keyword.lower())
            if count > 0:
                indicators['tech_keyword_count'] += count

        # 统计流程关键词
        for keyword in self.PROCESS_KEYWORDS:
            count = content_lower.count(keyword.lower())
            if count > 0:
                indicators['process_keyword_count'] += count

        # 检测代码块
        code_block_pattern = r'```[\w]*\n([\s\S]*?)```'
        code_blocks = re.findall(code_block_pattern, content)
        indicators['code_block_count'] = len(code_blocks)
        indicators['has_code_example'] = len(code_blocks) > 0

        # 结构化程度（标题层级、列表等）
        heading_pattern = r'^#{1,6}\s+.+$'
        headings = re.findall(heading_pattern, content, re.MULTILINE)
        indicators['structure_score'] = len(headings)

        # 计算技术得分
        tech_score = 0
        tech_score += min(indicators['code_block_count'] * 20, 40)  # 代码块最多40分
        tech_score += min(indicators['tech_keyword_count'] * 2, 30)  # 技术词最多30分
        tech_score += min(indicators['process_keyword_count'], 20)  # 流程词最多20分
        tech_score += min(indicators['structure_score'] * 2, 10)  # 结构最多10分

        # 判断阈值
        if tech_score >= 30:
            return {
                'type': 'technical',
                'confidence': min(0.9, 0.5 + tech_score / 100),
                'reason': f'技术得分 {tech_score} >= 30',
                'indicators': indicators,
                'tech_score': tech_score
            }
        elif tech_score >= 15:
            return {
                'type': 'normal',
                'confidence': 0.6,
                'reason': f'技术得分 {tech_score} 在边界范围，归类为普通文档',
                'indicators': indicators,
                'tech_score': tech_score
            }
        else:
            return {
                'type': 'normal',
                'confidence': 0.9,
                'reason': f'技术得分 {tech_score} < 15，确认为普通文档',
                'indicators': indicators,
                'tech_score': tech_score
            }

    def _llm_classification(self, content: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于 LLM 的分类（准确但较慢）

        Args:
            content: 文档内容
            meta: 文档元数据

        Returns:
            分类结果
        """
        try:
            # 动态导入 LLM 客户端
            if self.provider == 'zhipu':
                from zhipuai import ZhipuAI
                api_key = self.llm_config.get('api_key') or self.config.get('api', {}).get('api_key', '')
                if not api_key:
                    # 回退到规则分类
                    return self._rule_based_classification(content, meta)
                client = ZhipuAI(api_key=api_key)
            else:
                # 其他 provider 暂未实现，回退到规则
                return self._rule_based_classification(content, meta)

            # 准备提示词
            prompt = self._build_classification_prompt(content, meta)

            # 调用 LLM
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个文档分类专家，擅长判断文档类型。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )

            result = response.choices[0].message.content.strip().lower()

            # 解析结果
            if 'technical' in result or '技术' in result:
                return {
                    'type': 'technical',
                    'confidence': 0.95,
                    'reason': f'LLM 判断为技术文档: {result}',
                    'method': 'llm',
                    'indicators': {},
                    'llm_response': result
                }
            else:
                return {
                    'type': 'normal',
                    'confidence': 0.95,
                    'reason': f'LLM 判断为普通文档: {result}',
                    'method': 'llm',
                    'indicators': {},
                    'llm_response': result
                }

        except Exception as e:
            print(f"  LLM 分类失败，使用规则分类: {e}")
            return self._rule_based_classification(content, meta)

    def _build_classification_prompt(self, content: str, meta: Dict[str, Any]) -> str:
        """构建分类提示词"""
        # 截取内容前500字用于分析
        content_preview = content[:500].replace('\n', ' ')

        prompt = f"""请判断以下文档是"技术文档"还是"普通文档"：

文档标题: {meta.get('title', '无标题')}
代码块数量: {meta.get('code_blocks', 0)}
内容预览: {content_preview}...

判断标准:
- 技术文档: 包含代码示例、API 文档、技术教程、架构设计、算法说明等
- 普通文档: 新闻、博客、文章、故事、生活内容等

请只回答: "technical" 或 "normal" """
        return prompt


def classify_document(doc, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    分类文档的便捷函数

    Args:
        doc: MarkdownDocument 对象
        config: 配置字典

    Returns:
        分类结果
    """
    classifier = DocumentClassifier(config)

    # 准备元数据
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

    return classifier.classify(content, meta)
