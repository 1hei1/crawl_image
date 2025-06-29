"""
图片爬虫主程序

提供命令行接口和程序入口
"""

import asyncio
import click
import sys
import os
from pathlib import Path
from typing import Optional
import time

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from crawler.main_crawler import ImageCrawler
from crawler.utils.logger import LoggerManager, ErrorHandler, PerformanceMonitor
from config.manager import ConfigManager


class CrawlerCLI:
    """爬虫命令行接口"""
    
    def __init__(self):
        self.crawler: Optional[ImageCrawler] = None
        self.logger_manager: Optional[LoggerManager] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
    
    def initialize(self, config_file: Optional[str] = None, verbose: bool = False):
        """初始化爬虫系统"""
        try:
            # 初始化配置
            config_manager = ConfigManager(config_file)
            settings = config_manager.get_settings()
            
            # 如果是详细模式，调整日志级别
            if verbose:
                settings.logging.level = "DEBUG"
                settings.logging.verbose = True
            
            # 初始化日志系统
            self.logger_manager = LoggerManager(settings.logging.__dict__)
            self.logger = self.logger_manager.get_logger("CrawlerCLI")
            
            # 初始化错误处理器和性能监控
            self.error_handler = ErrorHandler(self.logger_manager)
            self.performance_monitor = PerformanceMonitor(self.logger_manager)
            
            # 初始化爬虫
            self.crawler = ImageCrawler(config_file)
            
            self.logger.info("爬虫系统初始化完成")
            return True
            
        except Exception as e:
            print(f"初始化失败: {e}")
            return False
    
    async def crawl_single_website(self, url: str, session_name: Optional[str] = None):
        """爬取单个网站"""
        if not self.crawler:
            raise RuntimeError("爬虫未初始化")
        
        self.logger.info(f"开始爬取网站: {url}")
        
        # 进度回调函数
        last_update_time = [0]  # 使用列表来避免闭包问题

        async def progress_callback(stats):
            current_time = time.time()
            # 每2秒更新一次进度，避免刷屏
            if current_time - last_update_time[0] >= 2:
                print(f"\r🔄 页面: {stats.get('pages_crawled', 0)} | "
                      f"发现: {stats.get('images_found', 0)} | "
                      f"下载: {stats.get('images_downloaded', 0)} | "
                      f"失败: {stats.get('images_failed', 0)}", end='', flush=True)
                last_update_time[0] = current_time
        
        try:
            # 开始性能监控
            op_id = self.performance_monitor.start_operation("crawl_website")
            
            # 执行爬取
            result = await self.crawler.crawl_website(
                url=url,
                session_name=session_name,
                progress_callback=progress_callback
            )
            
            # 结束性能监控
            self.performance_monitor.end_operation(
                op_id,
                pages_crawled=result.get('stats', {}).get('pages_crawled', 0),
                images_downloaded=result.get('stats', {}).get('images_downloaded', 0)
            )
            
            # 输出结果
            print()  # 换行，结束进度显示
            if result.get('success', False):
                self.logger.info(f"爬取完成: {result.get('summary', '')}")
                return result
            else:
                self.logger.error(f"爬取失败: {result.get('error', '未知错误')}")
                return result
                
        except Exception as e:
            error_info = self.error_handler.handle_error(
                e, 
                context={'url': url, 'session_name': session_name},
                operation='crawl_website'
            )
            raise e
    
    def display_statistics(self):
        """显示统计信息"""
        if not self.crawler:
            print("爬虫未初始化")
            return
        
        stats = self.crawler.get_statistics()
        error_stats = self.error_handler.get_error_statistics()
        perf_report = self.performance_monitor.get_performance_report()
        
        print("\n" + "="*50)
        print("爬虫统计信息")
        print("="*50)
        
        print(f"总图片数: {stats['total_images']}")
        print(f"已下载图片: {stats['downloaded_images']}")
        print(f"爬取会话数: {stats['total_sessions']}")
        print(f"活跃任务数: {stats['active_tasks']}")
        
        print("\n错误统计:")
        print(f"总错误数: {error_stats['total_errors']}")
        print(f"网络错误: {error_stats['network_errors']}")
        print(f"解析错误: {error_stats['parsing_errors']}")
        print(f"文件错误: {error_stats['file_errors']}")
        print(f"数据库错误: {error_stats['database_errors']}")
        
        print("\n性能信息:")
        print(f"活跃操作数: {perf_report['active_operations']}")
        if perf_report['current_resource_usage']:
            usage = perf_report['current_resource_usage']
            print(f"CPU使用率: {usage.get('cpu_percent', 0):.1f}%")
            print(f"内存使用: {usage.get('memory_mb', 0):.1f}MB")
        
        print("="*50)

    async def clean_data(self, clean_images: bool = False, clean_database: bool = False):
        """
        清空数据

        Args:
            clean_images: 是否清空图片文件
            clean_database: 是否清空数据库记录

        Returns:
            清理结果
        """
        try:
            result = {
                'success': True,
                'images_deleted': 0,
                'database_cleared': False,
                'records_deleted': 0
            }

            # 清空图片文件
            if clean_images:
                images_path = Path(self.crawler.settings.crawler.download_path)
                if images_path.exists():
                    import shutil
                    deleted_count = 0

                    # 计算要删除的文件数
                    for file_path in images_path.rglob('*'):
                        if file_path.is_file():
                            deleted_count += 1

                    # 删除整个目录
                    shutil.rmtree(images_path)

                    # 重新创建空目录
                    images_path.mkdir(parents=True, exist_ok=True)

                    result['images_deleted'] = deleted_count
                    self.logger.info(f"已删除 {deleted_count} 个图片文件")

            # 清空数据库记录
            if clean_database:
                records_deleted = await self._clear_database_records()
                result['database_cleared'] = True
                result['records_deleted'] = records_deleted
                self.logger.info(f"已清空 {records_deleted} 条数据库记录")

            return result

        except Exception as e:
            self.logger.error(f"清理数据失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _clear_database_records(self):
        """清空数据库记录"""
        try:
            from database.models.image import ImageModel
            from database.models.category import CategoryModel, TagModel
            from database.models.crawl_session import CrawlSessionModel

            # 使用数据库管理器的会话上下文
            with self.crawler.db_manager.get_session() as session:
                records_deleted = 0

                # 删除图片记录
                image_count = session.query(ImageModel).count()
                session.query(ImageModel).delete()
                records_deleted += image_count

                # 删除爬取会话记录
                session_count = session.query(CrawlSessionModel).count()
                session.query(CrawlSessionModel).delete()
                records_deleted += session_count

                # 删除标签记录
                tag_count = session.query(TagModel).count()
                session.query(TagModel).delete()
                records_deleted += tag_count

                # 重置分类记录（保留默认分类，但清空统计）
                categories = session.query(CategoryModel).all()
                for category in categories:
                    category.image_count = 0
                    category.total_size = 0

                session.commit()
                return records_deleted

        except Exception as e:
            self.logger.error(f"清空数据库记录失败: {e}")
            raise e


# CLI命令定义
@click.group()
@click.option('--config', '-c', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出模式')
@click.option('--quiet', '-q', is_flag=True, help='静默模式（最小化输出）')
@click.pass_context
def cli(ctx, config, verbose, quiet):
    """图片爬虫命令行工具"""
    ctx.ensure_object(dict)

    # 如果是静默模式，使用静默配置
    if quiet and not config:
        config = str(Path(__file__).parent / 'config' / 'quiet_config.yaml')

    # 初始化CLI
    crawler_cli = CrawlerCLI()
    if not crawler_cli.initialize(config, verbose):
        ctx.exit(1)

    ctx.obj['cli'] = crawler_cli


@cli.command()
@click.argument('url')
@click.option('--name', '-n', help='会话名称')
@click.pass_context
def crawl(ctx, url, name):
    """爬取指定网站的图片"""
    crawler_cli = ctx.obj['cli']
    
    try:
        # 运行异步爬取
        result = asyncio.run(crawler_cli.crawl_single_website(url, name))
        
        if result.get('success', False):
            click.echo(f"✅ 爬取成功: {result.get('summary', '')}")
            click.echo(f"📊 统计信息:")
            stats = result.get('stats', {})
            click.echo(f"   - 页面数: {stats.get('pages_crawled', 0)}")
            click.echo(f"   - 发现图片: {stats.get('images_found', 0)}")
            click.echo(f"   - 下载成功: {stats.get('images_downloaded', 0)}")
            click.echo(f"   - 下载失败: {stats.get('images_failed', 0)}")
            click.echo(f"   - 耗时: {stats.get('duration', 0):.2f}秒")
        else:
            click.echo(f"❌ 爬取失败: {result.get('error', '未知错误')}")
            ctx.exit(1)
            
    except KeyboardInterrupt:
        click.echo("\n⚠️  用户中断操作")
        crawler_cli.crawler.stop_all_tasks()
        ctx.exit(0)
    except Exception as e:
        click.echo(f"❌ 发生错误: {e}")
        ctx.exit(1)


@cli.command()
@click.argument('urls', nargs=-1, required=True)
@click.option('--name', '-n', help='批次名称前缀')
@click.pass_context
def batch(ctx, urls, name):
    """批量爬取多个网站"""
    crawler_cli = ctx.obj['cli']
    
    try:
        click.echo(f"开始批量爬取 {len(urls)} 个网站...")
        
        # 运行批量爬取
        results = asyncio.run(crawler_cli.crawler.crawl_multiple_websites(list(urls), name))
        
        # 统计结果
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        
        click.echo(f"\n📊 批量爬取完成:")
        click.echo(f"   - 成功: {successful}")
        click.echo(f"   - 失败: {failed}")
        click.echo(f"   - 总计: {len(results)}")
        
        # 显示详细结果
        for i, result in enumerate(results):
            status = "✅" if result.get('success', False) else "❌"
            url = urls[i] if i < len(urls) else "未知"
            summary = result.get('summary', result.get('error', '无信息'))
            click.echo(f"   {status} {url}: {summary}")
            
    except KeyboardInterrupt:
        click.echo("\n⚠️  用户中断操作")
        crawler_cli.crawler.stop_all_tasks()
        ctx.exit(0)
    except Exception as e:
        click.echo(f"❌ 发生错误: {e}")
        ctx.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """显示爬虫统计信息"""
    crawler_cli = ctx.obj['cli']
    crawler_cli.display_statistics()


@cli.command()
@click.pass_context
def stop(ctx):
    """停止所有活跃的爬取任务"""
    crawler_cli = ctx.obj['cli']
    crawler_cli.crawler.stop_all_tasks()
    click.echo("✅ 已发送停止信号给所有活跃任务")


@cli.command()
@click.option('--output', '-o', default='config/config.yaml', help='输出配置文件路径')
@click.pass_context
def init_config(ctx, output):
    """生成默认配置文件"""
    try:
        from shutil import copy2
        
        # 复制模板配置文件
        template_path = Path(__file__).parent / 'config' / 'templates' / 'config.yaml'
        output_path = Path(output)
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        copy2(template_path, output_path)
        click.echo(f"✅ 配置文件已生成: {output_path}")
        click.echo("请根据需要修改配置文件中的参数")
        
    except Exception as e:
        click.echo(f"❌ 生成配置文件失败: {e}")
        ctx.exit(1)


@cli.command()
@click.option('--images', is_flag=True, help='清空下载的图片文件')
@click.option('--database', is_flag=True, help='清空数据库记录')
@click.option('--all', is_flag=True, help='清空所有数据（图片+数据库）')
@click.option('--force', is_flag=True, help='强制清空，不询问确认')
@click.pass_context
def clean(ctx, images, database, all, force):
    """清空下载的图片和数据库记录"""
    crawler_cli = ctx.obj['cli']

    # 如果指定了--all，则清空所有
    if all:
        images = True
        database = True

    # 如果没有指定任何选项，默认询问
    if not images and not database:
        click.echo("请指定要清空的内容:")
        click.echo("  --images    清空下载的图片文件")
        click.echo("  --database  清空数据库记录")
        click.echo("  --all       清空所有数据")
        return

    # 确认操作
    if not force:
        operations = []
        if images:
            operations.append("下载的图片文件")
        if database:
            operations.append("数据库记录")

        click.echo(f"⚠️  即将清空: {', '.join(operations)}")
        if not click.confirm("确定要继续吗？此操作不可恢复"):
            click.echo("❌ 操作已取消")
            return

    try:
        result = asyncio.run(crawler_cli.clean_data(images, database))

        if result.get('success', False):
            click.echo("✅ 清理完成!")
            if result.get('images_deleted', 0) > 0:
                click.echo(f"   删除图片文件: {result['images_deleted']} 个")
            if result.get('database_cleared', False):
                click.echo(f"   清空数据库记录: {result['records_deleted']} 条")
        else:
            click.echo(f"❌ 清理失败: {result.get('error', '未知错误')}")
            ctx.exit(1)

    except Exception as e:
        click.echo(f"❌ 清理失败: {e}")
        ctx.exit(1)


@cli.command()
@click.pass_context
def test(ctx):
    """测试爬虫系统"""
    crawler_cli = ctx.obj['cli']

    click.echo("🔧 测试爬虫系统...")

    try:
        # 测试数据库连接
        if crawler_cli.crawler.db_manager.test_connection():
            click.echo("✅ 数据库连接正常")
        else:
            click.echo("❌ 数据库连接失败")
            return

        # 测试网络连接
        click.echo("🌐 测试网络连接...")
        test_result = asyncio.run(test_network_connection())
        if test_result:
            click.echo("✅ 网络连接正常")
        else:
            click.echo("❌ 网络连接失败")

        click.echo("✅ 系统测试完成")

    except Exception as e:
        click.echo(f"❌ 测试失败: {e}")


async def test_network_connection():
    """测试网络连接"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://httpbin.org/get', timeout=10) as response:
                return response.status == 200
    except Exception:
        return False


if __name__ == '__main__':
    cli()
