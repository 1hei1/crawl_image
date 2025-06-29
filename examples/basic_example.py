#!/usr/bin/env python3
"""
基本使用示例

演示如何使用图片爬虫系统的基本功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.main_crawler import ImageCrawler


async def basic_crawl_example():
    """基本爬取示例"""
    print("🚀 基本爬取示例")
    print("=" * 50)
    
    try:
        # 初始化爬虫
        print("📝 初始化爬虫...")
        crawler = ImageCrawler()
        
        # 定义进度回调函数
        async def progress_callback(stats):
            print(f"📊 进度更新: "
                  f"页面 {stats.get('pages_crawled', 0)}, "
                  f"图片 {stats.get('images_found', 0)}, "
                  f"下载 {stats.get('images_downloaded', 0)}")
        
        # 爬取网站
        print("🌐 开始爬取网站...")
        result = await crawler.crawl_website(
            url='https://httpbin.org',  # 使用测试网站
            session_name='basic_example',
            progress_callback=progress_callback
        )
        
        # 显示结果
        if result.get('success', False):
            print("\n✅ 爬取成功!")
            print(f"📊 {result.get('summary', '')}")
            
            stats = result.get('stats', {})
            print(f"\n详细统计:")
            print(f"  • 爬取页面: {stats.get('pages_crawled', 0)}")
            print(f"  • 发现图片: {stats.get('images_found', 0)}")
            print(f"  • 下载成功: {stats.get('images_downloaded', 0)}")
            print(f"  • 下载失败: {stats.get('images_failed', 0)}")
            print(f"  • 耗时: {stats.get('duration', 0):.2f}秒")
        else:
            print(f"\n❌ 爬取失败: {result.get('error', '未知错误')}")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")


async def batch_crawl_example():
    """批量爬取示例"""
    print("\n🚀 批量爬取示例")
    print("=" * 50)
    
    try:
        # 初始化爬虫
        crawler = ImageCrawler()
        
        # 定义要爬取的网站列表
        urls = [
            'https://httpbin.org',
            'https://jsonplaceholder.typicode.com',
        ]
        
        print(f"🌐 开始批量爬取 {len(urls)} 个网站...")
        
        # 执行批量爬取
        results = await crawler.crawl_multiple_websites(urls, 'batch_example')
        
        # 统计结果
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        
        print(f"\n📊 批量爬取完成:")
        print(f"  • 成功: {successful}")
        print(f"  • 失败: {failed}")
        print(f"  • 总计: {len(results)}")
        
        # 显示详细结果
        print(f"\n详细结果:")
        for i, result in enumerate(results):
            status = "✅" if result.get('success', False) else "❌"
            url = urls[i] if i < len(urls) else "未知"
            summary = result.get('summary', result.get('error', '无信息'))
            print(f"  {status} {url}")
            print(f"     {summary}")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")


def statistics_example():
    """统计信息示例"""
    print("\n🚀 统计信息示例")
    print("=" * 50)
    
    try:
        # 初始化爬虫
        crawler = ImageCrawler()
        
        # 获取统计信息
        stats = crawler.get_statistics()
        
        print("📊 系统统计信息:")
        print(f"  • 总图片数: {stats['total_images']}")
        print(f"  • 已下载图片: {stats['downloaded_images']}")
        print(f"  • 爬取会话数: {stats['total_sessions']}")
        print(f"  • 活跃任务数: {stats['active_tasks']}")
        
        # 数据库信息
        db_info = stats.get('database_info', {})
        print(f"\n💾 数据库信息:")
        if isinstance(db_info.get('tables'), dict):
            tables = db_info['tables']
            print(f"  • 图片记录: {tables.get('images', 0)}")
            print(f"  • 分类记录: {tables.get('categories', 0)}")
            print(f"  • 标签记录: {tables.get('tags', 0)}")
            print(f"  • 会话记录: {tables.get('crawl_sessions', 0)}")
        
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")


async def custom_config_example():
    """自定义配置示例"""
    print("\n🚀 自定义配置示例")
    print("=" * 50)
    
    try:
        # 使用自定义配置文件（如果存在）
        config_file = Path(__file__).parent.parent / 'config' / 'config.yaml'
        
        if config_file.exists():
            print(f"📝 使用配置文件: {config_file}")
            crawler = ImageCrawler(str(config_file))
        else:
            print("📝 使用默认配置")
            crawler = ImageCrawler()
        
        # 显示配置摘要
        config_summary = crawler.config_manager.get_config_summary()
        print(f"\n⚙️ 配置摘要:")
        print(f"  • 数据库类型: {config_summary['database_type']}")
        print(f"  • 最大深度: {config_summary['max_depth']}")
        print(f"  • 最大图片数: {config_summary['max_images']}")
        print(f"  • 最大并发数: {config_summary['max_concurrent']}")
        print(f"  • 下载路径: {config_summary['download_path']}")
        print(f"  • 日志级别: {config_summary['log_level']}")
        print(f"  • 环境: {config_summary['environment']}")
        
    except Exception as e:
        print(f"❌ 配置示例失败: {e}")


async def main():
    """主函数"""
    print("🎯 图片爬虫系统使用示例")
    print("=" * 60)
    
    # 运行各种示例
    await basic_crawl_example()
    await batch_crawl_example()
    statistics_example()
    await custom_config_example()
    
    print("\n🎉 所有示例运行完成!")
    print("\n💡 提示:")
    print("  • 查看 docs/USAGE.md 获取详细使用说明")
    print("  • 运行 python main.py --help 查看命令行选项")
    print("  • 运行 python run.py 使用交互式界面")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  示例被用户中断")
    except Exception as e:
        print(f"\n❌ 运行示例时发生错误: {e}")
        import traceback
        traceback.print_exc()
