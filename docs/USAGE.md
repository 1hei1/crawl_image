# 使用说明

本文档详细介绍如何使用智能图片爬虫系统。

## 📋 目录

- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [命令行使用](#命令行使用)
- [Python API](#python-api)
- [高级功能](#高级功能)
- [故障排除](#故障排除)

## 🚀 快速开始

### 1. 环境准备

确保您的系统满足以下要求：
- Python 3.8 或更高版本
- 至少 2GB 可用内存
- 稳定的网络连接

### 2. 安装依赖

```bash
cd image_crawler
pip install -r requirements.txt
```

### 3. 初始化配置

```bash
python main.py init-config
```

这将在 `config/` 目录下生成默认配置文件 `config.yaml`。

### 4. 第一次爬取

使用交互式界面：
```bash
python run.py
```

或使用命令行：
```bash
python main.py crawl https://example.com
```

## ⚙️ 配置说明

### 配置文件结构

配置文件采用 YAML 格式，主要包含以下部分：

```yaml
# 项目基本信息
project_name: "图片爬虫系统"
version: "1.0.0"
environment: "development"
debug: true

# 数据库配置
database:
  type: "sqlite"
  sqlite_path: "data/images.db"

# 爬虫配置
crawler:
  max_depth: 3
  max_images: 1000
  max_concurrent: 10

# 反爬虫配置
anti_crawler:
  use_random_user_agent: true
  random_delay: true

# 分类配置
classification:
  enable_auto_classification: true

# 日志配置
logging:
  level: "INFO"
  log_file: "logs/crawler.log"
```

### 重要配置项说明

#### 数据库配置

**SQLite（推荐用于开发和小规模使用）**
```yaml
database:
  type: "sqlite"
  sqlite_path: "data/images.db"
```

**PostgreSQL（推荐用于生产环境）**
```yaml
database:
  type: "postgresql"
  host: "localhost"
  port: 5432
  database: "image_crawler"
  username: "your_username"
  password: "your_password"
```

#### 爬虫性能配置

```yaml
crawler:
  max_depth: 3              # 爬取深度，建议 1-5
  max_images: 1000          # 最大图片数量
  max_concurrent: 10        # 并发数，根据网络和目标服务器调整
  request_delay: 1.0        # 请求延迟（秒）
  timeout: 30               # 请求超时时间
```

#### 反爬虫配置

```yaml
anti_crawler:
  use_random_user_agent: true    # 随机 User-Agent
  use_proxy: false               # 是否使用代理
  proxy_list: []                 # 代理列表
  random_delay: true             # 随机延迟
  min_delay: 0.5                 # 最小延迟
  max_delay: 3.0                 # 最大延迟
```

### 环境变量配置

您也可以使用环境变量覆盖配置文件中的设置：

```bash
# 数据库配置
export DB_TYPE=postgresql
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=image_crawler
export DB_USER=username
export DB_PASSWORD=password

# 爬虫配置
export CRAWLER_MAX_DEPTH=5
export CRAWLER_MAX_IMAGES=2000
export CRAWLER_MAX_CONCURRENT=20

# 日志配置
export LOG_LEVEL=DEBUG
export LOG_FILE=logs/debug.log
```

## 💻 命令行使用

### 基本命令

```bash
# 查看帮助
python main.py --help

# 爬取单个网站
python main.py crawl https://example.com

# 指定会话名称
python main.py crawl https://example.com --name "example_session"

# 使用自定义配置文件
python main.py -c my_config.yaml crawl https://example.com

# 详细输出模式
python main.py -v crawl https://example.com
```

### 批量爬取

```bash
# 批量爬取多个网站
python main.py batch https://site1.com https://site2.com https://site3.com

# 指定批次名称
python main.py batch --name "batch_001" https://site1.com https://site2.com
```

### 系统管理

```bash
# 查看统计信息
python main.py stats

# 停止所有活跃任务
python main.py stop

# 测试系统
python main.py test

# 生成配置文件
python main.py init-config --output my_config.yaml
```

## 🐍 Python API

### 基本使用

```python
import asyncio
from crawler.main_crawler import ImageCrawler

async def main():
    # 初始化爬虫
    crawler = ImageCrawler('config/config.yaml')
    
    # 爬取网站
    result = await crawler.crawl_website('https://example.com')
    
    if result['success']:
        print(f"爬取成功: {result['summary']}")
        print(f"下载图片: {result['stats']['images_downloaded']}")
    else:
        print(f"爬取失败: {result['error']}")

# 运行
asyncio.run(main())
```

### 带进度回调的爬取

```python
async def progress_callback(stats):
    print(f"进度: {stats['pages_crawled']} 页面, {stats['images_downloaded']} 图片")

async def main():
    crawler = ImageCrawler()
    
    result = await crawler.crawl_website(
        url='https://example.com',
        session_name='my_session',
        progress_callback=progress_callback
    )
```

### 批量爬取

```python
async def main():
    crawler = ImageCrawler()
    
    urls = [
        'https://site1.com',
        'https://site2.com',
        'https://site3.com'
    ]
    
    results = await crawler.crawl_multiple_websites(urls, 'batch_session')
    
    for result in results:
        if result['success']:
            print(f"✅ {result['start_url']}: {result['summary']}")
        else:
            print(f"❌ {result['start_url']}: {result['error']}")
```

### 获取统计信息

```python
def main():
    crawler = ImageCrawler()
    stats = crawler.get_statistics()
    
    print(f"总图片数: {stats['total_images']}")
    print(f"已下载: {stats['downloaded_images']}")
    print(f"总会话: {stats['total_sessions']}")
```

## 🔧 高级功能

### 自定义图片分类规则

编辑配置文件中的分类规则：

```yaml
classification:
  enable_auto_classification: true
  
  # 基于文件名的分类规则
  filename_rules:
    "产品图片":
      - "product"
      - "item"
      - "goods"
    "用户头像":
      - "avatar"
      - "profile"
      - "user"
  
  # 基于尺寸的分类规则
  size_rules:
    "大图":
      min_width: 1200
      min_height: 800
    "小图标":
      max_width: 100
      max_height: 100
```

### 使用代理

```yaml
anti_crawler:
  use_proxy: true
  proxy_list:
    - "http://proxy1:8080"
    - "http://proxy2:8080"
    - "socks5://proxy3:1080"
  proxy_rotation: true
```

### 自定义 User-Agent

```yaml
anti_crawler:
  use_random_user_agent: true
  custom_user_agents:
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
```

### 文件过滤

```yaml
crawler:
  # 允许的文件扩展名
  allowed_extensions:
    - ".jpg"
    - ".png"
    - ".webp"
  
  # 文件大小限制
  min_file_size: 1024      # 1KB
  max_file_size: 10485760  # 10MB
  
  # 图片尺寸限制
  min_width: 100
  min_height: 100
  max_width: 5000
  max_height: 5000
```

## 🔍 故障排除

### 常见问题

**1. 网络连接失败**
```
错误: aiohttp.ClientConnectorError
解决: 检查网络连接，尝试使用代理
```

**2. 图片下载失败**
```
错误: HTTP 403 Forbidden
解决: 调整 User-Agent 设置，增加请求延迟
```

**3. 数据库连接失败**
```
错误: sqlalchemy.exc.OperationalError
解决: 检查数据库配置和服务状态
```

**4. 内存使用过高**
```
解决: 减少并发数，设置图片大小限制
```

### 调试模式

启用详细日志：
```bash
python main.py -v crawl https://example.com
```

或在配置文件中设置：
```yaml
logging:
  level: "DEBUG"
  verbose: true
```

### 性能优化

**提高下载速度：**
- 增加并发数（注意服务器负载）
- 使用更快的网络连接
- 启用代理池

**减少资源使用：**
- 设置合理的图片大小限制
- 启用图片格式过滤
- 定期清理下载目录

### 日志分析

日志文件位置：
- 普通日志: `logs/crawler.log`
- 错误日志: `logs/crawler_error.log`

查看实时日志：
```bash
tail -f logs/crawler.log
```

## 📞 获取帮助

如果遇到问题，请：

1. 查看日志文件获取详细错误信息
2. 检查配置文件是否正确
3. 运行系统测试: `python main.py test`
4. 查看项目文档和示例
5. 提交 GitHub Issue

---

更多详细信息请参考项目 README 文件。
