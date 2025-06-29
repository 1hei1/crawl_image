# 分布式高可用数据库系统

这是一个为图片爬虫项目设计的分布式高可用数据库系统，支持跨服务器的数据库自动故障转移和实时数据同步。

## 🌟 核心特性

### 1. 自动故障检测和转移
- **实时健康监控**: 每5秒检查一次所有数据库节点
- **智能故障检测**: 连续3次连接失败自动触发故障转移
- **零停机切换**: 主数据库故障时自动切换到备用数据库
- **优先级管理**: 按配置的优先级选择最佳备用节点

### 2. 实时数据同步
- **异步复制**: 支持异步、同步、半同步复制模式
- **增量同步**: 只同步变更的数据，减少网络开销
- **冲突解决**: 自动处理数据冲突和重复
- **延迟监控**: 实时监控复制延迟

### 3. 负载均衡
- **读写分离**: 写操作路由到主节点，读操作可分发到备节点
- **智能路由**: 根据节点健康状态和负载自动选择最佳节点
- **连接池管理**: 优化数据库连接使用

### 4. 跨服务器部署
- **多机房支持**: 支持跨数据中心部署
- **网络容错**: 处理网络分区和连接中断
- **API通信**: 节点间通过REST API进行通信

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   服务器 A      │    │   服务器 B      │    │   服务器 C      │
│  (主节点)       │    │  (备节点1)      │    │  (备节点2)      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ 图片爬虫 API    │    │ 图片爬虫 API    │    │ 图片爬虫 API    │
│ :8000          │    │ :8000          │    │ :8000          │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ HA API服务      │    │ HA API服务      │    │ HA API服务      │
│ :8001          │    │ :8001          │    │ :8001          │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ HA管理器        │◄──►│ HA管理器        │◄──►│ HA管理器        │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ SQLite/PG数据库 │    │ PostgreSQL      │    │ PostgreSQL      │
│ (主)           │───►│ (备)           │    │ (备)           │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 快速开始

### 1. 环境准备

在每台服务器上安装依赖：

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装PostgreSQL (备用服务器)
sudo apt-get install postgresql postgresql-contrib

# 创建数据库和用户
sudo -u postgres psql
CREATE DATABASE image_crawler;
CREATE USER crawler_user WITH PASSWORD 'crawler_pass';
GRANT ALL PRIVILEGES ON DATABASE image_crawler TO crawler_user;
```

### 2. 配置文件设置

编辑 `config/distributed_ha_config.yaml`：

```yaml
# 本地节点名称 (每台服务器不同)
local_node: "node1"  # 服务器A: node1, 服务器B: node2, 服务器C: node3

nodes:
  node1:  # 主节点 (服务器A)
    name: "node1"
    role: "primary"
    priority: 1
    server:
      host: "192.168.1.10"  # 服务器A的IP
      port: 5432
      api_port: 8001
    database_url: "sqlite:///data/images.db"
    
  node2:  # 备节点1 (服务器B)
    name: "node2"
    role: "secondary"
    priority: 2
    server:
      host: "192.168.1.11"  # 服务器B的IP
      port: 5432
      api_port: 8001
    database_url: "postgresql://crawler_user:crawler_pass@192.168.1.11:5432/image_crawler"
    
  node3:  # 备节点2 (服务器C)
    name: "node3"
    role: "secondary"
    priority: 3
    server:
      host: "192.168.1.12"  # 服务器C的IP
      port: 5432
      api_port: 8001
    database_url: "postgresql://crawler_user:crawler_pass@192.168.1.12:5432/image_crawler"
```

### 3. 启动系统

在每台服务器上运行：

```bash
# 启动分布式高可用系统
python start_ha_system.py
```

### 4. 验证部署

访问任意服务器的API：
- 主应用API: http://服务器IP:8000
- HA管理API: http://服务器IP:8001/api/status

## 📊 监控和管理

### 查看集群状态

```bash
curl http://localhost:8001/api/status
```

### 手动故障转移

```bash
curl -X POST http://localhost:8001/api/failover/node2
```

### 强制全量同步

```bash
curl -X POST http://localhost:8001/api/force-sync
```

### 查看复制延迟

```bash
curl http://localhost:8001/api/replication-lag
```

## 🔧 故障场景测试

### 1. 主数据库故障模拟

```bash
# 在主服务器上停止数据库
sudo systemctl stop postgresql

# 观察日志，系统应自动切换到备用节点
tail -f logs/ha_system.log
```

### 2. 网络分区模拟

```bash
# 临时阻断网络连接
sudo iptables -A INPUT -s 192.168.1.11 -j DROP
sudo iptables -A OUTPUT -d 192.168.1.11 -j DROP

# 恢复网络连接
sudo iptables -D INPUT -s 192.168.1.11 -j DROP
sudo iptables -D OUTPUT -d 192.168.1.11 -j DROP
```

## 📈 性能优化

### 1. 数据库优化

```sql
-- PostgreSQL优化配置
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
SELECT pg_reload_conf();
```

### 2. 网络优化

```yaml
# 在配置文件中调整
synchronization:
  batch_size: 500  # 增加批量大小
  sync_interval: 0.5  # 减少同步间隔
```

## 🚨 故障排除

### 常见问题

1. **节点连接失败**
   - 检查网络连接和防火墙设置
   - 验证数据库连接字符串
   - 确认API端口未被占用

2. **数据同步延迟**
   - 检查网络带宽和延迟
   - 调整同步批量大小
   - 监控数据库性能

3. **故障转移失败**
   - 确认备用节点健康状态
   - 检查节点优先级配置
   - 查看详细错误日志

### 日志文件

- 系统日志: `logs/ha_system.log`
- HA管理器日志: `logs/ha_manager.log`
- API服务器日志: `logs/crawler.log`

## 🔒 安全考虑

1. **网络安全**
   - 使用VPN或专用网络连接服务器
   - 配置防火墙只允许必要端口
   - 启用SSL/TLS加密通信

2. **数据库安全**
   - 使用强密码和专用用户
   - 定期更新数据库软件
   - 启用数据库审计日志

3. **API安全**
   - 添加API认证和授权
   - 限制API访问频率
   - 监控异常访问模式

## 📝 维护指南

### 定期维护任务

1. **每日检查**
   - 查看系统日志
   - 检查节点健康状态
   - 监控复制延迟

2. **每周维护**
   - 清理历史日志文件
   - 检查磁盘空间使用
   - 更新系统补丁

3. **每月维护**
   - 备份配置文件
   - 测试故障转移流程
   - 性能调优评估

## 🤝 贡献

欢迎提交问题报告和功能请求！

## 📄 许可证

本项目采用 MIT 许可证。
