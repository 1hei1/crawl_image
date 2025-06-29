# 图像爬虫分布式高可用系统配置指南

## 📋 配置文件概览

系统使用YAML格式的配置文件，主要配置文件包括：

- `config/distributed_ha_config.yaml` - 分布式HA核心配置
- `config/config.yaml` - 基础系统配置
- `config/disaster_recovery_example.yaml` - 容灾备份配置示例

---

## 🔧 分布式HA配置详解

### 基础节点配置

```yaml
# 本地节点配置 (当前运行的节点)
local_node: "primary_node"

# 数据库节点配置
nodes:
  # 主节点配置
  primary_node:
    name: "primary_node"              # 节点名称，必须唯一
    role: "primary"                   # 节点角色：primary/secondary
    priority: 1                       # 优先级，数字越小优先级越高
    
    # 服务器信息
    server:
      host: "113.29.231.99"          # 数据库服务器IP地址
      port: 5432                      # PostgreSQL端口
      api_port: 8001                  # HA API服务端口
      location: "cloud_server_1"      # 服务器位置标识
      datacenter: "primary_dc"        # 数据中心标识
    
    # 数据库连接配置
    database_url: "postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler"
    max_connections: 100              # 最大连接数
    connection_timeout: 30            # 连接超时时间(秒)
    
    # 同步配置
    sync_mode: "async"                # 同步模式：async/sync/semi_sync
    sync_timeout: 10                  # 同步超时时间(秒)
    
    # 健康检查配置
    health_check_interval: 5          # 健康检查间隔(秒)
    failure_threshold: 3              # 故障检测阈值(连续失败次数)
    is_active: true                   # 是否激活此节点
```

### 监控配置

```yaml
monitoring:
  health_check_interval: 5           # 全局健康检查间隔(秒)
  replication_lag_threshold: 60      # 复制延迟阈值(秒)
  failure_threshold: 3               # 全局故障检测阈值
  auto_failover: true                # 是否启用自动故障转移
  
  # 性能监控配置
  performance_monitoring:
    enabled: true                    # 是否启用性能监控
    metrics_interval: 30             # 性能指标收集间隔(秒)
    slow_query_threshold: 5          # 慢查询阈值(秒)
    
  # 告警配置
  alerts:
    enabled: true                    # 是否启用告警
    email_notifications: false       # 邮件通知
    webhook_notifications: false     # Webhook通知
    log_level: "WARNING"             # 告警日志级别
```

### 同步配置

```yaml
synchronization:
  auto_sync_enabled: true            # 是否启用自动同步
  sync_batch_size: 100               # 同步批次大小
  sync_interval: 5                   # 同步间隔(秒)
  full_sync_interval: 300            # 全量同步间隔(秒)
  max_sync_retries: 3                # 最大重试次数
  sync_timeout: 30                   # 同步超时时间(秒)
  
  # 冲突解决策略
  conflict_resolution:
    strategy: "timestamp"            # 冲突解决策略：timestamp/priority/manual
    prefer_primary: true             # 是否优先使用主节点数据
    
  # 数据验证
  validation:
    enabled: true                    # 是否启用数据验证
    checksum_validation: true        # 校验和验证
    consistency_check_interval: 600  # 一致性检查间隔(秒)
```

### API服务器配置

```yaml
api_server:
  host: "0.0.0.0"                   # 监听地址
  port: 8001                        # 监听端口
  workers: 4                        # 工作进程数
  
  # 安全配置
  security:
    enable_auth: false              # 是否启用认证
    api_key_required: false         # 是否需要API密钥
    rate_limiting: true             # 是否启用速率限制
    max_requests_per_minute: 100    # 每分钟最大请求数
  
  # CORS配置
  cors:
    enabled: true                   # 是否启用CORS
    allow_origins: ["*"]            # 允许的源
    allow_methods: ["GET", "POST"]  # 允许的方法
```

---

## 🗄️ 数据库配置详解

### PostgreSQL连接配置

```yaml
database:
  # 基础连接信息
  type: "postgresql"
  host: "localhost"
  port: 5432
  database: "image_crawler"
  username: "postgres"
  password: "Abcdefg6"
  
  # 连接池配置
  pool_size: 10                     # 连接池大小
  max_overflow: 20                  # 最大溢出连接数
  pool_recycle: 3600                # 连接回收时间(秒)
  pool_pre_ping: true               # 连接前ping测试
  
  # 事务配置
  isolation_level: "READ_COMMITTED" # 事务隔离级别
  autocommit: false                 # 是否自动提交
  
  # 性能配置
  statement_timeout: 30000          # 语句超时时间(毫秒)
  lock_timeout: 10000               # 锁超时时间(毫秒)
  idle_in_transaction_session_timeout: 60000  # 空闲事务超时(毫秒)
```

### 数据库优化配置

```yaml
database_optimization:
  # 索引配置
  indexes:
    auto_create: true               # 是否自动创建索引
    analyze_threshold: 1000         # 分析阈值
    
  # 查询优化
  query_optimization:
    enable_query_cache: true        # 启用查询缓存
    cache_size: "128MB"             # 缓存大小
    max_query_time: 30              # 最大查询时间(秒)
    
  # 维护配置
  maintenance:
    auto_vacuum: true               # 自动清理
    vacuum_scale_factor: 0.2        # 清理比例因子
    analyze_scale_factor: 0.1       # 分析比例因子
```

---

## 🕷️ 爬虫配置详解

### 爬虫引擎配置

```yaml
crawler:
  # 并发配置
  max_concurrent: 10                # 最大并发数
  max_workers: 4                    # 最大工作线程数
  request_delay: 1                  # 请求延迟(秒)
  
  # 超时配置
  request_timeout: 30               # 请求超时时间(秒)
  download_timeout: 60              # 下载超时时间(秒)
  
  # 重试配置
  max_retries: 3                    # 最大重试次数
  retry_delay: 5                    # 重试延迟(秒)
  
  # 用户代理配置
  user_agents:
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
  
  # 代理配置
  proxies:
    enabled: false                  # 是否启用代理
    proxy_list: []                  # 代理列表
    rotation: true                  # 是否轮换代理
```

### 图像处理配置

```yaml
image_processing:
  # 支持的图像格式
  supported_formats: ["jpg", "jpeg", "png", "gif", "webp"]
  
  # 图像大小限制
  min_width: 100                    # 最小宽度(像素)
  min_height: 100                   # 最小高度(像素)
  max_file_size: 10485760          # 最大文件大小(字节，10MB)
  
  # 图像质量配置
  quality_check:
    enabled: true                   # 是否启用质量检查
    min_quality_score: 0.7          # 最小质量分数
    
  # 重复检测
  duplicate_detection:
    enabled: true                   # 是否启用重复检测
    hash_algorithm: "phash"         # 哈希算法：phash/dhash/ahash
    similarity_threshold: 0.9       # 相似度阈值
```

---

## 💾 存储配置详解

### 文件存储配置

```yaml
storage:
  # 本地存储配置
  local:
    base_path: "./data/images"      # 基础存储路径
    create_subdirs: true            # 是否创建子目录
    subdir_pattern: "%Y/%m/%d"      # 子目录模式
    
  # 分布式存储配置
  distributed:
    enabled: true                   # 是否启用分布式存储
    replication_factor: 2           # 复制因子
    sync_mode: "async"              # 同步模式
    
  # 文件命名配置
  naming:
    pattern: "{timestamp}_{hash}_{original}"  # 命名模式
    preserve_extension: true        # 是否保留扩展名
    
  # 清理配置
  cleanup:
    enabled: true                   # 是否启用自动清理
    retention_days: 30              # 保留天数
    cleanup_interval: 86400         # 清理间隔(秒)
```

### 备份存储配置

```yaml
backup_storage:
  # 备份策略
  strategy:
    full_backup_interval: 86400     # 全量备份间隔(秒)
    incremental_backup_interval: 3600  # 增量备份间隔(秒)
    
  # 备份保留策略
  retention:
    daily_backups: 7                # 保留日备份数量
    weekly_backups: 4               # 保留周备份数量
    monthly_backups: 12             # 保留月备份数量
    
  # 备份压缩
  compression:
    enabled: true                   # 是否启用压缩
    algorithm: "gzip"               # 压缩算法
    level: 6                        # 压缩级别(1-9)
```

---

## 📊 日志配置详解

### 日志系统配置

```yaml
logging:
  # 日志级别
  level: "INFO"                     # 日志级别：DEBUG/INFO/WARNING/ERROR
  
  # 日志格式
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # 日志文件配置
  file:
    enabled: true                   # 是否启用文件日志
    path: "./logs"                  # 日志文件路径
    filename: "system.log"          # 日志文件名
    max_size: "100MB"               # 最大文件大小
    backup_count: 5                 # 备份文件数量
    
  # 控制台日志配置
  console:
    enabled: true                   # 是否启用控制台日志
    colored: true                   # 是否启用彩色输出
    
  # 结构化日志配置
  structured:
    enabled: false                  # 是否启用结构化日志(JSON格式)
    include_extra_fields: true      # 是否包含额外字段
```

### 审计日志配置

```yaml
audit_logging:
  enabled: true                     # 是否启用审计日志
  
  # 审计事件
  events:
    database_operations: true       # 数据库操作
    failover_events: true           # 故障转移事件
    configuration_changes: true     # 配置变更
    api_requests: false             # API请求
    
  # 审计日志存储
  storage:
    type: "file"                    # 存储类型：file/database/remote
    path: "./logs/audit.log"        # 审计日志路径
    retention_days: 90              # 保留天数
```

---

## 🔒 安全配置详解

### 认证和授权配置

```yaml
security:
  # 认证配置
  authentication:
    enabled: false                  # 是否启用认证
    method: "jwt"                   # 认证方法：jwt/basic/oauth
    secret_key: "your-secret-key"   # JWT密钥
    token_expiry: 3600              # 令牌过期时间(秒)
    
  # 授权配置
  authorization:
    enabled: false                  # 是否启用授权
    default_role: "user"            # 默认角色
    
  # 访问控制
  access_control:
    ip_whitelist: []                # IP白名单
    ip_blacklist: []                # IP黑名单
    rate_limiting: true             # 速率限制
    max_requests_per_hour: 1000     # 每小时最大请求数
```

### 数据加密配置

```yaml
encryption:
  # 传输加密
  in_transit:
    enabled: true                   # 是否启用传输加密
    tls_version: "1.2"              # TLS版本
    cipher_suites: []               # 加密套件
    
  # 存储加密
  at_rest:
    enabled: false                  # 是否启用存储加密
    algorithm: "AES-256"            # 加密算法
    key_rotation_interval: 2592000  # 密钥轮换间隔(秒)
```

---

## 🚀 性能调优配置

### 系统性能配置

```yaml
performance:
  # 内存配置
  memory:
    max_heap_size: "2G"             # 最大堆内存
    gc_algorithm: "G1GC"            # 垃圾回收算法
    
  # 网络配置
  network:
    tcp_keepalive: true             # TCP保活
    tcp_nodelay: true               # TCP无延迟
    socket_timeout: 30              # Socket超时
    
  # 缓存配置
  cache:
    enabled: true                   # 是否启用缓存
    type: "memory"                  # 缓存类型：memory/redis/memcached
    max_size: "512MB"               # 最大缓存大小
    ttl: 3600                       # 缓存过期时间(秒)
```

---

本配置指南涵盖了图像爬虫分布式高可用系统的所有主要配置选项。根据实际部署环境和需求，可以调整这些配置参数以获得最佳性能和可靠性。
