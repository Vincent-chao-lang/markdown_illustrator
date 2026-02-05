# Markdown Illustrator - 自动配图系统

![封面图 - Markdown Illustrator - 自动配图系统](output/images/0_cover_20260119_214107.jpg)

*文章封面：Markdown Illustrator - 自动配图系统*

为 Markdown 文章自动生成并插入配图的完整解决方案，支持多种 AI 文生图服务。

## 功能特点

- **智能解析**: 自动解析 Markdown 文章结构（标题、段落、代码块等）
- **智能配图**: 根据内容类型自动决定配图位置和类型
- **智能模式 (NEW)**: 自动识别文档类型，选择最优图片来源
  - 技术文档 → Mermaid 流程图（免费）
  - 普通文档 → Unsplash 图库
  - 封面图 → AI 生成
- **LLM 智能提示词**: 使用 glm-4-flash 理解内容，生成精准提示词
- **批量生成**: 为每个位置生成多张候选图供选择，解决文生图效果不理想的问题
- **增量更新**: 支持只重新生成指定图片，保留其他已生成的图片
- **Web 交互界面**: 提供可视化界面，支持预览、选择和编辑 Markdown
  - 实时预览带 Mermaid 图表的渲染效果
  - 可视化选择候选图
  - 在线编辑并保存修改
  - 一键导出 Markdown 文件
  - **图片来源选择器 (NEW)**: Web 界面可选择图片来源
  - **内置帮助文档 (NEW)**: 点击"❓ 帮助"按钮查看使用说明
  - 直接在页面上为内容配图
- **多源支持**: 支持 8 种图片来源
  - **auto** - 智能选择（推荐）
  - 智谱 CogView (中文优化)
  - DALL-E 3 (OpenAI)
  - 豆包文生图 (火山引擎 Ark)
  - Flux.1 (高质量)
  - Unsplash (免费图库)
  - Pexels (免费图库)
  - Mermaid (免费)
- **灵活配置**: YAML 配置文件 + 环境变量 + 命令行参数
- **提示词优化**: 针对不同模型优化的中文/英文提示词

## 项目结构

```
markdown_illustrator/
├── config/
│   └── settings.yaml       # 配置文件
├── src/
│   ├── main.py            # 主入口和 CLI
│   ├── parser.py          # Markdown 解析器
│   ├── analyzer.py        # 内容分析器（含 LLM 智能提示词）
│   ├── classifier.py      # 文档分类器（技术/普通文档）
│   ├── prompt_generator.py # LLM 智能提示词生成器
│   ├── image_source_manager.py # 图片源管理器
│   ├── image_gen.py       # 图片生成器工厂
│   ├── zhipu_gen.py       # 智谱 CogView 实现
│   ├── doubao_gen.py      # 豆包 + Flux.1 实现
│   ├── dalle_gen.py       # DALL-E 3 实现
│   ├── unsplash_gen.py    # Unsplash/Pexels 实现
│   ├── mermaid_gen.py     # Mermaid 技术图表生成
│   ├── assembler.py       # Markdown 重组器
│   ├── web_server.py      # Web 交互服务器
│   └── regenerate.py      # 增量更新模块
├── templates/
│   └── selector.html      # Web 选择器模板
├── static/
│   └── assets/            # 静态资源
├── output/
│   └── images/            # 图片保存目录
├── examples/              # 示例文件
├── requirements.txt        # 依赖
├── .env.example           # 环境变量模板
├── mi.py                  # 命令行快捷入口
└── README.md
```

## 安装

```
# 安装依赖
pip install -r requirements.txt
```

## 配置

### 1. 获取 API Key

根据你使用的图片来源，在相应平台注册并获取 API Key：

| 提供商 | 注册地址 |
|-------|---------|
| 智谱 CogView | https://open.bigmodel.cn/ |
| 智谱 LLM | https://open.bigmodel.cn/ |
| DALL-E 3 | https://platform.openai.com/api-keys |
| 豆包 (火山引擎) | https://console.volcengine.com/ark |
| Flux.1 | https://replicate.com (需 GitHub 账号) |
| DeepSeek LLM | https://platform.deepseek.com/ |
| Unsplash | https://unsplash.com/developers |
| Pexels | https://www.pexels.com/api/ |

### 2. 设置 API Key

**使用 `.env` 文件（推荐）**

```
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
```

`.env` 文件格式：

```
# 智谱AI CogView / LLM
ZHIPUAI_API_KEY=your_api_key_here

# 豆包 (火山引擎 Ark)
ARK_API_KEY=your_ark_api_key_here

# Flux.1 (Replicate)
FLUX_API_KEY=your_flux_api_key_here

# OpenAI DALL-E 3 / LLM
OPENAI_API_KEY=your_openai_key_here

# DeepSeek LLM
DEEPSEEK_API_KEY=your_deepseek_key_here

# Unsplash
UNSPLASH_ACCESS_KEY=your_unsplash_key_here

# Pexels
PEXELS_API_KEY=your_pexels_key_here
```

**或使用命令行参数**

```
python src/main.py article.md --api-key your_key
```

### 3. 选择图片来源

在 `config/settings.yaml` 中设置默认图片来源：

```
image_source: auto  # 可选: auto, zhipu, dalle, doubao, flux, unsplash, pexels, mermaid
```

**推荐使用 `auto` 智能模式**：
- 系统自动识别文档类型（技术/普通）
- 技术文档使用 Mermaid（免费）
- 普通文档使用 Unsplash 图库
- 封面图统一使用 AI 生成

## 使用方法

### 命令行使用

```
# 基本使用（使用配置文件中设置的默认图片来源）
python mi.py article.md

# 使用智能模式（推荐）
python mi.py article.md --source auto

# 指定图片来源
python mi.py article.md --source mermaid   # Mermaid (免费技术图表)
python mi.py article.md --source doubao    # 豆包 (最便宜 0.005元/张)
python mi.py article.md --source flux      # Flux.1 (质量好 0.01元/张)
python mi.py article.md --source zhipu     # 智谱 CogView (0.06元/张)
python mi.py article.md --source dalle     # DALL-E 3 (0.4元/张)
python mi.py article.md --source unsplash  # Unsplash 免费图库
python mi.py article.md --source pexels    # Pexels 免费图库

# 指定 CogView 模型
python mi.py article.md --source zhipu --model cogview-4 #cogview-3-flash cogview-3-plus

# 指定输出文件
python mi.py article.md -o article_with_images.md

# 只分析不生成图片（dry run）
python mi.py article.md --dry-run

# 调试模式：打印完整提示词
python mi.py article.md --debug

# 调试模式 + 干运行（查看提示词但不生成）
python mi.py article.md --debug --dry-run

# 指定 API Key
python mi.py article.md --api-key your_key
```

### 批量生成模式

AI 文生图往往很难一次生成满意的结果。批量生成模式为每个配图位置生成 N 张候选图，你可以选择最满意的一张。

```
# 为每个位置生成 3 张候选图
python mi.py article.md --batch 3 --source zhipu

# 批量生成 + 调试模式
python mi.py article.md --batch 3 --debug

# 使用 Mermaid 批量生成（免费测试）
python mi.py article.md --batch 3 --source mermaid

# 使用智能模式批量生成
python mi.py article.md --batch 3 --source auto
```

**生成的文件命名格式**：
```
# 批量模式的文件名包含候选索引
0_cover_20260119_143000_000.png    # 第1张候选图（默认选中）
0_cover_20260119_143000_001.png    # 第2张候选图
0_cover_20260119_143000_002.png    # 第3张候选图
```

**Markdown 输出格式**：
```markdown
<!-- 候选图：从3张中选择第1张 -->

![封面图 - 文章标题](0_cover_20260119_143000_000.png) ⭐

<!-- 其他候选图已注释

<!-- 候选2: ![封面图 - 文章标题](0_cover_20260119_143000_001.png) -->
<!-- 候选3: ![封面图 - 文章标题](0_cover_20260119_143000_002.png) -->

-->
```

**使用方式**：
1. 运行批量生成命令
2. 查看所有候选图，选择最满意的一张
3. 手动编辑 Markdown 文件，取消注释你选择的候选图，注释掉其他候选图

### 增量更新模式

当文章中某些图片不满意时，可以使用增量更新模式只重新生成指定的图片，其他图片保持不变。

```
# 只重新生成第 1 张图片（索引从 0 开始）
python mi.py article.md --regenerate 0

# 只重新生成第 3 张图片
python mi.py article.md --regenerate 2

# 重新生成所有封面图
python mi.py article.md --regenerate-type cover

# 重新生成所有章节配图
python mi.py article.md --regenerate-type section

# 只重新生成失败的图片
python mi.py article.md --regenerate-failed

# 批量模式 + 增量更新（为指定位置生成新的候选图）
python mi.py article.md --regenerate 2 --batch 3
```

**工作流程**：
```
Step 1: 解析现有 Markdown 文件
  └─> 找到已生成的图片

Step 2: 分析需要重新生成的图片
  ├─> keep: 保留现有图片
  ├─> regenerate: 需要重新生成的图片
  └─> missing: 新增的图片位置

Step 3: 只生成指定的图片
  └─> 其他图片保持原样

Step 4: 重组 Markdown 文件
  └─> 输出包含新旧图片的完整文件
```

**使用场景**：
- 某张图片效果不好，只想重新生成这一张
- 想为某个位置尝试更多候选图（`--regenerate N --batch 3`）
- 某类图片（如封面图）需要统一更换风格
- 之前生成失败，只想重新生成失败的图片

**示例**：
```bash
# 假设文章有 5 张配图，你对第 3 张不满意
# 1. 只重新生成第 3 张，生成 3 张候选图供选择
python src/main.py article.md --regenerate 2 --batch 3 --source zhipu

# 2. 查看生成的候选图，选择满意的一张
# 3. 手动编辑 article.md，选中想要的候选图
```

**批量 + 增量组合工作流**：
```bash
# 1. 首次生成：为每个位置生成 3 张候选图
python mi.py article.md --batch 3 --source mermaid

# 2. 对第 2 张图不满意，为该位置重新生成 5 张新候选图
python mi.py article.md --regenerate 1 --batch 5

# 3. 发现所有封面图风格不统一，重新生成所有封面
python mi.py article.md --regenerate-type cover --batch 3
```

### 作为库使用

```
from src.main import MarkdownIllustrator

# 创建实例
illustrator = MarkdownIllustrator()

# 为文章配图
result = illustrator.illustrate(
    input_path='article.md',
    output_path='article_with_images.md',
    image_source='auto',     # 可选：auto, zhipu, dalle, doubao, flux, unsplash, pexels, mermaid
    batch=3,                 # 可选：批量生成模式，为每个位置生成 N 张候选图
    dry_run=False,           # 可选：只分析不生成图片
    debug=False              # 可选：调试模式，打印完整提示词
)

print(f"生成了 {result['images_generated']} 张图片")

# 增量更新：只重新生成第 2 张图片，生成 3 张候选图
result = illustrator.illustrate(
    input_path='article.md',
    image_source='auto',
    regenerate=1,            # 只重新生成索引为 1 的图片
    batch=3                  # 为该位置生成 3 张候选图
)

# 增量更新：重新生成所有封面图
result = illustrator.illustrate(
    input_path='article.md',
    image_source='auto',
    regenerate_type='cover'  # 只重新生成类型为 cover 的图片
)
```

## 配图规则

在 `config/settings.yaml` 中配置：

```
rules:
  # H1 标题后配封面图
  h1_after: true

  # H2 标题后配图 (true/false/"smart"智能判断)
  h2_after: "smart"

  # 长段落配图阈值（字数）
  long_paragraph_threshold: 150

  # 两张图片最小间隔段落数
  min_gap_between_images: 3

  # 单篇文章最大配图数
  max_images_per_article: 10
```

## 图片类型

| 类型 | 使用场景 | Prompt 模板 |
|-----|---------|------------|
| `cover` | H1 标题后 | 封面图，展示文章主题 |
| `section` | H2 标题后 | 章节配图，展示章节内容 |
| `concept` | 概念解释 | 概念示意图，帮助理解 |
| `atmospheric` | 长段落 | 氛围插图，匹配内容情绪 |
| `diagram` | 代码/技术 | 架构图/流程图（Mermaid 使用） |
| `code_concept` | 代码块前 | 代码结构图，流程说明 |

## API 提供商对比

| 提供商 | 价格 | 质量评价 | 中文支持 | 推荐场景 |
|-------|------|---------|---------|---------|
| **auto** | 智能选择 | ⭐⭐⭐⭐⭐ | ✓ | **推荐使用** |
| ↳ Mermaid | 免费 | ⭐⭐⭐⭐⭐ | ✓ | 技术文档、流程图 |
| ↳ Unsplash | 免费 | ⭐⭐⭐⭐ | - | 普通文档、真实照片 |
| ↳ Pexels | 免费 | ⭐⭐⭐⭐ | - | 普通文档、真实照片 |
| ↳ zhipu | 0.06元/张 | ⭐⭐⭐ | ✓✓ | 封面图、中文文章 |
| 豆包 | 0.005元/张 | ⭐⭐ | ✓ | 成本敏感 |
| Flux.1 | 0.01元/张 | ⭐⭐⭐⭐⭐ | - | 质量优先 |
| 智谱 CogView-4 | 0.06元/张 | ⭐⭐⭐ | ✓✓ | 中文文章 |
| Gemini/Imagen 3 | 0.22元/张 | ⭐⭐⭐⭐ | - | - |
| DALL-E 3 | 0.4元/张 | ⭐⭐⭐⭐⭐ | - | 最高质量 |

### 智能模式 (auto) 工作原理

1. **文档分类**：LLM 分析文档内容，判断为技术文档或普通文档
2. **来源选择**：
   - 技术文档 → Mermaid 流程图（完全免费）
   - 普通文档 → Unsplash 图库
   - 封面图 → AI 生成（zhipu）
3. **提示词生成**：使用 glm-4-flash 生成精准提示词
4. **自动降级**：图库无结果时自动使用 AI 生成

### 智谱 CogView 模型选择

| 模型 | 价格 | 特点 |
|-----|------|------|
| `cogview-4` | 0.06元/次 | 最新版，支持生成汉字 |
| `cogview-3-plus` | 按次计费 | 接近 Midjourney V6 水平 |
| `cogview-3-flash` | 免费 | 快速，适合测试 |

### 推荐方案

- **智能模式（推荐）**: `--source auto` - 自动选择最优方案
- **技术文档**: Mermaid (完全免费, 生成流程图/序列图等)
- **性价比首选**: 豆包 (0.005元/张) + LLM 智能提示词
- **质量优先**: Flux.1 (0.01元/张)
- **中文文章**: 智谱 CogView + LLM 智能提示词

## Mermaid 技术图表

系统支持使用 Mermaid 生成免费的技术图表，完全无需调用 AI 图片生成 API。

### 支持的图表类型

| 类型 | 说明 | 适用场景 |
|-----|------|---------|
| `flowchart` | 流程图 | 操作步骤、决策流程 |
| `sequence` | 时序图 | API 调用、交互流程 |
| `class` | 类图 | 代码结构、类关系 |
| `state` | 状态图 | 状态机转换 |
| `er` | ER图 | 数据库关系 |
| `mindmap` | 思维导图 | 知识结构梳理 |
| `gantt` | 甘特图 | 时间线规划 |

### 配置方法

```
# config/settings.yaml
image_source: mermaid

mermaid:
  render_mode: code          # code(插入代码块) / image(渲染为PNG)
  default_diagram_type: flowchart
  auto_detect_type: true    # 自动检测内容类型选择图表
```

### 使用示例

```
# 生成 Mermaid 技术图表
python src/main.py article.md --source mermaid
```

生成的结果：

```
## 用户登录流程

```

flowchart TD     A[用户输入账号密码] --> B{系统验证}     B -->|验证成功| C[生成 Token]     B -->|验证失败| D[返回错误]

```

```

### 优势

- **完全免费**：无需调用付费 API
- **可编辑**：直接修改 Mermaid 代码
- **精确表达**：准确展示逻辑关系
- **广泛支持**：GitHub、GitLab 等平台原生支持

## LLM 智能提示词生成

系统支持使用 LLM（大语言模型）进行智能提示词生成，大幅提升配图的准确性。

### 功能对比

| 对比项 | 模板方式 | LLM 智能生成 |
|-------|---------|-------------|
| **理解能力** | 只用标题 | 理解全文语义 |
| **流程提取** | 无 | 识别操作步骤 |
| **要点总结** | 无 | 提炼核心概念 |
| **上下文** | 无 | 结合前后段落 |
| **成本** | 免费 | 0-0.001元/次 |

### 效果示例

**原文内容：**

```
## useEffect 完整指南

useEffect 用于处理副作用操作，比如数据获取、订阅、手动修改 DOM 等...
```

**模板方式：**

```
Prompt: useEffect 完整指南，示意图，简洁清晰
```

**LLM 智能生成：**

```
Prompt: React副作用处理机制，展示数据获取、订阅更新、DOM操作三个核心流程
```

### 支持的 LLM 提供商

| 提供商 | 模型 | 价格 | 推荐度 |
|-------|-----|------|-------|
| **智谱** | glm-4-flash | 免费/0.001元/次 | ⭐⭐⭐⭐⭐ |
| **DeepSeek** | deepseek-chat | 0.001元/次 | ⭐⭐⭐⭐ |
| **OpenAI** | gpt-4o-mini | 按OpenAI价格 | ⭐⭐⭐ |

### 配置方法

**1. 修改配置文件** (`config/settings.yaml`)：

```
llm:
  enabled: true           # 启用 LLM 智能生成
  provider: zhipu         # 提供商: zhipu/deepseek/openai
  model: glm-4-flash      # 模型名称
  api_key: ""             # API Key（或使用环境变量）
```

**2. 设置环境变量**（推荐）：

```
# 智谱
export ZHIPUAI_API_KEY=your_key

# DeepSeek
export DEEPSEEK_API_KEY=your_key
```

**3. 运行：**

```
python src/main.py article.md --source zhipu --debug
```

### 核心逻辑

LLM 智能生成时的输入参数：

```
_generate_prompt(
    element: MarkdownElement,  # 当前元素（标题/段落）
    doc: MarkdownDocument,     # 整个文档
    image_type: str            # 图片类型
)
```

**传递给 LLM 的信息：**

| 参数 | 说明 | 示例 |
|-----|------|------|
| `title` | 文章标题 | "React Hooks 深入理解" |
| `content` | 当前元素内容 | "useEffect 完整指南" |
| `context` | 后续段落内容 | "useEffect 用于处理副作用操作..." |
| `image_type` | 图片类型 | "section" / "cover" / "concept" |

**回退机制：**

```
LLM 生成 → 失败 → 模板回退 → 保证可用
```

如果 LLM 调用失败（API Key 未设置、网络问题等），系统自动回退到模板方式，确保稳定运行。

## 示例

输入 `article.md`:

```
# 深入理解 JavaScript 闭包

闭包是 JavaScript 中最重要的概念之一...

## 什么是闭包

闭包是指有权访问另一个函数作用域中变量的函数...
```

运行后生成 `article.md` (原文件保存为 `article.original.md`):

```
# 深入理解 JavaScript 闭包

![封面图 - 深入理解 JavaScript 闭包](output/images/0_cover_20250119.png)
*文章封面：深入理解 JavaScript 闭包*

闭包是 JavaScript 中最重要的概念之一...

## 什么是闭包

![章节配图 - 什么是闭包](output/images/1_section_20250119.png)
*章节插图：什么是闭包*

闭包是指有权访问另一个函数作用域中变量的函数...
```

## Web 交互界面

系统提供 Web 交互界面，支持可视化预览、选择和编辑 Markdown 文件。

#### 启动 Web 服务器

```bash
# 启动 Web 服务器
python src/web_server.py article.md [port]

# 示例
python src/web_server.py article.md 5000
```

启动后会自动打开浏览器，访问 `http://localhost:5000`。

#### 功能说明

**预览模式**

- 实时渲染 Markdown 内容
- 支持 Mermaid 图表渲染（流程图、时序图、状态图等）
- 支持表格、列表、引用等标准 Markdown 语法
- 图片默认缩放至 50%

**图片来源选择器 (NEW)**

- 位于页面左上角
- 可选择 8 种图片来源
  - `auto` - 智能选择（推荐）
  - `zhipu` - 智谱AI
  - `doubao` - 豆包
  - `flux` - Flux.1
  - `dalle` - DALL-E 3
  - `unsplash` - 免费图库
  - `pexels` - 免费图库
  - `mermaid` - 技术图表
- 选择不同来源时会显示对应的提示说明

**候选图选择**

- 显示所有配图位置和候选图
- 点击候选图即可切换选择
- 选择结果自动保存到 Markdown 文件

**编辑模式**

- 在线编辑 Markdown 内容
- 保存后自动刷新预览

**配图功能**

- 在编辑模式下粘贴 Markdown 内容
- 选择图片来源后点击"开始配图"按钮
- 配图成功后自动更新页面内容
- 支持智能模式自动识别文档类型

**帮助功能 (NEW)**

- 点击"❓ 帮助"按钮打开帮助文档
- 包含快速开始、图片来源说明、界面功能、按钮说明
- 配图规则、快捷键、常见问题等完整文档

**导出功能**

- 点击"导出 Markdown"按钮下载文件
- 自动生成文件名

#### 批量操作

- **全选第一张**: 为所有位置选择第一张候选图
- **保存修改**: 保存当前选择到文件

#### 界面按钮

| 按钮          | 功能                       |
| ------------- | -------------------------- |
| 开始配图      | 为当前内容生成配图         |
| 全选第一张    | 选择所有位置的第一张候选图 |
| 保存修改      | 保存选择到文件             |
| 导出 Markdown | 下载 Markdown 文件         |
| ❓ 帮助 (NEW)  | 打开使用帮助文档           |



## 依赖项

```
markdown>=3.5.0        # Markdown 解析
pyyaml>=6.0            # 配置文件解析
requests>=2.31.0       # HTTP 请求
zhipuai>=2.0.0         # 智谱AI SDK (用于 CogView、LLM)
openai>=1.0.0          # OpenAI SDK (用于 DALL-E、豆包、LLM)
pillow>=10.0.0         # 图片处理
python-dotenv>=1.0.0   # .env 文件支持
python-dateutil>=2.8.0 # 数据处理
flask>=3.0.0           # Web 服务器
marko>=2.0.0           # Markdown 渲染（Web 界面）
```

## 核心模块说明

### Parser (parser.py)

解析 Markdown 文件，提取结构化元素：

```
from parser import parse_markdown_file

doc = parse_markdown_file('article.md')
print(doc.title)              # 文章标题
print(doc.get_headings())     # 所有标题
print(doc.get_paragraphs())   # 所有段落
```

### Classifier (classifier.py)

文档分类器，判断文档类型（技术/普通）：

```
from classifier import DocumentClassifier

classifier = DocumentClassifier(config)
result = classifier.classify(content, meta)
print(result['type'])         # 'technical' or 'normal'
print(result['confidence'])   # 置信度 0-1
```

### Prompt Generator (prompt_generator.py)

LLM 智能提示词生成器：

```
from prompt_generator import PromptGenerator

generator = PromptGenerator(config)
prompt = generator.generate(
    element_content="React Hooks 深入理解",
    image_type="section",
    doc_context={'title': '...', 'keywords': [...], 'doc_type': 'technical'}
)
```

### Image Source Manager (image_source_manager.py)

图片源管理器，智能选择和降级：

```
from image_source_manager import ImageSourceManager

manager = ImageSourceManager(config)
result = manager.generate_with_fallback(
    prompt="...",
    index=0,
    image_type="section",
    doc_type="normal"
)
```

### Analyzer (analyzer.py)

分析内容，决定配图位置：

```
from analyzer import analyze_content

decisions = analyze_content(doc, config, image_source='auto')
for decision in decisions:
    print(f"位置: {decision.element_index}")
    print(f"类型: {decision.image_type}")
    print(f"来源: {decision.image_source}")  # NEW
    print(f"提示词: {decision.prompt}")
```

### Image Generator (image_gen.py)

工厂模式，根据配置选择图片来源：

```
from image_gen import get_image_generator

generator = get_image_generator(config, use_sdk=True, image_source='zhipu')
image_path = generator.generate(prompt, index=0, image_type='cover')
```

## 开发指南

### 添加新的图片来源

1. 创建新的生成器类，实现 `generate(prompt, index, image_type)` 方法
2. 在 `image_gen.py` 中注册新的图片来源
3. 在 `config/settings.yaml` 中添加配置

示例：

```
# src/my_gen.py
class MyImageGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, prompt: str, index: int = 0, image_type: str = 'image') -> str:
        # 生成图片
        # 返回图片路径
        return image_path
```

## 常见问题

### Q: 如何使用智能模式？

A: 智能模式 (`--source auto`) 会自动选择最优的图片来源：

```bash
# 命令行使用
python mi.py article.md --source auto

# Web 界面使用
# 在页面左上角选择 "auto - 智能选择"
```

智能模式的工作原理：
1. LLM 分析文档内容，判断为技术文档或普通文档
2. 技术文档使用 Mermaid 流程图（免费）
3. 普通文档使用 Unsplash 图库
4. 封面图统一使用 AI 生成

### Q: 批量模式配图失败，返回成功但生成0张候选图？

A: 这可能是 ElementType 枚举比较问题（已修复）。如果遇到此问题：

1. 确保使用最新版本代码
2. 检查 `config/settings.yaml` 中的 `rules.h1_after` 是否为 `true`
3. 使用调试模式查看：`python src/main.py article.md --batch 2 --debug`

### Q: Web 界面配图后页面内容没有更新？

A: 这可能是临时文件被删除的问题（已修复）。如果遇到此问题：

1. 确保使用最新版本代码
2. 检查浏览器控制台是否有错误信息
3. 重新启动 Web 服务器

### Q: 豆包生成的图片质量不理想？

A: 豆包价格便宜但质量相对较低。建议：

- 尝试 Flux.1（质量更好，价格仍合理）
- 优化 Prompt，使用更简洁的中文描述
- 考虑使用智谱 CogView-4

### Q: Unsplash/Pexels 无法使用？

A: 公开 API 不稳定（403/503 错误）。建议：

- 注册正式 API Key
- 或使用其他文生图服务

### Q: 如何提高配图质量？

A: 有多种方式提升配图质量：

1. **启用 LLM 智能提示词**：设置 `llm.enabled: true`，让 AI 理解内容生成更准确的描述
2. **根据模型调整提示词**：
   - 智谱/豆包：使用简洁的中文提示词
   - DALL-E/Flux：使用英文提示词
3. **自定义 prompts 模板**：在 `config/settings.yaml` 中针对不同图片来源优化
4. **使用调试模式**：运行 `--debug --dry-run` 查看生成的提示词

### Q: LLM 智能生成失败怎么办？

A: 系统有自动回退机制：

- LLM 调用失败 → 自动使用模板生成
- 确保 API Key 正确设置
- 检查网络连接
- 查看 `--debug` 模式下的错误信息

### Q: 如何查看生成的提示词？

A: 使用调试模式：

```
# 查看完整提示词
python src/main.py article.md --debug

# 只查看提示词，不生成图片
python src/main.py article.md --debug --dry-run
```

### Q: 批量生成模式如何使用？

A: 批量生成模式为每个位置生成 N 张候选图，解决 AI 文生图效果不理想的问题：

```
# 为每个位置生成 3 张候选图
python src/main.py article.md --batch 3 --source zhipu

# 查看所有候选图，选择最满意的一张
# 然后手动编辑 Markdown，取消注释你选择的候选图
```

生成的文件包含候选索引：
```
0_cover_20260119_143000_000.png  # 第1张候选图（默认选中）
0_cover_20260119_143000_001.png  # 第2张候选图
0_cover_20260119_143000_002.png  # 第3张候选图
```

### Q: 如何只重新生成某一张图片？

A: 使用增量更新模式的 `--regenerate` 参数：

```
# 只重新生成第 1 张图片（索引从 0 开始）
python src/main.py article.md --regenerate 0

# 只重新生成第 3 张图片，并生成 5 张候选图供选择
python src/main.py article.md --regenerate 2 --batch 5
```

### Q: 如何重新生成所有封面图或章节配图？

A: 使用 `--regenerate-type` 参数按类型重新生成：

```
# 重新生成所有封面图
python src/main.py article.md --regenerate-type cover

# 重新生成所有章节配图
python src/main.py article.md --regenerate-type section

# 重新生成所有概念示意图
python src/main.py article.md --regenerate-type concept
```

支持的图片类型：`cover`（封面）、`section`（章节配图）、`concept`（概念示意图）、`atmospheric`（氛围插图）、`diagram`（架构图）、`code_concept`（代码结构图）

### Q: 如何只重新生成失败的图片？

A: 使用 `--regenerate-failed` 参数：

```
python src/main.py article.md --regenerate-failed
```

系统会自动识别之前生成失败的图片并重新生成。

## 注意事项

1. 首次使用建议先用 `cogview-3-flash` 免费模型测试
2. 推荐使用 `.env` 文件管理 API Key，避免泄露
3. 生成的图片会保存在 `output/images/` 目录
4. 默认会保留原始文件（`.original.md` 后缀）
5. 不同模型对 Prompt 的敏感度不同，需要针对性优化

## 多用户部署 (NEW in v1.8)

Markdown Illustrator v1.8 引入了多用户支持，适合企业内部团队使用（10-50人）。

**主要特性：**

- **用户认证**: 登录认证（用户名/密码）
- **会话隔离**: 每个用户独立的工作空间
- **文件隔离**: 会话级临时目录，互不干扰
- **速率限制**: 防误操作保护
- **配额管理**: 每日配图次数限制

**快速启动：**

```bash
# 开发模式
./start_server.sh dev

# 生产模式（Gunicorn 多进程）
./start_server.sh prod

# 自定义端口
./start_server.sh dev 8000
```

**默认账户：**
- 用户名: `admin`
- 密码: `admin123`

**用户配置** (`config/users.yaml`):

```yaml
users:
  admin:
    password: admin123
    name: 管理员
    role: admin
    quota_limit: 1000

  user1:
    password: user123
    name: 张三
    role: user
    quota_limit: 50
```

**详细部署文档**: [docs/MULTI_USER_DEPLOYMENT.md](docs/MULTI_USER_DEPLOYMENT.md)

## 版本历史

- **v1.8** - 添加多用户支持：用户认证、会话隔离、文件隔离、速率限制、配额管理；添加 Gunicorn 部署配置；添加启动脚本和 systemd 服务配置
- **v1.7** - 添加智能配图模式 (`auto`)：自动识别文档类型选择最优来源；添加 LLM 智能提示词生成（glm-4-flash）；Web 界面添加图片来源选择器；新增 `classifier.py`、`prompt_generator.py`、`image_source_manager.py` 模块
- **v1.6** - 添加 Web 交互界面，支持可视化预览和选择候选图；修复批量模式下的关键 bug（ElementType 枚举比较问题、image_paths 赋值问题）
- **v1.5** - 添加批量生成模式 (`--batch N`)，为每个位置生成多张候选图供选择；添加增量更新模式 (`--regenerate`, `--regenerate-type`, `--regenerate-failed`)，支持只重新生成指定图片；解决文生图效果不理想需要反复调整的核心痛点
- **v1.4** - 添加 Mermaid 技术图表支持；添加 LLM 智能提示词生成；多图片来源提示词优化；添加调试模式
- **v1.3** - 添加豆包、Flux.1 支持；优化提示词；添加 `.env` 文件支持
- **v1.2** - 添加 DALL-E 3、Unsplash/Pexels 支持
- **v1.1** - 改进内容分析算法，添加智能配图模式
- **v1.0** - 初始版本，支持智谱 CogView

## License

MIT