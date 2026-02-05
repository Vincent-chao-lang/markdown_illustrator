# Markdown Illustrator 技术架构文档

> 版本: v1.8
> 更新时间: 2025-01-20

---

## 目录

1. [系统概述](#系统概述)
2. [整体架构](#整体架构)
3. [核心模块](#核心模块)
4. [数据流转](#数据流转)
5. [设计模式](#设计模式)
6. [多用户架构](#多用户架构)
7. [技术栈](#技术栈)
8. [扩展机制](#扩展机制)
9. [性能优化](#性能优化)
10. [部署架构](#部署架构)

---

## 系统概述

Markdown Illustrator 是一个为 Markdown 文章自动生成配图的智能系统。系统采用模块化设计，支持多种图片来源，具备智能文档分类、LLM 驱动的提示词生成、批量候选图生成等核心功能。

### 核心能力

```
┌─────────────────────────────────────────────────────────────┐
│                    系统能力矩阵                              │
├─────────────────────────────────────────────────────────────┤
│  文档解析   → 自动提取结构化元素（标题/段落/代码块）          │
│  智能分类   → 识别技术文档 vs 普通文档                        │
│  提示词生成 → LLM 驱动的精准描述生成                         │
│  多源生成   → 支持 8 种图片来源（AI/图库/图表）              │
│  批量处理   → 为每位置生成多张候选图                         │
│  增量更新   → 只重新生成指定图片                             │
│  Web 交互   → 可视化预览、选择、编辑                         │
│  多用户     → 会话隔离、配额管理（v1.8）                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 整体架构

### 分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         表现层 (Presentation)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  CLI 入口    │  │  Web 界面    │  │  API 接口    │          │
│  │  (main.py)   │  │ (selector)   │  │  (Flask)     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                         业务层 (Business Logic)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  配图决策    │  │  文档分类    │  │  提示词生成  │          │
│  │ (analyzer)   │  │(classifier)  │  │(prompt_gen)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  来源管理    │  │  增量更新    │  │  会话管理    │          │
│  │(source_mgr)  │  │(regenerate)  │  │(session_mgr) │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                         服务层 (Services)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  图片生成    │  │  LLM 调用    │  │  用户管理    │          │
│  │ (image_gen)  │  │(llm_client)  │  │(user_mgr)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                         数据层 (Data Access)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  文件系统    │  │  配置管理    │  │  会话存储    │          │
│  │(local files) │  │  (yaml)      │  │(memory)      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                         外部服务 (External Services)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  AI 图片API  │  │  LLM API     │  │  图库API     │          │
│  │(zhipu/dalle) │  │(glm-4/gpt)   │  │(unsplash)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       配图处理流程                                │
└─────────────────────────────────────────────────────────────────┘

  输入                   中间处理                    输出
  ─────                  ─────────                   ─────

  Markdown
  └─> parser.py ──────────────┐
                                │
                                ▼
                      MarkdownDocument
                      ├─ title
                      ├─ elements[]
                      └─ metadata
                                │
                                ▼
  ┌───────────────────────────────────────────────────────┐
  │                    analyzer.py                        │
  │  ┌─────────────────┐    ┌─────────────────────────┐   │
  │  │  文档分类        │    │  提示词生成              │   │
  │  │  (classifier)   │───>│  (prompt_generator)     │   │
  │  └─────────────────┘    └─────────────────────────┘   │
  │           │                         │                   │
  │           ▼                         ▼                   │
  │     technical/normal           enhanced_prompt          │
  │           │                         │                   │
  │           ▼                         │                   │
  │  ┌─────────────────┐              │                     │
  │  │  来源选择        │<─────────────┘                   │
  │  │(source_manager) │                                   │
  │  └─────────────────┘                                   │
  │           │                                             │
  │           ▼                                             │
  │     image_source                                        │
  │           │                                             │
  │           ▼                                             │
  │  ┌─────────────────────────────────────────────────┐    │
  │  │              ImageDecision                       │    │
  │  │  ├─ element_index                               │    │
  │  │  ├─ image_type (cover/section/...)              │    │
  │  │  ├─ image_source (mermaid/zhipu/...)            │    │
  │  │  └─ prompt                                      │    │
  │  └─────────────────────────────────────────────────┘    │
  └───────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌───────────────────────────────────────────────────────┐
  │                   image_gen.py                         │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
  │  │ Mermaid  │  │   AI     │  │  图库    │           │
  │  │  Generator│  │ Generator│  │ Generator│          │
  │  └──────────┘  └──────────┘  └──────────┘           │
  └───────────────────────────────────────────────────────┘
                                │
                                ▼
                      image_path(s)
                                │
                                ▼
  ┌───────────────────────────────────────────────────────┐
  │                   assembler.py                         │
  │  将图片插入到 Markdown 的合适位置                       │
  └───────────────────────────────────────────────────────┘
                                │
                                ▼
                      Markdown with Images
```

---

## 核心模块

### 1. Parser 模块 (parser.py)

**职责**: Markdown 文档解析

**核心类**:

```python
class ElementType(Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    LIST = "list"
    QUOTE = "quote"
    # ...

@dataclass
class MarkdownElement:
    type: ElementType
    content: str
    level: int = 0          # 标题层级
    position: int = 0       # 元素位置
    word_count: int = 0     # 字数统计

@dataclass
class MarkdownDocument:
    elements: List[MarkdownElement]
    title: str = ""
    keywords: List[str] = []
    sections: List[Dict] = []
```

**设计要点**:
- 使用正则表达式逐行解析
- 区分元素类型，保留原始结构
- 计算统计信息（字数、行数）用于后续决策

---

### 2. Classifier 模块 (classifier.py)

**职责**: 文档类型分类

**分类策略**:

```
规则分类 (Rule-based)
├─ 代码块计数 (最高40分)
├─ 技术关键词 (最高30分)
├─ 流程关键词 (最高20分)
├─ 结构化程度 (最高10分)
└─ 总分 ≥ 30 → 技术文档

LLM 分类 (可选)
└─ 置信度 < 0.8 时使用 LLM 验证
```

**核心方法**:

```python
def classify(doc_content: str, doc_meta: Dict) -> Dict:
    return {
        'type': 'technical' | 'normal',
        'confidence': float (0-1),
        'reason': str,
        'indicators': Dict
    }
```

**技术关键词**:
- 代码相关: 函数、算法、API、框架...
- 流程相关: 流程、步骤、循环、判断...
- 英文术语: code, function, algorithm, API...

---

### 3. Prompt Generator 模块 (prompt_generator.py)

**职责**: LLM 智能提示词生成

**工作流程**:

```
┌─────────────────────────────────────────────────────────────┐
│                    提示词生成流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  输入                                                        │
│  ├─ element_content: 当前元素内容                           │
│  ├─ image_type: 图片类型                                    │
│  └─ doc_context: 文档上下文                                 │
│      ├─ title: 文章标题                                     │
│      ├─ keywords: 关键词                                    │
│      └─ doc_type: 文档类型                                  │
│                                                             │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────┐                                       │
│  │  LLM 生成基础    │                                       │
│  │  提示词          │                                       │
│  │  (glm-4-flash)   │                                       │
│  └────────┬────────┘                                       │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                       │
│  │  结合规则模板    │                                       │
│  │  优化和长度控制  │                                       │
│  └────────┬────────┘                                       │
│           │                                                 │
│           ▼                                                 │
│  输出: 最终提示词                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**回退机制**:
```
LLM 生成失败 → 使用规则模板 → 保证系统可用性
```

---

### 4. Image Source Manager 模块 (image_source_manager.py)

**职责**: 图片来源选择和降级

**选择逻辑**:

```python
def select_source(image_type, doc_type) -> str:
    # 封面图统一使用 AI
    if image_type == 'cover':
        return 'zhipu'

    # 技术文档使用 Mermaid
    if doc_type == 'technical' and image_type in ['section', 'concept']:
        return 'mermaid'

    # 普通文档使用图库
    return 'unsplash'
```

**降级策略** (未完全实现):
```
Unsplash 失败 → Pexels → AI (zhipu)
```

---

### 5. Image Generator 模块 (image_gen.py)

**职责**: 图片生成工厂

**工厂模式**:

```python
def get_image_generator(config, use_sdk=True, image_source=None):
    if image_source == 'mermaid':
        return MermaidDiagramGenerator(config)
    elif image_source == 'zhipu':
        return ZhipuImageGenerator(config)
    elif image_source == 'dalle':
        return DALLEImageGenerator(config)
    # ...

class ImageGenerator(ABC):
    @abstractmethod
    def generate(prompt, index, image_type) -> str:
        pass
```

**统一接口**:
```python
image_path = generator.generate(
    prompt: str,
    index: int = 0,
    image_type: str = 'image',
    candidate_index: int = 0  # 批量模式
)
```

---

### 6. Analyzer 模块 (analyzer.py)

**职责**: 内容分析和配图决策

**决策流程**:

```
MarkdownDocument
      │
      ▼
┌─────────────────────────────────────────┐
│  遍历 elements                          │
│  for each element:                      │
│                                         │
│  1. 判断是否需要配图                     │
│     ├─ H1 后 → cover                   │
│     ├─ H2 后 → section (smart判断)     │
│     └─ 长段落 → atmospheric             │
│                                         │
│  2. 决定图片类型                         │
│                                         │
│  3. 选择图片来源                         │
│     ├─ 调用 classifier 分类            │
│     ├─ 调用 source_manager 选择        │
│     └─ 智能模式 (auto) 时动态选择       │
│                                         │
│  4. 生成提示词                           │
│     ├─ LLM 智能生成 (如果启用)          │
│     └─ 回退到规则模板                   │
│                                         │
│  5. 创建 ImageDecision                  │
└─────────────────────────────────────────┘
      │
      ▼
List[ImageDecision]
```

---

### 7. Regenerate 模块 (regenerate.py)

**职责**: 增量更新处理

**更新类型**:

```python
# 按索引更新
--regenerate 0          # 第1张图片

# 按类型更新
--regenerate-type cover # 所有封面图

# 失败重试
--regenerate-failed     # 之前失败的图片
```

**处理流程**:

```
现有 Markdown
      │
      ▼
┌─────────────────────────────────────────┐
│  解析已生成的图片                         │
│  (正则匹配 ![alt](path))                 │
│                                         │
│  分类:                                   │
│  ├─ keep: 保留                          │
│  ├─ regenerate: 需要重新生成             │
│  └─ missing: 新增位置                   │
└─────────────────────────────────────────┘
      │
      ▼
只生成指定的图片
      │
      ▼
┌─────────────────────────────────────────┐
│  重组 Markdown                           │
│  ├─ 保留 keep 的图片                     │
│  ├─ 插入 regenerate 的新图片             │
│  └─ 添加 missing 位置的图片              │
└─────────────────────────────────────────┘
```

---

### 8. Web Server 模块 (web_server.py)

**职责**: Web 交互服务器 (v1.8 多用户)

**架构**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Web 服务器                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              认证层 (Authentication)                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │
│  │  │  UserManager │  │   Login      │  │   Logout     │  │ │
│  │  │  (用户管理)  │  │  (登录认证)  │  │  (注销清理)  │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              会话层 (Session Management)                │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │         SessionManager                          │   │ │
│  │  │  sessions: {session_id: ImageSelectorServer}     │   │ │
│  │  │  user_quota: {username: {date: count}}          │   │ │
│  │  │  temp_dir: /temp/sessions/<session_id>/         │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │
│  │  │  RateLimiter │  │ 配额检查     │  │ 会话清理     │  │ │
│  │  │  (速率限制)  │  │(quota_check) │  │  (cleanup)   │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐ │
│  │              路由层 (Routes)                            │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐       │ │
│  │  │ /login     │  │ /logout    │  │ /api/me    │       │ │
│  │  ├────────────┤  ├────────────┤  ├────────────┤       │ │
│  │  │ /          │  │/api/status │  │/api/upload │       │ │
│  │  ├────────────┤  ├────────────┤  ├────────────┤       │ │
│  │  │/api/markdown│  │/api/...    │  │             │       │ │
│  │  └────────────┘  └────────────┘  └────────────┘       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键设计**:
- 会话隔离: 每个用户独立的 `ImageSelectorServer` 实例
- 文件隔离: 会话级临时目录 `temp/sessions/<session_id>/`
- 速率限制: 配图 10次/小时，保存 100次/小时
- 配额管理: 每日配图次数限制

---

## 数据流转

### 核心数据结构

```
MarkdownDocument
├─ elements: List[MarkdownElement]
│   ├─ type: ElementType
│   ├─ content: str
│   ├─ level: int
│   └─ position: int
├─ title: str
├─ keywords: List[str]
└─ doc_type: str  # 'technical' | 'normal'

ImageDecision
├─ element_index: int
├─ element_type: ElementType
├─ element_content: str
├─ image_type: str  # cover/section/concept/...
├─ image_source: str  # mermaid/zhipu/unsplash/...
└─ prompt: str

ImageContext
├─ title: str
├─ keywords: List[str]
├─ doc_type: str
├─ total_images: int
└─ sections: List[Dict]
```

### 完整数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据流转图                                │
└─────────────────────────────────────────────────────────────────┘

输入层
──────
Markdown File (磁盘)
      │
      ▼
解析层
──────
parser.parse()
      │
      ├─> MarkdownDocument
      │    ├─ elements: List[MarkdownElement]
      │    ├─ title: str
      │    └─ metadata: Dict
      │
      ▼
分析层
──────
analyzer.analyze(doc, config, image_source)
      │
      ├─> classifier.classify()
      │    └─> {type: 'technical', confidence: 0.85}
      │
      ├─> source_manager.select_source()
      │    └─> 'mermaid'
      │
      ├─> prompt_generator.generate()
      │    └─> 'React状态管理流程图...'
      │
      └─> List[ImageDecision]
           ├─ element_index: 0
           ├─ image_type: 'cover'
           ├─ image_source: 'zhipu'
           └─ prompt: '...'
      │
      ▼
生成层
──────
image_gen.get_generator(source)
      │
      ├─> MermaidDiagramGenerator
      ├─> ZhipuImageGenerator
      ├─> DALLEImageGenerator
      ├─> UnsplashImageGenerator
      └─> ...
      │
      └─> image_path: str
      │
      ▼
组装层
──────
assembler.assemble(markdown, decisions, images)
      │
      └─> Markdown with Images
      │
      ▼
输出层
──────
output.md (磁盘) + images/ (目录)
```

---

## 设计模式

### 1. 工厂模式 (Factory)

**位置**: `image_gen.py`

```python
# 抽象产品
class ImageGenerator(ABC):
    @abstractmethod
    def generate(prompt, index, image_type) -> str:
        pass

# 具体产品
class ZhipuImageGenerator(ImageGenerator):
    def generate(self, prompt, index, image_type) -> str:
        # 智谱AI生成逻辑

class MermaidDiagramGenerator(ImageGenerator):
    def generate(self, prompt, index, image_type) -> str:
        # Mermaid生成逻辑

# 工厂
def get_image_generator(config, use_sdk, image_source) -> ImageGenerator:
    if image_source == 'zhipu':
        return ZhipuImageGenerator(config)
    elif image_source == 'mermaid':
        return MermaidDiagramGenerator(config)
    # ...
```

**优点**:
- 易于扩展新的图片来源
- 客户端代码与具体实现解耦

---

### 2. 策略模式 (Strategy)

**位置**: `classifier.py`, `image_source_manager.py`

```python
# 文档分类策略
class ClassificationStrategy(ABC):
    @abstractmethod
    def classify(self, content, meta) -> Dict:
        pass

class RuleBasedStrategy(ClassificationStrategy):
    def classify(self, content, meta) -> Dict:
        # 基于规则的分类

class LLMBasedStrategy(ClassificationStrategy):
    def classify(self, content, meta) -> Dict:
        # 基于LLM的分类

# 上下文
class DocumentClassifier:
    def __init__(self):
        self.rule_strategy = RuleBasedStrategy()
        self.llm_strategy = LLMBasedStrategy()

    def classify(self, content, meta):
        result = self.rule_strategy.classify(content, meta)
        if result['confidence'] < 0.8:
            return self.llm_strategy.classify(content, meta)
        return result
```

---

### 3. 建造者模式 (Builder)

**位置**: `assembler.py`

```python
class MarkdownBuilder:
    def __init__(self):
        self.lines = []
        self.images = {}

    def add_line(self, line: str):
        self.lines.append(line)
        return self

    def insert_image(self, position: int, image: ImageInfo):
        self.images[position] = image
        return self

    def build(self) -> str:
        # 组装最终Markdown
        return '\n'.join(self.lines)

# 使用
builder = MarkdownBuilder()
builder.add_line('# Title')
    .insert_image(0, image_info)
    .add_line('Content')
result = builder.build()
```

---

### 4. 单例模式 (Singleton)

**位置**: `web_server.py`

```python
# 全局单例
session_manager = SessionManager()
user_manager = UserManager()
rate_limiter = RateLimiter()
```

**注意**: 多进程环境下需使用进程级单例或分布式存储

---

## 多用户架构

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     多用户架构 (v1.8)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐    │
│  │                  Gunicorn 多进程                       │    │
│  │  Worker 1  │  Worker 2  │  Worker 3  │  Worker 4      │    │
│  │  ──────────┼───────────┼───────────┼────────────────  │    │
│  │  ┌─────────────────────────────────────────────────┐  │    │
│  │  │         Flask Application (每个Worker独立)       │  │    │
│  │  │                                                 │  │    │
│  │  │  ┌─────────────────────────────────────────┐    │  │    │
│  │  │  │         SessionManager (内存存储)        │    │  │    │
│  │  │  │  sessions: {                             │    │  │    │
│  │  │  │    session_id_1: ImageSelectorServer,     │    │  │    │
│  │  │  │    session_id_2: ImageSelectorServer,     │    │  │    │
│  │  │  │    ...                                   │    │  │    │
│  │  │  │  }                                        │    │  │    │
│  │  │  └─────────────────────────────────────────┘    │  │    │
│  │  │                                                 │  │    │
│  │  │  User A (Session ID: xxx) ──┐                  │  │    │
│  │  │  User B (Session ID: yyy) ──┼──> 隔离的数据     │  │    │
│  │  │  User C (Session ID: zzz) ──┘                  │  │    │
│  │  │                                                 │  │    │
│  │  └─────────────────────────────────────────────────┘    │  │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐    │
│  │                  文件系统隔离                          │    │
│  │  temp/sessions/                                       │    │
│  │  ├─ xxx/  (User A)                                   │    │
│  │  │  ├─ input.md                                     │    │
│  │  │  └─ images/                                      │    │
│  │  ├─ yyy/  (User B)                                   │    │
│  │  │  ├─ input.md                                     │    │
│  │  │  └─ images/                                      │    │
│  │  └─ zzz/  (User C)                                   │    │
│  │     ├─ input.md                                     │    │
│  │     └─ images/                                      │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 会话隔离机制

```python
class SessionManager:
    def __init__(self):
        # 会话 -> 服务器实例映射
        self.sessions: Dict[str, ImageSelectorServer] = {}

        # 用户 -> 配额使用
        self.user_quota: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 临时目录
        self.temp_dir = PROJECT_ROOT / 'temp' / 'sessions'

    def get_server(self, session_id: str) -> ImageSelectorServer:
        """获取会话对应的服务器实例"""
        return self.sessions.get(session_id)

    def set_server(self, session_id: str, server: ImageSelectorServer):
        """设置会话的服务器实例"""
        self.sessions[session_id] = server

    def get_session_temp_dir(self, session_id: str) -> Path:
        """获取会话的临时文件目录"""
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir
```

### 速率限制

```python
class RateLimiter:
    def __init__(self):
        # {session_id:endpoint: [timestamp1, timestamp2, ...]}
        self.requests: Dict[str, List[float]] = defaultdict(list)

        self.limits = {
            'illustrate': {'max': 10, 'window': 3600},  # 10次/小时
            'save': {'max': 100, 'window': 3600},
            'default': {'max': 1000, 'window': 3600}
        }

    def is_allowed(self, session_id: str, endpoint: str) -> bool:
        key = f"{session_id}:{endpoint}"
        now = time.time()

        # 清理过期记录
        self.requests[key] = [t for t in self.requests[key]
                              if now - t < self.limits[endpoint]['window']]

        # 检查是否超限
        if len(self.requests[key]) >= self.limits[endpoint]['max']:
            return False

        # 记录本次请求
        self.requests[key].append(now)
        return True
```

---

## 技术栈

### 后端技术

| 组件 | 技术选型 | 说明 |
|-----|---------|------|
| 语言 | Python 3.7+ | 主要开发语言 |
| Web框架 | Flask | 轻量级Web框架 |
| WSGI服务器 | Gunicorn | 生产环境多进程部署 |
| 配置管理 | PyYAML | 配置文件解析 |
| HTTP客户端 | requests | API调用 |
| 环境变量 | python-dotenv | .env文件支持 |

### AI/LLM服务

| 服务 | SDK | 用途 |
|-----|-----|------|
| 智谱AI | zhipuai | 图片生成 + LLM |
| OpenAI | openai | DALL-E + GPT |
| 火山引擎 | openai | 豆包文生图 |

### 前端技术

| 组件 | 技术选型 | 说明 |
|-----|---------|------|
| CSS框架 | Tailwind CDN | 快速样式开发 |
| Markdown渲染 | Marko | 服务端渲染 |
| 图表渲染 | Mermaid.js | 技术图表渲染 |
| 图标 | - | Emoji文本图标 |

### 数据存储

| 类型 | 技术 | 说明 |
|-----|------|------|
| 配置 | YAML文件 | settings.yaml, users.yaml |
| 会话 | 内存字典 | SessionManager.sessions |
| 文件 | 本地文件 | Markdown + 图片 |
| 临时 | 临时目录 | temp/sessions/<session_id>/ |

---

## 扩展机制

### 添加新图片来源

**步骤**:

1. **创建生成器类** (`src/my_gen.py`):

```python
from image_gen import ImageGenerator

class MyImageGenerator(ImageGenerator):
    def __init__(self, config):
        self.api_key = config['api'].get('my_api_key', '')
        self.save_dir = Path(config['image']['save_dir'])

    def generate(self, prompt: str, index: int = 0,
                  image_type: str = 'image', candidate_index: int = 0) -> str:
        # 1. 调用API生成图片
        # 2. 下载到本地
        # 3. 返回本地路径
        return image_path

    def generate_batch(self, prompts: list) -> list:
        # 批量生成（可选）
        pass
```

2. **注册到工厂** (`image_gen.py`):

```python
def get_image_generator(config, use_sdk=True, image_source=None):
    # ...
    elif image_source == 'my_source':
        from my_gen import MyImageGenerator
        return MyImageGenerator(config)
    # ...
```

3. **添加配置** (`config/settings.yaml`):

```yaml
api:
  my_api_key: ""  # 在.env中配置
```

---

### 添加新的图片类型

**步骤**:

1. **更新 ElementType** (如需要):

```python
class ImageType(Enum):
    COVER = "cover"
    SECTION = "section"
    # 添加新类型
    CUSTOM_TYPE = "custom_type"
```

2. **更新决策逻辑** (`analyzer.py`):

```python
def _determine_image_type(self, element: MarkdownElement) -> str:
    if element.type == ElementType.HEADING and element.level == 1:
        return 'cover'
    # 添加新类型的判断逻辑
    if some_condition:
        return 'custom_type'
```

3. **添加提示词模板** (`config/settings.yaml`):

```yaml
prompts:
  zhipu:
    custom_type: "{title}，自定义类型图片描述"
```

---

## 性能优化

### 1. 并发处理

**Gunicorn 多进程部署**:

```python
# gunicorn_conf.py
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1  # CPU核心数 * 2 + 1
worker_class = "sync"
worker_connections = 1000
```

**并发能力**:
- 8核CPU = 17 workers
- 理论上可同时处理17个配图请求
- 适合50人团队使用

### 2. 会话管理

**定期清理过期会话**:

```python
def cleanup_task():
    """后台线程，每小时执行一次"""
    while True:
        time.sleep(3600)
        session_manager.cleanup_old_sessions(max_age_hours=24)
```

**清理逻辑**:
- 检查会话目录最后修改时间
- 超过24小时未访问的会话将被删除
- 释放内存和磁盘空间

### 3. 速率限制

**多层级限制**:

```
用户级配额
├─ 每日配图次数限制 (quota_limit)
└─ 达到限制后返回 429 错误

会话级速率
├─ 配图: 10次/小时
├─ 保存: 100次/小时
└─ 其他: 1000次/小时
```

### 4. 文件缓存

**图片本地缓存**:
- 所有生成的图片保存到 `output/images/`
- 避免重复生成相同内容的图片
- 支持手动复用图片

---

## 部署架构

### 开发环境

```
┌─────────────────────────────────────────────────────────────┐
│                    开发环境架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  python src/web_server.py --debug                          │
│         │                                                   │
│         ▼                                                   │
│  Flask Development Server                                   │
│  ├─ 单进程                                                  │
│  ├─ 自动重载                                                │
│  ├─ 调试模式                                                │
│  └─ 端口: 5000                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 生产环境

```
┌─────────────────────────────────────────────────────────────┐
│                    生产环境架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Nginx (可选)                              │  │
│  │  ├─ 反向代理                                           │  │
│  │  ├─ 静态文件服务                                       │  │
│  │  ├─ SSL/TLS 终止                                       │  │
│  │  └─ 负载均衡                                           │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Gunicorn WSGI Server                      │  │
│  │  Master Process                                       │  │
│  │  ├─ Worker 1 (独立进程)                                │  │
│  │  ├─ Worker 2 (独立进程)                                │  │
│  │  ├─ Worker N (独立进程)                                │  │
│  │  └─ 自动重启 Worker                                     │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Flask Application                         │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │         SessionManager (每个Worker独立)          │  │  │
│  │  │         UserManager (共享配置)                    │  │  │
│  │  │         RateLimiter (每个Worker独立)             │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              File System                               │  │
│  │  ├─ output/images/ (共享)                             │  │
│  │  └─ temp/sessions/ (每个Worker独立访问)               │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 部署清单

**系统服务** (systemd):

```bash
# /etc/systemd/system/markdown-illustrator.service
[Unit]
Description=Markdown Illustrator Multi-User Server
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/markdown_illustrator
ExecStart=/opt/markdown_illustrator/venv/bin/gunicorn -c gunicorn_conf.py src.web_server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**启动命令**:

```bash
# 方式1: 启动脚本
./start_server.sh prod

# 方式2: 直接使用 Gunicorn
gunicorn -c gunicorn_conf.py src.web_server:app

# 方式3: systemd
sudo systemctl start markdown-illustrator
```

---

## 安全设计

### 1. 认证安全

```python
# 密码哈希存储
def _hash_password(self, password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# 会话管理
session['username'] = user['username']
session['session_id'] = secrets.token_urlsafe(16)
session.permanent = True
```

### 2. API Key 保护

```python
# 使用环境变量
api_key = os.environ.get('ZHIPUAI_API_KEY')

# .env 文件不提交到版本控制
# .envignore
.env
*.key
```

### 3. 文件隔离

```python
# 每个会话独立目录
session_dir = temp_dir / session_id / 'input.md'
# 防止路径穿越
filepath = Path(filepath).resolve()
if not str(filepath).startswith(str(session_dir)):
    raise ValueError("Invalid file path")
```

---

## 监控与日志

### 日志策略

```python
# Gunicorn 配置
accesslog = "-"  # 输出到 stdout
errorlog = "-"   # 输出到 stderr
loglevel = "info"
```

### 监控指标

| 指标 | 获取方式 |
|-----|---------|
| 活跃会话数 | `len(session_manager.sessions)` |
| 用户配额使用 | `session_manager.get_user_quota_today(username)` |
| 请求速率 | `rate_limiter.get_remaining(session_id, endpoint)` |
| Worker状态 | Gunicorn master 监控 |

---

## 故障处理

### 常见问题

| 问题 | 原因 | 解决方案 |
|-----|------|---------|
| LLM调用失败 | API Key错误/网络问题 | 自动回退到规则模板 |
| 图片生成失败 | API限流/超时 | 重试机制 (max_retries=3) |
| 会话丢失 | 临时文件被清理 | 检查cleanup配置 |
| 内存溢出 | 会话过多 | 定期清理+限制会话数 |

### 错误处理策略

```python
try:
    # 尝试 LLM 生成
    prompt = self._llm_generate(...)
except Exception as e:
    logger.warning(f"LLM generation failed: {e}")
    # 回退到规则模板
    prompt = self._template_generate(...)

# 图片生成重试
for attempt in range(max_retries):
    try:
        return self._generate_image(...)
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep((attempt + 1) * 2)
        else:
            raise
```

---

## 未来规划

### 完整改造（待安排）

```
当前中等改造
    │
    ├─ 单进程多会话
    ├─ 内存存储
    ├─ Flask开发服务器/Gunicorn
    └─ 适合 10-50 人
    │
    ▼
完整改造目标
    │
    ├─ 任务队列 (Celery + Redis)
    ├─ 数据库持久化 (PostgreSQL)
    ├─ 缓存层 (Redis)
    ├─ WebSocket 实时推送
    ├─ K8s 自动扩缩容
    └─ 适合 公开服务
```

### 改进方向

1. **异步任务队列**
   - 使用 Celery + Redis
   - 图片生成异步化
   - 任务进度实时推送

2. **数据持久化**
   - PostgreSQL 存储用户、任务、配额
   - Redis 缓存会话和配置

3. **监控告警**
   - Prometheus + Grafana
   - API 调用统计
   - 成本监控

4. **负载均衡**
   - Nginx 反向代理
   - 多服务器部署
   - Redis 共享会话

---

## 附录

### 配置文件完整示例

```yaml
# config/settings.yaml
image_source: auto

api:
  api_key: ""
  model: cogview-4
  timeout: 60
  max_retries: 3

image:
  size: 1024x1024
  save_dir: output/images
  use_cdn: false
  cdn_url: ""

rules:
  h1_after: true
  h2_after: "smart"
  long_paragraph_threshold: 150
  min_gap_between_images: 3
  max_images_per_article: 10

llm:
  enabled: true
  provider: zhipu
  model: glm-4-flash
  api_key: ""
  max_tokens: 300

mermaid:
  render_mode: code
  default_diagram_type: flowchart
  auto_detect_type: true

prompts:
  zhipu:
    cover: "{title}，极简风格，白色背景"
    section: "{topic}，简洁明了"
```

### API 接口规范

```
POST /api/illustrate
Content-Type: application/json

Request:
{
  "content": "Markdown content",
  "batch": 3,
  "imageSource": "auto"
}

Response:
{
  "success": true,
  "content": "Generated markdown",
  "path": "/path/to/file",
  "images_generated": 3,
  "message": "配图成功，生成了 3 张图片",
  "quota_remaining": 47
}
```

---

**文档版本**: v1.0
**最后更新**: 2025-01-20
**维护者**: Markdown Illustrator Team
