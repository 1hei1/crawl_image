# 快速启动指南

## 🚀 5分钟快速开始

### 步骤1：安装依赖

**推荐方式（解决编码问题）：**
```bash
cd image_crawler
python install.py
```

**如果上述方式不可用：**
```bash
pip install requests beautifulsoup4 aiohttp sqlalchemy Pillow pyyaml loguru click tqdm fake-useragent
```

### 步骤2：生成配置文件
```bash
python main.py init-config
```

### 步骤3：开始爬取
```bash
python main.py crawl https://httpbin.org
```

## 🎯 常用命令

### 命令行模式
```bash
# 爬取单个网站
python main.py crawl https://example.com

# 指定会话名称
python main.py crawl https://example.com --name "my_session"

# 批量爬取
python main.py batch https://site1.com https://site2.com

# 查看统计信息
python main.py stats

# 测试系统
python main.py test
```

### 交互式模式
```bash
python run.py
```

## ⚠️ 常见问题解决

### 编码错误
如果遇到 `UnicodeDecodeError: 'gbk' codec can't decode byte` 错误：

1. 使用安装脚本：`python install.py`
2. 或手动安装核心依赖：`pip install requests beautifulsoup4 aiohttp sqlalchemy Pillow pyyaml loguru click tqdm fake-useragent`

### 网络连接问题
如果遇到网络连接失败：

1. 检查网络连接
2. 在配置文件中启用代理
3. 调整请求延迟设置

### 权限问题
如果遇到文件权限错误：

1. 确保有写入权限
2. 在Windows上可能需要以管理员身份运行

## 📝 配置示例

### 基本配置 (config/config.yaml)
```yaml
# 数据库配置
database:
  type: "sqlite"
  sqlite_path: "data/images.db"

# 爬虫配置
crawler:
  max_depth: 2
  max_images: 100
  max_concurrent: 5
  request_delay: 1.0

# 反爬虫配置
anti_crawler:
  use_random_user_agent: true
  random_delay: true
  min_delay: 0.5
  max_delay: 2.0
```

## 🔧 Python API 快速示例

```python
import asyncio
from crawler.main_crawler import ImageCrawler

async def main():
    # 初始化爬虫
    crawler = ImageCrawler()
    
    # 爬取网站
    result = await crawler.crawl_website('https://httpbin.org')
    
    if result['success']:
        print(f"成功下载 {result['stats']['images_downloaded']} 张图片")
    else:
        print(f"爬取失败: {result['error']}")

# 运行
asyncio.run(main())
```

## 📊 验证安装

运行以下命令验证安装是否成功：

```bash
python main.py test
```

如果看到 "✅ 系统测试完成"，说明安装成功！

## 🆘 获取帮助

- 查看完整文档：`README.md`
- 查看使用说明：`docs/USAGE.md`
- 运行帮助命令：`python main.py --help`
- 查看示例代码：`examples/basic_example.py`

---

🎉 现在您可以开始使用智能图片爬虫系统了！
