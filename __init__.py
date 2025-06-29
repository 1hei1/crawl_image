"""
图片爬虫项目 - 智能网络图片采集与分类系统

这是一个功能完整的网络爬虫解决方案，专门用于自动化采集和智能分类网站图片资源。

主要功能：
- 自动爬取指定网站的所有图片资源
- 支持多种图片格式（jpg、png、gif、webp等）
- 智能图片分类和存储
- 反爬虫机制处理
- 异步多线程处理
- 完整的错误处理和日志记录

作者: AI Assistant
版本: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "AI Assistant"
__email__ = "assistant@example.com"
__description__ = "智能网络图片采集与分类系统"

# 导入主要模块
from .crawler import ImageCrawler
from .database import DatabaseManager
from .config import ConfigManager

__all__ = [
    "ImageCrawler",
    "DatabaseManager", 
    "ConfigManager",
]
