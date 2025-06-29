# 🛡️ 容灾备份架构指南

## 问题分析：为什么之前的设计不合理？

### ❌ 原有设计的问题

1. **伪分布式架构**
   ```
   同一台服务器上：
   ├── data/images_primary.db     (主数据库)
   ├── data/images_secondary1.db (备用数据库1)  
   └── data/images_secondary2.db (备用数据库2)
   ```
   - 所有数据库文件在同一台服务器
   - 服务器宕机时所有数据库都不可用
   - 只是文件复制，不是真正的数据库复制

2. **单点故障风险**
   - 硬件故障：整台服务器宕机
   - 操作系统故障：所有数据库实例失效
   - 磁盘故障：所有数据库文件损坏
   - 网络故障：整个服务不可访问

3. **缺乏真正的容灾能力**
   - 无法应对机房断电
   - 无法应对自然灾害
   - 无法应对网络分区
   - 无法实现异地容灾

## ✅ 正确的容灾备份架构

### 1. 真正的分布式部署

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   服务器 A       │    │   服务器 B       │    │   服务器 C       │
│   (主数据中心)   │    │   (同城备份)     │    │   (异地备份)     │
│                │    │                │    │                │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ PostgreSQL  │ │    │ │ PostgreSQL  │ │    │ │ PostgreSQL  │ │
│ │ Primary     │◄────┤ │ Standby 1   │ │    │ │ Standby 2   │ │
│ │ 主数据库     │ │ │  │ │ 备用数据库1  │ │    │ │ 备用数据库2  │ │
│ └─────────────┘ │ │  │ └─────────────┘ │    │ └─────────────┘ │
│                │ │  │                │    │                │
│ 爬虫应用        │ │  │ 爬虫应用        │    │ 爬虫应用        │
│ 192.168.1.100  │ │  │ 192.168.1.101  │    │ 192.168.2.100  │
└─────────────────┘ │  └─────────────────┘    └─────────────────┘
                    │
                    └── 流复制/逻辑复制
```

### 2. 数据库级别的复制

#### PostgreSQL 流复制
```sql
-- 主数据库配置
wal_level = replica
max_wal_senders = 3
wal_keep_segments = 64
archive_mode = on
archive_command = 'cp %p /archive/%f'

-- 备用数据库自动从主数据库同步
```

#### PostgreSQL 逻辑复制
```sql
-- 主数据库创建发布
CREATE PUBLICATION crawler_pub FOR ALL TABLES;

-- 备用数据库创建订阅
CREATE SUBSCRIPTION crawler_sub 
CONNECTION 'host=primary_server dbname=crawler user=repl_user' 
PUBLICATION crawler_pub;
```

### 3. 多层次容灾策略

#### 第一层：本地高可用
- **主服务器**：处理所有读写请求
- **本地备用**：同机房热备，秒级切换
- **用途**：应对单机故障

#### 第二层：同城容灾
- **同城备份中心**：不同机房，分钟级切换
- **用途**：应对机房故障、网络故障

#### 第三层：异地容灾
- **异地备份中心**：不同城市，小时级切换
- **用途**：应对自然灾害、区域性故障

## 🚀 实施方案

### 方案一：生产环境（推荐）

#### 硬件要求
```yaml
主服务器:
  CPU: 8核+
  内存: 16GB+
  存储: SSD 500GB+
  网络: 千兆网卡
  位置: 主数据中心

同城备份:
  CPU: 8核+
  内存: 16GB+
  存储: SSD 500GB+
  网络: 千兆网卡
  位置: 同城不同机房

异地备份:
  CPU: 4核+
  内存: 8GB+
  存储: SSD 200GB+
  网络: 百兆网卡
  位置: 异地数据中心
```

#### 配置示例
```yaml
disaster_recovery:
  enabled: true
  mode: "distributed"
  
  databases:
    primary:
      host: "db-primary.company.com"
      port: 5432
      database: "image_crawler"
      server_info:
        location: "主数据中心"
        ip: "10.0.1.100"
        region: "华东"
        
    secondary1:
      host: "db-backup1.company.com"
      port: 5432
      database: "image_crawler"
      server_info:
        location: "同城备份中心"
        ip: "10.0.2.100"
        region: "华东"
        
    secondary2:
      host: "db-backup2.company.com"
      port: 5432
      database: "image_crawler"
      server_info:
        location: "异地备份中心"
        ip: "10.1.1.100"
        region: "华南"
```

### 方案二：开发测试环境

#### 使用Docker模拟多服务器
```yaml
# docker-compose.yml
version: '3.8'
services:
  db-primary:
    image: postgres:13
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: image_crawler_primary
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - primary_data:/var/lib/postgresql/data
      
  db-secondary1:
    image: postgres:13
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: image_crawler_backup1
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - secondary1_data:/var/lib/postgresql/data
      
  db-secondary2:
    image: postgres:13
    ports:
      - "5434:5432"
    environment:
      POSTGRES_DB: image_crawler_backup2
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - secondary2_data:/var/lib/postgresql/data

volumes:
  primary_data:
  secondary1_data:
  secondary2_data:
```

### 方案三：云服务环境

#### 使用云数据库服务
```yaml
# 阿里云RDS示例
disaster_recovery:
  databases:
    primary:
      host: "rm-xxxxxxxx.mysql.rds.aliyuncs.com"
      region: "华东1"
      
    secondary1:
      host: "rm-yyyyyyyy.mysql.rds.aliyuncs.com"
      region: "华东2"
      
    secondary2:
      host: "rm-zzzzzzzz.mysql.rds.aliyuncs.com"
      region: "华南1"
```

## 📋 部署检查清单

### 部署前检查
- [ ] 确认服务器分布在不同物理位置
- [ ] 验证网络连通性和延迟
- [ ] 配置数据库复制用户和权限
- [ ] 设置防火墙规则
- [ ] 准备SSL证书（如需要）

### 部署后验证
- [ ] 测试所有数据库连接
- [ ] 验证数据复制是否正常
- [ ] 测试手动故障转移
- [ ] 验证自动故障转移
- [ ] 检查监控和告警

### 运维检查
- [ ] 定期检查复制延迟
- [ ] 监控磁盘空间使用
- [ ] 验证备份完整性
- [ ] 测试故障恢复流程
- [ ] 更新容灾演练计划

## 🎯 最佳实践

### 1. 数据库配置
- 使用专用的复制用户
- 配置合适的WAL保留策略
- 启用连接池和连接复用
- 定期清理归档日志

### 2. 网络配置
- 使用专用网络连接
- 配置网络QoS保证复制优先级
- 启用网络加密
- 监控网络延迟和丢包

### 3. 监控告警
- 设置复制延迟告警
- 监控磁盘空间使用
- 配置数据库连接告警
- 建立故障通知机制

### 4. 安全配置
- 使用强密码和密钥
- 限制网络访问权限
- 启用数据库审计
- 定期更新安全补丁

## 🔧 故障处理

### 常见故障场景

#### 主数据库故障
1. **检测**：健康检查失败
2. **切换**：自动切换到同城备份
3. **恢复**：修复主数据库后重新同步
4. **回切**：可选择回切到原主数据库

#### 网络分区
1. **检测**：部分数据库不可达
2. **策略**：保持当前主数据库运行
3. **监控**：持续监控网络状态
4. **恢复**：网络恢复后重新建立复制

#### 数据中心故障
1. **检测**：整个数据中心不可达
2. **切换**：切换到异地备份中心
3. **通知**：通知相关人员
4. **恢复**：制定数据中心恢复计划

---

**总结**：真正的容灾备份需要多服务器、多地域的分布式部署，使用数据库原生的复制功能，而不是简单的文件复制。这样才能在各种故障场景下保证业务连续性和数据安全。
