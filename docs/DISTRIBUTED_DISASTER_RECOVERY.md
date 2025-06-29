# 分布式容灾备份系统

真正适用于多服务器环境的容灾备份解决方案

## 🏗️ 架构设计

### 传统方案 vs 分布式方案

#### ❌ 传统方案问题
- **文件复制方式**：只适合单机环境，无法跨服务器
- **假容灾**：多个SQLite文件在同一台服务器上
- **无真正复制**：缺乏数据库级别的主从复制
- **单点故障**：服务器宕机整个系统不可用

#### ✅ 分布式方案优势
- **真正的多服务器部署**：数据库分布在不同物理服务器
- **PostgreSQL主从复制**：使用数据库原生复制功能
- **逻辑复制支持**：支持跨版本、跨平台复制
- **智能故障转移**：自动检测并切换到健康的服务器
- **地理分布**：支持同城、异地多活部署

## 🌐 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        分布式容灾架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   主数据中心     │    │   同城备份中心   │    │   异地备份中心   │ │
│  │   (华东)        │    │   (华东)        │    │   (华南)        │ │
│  │                │    │                │    │                │ │
│  │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │ │
│  │ │ 主数据库     │ │    │ │ 备用数据库1  │ │    │ │ 备用数据库2  │ │ │
│  │ │ Primary     │◄────┤ │ Secondary1  │ │    │ │ Secondary2  │ │ │
│  │ │ 10.0.1.100  │ │ │  │ │ 10.0.2.100  │ │    │ │ 10.1.1.100  │ │ │
│  │ │ 优先级: 0    │ │ │  │ │ 优先级: 1    │ │    │ │ 优先级: 2    │ │ │
│  │ └─────────────┘ │ │  │ └─────────────┘ │    │ └─────────────┘ │ │
│  │                │ │  │                │    │                │ │
│  │ 应用服务器       │ │  │ 应用服务器       │    │ 应用服务器       │ │
│  │ 爬虫系统        │ │  │ 爬虫系统        │    │ 爬虫系统        │ │
│  └─────────────────┘ │  └─────────────────┘    └─────────────────┘ │
│                      │                                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    逻辑复制流                                │ │
│  │  Primary ──async──► Secondary1 ──async──► Secondary2       │ │
│  │     │                   │                     │            │ │
│  │     └─────── 实时同步 ────┴──────── 异步同步 ────┘            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 快速部署

### 1. 环境准备

#### 服务器要求
- **主服务器**：PostgreSQL 12+，4核8G，SSD存储
- **备用服务器1**：PostgreSQL 12+，4核8G，SSD存储  
- **备用服务器2**：PostgreSQL 12+，2核4G，普通存储

#### 网络要求
- 服务器间网络延迟 < 50ms（同城）
- 服务器间网络延迟 < 200ms（异地）
- 稳定的网络连接，支持PostgreSQL复制端口

### 2. PostgreSQL配置

#### 主数据库配置 (postgresql.conf)
```ini
# 复制配置
wal_level = logical
max_wal_senders = 10
max_replication_slots = 10
max_logical_replication_workers = 4
max_worker_processes = 8

# 性能配置
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
```

#### 备用数据库配置 (postgresql.conf)
```ini
# 复制配置
wal_level = logical
max_logical_replication_workers = 4
max_worker_processes = 8

# 性能配置
shared_buffers = 128MB
effective_cache_size = 512MB
```

#### 访问控制配置 (pg_hba.conf)
```ini
# 允许复制连接
host replication crawler_user 10.0.0.0/8 md5
host all crawler_user 10.0.0.0/8 md5
```

### 3. 应用配置

复制配置文件：
```bash
cp config/distributed_disaster_recovery.yaml config/config.yaml
```

修改数据库连接信息：
```yaml
disaster_recovery:
  enabled: true
  mode: "distributed"
  
  databases:
    primary:
      host: "db-primary.company.com"
      port: 5432
      database: "image_crawler"
      username: "crawler_user"
      password: "your_password"
      
    secondary1:
      host: "db-backup1.company.com"
      port: 5432
      database: "image_crawler"
      username: "crawler_user"
      password: "your_password"
      
    secondary2:
      host: "db-backup2.company.com"
      port: 5432
      database: "image_crawler"
      username: "crawler_user"
      password: "your_password"
```

### 4. 初始化复制

```bash
# 在主数据库创建用户和数据库
createuser -h db-primary.company.com -U postgres crawler_user
createdb -h db-primary.company.com -U postgres -O crawler_user image_crawler

# 在备用数据库创建用户和数据库
createuser -h db-backup1.company.com -U postgres crawler_user
createdb -h db-backup1.company.com -U postgres -O crawler_user image_crawler

createuser -h db-backup2.company.com -U postgres crawler_user
createdb -h db-backup2.company.com -U postgres -O crawler_user image_crawler

# 初始化表结构
python -c "
from database.distributed_backup_manager import DistributedBackupManager
from config.manager import ConfigManager

config = ConfigManager('config/config.yaml')
# 创建表结构...
"
```

## 🔧 使用方法

### 1. 启动系统

```bash
# 启动爬虫系统（自动启用分布式容灾）
python run.py
```

系统启动时会：
- 自动检测所有数据库服务器连接
- 设置PostgreSQL逻辑复制
- 启动复制延迟监控
- 开始健康检查

### 2. 监控集群状态

```bash
# 查看集群状态
python disaster_recovery.py status

# 输出示例：
=== 分布式容灾集群状态 ===
当前主数据库: primary (主数据中心)
集群健康状态: 健康

--- 数据库服务器 ---
🟢 primary (主数据中心)
   类型: primary | 优先级: 0
   位置: 华东 (10.0.1.100)
   状态: 正常 | 响应时间: 5ms

🟢 secondary1 (同城备份中心)  
   类型: secondary | 优先级: 1
   位置: 华东 (10.0.2.100)
   状态: 正常 | 响应时间: 12ms
   复制延迟: 0.5秒

🟢 secondary2 (异地备份中心)
   类型: secondary | 优先级: 2  
   位置: 华南 (10.1.1.100)
   状态: 正常 | 响应时间: 45ms
   复制延迟: 2.1秒
```

### 3. 故障转移测试

```bash
# 手动故障转移到同城备份
python disaster_recovery.py failover secondary1 --reason "计划维护"

# 手动故障转移到异地备份
python disaster_recovery.py failover secondary2 --reason "灾难恢复"
```

### 4. 备份管理

```bash
# 创建分布式备份（所有服务器）
python disaster_recovery.py backup --distributed

# 恢复特定服务器的备份
python disaster_recovery.py restore backup_primary_20231201.sql --target primary
```

## 📊 监控指标

### 关键指标
- **复制延迟**：从库落后主库的时间
- **网络延迟**：服务器间的网络响应时间
- **连接状态**：各数据库服务器的连接健康状态
- **磁盘使用率**：各服务器的存储使用情况
- **CPU/内存使用率**：服务器资源使用情况

### 告警阈值
- 复制延迟 > 30秒：警告
- 复制延迟 > 2分钟：严重
- 网络延迟 > 100ms：警告
- 连接失败 > 3次：触发故障转移

## 🔄 故障场景处理

### 场景1：主服务器宕机
1. **自动检测**：30秒内检测到主服务器不可达
2. **自动切换**：切换到同城备份服务器（secondary1）
3. **服务恢复**：2分钟内恢复服务
4. **数据一致性**：最多丢失30秒数据

### 场景2：同城灾难
1. **检测**：主服务器和同城备份同时不可达
2. **切换**：自动切换到异地备份服务器（secondary2）
3. **恢复**：5分钟内恢复服务
4. **数据**：最多丢失2分钟数据

### 场景3：网络分区
1. **检测**：部分服务器网络不通
2. **策略**：保持当前主服务器，等待网络恢复
3. **监控**：持续监控网络状态
4. **恢复**：网络恢复后自动重新同步

## 🛠️ 运维管理

### 日常维护
```bash
# 检查复制状态
python disaster_recovery.py replication-status

# 手动同步数据
python disaster_recovery.py sync --source primary --target secondary1

# 重建复制
python disaster_recovery.py rebuild-replication secondary1
```

### 性能优化
- 调整PostgreSQL复制参数
- 优化网络配置
- 监控磁盘I/O性能
- 定期清理WAL日志

### 安全配置
- 使用SSL加密复制连接
- 配置防火墙规则
- 定期更新数据库密码
- 审计复制日志

## 📈 容量规划

### 存储需求
- **主服务器**：业务数据 + WAL日志
- **备用服务器**：业务数据 + 复制日志
- **备份存储**：3-7天的完整备份

### 网络带宽
- **同城复制**：10Mbps+
- **异地复制**：5Mbps+
- **备份传输**：根据数据量计算

### 服务器规格
- **主服务器**：高性能配置
- **同城备份**：与主服务器相当
- **异地备份**：可适当降低配置

---

这个分布式容灾备份系统提供了真正的多服务器容灾能力，确保在任何单点故障情况下都能快速恢复服务，保证数据安全和业务连续性。
