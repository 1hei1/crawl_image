# 🛡️ 容灾备份系统

为图片爬取系统增加的数据库容灾备份功能，实现一台服务器宕机另一台可以立即接管的高可用性架构。

## ✨ 功能特性

### 🔄 主从数据库架构
- ✅ 支持多个数据库实例（1主 + N备）
- ✅ 自动选择最优数据库作为主数据库
- ✅ 按优先级进行智能故障转移
- ✅ 支持 SQLite 和 PostgreSQL

### 💾 智能备份管理
- ✅ 定时自动备份数据库
- ✅ 备份文件压缩和自动清理
- ✅ 一键备份恢复功能
- ✅ 备份完整性验证

### 🔍 实时健康监控
- ✅ 数据库连接状态监控
- ✅ 响应时间性能监控
- ✅ 自定义告警规则
- ✅ 历史数据记录和分析

### ⚡ 自动故障转移
- ✅ 实时故障检测
- ✅ 秒级自动切换
- ✅ 零配置智能选择备用数据库
- ✅ 故障转移历史记录

## 🚀 快速开始

### 1. 启用容灾功能

编辑 `config/config.yaml`：

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

### 2. 启动系统

```bash
# 查看系统状态
python disaster_recovery.py status

# 启动监控服务
python disaster_recovery.py start-monitoring

# 创建备份
python disaster_recovery.py backup
```

## 📋 主要命令

```bash
# 系统状态
python disaster_recovery.py status

# 备份管理
python disaster_recovery.py backup                    # 创建备份
python disaster_recovery.py backup --name my_backup   # 指定备份名称
python disaster_recovery.py restore backup.sql        # 恢复备份

# 故障转移
python disaster_recovery.py failover secondary1       # 手动故障转移
python disaster_recovery.py history                   # 查看转移历史

# 监控控制
python disaster_recovery.py start-monitoring          # 启动监控
python disaster_recovery.py enable-auto-failover      # 启用自动故障转移
python disaster_recovery.py disable-auto-failover     # 禁用自动故障转移

# 连接测试
python disaster_recovery.py test                      # 测试数据库连接
```

## 🏗️ 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   主数据库       │    │   备用数据库1    │    │   备用数据库2    │
│   (Primary)     │    │   (Secondary1)  │    │   (Secondary2)  │
│   优先级: 0     │    │   优先级: 1     │    │   优先级: 2     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   容灾管理器     │
                    │                │
                    │ • 健康监控      │
                    │ • 故障检测      │
                    │ • 自动切换      │
                    │ • 备份管理      │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   应用程序       │
                    │  (图片爬虫)     │
                    └─────────────────┘
```

## 📁 文件结构

```
image_crawler/
├── database/
│   ├── backup_manager.py      # 备份管理器
│   ├── health_monitor.py      # 健康监控器
│   ├── failover_manager.py    # 故障转移管理器
│   └── enhanced_manager.py    # 增强数据库管理器
├── tools/
│   └── disaster_recovery_cli.py  # 命令行工具
├── config/
│   └── disaster_recovery_example.yaml  # 配置示例
├── docs/
│   └── DISASTER_RECOVERY.md   # 详细文档
├── tests/
│   └── test_disaster_recovery.py  # 测试用例
└── disaster_recovery.py       # 管理脚本
```

## 🔧 配置示例

### SQLite 配置
```yaml
disaster_recovery:
  enabled: true
  databases:
    primary:
      url: "sqlite:///data/images_primary.db"
    secondary1:
      url: "sqlite:///backup/images_secondary1.db"
```

### PostgreSQL 配置
```yaml
disaster_recovery:
  enabled: true
  databases:
    primary:
      url: "postgresql://user:pass@localhost:5432/crawler_db"
    secondary1:
      url: "postgresql://user:pass@backup-server:5432/crawler_backup"
```

## 📊 监控面板

运行 `python disaster_recovery.py status` 查看：

```
=== 容灾备份系统状态 ===
容灾备份功能: 启用

--- 数据库状态 ---
当前主数据库: primary
自动备份: 启用
健康监控: 启用
自动故障转移: 启用

  🟢 primary 👑
    类型: primary
    优先级: 0
    连接状态: 正常

  🟢 secondary1
    类型: secondary
    优先级: 1
    连接状态: 正常

--- 健康状态 ---
整体状态: healthy
  primary: healthy
    响应时间: 12.34ms
  secondary1: healthy
    响应时间: 15.67ms

--- 故障转移状态 ---
当前状态: normal
自动故障转移: 启用
检测阈值: 3
```

## 🧪 测试

运行测试用例：

```bash
python -m pytest tests/test_disaster_recovery.py -v
```

## 📚 详细文档

- [完整使用指南](docs/DISASTER_RECOVERY.md)
- [配置示例](config/disaster_recovery_example.yaml)

## 🛠️ 故障排除

### 常见问题

**Q: 容灾功能无法启用**
```bash
# 检查配置
python disaster_recovery.py status
```

**Q: 自动故障转移不工作**
```bash
# 检查监控服务
python disaster_recovery.py start-monitoring
```

**Q: 备份创建失败**
```bash
# 测试数据库连接
python disaster_recovery.py test
```

## 🎯 最佳实践

1. **定期测试**：定期执行故障转移测试
2. **监控告警**：配置合适的告警阈值
3. **备份验证**：定期验证备份文件完整性
4. **异地部署**：将备用数据库部署在不同位置
5. **文档记录**：记录故障转移操作流程

## 🔒 安全考虑

- 数据库连接使用加密传输
- 备份文件支持压缩和加密
- 访问权限控制和审计日志
- 敏感信息配置文件保护

## 📈 性能优化

- 监控频率可调节，避免过度检查
- 备份策略可配置，支持增量备份
- 故障转移时间优化，最小化服务中断
- 资源使用监控，避免影响主业务

---

**🎉 现在您的图片爬取系统已经具备了企业级的容灾备份能力！**

当主数据库出现故障时，系统会自动检测并在几秒内切换到备用数据库，确保服务的连续性和数据的安全性。
