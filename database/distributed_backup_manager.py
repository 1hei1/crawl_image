"""
分布式容灾备份管理器

适用于多服务器环境的真正容灾备份系统
支持PostgreSQL主从复制、逻辑复制等
"""

import logging
import time
import threading
import psycopg2
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class ReplicationStatus(Enum):
    """复制状态"""
    HEALTHY = "healthy"
    LAGGING = "lagging"
    BROKEN = "broken"
    UNKNOWN = "unknown"


@dataclass
class ServerInfo:
    """服务器信息"""
    location: str
    ip: str
    region: str = ""
    description: str = ""


@dataclass
class ReplicationConfig:
    """复制配置"""
    source: str = ""
    mode: str = "async"  # sync, async
    lag_monitoring: bool = True


@dataclass
class DistributedDatabaseConfig:
    """分布式数据库配置"""
    name: str
    type: str  # 'primary' or 'secondary'
    priority: int
    host: str
    port: int
    database: str
    username: str
    password: str
    url: str
    server_info: ServerInfo
    replication: Optional[ReplicationConfig] = None
    is_active: bool = True
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    replication_lag: float = 0.0  # 复制延迟（秒）


class DistributedBackupManager:
    """
    分布式容灾备份管理器
    
    功能：
    - PostgreSQL主从复制管理
    - 跨服务器数据同步
    - 智能故障转移
    - 复制延迟监控
    - 分布式备份策略
    """
    
    def __init__(self, databases: List[DistributedDatabaseConfig]):
        """
        初始化分布式备份管理器
        
        Args:
            databases: 分布式数据库配置列表
        """
        self.databases = {db.name: db for db in databases}
        
        # 当前活跃的数据库
        self.current_primary: Optional[str] = None
        self.engines: Dict[str, Engine] = {}
        self.session_makers: Dict[str, sessionmaker] = {}
        
        # 复制监控
        self.replication_status: Dict[str, ReplicationStatus] = {}
        self.replication_lag: Dict[str, float] = {}
        
        # 监控线程
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 状态锁
        self._lock = threading.Lock()
        
        # 初始化
        self._initialize_engines()
        self._select_primary_database()
        self._setup_replication_monitoring()
        
        logger.info("分布式容灾备份管理器初始化完成")
    
    def _initialize_engines(self):
        """初始化数据库引擎"""
        for name, config in self.databases.items():
            try:
                engine = create_engine(
                    config.url,
                    echo=False,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args={
                        "connect_timeout": 10,
                        "application_name": f"crawler_{name}"
                    }
                )
                
                self.engines[name] = engine
                self.session_makers[name] = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=engine
                )
                
                logger.info(f"数据库引擎初始化成功: {name} ({config.server_info.location})")
                
            except Exception as e:
                logger.error(f"数据库引擎初始化失败 {name}: {e}")
                config.is_active = False
                config.last_error = str(e)
    
    def _select_primary_database(self):
        """选择主数据库"""
        # 首先尝试找到配置为primary的数据库
        primary_candidates = [
            (name, config) for name, config in self.databases.items()
            if config.type == 'primary' and config.is_active and self._test_database_connection(name)
        ]
        
        if primary_candidates:
            # 按优先级排序
            primary_candidates.sort(key=lambda x: x[1].priority)
            self.current_primary = primary_candidates[0][0]
        else:
            # 如果没有可用的primary，从secondary中选择
            available_dbs = [
                (name, config) for name, config in self.databases.items()
                if config.is_active and self._test_database_connection(name)
            ]
            
            if available_dbs:
                available_dbs.sort(key=lambda x: x[1].priority)
                self.current_primary = available_dbs[0][0]
                # 临时提升为primary
                self.databases[self.current_primary].type = 'primary'
            else:
                raise RuntimeError("没有可用的数据库")
        
        logger.info(f"选择主数据库: {self.current_primary} ({self.databases[self.current_primary].server_info.location})")
    
    def _test_database_connection(self, db_name: str) -> bool:
        """测试数据库连接"""
        try:
            if db_name not in self.engines:
                return False
            
            engine = self.engines[db_name]
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # 更新状态
            config = self.databases[db_name]
            config.last_check = datetime.now()
            config.last_error = None
            
            return True
            
        except Exception as e:
            logger.error(f"数据库连接测试失败 {db_name}: {e}")
            config = self.databases[db_name]
            config.last_check = datetime.now()
            config.last_error = str(e)
            return False
    
    def _setup_replication_monitoring(self):
        """设置复制监控"""
        for name, config in self.databases.items():
            if config.type == 'secondary' and config.replication:
                self.replication_status[name] = ReplicationStatus.UNKNOWN
                self.replication_lag[name] = 0.0
    
    def check_replication_status(self, db_name: str) -> Tuple[ReplicationStatus, float]:
        """检查复制状态"""
        try:
            if db_name not in self.engines:
                return ReplicationStatus.UNKNOWN, 0.0
            
            config = self.databases[db_name]
            if config.type != 'secondary' or not config.replication:
                return ReplicationStatus.UNKNOWN, 0.0
            
            engine = self.engines[db_name]
            
            with engine.connect() as conn:
                # 检查PostgreSQL复制状态
                if config.url.startswith('postgresql'):
                    # 检查复制延迟
                    result = conn.execute(text("""
                        SELECT 
                            CASE 
                                WHEN pg_is_in_recovery() THEN 
                                    EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
                                ELSE 0 
                            END as lag_seconds
                    """))
                    
                    lag_seconds = result.scalar() or 0.0
                    
                    # 判断复制状态
                    if lag_seconds < 10:
                        status = ReplicationStatus.HEALTHY
                    elif lag_seconds < 60:
                        status = ReplicationStatus.LAGGING
                    else:
                        status = ReplicationStatus.BROKEN
                    
                    # 更新状态
                    self.replication_status[db_name] = status
                    self.replication_lag[db_name] = lag_seconds
                    config.replication_lag = lag_seconds
                    
                    return status, lag_seconds
                
            return ReplicationStatus.UNKNOWN, 0.0
            
        except Exception as e:
            logger.error(f"检查复制状态失败 {db_name}: {e}")
            self.replication_status[db_name] = ReplicationStatus.BROKEN
            return ReplicationStatus.BROKEN, 0.0
    
    def setup_logical_replication(self, source_db: str, target_db: str) -> bool:
        """设置逻辑复制"""
        try:
            source_config = self.databases[source_db]
            target_config = self.databases[target_db]
            
            # 在源数据库创建发布
            with self.engines[source_db].connect() as conn:
                # 检查发布是否已存在
                result = conn.execute(text(
                    "SELECT 1 FROM pg_publication WHERE pubname = 'crawler_replication'"
                ))
                
                if not result.fetchone():
                    # 创建发布
                    conn.execute(text(
                        "CREATE PUBLICATION crawler_replication FOR ALL TABLES"
                    ))
                    conn.commit()
                    logger.info(f"在 {source_db} 创建发布成功")
            
            # 在目标数据库创建订阅
            with self.engines[target_db].connect() as conn:
                # 检查订阅是否已存在
                result = conn.execute(text(
                    "SELECT 1 FROM pg_subscription WHERE subname = 'crawler_subscription'"
                ))
                
                if not result.fetchone():
                    # 创建订阅
                    conn_str = f"host={source_config.host} port={source_config.port} " \
                              f"dbname={source_config.database} user={source_config.username} " \
                              f"password={source_config.password}"
                    
                    conn.execute(text(f"""
                        CREATE SUBSCRIPTION crawler_subscription 
                        CONNECTION '{conn_str}' 
                        PUBLICATION crawler_replication
                    """))
                    conn.commit()
                    logger.info(f"在 {target_db} 创建订阅成功")
            
            return True
            
        except Exception as e:
            logger.error(f"设置逻辑复制失败 {source_db} -> {target_db}: {e}")
            return False
    
    def create_distributed_backup(self, backup_name: Optional[str] = None) -> Dict[str, str]:
        """创建分布式备份"""
        backup_results = {}
        
        for db_name, config in self.databases.items():
            if not config.is_active:
                continue
                
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if backup_name:
                    file_name = f"{backup_name}_{db_name}_{timestamp}.sql"
                else:
                    file_name = f"backup_{db_name}_{timestamp}.sql"
                
                backup_path = f"backups/{file_name}"
                
                # 使用pg_dump创建备份
                import subprocess
                cmd = [
                    'pg_dump',
                    '-h', config.host,
                    '-p', str(config.port),
                    '-U', config.username,
                    '-d', config.database,
                    '--no-password',
                    '--verbose',
                    '--clean',
                    '--if-exists',
                    '-f', backup_path
                ]
                
                env = {'PGPASSWORD': config.password}
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env
                )
                
                if result.returncode == 0:
                    backup_results[db_name] = backup_path
                    logger.info(f"数据库备份成功: {db_name} -> {backup_path}")
                else:
                    logger.error(f"数据库备份失败 {db_name}: {result.stderr}")
                    
            except Exception as e:
                logger.error(f"创建备份失败 {db_name}: {e}")
        
        return backup_results
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """获取集群状态"""
        status = {
            "current_primary": self.current_primary,
            "total_databases": len(self.databases),
            "active_databases": sum(1 for db in self.databases.values() if db.is_active),
            "databases": {},
            "replication": {}
        }
        
        for name, config in self.databases.items():
            is_connected = self._test_database_connection(name)
            
            db_status = {
                "name": name,
                "type": config.type,
                "is_active": config.is_active,
                "is_connected": is_connected,
                "is_primary": name == self.current_primary,
                "priority": config.priority,
                "server_info": {
                    "location": config.server_info.location,
                    "ip": config.server_info.ip,
                    "region": config.server_info.region,
                    "description": config.server_info.description
                },
                "last_check": config.last_check.isoformat() if config.last_check else None,
                "last_error": config.last_error
            }
            
            # 添加复制信息
            if config.type == 'secondary' and config.replication:
                repl_status, lag = self.check_replication_status(name)
                db_status["replication"] = {
                    "source": config.replication.source,
                    "mode": config.replication.mode,
                    "status": repl_status.value,
                    "lag_seconds": lag
                }
            
            status["databases"][name] = db_status
        
        return status
    
    def failover_to_database(self, target_db: str, reason: str = "手动故障转移") -> bool:
        """故障转移到指定数据库"""
        with self._lock:
            if target_db not in self.databases:
                logger.error(f"目标数据库不存在: {target_db}")
                return False
            
            if not self._test_database_connection(target_db):
                logger.error(f"目标数据库连接失败: {target_db}")
                return False
            
            old_primary = self.current_primary
            
            # 如果目标数据库是从库，需要提升为主库
            target_config = self.databases[target_db]
            if target_config.type == 'secondary':
                if not self._promote_secondary_to_primary(target_db):
                    logger.error(f"提升从库为主库失败: {target_db}")
                    return False
            
            self.current_primary = target_db
            
            # 更新数据库类型
            if old_primary:
                self.databases[old_primary].type = 'secondary'
            self.databases[target_db].type = 'primary'
            
            logger.warning(f"分布式故障转移完成: {old_primary} -> {target_db} ({reason})")
            
            return True
    
    def _promote_secondary_to_primary(self, db_name: str) -> bool:
        """提升从库为主库"""
        try:
            config = self.databases[db_name]
            
            with self.engines[db_name].connect() as conn:
                # 检查是否是从库
                result = conn.execute(text("SELECT pg_is_in_recovery()"))
                is_in_recovery = result.scalar()
                
                if is_in_recovery:
                    # 提升从库为主库
                    conn.execute(text("SELECT pg_promote()"))
                    logger.info(f"从库提升为主库成功: {db_name}")
                    
                    # 等待提升完成
                    time.sleep(2)
                    
                    # 验证提升结果
                    result = conn.execute(text("SELECT pg_is_in_recovery()"))
                    is_still_in_recovery = result.scalar()
                    
                    if not is_still_in_recovery:
                        logger.info(f"从库提升验证成功: {db_name}")
                        return True
                    else:
                        logger.error(f"从库提升验证失败: {db_name}")
                        return False
                else:
                    logger.info(f"数据库已经是主库: {db_name}")
                    return True
                    
        except Exception as e:
            logger.error(f"提升从库为主库失败 {db_name}: {e}")
            return False
