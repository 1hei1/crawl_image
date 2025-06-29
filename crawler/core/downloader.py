"""
图片下载器

负责图片的下载、验证和存储
"""

import hashlib
import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
from PIL import Image
import time

from crawler.utils.url_parser import URLParser

logger = logging.getLogger(__name__)


class ImageDownloader:
    """
    图片下载器
    
    功能：
    - 异步下载图片
    - 图片验证和元数据提取
    - 文件去重和哈希计算
    - 下载进度跟踪
    - 错误处理和重试
    """
    
    def __init__(self, download_path: str, session: Optional[aiohttp.ClientSession] = None):
        """
        初始化下载器
        
        Args:
            download_path: 下载目录
            session: HTTP会话对象
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.session = session
        self.downloaded_count = 0
        self.failed_count = 0
        self.total_size = 0
    
    async def download_image(self, url: str, filename: Optional[str] = None, 
                           max_retries: int = 3, timeout: int = 30) -> Dict[str, Any]:
        """
        下载单个图片
        
        Args:
            url: 图片URL
            filename: 自定义文件名
            max_retries: 最大重试次数
            timeout: 超时时间
            
        Returns:
            下载结果字典
        """
        result = {
            'url': url,
            'success': False,
            'local_path': None,
            'file_size': 0,
            'width': 0,
            'height': 0,
            'format': None,
            'md5_hash': None,
            'error': None,
            'download_time': 0,
        }
        
        start_time = time.time()
        
        try:
            # 解析URL获取文件名
            if not filename:
                url_parser = URLParser(url)
                filename = url_parser.extract_filename(url)

                # 如果文件名没有扩展名，先尝试获取Content-Type来确定扩展名
                if '.' not in filename or not any(ext in filename.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                    filename = await self._get_filename_with_extension(url, filename)
            
            # 构建本地文件路径
            local_path = self.download_path / filename
            
            # 如果文件已存在，检查是否需要重新下载
            if local_path.exists():
                logger.info(f"文件已存在: {local_path}")
                # 验证现有文件
                existing_result = await self._validate_image(local_path)
                if existing_result['success']:
                    result.update(existing_result)
                    result['local_path'] = str(local_path)
                    result['success'] = True
                    return result
            
            # 下载文件
            for attempt in range(max_retries + 1):
                session = None
                try:
                    if self.session:
                        session = self.session
                    else:
                        session = aiohttp.ClientSession()

                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                        if response.status == 200:
                            # 检查内容类型
                            content_type = response.headers.get('content-type', '')
                            if not content_type.startswith('image/'):
                                logger.warning(f"非图片内容类型: {content_type} for {url}")

                            # 读取内容
                            content = await response.read()

                            # 保存文件
                            with open(local_path, 'wb') as f:
                                f.write(content)

                            # 验证图片
                            validation_result = await self._validate_image(local_path)
                            if validation_result['success']:
                                result.update(validation_result)
                                result['local_path'] = str(local_path)
                                result['success'] = True
                                result['file_size'] = len(content)

                                # 计算哈希值
                                result['md5_hash'] = hashlib.md5(content).hexdigest()

                                self.downloaded_count += 1
                                self.total_size += len(content)

                                logger.info(f"下载成功: {url} -> {local_path}")
                                break
                            else:
                                # 删除无效文件
                                local_path.unlink(missing_ok=True)
                                result['error'] = validation_result['error']
                        else:
                            result['error'] = f"HTTP {response.status}: {response.reason}"

                except asyncio.TimeoutError:
                    result['error'] = f"下载超时 (尝试 {attempt + 1}/{max_retries + 1})"
                    logger.warning(f"下载超时: {url} (尝试 {attempt + 1})")

                except Exception as e:
                    result['error'] = f"下载错误: {str(e)} (尝试 {attempt + 1}/{max_retries + 1})"
                    logger.warning(f"下载失败: {url} -> {e} (尝试 {attempt + 1})")

                finally:
                    # 关闭会话（如果是临时创建的）
                    if not self.session and session and not session.closed:
                        await session.close()

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            
            if not result['success']:
                self.failed_count += 1
                logger.error(f"下载失败: {url} -> {result['error']}")
                
        except Exception as e:
            result['error'] = f"未知错误: {str(e)}"
            self.failed_count += 1
            logger.error(f"下载异常: {url} -> {e}")
        
        finally:
            result['download_time'] = time.time() - start_time
        
        return result

    async def _validate_image(self, file_path: Path) -> Dict[str, Any]:
        """
        验证图片文件

        Args:
            file_path: 图片文件路径

        Returns:
            验证结果
        """
        result = {
            'success': False,
            'width': 0,
            'height': 0,
            'format': None,
            'mode': None,
            'has_transparency': False,
            'error': None
        }

        try:
            if not file_path.exists():
                result['error'] = "文件不存在"
                return result

            # 检查文件大小
            file_size = file_path.stat().st_size
            if file_size == 0:
                result['error'] = "文件为空"
                return result

            if file_size < 100:  # 小于100字节的文件可能不是有效图片
                result['error'] = "文件太小"
                return result

            # 使用PIL验证图片
            with Image.open(file_path) as img:
                result['width'] = img.width
                result['height'] = img.height
                result['format'] = img.format
                result['mode'] = img.mode
                result['has_transparency'] = img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                result['success'] = True

                # 基本质量检查
                if img.width < 10 or img.height < 10:
                    result['error'] = "图片尺寸太小"
                    result['success'] = False

        except Exception as e:
            result['error'] = f"图片验证失败: {str(e)}"
            logger.warning(f"图片验证失败: {file_path} -> {e}")

        return result

    async def download_batch(self, urls: list, max_concurrent: int = 10,
                           progress_callback=None) -> Dict[str, Any]:
        """
        批量下载图片

        Args:
            urls: URL列表
            max_concurrent: 最大并发数
            progress_callback: 进度回调函数

        Returns:
            批量下载结果
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def download_with_semaphore(url):
            async with semaphore:
                result = await self.download_image(url)
                if progress_callback:
                    await progress_callback(result, len(results) + 1, len(urls))
                return result

        # 创建任务
        tasks = [download_with_semaphore(url) for url in urls]

        # 执行下载
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # 统计结果
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success', False))
        failed = len(results) - successful
        total_time = end_time - start_time

        return {
            'total_urls': len(urls),
            'successful': successful,
            'failed': failed,
            'success_rate': successful / len(urls) * 100 if urls else 0,
            'total_time': total_time,
            'average_time': total_time / len(urls) if urls else 0,
            'total_size': self.total_size,
            'results': results
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取下载统计信息"""
        return {
            'downloaded_count': self.downloaded_count,
            'failed_count': self.failed_count,
            'total_size': self.total_size,
            'total_size_mb': round(self.total_size / (1024 * 1024), 2),
            'success_rate': (
                self.downloaded_count / (self.downloaded_count + self.failed_count) * 100
                if (self.downloaded_count + self.failed_count) > 0 else 0
            )
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.downloaded_count = 0
        self.failed_count = 0
        self.total_size = 0

    async def _get_filename_with_extension(self, url: str, default_filename: str) -> str:
        """
        通过HTTP HEAD请求获取正确的文件扩展名

        Args:
            url: 图片URL
            default_filename: 默认文件名

        Returns:
            带正确扩展名的文件名
        """
        try:
            session = None
            if self.session:
                session = self.session
            else:
                import aiohttp
                session = aiohttp.ClientSession()

            try:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    content_type = response.headers.get('content-type', '').lower()

                    # 根据Content-Type确定扩展名
                    extension_map = {
                        'image/jpeg': '.jpg',
                        'image/jpg': '.jpg',
                        'image/png': '.png',
                        'image/gif': '.gif',
                        'image/webp': '.webp',
                        'image/bmp': '.bmp',
                        'image/tiff': '.tiff',
                        'image/svg+xml': '.svg'
                    }

                    for content_type_key, ext in extension_map.items():
                        if content_type_key in content_type:
                            # 如果默认文件名已经有扩展名，替换它
                            if '.' in default_filename:
                                base_name = default_filename.rsplit('.', 1)[0]
                                return f"{base_name}{ext}"
                            else:
                                return f"{default_filename}{ext}"

                    # 如果无法确定类型，尝试从Content-Disposition获取文件名
                    content_disposition = response.headers.get('content-disposition', '')
                    if 'filename=' in content_disposition:
                        import re
                        match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
                        if match:
                            suggested_filename = match.group(1).strip('"\'')
                            if '.' in suggested_filename:
                                return suggested_filename

            finally:
                if not self.session and session:
                    await session.close()

        except Exception as e:
            logger.debug(f"获取文件扩展名失败: {url} -> {e}")

        # 如果都失败了，使用默认扩展名
        if '.' not in default_filename:
            return f"{default_filename}.jpg"  # 默认使用.jpg

        return default_filename
