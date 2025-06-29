# 容灾备份系统使用指南

图片爬取系统的容灾备份功能提供了完整的数据库高可用性解决方案，包括自动备份、健康监控、故障检测和自动故障转移等功能。

## 🚀 快速开始

### 1. 启用容灾备份功能

编辑 `config/config.yaml` 文件，设置：

```yaml
disaster_recovery:
  enabled: true
  databases:
    primary:
      name: "primary"
      type: "primary"
      priority: 0
      url: "sqlite:///data/images_primary.db"
    secondary1:
      name: "secondary1"
      type: "secondary"
      priority: 1
      url: "sqlite:///data/images_secondary1.db"
```

### 2. 启动监控服务

```bash
python disaster_recovery.py start-monitoring
```

### 3. 查看系统状态

```bash
python disaster_recovery.py status
```

### 4. 创建备份

```bash
python disaster_recovery.py backup
```

现在您的系统已经具备了容灾备份能力！🎉

## 功能特性

### 🔄 主从数据库架构
- 支持多个数据库实例（主数据库 + 多个备用数据库）
- 自动选择最优数据库作为主数据库
- 按优先级进行故障转移

### 💾 自动备份管理
- 定时自动备份数据库
- 支持 SQLite 和 PostgreSQL
- 备份文件压缩和清理
- 备份恢复功能

### 🔍 健康监控
- 实时数据库健康检查
- 响应时间监控
- 连接状态监控
- 自定义告警规则

### ⚡ 自动故障转移
- 自动检测数据库故障
- 智能选择备用数据库
- 平滑切换，最小化服务中断
- 故障转移历史记录

## 配置说明

### 1. 启用容灾备份功能

在 `config/config.yaml` 中添加容灾备份配置：

```yaml
# 容灾备份配置
disaster_recovery:
  # 启用容灾备份功能
  enabled: true
  
  # 数据库实例配置
  databases:
    # 主数据库
    primary:
      name: "primary"
      type: "primary"
      priority: 0
      url: "sqlite:///data/images_primary.db"
    
    # 备用数据库1
    secondary1:
      name: "secondary1"
      type: "secondary"
      priority: 1
      url: "sqlite:///data/images_secondary1.db"
    
    # 备用数据库2（可选）
    secondary2:
      name: "secondary2"
      type: "secondary"
      priority: 2
      url: "sqlite:///data/images_secondary2.db"
      enabled: false  # 可以禁用某个数据库
  
  # 备份配置
  backup:
    backup_dir: "backups"
    enable_auto_backup: true
    backup_interval: 3600  # 1小时备份一次
    max_backups: 10
    retention_days: 30
    enable_compression: true
  
  # 故障转移配置
  failover:
    enable_auto_failover: true
    health_check_interval: 30  # 30秒检查一次
    detection_threshold: 3     # 连续3次失败触发故障转移
    max_retry_attempts: 3
    retry_delay: 5
    notification_enabled: true
  
  # 监控配置
  monitoring:
    enable_health_monitoring: true
    check_interval: 30
    history_retention_hours: 24
    
    # 告警规则
    alert_rules:
      response_time_warning:
        enabled: true
        metric: "response_time"
        operator: ">"
        threshold: 5000.0  # 5秒
        severity: "warning"
      
      response_time_critical:
        enabled: true
        metric: "response_time"
        operator: ">"
        threshold: 10000.0  # 10秒
        severity: "critical"
```

### 2. PostgreSQL 配置示例

对于 PostgreSQL 数据库，配置如下：

```yaml
disaster_recovery:
  enabled: true
  databases:
    primary:
      name: "primary"
      type: "primary"
      priority: 0
      url: "postgresql://user:password@localhost:5432/image_crawler_primary"
    
    secondary1:
      name: "secondary1"
      type: "secondary"
      priority: 1
      url: "postgresql://user:password@backup-server:5432/image_crawler_backup"
```

## 使用方法

### 1. 命令行工具

系统提供了专门的命令行工具用于容灾备份管理：

```bash
# 显示系统状态
python disaster_recovery.py status

# 创建备份
python disaster_recovery.py backup
python disaster_recovery.py backup --name "manual_backup_20231201"

# 恢复备份
python disaster_recovery.py restore backups/backup_20231201.sql

# 手动故障转移
python disaster_recovery.py failover secondary1 --reason "维护升级"

# 查看故障转移历史
python disaster_recovery.py history --limit 20

# 启用/禁用自动故障转移
python disaster_recovery.py enable-auto-failover
python disaster_recovery.py disable-auto-failover

# 启动监控服务
python disaster_recovery.py start-monitoring

# 测试数据库连接
python disaster_recovery.py test
```

### 2. 程序集成

在爬虫程序中使用增强的数据库管理器：

```python
from config.manager import ConfigManager
from database.enhanced_manager import EnhancedDatabaseManager

# 加载配置
config_manager = ConfigManager("config/config.yaml")
settings = config_manager.get_settings()

# 初始化增强数据库管理器
database_url = config_manager.get_database_url()
db_manager = EnhancedDatabaseManager(
    database_url, 
    settings.disaster_recovery
)

# 启动监控服务
db_manager.start_monitoring()

# 使用数据库（自动使用当前主数据库）
with db_manager.get_session() as session:
    # 数据库操作
    pass

# 手动创建备份
backup_path = db_manager.create_backup("manual_backup")

# 手动故障转移
success = db_manager.manual_failover("secondary1", "计划维护")

# 获取系统状态
status = db_manager.get_database_info()
health = db_manager.get_health_status()
failover_status = db_manager.get_failover_status()
```

## 监控和告警

### 1. 健康指标

系统监控以下健康指标：

- **响应时间**：数据库查询响应时间
- **连接状态**：数据库连接是否正常
- **连接数**：当前数据库连接数（PostgreSQL）
- **错误计数**：数据库操作错误次数
- **数据库大小**：数据库文件大小

### 2. 告警规则

可以配置自定义告警规则：

```yaml
alert_rules:
  # 响应时间告警
  response_time_warning:
    enabled: true
    metric: "response_time"
    operator: ">"
    threshold: 5000.0
    severity: "warning"
    duration: 60  # 持续60秒触发告警
  
  # 连接数告警
  connection_count_high:
    enabled: true
    metric: "connection_count"
    operator: ">"
    threshold: 100
    severity: "warning"
  
  # 错误率告警
  error_rate_critical:
    enabled: true
    metric: "error_count"
    operator: ">"
    threshold: 10
    severity: "critical"
    duration: 300  # 5分钟内超过10个错误
```

### 3. 告警处理

当触发告警时，系统会：

1. 记录告警日志
2. 如果启用了自动故障转移，尝试切换到备用数据库
3. 发送通知（如果配置了通知功能）

## 故障转移流程

### 1. 自动故障转移

当检测到主数据库故障时，系统会自动执行以下步骤：

1. **故障检测**：连续多次连接失败达到阈值
2. **选择目标**：按优先级选择可用的备用数据库
3. **数据同步**：尝试同步最新数据到目标数据库
4. **切换数据库**：更新当前主数据库指向
5. **通知告警**：记录故障转移事件并发送通知

### 2. 手动故障转移

管理员可以手动执行故障转移：

```bash
# 切换到指定数据库
python disaster_recovery.py failover secondary1 --reason "计划维护"
```

### 3. 故障恢复

当原主数据库恢复后，可以：

1. 手动切换回原主数据库
2. 或者让系统继续使用当前数据库

## 备份和恢复

### 1. 自动备份

系统会根据配置定期创建备份：

- 备份间隔：可配置（默认1小时）
- 备份保留：按数量和时间双重限制
- 备份压缩：可选择是否压缩备份文件

### 2. 手动备份

```bash
# 创建备份
python disaster_recovery.py backup --name "before_upgrade"
```

### 3. 备份恢复

```bash
# 恢复备份
python disaster_recovery.py restore backups/backup_20231201.sql.gz
```

⚠️ **注意**：恢复备份会覆盖当前数据库，请谨慎操作。

## 最佳实践

### 1. 数据库配置

- **使用不同的物理位置**：将备用数据库部署在不同的服务器或数据中心
- **定期测试**：定期测试故障转移和备份恢复流程
- **监控告警**：配置合适的告警阈值，及时发现问题

### 2. 备份策略

- **定期备份**：根据数据重要性设置合适的备份频率
- **异地备份**：将备份文件存储在不同位置
- **备份验证**：定期验证备份文件的完整性

### 3. 故障转移

- **测试环境**：在测试环境中验证故障转移流程
- **回滚计划**：准备故障转移的回滚方案
- **文档记录**：记录故障转移的操作步骤和注意事项

## 故障排除

### 1. 常见问题

**Q: 容灾功能无法启用**
A: 检查配置文件中 `disaster_recovery.enabled` 是否为 `true`，确保数据库连接配置正确。

**Q: 自动故障转移不工作**
A: 检查 `failover.enable_auto_failover` 配置，确保监控服务已启动。

**Q: 备份创建失败**
A: 检查备份目录权限，确保数据库连接正常，查看日志文件获取详细错误信息。

### 2. 日志查看

容灾相关的日志会记录在系统日志中：

```bash
# 查看日志
tail -f logs/crawler.log | grep -E "(backup|failover|disaster)"
```

### 3. 调试模式

启用调试模式获取更详细的信息：

```yaml
# 在配置文件中启用调试
debug: true
logging:
  level: "DEBUG"
```

## 性能考虑

### 1. 监控频率

- 健康检查间隔不宜过短，避免对数据库造成额外负载
- 建议设置为 30-60 秒

### 2. 备份策略

- 大型数据库建议在业务低峰期进行备份
- 考虑使用增量备份减少备份时间

### 3. 故障转移

- 故障转移过程中可能有短暂的服务中断
- 应用程序应实现重试机制处理临时连接失败
