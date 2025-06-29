"""
数据库备份管理器

提供数据库容灾备份功能，包括：
- 主从数据库管理
- 自动备份和恢复
- 故障检测和转移
- 数据同步
"""

import os
import json
import time
import logging
import threading
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, asdict

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.engine import Engine

from database.models.base import Base

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """数据库配置"""
    name: str
    type: str  # 'primary' or 'secondary'
    url: str
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    priority: int = 0  # 优先级，数字越小优先级越高
    is_active: bool = True
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None


@dataclass
class BackupConfig:
    """备份配置"""
    backup_dir: str = "backups"
    max_backups: int = 10
    backup_interval: int = 3600  # 秒
    enable_auto_backup: bool = True
    enable_compression: bool = True
    backup_format: str = "sql"  # sql, binary
    retention_days: int = 30


@dataclass
class FailoverConfig:
    """故障转移配置"""
    enable_auto_failover: bool = True
    health_check_interval: int = 30  # 秒
    max_retry_attempts: int = 3
    retry_delay: int = 5  # 秒
    failover_timeout: int = 60  # 秒
    notification_enabled: bool = True


class DatabaseBackupManager:
    """
    数据库备份管理器
    
    功能：
    - 管理多个数据库实例（主从架构）
    - 自动备份和恢复
    - 健康检查和故障检测
    - 自动故障转移
    - 数据同步
    """
    
    def __init__(self, 
                 databases: List[DatabaseConfig],
                 backup_config: BackupConfig,
                 failover_config: FailoverConfig):
        """
        初始化备份管理器
        
        Args:
            databases: 数据库配置列表
            backup_config: 备份配置
            failover_config: 故障转移配置
        """
        self.databases = {db.name: db for db in databases}
        self.backup_config = backup_config
        self.failover_config = failover_config
        
        # 当前活跃的数据库
        self.current_primary: Optional[str] = None
        self.engines: Dict[str, Engine] = {}
        self.session_makers: Dict[str, sessionmaker] = {}
        
        # 监控和状态
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_backup_time: Optional[datetime] = None
        self.backup_thread: Optional[threading.Thread] = None
        
        # 状态锁
        self._lock = threading.Lock()
        
        # 初始化
        self._initialize_engines()
        self._select_primary_database()
        
        # 创建备份目录
        Path(self.backup_config.backup_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("数据库备份管理器初始化完成")
    
    def _initialize_engines(self):
        """初始化数据库引擎"""
        for name, config in self.databases.items():
            try:
                if config.url.startswith('sqlite'):
                    engine = create_engine(
                        config.url,
                        echo=False,
                        connect_args={"check_same_thread": False, "timeout": 30}
                    )
                else:
                    engine = create_engine(
                        config.url,
                        echo=False,
                        pool_size=5,
                        max_overflow=10,
                        pool_pre_ping=True,
                        pool_recycle=3600
                    )
                
                self.engines[name] = engine
                self.session_makers[name] = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=engine
                )
                
                logger.info(f"数据库引擎初始化成功: {name}")
                
            except Exception as e:
                logger.error(f"数据库引擎初始化失败 {name}: {e}")
                config.is_active = False
                config.last_error = str(e)
    
    def _select_primary_database(self):
        """选择主数据库"""
        # 按优先级排序，选择可用的数据库作为主数据库
        available_dbs = [
            (name, config) for name, config in self.databases.items()
            if config.is_active and self._test_database_connection(name)
        ]
        
        if not available_dbs:
            raise RuntimeError("没有可用的数据库")
        
        # 按优先级排序
        available_dbs.sort(key=lambda x: x[1].priority)
        
        self.current_primary = available_dbs[0][0]
        logger.info(f"选择主数据库: {self.current_primary}")
    
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
    
    @contextmanager
    def get_session(self, db_name: Optional[str] = None):
        """获取数据库会话"""
        if db_name is None:
            db_name = self.current_primary
        
        if db_name not in self.session_makers:
            raise ValueError(f"数据库不存在: {db_name}")
        
        session = self.session_makers[db_name]()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败 {db_name}: {e}")
            raise
        finally:
            session.close()
    
    def get_current_engine(self) -> Engine:
        """获取当前主数据库引擎"""
        if not self.current_primary:
            raise RuntimeError("没有可用的主数据库")
        return self.engines[self.current_primary]
    
    def get_database_status(self) -> Dict[str, Any]:
        """获取所有数据库状态"""
        status = {}
        for name, config in self.databases.items():
            is_connected = self._test_database_connection(name)
            status[name] = {
                "name": name,
                "type": config.type,
                "is_active": config.is_active,
                "is_connected": is_connected,
                "is_primary": name == self.current_primary,
                "priority": config.priority,
                "last_check": config.last_check.isoformat() if config.last_check else None,
                "last_error": config.last_error,
                "url": config.url
            }
        return status

    def create_backup(self, db_name: Optional[str] = None, backup_name: Optional[str] = None) -> str:
        """
        创建数据库备份

        Args:
            db_name: 数据库名称，默认为当前主数据库
            backup_name: 备份名称，默认自动生成

        Returns:
            备份文件路径
        """
        if db_name is None:
            db_name = self.current_primary

        if db_name not in self.engines:
            raise ValueError(f"数据库不存在: {db_name}")

        # 生成备份文件名
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{db_name}_backup_{timestamp}"

        backup_path = Path(self.backup_config.backup_dir) / f"{backup_name}.sql"

        try:
            config = self.databases[db_name]

            if config.url.startswith('sqlite'):
                # SQLite备份
                self._backup_sqlite(config.url, backup_path)
            else:
                # PostgreSQL备份
                self._backup_postgresql(config, backup_path)

            # 压缩备份文件
            if self.backup_config.enable_compression:
                compressed_path = self._compress_backup(backup_path)
                backup_path.unlink()  # 删除原文件
                backup_path = compressed_path

            # 清理旧备份
            self._cleanup_old_backups()

            self.last_backup_time = datetime.now()
            logger.info(f"数据库备份创建成功: {backup_path}")

            return str(backup_path)

        except Exception as e:
            logger.error(f"创建数据库备份失败: {e}")
            if backup_path.exists():
                backup_path.unlink()
            raise

    def _backup_sqlite(self, db_url: str, backup_path: Path):
        """使用Python内置的sqlite3模块备份数据库，避免依赖外部命令。"""
        import sqlite3
        
        # 提取SQLite文件路径
        db_file = db_url.replace('sqlite:///', '')

        if not Path(db_file).exists():
            raise FileNotFoundError(f"SQLite数据库文件不存在: {db_file}")

        try:
            # 连接到源数据库
            source_conn = sqlite3.connect(db_file)
            
            # 以文本模式和UTF-8编码打开备份文件
            with open(backup_path, 'w', encoding='utf-8') as f:
                # iterdump() 生成SQL转储
                for line in source_conn.iterdump():
                    f.write(f'{line}\n')
            
            source_conn.close()
            logger.info(f"通过Python sqlite3模块成功创建备份: {backup_path}")

        except sqlite3.Error as e:
            logger.error(f"使用Python sqlite3模块备份失败: {e}")
            if backup_path.exists():
                backup_path.unlink() # 清理不完整的备份
            raise RuntimeError(f"SQLite备份失败: {e}") from e
        except Exception as e:
            logger.error(f"创建SQLite备份时发生未知错误: {e}")
            if backup_path.exists():
                backup_path.unlink()
            raise e

    def _backup_postgresql(self, config: DatabaseConfig, backup_path: Path):
        """备份PostgreSQL数据库"""
        # 构建pg_dump命令
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
            '--create'
        ]

        # 设置环境变量
        env = os.environ.copy()
        env['PGPASSWORD'] = config.password

        with open(backup_path, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"PostgreSQL备份失败: {result.stderr}")

    def _compress_backup(self, backup_path: Path) -> Path:
        """压缩备份文件"""
        import gzip

        compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')

        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)

        return compressed_path

    def _cleanup_old_backups(self):
        """清理旧备份文件"""
        backup_dir = Path(self.backup_config.backup_dir)

        # 获取所有备份文件
        backup_files = []
        for pattern in ['*.sql', '*.sql.gz']:
            backup_files.extend(backup_dir.glob(pattern))

        # 按修改时间排序
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 删除超过数量限制的备份
        if len(backup_files) > self.backup_config.max_backups:
            for file_path in backup_files[self.backup_config.max_backups:]:
                try:
                    file_path.unlink()
                    logger.info(f"删除旧备份文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除备份文件失败 {file_path}: {e}")

        # 删除超过保留期限的备份
        cutoff_time = datetime.now() - timedelta(days=self.backup_config.retention_days)
        for file_path in backup_files:
            try:
                if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_time:
                    file_path.unlink()
                    logger.info(f"删除过期备份文件: {file_path}")
            except Exception as e:
                logger.error(f"删除过期备份文件失败 {file_path}: {e}")

    def restore_backup(self, backup_path: str, db_name: Optional[str] = None) -> bool:
        """
        恢复数据库备份

        Args:
            backup_path: 备份文件路径
            db_name: 目标数据库名称，默认为当前主数据库

        Returns:
            是否恢复成功
        """
        if db_name is None:
            db_name = self.current_primary

        if db_name not in self.engines:
            raise ValueError(f"数据库不存在: {db_name}")

        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        try:
            config = self.databases[db_name]

            # 解压备份文件（如果需要）
            if backup_file.suffix == '.gz':
                temp_path = self._decompress_backup(backup_file)
            else:
                temp_path = backup_file

            if config.url.startswith('sqlite'):
                # SQLite恢复
                self._restore_sqlite(config.url, temp_path)
            else:
                # PostgreSQL恢复
                self._restore_postgresql(config, temp_path)

            # 清理临时文件
            if temp_path != backup_file:
                temp_path.unlink()

            logger.info(f"数据库恢复成功: {db_name} <- {backup_path}")
            return True

        except Exception as e:
            logger.error(f"数据库恢复失败: {e}")
            return False

    def _decompress_backup(self, compressed_path: Path) -> Path:
        """解压备份文件"""
        import gzip

        temp_path = compressed_path.with_suffix('')

        with gzip.open(compressed_path, 'rb') as f_in:
            with open(temp_path, 'wb') as f_out:
                f_out.writelines(f_in)

        return temp_path

    def _restore_sqlite(self, db_url: str, backup_path: Path):
        """恢复SQLite数据库"""
        db_file = db_url.replace('sqlite:///', '')

        # 关闭所有数据库连接
        db_name = None
        for name, config in self.databases.items():
            if config.url == db_url:
                db_name = name
                break

        if db_name and db_name in self.engines:
            try:
                # 关闭引擎连接
                self.engines[db_name].dispose()
                time.sleep(0.5)  # 等待连接完全关闭
            except Exception as e:
                logger.warning(f"关闭数据库连接时出错: {e}")

        # 备份当前数据库文件
        backup_current = None
        if Path(db_file).exists():
            backup_current = Path(db_file).with_suffix(f'.bak_{int(time.time())}')
            try:
                import shutil
                shutil.copy2(db_file, backup_current)
                Path(db_file).unlink()  # 删除原文件
            except Exception as e:
                logger.error(f"备份当前数据库文件失败: {e}")
                raise RuntimeError(f"无法备份当前数据库文件: {e}")

        try:
            # 执行恢复
            cmd = f'sqlite3 "{db_file}" < "{backup_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"SQLite恢复失败: {result.stderr}")

        except Exception as e:
            # 恢复失败，还原原文件
            if backup_current and backup_current.exists():
                try:
                    import shutil
                    shutil.copy2(backup_current, db_file)
                except Exception as restore_error:
                    logger.error(f"还原原数据库文件失败: {restore_error}")
            raise e
        else:
            # 删除备份文件
            if backup_current and backup_current.exists():
                try:
                    backup_current.unlink()
                except Exception as e:
                    logger.warning(f"删除临时备份文件失败: {e}")

        # 重新初始化数据库引擎
        if db_name:
            try:
                self._initialize_engines()
            except Exception as e:
                logger.error(f"重新初始化数据库引擎失败: {e}")

    def _restore_postgresql(self, config: DatabaseConfig, backup_path: Path):
        """恢复PostgreSQL数据库"""
        cmd = [
            'psql',
            '-h', config.host,
            '-p', str(config.port),
            '-U', config.username,
            '-d', config.database,
            '-f', str(backup_path)
        ]

        env = os.environ.copy()
        env['PGPASSWORD'] = config.password

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            raise RuntimeError(f"PostgreSQL恢复失败: {result.stderr}")

    def sync_databases(self, source_db: str, target_db: str) -> bool:
        """
        同步数据库

        Args:
            source_db: 源数据库名称
            target_db: 目标数据库名称

        Returns:
            是否同步成功
        """
        try:
            # 检查源数据库和目标数据库是否都可用
            if not self._test_database_connection(source_db):
                logger.error(f"源数据库连接失败: {source_db}")
                return False

            if not self._test_database_connection(target_db):
                logger.error(f"目标数据库连接失败: {target_db}")
                return False

            # 对于SQLite数据库，使用文件复制方式同步
            source_config = self.databases[source_db]
            target_config = self.databases[target_db]

            if (source_config.url.startswith('sqlite') and
                target_config.url.startswith('sqlite')):
                return self._sync_sqlite_databases(source_config, target_config)
            else:
                # 对于PostgreSQL，使用备份恢复方式
                return self._sync_via_backup_restore(source_db, target_db)

        except Exception as e:
            logger.error(f"数据库同步失败: {e}")
            return False

    def _sync_sqlite_databases(self, source_config: DatabaseConfig, target_config: DatabaseConfig) -> bool:
        """同步SQLite数据库（使用文件复制）"""
        try:
            source_file = source_config.url.replace('sqlite:///', '')
            target_file = target_config.url.replace('sqlite:///', '')

            if not Path(source_file).exists():
                logger.error(f"源数据库文件不存在: {source_file}")
                return False

            # 确保目标目录存在
            Path(target_file).parent.mkdir(parents=True, exist_ok=True)

            # 关闭目标数据库连接
            target_name = target_config.name
            if target_name in self.engines:
                try:
                    self.engines[target_name].dispose()
                    time.sleep(0.3)  # 等待连接关闭
                except Exception as e:
                    logger.warning(f"关闭目标数据库连接时出错: {e}")

            # 备份现有目标文件（如果存在）
            backup_target = None
            if Path(target_file).exists():
                backup_target = Path(target_file).with_suffix(f'.backup_{int(time.time())}')
                try:
                    import shutil
                    shutil.copy2(target_file, backup_target)
                except Exception as e:
                    logger.warning(f"备份目标文件失败: {e}")

            try:
                # 复制文件
                import shutil
                shutil.copy2(source_file, target_file)
                logger.info(f"数据库文件复制成功: {source_file} -> {target_file}")

            except Exception as e:
                # 复制失败，尝试恢复备份
                if backup_target and backup_target.exists():
                    try:
                        import shutil
                        shutil.copy2(backup_target, target_file)
                        logger.info("已恢复目标数据库备份")
                    except Exception as restore_error:
                        logger.error(f"恢复目标数据库备份失败: {restore_error}")
                raise e

            # 重新初始化目标数据库引擎
            try:
                # 重新创建引擎
                if target_config.url.startswith('sqlite'):
                    engine = create_engine(
                        target_config.url,
                        echo=False,
                        connect_args={"check_same_thread": False, "timeout": 30}
                    )
                else:
                    engine = create_engine(
                        target_config.url,
                        echo=False,
                        pool_size=5,
                        max_overflow=10,
                        pool_pre_ping=True,
                        pool_recycle=3600
                    )

                self.engines[target_name] = engine
                self.session_makers[target_name] = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=engine
                )

                # 验证同步结果
                if self._test_database_connection(target_name):
                    logger.info(f"目标数据库连接验证成功: {target_name}")
                else:
                    logger.error(f"目标数据库连接验证失败: {target_name}")
                    return False

            except Exception as e:
                logger.error(f"重新初始化目标数据库引擎失败: {e}")
                return False

            # 清理备份文件
            if backup_target and backup_target.exists():
                try:
                    backup_target.unlink()
                except Exception as e:
                    logger.warning(f"清理备份文件失败: {e}")

            logger.info(f"SQLite数据库同步成功: {source_config.name} -> {target_config.name}")
            return True

        except Exception as e:
            logger.error(f"SQLite数据库同步失败: {e}")
            return False

    def _sync_via_backup_restore(self, source_db: str, target_db: str) -> bool:
        """通过备份恢复方式同步数据库"""
        try:
            # 创建源数据库备份
            backup_path = self.create_backup(source_db, f"sync_temp_{int(time.time())}")

            if not backup_path:
                logger.error("创建同步备份失败")
                return False

            # 恢复到目标数据库
            success = self.restore_backup(backup_path, target_db)

            # 清理临时备份
            try:
                Path(backup_path).unlink()
            except Exception as e:
                logger.warning(f"清理临时备份文件失败: {e}")

            if success:
                logger.info(f"数据库同步成功: {source_db} -> {target_db}")
            else:
                logger.error(f"数据库同步失败: {source_db} -> {target_db}")

            return success

        except Exception as e:
            logger.error(f"备份恢复同步失败: {e}")
            return False

    def failover_to_database(self, target_db: str) -> bool:
        """
        故障转移到指定数据库

        Args:
            target_db: 目标数据库名称

        Returns:
            是否转移成功
        """
        with self._lock:
            if target_db not in self.databases:
                logger.error(f"目标数据库不存在: {target_db}")
                return False

            if not self._test_database_connection(target_db):
                logger.error(f"目标数据库连接失败: {target_db}")
                return False

            old_primary = self.current_primary
            self.current_primary = target_db

            # 更新数据库类型
            if old_primary:
                self.databases[old_primary].type = 'secondary'
            self.databases[target_db].type = 'primary'

            logger.warning(f"故障转移完成: {old_primary} -> {target_db}")

            # 发送通知
            if self.failover_config.notification_enabled:
                self._send_failover_notification(old_primary, target_db)

            return True

    def _send_failover_notification(self, old_db: str, new_db: str):
        """发送故障转移通知"""
        message = f"数据库故障转移: {old_db} -> {new_db} at {datetime.now()}"
        logger.critical(message)
        # 这里可以添加邮件、短信等通知方式

    def start_monitoring(self):
        """启动监控"""
        if self.is_monitoring:
            logger.warning("监控已经在运行")
            return

        self.is_monitoring = True

        # 启动健康检查线程
        self.monitor_thread = threading.Thread(
            target=self._monitor_databases,
            daemon=True
        )
        self.monitor_thread.start()

        # 启动自动备份线程
        if self.backup_config.enable_auto_backup:
            self.backup_thread = threading.Thread(
                target=self._auto_backup,
                daemon=True
            )
            self.backup_thread.start()

        logger.info("数据库监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        if self.backup_thread:
            self.backup_thread.join(timeout=5)

        logger.info("数据库监控已停止")

    def _monitor_databases(self):
        """监控数据库健康状态"""
        while self.is_monitoring:
            try:
                # 检查当前主数据库
                if self.current_primary and not self._test_database_connection(self.current_primary):
                    logger.error(f"主数据库连接失败: {self.current_primary}")

                    # 尝试故障转移
                    if self.failover_config.enable_auto_failover:
                        self._attempt_failover()

                # 检查所有数据库状态
                for db_name in self.databases:
                    self._test_database_connection(db_name)

                time.sleep(self.failover_config.health_check_interval)

            except Exception as e:
                logger.error(f"数据库监控异常: {e}")
                time.sleep(self.failover_config.health_check_interval)

    def _attempt_failover(self):
        """尝试自动故障转移"""
        # 查找可用的备用数据库
        available_dbs = [
            (name, config) for name, config in self.databases.items()
            if name != self.current_primary and
               config.is_active and
               self._test_database_connection(name)
        ]

        if not available_dbs:
            logger.critical("没有可用的备用数据库进行故障转移")
            return

        # 按优先级排序
        available_dbs.sort(key=lambda x: x[1].priority)

        # 尝试转移到优先级最高的数据库
        target_db = available_dbs[0][0]

        if self.failover_to_database(target_db):
            logger.info(f"自动故障转移成功: {target_db}")
        else:
            logger.error(f"自动故障转移失败: {target_db}")

    def _auto_backup(self):
        """自动备份"""
        while self.is_monitoring:
            try:
                # 检查是否需要备份
                if (self.last_backup_time is None or
                    datetime.now() - self.last_backup_time >= timedelta(seconds=self.backup_config.backup_interval)):

                    if self.current_primary:
                        self.create_backup(self.current_primary)

                time.sleep(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"自动备份异常: {e}")
                time.sleep(60)
