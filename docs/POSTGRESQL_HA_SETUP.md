# PostgreSQL分布式高可用数据库系统设置指南

## 🎯 系统概述

本系统使用两台PostgreSQL服务器构建分布式高可用数据库：

- **主数据库**: 113.29.231.99:5432 (postgres/Abcdefg6)
- **备数据库**: 113.29.232.245:5432 (postgres/Abcdefg6)

当主数据库故障时，系统会自动切换到备数据库，确保服务不中断。

## 🚀 快速开始

### 1. 环境准备

确保已安装必要的Python包：

```bash
pip install psycopg2-binary sqlalchemy fastapi uvicorn pyyaml aiohttp requests
```

### 2. 测试数据库连接

首先测试两个PostgreSQL服务器的连接性：

```bash
python test_postgresql_connection.py
```

如果连接失败，请检查：
- 网络连接和防火墙设置
- PostgreSQL服务是否运行
- 用户名密码是否正确

### 3. 初始化数据库

在两个PostgreSQL服务器上创建数据库和表结构：

```bash
python setup_postgresql_databases.py
```

这个脚本会：
- 创建 `image_crawler` 数据库
- 创建所有必要的表结构
- 验证设置是否正确

### 4. 启动高可用系统

```bash
python start_postgresql_ha.py
```

系统启动后会显示：
- 集群状态信息
- 各节点健康状态
- API服务地址

## 📊 系统监控

### Web界面

- **主应用**: http://localhost:8000
- **HA状态**: http://localhost:8000/api/ha-status
- **数据库状态**: http://localhost:8000/api/db-status

### API端点

```bash
# 查看集群状态
curl http://localhost:8001/api/status

# 查看节点健康状态
curl http://localhost:8001/api/health

# 查看复制延迟
curl http://localhost:8001/api/replication-lag

# 手动故障转移
curl -X POST http://localhost:8001/api/failover/backup_node
```

## 🔧 故障转移测试

### 模拟主数据库故障

1. **停止主数据库连接**（模拟网络故障）：
   ```bash
   # 在防火墙中阻断主数据库IP
   # 或者直接关闭主数据库服务
   ```

2. **观察自动故障转移**：
   ```bash
   # 查看日志
   tail -f logs/postgresql_ha.log
   
   # 查看集群状态
   curl http://localhost:8001/api/status
   ```

3. **验证服务继续可用**：
   ```bash
   # 测试API是否正常
   curl http://localhost:8000/api/images
   ```

### 手动故障转移

```bash
# 手动切换到备用节点
curl -X POST http://localhost:8001/api/failover/backup_node
```

## 📁 配置文件说明

### config/distributed_ha_config.yaml

```yaml
# 本地节点名称
local_node: "primary_node"

nodes:
  # 主节点配置
  primary_node:
    name: "primary_node"
    role: "primary"
    priority: 1
    server:
      host: "113.29.231.99"
      port: 5432
      api_port: 8001
    database_url: "postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler"
    
  # 备节点配置
  backup_node:
    name: "backup_node"
    role: "secondary"
    priority: 2
    server:
      host: "113.29.232.245"
      port: 5432
      api_port: 8001
    database_url: "postgresql://postgres:Abcdefg6@113.29.232.245:5432/image_crawler"
```

### 关键配置项

- **local_node**: 当前运行节点的名称
- **role**: 节点角色（primary/secondary/standby）
- **priority**: 故障转移优先级（数字越小优先级越高）
- **database_url**: 数据库连接字符串

## 🔍 故障排除

### 常见问题

1. **连接超时**
   ```
   解决方案：
   - 检查网络连接
   - 验证防火墙设置
   - 确认PostgreSQL服务运行状态
   ```

2. **认证失败**
   ```
   解决方案：
   - 检查用户名密码
   - 验证pg_hba.conf配置
   - 确认用户权限
   ```

3. **数据库不存在**
   ```
   解决方案：
   - 运行 setup_postgresql_databases.py
   - 手动创建数据库
   ```

4. **故障转移失败**
   ```
   解决方案：
   - 检查备用节点健康状态
   - 验证网络连接
   - 查看详细错误日志
   ```

### 日志文件

- **系统日志**: `logs/postgresql_ha.log`
- **应用日志**: `logs/crawler.log`

### 调试命令

```bash
# 检查进程状态
ps aux | grep python

# 检查端口占用
netstat -tlnp | grep :800

# 查看实时日志
tail -f logs/postgresql_ha.log

# 测试数据库连接
python -c "
import psycopg2
conn = psycopg2.connect(
    host='113.29.231.99',
    port=5432,
    user='postgres',
    password='Abcdefg6',
    database='image_crawler'
)
print('连接成功')
conn.close()
"
```

## 🔒 安全建议

1. **网络安全**
   - 使用VPN连接数据库服务器
   - 配置防火墙只允许必要端口
   - 定期更新系统补丁

2. **数据库安全**
   - 更改默认密码
   - 创建专用数据库用户
   - 启用SSL连接

3. **监控告警**
   - 设置故障转移通知
   - 监控系统资源使用
   - 定期备份数据

## 📈 性能优化

### PostgreSQL优化

```sql
-- 连接到PostgreSQL并执行优化配置
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
SELECT pg_reload_conf();
```

### 应用优化

```yaml
# 在配置文件中调整
nodes:
  primary_node:
    max_connections: 200
    connection_timeout: 60
    
synchronization:
  batch_size: 500
  sync_interval: 0.5
```

## 🎯 下一步

1. **生产部署**
   - 配置SSL证书
   - 设置监控告警
   - 制定备份策略

2. **扩展功能**
   - 添加更多备用节点
   - 实现读写分离
   - 集成负载均衡

3. **运维自动化**
   - 自动化部署脚本
   - 健康检查脚本
   - 故障恢复流程

## 📞 支持

如果遇到问题，请：
1. 查看日志文件
2. 运行测试脚本
3. 检查网络连接
4. 验证配置文件
