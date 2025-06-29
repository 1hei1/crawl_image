"""
增强的数据库管理器

集成容灾备份功能的数据库管理器
"""

import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from database.manager import DatabaseManager
from database.backup_manager import (
    DatabaseBackupManager, DatabaseConfig, BackupConfig, FailoverConfig
)
from database.health_monitor import DatabaseHealthMonitor
from database.failover_manager import DatabaseFailoverManager
from config.settings import DisasterRecoveryConfig

logger = logging.getLogger(__name__)


class EnhancedDatabaseManager:
    """
    增强的数据库管理器
    
    集成了以下功能：
    - 基础数据库操作（继承自DatabaseManager）
    - 容灾备份管理
    - 健康监控
    - 自动故障转移
    """
    
    def __init__(self, database_url: str, disaster_recovery_config: Optional[DisasterRecoveryConfig] = None, ha_manager=None):
        """
        初始化增强数据库管理器

        Args:
            database_url: 主数据库连接URL
            disaster_recovery_config: 容灾备份配置
            ha_manager: 高可用管理器实例
        """
        # 初始化基础数据库管理器
        self.base_manager = DatabaseManager(database_url)

        # 容灾备份相关组件
        self.backup_manager: Optional[DatabaseBackupManager] = None
        self.health_monitor: Optional[DatabaseHealthMonitor] = None
        self.failover_manager: Optional[DatabaseFailoverManager] = None

        # 高可用管理器
        self.ha_manager = ha_manager

        # 容灾配置
        self.disaster_recovery_config = disaster_recovery_config

        # 如果启用了容灾备份，初始化相关组件
        if disaster_recovery_config and disaster_recovery_config.enabled:
            self._initialize_disaster_recovery()

        logger.info("增强数据库管理器初始化完成")
    
    def _initialize_disaster_recovery(self):
        """初始化容灾备份功能"""
        try:
            config = self.disaster_recovery_config
            
            # 构建数据库配置列表
            databases = []
            for db_name, db_config in config.databases.items():
                if db_config.enabled:
                    databases.append(DatabaseConfig(
                        name=db_config.name,
                        type=db_config.type,
                        url=db_config.url,
                        priority=db_config.priority
                    ))
            
            if not databases:
                logger.warning("没有配置可用的数据库实例")
                return
            
            # 构建备份配置
            backup_config = BackupConfig(
                backup_dir=config.backup.backup_dir,
                max_backups=config.backup.max_backups,
                backup_interval=config.backup.backup_interval,
                enable_auto_backup=config.backup.enable_auto_backup,
                enable_compression=config.backup.enable_compression,
                backup_format=config.backup.backup_format,
                retention_days=config.backup.retention_days
            )
            
            # 构建故障转移配置
            failover_config = FailoverConfig(
                enable_auto_failover=config.failover.enable_auto_failover,
                health_check_interval=config.failover.health_check_interval,
                max_retry_attempts=config.failover.max_retry_attempts,
                retry_delay=config.failover.retry_delay,
                failover_timeout=config.failover.failover_timeout,
                notification_enabled=config.failover.notification_enabled
            )
            
            # 初始化备份管理器
            self.backup_manager = DatabaseBackupManager(
                databases, backup_config, failover_config
            )
            
            # 初始化健康监控器
            if config.monitoring.enable_health_monitoring:
                self.health_monitor = DatabaseHealthMonitor(self.backup_manager)
                self.health_monitor.check_interval = config.monitoring.check_interval
                self.health_monitor.history_retention_hours = config.monitoring.history_retention_hours
                self.health_monitor.max_history_size = config.monitoring.max_history_size
                
                # 添加告警规则
                for rule_name, rule_config in config.monitoring.alert_rules.items():
                    if rule_config.enabled:
                        from database.health_monitor import AlertRule
                        alert_rule = AlertRule(
                            name=rule_name,
                            metric=rule_config.metric,
                            operator=rule_config.operator,
                            threshold=rule_config.threshold,
                            severity=rule_config.severity,
                            duration=rule_config.duration
                        )
                        self.health_monitor.add_alert_rule(alert_rule)
            
            # 初始化故障转移管理器
            if config.failover.enable_auto_failover and self.health_monitor:
                self.failover_manager = DatabaseFailoverManager(
                    self.backup_manager, self.health_monitor
                )
                self.failover_manager.detection_threshold = config.failover.detection_threshold
            
            logger.info("容灾备份功能初始化完成")
            
        except Exception as e:
            logger.error(f"容灾备份功能初始化失败: {e}")
            # 即使容灾功能初始化失败，也要保证基础功能可用
            self.backup_manager = None
            self.health_monitor = None
            self.failover_manager = None
    
    def start_monitoring(self):
        """启动监控服务"""
        if self.backup_manager:
            self.backup_manager.start_monitoring()
        
        if self.health_monitor:
            self.health_monitor.start_monitoring()
        
        if self.failover_manager:
            self.failover_manager.start_monitoring()
        
        logger.info("数据库监控服务已启动")
    
    def stop_monitoring(self):
        """停止监控服务"""
        if self.backup_manager:
            self.backup_manager.stop_monitoring()
        
        if self.health_monitor:
            self.health_monitor.stop_monitoring()
        
        if self.failover_manager:
            self.failover_manager.stop_monitoring()
        
        logger.info("数据库监控服务已停止")
    
    # 代理基础数据库管理器的方法
    def create_tables(self):
        """创建数据库表"""
        if self.backup_manager:
            # 使用容灾管理器的当前主数据库
            engine = self.backup_manager.get_current_engine()
            from database.models.base import Base
            Base.metadata.create_all(bind=engine)
            logger.info("数据库表创建成功")
        else:
            # 使用基础管理器
            self.base_manager.create_tables()
    
    def drop_tables(self):
        """删除数据库表"""
        if self.backup_manager:
            engine = self.backup_manager.get_current_engine()
            from database.models.base import Base
            Base.metadata.drop_all(bind=engine)
            logger.info("数据库表删除成功")
        else:
            self.base_manager.drop_tables()
    
    @contextmanager
    def get_session(self):
        """获取数据库会话"""
        # 优先使用HA管理器
        if self.ha_manager:
            with self.ha_manager.get_session() as session:
                yield session
        elif self.backup_manager:
            with self.backup_manager.get_session() as session:
                yield session
        else:
            with self.base_manager.get_session() as session:
                yield session
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        if self.backup_manager:
            return self.backup_manager._test_database_connection(
                self.backup_manager.current_primary
            )
        else:
            return self.base_manager.test_connection()
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        if self.backup_manager:
            info = self.backup_manager.get_database_status()
            
            # 添加容灾相关信息
            info["disaster_recovery"] = {
                "enabled": True,
                "current_primary": self.backup_manager.current_primary,
                "backup_enabled": self.backup_manager.backup_config.enable_auto_backup,
                "monitoring_enabled": self.health_monitor is not None,
                "failover_enabled": self.failover_manager is not None
            }
            
            return info
        else:
            info = self.base_manager.get_database_info()
            info["disaster_recovery"] = {"enabled": False}
            return info
    
    # 容灾备份相关方法
    def create_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """创建数据库备份"""
        if self.backup_manager:
            try:
                return self.backup_manager.create_backup(backup_name=backup_name)
            except Exception as e:
                logger.error(f"创建备份失败: {e}")
                return None
        else:
            logger.warning("容灾备份功能未启用")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """恢复数据库备份"""
        if self.backup_manager:
            try:
                return self.backup_manager.restore_backup(backup_path)
            except Exception as e:
                logger.error(f"恢复备份失败: {e}")
                return False
        else:
            logger.warning("容灾备份功能未启用")
            return False
    
    def manual_failover(self, target_db: str, reason: str = "手动故障转移") -> bool:
        """手动故障转移"""
        if self.failover_manager:
            try:
                return self.failover_manager.manual_failover(target_db, reason)
            except Exception as e:
                logger.error(f"手动故障转移失败: {e}")
                return False
        else:
            logger.warning("故障转移功能未启用")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        if self.health_monitor:
            return self.health_monitor.get_health_status()
        else:
            return {"status": "unknown", "message": "健康监控未启用"}
    
    def get_failover_status(self) -> Dict[str, Any]:
        """获取故障转移状态"""
        if self.failover_manager:
            return self.failover_manager.get_failover_status()
        else:
            return {"enabled": False, "message": "故障转移功能未启用"}
    
    def get_failover_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取故障转移历史"""
        if self.failover_manager:
            return self.failover_manager.get_failover_history(limit)
        else:
            return []
    
    def enable_auto_failover(self):
        """启用自动故障转移"""
        if self.failover_manager:
            self.failover_manager.enable_auto_failover()
        else:
            logger.warning("故障转移功能未启用")
    
    def disable_auto_failover(self):
        """禁用自动故障转移"""
        if self.failover_manager:
            self.failover_manager.disable_auto_failover()
        else:
            logger.warning("故障转移功能未启用")
    
    def is_disaster_recovery_enabled(self) -> bool:
        """检查是否启用了容灾备份功能"""
        return self.backup_manager is not None
