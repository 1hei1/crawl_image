"""
URL解析和处理工具

提供URL的解析、验证、标准化等功能
"""

import re
import logging
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from typing import List, Set, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class URLParser:
    """
    URL解析器
    
    功能：
    - URL标准化和清理
    - 相对URL转绝对URL
    - URL有效性验证
    - 图片URL识别
    - 域名提取和验证
    """
    
    # 支持的图片扩展名
    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', 
        '.bmp', '.tiff', '.tif', '.svg', '.ico'
    }
    
    # 常见的图片URL模式
    IMAGE_URL_PATTERNS = [
        r'.*\.(jpg|jpeg|png|gif|webp|bmp|tiff|tif|svg|ico)(\?.*)?$',
        r'.*/images?/.*',
        r'.*/img/.*',
        r'.*/photos?/.*',
        r'.*/pictures?/.*',
        r'.*/gallery/.*',
        r'.*/media/.*\.(jpg|jpeg|png|gif|webp|bmp|tiff|tif|svg|ico)',
        # 动态图片URL模式
        r'.*/getCroppingImg/.*',  # 如 haowallpaper.com
        r'.*/getImage/.*',
        r'.*/image/.*',
        r'.*/thumbnail/.*',
        r'.*/resize/.*',
        r'.*/crop/.*',
        r'.*/photo/.*',
        r'.*/picture/.*',
        r'.*/wallpaper/.*',
        r'.*/avatar/.*',
        r'.*/cover/.*',
        r'.*/banner/.*',
        # API风格的图片URL
        r'.*/api/.*/(image|img|photo|picture)/.*',
        r'.*/v\d+/(image|img|photo|picture)/.*',
        # 包含图片相关关键词的动态URL
        r'.*/(image|img|photo|picture|wallpaper|avatar|cover|banner).*\d+.*',
        # CDN和云存储图片URL
        r'.*\.cloudfront\.net/.*',
        r'.*\.amazonaws\.com/.*\.(jpg|jpeg|png|gif|webp|bmp)',
        r'.*\.qiniudn\.com/.*',
        r'.*\.aliyuncs\.com/.*',
    ]
    
    # 需要排除的URL模式
    EXCLUDE_PATTERNS = [
        r'.*\.(css|js|xml|txt|pdf|doc|docx|xls|xlsx|zip|rar)(\?.*)?$',
        r'.*/ads?/.*',
        r'.*/advertisement/.*',
        r'.*\b(thumb|thumbnail|icon|favicon)\b.*',
        r'.*data:image/.*',  # base64图片
        r'.*javascript:.*',
        r'.*mailto:.*',
        r'.*tel:.*',
    ]
    
    def __init__(self, base_url: str):
        """
        初始化URL解析器
        
        Args:
            base_url: 基础URL，用于解析相对URL
        """
        self.base_url = self.normalize_url(base_url)
        self.base_domain = self.extract_domain(self.base_url)
        self.compiled_image_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.IMAGE_URL_PATTERNS]
        self.compiled_exclude_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.EXCLUDE_PATTERNS]
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        标准化URL
        
        Args:
            url: 原始URL
            
        Returns:
            标准化后的URL
        """
        if not url:
            return ""
        
        # 移除首尾空白
        url = url.strip()
        
        # 添加协议
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # 解析URL
        parsed = urlparse(url)
        
        # 标准化域名（转小写）
        netloc = parsed.netloc.lower()
        
        # 移除默认端口
        if netloc.endswith(':80') and parsed.scheme == 'http':
            netloc = netloc[:-3]
        elif netloc.endswith(':443') and parsed.scheme == 'https':
            netloc = netloc[:-4]
        
        # 标准化路径
        path = parsed.path
        if not path:
            path = '/'
        
        # 重新构建URL
        normalized = urlunparse((
            parsed.scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            ''  # 移除fragment
        ))
        
        return normalized
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """
        提取域名
        
        Args:
            url: URL
            
        Returns:
            域名
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def to_absolute_url(self, url: str) -> str:
        """
        将相对URL转换为绝对URL
        
        Args:
            url: 相对或绝对URL
            
        Returns:
            绝对URL
        """
        if not url:
            return ""
        
        try:
            # 如果已经是绝对URL，直接返回标准化结果
            if url.startswith(('http://', 'https://')):
                return self.normalize_url(url)
            
            # 处理协议相对URL
            if url.startswith('//'):
                parsed_base = urlparse(self.base_url)
                return self.normalize_url(f"{parsed_base.scheme}:{url}")
            
            # 处理相对URL
            absolute_url = urljoin(self.base_url, url)
            return self.normalize_url(absolute_url)
            
        except Exception as e:
            logger.warning(f"URL转换失败: {url} -> {e}")
            return ""
    
    def is_valid_url(self, url: str) -> bool:
        """
        验证URL是否有效
        
        Args:
            url: URL
            
        Returns:
            是否有效
        """
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ('http', 'https'),
                parsed.netloc,
                len(url) < 2048,  # URL长度限制
            ])
        except Exception:
            return False
    
    def is_image_url(self, url: str, check_content_type: bool = False) -> bool:
        """
        判断URL是否为图片URL

        Args:
            url: URL
            check_content_type: 是否检查HTTP响应的Content-Type

        Returns:
            是否为图片URL
        """
        if not url:
            return False

        # 检查是否在排除列表中
        for pattern in self.compiled_exclude_patterns:
            if pattern.match(url):
                return False

        # 检查文件扩展名
        parsed = urlparse(url)
        path = parsed.path.lower()

        # 从路径中提取扩展名
        if '.' in path:
            ext = Path(path).suffix
            if ext in self.IMAGE_EXTENSIONS:
                return True

        # 检查图片URL模式
        for pattern in self.compiled_image_patterns:
            if pattern.match(url):
                return True

        # 如果启用内容类型检查，对可疑的动态URL进行HTTP HEAD请求
        if check_content_type and self._is_potential_dynamic_image_url(url):
            return self._check_content_type(url)

        return False

    def _is_potential_dynamic_image_url(self, url: str) -> bool:
        """
        判断是否为潜在的动态图片URL

        Args:
            url: URL

        Returns:
            是否为潜在的动态图片URL
        """
        # 检查URL中是否包含图片相关关键词
        image_keywords = [
            'image', 'img', 'photo', 'picture', 'wallpaper', 'avatar',
            'cover', 'banner', 'thumbnail', 'thumb', 'crop', 'resize',
            'getCroppingImg', 'getImage'
        ]

        url_lower = url.lower()
        for keyword in image_keywords:
            if keyword in url_lower:
                return True

        # 检查是否为API风格的URL
        if '/api/' in url_lower or re.search(r'/v\d+/', url):
            return True

        # 检查是否包含数字ID（常见于动态图片URL）
        if re.search(r'/\d{8,}', url):  # 8位以上数字
            return True

        return False

    def _check_content_type(self, url: str) -> bool:
        """
        通过HTTP HEAD请求检查Content-Type

        Args:
            url: URL

        Returns:
            是否为图片类型
        """
        try:
            import requests
            response = requests.head(url, timeout=5, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()

            # 检查是否为图片类型
            image_types = [
                'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
                'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml'
            ]

            return any(img_type in content_type for img_type in image_types)

        except Exception as e:
            logger.debug(f"检查Content-Type失败: {url} -> {e}")
            return False
    
    def is_same_domain(self, url: str) -> bool:
        """
        判断URL是否与基础域名相同
        
        Args:
            url: URL
            
        Returns:
            是否同域名
        """
        domain = self.extract_domain(url)
        return domain == self.base_domain
    
    def clean_url(self, url: str) -> str:
        """
        清理URL，移除不必要的参数
        
        Args:
            url: 原始URL
            
        Returns:
            清理后的URL
        """
        if not url:
            return ""
        
        try:
            parsed = urlparse(url)
            
            # 需要保留的查询参数
            keep_params = ['id', 'size', 'width', 'height', 'quality', 'format']
            
            if parsed.query:
                query_params = parse_qs(parsed.query)
                filtered_params = {
                    k: v for k, v in query_params.items() 
                    if k.lower() in keep_params
                }
                new_query = urlencode(filtered_params, doseq=True)
            else:
                new_query = ""
            
            cleaned = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                ""
            ))
            
            return cleaned
            
        except Exception as e:
            logger.warning(f"URL清理失败: {url} -> {e}")
            return url
    
    def extract_filename(self, url: str) -> str:
        """
        从URL中提取文件名
        
        Args:
            url: URL
            
        Returns:
            文件名
        """
        if not url:
            return ""
        
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            if path and path != '/':
                filename = Path(path).name
                if filename and '.' in filename:
                    return filename
            
            # 如果无法从路径提取，使用URL的哈希值作为文件名
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            return f"image_{url_hash}.jpg"
            
        except Exception:
            return "unknown.jpg"
    
    def get_url_info(self, url: str) -> dict:
        """
        获取URL的详细信息
        
        Args:
            url: URL
            
        Returns:
            URL信息字典
        """
        absolute_url = self.to_absolute_url(url)
        
        return {
            'original_url': url,
            'absolute_url': absolute_url,
            'cleaned_url': self.clean_url(absolute_url),
            'domain': self.extract_domain(absolute_url),
            'filename': self.extract_filename(absolute_url),
            'is_valid': self.is_valid_url(absolute_url),
            'is_image': self.is_image_url(absolute_url),
            'is_same_domain': self.is_same_domain(absolute_url),
        }
