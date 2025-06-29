"""
爬虫模块 - 负责网站图片的采集和下载

包含以下子模块：
- core: 核心爬虫引擎
- utils: 工具函数
- handlers: 各种处理器（反爬虫、下载等）
"""

from .core.spider import ImageSpider
from .core.downloader import ImageDownloader
from .utils.url_parser import URLParser
from .handlers.anti_crawler import AntiCrawlerHandler

__all__ = [
    "ImageSpider",
    "ImageDownloader", 
    "URLParser",
    "AntiCrawlerHandler",
]
