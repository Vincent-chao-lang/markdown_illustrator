"""
Mermaid 图表生成模块
为 Markdown 文档生成基于 Mermaid 的技术图表
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


class DiagramStrategy(ABC):
    """图表生成策略基类"""

    @abstractmethod
    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成 Mermaid 代码"""
        pass

    @abstractmethod
    def get_diagram_type(self) -> str:
        """返回图表类型"""
        pass


class FlowchartStrategy(DiagramStrategy):
    """流程图生成策略"""

    def get_diagram_type(self) -> str:
        return "flowchart"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成流程图"""
        # 简化版：基于关键词生成模板
        keywords_lower = prompt.lower()

        # 检测是否包含条件/判断
        has_condition = any(word in keywords_lower for word in ['如果', '否则', '判断', '验证', '检查', '当', 'whether', 'if', 'check'])

        # 检测是否包含循环
        has_loop = any(word in keywords_lower for word in ['循环', '重复', '直到', 'while', 'loop', 'repeat'])

        # 基于模板生成
        if has_condition and has_loop:
            return self._generate_complex_flowchart(prompt)
        elif has_condition:
            return self._generate_decision_flowchart(prompt)
        elif has_loop:
            return self._generate_loop_flowchart(prompt)
        else:
            return self._generate_simple_flowchart(prompt)

    def _generate_simple_flowchart(self, prompt: str) -> str:
        """简单流程图"""
        # 提取主要步骤
        steps = self._extract_steps(prompt)
        if not steps:
            steps = ["开始", prompt, "结束"]

        mermaid = ["flowchart TD"]
        for i, step in enumerate(steps):
            node_id = chr(65 + i)  # A, B, C, ...
            mermaid.append(f'    {node_id}["{step}"]')
            if i > 0:
                prev_id = chr(65 + i - 1)
                mermaid.append(f'    {prev_id} --> {node_id}')

        return "\n".join(mermaid)

    def _generate_decision_flowchart(self, prompt: str) -> str:
        """带判断的流程图"""
        # 尝试提取条件和结果
        positive = self._extract_positive_outcome(prompt)
        negative = self._extract_negative_outcome(prompt)
        condition = self._extract_condition(prompt)

        mermaid = [
            "flowchart TD",
            f'    A["开始"]',
            f'    B{{{condition or "判断条件"}}}',
            f'    C["{positive or "执行操作"}"]',
            f'    D["{negative or "处理失败"}"]',
            f'    E["结束"]',
            f'    A --> B',
            f'    B -->|是| C',
            f'    B -->|否| D',
            f'    C --> E',
            f'    D --> E'
        ]
        return "\n".join(mermaid)

    def _generate_loop_flowchart(self, prompt: str) -> str:
        """带循环的流程图"""
        mermaid = [
            "flowchart TD",
            f'    A["开始"]',
            f'    B["执行操作"]',
            f'    C{"满足条件?"}',
            f'    D["结束"]',
            f'    A --> B',
            f'    B --> C',
            f'    C -->|是| D',
            f'    C -->|否| B'
        ]
        return "\n".join(mermaid)

    def _generate_complex_flowchart(self, prompt: str) -> str:
        """复杂流程图（包含判断和循环）"""
        return self._generate_decision_flowchart(prompt)

    def _extract_steps(self, prompt: str) -> List[str]:
        """从文本中提取步骤"""
        # 常见步骤分隔符
        separators = ['然后', '接着', '之后', '最后', '随后', 'then', 'next', 'finally', '。', '，', ',']

        steps = []
        current = ""

        for char in prompt:
            current += char
            if any(sep in current for sep in separators):
                step = current.strip()
                if step and len(step) > 2:
                    steps.append(step.rstrip('。，, '))
                current = ""

        if current.strip():
            steps.append(current.strip())

        return steps[:5] if steps else []

    def _extract_condition(self, prompt: str) -> str:
        """提取判断条件"""
        condition_patterns = [
            r'如果(.+?)[，,则则]',
            r'验证(.+?)[，,则则]',
            r'检查(.+?)[，,则则]',
            r'判断(.+?)[，,则则]',
        ]
        for pattern in condition_patterns:
            match = re.search(pattern, prompt)
            if match:
                return match.group(1).strip()
        return "判断条件"

    def _extract_positive_outcome(self, prompt: str) -> str:
        """提取成功结果"""
        patterns = [
            r'成功.*?[:：](.+?)[。，,]',
            r'通过.*?[:：](.+?)[。，,]',
            r'则是(.+?)[。，,]',
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                return match.group(1).strip()
        return "继续执行"

    def _extract_negative_outcome(self, prompt: str) -> str:
        """提取失败结果"""
        patterns = [
            r'失败.*?[:：](.+?)[。，,]',
            r'错误.*?[:：](.+?)[。，,]',
            r'否则(.+?)[。，,]',
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                return match.group(1).strip()
        return "返回错误"


class SequenceStrategy(DiagramStrategy):
    """时序图生成策略"""

    def get_diagram_type(self) -> str:
        return "sequenceDiagram"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成时序图"""
        # 检测API调用相关关键词
        has_api = any(word in prompt.lower() for word in ['api', '接口', '请求', '响应', '调用', 'request', 'response'])

        if has_api:
            return self._generate_api_sequence(prompt)
        else:
            return self._generate_generic_sequence(prompt)

    def _generate_api_sequence(self, prompt: str) -> str:
        """生成 API 调用时序图"""
        mermaid = [
            "sequenceDiagram",
            "    participant User as 用户",
            "    participant Client as 客户端",
            "    participant Server as 服务器",
            "    participant DB as 数据库",
            "    User->>Client: 发起请求",
            "    Client->>Server: API 调用",
            "    Server->>DB: 查询数据",
            "    DB-->>Server: 返回结果",
            "    Server-->>Client: 响应数据",
            "    Client-->>User: 显示结果"
        ]
        return "\n".join(mermaid)

    def _generate_generic_sequence(self, prompt: str) -> str:
        """生成通用时序图"""
        # 提取可能的参与者
        participants = self._extract_participants(prompt)

        mermaid = ["sequenceDiagram"]
        for i, participant in enumerate(participants[:4]):
            mermaid.append(f'    participant P{i + 1} as {participant}')

        # 添加交互
        if len(participants) >= 2:
            mermaid.append(f'    P1->>P2: 发起操作')
            mermaid.append(f'    P2-->>P1: 返回结果')

        return "\n".join(mermaid)

    def _extract_participants(self, prompt: str) -> List[str]:
        """提取参与者"""
        default_participants = ["用户", "系统", "服务", "数据库"]

        # 尝试提取特定实体
        entities = re.findall(r'([A-Z][a-z]+|[一-龥]{2,4})', prompt)
        return entities[:4] if entities else default_participants


class ClassDiagramStrategy(DiagramStrategy):
    """类图生成策略"""

    def get_diagram_type(self) -> str:
        return "classDiagram"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成类图"""
        # 检测继承、实现等关系
        has_inheritance = any(word in prompt.lower() for word in ['继承', 'extends', 'parent', 'child'])
        has_interface = any(word in prompt.lower() for word in ['接口', 'interface', 'implements'])

        if has_inheritance or has_interface:
            return self._generate_complex_class_diagram(prompt)
        else:
            return self._generate_simple_class_diagram(prompt)

    def _generate_simple_class_diagram(self, prompt: str) -> str:
        """简单类图"""
        # 提取类名
        class_name = self._extract_class_name(prompt)

        mermaid = [
            "classDiagram",
            f'    class {class_name} {{',
            f'        +属性1',
            f'        +属性2',
            f'        +方法1()',
            f'        +方法2()',
            f'    }}'
        ]
        return "\n".join(mermaid)

    def _generate_complex_class_diagram(self, prompt: str) -> str:
        """复杂类图（包含继承关系）"""
        parent = self._extract_parent_class(prompt)
        child = self._extract_child_class(prompt)

        mermaid = [
            "classDiagram",
            f'    class {parent} {{',
            f'        +父类方法()',
            f'    }}',
            f'    class {child} {{',
            f'        +子类方法()',
            f'    }}',
            f'    {child} --|> {parent}'
        ]
        return "\n".join(mermaid)

    def _extract_class_name(self, prompt: str) -> str:
        """提取类名"""
        # 尝试提取大写开头的词
        match = re.search(r'\b([A-Z][a-zA-Z0-9]*)\b', prompt)
        return match.group(1) if match else "ExampleClass"

    def _extract_parent_class(self, prompt: str) -> str:
        """提取父类名"""
        match = re.search(r'([A-Z][a-zA-Z0-9]*)\s*(?:继承|extends)', prompt)
        return match.group(1) if match else "BaseClass"

    def _extract_child_class(self, prompt: str) -> str:
        """提取子类名"""
        match = re.search(r'(?:继承|extends)\s*([A-Z][a-zA-Z0-9]*)', prompt)
        return match.group(1) if match else "DerivedClass"


class StateDiagramStrategy(DiagramStrategy):
    """状态图生成策略"""

    def get_diagram_type(self) -> str:
        return "stateDiagram-v2"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成状态图"""
        mermaid = [
            "stateDiagram-v2",
            "    [*] --> 待处理",
            "    待处理 --> 处理中",
            "    处理中 --> 已完成",
            "    处理中 --> 失败",
            "    失败 --> 待处理",
            "    已完成 --> [*]"
        ]
        return "\n".join(mermaid)


class ERDiagramStrategy(DiagramStrategy):
    """ER图生成策略"""

    def get_diagram_type(self) -> str:
        return "erDiagram"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成ER图"""
        mermaid = [
            "erDiagram",
            "    USER ||--o{ ORDER : places",
            "    ORDER ||--|{ ITEM : contains",
            "    USER {",
            "        int id PK",
            "        string name",
            "        string email",
            "    }",
            "    ORDER {",
            "        int id PK",
            "        date created",
            "        string status",
            "    }"
        ]
        return "\n".join(mermaid)


class MindMapStrategy(DiagramStrategy):
    """思维导图生成策略"""

    def get_diagram_type(self) -> str:
        return "mindmap"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成思维导图"""
        # 提取主题和分支
        topic = self._extract_topic(prompt)

        mermaid = [
            "mindmap",
            f"  root(({topic}))",
            "    概念1",
            "      子概念A",
            "      子概念B",
            "    概念2",
            "      子概念C",
            "      子概念D"
        ]
        return "\n".join(mermaid)

    def _extract_topic(self, prompt: str) -> str:
        """提取主题"""
        # 取前10个字作为主题
        return prompt[:10] if len(prompt) > 10 else prompt


class GanttStrategy(DiagramStrategy):
    """甘特图生成策略"""

    def get_diagram_type(self) -> str:
        return "gantt"

    def generate(self, prompt: str, context: Dict[str, Any]) -> str:
        """生成甘特图"""
        mermaid = [
            "gantt",
            "    title 项目时间线",
            "    dateFormat  YYYY-MM-DD",
            "    section 阶段1",
            "    任务1           :a1, 2024-01-01, 30d",
            "    任务2           :a2, after a1, 20d",
            "    section 阶段2",
            "    任务3           :b1, after a2, 25d"
        ]
        return "\n".join(mermaid)


class MermaidDiagramGenerator:
    """Mermaid 图表生成器"""

    # 内容类型到图表策略的映射
    CONTENT_TYPE_TO_STRATEGY = {
        'flowchart': FlowchartStrategy(),
        'sequence': SequenceStrategy(),
        'class': ClassDiagramStrategy(),
        'state': StateDiagramStrategy(),
        'er': ERDiagramStrategy(),
        'mindmap': MindMapStrategy(),
        'gantt': GanttStrategy(),
    }

    # 图表类型优先级（按内容关键词匹配）
    DIAGRAM_TYPE_KEYWORDS = {
        'sequence': ['api', '接口', '请求', '响应', '调用', 'request', 'response', '时序', '序列'],
        'class': ['类', '继承', '接口', '实现', 'class', 'interface', 'extends', 'implements'],
        'state': ['状态', '转换', 'state', 'status', '机'],
        'er': ['数据库', '表', '关系', 'database', 'table', 'relation', '实体'],
        'mindmap': ['结构', '知识', '概念', '思维', 'structure', 'knowledge', 'concept'],
        'gantt': ['时间', '计划', '进度', 'timeline', 'schedule', 'plan'],
    }

    def __init__(self, config: Dict[str, Any]):
        """
        初始化生成器

        Args:
            config: 配置字典
        """
        self.mermaid_config = config.get('mermaid', {})
        self.image_config = config.get('image', {})

        # 渲染模式: code (插入代码块) / image (渲染为图片)
        self.render_mode = self.mermaid_config.get('render_mode', 'code')

        # 保存目录
        self.save_dir = Path(self.image_config.get('save_dir', 'output/images'))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 默认图表类型
        self.default_diagram_type = self.mermaid_config.get('default_diagram_type', 'flowchart')

    def generate(self, prompt: str, index: int = 0, image_type: str = 'diagram', context: Dict[str, None] = None, candidate_index: int = 0) -> str:
        """
        生成 Mermaid 图表

        Args:
            prompt: 内容描述
            index: 索引
            image_type: 图片类型（用于推断图表类型）
            context: 额外上下文信息
            candidate_index: 候选图索引（批量模式下使用）

        Returns:
            如果 render_mode='code'，返回空的虚拟路径（用于兼容）
            如果 render_mode='image'，返回图片路径
        """
        if context is None:
            context = {}

        print(f"  正在生成 Mermaid 图表 #{index + 1}...")

        # 确定图表类型
        diagram_type = self._determine_diagram_type(prompt, image_type)

        # 获取对应的策略
        strategy = self.CONTENT_TYPE_TO_STRATEGY.get(diagram_type, FlowchartStrategy())

        print(f"  图表类型: {strategy.get_diagram_type()}")

        # 生成 Mermaid 代码
        mermaid_code = strategy.generate(prompt, context)

        if self.render_mode == 'code':
            # 直接返回 Mermaid 代码块（在 assembler 中处理）
            return self._format_as_mermaid_block(mermaid_code, diagram_type)
        else:
            # 渲染为图片
            return self._render_to_image(mermaid_code, index, diagram_type, candidate_index)

    def _determine_diagram_type(self, prompt: str, image_type: str) -> str:
        """根据内容和类型确定图表类型"""
        prompt_lower = prompt.lower()

        # 检查关键词匹配
        for diagram_type, keywords in self.DIAGRAM_TYPE_KEYWORDS.items():
            if any(keyword in prompt_lower for keyword in keywords):
                return diagram_type

        # 根据 image_type 映射
        type_mapping = {
            'code_concept': 'flowchart',
            'concept': 'flowchart',
            'cover': 'mindmap',
            'section': 'flowchart',
        }
        return type_mapping.get(image_type, self.default_diagram_type)

    def _format_as_mermaid_block(self, mermaid_code: str, diagram_type: str) -> str:
        """格式化为 Mermaid 代码块（特殊标记）"""
        # 使用特殊前缀标记这是 Mermaid 代码
        return f"MERMAID_CODE:{diagram_type}:{mermaid_code}"

    def _render_to_image(self, mermaid_code: str, index: int, diagram_type: str, candidate_index: int = 0) -> str:
        """渲染 Mermaid 为图片（需要 mermaid-cli）"""
        try:
            import subprocess

            # 创建临时文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if candidate_index > 0:
                # 批量模式：在文件名中包含候选索引
                filename = f"{index}_{diagram_type}_{timestamp}_{candidate_index:03d}.png"
            else:
                filename = f"{index}_{diagram_type}_{timestamp}.png"
            filepath = self.save_dir / filename

            # 创建临时 mmd 文件
            mmd_file = self.save_dir / f"temp_{timestamp}.mmd"
            with open(mmd_file, 'w', encoding='utf-8') as f:
                f.write(mermaid_code)

            # 调用 mermaid CLI (需要先安装: npm install -g @mermaid-js/mermaid-cli)
            # mmdc -i input.mmd -o output.png
            result = subprocess.run(
                ['mmdc', '-i', str(mmd_file), '-o', str(filepath), '-b', 'transparent'],
                capture_output=True,
                timeout=30
            )

            # 清理临时文件
            mmd_file.unlink(missing_ok=True)

            if result.returncode == 0:
                print(f"  已渲染到: {filepath}")
                return str(filepath)
            else:
                print(f"  mermaid CLI 调用失败，使用代码块模式")
                print(f"  错误: {result.stderr.decode()}")
                return self._format_as_mermaid_block(mermaid_code, diagram_type)

        except (FileNotFoundError, ImportError) as e:
            print(f"  未安装 mermaid CLI，使用代码块模式")
            print(f"  安装方法: npm install -g @mermaid-js/mermaid-cli")
            return self._format_as_mermaid_block(mermaid_code, diagram_type)
        except Exception as e:
            print(f"  渲染失败: {e}")
            return self._format_as_mermaid_block(mermaid_code, diagram_type)

    def generate_batch(self, prompts: list, contexts: list = None) -> list:
        """批量生成图表"""
        if contexts is None:
            contexts = [{}] * len(prompts)

        results = []
        for i, (prompt, context) in enumerate(zip(prompts, contexts)):
            try:
                result = self.generate(prompt, i, context=context)
                results.append(result)
            except Exception as e:
                print(f"  第 {i + 1} 个图表生成失败: {e}")
                results.append(None)
        return results


# 便捷函数：判断是否是 Mermaid 代码块
def is_mermaid_code(image_path: str) -> bool:
    """判断给定的路径是否是 Mermaid 代码块标记"""
    return isinstance(image_path, str) and image_path.startswith("MERMAID_CODE:")


# 便捷函数：解析 Mermaid 代码块
def parse_mermaid_code(image_path: str) -> tuple:
    """
    解析 Mermaid 代码块标记

    Returns:
        (diagram_type, mermaid_code)
    """
    if not is_mermaid_code(image_path):
        return None, None

    # 格式: MERMAID_CODE:diagram_type:code
    parts = image_path.split(":", 2)
    if len(parts) >= 3:
        return parts[1], parts[2]
    return None, None
