# 自动数据同步功能指南

## 📋 概述

智能图片爬虫分布式高可用系统现已支持主数据库到备份数据库的自动数据同步功能。该功能确保主备数据库之间的数据一致性，提供真正的高可用性保障。

## 🌟 功能特性

### 🔄 自动同步机制
- **实时增量同步**: 主数据库的每个写操作都会自动同步到备用数据库
- **定时全量同步**: 定期检查数据一致性，同步缺失的数据
- **智能队列管理**: 异步处理同步操作，不影响主业务性能
- **故障恢复**: 网络中断后自动重试和恢复同步

### 📊 监控和管理
- **实时状态监控**: 查看同步队列、延迟、成功率等指标
- **健康检查**: 自动检测同步异常并告警
- **手动控制**: 支持启用/禁用自动同步、强制全量同步
- **性能优化**: 批量处理、压缩传输、超时控制

## ⚙️ 配置说明

### 配置文件位置
```
config/distributed_ha_config.yaml
```

### 同步配置项
```yaml
synchronization:
  # 自动同步设置
  auto_sync_enabled: true          # 是否启用自动同步
  full_sync_interval: 300          # 全量同步检查间隔(秒) - 5分钟
  incremental_sync_interval: 10    # 增量同步检查间隔(秒)
  
  # 批量处理设置
  batch_size: 100                  # 批量同步大小
  sync_interval: 1                 # 同步队列处理间隔(秒)
  max_retry_attempts: 3            # 最大重试次数
  retry_delay: 5                   # 重试延迟(秒)
  
  # 性能优化设置
  max_queue_size: 1000            # 最大同步队列大小
  sync_timeout: 30                # 单个同步操作超时时间(秒)
  enable_compression: false       # 是否启用数据压缩传输
  
  # 数据一致性设置
  verify_sync: true               # 是否验证同步结果
  conflict_resolution: "primary_wins"  # 冲突解决策略
  
  # 同步范围设置
  sync_tables:
    - "images"                    # 同步图片表
    - "categories"                # 同步分类表
```

## 🚀 使用方法

### 1. 启动系统
```bash
# 启动分布式高可用系统（自动启用同步功能）
python start_simple_ha.py
```

### 2. 查看同步状态
```bash
# 使用监控工具查看状态
python tools/sync_monitor.py status

# 持续监控
python tools/sync_monitor.py monitor --interval 5

# 健康检查
python tools/sync_monitor.py health
```

### 3. API接口

#### 获取同步状态
```bash
# 主API
curl http://localhost:8000/api/sync-status

# HA管理API
curl http://localhost:8001/api/sync-status
```

#### 强制全量同步
```bash
# 通过主API
curl -X POST http://localhost:8000/api/force-sync

# 通过HA管理API
curl -X POST http://localhost:8001/api/force-sync

# 使用监控工具
python tools/sync_monitor.py force-sync
```

#### 控制自动同步
```bash
# 启用自动同步
curl -X POST http://localhost:8001/api/sync/enable

# 禁用自动同步
curl -X POST http://localhost:8001/api/sync/disable
```

## 🔍 监控指标

### 同步状态指标
- **auto_sync_enabled**: 自动同步是否启用
- **sync_queue_size**: 当前同步队列大小
- **last_full_sync**: 最后一次全量同步时间
- **current_primary**: 当前主节点
- **is_monitoring**: 监控服务是否运行

### 集群健康指标
- **节点状态**: 每个节点的健康状态
- **复制延迟**: 主备节点间的数据延迟
- **连接状态**: 数据库连接是否正常

## 🧪 测试验证

### 自动测试
```bash
# 运行自动同步功能测试
python tests/test_auto_sync.py
```

### 手动测试步骤

1. **添加测试数据**
```python
# 在主数据库添加图片记录
with ha_manager.get_session() as session:
    test_image = ImageModel(
        url="https://example.com/test.jpg",
        source_url="https://example.com",
        filename="test.jpg",
        file_extension="jpg",
        md5_hash="test_hash_123"
    )
    session.add(test_image)
    session.commit()
```

2. **检查同步状态**
```bash
python tools/sync_monitor.py status
```

3. **验证备用数据库**
```bash
# 连接到备用数据库检查数据
psql -h 113.29.232.245 -U postgres -d image_crawler
SELECT * FROM images WHERE filename = 'test.jpg';
```

## ⚠️ 故障排除

### 常见问题

#### 1. 同步队列积压
**症状**: sync_queue_size 持续增长
**解决方案**:
- 检查备用数据库连接
- 增加 batch_size 配置
- 检查网络延迟

#### 2. 数据不一致
**症状**: 主备数据库记录数量不同
**解决方案**:
```bash
# 强制全量同步
python tools/sync_monitor.py force-sync

# 检查同步日志
tail -f logs/simple_ha.log | grep sync
```

#### 3. 同步服务停止
**症状**: is_monitoring 为 false
**解决方案**:
```bash
# 重启系统
python start_simple_ha.py
```

### 日志分析
```bash
# 查看同步相关日志
grep -i sync logs/simple_ha.log

# 查看错误日志
grep -i error logs/simple_ha.log | grep sync
```

## 📈 性能优化

### 配置调优
```yaml
synchronization:
  # 高性能配置
  batch_size: 200                 # 增加批量大小
  sync_interval: 0.5              # 减少处理间隔
  max_queue_size: 2000           # 增加队列容量
  
  # 网络优化
  sync_timeout: 60               # 增加超时时间
  enable_compression: true       # 启用压缩传输
```

### 监控建议
- 定期检查同步延迟
- 监控队列大小变化
- 关注错误日志
- 设置告警阈值

## 🔧 高级功能

### 自定义同步策略
可以通过修改 `DistributedHAManager` 类来实现自定义同步逻辑：

```python
# 自定义同步过滤器
def custom_sync_filter(operation):
    # 只同步特定类型的数据
    if operation.table_name == 'images':
        return operation.data.get('is_downloaded', False)
    return True
```

### 同步回调函数
```python
# 注册同步完成回调
def on_sync_complete(operation, success):
    if success:
        logger.info(f"同步完成: {operation.operation_id}")
    else:
        logger.error(f"同步失败: {operation.operation_id}")

ha_manager.add_sync_callback(on_sync_complete)
```

## 📚 相关文档

- [分布式高可用架构指南](DISTRIBUTED_HA_README.md)
- [灾难恢复指南](DISASTER_RECOVERY_GUIDE.md)
- [PostgreSQL HA 设置](POSTGRESQL_HA_SETUP.md)
- [系统使用说明](USAGE.md)

---

**注意**: 自动同步功能需要确保主备数据库之间的网络连接稳定，建议在生产环境中配置专用的数据库同步网络。
