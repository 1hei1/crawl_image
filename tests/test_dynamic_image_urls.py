#!/usr/bin/env python3
"""
测试动态图片URL识别功能

测试各种类型的图片URL，包括：
1. 传统的带扩展名的图片URL
2. 动态生成的图片URL（无扩展名）
3. API风格的图片URL
4. CDN图片URL
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from crawler.utils.url_parser import URLParser
from crawler.core.downloader import ImageDownloader


def test_url_recognition():
    """测试URL识别功能"""
    print("🔍 测试图片URL识别功能")
    print("=" * 60)
    
    # 创建URL解析器
    parser = URLParser("https://example.com")
    
    # 测试URL列表
    test_urls = [
        # 传统图片URL
        ("https://example.com/image.jpg", "传统JPG图片"),
        ("https://example.com/photo.png", "传统PNG图片"),
        ("https://example.com/picture.gif", "传统GIF图片"),
        
        # 动态图片URL（您提到的例子）
        ("https://haowallpaper.com/link/common/file/getCroppingImg/17044056264658304", "动态裁剪图片"),
        ("https://haowallpaper.com/link/common/file/getCroppingImg/17112428137401728", "动态裁剪图片2"),
        
        # 其他动态图片URL模式
        ("https://api.example.com/v1/image/12345", "API风格图片"),
        ("https://cdn.example.com/getImage/67890", "CDN图片"),
        ("https://example.com/thumbnail/98765", "缩略图"),
        ("https://example.com/resize/400x300/image123", "调整尺寸图片"),
        ("https://example.com/avatar/user_456789", "用户头像"),
        ("https://example.com/wallpaper/nature_12345", "壁纸"),
        
        # CDN和云存储
        ("https://d1234567890.cloudfront.net/images/photo123", "CloudFront CDN"),
        ("https://bucket.s3.amazonaws.com/images/pic.jpg", "AWS S3"),
        
        # 非图片URL（应该被排除）
        ("https://example.com/page.html", "HTML页面"),
        ("https://example.com/script.js", "JavaScript文件"),
        ("https://example.com/ads/banner.jpg", "广告图片（应排除）"),
        ("https://example.com/thumb_small.jpg", "缩略图（应排除）"),
    ]
    
    print("基础模式匹配测试:")
    print("-" * 40)
    
    for url, description in test_urls:
        is_image_basic = parser.is_image_url(url, check_content_type=False)
        print(f"{'✅' if is_image_basic else '❌'} {description}")
        print(f"   URL: {url}")
        print(f"   基础识别: {is_image_basic}")
        print()


async def test_content_type_detection():
    """测试内容类型检测功能"""
    print("\n🌐 测试内容类型检测功能")
    print("=" * 60)
    
    # 创建URL解析器
    parser = URLParser("https://example.com")
    
    # 真实的图片URL（用于测试内容类型检测）
    real_image_urls = [
        ("https://httpbin.org/image/jpeg", "HTTPBin JPEG图片"),
        ("https://httpbin.org/image/png", "HTTPBin PNG图片"),
        ("https://httpbin.org/image/webp", "HTTPBin WebP图片"),
        # 您提到的真实URL
        ("https://haowallpaper.com/link/common/file/getCroppingImg/17044056264658304", "哲风壁纸动态图片"),
    ]
    
    print("内容类型检测测试:")
    print("-" * 40)
    
    for url, description in real_image_urls:
        try:
            is_image_basic = parser.is_image_url(url, check_content_type=False)
            is_image_with_check = parser.is_image_url(url, check_content_type=True)
            
            print(f"📷 {description}")
            print(f"   URL: {url}")
            print(f"   基础识别: {'✅' if is_image_basic else '❌'}")
            print(f"   内容检测: {'✅' if is_image_with_check else '❌'}")
            print()
            
        except Exception as e:
            print(f"❌ {description}: 检测失败 - {e}")
            print()


async def test_download_dynamic_images():
    """测试下载动态图片"""
    print("\n⬇️ 测试下载动态图片")
    print("=" * 60)
    
    # 创建下载器
    downloader = ImageDownloader("test_downloads")
    
    # 测试下载的URL
    download_urls = [
        "https://httpbin.org/image/jpeg",
        "https://httpbin.org/image/png",
        # 如果您有可访问的动态图片URL，可以添加到这里
        # "https://haowallpaper.com/link/common/file/getCroppingImg/17044056264658304",
    ]
    
    for url in download_urls:
        try:
            print(f"📥 下载: {url}")
            result = await downloader.download_image(url)
            
            if result['success']:
                print(f"   ✅ 下载成功")
                print(f"   📁 文件: {result['local_path']}")
                print(f"   📏 尺寸: {result['width']}x{result['height']}")
                print(f"   📄 格式: {result['format']}")
                print(f"   💾 大小: {result['file_size']} bytes")
            else:
                print(f"   ❌ 下载失败: {result['error']}")
            
            print()
            
        except Exception as e:
            print(f"   ❌ 下载异常: {e}")
            print()
    
    # downloader.close()  # ImageDownloader没有close方法


def test_url_patterns():
    """测试URL模式匹配"""
    print("\n🔍 测试URL模式匹配")
    print("=" * 60)
    
    parser = URLParser("https://example.com")
    
    # 测试各种动态图片URL模式
    dynamic_patterns = [
        "https://site.com/getCroppingImg/123456",
        "https://site.com/getImage/789012",
        "https://site.com/api/v1/image/345678",
        "https://site.com/thumbnail/901234",
        "https://site.com/resize/567890",
        "https://site.com/crop/123789",
        "https://site.com/photo/456012",
        "https://site.com/picture/789345",
        "https://site.com/wallpaper/012678",
        "https://site.com/avatar/345901",
        "https://site.com/cover/678234",
        "https://site.com/banner/901567",
        "https://cdn.cloudfront.net/images/890123",
        "https://bucket.amazonaws.com/photos/234567.jpg",
    ]
    
    print("动态URL模式匹配:")
    print("-" * 30)
    
    for url in dynamic_patterns:
        is_match = parser.is_image_url(url, check_content_type=False)
        print(f"{'✅' if is_match else '❌'} {url}")
    
    print()


async def main():
    """主函数"""
    print("🖼️ 动态图片URL识别测试")
    print("=" * 80)
    
    # 1. 测试URL识别
    test_url_recognition()
    
    # 2. 测试URL模式
    test_url_patterns()
    
    # 3. 测试内容类型检测
    await test_content_type_detection()
    
    # 4. 测试下载功能
    await test_download_dynamic_images()
    
    print("\n✅ 测试完成！")
    print("\n💡 使用建议:")
    print("1. 对于已知的动态图片URL模式，已添加到URL_PATTERNS中")
    print("2. 对于未知模式，启用check_content_type=True进行内容检测")
    print("3. 下载器会自动根据Content-Type确定正确的文件扩展名")


if __name__ == "__main__":
    asyncio.run(main())
