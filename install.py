#!/usr/bin/env python3
"""
依赖安装脚本

解决Windows系统下的编码问题和依赖安装
"""

import subprocess
import sys
import os
from pathlib import Path


def print_banner():
    """打印安装横幅"""
    print("=" * 60)
    print("智能图片爬虫系统 - 依赖安装脚本")
    print("=" * 60)


def check_python_version():
    """检查Python版本"""
    print("🔍 检查Python版本...")
    
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        print(f"当前版本: {sys.version}")
        return False
    
    print(f"✅ Python版本: {sys.version}")
    return True


def install_package(package):
    """安装单个包"""
    try:
        print(f"📦 安装 {package}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            print(f"✅ {package} 安装成功")
            return True
        else:
            print(f"❌ {package} 安装失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 安装 {package} 时发生错误: {e}")
        return False


def install_core_dependencies():
    """安装核心依赖"""
    print("\n🚀 开始安装核心依赖...")
    
    # 核心依赖列表
    core_packages = [
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0", 
        "aiohttp>=3.8.0",
        "sqlalchemy>=2.0.0",
        "Pillow>=10.0.0",
        "pyyaml>=6.0",
        "loguru>=0.7.0",
        "click>=8.1.0",
        "tqdm>=4.66.0",
        "fake-useragent>=1.4.0"
    ]
    
    failed_packages = []
    
    for package in core_packages:
        if not install_package(package):
            failed_packages.append(package)
    
    if failed_packages:
        print(f"\n⚠️  以下包安装失败: {', '.join(failed_packages)}")
        return False
    
    print("\n✅ 所有核心依赖安装完成!")
    return True


def install_optional_dependencies():
    """安装可选依赖"""
    print("\n🔧 安装可选依赖...")
    
    optional_packages = [
        "psycopg2-binary>=2.9.0",  # PostgreSQL支持
        "pytest>=7.4.0",           # 测试框架
        "pytest-asyncio>=0.21.0",  # 异步测试
        "numpy>=1.24.0",           # 数值计算
        "scikit-learn>=1.3.0"      # 机器学习
    ]
    
    for package in optional_packages:
        install_package(package)
    
    print("\n✅ 可选依赖安装完成!")


def create_directories():
    """创建必要的目录"""
    print("\n📁 创建项目目录...")
    
    directories = [
        "data",
        "logs", 
        "config",
        "tests/reports"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目录: {directory}")


def test_installation():
    """测试安装"""
    print("\n🧪 测试安装...")
    
    try:
        # 测试核心模块导入
        import requests
        import aiohttp
        import sqlalchemy
        from PIL import Image
        import yaml
        from loguru import logger
        import click
        
        print("✅ 所有核心模块导入成功")
        
        # 测试数据库连接
        from sqlalchemy import create_engine
        engine = create_engine("sqlite:///:memory:")
        print("✅ 数据库连接测试成功")
        
        return True
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    """主函数"""
    print_banner()
    
    # 检查Python版本
    if not check_python_version():
        return 1
    
    # 升级pip
    print("\n🔄 升级pip...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                  capture_output=True)
    
    # 安装核心依赖
    if not install_core_dependencies():
        print("\n❌ 核心依赖安装失败，请检查网络连接或Python环境")
        return 1
    
    # 询问是否安装可选依赖
    install_optional = input("\n❓ 是否安装可选依赖（PostgreSQL、测试工具等）? (y/N): ").strip().lower()
    if install_optional == 'y':
        install_optional_dependencies()
    
    # 创建目录
    create_directories()
    
    # 测试安装
    if test_installation():
        print("\n🎉 安装完成!")
        print("\n📖 接下来的步骤:")
        print("1. 生成配置文件: python main.py init-config")
        print("2. 开始爬取: python main.py crawl https://example.com")
        print("3. 或使用交互界面: python run.py")
        return 0
    else:
        print("\n❌ 安装测试失败，请检查错误信息")
        return 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  安装被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 安装过程中发生错误: {e}")
        sys.exit(1)
