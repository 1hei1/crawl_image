# 智能图片爬虫分布式高可用系统

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-生产就绪-brightgreen.svg)

一个企业级的智能图片爬虫系统，具备分布式高可用架构、自动故障转移、实时数据同步等特性。专为大规模图片采集和管理而设计，支持跨服务器部署和容灾恢复。

## 🌟 系统特色

### 🏗️ 分布式高可用架构
- **双机热备**: 主备PostgreSQL数据库自动同步
- **自动故障转移**: 主数据库故障时秒级切换到备用数据库
- **实时健康监控**: 持续监控数据库和服务状态
- **数据一致性**: 确保主备数据库数据完全一致
- **零停机维护**: 支持在线维护和升级

### 🚀 核心功能特性
- **🕷️ 智能爬虫引擎**: 支持多种网站的图片爬取，智能URL解析和递归爬取
- **🏷️ AI智能分类**: 基于内容、尺寸、质量的多维度自动分类系统
- **⚡ 异步高并发**: 基于asyncio的高性能异步处理架构，支持数千并发
- **🛡️ 反爬虫机制**: User-Agent轮换、代理支持、智能延迟控制
- **📊 实时监控**: Web界面监控、API状态查询、详细日志分析
- **🗄️ 多数据库支持**: PostgreSQL集群 + SQLite本地缓存
- **🔧 灵活配置**: YAML配置文件、环境变量、动态配置更新
- **💾 自动备份**: 定时数据备份和一键恢复机制

### 🌐 分布式部署架构
```
┌─────────────────────────────┐    ┌─────────────────────────────┐
│        主服务器              │    │        备服务器              │
│    113.29.231.99           │◄──►│    113.29.232.245          │
│                            │    │                            │
│ ┌─────────────────────────┐ │    │ ┌─────────────────────────┐ │
│ │   PostgreSQL 16         │ │    │ │   PostgreSQL 16         │ │
│ │   (Primary Database)    │ │    │ │   (Backup Database)     │ │
│ │   Port: 5432           │ │    │ │   Port: 5432           │ │
│ │   实时数据同步           │ │    │ │   自动故障接管          │ │
│ └─────────────────────────┘ │    │ └─────────────────────────┘ │
│                            │    │                            │
│ ┌─────────────────────────┐ │    │ ┌─────────────────────────┐ │
│ │   HA管理器              │ │    │ │   HA管理器              │ │
│ │   - 健康监控            │ │    │ │   - 状态同步            │ │
│ │   - 故障检测            │ │    │ │   - 备份管理            │ │
│ │   - API: 8001          │ │    │ │   - API: 8001          │ │
│ └─────────────────────────┘ │    │ └─────────────────────────┘ │
│                            │    │                            │
│ ┌─────────────────────────┐ │    │ ┌─────────────────────────┐ │
│ │   爬虫API服务           │ │    │ │   文件同步服务          │ │
│ │   - 图片爬取            │ │    │ │   - 图片文件同步        │ │
│ │   - 智能分类            │ │    │ │   - 数据备份            │ │
│ │   - Port: 8000         │ │    │ │   - 状态监控            │ │
│ └─────────────────────────┘ │    │ └─────────────────────────┘ │
└─────────────────────────────┘    └─────────────────────────────┘
```

## 🛠️ 技术栈

### 后端核心
- **Python 3.8+**: 主要开发语言
- **FastAPI**: 现代化的Web API框架
- **SQLAlchemy 2.0**: 强大的ORM框架
- **asyncio/aiohttp**: 异步编程和HTTP客户端
- **PostgreSQL 16**: 企业级关系数据库

### 爬虫引擎
- **BeautifulSoup4**: HTML解析和数据提取
- **Scrapy**: 专业的网络爬虫框架
- **requests**: HTTP请求库
- **fake-useragent**: User-Agent伪装

### 图片处理
- **Pillow**: 图片处理和格式转换
- **OpenCV**: 计算机视觉和图像分析
- **hashlib**: 图片去重和完整性校验

### 监控和日志
- **loguru**: 高级日志管理
- **uvicorn**: ASGI服务器
- **pyyaml**: 配置文件管理

## 🚀 快速开始

### 📋 系统要求

#### 硬件要求
- **CPU**: 2核心以上
- **内存**: 4GB RAM (推荐8GB)
- **存储**: 20GB可用空间 (用于图片存储)
- **网络**: 稳定的互联网连接

#### 软件要求
- **Python**: 3.8+ (推荐3.11)
- **PostgreSQL**: 16+ (两台服务器)
- **操作系统**: Windows/Linux/macOS

#### 服务器配置
- **主服务器**: 113.29.231.99:5432 (PostgreSQL)
- **备服务器**: 113.29.232.245:5432 (PostgreSQL)
- **用户名**: postgres
- **密码**: Abcdefg6
- **数据库**: image_crawler

### 📦 安装步骤

#### 1. 克隆项目
```bash
git clone <repository-url>
cd image_crawler
```

#### 2. 安装依赖
推荐使用我们提供的安装脚本，可以自动处理编码问题：

```bash
python install.py
```

或者手动安装：
```bash
pip install -r requirements.txt
```

#### 3. 数据库初始化
系统会自动连接到配置的PostgreSQL服务器，首次运行时会自动创建必要的表结构：

```bash
# 初始化PostgreSQL数据库
python setup_postgresql_databases.py
```

#### 4. 配置验证
系统使用预配置的分布式高可用配置文件 `config/distributed_ha_config.yaml`：


````yaml
# 本地节点配置
local_node: "primary_node"

# 数据库节点配置
nodes:
  primary_node:
    name: "primary_node"
    role: "primary"
    server:
      host: "113.29.231.99"
      port: 5432
    database_url: "postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler"

  backup_node:
    name: "backup_node"
    role: "secondary"
    server:
      host: "113.29.232.245"
      port: 5432
    database_url: "postgresql://postgres:Abcdefg6@113.29.232.245:5432/image_crawler"
````

### 🎯 系统启动

#### 启动分布式高可用系统 (推荐)

使用系统启动文件启动完整的高可用系统：

```bash
python start_simple_ha.py
```

**启动过程说明**：
1. **连接测试**: 自动测试两台PostgreSQL服务器连接
2. **配置加载**: 加载分布式高可用配置
3. **HA管理器**: 启动高可用管理器，监控数据库状态
4. **API服务**: 启动HA管理API (端口8001) 和主应用API (端口8000)
5. **状态显示**: 显示系统运行状态和访问地址

**启动成功输出示例**：
```
PostgreSQL分布式高可用数据库系统
============================================================
主数据库: 113.29.231.99:5432
备数据库: 113.29.232.245:5432
============================================================

数据库连接测试通过

启动PostgreSQL分布式高可用数据库系统
============================================================
加载配置文件...
配置加载成功，本地节点: primary_node
发现 2 个数据库节点
初始化HA管理器...
HA管理器启动成功，当前主节点: primary_node
启动HA API服务器...
HA API服务器启动成功 (端口: 8001)
启动主应用API服务器...
主API服务器启动成功 (端口: 8000)

============================================================
PostgreSQL分布式高可用数据库系统状态
============================================================
当前主节点: primary_node
本地节点: primary_node
监控状态: 运行中
同步队列: 0 个操作

数据库节点:
  主节点: primary_node
    状态: 健康
    服务器: 113.29.231.99:5432
    优先级: 1

  备节点: backup_node
    状态: 健康
    服务器: 113.29.232.245:5432
    优先级: 2

API服务:
  主应用: http://localhost:8000
  HA管理: http://localhost:8001/api/status
  集群状态: http://localhost:8000/api/ha-status
============================================================

系统启动完成！
按 Ctrl+C 停止系统
```

#### 其他启动方式

**简单模式 (单机SQLite)**:
```bash
# 命令行模式
python main.py crawl https://example.com

# 交互式模式
python run.py
```

**灾难恢复模式**:
```bash
# 启动灾难恢复系统
python disaster_recovery.py
```

### 🌐 系统访问地址

系统启动后，可通过以下地址访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| **主应用API** | http://localhost:8000 | 爬虫核心功能API |
| **HA管理API** | http://localhost:8001 | 高可用管理和监控API |
| **Web界面** | http://localhost:8000/frontend/ | 图形化管理界面 |
| **API文档** | http://localhost:8000/docs | 自动生成的API文档 |
| **集群状态** | http://localhost:8000/api/ha-status | 集群状态查询 |
| **健康检查** | http://localhost:8001/api/status | 详细健康状态 |

## 📡 API接口详解

### 主应用API (端口8000)

#### 爬虫控制接口
```bash
# 启动爬取任务
POST /api/crawl
{
    "url": "https://example.com",
    "max_images": 100,
    "max_depth": 2,
    "categories": ["nature", "technology"]
}

# 查询任务状态
GET /api/status/{task_id}

# 获取爬取结果
GET /api/results/{task_id}

# 停止爬取任务
POST /api/stop/{task_id}
```

#### 图片管理接口
```bash
# 获取图片列表
GET /api/images?page=1&limit=20&category=nature

# 获取图片详情
GET /api/images/{image_id}

# 下载图片
GET /api/images/{image_id}/download

# 删除图片
DELETE /api/images/{image_id}
```

#### 系统状态接口
```bash
# 获取系统状态
GET /api/system-status

# 获取HA集群状态
GET /api/ha-status

# 获取统计信息
GET /api/statistics
```

### HA管理API (端口8001)

#### 集群管理接口
```bash
# 获取详细集群状态
GET /api/status

# 手动故障转移
POST /api/failover

# 获取节点信息
GET /api/nodes

# 获取同步状态
GET /api/sync-status
```

#### 备份管理接口
```bash
# 创建备份
POST /api/backup

# 获取备份列表
GET /api/backups

# 恢复备份
POST /api/restore/{backup_id}
```

## 📁 项目结构

```
image_crawler/
├── 📁 config/                      # 配置管理
│   ├── distributed_ha_config.yaml  # 分布式HA配置
│   ├── ha_config_loader.py         # 配置加载器
│   └── settings.py                 # 系统设置
├── 📁 crawler/                     # 爬虫核心引擎
│   ├── 📁 core/                    # 核心组件
│   │   ├── async_crawler.py        # 异步爬虫
│   │   ├── spider.py               # 网页爬取
│   │   └── downloader.py           # 图片下载
│   ├── 📁 handlers/                # 处理器
│   ├── 📁 utils/                   # 工具模块
│   └── main_crawler.py             # 主爬虫类
├── 📁 database/                    # 数据库管理
│   ├── 📁 models/                  # 数据模型
│   │   ├── base.py                 # 基础模型
│   │   ├── image.py                # 图片模型
│   │   └── crawl_session.py        # 爬取会话
│   ├── distributed_ha_manager.py   # 分布式HA管理器
│   ├── backup_manager.py           # 备份管理器
│   ├── health_monitor.py           # 健康监控
│   └── ha_api_server.py            # HA API服务器
├── 📁 storage/                     # 存储管理
│   ├── distributed_file_manager.py # 分布式文件管理
│   └── file_sync_api.py            # 文件同步API
├── 📁 frontend/                    # Web界面
│   ├── index.html                  # 主页面
│   ├── script.js                   # 前端脚本
│   └── style.css                   # 样式文件
├── 📁 logs/                        # 日志文件
├── 📁 data/                        # 数据存储
├── 📁 backups/                     # 数据备份
├── 📁 tests/                       # 测试用例
├── 📁 docs/                        # 文档
├── 📁 examples/                    # 示例代码
├── 🚀 start_simple_ha.py           # 系统启动文件 (主要入口)
├── api.py                          # FastAPI应用
├── main.py                         # 命令行入口
├── run.py                          # 交互式入口
├── disaster_recovery.py            # 灾难恢复
├── requirements.txt                # 依赖列表
└── README.md                       # 本文档
```

## 💡 使用示例

### 基本爬取示例

#### 1. 通过API启动爬取
```bash
# 使用curl启动爬取任务
curl -X POST "http://localhost:8000/api/crawl" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "max_images": 50,
       "max_depth": 2,
       "download_images": true
     }'
```

#### 2. Python API调用
```python
import asyncio
import aiohttp

async def start_crawl():
    async with aiohttp.ClientSession() as session:
        data = {
            "url": "https://example.com",
            "max_images": 100,
            "max_depth": 3,
            "categories": ["nature", "technology"]
        }
        async with session.post("http://localhost:8000/api/crawl", json=data) as resp:
            result = await resp.json()
            task_id = result["task_id"]
            print(f"爬取任务已启动，任务ID: {task_id}")
            return task_id

# 运行示例
task_id = asyncio.run(start_crawl())
```

#### 3. 监控爬取进度
```python
import asyncio
import aiohttp

async def monitor_task(task_id):
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(f"http://localhost:8000/api/status/{task_id}") as resp:
                status = await resp.json()
                print(f"进度: {status['progress']}%, 已下载: {status['downloaded_count']}张")

                if status['status'] == 'completed':
                    print("爬取完成！")
                    break
                elif status['status'] == 'failed':
                    print(f"爬取失败: {status['error']}")
                    break

            await asyncio.sleep(5)  # 每5秒检查一次

# 监控任务
asyncio.run(monitor_task(task_id))
```

### 高可用功能示例

#### 1. 查询集群状态
```bash
# 获取HA集群状态
curl http://localhost:8001/api/status

# 获取简要状态
curl http://localhost:8000/api/ha-status
```

#### 2. 手动故障转移
```bash
# 触发主备切换
curl -X POST http://localhost:8001/api/failover
```

#### 3. 创建数据备份
```bash
# 创建备份
curl -X POST http://localhost:8001/api/backup

# 查看备份列表
curl http://localhost:8001/api/backups
```

## 🔧 高级配置

### 性能调优
```yaml
# config/distributed_ha_config.yaml
monitoring:
  health_check_interval: 5      # 健康检查间隔(秒)
  failure_threshold: 3          # 故障检测阈值
  auto_failover: true          # 自动故障转移

synchronization:
  batch_size: 100              # 批量同步大小
  sync_interval: 1             # 同步间隔(秒)
  max_retry_attempts: 3        # 最大重试次数
```

### 爬虫配置
```yaml
crawler:
  max_concurrent_requests: 10   # 最大并发请求数
  request_delay: 1             # 请求延迟(秒)
  timeout: 30                  # 请求超时(秒)
  max_retries: 3               # 最大重试次数

image_processing:
  max_file_size: "10MB"        # 最大文件大小
  supported_formats: [".jpg", ".png", ".gif", ".webp"]
  quality_threshold: 0.7       # 质量阈值
```

## 🚨 故障排除

### 常见问题

#### 1. 数据库连接失败
```bash
# 检查PostgreSQL服务状态
systemctl status postgresql

# 测试数据库连接
python test_postgresql_connection.py

# 检查防火墙设置
telnet 113.29.231.99 5432
```

#### 2. 系统启动失败
```bash
# 查看详细日志
tail -f logs/simple_ha.log

# 检查端口占用
netstat -tulpn | grep :8000
netstat -tulpn | grep :8001

# 重置系统状态
python disaster_recovery.py --reset
```

#### 3. 故障转移不工作
```bash
# 检查HA管理器状态
curl http://localhost:8001/api/status

# 手动触发故障转移
curl -X POST http://localhost:8001/api/failover

# 查看HA日志
tail -f logs/ha_system.log
```

#### 4. 图片下载失败
```bash
# 检查网络连接
ping google.com

# 测试目标网站
curl -I https://example.com

# 查看爬虫日志
tail -f logs/crawler.log
```

### 日志文件说明
- `logs/simple_ha.log`: 系统启动和HA管理日志
- `logs/crawler.log`: 爬虫运行日志
- `logs/ha_system.log`: 高可用系统日志
- `logs/postgresql_ha.log`: PostgreSQL相关日志

## 📊 系统监控

### 性能指标
- **数据库连接数**: 监控活跃连接数量
- **爬取速度**: 每分钟处理的图片数量
- **存储使用**: 磁盘空间使用情况
- **网络带宽**: 下载带宽使用率
- **系统资源**: CPU和内存使用率

### 监控命令
```bash
# 查看系统状态
curl http://localhost:8000/api/system-status

# 查看统计信息
curl http://localhost:8000/api/statistics

# 查看集群健康状态
curl http://localhost:8001/api/status
```

## 🎯 最佳实践

### 1. 生产环境部署
- 使用专用的PostgreSQL服务器
- 配置适当的防火墙规则
- 设置定期数据备份
- 监控系统资源使用情况
- 配置日志轮转

### 2. 性能优化
- 根据网络带宽调整并发数
- 使用SSD存储提高I/O性能
- 配置数据库连接池
- 启用图片压缩和去重
- 使用CDN加速图片访问

### 3. 安全考虑
- 使用强密码保护数据库
- 限制API访问权限
- 配置HTTPS加密传输
- 定期更新系统依赖
- 监控异常访问行为

## 🔮 未来规划

### 即将推出的功能
- **机器学习集成**: 基于AI的图片内容识别和分类
- **分布式爬取**: 支持多机器协同爬取
- **云存储支持**: 集成AWS S3、阿里云OSS等云存储
- **实时监控面板**: Web界面的实时监控和管理
- **API限流**: 智能API访问频率控制
- **图片去重优化**: 更高效的重复图片检测算法

### 扩展性增强
- **微服务架构**: 拆分为独立的微服务
- **容器化部署**: Docker和Kubernetes支持
- **负载均衡**: 多实例负载均衡
- **消息队列**: 异步任务处理优化

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：

1. **Fork项目** 到您的GitHub账户
2. **创建功能分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送分支** (`git push origin feature/AmazingFeature`)
5. **创建Pull Request**

### 开发环境设置
```bash
# 克隆开发版本
git clone https://github.com/your-username/image_crawler.git
cd image_crawler

# 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/

# 代码格式化
black .
flake8 .
```

## 📄 许可证

本项目采用 [MIT License](LICENSE) 许可证。

## 📞 支持与联系

- **项目主页**: https://github.com/your-username/image_crawler
- **问题反馈**: https://github.com/your-username/image_crawler/issues
- **文档**: https://your-username.github.io/image_crawler
- **邮箱**: support@example.com

---

## 🌟 致谢

感谢所有为这个项目做出贡献的开发者和用户！

**开发团队**: 智能图片爬虫系统开发组
**版本**: v2.0.0
**最后更新**: 2025年6月26日
**项目状态**: 🟢 生产就绪