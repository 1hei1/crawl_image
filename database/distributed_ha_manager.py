"""
分布式高可用数据库管理器

实现跨服务器的数据库高可用性，包括：
- 实时数据同步
- 自动故障检测和转移
- 负载均衡
- 数据一致性保证
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from contextlib import contextmanager

import aiohttp
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from database.models.base import Base
from database.models.image import ImageModel

logger = logging.getLogger(__name__)


class AutoSyncSession:
    """
    自动同步的数据库会话包装器

    在数据库操作提交时自动触发数据同步到备用节点
    """

    def __init__(self, session, ha_manager):
        self.session = session
        self.ha_manager = ha_manager
        self._pending_operations = []

    def __getattr__(self, name):
        """代理所有session方法"""
        return getattr(self.session, name)

    def add(self, instance):
        """添加实例到会话"""
        result = self.session.add(instance)

        # 记录待同步的操作
        if hasattr(instance, '__tablename__'):
            self._pending_operations.append({
                'type': 'INSERT',
                'table': instance.__tablename__,
                'instance': instance
            })

        return result

    def delete(self, instance):
        """从会话删除实例"""
        result = self.session.delete(instance)

        # 记录待同步的操作
        if hasattr(instance, '__tablename__') and hasattr(instance, 'id'):
            self._pending_operations.append({
                'type': 'DELETE',
                'table': instance.__tablename__,
                'instance': instance
            })

        return result

    def commit(self):
        """提交事务并触发同步"""
        try:
            # 先提交到主数据库
            self.session.commit()

            # 处理待同步的操作
            self._process_pending_sync_operations()

        except Exception as e:
            self.session.rollback()
            raise e

    def _process_pending_sync_operations(self):
        """处理待同步的操作"""
        for operation in self._pending_operations:
            try:
                if operation['type'] == 'INSERT':
                    self._sync_insert_operation(operation)
                elif operation['type'] == 'DELETE':
                    self._sync_delete_operation(operation)
                elif operation['type'] == 'UPDATE':
                    self._sync_update_operation(operation)
            except Exception as e:
                logger.error(f"同步操作失败: {e}")

        # 清空待同步操作
        self._pending_operations.clear()

    def _sync_insert_operation(self, operation):
        """同步插入操作"""
        instance = operation['instance']
        table_name = operation['table']

        # 使用HA管理器的序列化方法
        data = self.ha_manager._serialize_model(instance)

        # 添加到同步队列
        self.ha_manager.add_sync_operation('INSERT', table_name, data)
        logger.debug(f"已添加INSERT同步操作: {table_name}, ID: {getattr(instance, 'id', 'N/A')}")

    def _sync_delete_operation(self, operation):
        """同步删除操作"""
        instance = operation['instance']
        table_name = operation['table']

        if hasattr(instance, 'id'):
            data = {'id': instance.id}
            self.ha_manager.add_sync_operation('DELETE', table_name, data)
            logger.debug(f"已添加DELETE同步操作: {table_name}, ID: {instance.id}")

    def _sync_update_operation(self, operation):
        """同步更新操作"""
        instance = operation['instance']
        table_name = operation['table']

        # 使用HA管理器的序列化方法
        data = self.ha_manager._serialize_model(instance)

        # 添加到同步队列
        self.ha_manager.add_sync_operation('UPDATE', table_name, data)
        logger.debug(f"已添加UPDATE同步操作: {table_name}, ID: {getattr(instance, 'id', 'N/A')}")


class DatabaseRole(Enum):
    """数据库角色"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    STANDBY = "standby"


class SyncMode(Enum):
    """同步模式"""
    SYNC = "sync"          # 同步复制
    ASYNC = "async"        # 异步复制
    SEMI_SYNC = "semi_sync"  # 半同步复制


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class ServerInfo:
    """服务器信息"""
    host: str
    port: int
    api_port: int = 8001  # API端口用于服务器间通信
    location: str = "unknown"
    datacenter: str = "default"


@dataclass
class DatabaseNode:
    """数据库节点配置"""
    name: str
    role: DatabaseRole
    priority: int  # 优先级，数字越小优先级越高
    server: ServerInfo
    database_url: str
    
    # 连接配置
    max_connections: int = 100
    connection_timeout: int = 30
    
    # 同步配置
    sync_mode: SyncMode = SyncMode.ASYNC
    sync_timeout: int = 10
    
    # 健康检查
    health_check_interval: int = 5
    failure_threshold: int = 3
    
    # 状态信息
    is_active: bool = True
    last_check: Optional[datetime] = None
    last_error: Optional[str] = None
    replication_lag: float = 0.0
    health_status: HealthStatus = HealthStatus.HEALTHY
    failure_count: int = 0


@dataclass
class SyncOperation:
    """同步操作"""
    operation_id: str
    timestamp: datetime
    operation_type: str  # INSERT, UPDATE, DELETE
    table_name: str
    data: Dict[str, Any]
    source_node: str
    target_nodes: List[str]
    status: str = "pending"  # pending, completed, failed


class DistributedHAManager:
    """
    分布式高可用数据库管理器
    
    核心功能：
    1. 多节点数据库管理
    2. 实时数据同步
    3. 自动故障检测和转移
    4. 负载均衡读操作
    5. 数据一致性保证
    """
    
    def __init__(self, nodes: List[DatabaseNode], local_node_name: str, config: Dict[str, Any] = None):
        """
        初始化分布式HA管理器

        Args:
            nodes: 数据库节点列表
            local_node_name: 当前节点名称
            config: 配置字典
        """
        self.nodes = {node.name: node for node in nodes}
        self.local_node_name = local_node_name
        self.local_node = self.nodes[local_node_name]
        self.config = config or {}

        # 当前主节点
        self.current_primary: Optional[str] = None

        # 数据库连接
        self.engines: Dict[str, Any] = {}
        self.session_makers: Dict[str, sessionmaker] = {}

        # 同步队列
        self.sync_queue: List[SyncOperation] = []
        self.sync_lock = threading.Lock()

        # 从配置文件加载同步配置
        sync_config = self.config.get('synchronization', {})
        self.auto_sync_enabled = sync_config.get('auto_sync_enabled', True)
        self.full_sync_interval = sync_config.get('full_sync_interval', 300)
        self.incremental_sync_interval = sync_config.get('incremental_sync_interval', 10)
        self.batch_size = sync_config.get('batch_size', 100)
        self.max_queue_size = sync_config.get('max_queue_size', 1000)
        self.sync_timeout = sync_config.get('sync_timeout', 30)
        self.verify_sync = sync_config.get('verify_sync', True)
        self.sync_tables = sync_config.get('sync_tables', ['images', 'categories'])

        self.last_full_sync = time.time()

        # 监控线程
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.sync_thread: Optional[threading.Thread] = None
        self.full_sync_thread: Optional[threading.Thread] = None

        # 故障转移回调
        self.failover_callbacks: List[Callable] = []
        
        # 初始化
        self._initialize_engines()
        self._select_primary_node()
        
        logger.info(f"分布式HA管理器初始化完成，本地节点: {local_node_name}")
    
    def _initialize_engines(self):
        """初始化数据库引擎"""
        for node_name, node in self.nodes.items():
            try:
                engine = create_engine(
                    node.database_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    connect_args={"connect_timeout": node.connection_timeout}
                )
                
                session_maker = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=engine
                )
                
                self.engines[node_name] = engine
                self.session_makers[node_name] = session_maker
                
                # 测试连接
                if self._test_node_connection(node_name):
                    node.health_status = HealthStatus.HEALTHY
                    logger.info(f"节点 {node_name} 连接成功")
                else:
                    node.health_status = HealthStatus.OFFLINE
                    logger.warning(f"节点 {node_name} 连接失败")
                    
            except Exception as e:
                logger.error(f"初始化节点 {node_name} 失败: {e}")
                node.health_status = HealthStatus.OFFLINE
                node.last_error = str(e)
    
    def _select_primary_node(self):
        """选择主节点"""
        # 查找当前的主节点
        primary_nodes = [
            name for name, node in self.nodes.items()
            if node.role == DatabaseRole.PRIMARY and 
               node.health_status == HealthStatus.HEALTHY
        ]
        
        if primary_nodes:
            # 按优先级选择
            primary_nodes.sort(key=lambda x: self.nodes[x].priority)
            self.current_primary = primary_nodes[0]
        else:
            # 没有健康的主节点，尝试提升备节点
            self._promote_secondary_to_primary()
        
        logger.info(f"当前主节点: {self.current_primary}")
    
    def _promote_secondary_to_primary(self):
        """提升备节点为主节点"""
        # 查找健康的备节点
        secondary_nodes = [
            (name, node) for name, node in self.nodes.items()
            if node.role == DatabaseRole.SECONDARY and 
               node.health_status == HealthStatus.HEALTHY
        ]
        
        if not secondary_nodes:
            logger.critical("没有可用的备节点进行提升")
            return False
        
        # 按优先级排序
        secondary_nodes.sort(key=lambda x: x[1].priority)
        target_node_name = secondary_nodes[0][0]
        target_node = secondary_nodes[0][1]
        
        # 提升为主节点
        target_node.role = DatabaseRole.PRIMARY
        self.current_primary = target_node_name
        
        # 通知其他节点
        self._notify_role_change(target_node_name, DatabaseRole.PRIMARY)
        
        logger.warning(f"节点 {target_node_name} 已提升为主节点")
        return True
    
    def start_monitoring(self):
        """启动监控"""
        if self.is_monitoring:
            return

        self.is_monitoring = True

        # 启动健康监控线程
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()

        # 启动同步线程
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True
        )
        self.sync_thread.start()

        # 启动全量同步线程
        if self.auto_sync_enabled:
            self.full_sync_thread = threading.Thread(
                target=self._full_sync_loop,
                daemon=True
            )
            self.full_sync_thread.start()

        logger.info("分布式HA监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        if self.sync_thread:
            self.sync_thread.join(timeout=5)

        if self.full_sync_thread:
            self.full_sync_thread.join(timeout=5)

        logger.info("分布式HA监控已停止")

    def _monitor_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                # 检查所有节点健康状态
                for node_name in self.nodes:
                    self._check_node_health(node_name)

                # 检查主节点状态
                if self.current_primary:
                    if not self._is_node_healthy(self.current_primary):
                        logger.error(f"主节点 {self.current_primary} 不健康，尝试故障转移")
                        self._attempt_failover()

                # 检查复制延迟
                self._check_replication_lag()

                time.sleep(5)  # 每5秒检查一次

            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(5)

    def _check_node_health(self, node_name: str):
        """检查节点健康状态"""
        node = self.nodes[node_name]

        try:
            # 测试数据库连接
            if self._test_node_connection(node_name):
                # 连接成功，重置失败计数
                node.failure_count = 0
                if node.health_status == HealthStatus.OFFLINE:
                    node.health_status = HealthStatus.HEALTHY
                    logger.info(f"节点 {node_name} 恢复健康")
            else:
                # 连接失败，增加失败计数
                node.failure_count += 1

                if node.failure_count >= node.failure_threshold:
                    if node.health_status != HealthStatus.OFFLINE:
                        node.health_status = HealthStatus.OFFLINE
                        logger.warning(f"节点 {node_name} 标记为离线")
                elif node.failure_count > 1:
                    node.health_status = HealthStatus.WARNING

            node.last_check = datetime.now(timezone.utc)

        except Exception as e:
            node.last_error = str(e)
            node.failure_count += 1
            logger.error(f"检查节点 {node_name} 健康状态失败: {e}")

    def _test_node_connection(self, node_name: str) -> bool:
        """测试节点连接"""
        try:
            if node_name not in self.engines:
                return False

            engine = self.engines[node_name]
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True

        except Exception as e:
            logger.debug(f"节点 {node_name} 连接测试失败: {e}")
            return False

    def _is_node_healthy(self, node_name: str) -> bool:
        """检查节点是否健康"""
        node = self.nodes[node_name]
        return node.health_status in [HealthStatus.HEALTHY, HealthStatus.WARNING]

    def _attempt_failover(self):
        """尝试故障转移"""
        if not self.current_primary:
            return

        failed_primary = self.current_primary

        # 查找可用的备节点
        available_nodes = [
            (name, node) for name, node in self.nodes.items()
            if name != failed_primary and
               self._is_node_healthy(name) and
               node.role in [DatabaseRole.SECONDARY, DatabaseRole.STANDBY]
        ]

        if not available_nodes:
            logger.critical("没有可用的备节点进行故障转移")
            return False

        # 按优先级排序
        available_nodes.sort(key=lambda x: x[1].priority)
        target_node_name = available_nodes[0][0]

        # 执行故障转移
        if self._execute_failover(failed_primary, target_node_name):
            logger.info(f"故障转移成功: {failed_primary} -> {target_node_name}")

            # 调用故障转移回调
            for callback in self.failover_callbacks:
                try:
                    callback(failed_primary, target_node_name)
                except Exception as e:
                    logger.error(f"故障转移回调执行失败: {e}")

            return True
        else:
            logger.error(f"故障转移失败: {failed_primary} -> {target_node_name}")
            return False

    def _execute_failover(self, failed_node: str, target_node: str) -> bool:
        """执行故障转移"""
        try:
            # 更新节点角色
            if failed_node in self.nodes:
                self.nodes[failed_node].role = DatabaseRole.SECONDARY

            self.nodes[target_node].role = DatabaseRole.PRIMARY
            self.current_primary = target_node

            # 通知所有节点角色变更
            self._notify_role_change(target_node, DatabaseRole.PRIMARY)
            self._notify_role_change(failed_node, DatabaseRole.SECONDARY)

            logger.warning(f"故障转移完成: {failed_node} -> {target_node}")
            return True

        except Exception as e:
            logger.error(f"执行故障转移失败: {e}")
            return False

    def _notify_role_change(self, node_name: str, new_role: DatabaseRole):
        """通知节点角色变更"""
        node = self.nodes[node_name]

        # 如果是本地节点，直接更新
        if node_name == self.local_node_name:
            node.role = new_role
            return

        # 通知远程节点
        try:
            url = f"http://{node.server.host}:{node.server.api_port}/api/role-change"
            data = {
                "node_name": node_name,
                "new_role": new_role.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"成功通知节点 {node_name} 角色变更为 {new_role.value}")
            else:
                logger.warning(f"通知节点 {node_name} 角色变更失败: {response.status_code}")

        except Exception as e:
            logger.error(f"通知节点 {node_name} 角色变更异常: {e}")

    def _sync_loop(self):
        """数据同步循环"""
        while self.is_monitoring:
            try:
                operations_to_process = []
                with self.sync_lock:
                    if self.sync_queue:
                        # 处理同步队列中的操作
                        operations_to_process = self.sync_queue.copy()
                        self.sync_queue.clear()

                for operation in operations_to_process:
                    self._process_sync_operation(operation)

                time.sleep(1)  # 每秒处理一次同步队列

            except Exception as e:
                logger.error(f"同步循环异常: {e}")
                time.sleep(1)

    def _full_sync_loop(self):
        """全量同步循环"""
        while self.is_monitoring:
            try:
                current_time = time.time()

                # 检查是否需要进行全量同步
                if (current_time - self.last_full_sync) >= self.full_sync_interval:
                    if self.current_primary == self.local_node_name:
                        logger.info("开始定时全量数据同步检查...")
                        self._check_and_sync_data()
                        self.last_full_sync = current_time

                # 每10秒检查一次
                time.sleep(self.incremental_sync_interval)

            except Exception as e:
                logger.error(f"全量同步循环异常: {e}")
                time.sleep(10)

    def _check_and_sync_data(self):
        """检查并同步数据到备用节点"""
        try:
            # 获取所有备用节点
            secondary_nodes = [
                name for name, node in self.nodes.items()
                if node.role == DatabaseRole.SECONDARY and name != self.local_node_name
            ]

            if not secondary_nodes:
                logger.debug("没有备用节点需要同步")
                return

            # 获取主节点的数据统计
            primary_stats = self._get_database_stats(self.current_primary)
            if not primary_stats:
                logger.warning("无法获取主节点数据统计")
                return

            # 检查每个备用节点的数据一致性
            for secondary_node in secondary_nodes:
                try:
                    secondary_stats = self._get_database_stats(secondary_node)
                    if not secondary_stats:
                        logger.warning(f"无法获取备用节点 {secondary_node} 数据统计")
                        continue

                    # 深度检查数据一致性
                    inconsistencies = self._deep_check_data_consistency(
                        self.current_primary, secondary_node, primary_stats, secondary_stats
                    )

                    if inconsistencies:
                        logger.info(f"检测到数据不一致，开始同步数据到备用节点: {secondary_node}")
                        for inconsistency in inconsistencies:
                            logger.info(f"  {inconsistency}")

                        self._sync_bidirectional_data(secondary_node, primary_stats, secondary_stats)
                    else:
                        logger.debug(f"备用节点 {secondary_node} 数据已是最新")

                except Exception as e:
                    logger.error(f"检查备用节点 {secondary_node} 数据一致性失败: {e}")

        except Exception as e:
            logger.error(f"检查和同步数据失败: {e}")

    def _deep_check_data_consistency(self, primary_node: str, secondary_node: str,
                                   primary_stats: Dict[str, int], secondary_stats: Dict[str, int]) -> List[str]:
        """深度检查数据一致性"""
        inconsistencies = []

        try:
            for table_name in self.sync_tables:
                primary_count = primary_stats.get(table_name, 0)
                secondary_count = secondary_stats.get(table_name, 0)

                # 1. 检查记录数量差异
                if primary_count != secondary_count:
                    inconsistencies.append(
                        f"{table_name}: 记录数不一致 主节点({primary_count}) vs 备节点({secondary_count})"
                    )
                    continue

                # 2. 如果数量相同但大于0，检查最新记录的一致性
                if primary_count > 0:
                    latest_inconsistency = self._check_latest_records_consistency(
                        primary_node, secondary_node, table_name
                    )
                    if latest_inconsistency:
                        inconsistencies.append(latest_inconsistency)

                # 3. 检查ID范围一致性
                id_range_inconsistency = self._check_id_range_consistency(
                    primary_node, secondary_node, table_name
                )
                if id_range_inconsistency:
                    inconsistencies.append(id_range_inconsistency)

        except Exception as e:
            logger.error(f"深度一致性检查失败: {e}")
            inconsistencies.append(f"一致性检查异常: {e}")

        return inconsistencies

    def _check_latest_records_consistency(self, primary_node: str, secondary_node: str, table_name: str) -> Optional[str]:
        """检查最新记录的一致性"""
        try:
            primary_session = self.session_makers[primary_node]()
            secondary_session = self.session_makers[secondary_node]()

            try:
                from sqlalchemy import text

                # 获取最新的5条记录的ID和更新时间
                sql = f"""
                    SELECT id, updated_at
                    FROM {table_name}
                    ORDER BY id DESC
                    LIMIT 5
                """

                primary_result = primary_session.execute(text(sql)).fetchall()
                secondary_result = secondary_session.execute(text(sql)).fetchall()

                # 转换为集合进行比较
                primary_records = set(primary_result)
                secondary_records = set(secondary_result)

                if primary_records != secondary_records:
                    return f"{table_name}: 最新记录不一致"

                return None

            finally:
                primary_session.close()
                secondary_session.close()

        except Exception as e:
            logger.debug(f"检查 {table_name} 最新记录一致性失败: {e}")
            return None

    def _check_id_range_consistency(self, primary_node: str, secondary_node: str, table_name: str) -> Optional[str]:
        """检查ID范围一致性"""
        try:
            primary_session = self.session_makers[primary_node]()
            secondary_session = self.session_makers[secondary_node]()

            try:
                from sqlalchemy import text

                # 获取ID范围
                sql = f"SELECT MIN(id), MAX(id) FROM {table_name}"

                primary_result = primary_session.execute(text(sql)).fetchone()
                secondary_result = secondary_session.execute(text(sql)).fetchone()

                if primary_result != secondary_result:
                    return f"{table_name}: ID范围不一致 主节点{primary_result} vs 备节点{secondary_result}"

                return None

            finally:
                primary_session.close()
                secondary_session.close()

        except Exception as e:
            logger.debug(f"检查 {table_name} ID范围一致性失败: {e}")
            return None

    def _get_database_stats(self, node_name: str) -> Optional[Dict[str, int]]:
        """获取数据库统计信息"""
        try:
            if node_name not in self.session_makers:
                return None

            session = self.session_makers[node_name]()
            try:
                stats = {}

                # 统计所有配置的同步表
                for table_name in self.sync_tables:
                    try:
                        if table_name == 'images':
                            count = session.query(ImageModel).count()
                        elif table_name == 'categories':
                            from database.models.category import CategoryModel
                            count = session.query(CategoryModel).count()
                        elif table_name == 'crawl_sessions':
                            from database.models.crawl_session import CrawlSessionModel
                            count = session.query(CrawlSessionModel).count()
                        elif table_name == 'tags':
                            try:
                                from database.models.tag import TagModel
                                count = session.query(TagModel).count()
                            except ImportError:
                                # 如果TagModel不存在，使用原生SQL查询
                                result = session.execute(f"SELECT COUNT(*) FROM {table_name}")
                                count = result.scalar()
                        else:
                            # 对于其他表，使用原生SQL查询
                            result = session.execute(f"SELECT COUNT(*) FROM {table_name}")
                            count = result.scalar()

                        stats[table_name] = count

                    except Exception as e:
                        logger.warning(f"无法统计表 {table_name}: {e}")
                        stats[table_name] = 0

                return stats

            finally:
                session.close()

        except Exception as e:
            logger.error(f"获取节点 {node_name} 数据统计失败: {e}")
            return None

    def _sync_missing_data(self, target_node: str, primary_stats: Dict[str, int], secondary_stats: Dict[str, int]):
        """同步缺失的数据到目标节点"""
        try:
            total_synced = 0

            # 同步所有配置的表
            for table_name in self.sync_tables:
                if table_name in primary_stats:
                    primary_count = primary_stats[table_name]
                    secondary_count = secondary_stats.get(table_name, 0)

                    if secondary_count < primary_count:
                        missing_count = primary_count - secondary_count
                        logger.info(f"需要同步 {missing_count} 条 {table_name} 记录到 {target_node}")

                        # 立即执行同步
                        synced_count = self._sync_table_missing_records(
                            table_name, target_node, missing_count
                        )
                        total_synced += synced_count

                        logger.info(f"已同步 {synced_count} 条 {table_name} 记录到 {target_node}")

            if total_synced > 0:
                logger.info(f"总共同步了 {total_synced} 条记录到 {target_node}")
            else:
                logger.debug(f"没有需要同步的数据到 {target_node}")

        except Exception as e:
            logger.error(f"同步缺失数据到 {target_node} 失败: {e}")

    def _sync_bidirectional_data(self, target_node: str, primary_stats: Dict[str, int], secondary_stats: Dict[str, int]):
        """双向同步数据"""
        try:
            total_synced = 0

            # 同步所有配置的表
            for table_name in self.sync_tables:
                if table_name in primary_stats and table_name in secondary_stats:
                    primary_count = primary_stats[table_name]
                    secondary_count = secondary_stats[table_name]

                    if primary_count > secondary_count:
                        # 主节点数据多，同步到备用节点
                        missing_count = primary_count - secondary_count
                        logger.info(f"同步 {missing_count} 条 {table_name} 记录：主节点 -> {target_node}")

                        synced_count = self._sync_table_missing_records(
                            table_name, target_node, missing_count
                        )
                        total_synced += synced_count

                    elif secondary_count > primary_count:
                        # 备用节点数据多，同步到主节点
                        missing_count = secondary_count - primary_count
                        logger.info(f"同步 {missing_count} 条 {table_name} 记录：{target_node} -> 主节点")

                        synced_count = self._sync_table_missing_records_reverse(
                            table_name, target_node, missing_count
                        )
                        total_synced += synced_count

                    else:
                        # 数量相同，但可能有内容差异，执行内容同步
                        if primary_count > 0:
                            synced_count = self._sync_table_content_differences(
                                table_name, target_node
                            )
                            total_synced += synced_count

            if total_synced > 0:
                logger.info(f"双向同步完成，总共处理了 {total_synced} 条记录")
            else:
                logger.debug(f"双向同步检查完成，无需同步数据")

        except Exception as e:
            logger.error(f"双向同步数据失败: {e}")

    def _sync_table_missing_records_reverse(self, table_name: str, source_node: str, missing_count: int) -> int:
        """反向同步：从备用节点同步到主节点"""
        try:
            # 获取源节点（备用）和目标节点（主）的会话
            source_session = self.session_makers[source_node]()
            target_session = self.session_makers[self.current_primary]()

            try:
                # 获取主节点的最大ID
                from sqlalchemy import text
                max_id_result = target_session.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"))
                max_id = max_id_result.scalar() or 0

                # 获取备用节点中ID大于主节点最大ID的记录
                missing_records = self._get_records_above_id(source_session, table_name, max_id, missing_count)

                if not missing_records:
                    logger.debug(f"没有找到需要反向同步的 {table_name} 记录")
                    return 0

                # 直接插入到主节点数据库
                synced_count = 0
                for record in missing_records:
                    try:
                        # 序列化记录
                        record_data = self._serialize_model(record)

                        # 构建插入SQL（使用命名参数）
                        columns = list(record_data.keys())
                        placeholders = ', '.join([f':{col}' for col in columns])
                        column_names = ', '.join(columns)

                        sql = f"""
                            INSERT INTO {table_name} ({column_names})
                            VALUES ({placeholders})
                            ON CONFLICT (id) DO UPDATE SET
                        """

                        # 添加更新子句
                        update_clauses = []
                        for col in columns:
                            if col != 'id':
                                update_clauses.append(f"{col} = EXCLUDED.{col}")

                        if update_clauses:
                            sql += ', '.join(update_clauses)
                        else:
                            sql = f"""
                                INSERT INTO {table_name} ({column_names})
                                VALUES ({placeholders})
                                ON CONFLICT (id) DO NOTHING
                            """

                        # 执行SQL
                        target_session.execute(text(sql), record_data)
                        synced_count += 1

                    except Exception as e:
                        logger.error(f"反向同步记录失败 {table_name} ID {getattr(record, 'id', 'N/A')}: {e}")

                # 提交事务
                target_session.commit()

                # 同步完成后，更新主节点的序列
                if synced_count > 0:
                    self._update_sequence_after_sync(target_session, table_name)

                return synced_count

            finally:
                source_session.close()
                target_session.close()

        except Exception as e:
            logger.error(f"反向同步表 {table_name} 失败: {e}")
            return 0

    def _get_records_above_id(self, session, table_name: str, min_id: int, limit: int):
        """获取ID大于指定值的记录"""
        try:
            if table_name == 'images':
                return session.query(ImageModel).filter(
                    ImageModel.id > min_id
                ).order_by(ImageModel.id).limit(limit).all()
            elif table_name == 'crawl_sessions':
                from database.models.crawl_session import CrawlSessionModel
                return session.query(CrawlSessionModel).filter(
                    CrawlSessionModel.id > min_id
                ).order_by(CrawlSessionModel.id).limit(limit).all()
            elif table_name == 'categories':
                from database.models.category import CategoryModel
                return session.query(CategoryModel).filter(
                    CategoryModel.id > min_id
                ).order_by(CategoryModel.id).limit(limit).all()
            elif table_name == 'tags':
                from database.models.tag import TagModel
                return session.query(TagModel).filter(
                    TagModel.id > min_id
                ).order_by(TagModel.id).limit(limit).all()
            else:
                logger.warning(f"不支持的表: {table_name}")
                return []
        except Exception as e:
            logger.error(f"获取 {table_name} 记录失败: {e}")
            return []

    def _sync_table_content_differences(self, table_name: str, target_node: str) -> int:
        """同步表内容差异（当数量相同但内容不同时）"""
        try:
            # 获取最新的几条记录进行对比和同步
            primary_session = self.session_makers[self.current_primary]()
            target_session = self.session_makers[target_node]()

            try:
                from sqlalchemy import text

                # 获取最新的10条记录进行对比
                sql = f"""
                    SELECT id, updated_at
                    FROM {table_name}
                    ORDER BY id DESC
                    LIMIT 10
                """

                primary_records = primary_session.execute(text(sql)).fetchall()
                target_records = target_session.execute(text(sql)).fetchall()

                # 找出差异记录的ID
                primary_set = set(primary_records)
                target_set = set(target_records)

                different_ids = []

                # 找出主节点有但备用节点没有或不同的记录
                for record in primary_records:
                    if record not in target_set:
                        different_ids.append(record[0])  # ID

                if different_ids:
                    logger.info(f"发现 {len(different_ids)} 条 {table_name} 记录需要内容同步")

                    # 同步这些记录
                    synced_count = 0
                    for record_id in different_ids:
                        if self._sync_single_record(table_name, record_id, target_node):
                            synced_count += 1

                    return synced_count

                return 0

            finally:
                primary_session.close()
                target_session.close()

        except Exception as e:
            logger.error(f"同步 {table_name} 内容差异失败: {e}")
            return 0

    def _sync_single_record(self, table_name: str, record_id: int, target_node: str) -> bool:
        """同步单条记录"""
        try:
            primary_session = self.session_makers[self.current_primary]()
            target_session = self.session_makers[target_node]()

            try:
                # 获取主节点的记录
                record = self._get_record_by_id(primary_session, table_name, record_id)
                if not record:
                    return False

                # 序列化并同步到目标节点
                record_data = self._serialize_model(record)

                # 构建更新SQL
                columns = list(record_data.keys())
                placeholders = ', '.join([f':{col}' for col in columns])
                column_names = ', '.join(columns)

                sql = f"""
                    INSERT INTO {table_name} ({column_names})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO UPDATE SET
                """

                # 添加更新子句
                update_clauses = []
                for col in columns:
                    if col != 'id':
                        update_clauses.append(f"{col} = EXCLUDED.{col}")

                if update_clauses:
                    sql += ', '.join(update_clauses)

                from sqlalchemy import text
                target_session.execute(text(sql), record_data)
                target_session.commit()

                return True

            finally:
                primary_session.close()
                target_session.close()

        except Exception as e:
            logger.error(f"同步单条记录失败 {table_name} ID {record_id}: {e}")
            return False

    def _get_record_by_id(self, session, table_name: str, record_id: int):
        """根据ID获取记录"""
        try:
            if table_name == 'images':
                return session.query(ImageModel).filter(ImageModel.id == record_id).first()
            elif table_name == 'crawl_sessions':
                from database.models.crawl_session import CrawlSessionModel
                return session.query(CrawlSessionModel).filter(CrawlSessionModel.id == record_id).first()
            elif table_name == 'categories':
                from database.models.category import CategoryModel
                return session.query(CategoryModel).filter(CategoryModel.id == record_id).first()
            elif table_name == 'tags':
                from database.models.tag import TagModel
                return session.query(TagModel).filter(TagModel.id == record_id).first()
            else:
                return None
        except Exception as e:
            logger.error(f"获取 {table_name} 记录 ID {record_id} 失败: {e}")
            return None

    def _sync_table_missing_records(self, table_name: str, target_node: str, missing_count: int) -> int:
        """同步指定表的缺失记录"""
        try:
            # 获取主节点的缺失记录
            primary_session = self.session_makers[self.current_primary]()
            target_session = self.session_makers[target_node]()

            try:
                # 获取目标节点的最大ID
                from sqlalchemy import text
                max_id_result = target_session.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"))
                max_id = max_id_result.scalar() or 0

                # 获取主节点中ID大于目标节点最大ID的记录
                if table_name == 'images':
                    missing_records = primary_session.query(ImageModel).filter(
                        ImageModel.id > max_id
                    ).order_by(ImageModel.id).limit(missing_count).all()
                elif table_name == 'crawl_sessions':
                    from database.models.crawl_session import CrawlSessionModel
                    missing_records = primary_session.query(CrawlSessionModel).filter(
                        CrawlSessionModel.id > max_id
                    ).order_by(CrawlSessionModel.id).limit(missing_count).all()
                elif table_name == 'categories':
                    from database.models.category import CategoryModel
                    missing_records = primary_session.query(CategoryModel).filter(
                        CategoryModel.id > max_id
                    ).order_by(CategoryModel.id).limit(missing_count).all()
                elif table_name == 'tags':
                    from database.models.tag import TagModel
                    missing_records = primary_session.query(TagModel).filter(
                        TagModel.id > max_id
                    ).order_by(TagModel.id).limit(missing_count).all()
                else:
                    logger.warning(f"不支持的表: {table_name}")
                    return 0

                if not missing_records:
                    logger.debug(f"没有找到需要同步的 {table_name} 记录")
                    return 0

                # 直接插入到目标数据库
                synced_count = 0
                for record in missing_records:
                    try:
                        # 序列化记录
                        record_data = self._serialize_model(record)

                        # 构建插入SQL（使用命名参数）
                        columns = list(record_data.keys())

                        # 使用命名参数占位符
                        placeholders = ', '.join([f':{col}' for col in columns])
                        column_names = ', '.join(columns)

                        sql = f"""
                            INSERT INTO {table_name} ({column_names})
                            VALUES ({placeholders})
                            ON CONFLICT (id) DO UPDATE SET
                        """

                        # 添加更新子句
                        update_clauses = []
                        for col in columns:
                            if col != 'id':
                                update_clauses.append(f"{col} = EXCLUDED.{col}")

                        if update_clauses:
                            sql += ', '.join(update_clauses)
                        else:
                            sql = f"""
                                INSERT INTO {table_name} ({column_names})
                                VALUES ({placeholders})
                                ON CONFLICT (id) DO NOTHING
                            """

                        # 执行SQL
                        target_session.execute(text(sql), record_data)
                        synced_count += 1

                    except Exception as e:
                        logger.error(f"同步记录失败 {table_name} ID {getattr(record, 'id', 'N/A')}: {e}")

                # 提交事务
                target_session.commit()

                # 同步完成后，更新目标数据库的序列
                if synced_count > 0:
                    self._update_sequence_after_sync(target_session, table_name)

                return synced_count

            finally:
                primary_session.close()
                target_session.close()

        except Exception as e:
            logger.error(f"同步表 {table_name} 缺失记录失败: {e}")
            return 0

    def _update_sequence_after_sync(self, session, table_name: str):
        """同步后更新序列值"""
        try:
            # 获取表的最大ID
            from sqlalchemy import text
            result = session.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"))
            max_id = result.scalar()

            if max_id > 0:
                # 构建序列名（PostgreSQL标准命名）
                sequence_name = f"{table_name}_id_seq"

                # 设置序列值为最大ID + 1
                new_sequence_value = max_id + 1
                session.execute(text(f"SELECT setval('{sequence_name}', {new_sequence_value})"))

                logger.info(f"已更新 {table_name} 序列值为: {new_sequence_value}")

        except Exception as e:
            logger.warning(f"更新 {table_name} 序列失败: {e}")

    def _sync_sequence_for_insert(self, session, table_name: str, record_id: int):
        """插入记录后同步序列"""
        try:
            from sqlalchemy import text

            # 构建序列名
            sequence_name = f"{table_name}_id_seq"

            # 获取当前序列值
            result = session.execute(text(f"SELECT last_value FROM {sequence_name}"))
            current_sequence = result.scalar()

            # 如果插入的ID大于等于当前序列值，更新序列
            if record_id >= current_sequence:
                new_sequence_value = record_id + 1
                session.execute(text(f"SELECT setval('{sequence_name}', {new_sequence_value})"))
                logger.debug(f"同步后更新 {table_name} 序列值为: {new_sequence_value}")

        except Exception as e:
            logger.warning(f"同步插入后更新 {table_name} 序列失败: {e}")

    def _serialize_model(self, model_instance) -> Dict[str, Any]:
        """序列化模型实例为字典"""
        data = {}
        for column in model_instance.__table__.columns:
            value = getattr(model_instance, column.name, None)
            if value is not None:
                # 处理datetime对象
                if hasattr(value, 'isoformat'):
                    data[column.name] = value.isoformat()
                # 处理字典和列表（JSON字段）
                elif isinstance(value, (dict, list)):
                    import json
                    data[column.name] = json.dumps(value)
                else:
                    data[column.name] = value
        return data

    def _serialize_image_model(self, image: ImageModel) -> Dict[str, Any]:
        """序列化ImageModel为字典（保持向后兼容）"""
        return self._serialize_model(image)

    def _process_sync_operation(self, operation: SyncOperation):
        """处理同步操作"""
        try:
            for target_node in operation.target_nodes:
                if target_node == self.local_node_name:
                    # 本地节点，直接执行
                    self._apply_local_operation(operation)
                else:
                    # 远程节点，发送同步请求
                    self._send_sync_request(target_node, operation)

            operation.status = "completed"

        except Exception as e:
            logger.error(f"处理同步操作失败: {e}")
            operation.status = "failed"

    def _apply_local_operation(self, operation: SyncOperation):
        """在本地应用同步操作"""
        try:
            with self.get_session() as session:
                if operation.operation_type == "INSERT":
                    # 插入操作
                    if operation.table_name == "images":
                        image = ImageModel(**operation.data)
                        session.add(image)

                elif operation.operation_type == "UPDATE":
                    # 更新操作
                    if operation.table_name == "images":
                        image_id = operation.data.get("id")
                        if image_id:
                            session.query(ImageModel).filter(
                                ImageModel.id == image_id
                            ).update(operation.data)

                elif operation.operation_type == "DELETE":
                    # 删除操作
                    if operation.table_name == "images":
                        image_id = operation.data.get("id")
                        if image_id:
                            session.query(ImageModel).filter(
                                ImageModel.id == image_id
                            ).delete()

                session.commit()
                logger.debug(f"本地应用同步操作成功: {operation.operation_id}")

        except Exception as e:
            logger.error(f"本地应用同步操作失败: {e}")
            raise

    def _send_sync_request(self, target_node: str, operation: SyncOperation):
        """直接通过数据库连接执行同步操作"""
        try:
            if target_node not in self.session_makers:
                logger.warning(f"目标节点 {target_node} 没有数据库连接")
                return False

            session = self.session_makers[target_node]()
            try:
                success = self._execute_sync_operation_on_node(session, operation)
                if success:
                    logger.debug(f"同步操作执行成功: {target_node} - {operation.operation_type} {operation.table_name}")
                else:
                    logger.warning(f"同步操作执行失败: {target_node} - {operation.operation_type} {operation.table_name}")
                return success

            finally:
                session.close()

        except Exception as e:
            logger.error(f"执行同步操作到 {target_node} 失败: {e}")
            return False

    def _execute_sync_operation_on_node(self, session, operation: SyncOperation):
        """在指定节点上执行同步操作"""
        try:
            if operation.operation_type == "INSERT":
                return self._execute_insert_operation(session, operation)
            elif operation.operation_type == "UPDATE":
                return self._execute_update_operation(session, operation)
            elif operation.operation_type == "DELETE":
                return self._execute_delete_operation(session, operation)
            else:
                logger.warning(f"未知的同步操作类型: {operation.operation_type}")
                return False

        except Exception as e:
            logger.error(f"执行同步操作失败: {e}")
            session.rollback()
            return False

    def _execute_insert_operation(self, session, operation: SyncOperation):
        """执行插入操作"""
        try:
            table_name = operation.table_name
            data = operation.data

            # 构建插入SQL
            columns = list(data.keys())
            values = list(data.values())

            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join(columns)

            sql = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT (id) DO UPDATE SET
            """

            # 添加更新子句
            update_clauses = []
            for col in columns:
                if col != 'id':
                    update_clauses.append(f"{col} = EXCLUDED.{col}")

            if update_clauses:
                sql += ', '.join(update_clauses)
            else:
                sql = f"""
                    INSERT INTO {table_name} ({column_names})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO NOTHING
                """

            from sqlalchemy import text
            session.execute(text(sql), values)
            session.commit()

            # 同步后更新序列
            if 'id' in data:
                self._sync_sequence_for_insert(session, table_name, data['id'])

            return True

        except Exception as e:
            logger.error(f"执行INSERT操作失败: {e}")
            session.rollback()
            return False

    def _execute_update_operation(self, session, operation: SyncOperation):
        """执行更新操作"""
        try:
            table_name = operation.table_name
            data = operation.data

            if 'id' not in data:
                logger.warning("UPDATE操作缺少ID字段")
                return False

            record_id = data['id']
            update_data = {k: v for k, v in data.items() if k != 'id'}

            if not update_data:
                logger.debug("没有需要更新的字段")
                return True

            # 构建更新SQL
            set_clauses = []
            values = []

            for col, value in update_data.items():
                set_clauses.append(f"{col} = %s")
                values.append(value)

            values.append(record_id)  # WHERE条件的值

            sql = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = %s"

            from sqlalchemy import text
            result = session.execute(text(sql), values)
            session.commit()

            if result.rowcount > 0:
                return True
            else:
                logger.debug(f"UPDATE操作未影响任何记录: {table_name} id={record_id}")
                return True  # 不算错误

        except Exception as e:
            logger.error(f"执行UPDATE操作失败: {e}")
            session.rollback()
            return False

    def _execute_delete_operation(self, session, operation: SyncOperation):
        """执行删除操作"""
        try:
            table_name = operation.table_name
            data = operation.data

            if 'id' not in data:
                logger.warning("DELETE操作缺少ID字段")
                return False

            record_id = data['id']
            sql = f"DELETE FROM {table_name} WHERE id = %s"

            from sqlalchemy import text
            result = session.execute(text(sql), [record_id])
            session.commit()

            if result.rowcount > 0:
                return True
            else:
                logger.debug(f"DELETE操作未影响任何记录: {table_name} id={record_id}")
                return True  # 记录可能已经不存在，不算错误

        except Exception as e:
            logger.error(f"执行DELETE操作失败: {e}")
            session.rollback()
            return False

    def _check_replication_lag(self):
        """检查复制延迟"""
        if not self.current_primary:
            return

        try:
            # 获取主节点的最新时间戳
            primary_timestamp = self._get_node_timestamp(self.current_primary)

            # 检查所有备节点的延迟
            for node_name, node in self.nodes.items():
                if (node_name != self.current_primary and
                    node.role == DatabaseRole.SECONDARY and
                    self._is_node_healthy(node_name)):

                    secondary_timestamp = self._get_node_timestamp(node_name)
                    if primary_timestamp and secondary_timestamp:
                        # 确保两个时间戳都是同一类型（都带时区或都不带时区）
                        if primary_timestamp.tzinfo is None and secondary_timestamp.tzinfo is not None:
                            primary_timestamp = primary_timestamp.replace(tzinfo=timezone.utc)
                        elif primary_timestamp.tzinfo is not None and secondary_timestamp.tzinfo is None:
                            secondary_timestamp = secondary_timestamp.replace(tzinfo=timezone.utc)

                        lag = (primary_timestamp - secondary_timestamp).total_seconds()
                        node.replication_lag = max(0, lag)

                        # 检查延迟阈值
                        if lag > 60:  # 超过60秒认为延迟过高
                            logger.warning(f"节点 {node_name} 复制延迟过高: {lag:.2f}秒")

        except Exception as e:
            logger.error(f"检查复制延迟失败: {e}")

    def _get_node_timestamp(self, node_name: str) -> Optional[datetime]:
        """获取节点的最新时间戳"""
        try:
            if node_name not in self.engines:
                return None

            engine = self.engines[node_name]
            with engine.connect() as conn:
                result = conn.execute(text("SELECT NOW()"))
                return result.fetchone()[0]

        except Exception as e:
            logger.debug(f"获取节点 {node_name} 时间戳失败: {e}")
            return None

    # 公共API接口

    @contextmanager
    def get_session(self, read_only: bool = False):
        """
        获取数据库会话

        Args:
            read_only: 是否为只读操作，只读操作可以路由到备节点
        """
        target_node = self._select_node_for_operation(read_only)

        if not target_node or target_node not in self.session_makers:
            raise Exception("没有可用的数据库节点")

        session = self.session_makers[target_node]()

        # 如果是写操作且当前是主节点，包装session以自动触发同步
        if not read_only and target_node == self.current_primary:
            session = AutoSyncSession(session, self)

        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    def _select_node_for_operation(self, read_only: bool = False) -> Optional[str]:
        """选择执行操作的节点"""
        if read_only:
            # 只读操作，可以使用备节点进行负载均衡
            available_nodes = [
                name for name, node in self.nodes.items()
                if self._is_node_healthy(name)
            ]

            if available_nodes:
                # 简单的轮询负载均衡
                import random
                return random.choice(available_nodes)

        # 写操作必须使用主节点
        if self.current_primary and self._is_node_healthy(self.current_primary):
            return self.current_primary

        return None

    def add_sync_operation(self, operation_type: str, table_name: str, data: Dict[str, Any]):
        """添加同步操作到队列"""
        operation = SyncOperation(
            operation_id=f"{int(time.time() * 1000)}_{self.local_node_name}",
            timestamp=datetime.now(timezone.utc),
            operation_type=operation_type,
            table_name=table_name,
            data=data,
            source_node=self.local_node_name,
            target_nodes=[
                name for name, node in self.nodes.items()
                if name != self.local_node_name and
                   node.role == DatabaseRole.SECONDARY
            ]
        )

        with self.sync_lock:
            self.sync_queue.append(operation)

        logger.debug(f"添加同步操作: {operation.operation_id}")

    def manual_failover(self, target_node: str) -> bool:
        """手动故障转移"""
        if target_node not in self.nodes:
            logger.error(f"目标节点不存在: {target_node}")
            return False

        if not self._is_node_healthy(target_node):
            logger.error(f"目标节点不健康: {target_node}")
            return False

        current_primary = self.current_primary
        return self._execute_failover(current_primary, target_node)

    def get_cluster_status(self) -> Dict[str, Any]:
        """获取集群状态"""
        return {
            "current_primary": self.current_primary,
            "local_node": self.local_node_name,
            "nodes": {
                name: {
                    "role": node.role.value,
                    "health_status": node.health_status.value,
                    "priority": node.priority,
                    "replication_lag": node.replication_lag,
                    "failure_count": node.failure_count,
                    "last_check": node.last_check.isoformat() if node.last_check else None,
                    "last_error": node.last_error,
                    "server": {
                        "host": node.server.host,
                        "port": node.server.port,
                        "location": node.server.location
                    }
                }
                for name, node in self.nodes.items()
            },
            "sync_queue_size": len(self.sync_queue),
            "is_monitoring": self.is_monitoring
        }

    def add_failover_callback(self, callback: Callable):
        """添加故障转移回调函数"""
        self.failover_callbacks.append(callback)

    def remove_failover_callback(self, callback: Callable):
        """移除故障转移回调函数"""
        if callback in self.failover_callbacks:
            self.failover_callbacks.remove(callback)

    def force_sync_all(self):
        """强制同步所有数据到备节点"""
        if not self.current_primary:
            logger.error("没有主节点，无法执行全量同步")
            return False

        if self.current_primary != self.local_node_name:
            logger.warning("当前节点不是主节点，无法执行全量同步")
            return False

        try:
            logger.info("开始强制全量数据同步...")

            # 获取主节点的所有数据
            with self.get_session(read_only=True) as session:
                images = session.query(ImageModel).all()
                total_images = len(images)

                if total_images == 0:
                    logger.info("主数据库为空，无需同步")
                    return True

                logger.info(f"准备同步 {total_images} 条图片记录")

                # 批量处理，避免内存占用过大
                batch_size = 100
                synced_count = 0

                for i in range(0, total_images, batch_size):
                    batch_images = images[i:i + batch_size]

                    for image in batch_images:
                        image_data = self._serialize_image_model(image)
                        self.add_sync_operation("INSERT", "images", image_data)
                        synced_count += 1

                    logger.info(f"已处理 {synced_count}/{total_images} 条记录")

            logger.info(f"全量同步操作已添加到队列，共 {synced_count} 条记录")
            return True

        except Exception as e:
            logger.error(f"强制全量同步失败: {e}")
            return False

    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        with self.sync_lock:
            queue_size = len(self.sync_queue)

        return {
            "auto_sync_enabled": self.auto_sync_enabled,
            "sync_queue_size": queue_size,
            "last_full_sync": self.last_full_sync,
            "full_sync_interval": self.full_sync_interval,
            "current_primary": self.current_primary,
            "local_node": self.local_node_name,
            "is_monitoring": self.is_monitoring
        }

    def enable_auto_sync(self):
        """启用自动同步"""
        self.auto_sync_enabled = True
        logger.info("自动数据同步已启用")

    def disable_auto_sync(self):
        """禁用自动同步"""
        self.auto_sync_enabled = False
        logger.info("自动数据同步已禁用")
