# 图像爬虫分布式高可用系统技术文档

## 📋 目录

1. [系统架构概览](#系统架构概览)
2. [核心功能模块详解](#核心功能模块详解)
3. [文件结构和功能说明](#文件结构和功能说明)
4. [工作流程详述](#工作流程详述)
5. [技术实现细节](#技术实现细节)
6. [配置参数说明](#配置参数说明)
7. [部署和运维指南](#部署和运维指南)

---

## 🏗️ 系统架构概览

### 整体架构设计

本系统采用分布式高可用架构，实现了跨服务器的数据库自动故障转移和实时数据同步。

```mermaid
graph TB
    subgraph "主服务器 (113.29.231.99)"
        A[主数据库 PostgreSQL:5432]
        B[HA API服务器:8001]
        C[主应用API:8000]
        D[图像爬虫引擎]
    end
    
    subgraph "备服务器 (113.29.232.245)"
        E[备数据库 PostgreSQL:5432]
        F[HA API服务器:8001]
        G[备应用API:8000]
        H[图像爬虫引擎]
    end
    
    subgraph "分布式HA管理器"
        I[健康监控]
        J[故障检测]
        K[自动切换]
        L[数据同步]
    end
    
    A <--> E
    B <--> F
    I --> A
    I --> E
    J --> K
    K --> L
    
    subgraph "外部服务"
        M[图像源网站]
        N[文件存储系统]
    end
    
    D --> M
    D --> N
    H --> M
    H --> N
```

### 主备数据库分布式部署架构

- **主数据库**: PostgreSQL 16 @ 113.29.231.99:5432
- **备数据库**: PostgreSQL 16 @ 113.29.232.245:5432
- **认证信息**: postgres用户，密码Abcdefg6
- **数据库名**: image_crawler

### 数据同步和故障转移机制

1. **实时健康监控**: 每5秒检查一次所有数据库节点
2. **智能故障检测**: 连续3次连接失败自动触发故障转移
3. **零停机切换**: 主数据库故障时自动切换到备用数据库
4. **双向数据同步**: 支持主备数据库间的双向数据同步

---

## 🔧 核心功能模块详解

### 1. 图像爬取功能实现原理

#### 核心组件

- **AsyncCrawler**: 异步爬虫引擎，支持并发爬取
- **Spider**: 网页内容解析和图片链接提取
- **Downloader**: 图片下载和存储管理
- **TaskScheduler**: 任务调度和并发控制

#### 工作原理

```python
# 爬虫主流程
class ImageCrawler:
    def __init__(self, config_file=None, db_manager=None):
        # 使用外部HA数据库管理器
        if db_manager is not None:
            self.db_manager = db_manager
            logger.info("✅ 使用外部数据库管理器（HA系统）")
        else:
            # 使用默认数据库管理器
            self.db_manager = EnhancedDatabaseManager(
                database_url, self.settings.disaster_recovery
            )
```

### 2. 数据库灾难恢复系统工作机制

#### 分布式HA管理器

<augment_code_snippet path="database/distributed_ha_manager.py" mode="EXCERPT">
````python
class DistributedHAManager:
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
````
</augment_code_snippet>

#### 健康监控机制

<augment_code_snippet path="database/distributed_ha_manager.py" mode="EXCERPT">
````python
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
````
</augment_code_snippet>

### 3. 自动故障转移流程

#### 故障检测触发条件

1. **连接失败**: 连续3次数据库连接失败
2. **响应超时**: 数据库响应时间超过30秒
3. **复制延迟**: 数据同步延迟超过60秒阈值

#### 故障转移执行流程

<augment_code_snippet path="database/failover_manager.py" mode="EXCERPT">
````python
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
````
</augment_code_snippet>

### 4. 双向数据同步机制

#### 同步操作类型

- **INSERT**: 新增记录同步
- **UPDATE**: 更新记录同步
- **DELETE**: 删除记录同步
- **FULL_SYNC**: 全量数据同步

#### 数据一致性检查算法

系统实现了多层次的数据一致性检查：

1. **记录数量差异检测**: 比较主备数据库的记录总数
2. **最新记录不匹配检测**: 检查最新插入记录的一致性
3. **ID范围不一致检测**: 验证记录ID范围的完整性

---

## 📁 文件结构和功能说明

### 核心启动文件

#### start_simple_ha.py - 系统启动入口

<augment_code_snippet path="start_simple_ha.py" mode="EXCERPT">
````python
def start_ha_system():
    """启动HA系统"""
    try:
        print("启动PostgreSQL分布式高可用数据库系统")
        
        # 1. 加载配置
        from config.ha_config_loader import load_ha_config
        nodes, local_node_name, config = load_ha_config()
        
        # 2. 创建HA管理器
        from database.distributed_ha_manager import DistributedHAManager
        ha_manager = DistributedHAManager(nodes, local_node_name, config)
        ha_manager.start_monitoring()
        
        # 3. 启动HA API服务器
        from database.ha_api_server import HAAPIServer
        ha_api_server = HAAPIServer(ha_manager, ha_api_port)
        
        # 4. 启动主应用API服务器
        import uvicorn
        from api import app
        uvicorn.run(app, host="0.0.0.0", port=8000)
````
</augment_code_snippet>

### 配置文件系统

#### distributed_ha_config.yaml - 分布式HA配置

<augment_code_snippet path="config/distributed_ha_config.yaml" mode="EXCERPT">
````yaml
# 本地节点配置 (当前运行的节点)
local_node: "primary_node"

# 数据库节点配置
nodes:
  # 主节点 (PostgreSQL 服务器1)
  primary_node:
    name: "primary_node"
    role: "primary"
    priority: 1
    server:
      host: "113.29.231.99"
      port: 5432
      api_port: 8001
    database_url: "postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler"
    max_connections: 100
    connection_timeout: 30
    sync_mode: "async"
    health_check_interval: 5
    failure_threshold: 3
    is_active: true

  # 备节点 (PostgreSQL 服务器2)
  backup_node:
    name: "backup_node"
    role: "secondary"
    priority: 2
    server:
      host: "113.29.232.245"
      port: 5432
      api_port: 8001
    database_url: "postgresql://postgres:Abcdefg6@113.29.232.245:5432/image_crawler"
````
</augment_code_snippet>

### 数据库管理模块

#### distributed_ha_manager.py - 分布式HA核心管理器

主要功能：
- 节点健康监控和故障检测
- 自动故障转移和主节点选举
- 数据同步队列管理
- 读写操作路由

#### failover_manager.py - 故障转移管理器

主要功能：
- 故障检测和阈值管理
- 故障转移策略执行
- 故障转移历史记录
- 自动恢复机制

#### ha_api_server.py - HA API服务器

提供RESTful API接口：
- `/api/status` - 集群状态查询
- `/api/failover` - 手动故障转移
- `/api/sync` - 数据同步控制
- `/api/health` - 健康检查

### 爬虫引擎模块

#### main_crawler.py - 主爬虫类

集成HA数据库管理器，支持：
- 外部数据库管理器注入
- 任务调度和并发控制
- 图片下载和存储管理
- 爬取会话管理

---

## 🔄 工作流程详述

### 系统启动流程

1. **配置加载**: 读取distributed_ha_config.yaml配置文件
2. **数据库连接测试**: 验证主备数据库连接可用性
3. **HA管理器初始化**: 创建分布式HA管理器实例
4. **监控启动**: 启动健康监控和数据同步线程
5. **API服务器启动**: 启动HA API服务器(8001端口)和主应用API(8000端口)
6. **系统状态显示**: 展示集群状态和节点信息

### 数据一致性检查执行机制

系统定期执行数据一致性检查，包括：

1. **自动检查**: 每300秒执行一次全量同步检查
2. **手动触发**: 通过API接口手动触发检查
3. **故障后检查**: 故障转移完成后自动执行检查

### 故障检测和自动切换触发条件

#### 故障检测条件

- 数据库连接失败连续3次
- 查询响应时间超过30秒
- 网络连接中断超过阈值时间

#### 自动切换流程

1. **故障检测**: 监控线程检测到主节点故障
2. **备节点选择**: 按优先级选择最佳备用节点
3. **连接切换**: 将所有数据库操作路由到备节点
4. **状态更新**: 更新集群状态和节点角色
5. **通知机制**: 记录故障转移事件和日志

### 数据同步时机和策略

#### 同步时机

- **实时同步**: 写操作完成后立即触发同步
- **批量同步**: 累积多个操作后批量同步
- **定时同步**: 定期执行全量数据同步

#### 同步策略

- **异步复制**: 默认模式，性能优先
- **同步复制**: 数据一致性优先
- **半同步复制**: 平衡性能和一致性

---

## ⚙️ 技术实现细节

### PostgreSQL 16双服务器配置

#### 主服务器配置 (113.29.231.99:5432)

```sql
-- 数据库创建
CREATE DATABASE image_crawler;
CREATE USER postgres WITH PASSWORD 'Abcdefg6';
GRANT ALL PRIVILEGES ON DATABASE image_crawler TO postgres;

-- 表结构
CREATE TABLE images (
    id SERIAL PRIMARY KEY,
    url VARCHAR(2048) NOT NULL,
    filename VARCHAR(255),
    file_path VARCHAR(512),
    file_size BIGINT,
    width INTEGER,
    height INTEGER,
    format VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 备服务器配置 (113.29.232.245:5432)

备服务器采用相同的数据库结构和配置，通过逻辑复制保持数据同步。

### 数据一致性检查算法详解

#### 记录数量差异检测

```python
def check_record_count_consistency(self):
    """检查记录数量一致性"""
    primary_count = self.get_table_count(self.primary_node, 'images')
    backup_count = self.get_table_count(self.backup_node, 'images')
    
    if primary_count != backup_count:
        logger.warning(f"记录数量不一致: 主库{primary_count}, 备库{backup_count}")
        return False
    return True
```

#### 最新记录不匹配检测

```python
def check_latest_record_consistency(self):
    """检查最新记录一致性"""
    primary_latest = self.get_latest_record(self.primary_node)
    backup_latest = self.get_latest_record(self.backup_node)
    
    if primary_latest != backup_latest:
        logger.warning("最新记录不匹配")
        return False
    return True
```

#### ID范围不一致检测

```python
def check_id_range_consistency(self):
    """检查ID范围一致性"""
    primary_range = self.get_id_range(self.primary_node)
    backup_range = self.get_id_range(self.backup_node)
    
    if primary_range != backup_range:
        logger.warning(f"ID范围不一致: 主库{primary_range}, 备库{backup_range}")
        return False
    return True
```

### 图像数据存储策略考虑因素

#### 存储方案对比

1. **数据库直接存储**
   - 优点: 数据一致性好，事务支持
   - 缺点: 数据库体积大，性能影响

2. **文件系统存储**
   - 优点: 性能好，存储成本低
   - 缺点: 一致性维护复杂

3. **混合存储方案**（推荐）
   - 元数据存储在数据库
   - 图片文件存储在文件系统
   - 通过分布式文件管理器保持同步

#### 当前实现

系统采用混合存储方案，通过DistributedFileManager实现跨服务器的文件同步：

```python
class DistributedFileManager:
    def __init__(self, local_storage_path, remote_nodes):
        self.local_storage_path = local_storage_path
        self.remote_nodes = remote_nodes
        
    def sync_file_to_remote(self, file_path):
        """同步文件到远程节点"""
        for node in self.remote_nodes:
            self._upload_file_to_node(file_path, node)
```

---

## 📊 监控和运维

### 系统监控指标

- **数据库连接状态**: 实时监控主备数据库连接
- **复制延迟**: 监控数据同步延迟时间
- **故障转移次数**: 统计自动故障转移频率
- **数据一致性**: 定期检查数据一致性状态

### API接口

- **主应用API**: http://localhost:8000
- **HA管理API**: http://localhost:8001/api/status
- **集群状态API**: http://localhost:8000/api/ha-status

### 日志管理

系统日志存储在`logs/`目录：
- `simple_ha.log`: HA系统运行日志
- `ha_system.log`: 详细系统日志
- `crawler.log`: 爬虫运行日志

---

## 🚀 部署指南

### 环境要求

- Python 3.8+
- PostgreSQL 16
- 网络连通性（主备服务器间）

### 部署步骤

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置数据库**
   ```bash
   python setup_postgresql_databases.py
   ```

3. **启动系统**
   ```bash
   python start_simple_ha.py
   ```

### 验证部署

访问以下URL验证系统运行状态：
- http://localhost:8000/api/ha-status
- http://localhost:8001/api/status

---

## 🔍 详细模块分析

### API服务器模块 (api.py)

#### 核心功能

<augment_code_snippet path="api.py" mode="EXCERPT">
````python
from crawler.main_crawler import ImageCrawler
from database.models.image import ImageModel
from database.distributed_ha_manager import DistributedHAManager
from config.ha_config_loader import load_ha_config
from storage.distributed_file_manager import DistributedFileManager
````
</augment_code_snippet>

API服务器集成了以下组件：
- **ImageCrawler**: 图像爬虫引擎
- **DistributedHAManager**: 分布式HA管理器
- **DistributedFileManager**: 分布式文件管理器
- **ImageModel**: 图像数据模型

#### 主要API端点

1. **爬虫控制API**
   - `POST /api/crawl/start` - 启动爬取任务
   - `GET /api/crawl/status` - 查询爬取状态
   - `POST /api/crawl/stop` - 停止爬取任务

2. **HA系统API**
   - `GET /api/ha-status` - 查询HA集群状态
   - `POST /api/ha/failover` - 手动故障转移
   - `GET /api/ha/sync-status` - 查询同步状态

3. **图像管理API**
   - `GET /api/images` - 获取图像列表
   - `GET /api/images/{id}` - 获取特定图像
   - `DELETE /api/images/{id}` - 删除图像

### 数据库模型详解

#### 图像模型 (models/image.py)

<augment_code_snippet path="database/models/image.py" mode="EXCERPT">
````python
class ImageModel(Base):
    __tablename__ = 'images'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False, index=True)
    filename = Column(String(255))
    file_path = Column(String(512))
    file_size = Column(BigInteger)
    width = Column(Integer)
    height = Column(Integer)
    format = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
````
</augment_code_snippet>

#### 爬取会话模型 (models/crawl_session.py)

用于跟踪爬取任务的执行状态和统计信息：
- 会话ID和开始/结束时间
- 爬取的图片数量和成功率
- 错误信息和重试次数

### 健康监控系统详解

#### 健康监控器 (health_monitor.py)

<augment_code_snippet path="database/health_monitor.py" mode="EXCERPT">
````python
class HealthMonitor:
    def __init__(self, databases: Dict[str, DatabaseConfig]):
        self.databases = databases
        self.health_status: Dict[str, HealthStatus] = {}
        self.monitoring_enabled = False
        self.monitor_thread: Optional[threading.Thread] = None

    def start_monitoring(self):
        """启动健康监控"""
        if self.monitoring_enabled:
            return

        self.monitoring_enabled = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("健康监控已启动")
````
</augment_code_snippet>

#### 监控指标

1. **连接状态监控**
   - 数据库连接可用性
   - 连接响应时间
   - 连接池使用情况

2. **性能监控**
   - 查询执行时间
   - 事务处理速度
   - 锁等待时间

3. **资源监控**
   - CPU使用率
   - 内存使用情况
   - 磁盘空间使用

### 备份管理系统

#### 分布式备份管理器 (distributed_backup_manager.py)

实现跨服务器的数据备份和恢复：

1. **自动备份策略**
   - 定时全量备份
   - 增量备份支持
   - 备份文件压缩和加密

2. **备份验证**
   - 备份完整性检查
   - 数据一致性验证
   - 恢复测试

3. **备份清理**
   - 过期备份自动清理
   - 备份保留策略
   - 存储空间管理

### 文件同步系统

#### 分布式文件管理器

<augment_code_snippet path="storage/distributed_file_manager.py" mode="EXCERPT">
````python
class DistributedFileManager:
    def __init__(self, config):
        self.local_storage_path = config.get('local_storage_path', './data/images')
        self.remote_nodes = config.get('remote_nodes', [])
        self.sync_enabled = config.get('sync_enabled', True)

    async def store_image(self, image_data: bytes, filename: str) -> str:
        """存储图像文件并同步到远程节点"""
        # 本地存储
        local_path = await self._store_locally(image_data, filename)

        # 同步到远程节点
        if self.sync_enabled:
            await self._sync_to_remote_nodes(local_path, filename)

        return local_path
````
</augment_code_snippet>

#### 文件同步策略

1. **实时同步**: 文件创建后立即同步
2. **批量同步**: 定期批量同步文件
3. **差异同步**: 只同步变更的文件
4. **断点续传**: 支持大文件的断点续传

---

## 🛠️ 高级配置和优化

### 性能优化配置

#### 数据库连接池优化

```yaml
# distributed_ha_config.yaml
nodes:
  primary_node:
    max_connections: 100
    connection_timeout: 30
    pool_size: 20
    max_overflow: 30
    pool_recycle: 3600
    pool_pre_ping: true
```

#### 同步性能优化

```yaml
synchronization:
  auto_sync_enabled: true
  sync_batch_size: 100
  sync_interval: 5
  full_sync_interval: 300
  max_sync_retries: 3
  sync_timeout: 30
```

### 监控配置详解

#### 健康检查配置

```yaml
monitoring:
  health_check_interval: 5  # 健康检查间隔(秒)
  replication_lag_threshold: 60  # 复制延迟阈值(秒)
  failure_threshold: 3  # 故障检测阈值
  auto_failover: true  # 是否启用自动故障转移
  notification:
    email_enabled: false
    webhook_enabled: false
    log_level: "INFO"
```

#### 告警配置

```yaml
alerts:
  database_down:
    enabled: true
    threshold: 3  # 连续失败次数
    cooldown: 300  # 告警冷却时间(秒)

  replication_lag:
    enabled: true
    threshold: 60  # 延迟阈值(秒)
    cooldown: 600

  disk_space:
    enabled: true
    threshold: 85  # 磁盘使用率阈值(%)
    cooldown: 1800
```

### 安全配置

#### 数据库安全

1. **连接加密**: 启用SSL/TLS连接
2. **访问控制**: 配置防火墙规则
3. **用户权限**: 最小权限原则
4. **审计日志**: 启用数据库审计

#### API安全

1. **身份认证**: JWT令牌认证
2. **访问限制**: IP白名单和速率限制
3. **数据加密**: 敏感数据加密存储
4. **HTTPS**: 强制使用HTTPS协议

---

## 📈 监控和运维进阶

### 系统监控仪表板

#### 关键指标监控

1. **数据库性能指标**
   - QPS (每秒查询数)
   - 平均响应时间
   - 连接数使用率
   - 锁等待时间

2. **HA系统指标**
   - 节点健康状态
   - 故障转移次数
   - 数据同步延迟
   - 一致性检查结果

3. **爬虫系统指标**
   - 爬取成功率
   - 图片下载速度
   - 存储使用情况
   - 任务队列长度

#### 日志分析

系统提供结构化日志，支持：
- 实时日志流分析
- 错误模式识别
- 性能趋势分析
- 异常事件告警

### 故障排查指南

#### 常见问题诊断

1. **数据库连接失败**
   ```bash
   # 检查网络连通性
   telnet 113.29.231.99 5432

   # 检查数据库服务状态
   systemctl status postgresql

   # 查看数据库日志
   tail -f /var/log/postgresql/postgresql.log
   ```

2. **数据同步延迟**
   ```bash
   # 检查同步队列状态
   curl http://localhost:8001/api/sync-status

   # 手动触发同步
   curl -X POST http://localhost:8001/api/sync/trigger
   ```

3. **故障转移异常**
   ```bash
   # 查看HA系统状态
   curl http://localhost:8001/api/status

   # 检查节点健康状态
   curl http://localhost:8001/api/health
   ```

#### 性能调优建议

1. **数据库优化**
   - 索引优化
   - 查询优化
   - 连接池调优
   - 缓存策略

2. **网络优化**
   - 带宽监控
   - 延迟优化
   - 连接复用
   - 压缩传输

3. **存储优化**
   - SSD存储
   - RAID配置
   - 分区策略
   - 清理策略

---

## 🔧 扩展和定制

### 水平扩展

#### 添加新节点

1. **配置新节点**
   ```yaml
   # 在distributed_ha_config.yaml中添加
   nodes:
     new_node:
       name: "new_node"
       role: "secondary"
       priority: 3
       server:
         host: "113.29.233.100"
         port: 5432
       database_url: "postgresql://postgres:Abcdefg6@113.29.233.100:5432/image_crawler"
   ```

2. **初始化数据同步**
   ```bash
   python scripts/init_new_node.py --node new_node
   ```

#### 负载均衡配置

支持读写分离和负载均衡：
- 写操作路由到主节点
- 读操作分发到备节点
- 智能路由算法
- 连接池管理

### 自定义扩展

#### 插件系统

系统支持插件扩展：
- 自定义爬虫处理器
- 图像处理插件
- 存储后端插件
- 通知插件

#### API扩展

支持自定义API端点：
- RESTful API扩展
- GraphQL支持
- WebSocket实时通信
- 批量操作API

---

本文档提供了图像爬虫分布式高可用系统的全面技术说明，涵盖了系统架构、核心功能、实现细节和运维指南。系统通过PostgreSQL双服务器配置实现了真正的跨服务器高可用性，确保在单点故障情况下的业务连续性。

通过本文档，开发人员和运维人员可以深入理解系统的工作原理，有效地部署、监控和维护这个分布式高可用系统。
