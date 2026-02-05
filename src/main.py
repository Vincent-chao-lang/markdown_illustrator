"""
Markdown Illustrator - 自动配图系统主入口
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    # 尝试加载项目根目录的 .env 文件
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv 未安装时忽略

from parser import parse_markdown_file
from analyzer import analyze_content
from image_gen import get_image_generator
from assembler import assemble_markdown

# 导入智能组件
try:
    from image_source_manager import ImageSourceManager
    INTELLIGENT_AVAILABLE = True
except ImportError:
    INTELLIGENT_AVAILABLE = False


class MarkdownIllustrator:
    """Markdown 自动配图系统"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化

        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.generator = None
        self.source_manager = None

        # 初始化图片源管理器（如果可用）
        if INTELLIGENT_AVAILABLE:
            try:
                self.source_manager = ImageSourceManager(self.config)
                print("智能图片来源选择已启用")
            except Exception as e:
                print(f"警告: 图片源管理器初始化失败: {e}")

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        加载配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            配置字典
        """
        # 默认配置文件路径
        if config_path is None:
            # 从当前目录查找
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / 'config' / 'settings.yaml'

        config_path = Path(config_path)

        if not config_path.exists():
            print(f"警告: 配置文件不存在: {config_path}")
            print("使用默认配置...")
            return self._default_config()

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 从环境变量读取 API Key
        api_key = os.getenv('ZHIPUAI_API_KEY') or os.getenv('GLM_API_KEY')
        if api_key:
            config['api']['api_key'] = api_key

        return config

    def _default_config(self) -> Dict[str, Any]:
        """返回默认配置"""
        return {
            'api': {
                'provider': 'zhipu',
                'model': 'cogview-3-flash',  # 使用免费版
                'api_key': os.getenv('ZHIPUAI_API_KEY', ''),
            },
            'image': {
                'size': '1024x1024',
                'save_dir': 'output/images',
            },
            'rules': {
                'h1_after': True,
                'h2_after': 'smart',
                'long_paragraph_threshold': 150,
                'min_gap_between_images': 3,
                'max_images_per_article': 10,
            },
            'prompts': {
                'cover': 'Create a professional cover image for: {title}',
                'section': 'Create an illustration for: {topic}',
                'atmospheric': 'Create an atmospheric image for: {topic}',
            },
            'output': {
                'keep_original': True,
                'add_image_caption': True,
            }
        }

    def illustrate(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        use_sdk: bool = True,
        dry_run: bool = False,
        image_source: str = None,
        debug: bool = False,
        batch: int = 1,
        regenerate: Optional[int] = None,
        regenerate_type: Optional[str] = None,
        regenerate_failed: bool = False
    ) -> Dict[str, Any]:
        """
        为 Markdown 文件自动配图

        Args:
            input_path: 输入 Markdown 文件路径
            output_path: 输出文件路径（默认覆盖原文件）
            use_sdk: 是否使用官方 SDK
            dry_run: 是否只分析不生成图片
            image_source: 图片来源 (zhipu, dalle, doubao, flux, unsplash, pexels, mermaid)
            debug: 调试模式，打印完整提示词
            batch: 批量生成数量（为每个位置生成 N 张候选图）
            regenerate: 只重新生成指定索引的图片
            regenerate_type: 只重新生成指定类型的图片
            regenerate_failed: 只重新生成失败的图片

            image_source: 图片来源 (auto, zhipu, dalle, doubao, flux, unsplash, pexels, mermaid)
                        auto: 智能选择 (技术文档用Mermaid, 普通文档用图库+AI降级)
        """
        input_path = Path(input_path)

        # 设置默认值
        if batch is None:
            batch = 1

        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        # 默认输出路径
        if output_path is None:
            output_path = input_path

        # 确定图片来源
        if image_source is None:
            image_source = self.config.get('image_source', 'zhipu')

        print(f"\n{'='*60}")
        print(f"Markdown 自动配图系统")
        print(f"{'='*60}")
        print(f"输入文件: {input_path}")
        print(f"输出文件: {output_path}")
        print(f"图片来源: {image_source}")
        if image_source == 'zhipu':
            print(f"模型: {self.config['api']['model']}")
        if batch > 1:
            print(f"批量模式: 每个位置生成 {batch} 张候选图")
        if regenerate is not None:
            print(f"增量更新: 重新生成第 {regenerate + 1} 张图片")
        if regenerate_type:
            print(f"增量更新: 重新生成所有 '{regenerate_type}' 类型的图片")
        if regenerate_failed:
            print(f"增量更新: 只重新生成失败的图片")
        print(f"{'='*60}\n")

        # Step 1: 解析 Markdown
        print("Step 1: 解析 Markdown...")
        doc = parse_markdown_file(str(input_path))
        print(f"  标题: {doc.title}")
        print(f"  元素数量: {len(doc.elements)}")
        print(f"  段落数量: {len(doc.get_paragraphs())}")
        print(f"  标题数量: {len(doc.get_headings())}\n")

        # Step 2: 分析内容，决定配图
        print("Step 2: 分析内容，决定配图位置...")
        decisions = analyze_content(doc, self.config, image_source)
        print(f"  决定配图数量: {len(decisions)}")

        if not decisions:
            print("  根据当前规则，不需要配图")
            print(f"  可以调整 config/settings.yaml 中的 rules 配置\n")
            return {
                'success': True,
                'images_generated': 0,
                'message': '不需要配图',
                'output_path': str(output_path),  # 始终返回输出路径
                'image_paths': []
            }

        for i, decision in enumerate(decisions):
            element = doc.elements[decision.element_index]
            print(f"  #{i+1}: [{decision.image_type}] {decision.reason}")
            if debug:
                # 调试模式：打印完整提示词
                print(f"      Prompt (完整):")
                print(f"        {decision.prompt}")
            else:
                # 正常模式：打印截断的提示词
                print(f"      Prompt: {decision.prompt[:80]}...")

        if debug:
            print()  # 调试模式后多加一个空行

        # 增量更新模式：解析现有文件并决定哪些图片需要重新生成
        regenerate_plan = None
        if regenerate is not None or regenerate_type or regenerate_failed:
            print("Step 2.5: 增量更新模式...")
            try:
                from regenerate import parse_for_regeneration
                regenerate_plan = parse_for_regeneration(
                    str(input_path),
                    self.config,
                    decisions,
                    regenerate,
                    regenerate_type,
                    regenerate_failed
                )

                if not regenerate_plan['regenerate'] and not regenerate_plan['missing']:
                    print("  没有需要重新生成的图片")
                    return {
                        'success': True,
                        'images_generated': 0,
                        'message': '没有需要重新生成的图片'
                    }

                print(f"  保留: {len(regenerate_plan['keep'])} 张现有图片")
                print(f"  重新生成: {len(regenerate_plan['regenerate'])} 张图片")
                print(f"  新增: {len(regenerate_plan['missing'])} 张图片\n")
            except ImportError:
                print("  警告: 增量更新模块不可用，将重新生成所有图片\n")
            except Exception as e:
                print(f"  增量更新解析失败: {e}")
                print(f"  将重新生成所有图片\n")

        # Step 3: 生成图片
        image_paths = []

        if dry_run:
            print("Step 3: [DRY RUN] 跳过图片生成\n")
            if batch > 1:
                # 批量模式的 dry run
                image_paths = [[] for _ in range(len(decisions))]
            else:
                image_paths = [None] * len(decisions)

            # 增量更新模式：填充现有图片路径
            if regenerate_plan and regenerate_plan['keep']:
                for item in regenerate_plan['keep']:
                    if batch > 1:
                        # 批量模式下，现有图片作为单张列表
                        image_paths[item['index']] = [item['image_path']]
                    else:
                        image_paths[item['index']] = item['image_path']
        else:
            print("Step 3: 生成图片...")

            # 初始化 image_paths，在增量更新模式下填充现有图片
            if batch > 1:
                image_paths = [[] for _ in range(len(decisions))]
            else:
                image_paths = [None] * len(decisions)

            if regenerate_plan and regenerate_plan['keep']:
                for item in regenerate_plan['keep']:
                    if batch > 1:
                        image_paths[item['index']] = [item['image_path']]
                    else:
                        image_paths[item['index']] = item['image_path']
                print(f"  已保留 {len(regenerate_plan['keep'])} 张现有图片")

            if self.generator is None:
                # 对于 auto，使用 zhipu 作为默认来源初始化 generator
                # 实际图片来源由 analyzer 决定
                actual_source = image_source
                if image_source == 'auto':
                    actual_source = 'zhipu'
                self.generator = get_image_generator(self.config, use_sdk, actual_source)

            # 确定需要生成图片的索引
            if regenerate_plan:
                # 增量更新模式：只生成指定的图片
                regenerate_indices = {item['index'] for item in regenerate_plan['regenerate']}
                missing_indices = {item['index'] for item in regenerate_plan['missing']}
                generate_indices = sorted(regenerate_indices | missing_indices)
                print(f"  将生成 {len(generate_indices)} 个位置的图片")
            else:
                # 正常模式：生成所有图片
                generate_indices = range(len(decisions))

            for i in generate_indices:
                decision = decisions[i]
                try:
                    print(f"\n[{i+1}/{len(decisions)}] {decision.image_type}: {decision.reason[:50]}")

                    # 检查是否有 A/B 测试变体
                    has_ab_test = decision.ab_variants is not None and len(decision.ab_variants) > 0

                    if has_ab_test:
                        # A/B 测试模式：每个变体使用不同的提示词
                        print(f"  A/B 测试模式：{len(decision.ab_variants)} 个变体")
                        variant_paths = []
                        for v_idx, variant in enumerate(decision.ab_variants):
                            try:
                                print(f"    [{variant['name']}] {variant['description']}", end=" ")
                                if debug:
                                    print(f"\n      提示词: {variant['prompt'][:80]}...")
                                else:
                                    print("")

                                path = self.generator.generate(
                                    variant['prompt'],
                                    i,
                                    decision.image_type,
                                    candidate_index=v_idx
                                )
                                variant_paths.append({
                                    'name': variant['name'],
                                    'description': variant['description'],
                                    'path': path
                                })
                                print(f"    ✓")
                            except Exception as e:
                                print(f"    ✗ ({e})")
                                variant_paths.append({
                                    'name': variant['name'],
                                    'description': variant['description'],
                                    'path': None
                                })

                        image_paths.append(variant_paths)
                        print(f"  完成: {len([p for p in variant_paths if p['path']])}/{len(variant_paths)} 个变体成功")

                    elif batch > 1:
                        # 批量生成模式：为每个位置生成 N 张候选图
                        print(f"  批量生成 {batch} 张候选图...")
                        candidate_paths = []
                        for b in range(batch):
                            try:
                                print(f"    生成候选图 {b + 1}/{batch}...", end=" ")
                                if debug:
                                    print(f"\n      提示词: {decision.prompt[:80]}...")
                                else:
                                    print("")

                                path = self.generator.generate(
                                    decision.prompt,
                                    i,
                                    decision.image_type,
                                    candidate_index=b
                                )
                                candidate_paths.append(path)
                                print(f"    ✓")
                            except Exception as e:
                                print(f"    ✗ ({e})")
                                candidate_paths.append(None)

                        image_paths[i] = candidate_paths  # Fixed: use assignment instead of append
                        print(f"  完成: {len([p for p in candidate_paths if p])}/{batch} 张成功")
                    else:
                        # 普通模式：生成 1 张图片
                        # 调试模式：打印完整提示词
                        if debug:
                            print(f"  提示词:")
                            print(f"    {decision.prompt}")
                            print()

                        image_source = getattr(decision, 'image_source', None)

                        # 确定实际使用的图片源
                        if not image_source or image_source == 'auto':
                            actual_source = self.config.get('image_source', 'zhipu')
                        else:
                            actual_source = image_source

                        # 获取对应的生成器
                        if actual_source != self.config.get('image_source', 'zhipu') and self.source_manager:
                            generator = self.source_manager.get_generator(actual_source)
                        else:
                            generator = self.generator

                        print(f"  来源: {actual_source}")

                        image_path = generator.generate(
                            decision.prompt,
                            i,
                            decision.image_type
                        )

                        image_paths[i] = image_path  # Fixed: use index assignment instead of append
                except Exception as e:
                    print(f"  生成失败: {e}")
                    if has_ab_test or batch > 1:
                        # 需要确定是 A/B 测试还是批量模式
                        if has_ab_test:
                            image_paths.append([{'name': v['name'], 'path': None} for v in decision.ab_variants])
                        else:
                            image_paths.append([None] * batch)
                    else:
                        image_paths.append(None)
            print()

        # Step 4: 重组 Markdown
        print("Step 4: 重组 Markdown，插入图片...")
        content = assemble_markdown(
            doc,
            image_paths,
            self.config,
            str(output_path),
            batch_mode=batch > 1
        )
        print()

        # 总结
        print(f"{'='*60}")
        print(f"完成！共生成 {_count_generated_images(image_paths)} 张图片")
        print(f"{'='*60}\n")

        return {
            'success': True,
            'images_generated': _count_generated_images(image_paths),
            'image_paths': image_paths,
            'decisions': decisions,
            'output_path': str(output_path)
        }


def _count_generated_images(image_paths):
    """正确计算生成的图片数量（支持批量模式）"""
    count = 0
    for paths in image_paths:
        if isinstance(paths, list):
            # 批量模式：候选图列表
            count += len([p for p in paths if p])
        elif paths:
            # 普通模式：单张图片
            count += 1
    return count


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Markdown 自动配图系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
图片来源说明:
  auto      智能选择 (技术文档用Mermaid, 普通文档用图库+AI降级)
  zhipu     智谱AI CogView (0.06元/张, 中文好)
  doubao    豆包文生图 (0.005元/张, 超便宜)
  flux      Flux.1 (0.01元/张, 质量接近Midjourney)
  dalle     OpenAI DALL-E 3 (~0.4元/张, 质量最好)
  unsplash  Unsplash 免费图库 (真实照片)
  pexels    Pexels 免费图库 (真实照片)
  mermaid   Mermaid 图表 (完全免费, 技术图表)

推荐方案:
  智能模式:   --source auto (自动选择最优方案)
  技术文档:   --source mermaid (完全免费, 生成流程图/序列图等)
  性价比首选: --source doubao (0.005元/张)
  质量优先:   --source flux (0.01元/张)
  中文文章:   --source zhipu 或 --source doubao

示例:
  python mi.py article.md --source auto        # 智能选择最优方案
  python mi.py article.md --source mermaid    # 使用 Mermaid (免费技术图表)
  python mi.py article.md --source doubao     # 使用豆包 (最便宜)
  python mi.py article.md --source flux       # 使用 Flux.1 (质量好)
  python mi.py article.md --source zhipu --model cogview-4  # 使用 CogView-4
        '''
    )
    parser.add_argument(
        'input',
        help='输入 Markdown 文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        help='输出文件路径（默认覆盖原文件）'
    )
    parser.add_argument(
        '-c', '--config',
        help='配置文件路径（默认: config/settings.yaml）'
    )
    parser.add_argument(
        '--source',
        choices=['auto', 'zhipu', 'dalle', 'doubao', 'flux', 'unsplash', 'pexels', 'mermaid'],
        help='图片来源 (默认: zhipu)'
    )
    parser.add_argument(
        '--model',
        choices=['cogview-4', 'cogview-3-plus', 'cogview-3-flash'],
        help='CogView 模型选择（仅当 --source=zhipu 时有效）'
    )
    parser.add_argument(
        '--api-key',
        help='API Key（覆盖配置文件和环境变量）'
    )
    parser.add_argument(
        '--no-sdk',
        action='store_true',
        help='不使用官方 SDK，直接调用 API（仅 zhipu）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只分析不生成图片'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='调试模式，打印完整提示词'
    )
    parser.add_argument(
        '--batch',
        type=int,
        metavar='N',
        help='批量生成模式：为每个位置生成 N 张候选图（需手动选择使用哪张）'
    )
    parser.add_argument(
        '--regenerate',
        type=int,
        metavar='INDEX',
        help='增量更新：只重新生成指定索引的图片（从0开始）'
    )
    parser.add_argument(
        '--regenerate-type',
        type=str,
        metavar='TYPE',
        help='增量更新：重新生成指定类型的图片 (cover/section/concept/atmospheric)'
    )
    parser.add_argument(
        '--regenerate-failed',
        action='store_true',
        help='增量更新：只重新生成失败的图片'
    )
    parser.add_argument(
        '--web',
        action='store_true',
        help='启动 Web 图片选择器界面（用于从批量生成的候选图中选择）'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        metavar='PORT',
        help='Web 服务器端口（默认: 5000）'
    )

    args = parser.parse_args()

    # Web 模式：启动图片选择器
    if args.web:
        from web_server import start_selector

        input_path = Path(args.input)
        if not input_path.exists():
            print(f"错误: 文件不存在: {args.input}")
            sys.exit(1)

        print("\n" + "="*60)
        print("Markdown Illustrator - Web 图片选择器")
        print("="*60)
        print(f"Markdown 文件: {input_path}")
        print(f"服务器地址: http://localhost:{args.port}")
        print("="*60 + "\n")

        start_selector(str(input_path), args.port)
        sys.exit(0)

    # 加载配置
    illustrator = MarkdownIllustrator(args.config)

    # 确定图片来源
    image_source = args.source or illustrator.config.get('image_source', 'zhipu')

    # 覆盖配置
    if args.model and image_source == 'zhipu':
        illustrator.config['api']['model'] = args.model
    if args.api_key:
        if image_source == 'zhipu':
            illustrator.config['api']['api_key'] = args.api_key
        elif image_source == 'dalle':
            illustrator.config['dalle']['api_key'] = args.api_key
        elif image_source == 'doubao':
            illustrator.config['doubao']['api_key'] = args.api_key
        elif image_source == 'flux':
            illustrator.config['flux']['api_key'] = args.api_key
        elif image_source == 'unsplash':
            illustrator.config['unsplash']['access_key'] = args.api_key
        elif image_source == 'pexels':
            illustrator.config['pexels']['api_key'] = args.api_key

    # 执行
    try:
        result = illustrator.illustrate(
            args.input,
            args.output,
            use_sdk=not args.no_sdk,
            dry_run=args.dry_run,
            image_source=image_source,
            debug=args.debug,
            batch=getattr(args, 'batch', 1),
            regenerate=getattr(args, 'regenerate', None),
            regenerate_type=getattr(args, 'regenerate_type', None),
            regenerate_failed=getattr(args, 'regenerate_failed', False)
        )

        if result['success']:
            print(f"✓ 成功！共生成 {result['images_generated']} 张图片")
            if result.get('output_path'):
                print(f"✓ 输出文件: {result['output_path']}")
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
