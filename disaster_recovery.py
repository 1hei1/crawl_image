#!/usr/bin/env python3
"""
容灾备份管理脚本

简化的容灾备份管理接口，提供常用操作的快捷方式
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from tools.disaster_recovery_cli import main

if __name__ == '__main__':
    main()
