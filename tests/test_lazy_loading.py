#!/usr/bin/env python3
"""
测试懒加载图片提取功能
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup
from crawler.utils.url_parser import URLParser
from crawler.core.async_crawler import AsyncCrawler

def test_lazy_loading_extraction():
    """测试懒加载图片提取"""
    
    # 模拟包含懒加载图片的HTML
    html_content = '''
    <html>
    <body>
        <!-- 标准图片 -->
        <img src="https://example.com/normal.jpg" alt="Normal Image" />
        
        <!-- 懒加载图片 - data-original -->
        <img src="/static/images/gray.gif" 
             data-original="https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg" 
             alt="秃头鹰6K高端电脑桌面壁纸" class="lazy" />
        
        <!-- 懒加载图片 - data-src -->
        <img src="placeholder.jpg" 
             data-src="https://example.com/lazy-image.png" 
             class="lazyload" />
        
        <!-- 懒加载图片 - data-lazy-src -->
        <img data-lazy-src="https://example.com/another-lazy.jpg" />
        
        <!-- 响应式图片 - srcset -->
        <img srcset="https://example.com/small.jpg 480w, https://example.com/large.jpg 800w" 
             src="https://example.com/fallback.jpg" />
        
        <!-- 背景图片 -->
        <div style="background-image: url('https://example.com/background.jpg');">Content</div>
        
        <!-- 其他元素的懒加载 -->
        <div data-original="https://example.com/div-image.jpg"></div>
        <a data-src="https://example.com/link-image.png">Link</a>
        
        <!-- 非图片链接（应该被过滤） -->
        <img src="https://example.com/script.js" />
        <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" />
    </body>
    </html>
    '''
    
    print("🧪 测试懒加载图片提取功能")
    print("=" * 50)
    
    # 创建解析器
    base_url = "https://example.com/"
    url_parser = URLParser(base_url)
    
    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 创建爬虫实例来使用其方法
    crawler = AsyncCrawler({})
    
    # 提取图片
    images = set()
    
    # 处理img标签
    for img in soup.find_all('img'):
        image_urls = crawler._extract_image_urls_from_element(img, url_parser)
        images.update(image_urls)
        
        # 显示提取结果
        src = img.get('src', '')
        data_original = img.get('data-original', '')
        data_src = img.get('data-src', '')
        data_lazy_src = img.get('data-lazy-src', '')
        srcset = img.get('srcset', '')
        
        print(f"📷 IMG标签:")
        if src:
            print(f"   src: {src}")
        if data_original:
            print(f"   data-original: {data_original}")
        if data_src:
            print(f"   data-src: {data_src}")
        if data_lazy_src:
            print(f"   data-lazy-src: {data_lazy_src}")
        if srcset:
            print(f"   srcset: {srcset}")
        
        if image_urls:
            print(f"   ✅ 提取到: {list(image_urls)}")
        else:
            print(f"   ❌ 未提取到图片")
        print()
    
    # 处理其他元素
    for element in soup.find_all(['div', 'span', 'a'], attrs={'data-original': True}):
        image_urls = crawler._extract_image_urls_from_element(element, url_parser)
        images.update(image_urls)
        
        print(f"📦 {element.name.upper()}标签:")
        print(f"   data-original: {element.get('data-original')}")
        if image_urls:
            print(f"   ✅ 提取到: {list(image_urls)}")
        else:
            print(f"   ❌ 未提取到图片")
        print()
    
    # 处理CSS背景图片
    for element in soup.find_all(attrs={'style': True}):
        style = element.get('style', '')
        if 'background-image' in style:
            bg_urls = crawler._extract_background_images(style, url_parser)
            images.update(bg_urls)
            
            print(f"🎨 CSS背景图片:")
            print(f"   style: {style}")
            if bg_urls:
                print(f"   ✅ 提取到: {list(bg_urls)}")
            else:
                print(f"   ❌ 未提取到图片")
            print()
    
    print("=" * 50)
    print(f"📊 总结:")
    print(f"   总共提取到 {len(images)} 个图片URL:")
    for i, url in enumerate(sorted(images), 1):
        print(f"   {i}. {url}")
    
    # 验证特定的懒加载图片是否被提取
    expected_urls = [
        "https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg",
        "https://example.com/lazy-image.png",
        "https://example.com/another-lazy.jpg",
        "https://example.com/background.jpg"
    ]
    
    print(f"\n🔍 验证关键懒加载图片:")
    for url in expected_urls:
        if url in images:
            print(f"   ✅ {url}")
        else:
            print(f"   ❌ {url}")

if __name__ == "__main__":
    test_lazy_loading_extraction()
