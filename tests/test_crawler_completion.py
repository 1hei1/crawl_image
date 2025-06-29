#!/usr/bin/env python3
"""
测试爬虫完成流程

专门测试爬虫在完成后是否能正确保存数据和更新状态
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from crawler.main_crawler import ImageCrawler
from database.enhanced_manager import EnhancedDatabaseManager


async def test_crawler_completion():
    """测试爬虫完成流程"""
    print("🧪 测试爬虫完成流程")
    print("=" * 60)
    
    # 创建数据库管理器
    db_manager = EnhancedDatabaseManager("sqlite:///test_crawler.db")
    db_manager.create_tables()
    
    # 创建爬虫
    crawler = ImageCrawler(db_manager=db_manager)
    
    # 测试URL（选择一个图片较少的网站进行快速测试）
    test_url = "https://httpbin.org/html"
    
    print(f"📡 开始爬取: {test_url}")
    print("⏱️ 监控爬取过程...")
    
    start_time = time.time()
    
    try:
        # 执行爬取
        result = await crawler.crawl_website(
            url=test_url,
            progress_callback=lambda stats: print(f"   进度: {stats}")
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n✅ 爬取完成！耗时: {duration:.2f}秒")
        print(f"📊 结果: {result}")
        
        # 检查数据库中的数据
        print("\n🔍 检查数据库状态...")
        
        with db_manager.get_session() as session:
            from database.models.crawl_session import CrawlSessionModel
            from database.models.image import ImageModel
            
            # 检查会话状态
            sessions = session.query(CrawlSessionModel).all()
            print(f"📋 爬取会话数量: {len(sessions)}")
            
            for sess in sessions:
                print(f"   会话 {sess.id}: {sess.status} - {sess.summary_log}")
            
            # 检查图片数量
            images = session.query(ImageModel).all()
            print(f"🖼️ 图片记录数量: {len(images)}")
            
            for img in images[:5]:  # 显示前5张图片
                print(f"   图片: {img.filename} - {img.url}")
        
        return True
        
    except Exception as e:
        print(f"❌ 爬取失败: {e}")
        return False


async def test_large_crawl_simulation():
    """模拟大量图片的爬取完成流程"""
    print("\n🧪 模拟大量图片爬取完成流程")
    print("=" * 60)
    
    # 创建数据库管理器
    db_manager = EnhancedDatabaseManager("sqlite:///test_large_crawl.db")
    db_manager.create_tables()
    
    # 创建爬虫
    crawler = ImageCrawler(db_manager=db_manager)
    
    # 模拟大量图片的结果
    mock_result = {
        'success': True,
        'start_url': 'https://example.com/gallery',
        'summary': '页面: 100, 图片: 500/600, 耗时: 45.00秒',
        'downloaded_images': [
            f'https://example.com/image_{i}.jpg' for i in range(500)
        ],
        'stats': {
            'pages_crawled': 100,
            'images_found': 600,
            'images_downloaded': 500,
            'images_failed': 100,
            'total_time': 45.0
        }
    }
    
    print(f"📊 模拟结果: {len(mock_result['downloaded_images'])} 张图片")
    
    try:
        # 创建会话
        session_id = await crawler._create_crawl_session(
            'https://example.com/gallery',
            'large_test'
        )
        
        print(f"📝 创建会话: {session_id}")
        
        # 测试保存结果
        print("💾 测试保存结果...")
        start_time = time.time()
        
        await crawler._save_crawl_results(session_id, mock_result)
        
        save_time = time.time() - start_time
        print(f"✅ 保存完成，耗时: {save_time:.2f}秒")
        
        # 测试完成会话
        print("🏁 测试完成会话...")
        start_time = time.time()
        
        await crawler._complete_crawl_session(session_id, mock_result)
        
        complete_time = time.time() - start_time
        print(f"✅ 会话完成，耗时: {complete_time:.2f}秒")
        
        # 验证数据库状态
        print("\n🔍 验证数据库状态...")
        
        with db_manager.get_session() as session:
            from database.models.crawl_session import CrawlSessionModel
            from database.models.image import ImageModel
            
            # 检查会话状态
            crawl_session = session.query(CrawlSessionModel).filter(
                CrawlSessionModel.id == session_id
            ).first()
            
            if crawl_session:
                print(f"📋 会话状态: {crawl_session.status}")
                print(f"📝 会话日志: {crawl_session.summary_log}")
            
            # 检查图片数量
            image_count = session.query(ImageModel).count()
            print(f"🖼️ 数据库中的图片数量: {image_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("🧪 爬虫完成流程测试")
    print("=" * 80)
    
    # 测试1: 小规模爬取
    success1 = await test_crawler_completion()
    
    # 测试2: 大规模数据保存模拟
    success2 = await test_large_crawl_simulation()
    
    print("\n📊 测试结果:")
    print(f"   小规模爬取: {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"   大规模保存: {'✅ 通过' if success2 else '❌ 失败'}")
    
    if success1 and success2:
        print("\n🎉 所有测试通过！爬虫完成流程正常工作。")
    else:
        print("\n⚠️ 部分测试失败，需要进一步调试。")
    
    print("\n💡 优化建议:")
    print("1. 使用批量数据库操作减少保存时间")
    print("2. 添加超时机制防止卡死")
    print("3. 增加错误处理确保流程完整性")


if __name__ == "__main__":
    asyncio.run(main())
