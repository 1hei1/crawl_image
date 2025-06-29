"""
重试机制和异常处理装饰器

提供灵活的重试策略和异常处理功能
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Any, Optional, Union, Tuple, Type
import random

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置类"""
    
    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True,
                 backoff_strategy: str = 'exponential'):
        """
        初始化重试配置
        
        Args:
            max_attempts: 最大尝试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            exponential_base: 指数退避的基数
            jitter: 是否添加随机抖动
            backoff_strategy: 退避策略 ('exponential', 'linear', 'fixed')
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.backoff_strategy = backoff_strategy
    
    def calculate_delay(self, attempt: int) -> float:
        """
        计算延迟时间
        
        Args:
            attempt: 当前尝试次数（从0开始）
            
        Returns:
            延迟时间（秒）
        """
        if self.backoff_strategy == 'exponential':
            delay = self.base_delay * (self.exponential_base ** attempt)
        elif self.backoff_strategy == 'linear':
            delay = self.base_delay * (attempt + 1)
        else:  # fixed
            delay = self.base_delay
        
        # 限制最大延迟
        delay = min(delay, self.max_delay)
        
        # 添加随机抖动
        if self.jitter:
            jitter_range = delay * 0.1  # 10%的抖动
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


def retry_on_exception(
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None,
    on_failure: Optional[Callable] = None
):
    """
    重试装饰器（同步版本）
    
    Args:
        exceptions: 需要重试的异常类型
        config: 重试配置
        on_retry: 重试时的回调函数
        on_failure: 最终失败时的回调函数
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        # 最后一次尝试失败
                        if on_failure:
                            on_failure(e, attempt + 1)
                        logger.error(f"函数 {func.__name__} 在 {config.max_attempts} 次尝试后最终失败: {e}")
                        raise e
                    
                    # 计算延迟时间
                    delay = config.calculate_delay(attempt)
                    
                    # 调用重试回调
                    if on_retry:
                        on_retry(e, attempt + 1, delay)
                    
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{delay:.2f}秒后重试")
                    
                    # 等待后重试
                    time.sleep(delay)
            
            # 理论上不会到达这里
            raise last_exception
        
        return wrapper
    return decorator


def async_retry_on_exception(
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None,
    on_failure: Optional[Callable] = None
):
    """
    异步重试装饰器
    
    Args:
        exceptions: 需要重试的异常类型
        config: 重试配置
        on_retry: 重试时的回调函数
        on_failure: 最终失败时的回调函数
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        # 最后一次尝试失败
                        if on_failure:
                            if asyncio.iscoroutinefunction(on_failure):
                                await on_failure(e, attempt + 1)
                            else:
                                on_failure(e, attempt + 1)
                        logger.error(f"异步函数 {func.__name__} 在 {config.max_attempts} 次尝试后最终失败: {e}")
                        raise e
                    
                    # 计算延迟时间
                    delay = config.calculate_delay(attempt)
                    
                    # 调用重试回调
                    if on_retry:
                        if asyncio.iscoroutinefunction(on_retry):
                            await on_retry(e, attempt + 1, delay)
                        else:
                            on_retry(e, attempt + 1, delay)
                    
                    logger.warning(f"异步函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{delay:.2f}秒后重试")
                    
                    # 异步等待后重试
                    await asyncio.sleep(delay)
            
            # 理论上不会到达这里
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    熔断器
    
    当错误率过高时暂时停止调用，避免系统雪崩
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败阈值
            recovery_timeout: 恢复超时时间（秒）
            expected_exception: 预期的异常类型
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        """装饰器调用"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self._call(func, *args, **kwargs)
        return wrapper
    
    def _call(self, func: Callable, *args, **kwargs):
        """执行函数调用"""
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise Exception(f"熔断器开启，函数 {func.__name__} 暂时不可用")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置"""
        return (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.recovery_timeout)
    
    def _on_success(self):
        """成功时的处理"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"熔断器开启，失败次数: {self.failure_count}")


class AsyncCircuitBreaker(CircuitBreaker):
    """异步熔断器"""
    
    def __call__(self, func: Callable) -> Callable:
        """装饰器调用"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await self._call(func, *args, **kwargs)
        return wrapper
    
    async def _call(self, func: Callable, *args, **kwargs):
        """执行异步函数调用"""
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise Exception(f"熔断器开启，异步函数 {func.__name__} 暂时不可用")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e


def timeout(seconds: float):
    """
    超时装饰器（同步版本）
    
    Args:
        seconds: 超时时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"函数 {func.__name__} 执行超时 ({seconds}秒)")
            
            # 设置信号处理器
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # 恢复原来的信号处理器
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    return decorator


def async_timeout(seconds: float):
    """
    异步超时装饰器
    
    Args:
        seconds: 超时时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"异步函数 {func.__name__} 执行超时 ({seconds}秒)")
        
        return wrapper
    return decorator


# 预定义的重试配置
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    backoff_strategy='exponential'
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=5.0,
    exponential_base=1.5,
    jitter=True,
    backoff_strategy='exponential'
)

FILE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=False,
    backoff_strategy='linear'
)
