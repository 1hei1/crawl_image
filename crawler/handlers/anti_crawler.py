"""
反爬虫处理器

实现各种反爬虫机制，包括User-Agent轮换、代理支持、请求延迟等
"""

import random
import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class AntiCrawlerHandler:
    """
    反爬虫处理器
    
    功能：
    - User-Agent轮换
    - 代理服务器支持
    - 请求延迟控制
    - 请求头伪装
    - 会话管理
    - 请求频率限制
    """
    
    # 常用的User-Agent列表 - 更新到最新版本
    DEFAULT_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化反爬虫处理器
        
        Args:
            config: 反爬虫配置
        """
        self.config = config
        self.user_agents = self._init_user_agents()
        self.proxies = self._init_proxies()
        self.current_proxy_index = 0
        self.request_count = 0
        self.last_request_time = 0
        
        # 初始化fake_useragent
        try:
            self.ua = UserAgent()
        except Exception as e:
            logger.warning(f"初始化fake_useragent失败: {e}")
            self.ua = None
    
    def _init_user_agents(self) -> List[str]:
        """初始化User-Agent列表"""
        user_agents = self.DEFAULT_USER_AGENTS.copy()
        
        # 添加自定义User-Agent
        custom_agents = self.config.get('custom_user_agents', [])
        if custom_agents:
            user_agents.extend(custom_agents)
        
        return user_agents
    
    def _init_proxies(self) -> List[str]:
        """初始化代理列表"""
        return self.config.get('proxy_list', [])
    
    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        if self.config.get('use_random_user_agent', True):
            # 优先使用fake_useragent
            if self.ua:
                try:
                    return self.ua.random
                except Exception:
                    pass
            
            # 回退到预定义列表
            return random.choice(self.user_agents)
        else:
            return self.user_agents[0] if self.user_agents else self.DEFAULT_USER_AGENTS[0]
    
    def get_headers(self, url: str = None) -> Dict[str, str]:
        """
        获取请求头
        
        Args:
            url: 目标URL
            
        Returns:
            请求头字典
        """
        headers = self.config.get('default_headers', {}).copy()
        
        # 设置User-Agent
        headers['User-Agent'] = self.get_random_user_agent()
        
        # 添加Referer - 增强版本
        if url and self.config.get('add_referer', True):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            # 对于图片请求，使用更真实的Referer
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                headers['Referer'] = f"{parsed.scheme}://{parsed.netloc}/"
            else:
                headers['Referer'] = f"{parsed.scheme}://{parsed.netloc}/"
        
        # 随机化一些头部
        if self.config.get('randomize_headers', True):
            # 随机Accept-Language
            languages = [
                'zh-CN,zh;q=0.9,en;q=0.8',
                'en-US,en;q=0.9',
                'zh-CN,zh;q=0.8,en;q=0.7',
                'en-GB,en;q=0.9',
            ]
            headers['Accept-Language'] = random.choice(languages)
            
            # 随机DNT
            headers['DNT'] = random.choice(['1', '0'])
        
        return headers
    
    def get_proxy(self) -> Optional[str]:
        """获取代理服务器"""
        if not self.config.get('use_proxy', False) or not self.proxies:
            return None
        
        if self.config.get('proxy_rotation', True):
            # 轮换代理
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            return proxy
        else:
            # 使用第一个代理
            return self.proxies[0]
    
    async def apply_delay(self):
        """应用请求延迟"""
        current_time = asyncio.get_event_loop().time()
        
        if self.last_request_time > 0:
            elapsed = current_time - self.last_request_time
            
            if self.config.get('random_delay', True):
                # 随机延迟
                min_delay = self.config.get('min_delay', 0.5)
                max_delay = self.config.get('max_delay', 3.0)
                delay = random.uniform(min_delay, max_delay)
            else:
                # 固定延迟
                delay = self.config.get('request_delay', 1.0)
            
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"应用请求延迟: {sleep_time:.2f}秒")
                await asyncio.sleep(sleep_time)
        
        self.last_request_time = asyncio.get_event_loop().time()
        self.request_count += 1
    
    async def create_session(self) -> aiohttp.ClientSession:
        """
        创建HTTP会话
        
        Returns:
            配置好的ClientSession
        """
        # 基础连接器配置
        connector_kwargs = {
            'limit': 100,
            'limit_per_host': 10,
            'ttl_dns_cache': 300,
            'use_dns_cache': True,
        }
        
        # 代理配置
        proxy = self.get_proxy()
        if proxy:
            connector_kwargs['proxy'] = proxy
            logger.info(f"使用代理: {proxy}")
        
        connector = aiohttp.TCPConnector(**connector_kwargs)
        
        # 会话配置
        timeout = aiohttp.ClientTimeout(
            total=self.config.get('session_timeout', 300),
            connect=30,
            sock_read=30
        )
        
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.get_headers()
        )
        
        return session
    
    async def make_request(self, session: aiohttp.ClientSession, method: str, 
                          url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        发送HTTP请求
        
        Args:
            session: HTTP会话
            method: 请求方法
            url: 请求URL
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        # 应用延迟
        await self.apply_delay()
        
        # 设置请求头
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        
        # 合并默认头部和自定义头部
        default_headers = self.get_headers(url)
        for key, value in default_headers.items():
            if key not in kwargs['headers']:
                kwargs['headers'][key] = value
        
        # 设置代理（如果会话级别没有设置）
        if 'proxy' not in kwargs:
            proxy = self.get_proxy()
            if proxy:
                kwargs['proxy'] = proxy
        
        logger.debug(f"发送请求: {method} {url}")
        
        try:
            response = await session.request(method, url, **kwargs)
            logger.debug(f"响应状态: {response.status} for {url}")
            return response
        except Exception as e:
            logger.error(f"请求失败: {url} -> {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'request_count': self.request_count,
            'user_agents_count': len(self.user_agents),
            'proxies_count': len(self.proxies),
            'current_proxy_index': self.current_proxy_index,
            'use_proxy': self.config.get('use_proxy', False),
            'use_random_user_agent': self.config.get('use_random_user_agent', True),
            'random_delay': self.config.get('random_delay', True),
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.request_count = 0
        self.last_request_time = 0
