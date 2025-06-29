#!/usr/bin/env python3
"""
图片爬虫快速启动脚本

提供简单的交互式界面
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from crawler.main_crawler import ImageCrawler
from crawler.utils.logger import LoggerManager


def print_banner():
    """打印程序横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    智能图片爬虫系统                          ║
║                  Image Crawler v1.0.0                       ║
║                                                              ║
║  功能特性:                                                   ║
║  • 智能图片发现和下载                                       ║
║  • 反爬虫机制处理                                           ║
║  • 异步高并发处理                                           ║
║  • 图片智能分类                                             ║
║  • 完整的错误处理和日志                                     ║
║  • 数据库容灾备份                                           ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_menu():
    """打印主菜单"""
    menu = """
请选择操作:
1. 爬取单个网站
2. 批量爬取网站
3. 查看统计信息
4. 容灾备份管理
5. 清理数据
6. 生成配置文件
7. 测试系统
8. 退出

请输入选项 (1-8): """
    return input(menu).strip()


async def crawl_single_website(crawler: ImageCrawler):
    """爬取单个网站"""
    url = input("请输入要爬取的网站URL: ").strip()
    if not url:
        print("❌ URL不能为空")
        return
    
    session_name = input("请输入会话名称 (可选): ").strip() or None
    
    print(f"\n🚀 开始爬取: {url}")
    print("按 Ctrl+C 可以中断爬取\n")
    
    # 进度回调
    import time
    last_update_time = [0]

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
        result = await crawler.crawl_website(
            url=url,
            session_name=session_name,
            progress_callback=progress_callback
        )
        
        print("\n")  # 换行
        
        if result.get('success', False):
            print("✅ 爬取完成!")
            print(f"📊 {result.get('summary', '')}")
            
            stats = result.get('stats', {})
            print(f"\n详细统计:")
            print(f"  • 爬取页面: {stats.get('pages_crawled', 0)}")
            print(f"  • 发现图片: {stats.get('images_found', 0)}")
            print(f"  • 下载成功: {stats.get('images_downloaded', 0)}")
            print(f"  • 下载失败: {stats.get('images_failed', 0)}")
            print(f"  • 耗时: {stats.get('duration', 0):.2f}秒")
            print(f"  • 成功率: {stats.get('success_rate', 0):.1f}%")
        else:
            print(f"❌ 爬取失败: {result.get('error', '未知错误')}")
            
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        crawler.stop_all_tasks()
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")


async def batch_crawl_websites(crawler: ImageCrawler):
    """批量爬取网站"""
    print("请输入要爬取的网站URL (每行一个，输入空行结束):")
    
    urls = []
    while True:
        url = input().strip()
        if not url:
            break
        urls.append(url)
    
    if not urls:
        print("❌ 没有输入任何URL")
        return
    
    session_name = input("请输入批次名称前缀 (可选): ").strip() or None
    
    print(f"\n🚀 开始批量爬取 {len(urls)} 个网站")
    print("按 Ctrl+C 可以中断爬取\n")
    
    try:
        results = await crawler.crawl_multiple_websites(urls, session_name)
        
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
            
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        crawler.stop_all_tasks()
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")


def show_statistics(crawler: ImageCrawler):
    """显示统计信息"""
    try:
        stats = crawler.get_statistics()
        
        print("\n" + "="*60)
        print("📊 爬虫统计信息")
        print("="*60)
        
        print(f"📸 图片统计:")
        print(f"  • 总图片数: {stats['total_images']}")
        print(f"  • 已下载: {stats['downloaded_images']}")
        print(f"  • 下载率: {stats['downloaded_images']/max(stats['total_images'], 1)*100:.1f}%")
        
        print(f"\n🔄 会话统计:")
        print(f"  • 总会话数: {stats['total_sessions']}")
        print(f"  • 活跃任务: {stats['active_tasks']}")
        
        print(f"\n💾 数据库信息:")
        db_info = stats.get('database_info', {})
        if isinstance(db_info.get('tables'), dict):
            tables = db_info['tables']
            print(f"  • 图片记录: {tables.get('images', 0)}")
            print(f"  • 分类记录: {tables.get('categories', 0)}")
            print(f"  • 标签记录: {tables.get('tags', 0)}")
            print(f"  • 会话记录: {tables.get('crawl_sessions', 0)}")
        
        print("="*60)
        
    except Exception as e:
        print(f"❌ 获取统计信息失败: {e}")


async def clean_data(crawler: ImageCrawler):
    """清理数据"""
    print("\n🧹 数据清理")
    print("请选择要清理的内容:")
    print("1. 清空下载的图片文件")
    print("2. 清空数据库记录")
    print("3. 清空所有数据（图片+数据库）")
    print("4. 返回主菜单")

    choice = input("\n请选择 (1-4): ").strip()

    if choice == '4':
        return

    clean_images = choice in ['1', '3']
    clean_database = choice in ['2', '3']

    if not clean_images and not clean_database:
        print("❌ 无效选项")
        return

    # 确认操作
    operations = []
    if clean_images:
        operations.append("下载的图片文件")
    if clean_database:
        operations.append("数据库记录")

    print(f"\n⚠️  即将清空: {', '.join(operations)}")
    confirm = input("确定要继续吗？此操作不可恢复 (y/N): ").strip().lower()

    if confirm != 'y':
        print("❌ 操作已取消")
        return

    try:
        print("\n🔄 正在清理...")

        result = {
            'success': True,
            'images_deleted': 0,
            'database_cleared': False,
            'records_deleted': 0
        }

        # 清空图片文件
        if clean_images:
            images_path = Path(crawler.settings.crawler.download_path)
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
                print(f"✅ 已删除 {deleted_count} 个图片文件")

        # 清空数据库记录
        if clean_database:
            from database.models.image import ImageModel
            from database.models.category import CategoryModel, TagModel
            from database.models.crawl_session import CrawlSessionModel

            # 使用数据库管理器的会话上下文
            with crawler.db_manager.get_session() as session:
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
                result['database_cleared'] = True
                result['records_deleted'] = records_deleted
                print(f"✅ 已清空 {records_deleted} 条数据库记录")

        print("\n✅ 清理完成!")

    except Exception as e:
        print(f"\n❌ 清理失败: {e}")


def generate_config():
    """生成配置文件"""
    try:
        from shutil import copy2

        template_path = Path(__file__).parent / 'config' / 'templates' / 'config.yaml'
        output_path = Path('config.yaml')

        if output_path.exists():
            overwrite = input(f"配置文件 {output_path} 已存在，是否覆盖? (y/N): ").strip().lower()
            if overwrite != 'y':
                print("❌ 操作已取消")
                return

        copy2(template_path, output_path)
        print(f"✅ 配置文件已生成: {output_path}")
        print("请根据需要修改配置文件中的参数")

    except Exception as e:
        print(f"❌ 生成配置文件失败: {e}")


async def test_system(crawler: ImageCrawler):
    """测试系统"""
    print("🔧 正在测试系统...")
    
    try:
        # 测试数据库连接
        print("📊 测试数据库连接...", end='')
        if crawler.db_manager.test_connection():
            print(" ✅")
        else:
            print(" ❌")
            return
        
        # 测试网络连接
        print("🌐 测试网络连接...", end='')
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://httpbin.org/get', timeout=10) as response:
                    if response.status == 200:
                        print(" ✅")
                    else:
                        print(f" ❌ (HTTP {response.status})")
        except Exception as e:
            print(f" ❌ ({e})")
        
        print("✅ 系统测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")


async def disaster_recovery_management(crawler):
    """容灾备份管理"""
    while True:
        print("\n" + "="*60)
        print("🛡️ 容灾备份管理")
        print("="*60)

        # 显示当前状态
        dr_status = crawler.get_disaster_recovery_status()

        if not dr_status.get('enabled', False):
            print("❌ 容灾备份功能未启用")
            print("\n请在配置文件中启用容灾备份功能:")
            print("disaster_recovery:")
            print("  enabled: true")
            input("\n按回车键返回主菜单...")
            return

        print("📊 当前状态:")

        # 数据库状态
        db_status = dr_status.get('database_status', {})
        if 'disaster_recovery' in db_status:
            dr_info = db_status['disaster_recovery']
            print(f"  当前主数据库: {dr_info.get('current_primary', 'N/A')}")
            print(f"  自动备份: {'✅ 启用' if dr_info.get('backup_enabled') else '❌ 禁用'}")
            print(f"  健康监控: {'✅ 启用' if dr_info.get('monitoring_enabled') else '❌ 禁用'}")
            print(f"  自动故障转移: {'✅ 启用' if dr_info.get('failover_enabled') else '❌ 禁用'}")

        # 健康状态
        health_status = dr_status.get('health_status', {})
        if isinstance(health_status, dict) and health_status:
            print("\n🔍 健康状态:")
            for db_name, status in health_status.items():
                if isinstance(status, dict):
                    status_icon = "🟢" if status.get('status') == 'healthy' else "🔴"
                    print(f"  {status_icon} {db_name}: {status.get('status', 'unknown')}")
                    if 'response_time' in status:
                        print(f"    响应时间: {status['response_time']:.2f}ms")

        # 故障转移状态
        failover_status = dr_status.get('failover_status', {})
        if failover_status.get('enabled', False):
            print(f"\n⚡ 故障转移状态: {failover_status.get('current_status', 'unknown')}")

            failure_counts = failover_status.get('failure_counts', {})
            if failure_counts:
                print("  失败计数:")
                for db_name, count in failure_counts.items():
                    print(f"    {db_name}: {count}")

        # 最近的故障转移历史
        history = dr_status.get('failover_history', [])
        if history:
            print(f"\n📋 最近故障转移记录 (最近{len(history)}条):")
            for i, event in enumerate(history[:3], 1):
                print(f"  {i}. {event['timestamp'][:19]}")
                print(f"     {event['source_db']} -> {event['target_db']}")
                print(f"     状态: {event['status']}")

        # 操作菜单
        print("\n" + "-"*40)
        print("操作选项:")
        print("1. 创建手动备份")
        print("2. 查看详细状态")
        print("3. 手动故障转移")
        print("4. 启用/禁用自动故障转移")
        print("5. 查看故障转移历史")
        print("6. 返回主菜单")

        choice = input("\n请选择操作 (1-6): ").strip()

        if choice == '1':
            await create_manual_backup(crawler)
        elif choice == '2':
            show_detailed_dr_status(crawler)
        elif choice == '3':
            await manual_failover(crawler)
        elif choice == '4':
            toggle_auto_failover(crawler)
        elif choice == '5':
            show_failover_history(crawler)
        elif choice == '6':
            break
        else:
            print("❌ 无效选项，请重新选择")

        input("\n按回车键继续...")


async def create_manual_backup(crawler):
    """创建手动备份"""
    print("\n🔄 创建手动备份...")

    backup_name = input("请输入备份名称 (留空使用默认名称): ").strip()
    if not backup_name:
        backup_name = None

    try:
        backup_path = crawler.db_manager.create_backup(backup_name)
        if backup_path:
            print(f"✅ 备份创建成功: {backup_path}")
        else:
            print("❌ 备份创建失败")
    except Exception as e:
        print(f"❌ 备份创建失败: {e}")


def show_detailed_dr_status(crawler):
    """显示详细的容灾状态"""
    print("\n📊 详细容灾状态:")

    try:
        # 使用命令行工具显示详细状态
        import subprocess
        result = subprocess.run(
            ["python", "disaster_recovery.py", "status"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',  # 忽略编码错误
            cwd=Path(__file__).parent
        )

        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"❌ 获取状态失败: {result.stderr}")

    except Exception as e:
        print(f"❌ 获取详细状态失败: {e}")

        # 如果subprocess失败，直接显示状态信息
        try:
            dr_status = crawler.get_disaster_recovery_status()
            if dr_status.get('enabled', False):
                print("\n=== 容灾备份系统状态 ===")

                # 数据库状态
                db_status = dr_status.get('database_status', {})
                if 'disaster_recovery' in db_status:
                    dr_info = db_status['disaster_recovery']
                    print(f"当前主数据库: {dr_info.get('current_primary', 'N/A')}")
                    print(f"自动备份: {'启用' if dr_info.get('backup_enabled') else '禁用'}")
                    print(f"健康监控: {'启用' if dr_info.get('monitoring_enabled') else '禁用'}")
                    print(f"自动故障转移: {'启用' if dr_info.get('failover_enabled') else '禁用'}")

                # 显示所有数据库实例
                print("\n--- 数据库实例 ---")
                for db_name, info in db_status.items():
                    if db_name != 'disaster_recovery' and isinstance(info, dict):
                        status_icon = "🟢" if info.get('is_connected') else "🔴"
                        primary_icon = "👑" if info.get('is_primary') else ""
                        print(f"  {status_icon} {db_name} {primary_icon}")
                        print(f"    类型: {info.get('type', 'N/A')}")
                        print(f"    优先级: {info.get('priority', 'N/A')}")
                        print(f"    连接状态: {'正常' if info.get('is_connected') else '异常'}")
                        if info.get('last_error'):
                            print(f"    最后错误: {info['last_error']}")
            else:
                print("❌ 容灾备份功能未启用")
        except Exception as fallback_error:
            print(f"❌ 显示状态信息失败: {fallback_error}")


async def manual_failover(crawler):
    """手动故障转移"""
    print("\n⚡ 手动故障转移")

    # 获取可用的数据库列表
    dr_status = crawler.get_disaster_recovery_status()
    db_status = dr_status.get('database_status', {})

    available_dbs = []
    current_primary = None

    for db_name, info in db_status.items():
        if db_name != 'disaster_recovery' and isinstance(info, dict):
            if info.get('is_primary'):
                current_primary = db_name
            elif info.get('is_connected'):
                available_dbs.append(db_name)

    if not available_dbs:
        print("❌ 没有可用的备用数据库")
        return

    print(f"当前主数据库: {current_primary}")
    print("可用的备用数据库:")
    for i, db_name in enumerate(available_dbs, 1):
        print(f"  {i}. {db_name}")

    try:
        choice = int(input(f"\n请选择目标数据库 (1-{len(available_dbs)}): ").strip())
        if 1 <= choice <= len(available_dbs):
            target_db = available_dbs[choice - 1]
            reason = input("请输入故障转移原因 (可选): ").strip() or "手动故障转移"

            # 确认操作
            confirm = input(f"⚠️ 确认要切换到 '{target_db}'？(y/N): ").strip().lower()
            if confirm == 'y':
                print(f"🔄 正在切换到 {target_db}...")
                success = crawler.db_manager.manual_failover(target_db, reason)
                if success:
                    print(f"✅ 故障转移成功: {current_primary} -> {target_db}")
                else:
                    print(f"❌ 故障转移失败")
            else:
                print("操作已取消")
        else:
            print("❌ 无效选择")
    except ValueError:
        print("❌ 请输入有效的数字")
    except Exception as e:
        print(f"❌ 故障转移失败: {e}")


def toggle_auto_failover(crawler):
    """切换自动故障转移状态"""
    print("\n⚙️ 自动故障转移设置")

    dr_status = crawler.get_disaster_recovery_status()
    failover_status = dr_status.get('failover_status', {})

    if not failover_status.get('enabled', False):
        print("❌ 故障转移功能未启用")
        return

    current_status = failover_status.get('auto_failover_enabled', False)
    print(f"当前状态: {'✅ 启用' if current_status else '❌ 禁用'}")

    action = "禁用" if current_status else "启用"
    confirm = input(f"是否要{action}自动故障转移？(y/N): ").strip().lower()

    if confirm == 'y':
        try:
            if current_status:
                crawler.db_manager.disable_auto_failover()
                print("✅ 自动故障转移已禁用")
            else:
                crawler.db_manager.enable_auto_failover()
                print("✅ 自动故障转移已启用")
        except Exception as e:
            print(f"❌ 操作失败: {e}")
    else:
        print("操作已取消")


def show_failover_history(crawler):
    """显示故障转移历史"""
    print("\n📋 故障转移历史")

    try:
        history = crawler.db_manager.get_failover_history(20)

        if not history:
            print("暂无故障转移记录")
            return

        print(f"共 {len(history)} 条记录:\n")

        for i, event in enumerate(history, 1):
            print(f"{i}. {event['timestamp']}")
            print(f"   {event['source_db']} -> {event['target_db']}")
            print(f"   原因: {event['reason']}")
            print(f"   状态: {event['status']}")
            if event.get('duration'):
                print(f"   耗时: {event['duration']:.2f}秒")
            if event.get('error_message'):
                print(f"   错误: {event['error_message']}")
            print()

    except Exception as e:
        print(f"❌ 获取历史记录失败: {e}")


async def main():
    """主函数"""
    print_banner()
    
    # 初始化爬虫
    print("🔧 正在初始化系统...")
    try:
        crawler = ImageCrawler()
        print("✅ 系统初始化完成\n")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return
    
    # 主循环
    while True:
        try:
            choice = print_menu()
            
            if choice == '1':
                await crawl_single_website(crawler)
            elif choice == '2':
                await batch_crawl_websites(crawler)
            elif choice == '3':
                show_statistics(crawler)
            elif choice == '4':
                await disaster_recovery_management(crawler)
            elif choice == '5':
                await clean_data(crawler)
            elif choice == '6':
                generate_config()
            elif choice == '7':
                await test_system(crawler)
            elif choice == '8':
                print("👋 再见!")
                # 停止容灾备份监控
                try:
                    crawler.stop_disaster_recovery()
                except:
                    pass
                break
            else:
                print("❌ 无效选项，请重新选择")
            
            input("\n按回车键继续...")
            
        except KeyboardInterrupt:
            print("\n👋 再见!")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            input("\n按回车键继续...")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见!")
    except Exception as e:
        print(f"❌ 程序异常退出: {e}")
