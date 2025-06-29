# 图像爬虫分布式高可用系统部署和故障排查指南

## 🚀 快速部署指南

### 环境要求

#### 硬件要求
- **主服务器**: 4核CPU, 8GB内存, 100GB存储
- **备服务器**: 4核CPU, 8GB内存, 100GB存储
- **网络**: 稳定的网络连接，延迟 < 50ms

#### 软件要求
- **操作系统**: Ubuntu 20.04+ / CentOS 8+ / Windows 10+
- **Python**: 3.8+
- **PostgreSQL**: 16+
- **网络端口**: 5432(PostgreSQL), 8000(主API), 8001(HA API)

### 部署步骤

#### 1. 环境准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装Python和pip
sudo apt install python3 python3-pip python3-venv -y

# 安装PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# 启动PostgreSQL服务
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### 2. 数据库配置

```bash
# 切换到postgres用户
sudo -u postgres psql

# 在PostgreSQL中执行以下命令
CREATE DATABASE image_crawler;
CREATE USER postgres WITH PASSWORD 'Abcdefg6';
GRANT ALL PRIVILEGES ON DATABASE image_crawler TO postgres;
ALTER USER postgres CREATEDB;
\q
```

#### 3. 项目部署

```bash
# 克隆项目（或解压项目文件）
cd /opt
git clone <project-repository> image_crawler
cd image_crawler

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建必要目录
mkdir -p logs data/images data/backup
```

#### 4. 配置文件设置

```bash
# 复制配置文件模板
cp config/distributed_ha_config.yaml.example config/distributed_ha_config.yaml

# 编辑配置文件
nano config/distributed_ha_config.yaml
```

**关键配置项**:
```yaml
# 修改数据库连接信息
nodes:
  primary_node:
    server:
      host: "113.29.231.99"  # 主服务器IP
    database_url: "postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler"
  
  backup_node:
    server:
      host: "113.29.232.245"  # 备服务器IP
    database_url: "postgresql://postgres:Abcdefg6@113.29.232.245:5432/image_crawler"
```

#### 5. 数据库初始化

```bash
# 运行数据库初始化脚本
python setup_postgresql_databases.py

# 验证数据库连接
python -c "
from config.ha_config_loader import load_ha_config
from sqlalchemy import create_engine, text

nodes, local_node_name, config = load_ha_config()
for node in nodes:
    try:
        engine = create_engine(node.database_url)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print(f'✅ {node.name} 连接成功')
    except Exception as e:
        print(f'❌ {node.name} 连接失败: {e}')
"
```

#### 6. 启动系统

```bash
# 启动分布式高可用系统
python start_simple_ha.py
```

#### 7. 验证部署

```bash
# 检查系统状态
curl http://localhost:8000/api/ha-status
curl http://localhost:8001/api/status

# 检查日志
tail -f logs/simple_ha.log
```

---

## 🔧 故障排查指南

### 常见问题诊断

#### 1. 数据库连接问题

**症状**: 系统启动时报数据库连接失败

**诊断步骤**:
```bash
# 检查PostgreSQL服务状态
sudo systemctl status postgresql

# 检查端口监听
netstat -tlnp | grep 5432

# 测试本地连接
psql -h localhost -U postgres -d image_crawler

# 测试远程连接
psql -h 113.29.231.99 -U postgres -d image_crawler
```

**解决方案**:
```bash
# 修改PostgreSQL配置允许远程连接
sudo nano /etc/postgresql/16/main/postgresql.conf
# 添加或修改: listen_addresses = '*'

sudo nano /etc/postgresql/16/main/pg_hba.conf
# 添加: host all all 0.0.0.0/0 md5

# 重启PostgreSQL
sudo systemctl restart postgresql

# 检查防火墙
sudo ufw allow 5432
```

#### 2. 故障转移不工作

**症状**: 主数据库故障时系统没有自动切换

**诊断步骤**:
```bash
# 检查HA管理器状态
curl http://localhost:8001/api/status

# 查看监控日志
grep "故障转移\|failover" logs/simple_ha.log

# 检查节点健康状态
curl http://localhost:8001/api/health
```

**解决方案**:
```bash
# 检查配置文件中的故障转移设置
grep -A 5 "auto_failover" config/distributed_ha_config.yaml

# 手动触发故障转移测试
curl -X POST http://localhost:8001/api/failover \
  -H "Content-Type: application/json" \
  -d '{"source_node": "primary_node", "target_node": "backup_node"}'
```

#### 3. 数据同步延迟

**症状**: 主备数据库数据不一致

**诊断步骤**:
```bash
# 检查同步状态
curl http://localhost:8001/api/sync-status

# 查看同步队列
curl http://localhost:8001/api/sync-queue

# 检查数据一致性
python -c "
from database.distributed_ha_manager import DistributedHAManager
from config.ha_config_loader import load_ha_config

nodes, local_node_name, config = load_ha_config()
ha_manager = DistributedHAManager(nodes, local_node_name, config)
result = ha_manager.check_data_consistency()
print(f'数据一致性检查结果: {result}')
"
```

**解决方案**:
```bash
# 手动触发全量同步
curl -X POST http://localhost:8001/api/sync/full

# 检查网络延迟
ping 113.29.232.245

# 调整同步配置
nano config/distributed_ha_config.yaml
# 修改 sync_interval 和 sync_batch_size
```

#### 4. API服务无法访问

**症状**: 无法访问API端点

**诊断步骤**:
```bash
# 检查进程状态
ps aux | grep python
ps aux | grep uvicorn

# 检查端口占用
netstat -tlnp | grep 8000
netstat -tlnp | grep 8001

# 检查防火墙
sudo ufw status
```

**解决方案**:
```bash
# 开放端口
sudo ufw allow 8000
sudo ufw allow 8001

# 重启API服务
pkill -f "uvicorn"
python start_simple_ha.py
```

#### 5. 内存不足问题

**症状**: 系统运行缓慢或崩溃

**诊断步骤**:
```bash
# 检查内存使用
free -h
top -p $(pgrep -f python)

# 检查日志中的内存错误
grep -i "memory\|oom" logs/simple_ha.log
```

**解决方案**:
```bash
# 调整连接池大小
nano config/distributed_ha_config.yaml
# 减少 max_connections 和 pool_size

# 增加系统交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 性能优化建议

#### 1. 数据库性能优化

```sql
-- 创建索引
CREATE INDEX idx_images_created_at ON images(created_at);
CREATE INDEX idx_images_url_hash ON images(md5(url));

-- 优化PostgreSQL配置
-- 在 postgresql.conf 中添加:
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

#### 2. 网络优化

```bash
# 调整TCP参数
echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_rmem = 4096 87380 16777216' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_wmem = 4096 65536 16777216' >> /etc/sysctl.conf
sysctl -p
```

#### 3. 应用程序优化

```yaml
# 在配置文件中调整并发参数
crawler:
  max_concurrent: 5  # 减少并发数
  request_delay: 2   # 增加请求延迟

synchronization:
  sync_batch_size: 50  # 减少批次大小
  sync_interval: 10    # 增加同步间隔
```

---

## 📊 监控和维护

### 系统监控脚本

```bash
#!/bin/bash
# monitor_system.sh - 系统监控脚本

echo "=== 系统状态监控 ==="
echo "时间: $(date)"
echo

# 检查进程状态
echo "1. 进程状态:"
if pgrep -f "start_simple_ha.py" > /dev/null; then
    echo "✅ HA系统运行中"
else
    echo "❌ HA系统未运行"
fi

# 检查API服务
echo "2. API服务状态:"
if curl -s http://localhost:8000/api/ha-status > /dev/null; then
    echo "✅ 主API服务正常"
else
    echo "❌ 主API服务异常"
fi

if curl -s http://localhost:8001/api/status > /dev/null; then
    echo "✅ HA API服务正常"
else
    echo "❌ HA API服务异常"
fi

# 检查数据库连接
echo "3. 数据库连接:"
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler')
    print('✅ 主数据库连接正常')
    conn.close()
except:
    print('❌ 主数据库连接异常')

try:
    conn = psycopg2.connect('postgresql://postgres:Abcdefg6@113.29.232.245:5432/image_crawler')
    print('✅ 备数据库连接正常')
    conn.close()
except:
    print('❌ 备数据库连接异常')
"

# 检查磁盘空间
echo "4. 磁盘空间:"
df -h | grep -E "/$|/data"

# 检查内存使用
echo "5. 内存使用:"
free -h

echo "=== 监控完成 ==="
```

### 自动化维护脚本

```bash
#!/bin/bash
# maintenance.sh - 自动化维护脚本

# 清理旧日志
find logs/ -name "*.log" -mtime +7 -delete

# 清理旧备份
find data/backup/ -name "*.sql" -mtime +30 -delete

# 数据库维护
psql -h 113.29.231.99 -U postgres -d image_crawler -c "VACUUM ANALYZE;"
psql -h 113.29.232.245 -U postgres -d image_crawler -c "VACUUM ANALYZE;"

# 重启服务（如果需要）
if [ "$1" = "restart" ]; then
    pkill -f "start_simple_ha.py"
    sleep 5
    nohup python start_simple_ha.py > logs/startup.log 2>&1 &
fi

echo "维护任务完成: $(date)"
```

### 定时任务配置

```bash
# 添加到crontab
crontab -e

# 每5分钟检查系统状态
*/5 * * * * /opt/image_crawler/monitor_system.sh >> /var/log/system_monitor.log

# 每天凌晨2点执行维护任务
0 2 * * * /opt/image_crawler/maintenance.sh

# 每周日凌晨3点重启系统
0 3 * * 0 /opt/image_crawler/maintenance.sh restart
```

---

## 🆘 紧急恢复程序

### 数据恢复

```bash
# 从备份恢复数据库
pg_restore -h 113.29.231.99 -U postgres -d image_crawler data/backup/latest_backup.sql

# 重建索引
psql -h 113.29.231.99 -U postgres -d image_crawler -c "REINDEX DATABASE image_crawler;"
```

### 系统重置

```bash
# 停止所有服务
pkill -f "start_simple_ha.py"
pkill -f "uvicorn"

# 清理临时文件
rm -rf logs/*.log
rm -rf data/temp/*

# 重新初始化数据库
python setup_postgresql_databases.py --reset

# 重启系统
python start_simple_ha.py
```

---

本指南提供了完整的部署流程和故障排查方法，帮助快速部署和维护图像爬虫分布式高可用系统。遇到问题时，请按照诊断步骤逐步排查，并参考解决方案进行修复。
