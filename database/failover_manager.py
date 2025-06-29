"""
数据库故障转移管理器

提供自动故障检测和数据库切换功能
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FailoverStatus(Enum):
    """故障转移状态"""
    NORMAL = "normal"
    DETECTING = "detecting"
    SWITCHING = "switching"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class FailoverEvent:
    """故障转移事件"""
    timestamp: datetime
    source_db: str
    target_db: str
    reason: str
    status: FailoverStatus
    duration: float = 0.0
    error_message: Optional[str] = None


class DatabaseFailoverManager:
    """
    数据库故障转移管理器
    
    功能：
    - 自动故障检测
    - 智能数据库选择
    - 平滑切换
    - 故障恢复
    - 事件记录
    """
    
    def __init__(self, backup_manager, health_monitor):
        """
        初始化故障转移管理器
        
        Args:
            backup_manager: 数据库备份管理器
            health_monitor: 健康监控器
        """
        self.backup_manager = backup_manager
        self.health_monitor = health_monitor
        
        # 故障转移配置
        self.auto_failover_enabled = True
        self.max_retry_attempts = 3
        self.retry_delay = 5  # 秒
        self.failover_timeout = 60  # 秒
        self.detection_threshold = 3  # 连续失败次数
        
        # 状态管理
        self.current_status = FailoverStatus.NORMAL
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 故障计数器
        self.failure_counts: Dict[str, int] = {}
        self.last_check_times: Dict[str, datetime] = {}
        
        # 事件历史
        self.failover_history: List[FailoverEvent] = []
        self.max_history_size = 100
        
        # 回调函数
        self.on_failover_start: Optional[Callable] = None
        self.on_failover_complete: Optional[Callable] = None
        self.on_failover_failed: Optional[Callable] = None
        
        logger.info("数据库故障转移管理器初始化完成")
    
    def start_monitoring(self):
        """启动故障转移监控"""
        if self.is_monitoring:
            logger.warning("故障转移监控已经在运行")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("故障转移监控已启动")
    
    def stop_monitoring(self):
        """停止故障转移监控"""
        self.is_monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("故障转移监控已停止")
    
    def _monitor_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                if self.auto_failover_enabled and self.current_status == FailoverStatus.NORMAL:
                    self._check_primary_database()
                
                time.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"故障转移监控异常: {e}")
                time.sleep(10)
    
    def _check_primary_database(self):
        """检查主数据库状态"""
        if not self.backup_manager.current_primary:
            return
        
        primary_db = self.backup_manager.current_primary
        
        # 测试数据库连接
        is_healthy = self.backup_manager._test_database_connection(primary_db)
        
        if is_healthy:
            # 重置失败计数
            self.failure_counts[primary_db] = 0
        else:
            # 增加失败计数
            self.failure_counts[primary_db] = self.failure_counts.get(primary_db, 0) + 1
            
            logger.warning(f"主数据库连接失败 {primary_db}: {self.failure_counts[primary_db]}/{self.detection_threshold}")
            
            # 检查是否达到故障转移阈值
            if self.failure_counts[primary_db] >= self.detection_threshold:
                self._trigger_automatic_failover(primary_db, "连续连接失败")
    
    def _trigger_automatic_failover(self, failed_db: str, reason: str):
        """触发自动故障转移"""
        if self.current_status != FailoverStatus.NORMAL:
            logger.warning("故障转移正在进行中，跳过新的故障转移请求")
            return
        
        logger.critical(f"触发自动故障转移: {failed_db} - {reason}")
        
        # 选择目标数据库
        target_db = self._select_failover_target(failed_db)
        
        if target_db:
            self.execute_failover(failed_db, target_db, reason, auto=True)
        else:
            logger.critical("没有可用的目标数据库进行故障转移")
            self._record_failover_event(
                failed_db, "", reason, FailoverStatus.FAILED,
                error_message="没有可用的目标数据库"
            )
    
    def _select_failover_target(self, failed_db: str) -> Optional[str]:
        """选择故障转移目标数据库"""
        # 获取所有可用的数据库（除了失败的数据库）
        available_dbs = []
        
        for db_name, config in self.backup_manager.databases.items():
            if (db_name != failed_db and 
                config.is_active and 
                self.backup_manager._test_database_connection(db_name)):
                available_dbs.append((db_name, config))
        
        if not available_dbs:
            return None
        
        # 按优先级排序
        available_dbs.sort(key=lambda x: x[1].priority)
        
        # 选择优先级最高的数据库
        return available_dbs[0][0]
    
    def execute_failover(self, source_db: str, target_db: str, reason: str, auto: bool = False) -> bool:
        """
        执行故障转移
        
        Args:
            source_db: 源数据库
            target_db: 目标数据库
            reason: 故障转移原因
            auto: 是否为自动故障转移
            
        Returns:
            是否成功
        """
        start_time = time.time()
        self.current_status = FailoverStatus.DETECTING
        
        try:
            logger.info(f"开始故障转移: {source_db} -> {target_db} ({reason})")
            
            # 执行回调
            if self.on_failover_start:
                self.on_failover_start(source_db, target_db, reason)
            
            # 验证目标数据库
            if not self._validate_target_database(target_db):
                raise RuntimeError(f"目标数据库验证失败: {target_db}")
            
            self.current_status = FailoverStatus.SWITCHING
            
            # 执行数据同步（无论是否自动故障转移都尝试同步）
            if source_db != target_db:
                logger.info("尝试同步数据到目标数据库")
                try:
                    # 如果源数据库还能连接，尝试同步最新数据
                    if self.backup_manager._test_database_connection(source_db):
                        sync_success = self.backup_manager.sync_databases(source_db, target_db)
                        if sync_success:
                            logger.info(f"数据同步成功: {source_db} -> {target_db}")
                        else:
                            logger.warning(f"数据同步失败，但继续故障转移")
                    else:
                        logger.warning(f"源数据库 {source_db} 连接失败，跳过数据同步")
                except Exception as e:
                    logger.warning(f"数据同步失败，继续故障转移: {e}")
            
            # 执行数据库切换
            success = self.backup_manager.failover_to_database(target_db)
            
            if success:
                self.current_status = FailoverStatus.COMPLETED
                duration = time.time() - start_time
                
                logger.info(f"故障转移成功完成: {source_db} -> {target_db} (耗时: {duration:.2f}秒)")
                
                # 记录事件
                self._record_failover_event(
                    source_db, target_db, reason, FailoverStatus.COMPLETED, duration
                )
                
                # 执行回调
                if self.on_failover_complete:
                    self.on_failover_complete(source_db, target_db, reason, duration)
                
                # 重置失败计数
                self.failure_counts.clear()
                
                return True
            else:
                raise RuntimeError("数据库切换失败")
                
        except Exception as e:
            self.current_status = FailoverStatus.FAILED
            duration = time.time() - start_time
            error_msg = str(e)
            
            logger.error(f"故障转移失败: {source_db} -> {target_db} - {error_msg}")
            
            # 记录事件
            self._record_failover_event(
                source_db, target_db, reason, FailoverStatus.FAILED, 
                duration, error_msg
            )
            
            # 执行回调
            if self.on_failover_failed:
                self.on_failover_failed(source_db, target_db, reason, error_msg)
            
            return False
        
        finally:
            # 恢复正常状态
            if self.current_status in [FailoverStatus.COMPLETED, FailoverStatus.FAILED]:
                self.current_status = FailoverStatus.NORMAL
    
    def _validate_target_database(self, target_db: str) -> bool:
        """验证目标数据库"""
        try:
            # 检查数据库是否存在
            if target_db not in self.backup_manager.databases:
                logger.error(f"目标数据库不存在: {target_db}")
                return False

            # 检查数据库连接
            if not self.backup_manager._test_database_connection(target_db):
                logger.error(f"目标数据库连接失败: {target_db}")
                return False

            # 检查并创建数据库表结构
            engine = self.backup_manager.engines[target_db]
            try:
                from sqlalchemy import inspect
                inspector = inspect(engine)
                tables = inspector.get_table_names()

                required_tables = ['images', 'categories', 'crawl_sessions', 'tags']
                missing_tables = [table for table in required_tables if table not in tables]

                if missing_tables:
                    logger.info(f"目标数据库缺少表: {missing_tables}，正在创建...")

                    # 创建缺少的表
                    from database.models.base import Base
                    Base.metadata.create_all(bind=engine)

                    logger.info(f"已在目标数据库 {target_db} 中创建缺少的表")

                    # 重新检查表是否创建成功
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    still_missing = [table for table in required_tables if table not in tables]

                    if still_missing:
                        logger.error(f"表创建失败，仍缺少: {still_missing}")
                        return False

                    logger.info("所有必要的表已创建完成")

            except Exception as e:
                logger.error(f"检查/创建表结构失败: {e}")
                return False

            return True

        except Exception as e:
            logger.error(f"验证目标数据库失败 {target_db}: {e}")
            return False
    
    def _record_failover_event(self, source_db: str, target_db: str, reason: str, 
                              status: FailoverStatus, duration: float = 0.0, 
                              error_message: Optional[str] = None):
        """记录故障转移事件"""
        event = FailoverEvent(
            timestamp=datetime.now(),
            source_db=source_db,
            target_db=target_db,
            reason=reason,
            status=status,
            duration=duration,
            error_message=error_message
        )
        
        self.failover_history.append(event)
        
        # 限制历史记录大小
        if len(self.failover_history) > self.max_history_size:
            self.failover_history = self.failover_history[-self.max_history_size:]
    
    def manual_failover(self, target_db: str, reason: str = "手动故障转移") -> bool:
        """
        手动故障转移
        
        Args:
            target_db: 目标数据库
            reason: 故障转移原因
            
        Returns:
            是否成功
        """
        current_primary = self.backup_manager.current_primary
        if not current_primary:
            logger.error("没有当前主数据库")
            return False
        
        if current_primary == target_db:
            logger.warning(f"目标数据库已经是当前主数据库: {target_db}")
            return True
        
        return self.execute_failover(current_primary, target_db, reason, auto=False)
    
    def get_failover_status(self) -> Dict[str, Any]:
        """获取故障转移状态"""
        return {
            "current_status": self.current_status.value,
            "auto_failover_enabled": self.auto_failover_enabled,
            "current_primary": self.backup_manager.current_primary,
            "failure_counts": self.failure_counts.copy(),
            "is_monitoring": self.is_monitoring,
            "detection_threshold": self.detection_threshold
        }
    
    def get_failover_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取故障转移历史"""
        history = self.failover_history[-limit:] if limit > 0 else self.failover_history
        
        return [
            {
                "timestamp": event.timestamp.isoformat(),
                "source_db": event.source_db,
                "target_db": event.target_db,
                "reason": event.reason,
                "status": event.status.value,
                "duration": event.duration,
                "error_message": event.error_message
            }
            for event in reversed(history)
        ]
    
    def enable_auto_failover(self):
        """启用自动故障转移"""
        self.auto_failover_enabled = True
        logger.info("自动故障转移已启用")
    
    def disable_auto_failover(self):
        """禁用自动故障转移"""
        self.auto_failover_enabled = False
        logger.info("自动故障转移已禁用")
    
    def set_detection_threshold(self, threshold: int):
        """设置故障检测阈值"""
        self.detection_threshold = max(1, threshold)
        logger.info(f"故障检测阈值设置为: {self.detection_threshold}")
    
    def reset_failure_counts(self):
        """重置失败计数"""
        self.failure_counts.clear()
        logger.info("失败计数已重置")
