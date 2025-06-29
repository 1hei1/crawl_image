"""
会话管理器

管理HTTP会话的生命周期和配置
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import aiohttp

from crawler.handlers.anti_crawler import AntiCrawlerHandler

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器
    
    功能：
    - HTTP会话生命周期管理
    - 反爬虫功能集成
    - 连接池管理
    - 错误处理和重试
    """
    
    def __init__(self, anti_crawler_config: Dict[str, Any]):
        """
        初始化会话管理器
        
        Args:
            anti_crawler_config: 反爬虫配置
        """
        self.anti_crawler = AntiCrawlerHandler(anti_crawler_config)
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_closed = False
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()
    
    async def create_session(self):
        """创建HTTP会话"""
        if self.session and not self.session.closed:
            return
        
        try:
            self.session = await self.anti_crawler.create_session()
            self.is_closed = False
            logger.info("HTTP会话创建成功")
        except Exception as e:
            logger.error(f"创建HTTP会话失败: {e}")
            raise
    
    async def close_session(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.is_closed = True
            logger.info("HTTP会话已关闭")
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        if not self.session or self.session.closed:
            await self.create_session()
        
        return await self.anti_crawler.make_request(self.session, 'GET', url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        发送POST请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        if not self.session or self.session.closed:
            await self.create_session()
        
        return await self.anti_crawler.make_request(self.session, 'POST', url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        发送HEAD请求
        
        Args:
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        if not self.session or self.session.closed:
            await self.create_session()
        
        return await self.anti_crawler.make_request(self.session, 'HEAD', url, **kwargs)
    
    def get_session(self) -> Optional[aiohttp.ClientSession]:
        """获取当前会话对象"""
        return self.session
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.anti_crawler.get_statistics()
        stats.update({
            'session_active': self.session is not None and not self.session.closed,
            'session_closed': self.is_closed,
        })
        return stats
    
    async def test_connection(self, test_url: str = "https://httpbin.org/get") -> bool:
        """
        测试网络连接
        
        Args:
            test_url: 测试URL
            
        Returns:
            连接是否正常
        """
        try:
            async with self.get(test_url) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False


class RobustSessionManager(SessionManager):
    """
    增强的会话管理器
    
    添加了自动重试和错误恢复功能
    """
    
    def __init__(self, anti_crawler_config: Dict[str, Any], max_retries: int = 3):
        """
        初始化增强会话管理器
        
        Args:
            anti_crawler_config: 反爬虫配置
            max_retries: 最大重试次数
        """
        super().__init__(anti_crawler_config)
        self.max_retries = max_retries
        self.retry_count = 0
    
    async def _make_request_with_retry(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        带重试的请求方法
        
        Args:
            method: 请求方法
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if not self.session or self.session.closed:
                    await self.create_session()
                
                response = await self.anti_crawler.make_request(self.session, method, url, **kwargs)
                
                # 重置重试计数
                self.retry_count = 0
                return response
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                self.retry_count += 1
                
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {url} -> {e}")
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.max_retries:
                    # 关闭当前会话
                    await self.close_session()
                    
                    # 指数退避
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    # 最后一次尝试失败
                    logger.error(f"请求最终失败: {url}")
                    raise last_exception
        
        # 理论上不会到达这里
        raise last_exception
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """发送GET请求（带重试）"""
        return await self._make_request_with_retry('GET', url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """发送POST请求（带重试）"""
        return await self._make_request_with_retry('POST', url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """发送HEAD请求（带重试）"""
        return await self._make_request_with_retry('HEAD', url, **kwargs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = super().get_statistics()
        stats.update({
            'max_retries': self.max_retries,
            'current_retry_count': self.retry_count,
        })
        return stats
