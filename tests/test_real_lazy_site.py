#!/usr/bin/env python3
"""
测试真实网站的懒加载图片提取
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from crawler.main_crawler import MainCrawler

async def test_real_lazy_loading():
    """测试真实网站的懒加载功能"""
    
    print("🌐 测试真实网站懒加载图片提取")
    print("=" * 60)
    
    # 创建爬虫实例
    crawler = MainCrawler()
    
    # 测试网站列表（这些网站通常使用懒加载）
    test_sites = [
        {
            'url': 'https://httpbin.org/html',
            'name': 'httpbin_test',
            'description': 'HTTPBin测试页面'
        }
    ]
    
    for site in test_sites:
        print(f"\n🔍 测试网站: {site['description']}")
        print(f"   URL: {site['url']}")
        print("-" * 40)
        
        try:
            # 执行爬取
            result = await crawler.crawl_website(
                url=site['url'],
                session_name=site['name']
            )
            
            if result.get('success', False):
                stats = result.get('stats', {})
                print(f"✅ 爬取成功:")
                print(f"   页面数: {stats.get('pages_crawled', 0)}")
                print(f"   发现图片: {stats.get('images_found', 0)}")
                print(f"   下载成功: {stats.get('images_downloaded', 0)}")
                print(f"   下载失败: {stats.get('images_failed', 0)}")
                print(f"   耗时: {stats.get('duration', 0):.2f}秒")
                
                # 显示发现的图片URL
                images = result.get('images', [])
                if images:
                    print(f"\n📷 发现的图片URL:")
                    for i, img_url in enumerate(images[:10], 1):  # 只显示前10个
                        print(f"   {i}. {img_url}")
                    if len(images) > 10:
                        print(f"   ... 还有 {len(images) - 10} 个图片")
                else:
                    print("   📷 未发现图片")
                    
            else:
                print(f"❌ 爬取失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 测试完成")

if __name__ == "__main__":
    asyncio.run(test_real_lazy_loading())
