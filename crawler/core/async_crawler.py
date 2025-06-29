"""
异步爬虫引擎

实现高效的异步爬取和下载功能
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


from crawler.core.downloader import ImageDownloader
from crawler.handlers.session_manager import RobustSessionManager
from crawler.utils.url_parser import URLParser

logger = logging.getLogger(__name__)


@dataclass
class CrawlTask:
    """爬取任务"""
    url: str
    depth: int = 0
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        return self.priority < other.priority


@dataclass
class DownloadTask:
    """下载任务"""
    url: str
    filename: Optional[str] = None
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """用于优先级队列排序"""
        return self.priority < other.priority


class AsyncCrawler:
    """
    异步爬虫引擎
    
    功能：
    - 异步并发爬取
    - 任务队列管理
    - 进度跟踪和回调
    - 资源限制和控制
    - 错误处理和重试
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化异步爬虫
        
        Args:
            config: 爬虫配置
        """
        self.config = config
        self.max_concurrent = config.get('max_concurrent', 10)
        self.max_depth = config.get('max_depth', 3)
        self.max_images = config.get('max_images', 1000)
        
        # 任务队列
        self.crawl_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.download_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # 状态跟踪
        self.visited_urls: Set[str] = set()
        self.found_images: Set[str] = set()
        self.downloaded_images: Set[str] = set()
        self.failed_urls: Set[str] = set()

        # 文件名映射：URL -> 实际文件名
        self.url_to_filename: Dict[str, str] = {}
        
        # 统计信息
        self.stats = {
            'pages_crawled': 0,
            'images_found': 0,
            'images_downloaded': 0,
            'images_failed': 0,
            'start_time': 0,
            'end_time': 0,
        }
        
        # 控制标志
        self.is_running = False
        self.should_stop = False
        
        # 回调函数
        self.progress_callback: Optional[Callable] = None
        self.page_callback: Optional[Callable] = None
        self.image_callback: Optional[Callable] = None
        
        # 会话管理器
        self.session_manager: Optional[RobustSessionManager] = None
        
        # 线程池（用于CPU密集型任务）
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
    
    async def start_crawling(self, start_url: str, 
                           progress_callback: Optional[Callable] = None,
                           page_callback: Optional[Callable] = None,
                           image_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        开始异步爬取
        
        Args:
            start_url: 起始URL
            progress_callback: 进度回调函数
            page_callback: 页面处理回调函数
            image_callback: 图片处理回调函数
            
        Returns:
            爬取结果
        """
        self.progress_callback = progress_callback
        self.page_callback = page_callback
        self.image_callback = image_callback
        
        self.stats['start_time'] = time.time()
        self.is_running = True
        self.should_stop = False
        
        logger.info(f"开始异步爬取: {start_url}")
        
        try:
            # 创建会话管理器
            anti_crawler_config = self.config.get('anti_crawler', {})
            self.session_manager = RobustSessionManager(anti_crawler_config)
            
            async with self.session_manager:
                # 添加初始任务
                await self.crawl_queue.put(CrawlTask(start_url, 0, 0))
                
                # 创建工作协程
                crawl_workers = [
                    asyncio.create_task(self._crawl_worker(f"crawler-{i}"))
                    for i in range(min(self.max_concurrent, 5))
                ]
                
                download_workers = [
                    asyncio.create_task(self._download_worker(f"downloader-{i}"))
                    for i in range(self.max_concurrent)
                ]
                
                # 等待所有任务完成
                await self._wait_for_completion()
                
                # 取消工作协程
                for worker in crawl_workers + download_workers:
                    worker.cancel()
                
                # 等待协程清理
                await asyncio.gather(*crawl_workers, *download_workers, return_exceptions=True)
            
            self.stats['end_time'] = time.time()
            self.is_running = False
            
            # 生成结果
            result = self._generate_result()
            logger.info(f"爬取完成: {result['summary']}")
            
            return result
            
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            self.is_running = False
            return {
                'success': False,
                'error': str(e),
                'stats': self.stats,
                'images': list(self.found_images)
            }
        finally:
            # 清理资源
            self.thread_pool.shutdown(wait=True)
    
    async def _crawl_worker(self, worker_name: str):
        """爬取工作协程"""
        logger.debug(f"启动爬取工作协程: {worker_name}")
        
        while not self.should_stop:
            try:
                # 获取任务（超时避免无限等待）
                task = await asyncio.wait_for(self.crawl_queue.get(), timeout=5.0)
                
                # 检查是否应该处理此任务
                if (task.url in self.visited_urls or 
                    task.depth > self.max_depth or
                    self.stats['pages_crawled'] >= self.config.get('max_pages', 100)):
                    self.crawl_queue.task_done()
                    continue
                
                # 处理爬取任务
                await self._process_crawl_task(task, worker_name)
                self.crawl_queue.task_done()
                
            except asyncio.TimeoutError:
                # 超时，检查是否还有任务
                if self.crawl_queue.empty():
                    break
            except Exception as e:
                logger.error(f"爬取工作协程 {worker_name} 发生错误: {e}")
                await asyncio.sleep(1)
        
        logger.debug(f"爬取工作协程退出: {worker_name}")
    
    async def _download_worker(self, worker_name: str):
        """下载工作协程"""
        logger.debug(f"启动下载工作协程: {worker_name}")
        
        # 创建下载器
        download_path = self.config.get('download_path', 'data/images')
        downloader = ImageDownloader(download_path, self.session_manager.get_session())
        
        while not self.should_stop:
            try:
                # 获取任务
                task = await asyncio.wait_for(self.download_queue.get(), timeout=5.0)
                
                # 检查是否已下载
                if task.url in self.downloaded_images:
                    self.download_queue.task_done()
                    continue
                
                # 检查下载数量限制
                if len(self.downloaded_images) >= self.max_images:
                    self.download_queue.task_done()
                    continue
                
                # 处理下载任务
                await self._process_download_task(task, downloader, worker_name)
                self.download_queue.task_done()
                
            except asyncio.TimeoutError:
                # 超时，检查是否还有任务
                if self.download_queue.empty():
                    break
            except Exception as e:
                logger.error(f"下载工作协程 {worker_name} 发生错误: {e}")
                await asyncio.sleep(1)
        
        logger.debug(f"下载工作协程退出: {worker_name}")
    
    async def _process_crawl_task(self, task: CrawlTask, worker_name: str):
        """处理爬取任务"""
        try:
            # 检查是否是图片URL，如果是则跳过页面爬取
            url_parser = URLParser(task.url)
            if url_parser.is_image_url(task.url):
                logger.debug(f"跳过图片URL的页面爬取: {task.url}")
                return

            self.visited_urls.add(task.url)
            logger.debug(f"{worker_name} 爬取页面: {task.url}")

            # 获取页面内容
            response = await self.session_manager.get(task.url)
            async with response:
                if response.status != 200:
                    logger.warning(f"页面响应异常: {response.status} for {task.url}")
                    return

                # 检查内容类型
                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('text/'):
                    logger.debug(f"跳过非文本内容: {task.url} (类型: {content_type})")
                    return

                # 智能编码检测和解码
                content = await self._decode_response_content(response)
            
            # 在线程池中解析页面（CPU密集型任务）
            loop = asyncio.get_event_loop()
            images, links = await loop.run_in_executor(
                self.thread_pool, 
                self._parse_page_content, 
                content, 
                task.url
            )
            
            # 添加图片下载任务
            for image_url in images:
                if image_url not in self.found_images:
                    self.found_images.add(image_url)
                    await self.download_queue.put(DownloadTask(image_url))
            
            # 添加新的爬取任务
            if task.depth < self.max_depth:
                for link_url in links:
                    if link_url not in self.visited_urls:
                        await self.crawl_queue.put(CrawlTask(link_url, task.depth + 1))
            
            self.stats['pages_crawled'] += 1
            self.stats['images_found'] = len(self.found_images)
            
            # 调用页面回调
            if self.page_callback:
                await self.page_callback(task.url, len(images), len(links))
            
            # 调用进度回调
            if self.progress_callback:
                await self.progress_callback(self.stats)
            
        except Exception as e:
            logger.error(f"处理爬取任务失败: {task.url} -> {e}")
            self.failed_urls.add(task.url)
            
            # 重试逻辑
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                await self.crawl_queue.put(task)
    
    def _parse_page_content(self, content: str, base_url: str) -> tuple:
        """解析页面内容（在线程池中执行）"""
        from bs4 import BeautifulSoup
        import warnings

        # 抑制XML解析警告
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="bs4")
            soup = BeautifulSoup(content, 'html.parser')
        url_parser = URLParser(base_url)
        
        # 提取图片 - 增强版本，支持懒加载
        images = set()

        # 处理img标签
        for img in soup.find_all('img'):
            image_urls = self._extract_image_urls_from_element(img, url_parser)
            images.update(image_urls)

        # 处理其他可能包含图片的元素
        for element in soup.find_all(['div', 'span', 'a'], attrs={'data-original': True}):
            image_urls = self._extract_image_urls_from_element(element, url_parser)
            images.update(image_urls)

        # 处理CSS背景图片
        for element in soup.find_all(attrs={'style': True}):
            style = element.get('style', '')
            if 'background-image' in style:
                bg_urls = self._extract_background_images(style, url_parser)
                images.update(bg_urls)
        
        # 提取链接
        links = set()
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            absolute_url = url_parser.to_absolute_url(href)
            if (url_parser.is_valid_url(absolute_url) and 
                url_parser.is_same_domain(absolute_url)):
                links.add(absolute_url)
        
        return list(images), list(links)

    def _extract_image_urls_from_element(self, element, url_parser):
        """从HTML元素中提取图片URL"""
        image_urls = set()

        # 常见的懒加载属性列表（按优先级排序）
        lazy_attributes = [
            'data-original',    # 最常见的懒加载属性
            'data-src',         # 另一个常见属性
            'data-lazy-src',    # 懒加载专用
            'data-lazy',        # 简化版本
            'data-url',         # 通用数据URL
            'data-img',         # 图片数据
            'data-image',       # 图片数据
            'data-large',       # 大图
            'data-full',        # 完整图片
            'data-hd',          # 高清图片
            'data-hi-res',      # 高分辨率
            'data-zoom',        # 缩放图片
            'data-thumb',       # 缩略图
            'data-preview',     # 预览图
            'srcset',           # 响应式图片
            'src'               # 标准属性（最后检查）
        ]

        # 按优先级检查属性
        for attr in lazy_attributes:
            value = element.get(attr)
            if value and value.strip():
                # 处理srcset属性（可能包含多个URL）
                if attr == 'srcset':
                    urls = self._parse_srcset(value)
                    for url in urls:
                        absolute_url = url_parser.to_absolute_url(url)
                        if url_parser.is_image_url(absolute_url):
                            image_urls.add(absolute_url)
                else:
                    # 处理单个URL
                    absolute_url = url_parser.to_absolute_url(value.strip())
                    if url_parser.is_image_url(absolute_url):
                        image_urls.add(absolute_url)
                        break  # 找到有效图片就停止

        return image_urls

    def _parse_srcset(self, srcset_value):
        """解析srcset属性值"""
        urls = []
        if srcset_value:
            # srcset格式: "url1 1x, url2 2x" 或 "url1 100w, url2 200w"
            parts = srcset_value.split(',')
            for part in parts:
                part = part.strip()
                if part:
                    # 提取URL（去掉尺寸描述符）
                    url = part.split()[0] if ' ' in part else part
                    urls.append(url)
        return urls

    def _extract_background_images(self, style_text, url_parser):
        """从CSS样式中提取背景图片URL"""
        import re
        image_urls = set()

        # 匹配CSS背景图片
        bg_pattern = r'background-image\s*:\s*url\s*\(\s*["\']?([^"\')\s]+)["\']?\s*\)'
        matches = re.findall(bg_pattern, style_text, re.IGNORECASE)

        for match in matches:
            absolute_url = url_parser.to_absolute_url(match)
            if url_parser.is_image_url(absolute_url):
                image_urls.add(absolute_url)

        return image_urls

    async def _decode_response_content(self, response):
        """智能解码响应内容，自动检测编码"""
        try:
            # 首先尝试从响应头获取编码
            content_type = response.headers.get('content-type', '')
            charset = None

            # 解析Content-Type头中的charset
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[1].split(';')[0].strip()
                logger.debug(f"从Content-Type头检测到编码: {charset}")

            # 如果响应头有编码信息，直接使用
            if charset:
                try:
                    return await response.text(encoding=charset)
                except (UnicodeDecodeError, LookupError) as e:
                    logger.warning(f"使用响应头编码 {charset} 解码失败: {e}")

            # 获取原始字节数据
            raw_content = await response.read()

            # 尝试自动检测编码
            detected_encoding = self._detect_encoding(raw_content)

            if detected_encoding:
                try:
                    content = raw_content.decode(detected_encoding)
                    logger.debug(f"使用检测到的编码 {detected_encoding} 解码成功")
                    return content
                except UnicodeDecodeError as e:
                    logger.warning(f"使用检测编码 {detected_encoding} 解码失败: {e}")

            # 如果自动检测失败，尝试常见编码
            common_encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'iso-8859-1', 'windows-1252']

            for encoding in common_encodings:
                try:
                    content = raw_content.decode(encoding)
                    logger.debug(f"使用编码 {encoding} 解码成功")
                    return content
                except UnicodeDecodeError:
                    continue

            # 最后的备选方案：使用errors='ignore'
            logger.warning(f"所有编码尝试失败，使用UTF-8忽略错误模式解码")
            return raw_content.decode('utf-8', errors='ignore')

        except Exception as e:
            logger.error(f"内容解码失败: {e}")
            # 返回空字符串避免程序崩溃
            return ""

    def _detect_encoding(self, raw_content):
        """检测文本编码"""
        try:
            # 尝试使用chardet库进行编码检测
            try:
                import chardet
                result = chardet.detect(raw_content[:10000])  # 只检测前10KB
                if result and result['encoding']:
                    confidence = result.get('confidence', 0)
                    encoding = result['encoding'].lower()

                    # 只有置信度足够高才使用检测结果
                    if confidence > 0.7:
                        logger.debug(f"chardet检测编码: {encoding} (置信度: {confidence:.2f})")
                        return encoding
                    else:
                        logger.debug(f"chardet检测编码置信度过低: {encoding} (置信度: {confidence:.2f})")
            except ImportError:
                logger.debug("chardet库未安装，使用内置编码检测")

            # 内置简单编码检测
            return self._simple_encoding_detection(raw_content)

        except Exception as e:
            logger.warning(f"编码检测失败: {e}")
            return None

    def _simple_encoding_detection(self, raw_content):
        """简单的编码检测方法"""
        try:
            # 检查BOM标记
            if raw_content.startswith(b'\xef\xbb\xbf'):
                return 'utf-8-sig'
            elif raw_content.startswith(b'\xff\xfe'):
                return 'utf-16-le'
            elif raw_content.startswith(b'\xfe\xff'):
                return 'utf-16-be'

            # 检查HTML meta标签中的编码声明
            content_sample = raw_content[:2048].lower()

            # 查找charset声明
            import re
            charset_patterns = [
                rb'<meta[^>]+charset["\s]*=["\s]*([^">\s]+)',
                rb'<meta[^>]+content[^>]+charset=([^">\s;]+)',
                rb'<?xml[^>]+encoding["\s]*=["\s]*([^">\s]+)'
            ]

            for pattern in charset_patterns:
                match = re.search(pattern, content_sample)
                if match:
                    encoding = match.group(1).decode('ascii', errors='ignore').strip()
                    logger.debug(f"从HTML meta标签检测到编码: {encoding}")
                    return encoding

            # 基于字节特征的简单判断
            # 检查是否包含中文GBK特征字节
            if any(b in raw_content[:1000] for b in [b'\xa1\xa1', b'\xa3\xa1', b'\xc1\xf7']):
                return 'gbk'

            # 检查是否为有效的UTF-8
            try:
                raw_content.decode('utf-8')
                return 'utf-8'
            except UnicodeDecodeError:
                pass

            return None

        except Exception as e:
            logger.warning(f"简单编码检测失败: {e}")
            return None

    async def _process_download_task(self, task: DownloadTask, downloader: ImageDownloader, worker_name: str):
        """处理下载任务"""
        try:
            logger.debug(f"{worker_name} 下载图片: {task.url}")

            # 下载图片
            result = await downloader.download_image(
                task.url,
                task.filename,
                max_retries=task.max_retries
            )

            if result['success']:
                self.downloaded_images.add(task.url)
                self.stats['images_downloaded'] += 1

                # 记录URL到实际文件名的映射
                if result.get('local_path'):
                    actual_filename = Path(result['local_path']).name
                    self.url_to_filename[task.url] = actual_filename

                logger.info(f"图片下载成功: {task.url} -> {self.url_to_filename.get(task.url, 'unknown')}")

                # 调用图片回调
                if self.image_callback:
                    await self.image_callback(task.url, result)
            else:
                self.stats['images_failed'] += 1
                logger.warning(f"图片下载失败: {task.url} -> {result['error']}")

                # 重试逻辑
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    await self.download_queue.put(task)

            # 调用进度回调
            if self.progress_callback:
                await self.progress_callback(self.stats)

        except Exception as e:
            logger.error(f"处理下载任务失败: {task.url} -> {e}")
            self.stats['images_failed'] += 1

    async def _wait_for_completion(self):
        """等待所有任务完成"""
        while not self.should_stop:
            # 检查队列是否为空
            crawl_empty = self.crawl_queue.empty()
            download_empty = self.download_queue.empty()

            if crawl_empty and download_empty:
                # 等待一段时间确保没有新任务
                await asyncio.sleep(2)
                if self.crawl_queue.empty() and self.download_queue.empty():
                    break
            else:
                await asyncio.sleep(1)

            # 检查是否达到限制
            if (self.stats['pages_crawled'] >= self.config.get('max_pages', 100) or
                len(self.downloaded_images) >= self.max_images):
                self.should_stop = True
                break

    def _generate_result(self) -> Dict[str, Any]:
        """生成爬取结果"""
        duration = self.stats['end_time'] - self.stats['start_time']

        return {
            'success': True,
            'stats': {
                **self.stats,
                'duration': duration,
                'pages_per_second': self.stats['pages_crawled'] / duration if duration > 0 else 0,
                'images_per_second': self.stats['images_downloaded'] / duration if duration > 0 else 0,
                'success_rate': (
                    self.stats['images_downloaded'] / self.stats['images_found'] * 100
                    if self.stats['images_found'] > 0 else 0
                ),
            },
            'summary': (
                f"页面: {self.stats['pages_crawled']}, "
                f"图片: {self.stats['images_downloaded']}/{self.stats['images_found']}, "
                f"耗时: {duration:.2f}秒"
            ),
            'images': list(self.found_images),
            'downloaded_images': list(self.downloaded_images),
            'failed_urls': list(self.failed_urls),
            'url_to_filename': dict(self.url_to_filename),  # URL到实际文件名的映射
        }

    def stop_crawling(self):
        """停止爬取"""
        self.should_stop = True
        logger.info("收到停止信号，正在停止爬取...")

    def get_statistics(self) -> Dict[str, Any]:
        """获取实时统计信息"""
        current_time = time.time()
        duration = current_time - self.stats['start_time'] if self.stats['start_time'] > 0 else 0

        return {
            **self.stats,
            'duration': duration,
            'is_running': self.is_running,
            'should_stop': self.should_stop,
            'queue_sizes': {
                'crawl_queue': self.crawl_queue.qsize(),
                'download_queue': self.download_queue.qsize(),
            },
            'visited_urls_count': len(self.visited_urls),
            'found_images_count': len(self.found_images),
            'downloaded_images_count': len(self.downloaded_images),
            'failed_urls_count': len(self.failed_urls),
        }


class TaskScheduler:
    """
    任务调度器

    管理多个爬取任务的调度和执行
    """

    def __init__(self, max_concurrent_crawlers: int = 3):
        """
        初始化任务调度器

        Args:
            max_concurrent_crawlers: 最大并发爬虫数
        """
        self.max_concurrent_crawlers = max_concurrent_crawlers
        self.active_crawlers: Dict[str, AsyncCrawler] = {}
        self.completed_tasks: List[Dict[str, Any]] = []
        self.semaphore = asyncio.Semaphore(max_concurrent_crawlers)

    async def schedule_crawl(self, task_id: str, start_url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调度爬取任务

        Args:
            task_id: 任务ID
            start_url: 起始URL
            config: 爬虫配置

        Returns:
            爬取结果
        """
        async with self.semaphore:
            try:
                logger.info(f"开始执行任务: {task_id}")

                # 创建爬虫
                crawler = AsyncCrawler(config)
                self.active_crawlers[task_id] = crawler

                # 执行爬取
                result = await crawler.start_crawling(start_url)
                result['task_id'] = task_id
                result['start_url'] = start_url

                # 记录完成的任务
                self.completed_tasks.append(result)

                return result

            except Exception as e:
                logger.error(f"任务执行失败: {task_id} -> {e}")
                return {
                    'success': False,
                    'task_id': task_id,
                    'start_url': start_url,
                    'error': str(e)
                }
            finally:
                # 清理
                if task_id in self.active_crawlers:
                    del self.active_crawlers[task_id]

    async def schedule_multiple_crawls(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        调度多个爬取任务

        Args:
            tasks: 任务列表，每个任务包含 task_id, start_url, config

        Returns:
            所有任务的结果列表
        """
        # 创建任务协程
        crawl_tasks = [
            self.schedule_crawl(task['task_id'], task['start_url'], task['config'])
            for task in tasks
        ]

        # 并发执行
        results = await asyncio.gather(*crawl_tasks, return_exceptions=True)

        return results

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取活跃任务状态"""
        return {
            task_id: crawler.get_statistics()
            for task_id, crawler in self.active_crawlers.items()
        }

    def stop_all_tasks(self):
        """停止所有活跃任务"""
        for crawler in self.active_crawlers.values():
            crawler.stop_crawling()
        logger.info("已发送停止信号给所有活跃任务")
