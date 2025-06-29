"""
数据库健康监控器

提供数据库健康检查、性能监控和告警功能
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetrics:
    """健康指标"""
    timestamp: datetime
    response_time: float  # 响应时间（毫秒）
    connection_count: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    query_count: int = 0
    error_count: int = 0
    status: HealthStatus = HealthStatus.UNKNOWN
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric: str  # 监控指标名称
    operator: str  # 比较操作符: >, <, >=, <=, ==, !=
    threshold: float  # 阈值
    duration: int = 60  # 持续时间（秒）
    severity: str = "warning"  # 严重级别: info, warning, critical
    enabled: bool = True
    callback: Optional[Callable] = None


class DatabaseHealthMonitor:
    """
    数据库健康监控器
    
    功能：
    - 实时健康检查
    - 性能指标收集
    - 告警规则管理
    - 历史数据记录
    """
    
    def __init__(self, backup_manager):
        """
        初始化健康监控器
        
        Args:
            backup_manager: 数据库备份管理器实例
        """
        self.backup_manager = backup_manager
        
        # 监控状态
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 健康数据存储
        self.health_history: Dict[str, List[HealthMetrics]] = {}
        self.max_history_size = 1000
        
        # 告警规则
        self.alert_rules: List[AlertRule] = []
        self.active_alerts: Dict[str, datetime] = {}
        
        # 监控配置
        self.check_interval = 30  # 检查间隔（秒）
        self.history_retention_hours = 24  # 历史数据保留时间（小时）
        
        # 初始化默认告警规则
        self._setup_default_alert_rules()
        
        logger.info("数据库健康监控器初始化完成")
    
    def _setup_default_alert_rules(self):
        """设置默认告警规则"""
        default_rules = [
            AlertRule(
                name="响应时间过长",
                metric="response_time",
                operator=">",
                threshold=5000.0,  # 5秒
                severity="warning"
            ),
            AlertRule(
                name="响应时间严重超时",
                metric="response_time",
                operator=">",
                threshold=10000.0,  # 10秒
                severity="critical"
            ),
            AlertRule(
                name="连接数过多",
                metric="connection_count",
                operator=">",
                threshold=100,
                severity="warning"
            ),
            AlertRule(
                name="错误率过高",
                metric="error_count",
                operator=">",
                threshold=10,
                duration=300,  # 5分钟
                severity="critical"
            )
        ]
        
        self.alert_rules.extend(default_rules)
    
    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.alert_rules.append(rule)
        logger.info(f"添加告警规则: {rule.name}")
    
    def remove_alert_rule(self, rule_name: str):
        """移除告警规则"""
        self.alert_rules = [rule for rule in self.alert_rules if rule.name != rule_name]
        logger.info(f"移除告警规则: {rule_name}")
    
    def start_monitoring(self):
        """启动健康监控"""
        if self.is_monitoring:
            logger.warning("健康监控已经在运行")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("数据库健康监控已启动")
    
    def stop_monitoring(self):
        """停止健康监控"""
        self.is_monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("数据库健康监控已停止")
    
    def _monitor_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                # 检查所有数据库
                for db_name in self.backup_manager.databases:
                    metrics = self._collect_health_metrics(db_name)
                    self._store_health_metrics(db_name, metrics)
                    self._check_alert_rules(db_name, metrics)
                
                # 清理历史数据
                self._cleanup_history()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"健康监控异常: {e}")
                time.sleep(self.check_interval)
    
    def _collect_health_metrics(self, db_name: str) -> HealthMetrics:
        """收集数据库健康指标"""
        start_time = time.time()
        metrics = HealthMetrics(
            timestamp=datetime.now(),
            response_time=0.0
        )
        
        try:
            # 测试数据库连接和响应时间
            if db_name in self.backup_manager.engines:
                engine = self.backup_manager.engines[db_name]
                
                with engine.connect() as conn:
                    # 执行简单查询测试响应时间
                    conn.execute(text("SELECT 1"))
                    
                    # 收集数据库特定指标
                    if self.backup_manager.databases[db_name].url.startswith('sqlite'):
                        self._collect_sqlite_metrics(conn, metrics)
                    else:
                        self._collect_postgresql_metrics(conn, metrics)
                
                metrics.status = HealthStatus.HEALTHY
                
        except Exception as e:
            logger.error(f"收集健康指标失败 {db_name}: {e}")
            metrics.status = HealthStatus.CRITICAL
            metrics.details["error"] = str(e)
            metrics.error_count = 1
        
        # 计算响应时间
        metrics.response_time = (time.time() - start_time) * 1000
        
        return metrics
    
    def _collect_sqlite_metrics(self, conn, metrics: HealthMetrics):
        """收集SQLite特定指标"""
        try:
            # 获取数据库大小
            result = conn.execute(text("PRAGMA page_count"))
            page_count = result.scalar()
            
            result = conn.execute(text("PRAGMA page_size"))
            page_size = result.scalar()
            
            if page_count and page_size:
                db_size = page_count * page_size
                metrics.details["database_size"] = db_size
            
            # 获取表数量
            result = conn.execute(text(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ))
            table_count = result.scalar()
            metrics.details["table_count"] = table_count
            
        except Exception as e:
            logger.error(f"收集SQLite指标失败: {e}")
    
    def _collect_postgresql_metrics(self, conn, metrics: HealthMetrics):
        """收集PostgreSQL特定指标"""
        try:
            # 获取连接数
            result = conn.execute(text(
                "SELECT count(*) FROM pg_stat_activity"
            ))
            metrics.connection_count = result.scalar() or 0
            
            # 获取数据库大小
            result = conn.execute(text(
                "SELECT pg_database_size(current_database())"
            ))
            db_size = result.scalar()
            if db_size:
                metrics.details["database_size"] = db_size
            
            # 获取查询统计
            result = conn.execute(text(
                "SELECT sum(calls) FROM pg_stat_user_functions"
            ))
            query_count = result.scalar()
            if query_count:
                metrics.query_count = query_count
                
        except Exception as e:
            logger.error(f"收集PostgreSQL指标失败: {e}")
    
    def _store_health_metrics(self, db_name: str, metrics: HealthMetrics):
        """存储健康指标"""
        if db_name not in self.health_history:
            self.health_history[db_name] = []
        
        self.health_history[db_name].append(metrics)
        
        # 限制历史数据大小
        if len(self.health_history[db_name]) > self.max_history_size:
            self.health_history[db_name] = self.health_history[db_name][-self.max_history_size:]
    
    def _cleanup_history(self):
        """清理过期的历史数据"""
        cutoff_time = datetime.now() - timedelta(hours=self.history_retention_hours)

        for db_name in self.health_history:
            self.health_history[db_name] = [
                metrics for metrics in self.health_history[db_name]
                if metrics.timestamp > cutoff_time
            ]
    
    def _check_alert_rules(self, db_name: str, metrics: HealthMetrics):
        """检查告警规则"""
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            try:
                # 获取指标值
                metric_value = getattr(metrics, rule.metric, None)
                if metric_value is None:
                    metric_value = metrics.details.get(rule.metric)
                
                if metric_value is None:
                    continue
                
                # 检查阈值
                triggered = self._evaluate_condition(metric_value, rule.operator, rule.threshold)
                
                alert_key = f"{db_name}:{rule.name}"
                
                if triggered:
                    if alert_key not in self.active_alerts:
                        self.active_alerts[alert_key] = datetime.now()
                    
                    # 检查持续时间
                    if (datetime.now() - self.active_alerts[alert_key]).total_seconds() >= rule.duration:
                        self._trigger_alert(db_name, rule, metric_value, metrics)
                else:
                    # 清除告警
                    if alert_key in self.active_alerts:
                        del self.active_alerts[alert_key]
                        self._clear_alert(db_name, rule)
                        
            except Exception as e:
                logger.error(f"检查告警规则失败 {rule.name}: {e}")
    
    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """评估条件"""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            return False
    
    def _trigger_alert(self, db_name: str, rule: AlertRule, value: float, metrics: HealthMetrics):
        """触发告警"""
        message = (
            f"数据库告警 [{rule.severity.upper()}] - {db_name}: {rule.name}\n"
            f"指标: {rule.metric} = {value} {rule.operator} {rule.threshold}\n"
            f"时间: {metrics.timestamp}\n"
            f"状态: {metrics.status.value}"
        )
        
        if rule.severity == "critical":
            logger.critical(message)
        elif rule.severity == "warning":
            logger.warning(message)
        else:
            logger.info(message)
        
        # 执行回调函数
        if rule.callback:
            try:
                rule.callback(db_name, rule, value, metrics)
            except Exception as e:
                logger.error(f"执行告警回调失败: {e}")
    
    def _clear_alert(self, db_name: str, rule: AlertRule):
        """清除告警"""
        message = f"数据库告警恢复 - {db_name}: {rule.name}"
        logger.info(message)
    
    def get_health_status(self, db_name: Optional[str] = None) -> Dict[str, Any]:
        """获取健康状态"""
        if db_name:
            # 获取指定数据库状态
            if db_name not in self.health_history or not self.health_history[db_name]:
                return {"status": "unknown", "message": "无健康数据"}
            
            latest_metrics = self.health_history[db_name][-1]
            return {
                "database": db_name,
                "status": latest_metrics.status.value,
                "timestamp": latest_metrics.timestamp.isoformat(),
                "response_time": latest_metrics.response_time,
                "connection_count": latest_metrics.connection_count,
                "details": latest_metrics.details
            }
        else:
            # 获取所有数据库状态
            status = {}
            for db_name in self.backup_manager.databases:
                status[db_name] = self.get_health_status(db_name)
            return status
    
    def get_health_history(self, db_name: str, hours: int = 1) -> List[Dict[str, Any]]:
        """获取健康历史数据"""
        if db_name not in self.health_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        history = [
            {
                "timestamp": metrics.timestamp.isoformat(),
                "status": metrics.status.value,
                "response_time": metrics.response_time,
                "connection_count": metrics.connection_count,
                "error_count": metrics.error_count,
                "details": metrics.details
            }
            for metrics in self.health_history[db_name]
            if metrics.timestamp > cutoff_time
        ]
        
        return history
