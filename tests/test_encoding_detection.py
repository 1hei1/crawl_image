#!/usr/bin/env python3
"""
测试编码检测功能
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from crawler.core.async_crawler import AsyncCrawler

def test_encoding_detection():
    """测试编码检测功能"""
    
    print("🔤 测试编码检测功能")
    print("=" * 50)
    
    # 创建爬虫实例
    crawler = AsyncCrawler({})
    
    # 测试不同编码的内容
    test_cases = [
        {
            'name': 'UTF-8 with BOM',
            'content': b'\xef\xbb\xbf<html><head><meta charset="utf-8"></head><body>Hello World</body></html>',
            'expected': 'utf-8-sig'
        },
        {
            'name': 'UTF-8 without BOM',
            'content': '<html><head><meta charset="utf-8"></head><body>Hello 世界</body></html>'.encode('utf-8'),
            'expected': 'utf-8'
        },
        {
            'name': 'GBK encoding',
            'content': '<html><head><meta charset="gbk"></head><body>你好世界</body></html>'.encode('gbk'),
            'expected': 'gbk'
        },
        {
            'name': 'GB2312 encoding',
            'content': '<html><head><meta charset="gb2312"></head><body>中文测试</body></html>'.encode('gb2312'),
            'expected': 'gb2312'
        },
        {
            'name': 'HTML meta charset',
            'content': b'<html><head><meta http-equiv="Content-Type" content="text/html; charset=gbk"></head><body>\xc4\xe3\xba\xc3</body></html>',
            'expected': 'gbk'
        },
        {
            'name': 'XML encoding declaration',
            'content': b'<?xml version="1.0" encoding="gb2312"?><root>\xd6\xd0\xce\xc4</root>',
            'expected': 'gb2312'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📝 测试 {i}: {case['name']}")
        print(f"   内容长度: {len(case['content'])} 字节")
        
        # 检测编码
        detected = crawler._detect_encoding(case['content'])
        expected = case['expected']
        
        print(f"   期望编码: {expected}")
        print(f"   检测编码: {detected}")
        
        if detected == expected:
            print(f"   ✅ 检测正确")
        elif detected and detected.replace('-', '').replace('_', '') == expected.replace('-', '').replace('_', ''):
            print(f"   ✅ 检测正确 (编码名称变体)")
        else:
            print(f"   ❌ 检测错误")
        
        # 尝试解码验证
        if detected:
            try:
                decoded = case['content'].decode(detected)
                print(f"   ✅ 解码成功: {len(decoded)} 字符")
            except Exception as e:
                print(f"   ❌ 解码失败: {e}")
        else:
            print(f"   ❌ 未检测到编码")
    
    print("\n" + "=" * 50)
    print("🏁 编码检测测试完成")

async def test_real_gbk_website():
    """测试真实的GBK网站"""
    
    print("\n🌐 测试真实GBK网站")
    print("=" * 50)
    
    # 创建爬虫实例
    crawler = AsyncCrawler({
        'max_depth': 1,
        'max_images': 10,
        'max_concurrent': 5
    })
    
    # 测试GBK编码的中文网站
    test_urls = [
        'http://www.netbian.com/',  # 网站使用GBK编码
    ]
    
    for url in test_urls:
        print(f"\n🔍 测试网站: {url}")
        print("-" * 30)
        
        try:
            result = await crawler.start_crawling(url)
            
            if result.get('success', False):
                stats = result.get('stats', {})
                print(f"✅ 爬取成功:")
                print(f"   页面数: {stats.get('pages_crawled', 0)}")
                print(f"   发现图片: {stats.get('images_found', 0)}")
                print(f"   下载成功: {stats.get('images_downloaded', 0)}")
                print(f"   耗时: {stats.get('duration', 0):.2f}秒")
            else:
                print(f"❌ 爬取失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    print("\n🏁 真实网站测试完成")

if __name__ == "__main__":
    # 测试编码检测
    test_encoding_detection()
    
    # 测试真实网站
    asyncio.run(test_real_gbk_website())
