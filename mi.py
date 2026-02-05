#!/usr/bin/env python3
"""
Markdown Illustrator CLI Entry Point
简单命令行入口，放在项目根目录使用
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from main import main

if __name__ == '__main__':
    main()
