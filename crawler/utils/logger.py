"""
日志系统

提供统一的日志记录和管理功能
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
import json
from datetime import datetime


class LoggerManager:
    """
    日志管理器
    
    功能：
    - 统一日志配置
    - 多种输出格式
    - 日志轮转
    - 性能监控
    - 错误追踪
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化日志管理器
        
        Args:
            config: 日志配置
        """
        self.config = config
        self.log_level = config.get('level', 'INFO')
        self.log_file = config.get('log_file', 'logs/crawler.log')
        self.max_file_size = config.get('max_file_size', '10MB')
        self.backup_count = config.get('backup_count', 5)
        self.console_output = config.get('console_output', True)
        self.verbose = config.get('verbose', False)
        self.format_string = config.get('format', 
            "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}")
        
        self._setup_logger()
    
    def _setup_logger(self):
        """设置日志器"""
        # 移除默认处理器
        logger.remove()
        
        # 确保日志目录存在
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 添加文件处理器
        logger.add(
            self.log_file,
            level=self.log_level,
            format=self.format_string,
            rotation=self.max_file_size,
            retention=self.backup_count,
            compression="zip",
            encoding="utf-8",
            enqueue=True,  # 异步写入
            backtrace=True,
            diagnose=True
        )
        
        # 添加控制台处理器
        if self.console_output:
            console_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
            
            logger.add(
                sys.stdout,
                level=self.log_level,
                format=console_format,
                colorize=True,
                backtrace=True,
                diagnose=True
            )
        
        # 添加错误文件处理器
        error_log_file = str(log_path.parent / f"{log_path.stem}_error{log_path.suffix}")
        logger.add(
            error_log_file,
            level="ERROR",
            format=self.format_string,
            rotation=self.max_file_size,
            retention=self.backup_count,
            compression="zip",
            encoding="utf-8",
            enqueue=True
        )
        
        # 设置第三方库日志级别
        self._configure_third_party_loggers()
        
        logger.info("日志系统初始化完成")
    
    def _configure_third_party_loggers(self):
        """配置第三方库的日志级别"""
        # 设置常见第三方库的日志级别
        third_party_loggers = [
            'aiohttp',
            'urllib3',
            'requests',
            'PIL',
            'sqlalchemy',
            'asyncio',
        ]
        
        for logger_name in third_party_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
        
        # 如果是详细模式，降低日志级别
        if self.verbose:
            for logger_name in third_party_loggers:
                logging.getLogger(logger_name).setLevel(logging.INFO)
    
    def get_logger(self, name: str = None):
        """获取日志器实例"""
        if name:
            return logger.bind(name=name)
        return logger
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """记录性能日志"""
        perf_data = {
            'operation': operation,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }
        
        logger.info(f"PERFORMANCE: {operation} took {duration:.3f}s", extra=perf_data)
    
    def log_error_with_context(self, error: Exception, context: Dict[str, Any] = None):
        """记录带上下文的错误"""
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        
        logger.error(f"ERROR: {error_data['error_type']}: {error_data['error_message']}", 
                    extra=error_data)
    
    def log_crawl_progress(self, stats: Dict[str, Any]):
        """记录爬取进度"""
        progress_msg = (
            f"PROGRESS: Pages: {stats.get('pages_crawled', 0)}, "
            f"Images: {stats.get('images_found', 0)}, "
            f"Downloaded: {stats.get('images_downloaded', 0)}, "
            f"Failed: {stats.get('images_failed', 0)}"
        )
        
        logger.info(progress_msg, extra={'stats': stats})


class ErrorHandler:
    """
    错误处理器
    
    功能：
    - 统一错误处理
    - 错误分类和统计
    - 自动重试机制
    - 错误恢复策略
    """
    
    def __init__(self, logger_manager: LoggerManager):
        """
        初始化错误处理器
        
        Args:
            logger_manager: 日志管理器
        """
        self.logger = logger_manager.get_logger("ErrorHandler")
        self.error_stats = {
            'network_errors': 0,
            'parsing_errors': 0,
            'file_errors': 0,
            'database_errors': 0,
            'unknown_errors': 0,
            'total_errors': 0,
        }
        self.retry_counts = {}
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None, 
                    operation: str = None) -> Dict[str, Any]:
        """
        处理错误
        
        Args:
            error: 异常对象
            context: 错误上下文
            operation: 操作名称
            
        Returns:
            错误处理结果
        """
        error_type = self._classify_error(error)
        self.error_stats[error_type] += 1
        self.error_stats['total_errors'] += 1
        
        error_info = {
            'error_type': error_type,
            'error_class': type(error).__name__,
            'error_message': str(error),
            'operation': operation,
            'context': context or {},
            'should_retry': self._should_retry(error, context),
            'retry_delay': self._get_retry_delay(error, context),
            'recovery_action': self._get_recovery_action(error, context)
        }
        
        # 记录错误
        self.logger.error(
            f"错误处理: {error_info['error_class']} in {operation or 'unknown'}: {error_info['error_message']}",
            extra=error_info
        )
        
        return error_info
    
    def _classify_error(self, error: Exception) -> str:
        """分类错误类型"""
        import aiohttp
        import asyncio
        from sqlalchemy.exc import SQLAlchemyError
        
        if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError)):
            return 'network_errors'
        elif isinstance(error, (ValueError, TypeError, AttributeError)):
            return 'parsing_errors'
        elif isinstance(error, (FileNotFoundError, PermissionError, OSError)):
            return 'file_errors'
        elif isinstance(error, SQLAlchemyError):
            return 'database_errors'
        else:
            return 'unknown_errors'
    
    def _should_retry(self, error: Exception, context: Dict[str, Any] = None) -> bool:
        """判断是否应该重试"""
        import aiohttp
        import asyncio
        
        # 网络相关错误通常可以重试
        if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError)):
            return True
        
        # 临时文件错误可以重试
        if isinstance(error, (PermissionError, OSError)) and "temporarily" in str(error).lower():
            return True
        
        # 其他错误通常不重试
        return False
    
    def _get_retry_delay(self, error: Exception, context: Dict[str, Any] = None) -> float:
        """获取重试延迟时间"""
        operation = context.get('operation', 'unknown') if context else 'unknown'
        retry_count = self.retry_counts.get(operation, 0)
        
        # 指数退避，最大60秒
        delay = min(2 ** retry_count, 60)
        
        # 网络错误使用较短延迟
        import aiohttp
        import asyncio
        if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError)):
            delay = min(delay, 10)
        
        return delay
    
    def _get_recovery_action(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """获取恢复操作建议"""
        import aiohttp
        import asyncio
        from sqlalchemy.exc import SQLAlchemyError
        
        if isinstance(error, asyncio.TimeoutError):
            return "增加超时时间或检查网络连接"
        elif isinstance(error, aiohttp.ClientError):
            return "检查目标网站状态或更换代理"
        elif isinstance(error, SQLAlchemyError):
            return "检查数据库连接或重启数据库服务"
        elif isinstance(error, FileNotFoundError):
            return "检查文件路径或创建必要的目录"
        elif isinstance(error, PermissionError):
            return "检查文件权限或以管理员身份运行"
        else:
            return "查看详细错误信息并手动处理"
    
    def increment_retry_count(self, operation: str):
        """增加重试计数"""
        self.retry_counts[operation] = self.retry_counts.get(operation, 0) + 1
    
    def reset_retry_count(self, operation: str):
        """重置重试计数"""
        self.retry_counts.pop(operation, None)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            **self.error_stats,
            'retry_counts': dict(self.retry_counts),
            'error_rate': {
                error_type: count / max(self.error_stats['total_errors'], 1) * 100
                for error_type, count in self.error_stats.items()
                if error_type != 'total_errors'
            }
        }


class PerformanceMonitor:
    """
    性能监控器
    
    功能：
    - 操作耗时监控
    - 资源使用监控
    - 性能瓶颈识别
    - 性能报告生成
    """
    
    def __init__(self, logger_manager: LoggerManager):
        """
        初始化性能监控器
        
        Args:
            logger_manager: 日志管理器
        """
        self.logger = logger_manager.get_logger("PerformanceMonitor")
        self.operation_times = {}
        self.resource_usage = {}
    
    def start_operation(self, operation: str) -> str:
        """开始监控操作"""
        import time
        import uuid
        
        operation_id = f"{operation}_{uuid.uuid4().hex[:8]}"
        self.operation_times[operation_id] = {
            'operation': operation,
            'start_time': time.time(),
            'end_time': None,
            'duration': None
        }
        
        return operation_id
    
    def end_operation(self, operation_id: str, **kwargs):
        """结束监控操作"""
        import time
        
        if operation_id in self.operation_times:
            op_info = self.operation_times[operation_id]
            op_info['end_time'] = time.time()
            op_info['duration'] = op_info['end_time'] - op_info['start_time']
            op_info.update(kwargs)
            
            # 记录性能日志
            self.logger.info(
                f"PERFORMANCE: {op_info['operation']} completed in {op_info['duration']:.3f}s",
                extra=op_info
            )
            
            # 清理已完成的操作
            del self.operation_times[operation_id]
    
    def monitor_resource_usage(self):
        """监控资源使用情况"""
        import psutil
        import os
        
        try:
            process = psutil.Process(os.getpid())
            
            self.resource_usage = {
                'cpu_percent': process.cpu_percent(),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'memory_percent': process.memory_percent(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections()),
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.debug(
                f"RESOURCE: CPU: {self.resource_usage['cpu_percent']:.1f}%, "
                f"Memory: {self.resource_usage['memory_mb']:.1f}MB",
                extra={'resource_usage': self.resource_usage}
            )
            
        except Exception as e:
            self.logger.warning(f"资源监控失败: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        return {
            'active_operations': len(self.operation_times),
            'current_resource_usage': self.resource_usage,
            'active_operation_list': list(self.operation_times.keys())
        }
