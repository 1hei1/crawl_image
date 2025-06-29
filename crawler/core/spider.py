"""
核心爬虫引擎

负责网页爬取、链接提取和图片发现
"""

import re
import logging
import asyncio
import aiohttp
from typing import List, Set, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time

from crawler.utils.url_parser import URLParser

logger = logging.getLogger(__name__)


class ImageSpider:
    """
    图片爬虫引擎
    
    功能：
    - 网页内容抓取
    - 图片链接提取
    - 递归爬取控制
    - 去重和过滤
    - 进度跟踪
    """
    
    def __init__(self, base_url: str, max_depth: int = 3, max_pages: int = 100):
        """
        初始化爬虫
        
        Args:
            base_url: 起始URL
            max_depth: 最大爬取深度
            max_pages: 最大页面数
        """
        self.base_url = base_url
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.url_parser = URLParser(base_url)
        
        # 状态跟踪
        self.visited_urls: Set[str] = set()
        self.found_images: Set[str] = set()
        self.pending_urls: List[tuple] = [(base_url, 0)]  # (url, depth)
        self.failed_urls: Set[str] = set()
        
        # 统计信息
        self.pages_crawled = 0
        self.images_found = 0
        self.start_time = None
        
        # 会话管理
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start_crawling(self, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        开始爬取
        
        Args:
            session: HTTP会话对象
            
        Returns:
            爬取结果
        """
        self.start_time = time.time()
        self.session = session
        
        logger.info(f"开始爬取: {self.base_url}")
        logger.info(f"最大深度: {self.max_depth}, 最大页面数: {self.max_pages}")
        
        try:
            while self.pending_urls and self.pages_crawled < self.max_pages:
                current_url, depth = self.pending_urls.pop(0)
                
                # 检查深度限制
                if depth > self.max_depth:
                    continue
                
                # 检查是否已访问
                if current_url in self.visited_urls:
                    continue
                
                # 爬取页面
                await self._crawl_page(current_url, depth)
                
                # 添加延迟避免过于频繁的请求
                await asyncio.sleep(0.5)
            
            end_time = time.time()
            duration = end_time - self.start_time
            
            result = {
                'success': True,
                'base_url': self.base_url,
                'pages_crawled': self.pages_crawled,
                'images_found': len(self.found_images),
                'failed_urls': len(self.failed_urls),
                'duration': duration,
                'images': list(self.found_images),
                'statistics': self._get_statistics()
            }
            
            logger.info(f"爬取完成: 页面 {self.pages_crawled}, 图片 {len(self.found_images)}, 耗时 {duration:.2f}秒")
            return result
            
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            return {
                'success': False,
                'error': str(e),
                'pages_crawled': self.pages_crawled,
                'images_found': len(self.found_images),
                'images': list(self.found_images)
            }
    
    async def _crawl_page(self, url: str, depth: int):
        """
        爬取单个页面
        
        Args:
            url: 页面URL
            depth: 当前深度
        """
        try:
            self.visited_urls.add(url)
            logger.info(f"爬取页面 (深度 {depth}): {url}")
            
            # 获取页面内容
            html_content = await self._fetch_page(url)
            if not html_content:
                self.failed_urls.add(url)
                return
            
            # 解析页面
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取图片链接
            page_images = self._extract_images(soup, url)
            self.found_images.update(page_images)
            
            # 如果还没达到最大深度，提取页面链接
            if depth < self.max_depth:
                page_links = self._extract_links(soup, url, depth + 1)
                self.pending_urls.extend(page_links)
            
            self.pages_crawled += 1
            logger.info(f"页面爬取完成: {url}, 发现图片 {len(page_images)} 张")
            
        except Exception as e:
            logger.error(f"爬取页面失败: {url} -> {e}")
            self.failed_urls.add(url)
    
    async def _fetch_page(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        获取页面内容
        
        Args:
            url: 页面URL
            timeout: 超时时间
            
        Returns:
            页面HTML内容
        """
        try:
            if self.session:
                session = self.session
            else:
                session = aiohttp.ClientSession()
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' in content_type:
                        content = await response.text()
                        return content
                    else:
                        logger.warning(f"非HTML内容: {content_type} for {url}")
                else:
                    logger.warning(f"HTTP {response.status}: {url}")
                    
        except asyncio.TimeoutError:
            logger.warning(f"页面请求超时: {url}")
        except Exception as e:
            logger.warning(f"页面请求失败: {url} -> {e}")
        finally:
            if not self.session and 'session' in locals():
                await session.close()
        
        return None

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """
        从页面中提取图片链接

        Args:
            soup: BeautifulSoup对象
            base_url: 页面URL

        Returns:
            图片URL集合
        """
        images = set()

        # 提取img标签中的图片
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                absolute_url = self.url_parser.to_absolute_url(src)
                # 对于动态URL，启用内容类型检查
                if self.url_parser.is_image_url(absolute_url, check_content_type=True):
                    images.add(absolute_url)

            # 检查data-src属性（懒加载图片）
            data_src = img.get('data-src')
            if data_src:
                absolute_url = self.url_parser.to_absolute_url(data_src)
                if self.url_parser.is_image_url(absolute_url, check_content_type=True):
                    images.add(absolute_url)

            # 检查srcset属性
            srcset = img.get('srcset')
            if srcset:
                for src_item in srcset.split(','):
                    src_url = src_item.strip().split()[0]
                    absolute_url = self.url_parser.to_absolute_url(src_url)
                    if self.url_parser.is_image_url(absolute_url, check_content_type=True):
                        images.add(absolute_url)

        # 提取CSS背景图片
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            bg_matches = re.findall(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
            for bg_url in bg_matches:
                absolute_url = self.url_parser.to_absolute_url(bg_url)
                if self.url_parser.is_image_url(absolute_url):
                    images.add(absolute_url)

        # 提取链接中的图片
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            absolute_url = self.url_parser.to_absolute_url(href)
            if self.url_parser.is_image_url(absolute_url):
                images.add(absolute_url)

        # 提取picture标签中的图片
        for picture in soup.find_all('picture'):
            for source in picture.find_all('source'):
                srcset = source.get('srcset')
                if srcset:
                    for src_item in srcset.split(','):
                        src_url = src_item.strip().split()[0]
                        absolute_url = self.url_parser.to_absolute_url(src_url)
                        if self.url_parser.is_image_url(absolute_url):
                            images.add(absolute_url)

        logger.debug(f"从页面提取到 {len(images)} 张图片: {base_url}")
        return images

    def _extract_links(self, soup: BeautifulSoup, base_url: str, next_depth: int) -> List[tuple]:
        """
        从页面中提取链接

        Args:
            soup: BeautifulSoup对象
            base_url: 页面URL
            next_depth: 下一层深度

        Returns:
            链接列表 [(url, depth), ...]
        """
        links = []

        for link in soup.find_all('a', href=True):
            href = link.get('href')
            absolute_url = self.url_parser.to_absolute_url(href)

            # 验证URL
            if not self.url_parser.is_valid_url(absolute_url):
                continue

            # 检查是否为同域名
            if not self.url_parser.is_same_domain(absolute_url):
                continue

            # 检查是否已访问或在待访问列表中
            if absolute_url in self.visited_urls:
                continue

            if any(url == absolute_url for url, _ in self.pending_urls):
                continue

            # 过滤不需要的链接
            if self._should_skip_link(absolute_url):
                continue

            links.append((absolute_url, next_depth))

        logger.debug(f"从页面提取到 {len(links)} 个链接: {base_url}")
        return links

    def _should_skip_link(self, url: str) -> bool:
        """
        判断是否应该跳过链接

        Args:
            url: URL

        Returns:
            是否跳过
        """
        # 跳过文件下载链接
        skip_patterns = [
            r'.*\.(pdf|doc|docx|xls|xlsx|zip|rar|tar|gz)(\?.*)?$',
            r'.*/(download|file|attachment)/',
            r'.*\?(download|file)=',
            r'.*#.*',  # 锚点链接
            r'.*javascript:.*',
            r'.*mailto:.*',
            r'.*tel:.*',
        ]

        for pattern in skip_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True

        return False

    def _get_statistics(self) -> Dict[str, Any]:
        """获取爬取统计信息"""
        duration = time.time() - self.start_time if self.start_time else 0

        return {
            'pages_crawled': self.pages_crawled,
            'images_found': len(self.found_images),
            'failed_urls': len(self.failed_urls),
            'pending_urls': len(self.pending_urls),
            'duration': duration,
            'pages_per_second': self.pages_crawled / duration if duration > 0 else 0,
            'images_per_page': len(self.found_images) / self.pages_crawled if self.pages_crawled > 0 else 0,
        }
