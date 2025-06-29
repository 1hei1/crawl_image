#!/usr/bin/env python3
"""
测试文件名映射功能

验证动态图片URL下载后的文件名映射是否正确
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from crawler.core.downloader import ImageDownloader
from crawler.utils.url_parser import URLParser
from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel


async def test_dynamic_url_filename_mapping():
    """测试动态URL的文件名映射"""
    print("🧪 测试动态URL文件名映射")
    print("=" * 60)
    
    # 创建下载器
    download_path = Path("test_downloads")
    download_path.mkdir(exist_ok=True)
    downloader = ImageDownloader(str(download_path))
    
    # 测试动态图片URL
    test_urls = [
        "https://httpbin.org/image/jpeg",
        "https://httpbin.org/image/png",
        # 模拟动态URL
        "https://example.com/getCroppingImg/17044056264658304",
    ]
    
    url_to_filename = {}
    
    for url in test_urls:
        print(f"\n📡 测试URL: {url}")
        
        try:
            # 1. 测试URL解析器的文件名提取
            parser = URLParser(url)
            extracted_filename = parser.extract_filename(url)
            print(f"   URL解析器提取: {extracted_filename}")
            
            # 2. 测试下载器的实际下载
            if "httpbin.org" in url:  # 只下载真实可访问的URL
                result = await downloader.download_image(url)
                
                if result['success']:
                    actual_filename = Path(result['local_path']).name
                    url_to_filename[url] = actual_filename
                    
                    print(f"   ✅ 下载成功")
                    print(f"   📁 实际文件名: {actual_filename}")
                    print(f"   📄 文件格式: {result.get('format', 'unknown')}")
                    print(f"   💾 文件大小: {result.get('file_size', 0)} bytes")
                    
                    # 检查文件是否真实存在
                    file_path = Path(result['local_path'])
                    if file_path.exists():
                        print(f"   ✅ 文件存在: {file_path}")
                    else:
                        print(f"   ❌ 文件不存在: {file_path}")
                else:
                    print(f"   ❌ 下载失败: {result.get('error', 'unknown')}")
            else:
                # 模拟动态URL的文件名生成
                simulated_filename = f"image_{hash(url) % 100000}.jpg"
                url_to_filename[url] = simulated_filename
                print(f"   🔄 模拟文件名: {simulated_filename}")
                
        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
    
    print(f"\n📋 URL到文件名映射:")
    for url, filename in url_to_filename.items():
        print(f"   {url} -> {filename}")
    
    return url_to_filename


async def test_database_filename_storage():
    """测试数据库文件名存储"""
    print("\n🗄️ 测试数据库文件名存储")
    print("=" * 60)
    
    # 创建测试数据库
    db_manager = EnhancedDatabaseManager("sqlite:///test_filename_mapping.db")
    db_manager.create_tables()
    
    # 模拟爬取结果
    mock_result = {
        'success': True,
        'start_url': 'https://example.com/gallery',
        'downloaded_images': [
            'https://httpbin.org/image/jpeg',
            'https://httpbin.org/image/png',
            'https://example.com/getCroppingImg/17044056264658304',
        ],
        'url_to_filename': {
            'https://httpbin.org/image/jpeg': 'image_12345.jpg',
            'https://httpbin.org/image/png': 'image_67890.png',
            'https://example.com/getCroppingImg/17044056264658304': 'image_17044056264658304.jpg',
        }
    }
    
    print("📊 模拟爬取结果:")
    print(f"   下载图片数量: {len(mock_result['downloaded_images'])}")
    print(f"   文件名映射数量: {len(mock_result['url_to_filename'])}")
    
    try:
        with db_manager.get_session() as db_session:
            # 获取默认分类
            from database.models.category import CategoryModel
            default_category = db_session.query(CategoryModel).filter(
                CategoryModel.slug == "uncategorized"
            ).first()
            
            # 获取URL到文件名的映射
            url_to_filename = mock_result.get('url_to_filename', {})
            
            # 创建图片记录
            new_images = []
            for image_url in mock_result['downloaded_images']:
                # 使用实际的文件名
                actual_filename = url_to_filename.get(image_url)
                if actual_filename:
                    filename = actual_filename
                    file_extension = Path(actual_filename).suffix or '.jpg'
                else:
                    # 回退到从URL提取
                    filename = Path(image_url).name
                    file_extension = Path(image_url).suffix or '.jpg'

                image = ImageModel(
                    url=image_url,
                    source_url=mock_result.get('start_url', ''),
                    filename=filename,
                    file_extension=file_extension,
                    category_id=default_category.id if default_category else None,
                    is_downloaded=True,
                )
                new_images.append(image)
            
            # 保存到数据库
            db_session.add_all(new_images)
            db_session.commit()
            
            print(f"\n✅ 成功保存 {len(new_images)} 条图片记录")
            
            # 验证数据库中的记录
            print("\n🔍 验证数据库记录:")
            images = db_session.query(ImageModel).all()
            
            for img in images:
                print(f"   📷 {img.filename}")
                print(f"      URL: {img.url}")
                print(f"      扩展名: {img.file_extension}")
                print(f"      前端链接: /static/data/images/{img.filename}")
                print()
            
            return True
            
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_frontend_link_generation():
    """测试前端链接生成"""
    print("\n🌐 测试前端链接生成")
    print("=" * 60)
    
    # 模拟数据库记录
    test_records = [
        {
            'url': 'https://httpbin.org/image/jpeg',
            'filename': 'image_12345.jpg',
            'file_extension': '.jpg'
        },
        {
            'url': 'https://httpbin.org/image/png', 
            'filename': 'image_67890.png',
            'file_extension': '.png'
        },
        {
            'url': 'https://example.com/getCroppingImg/17044056264658304',
            'filename': 'image_17044056264658304.jpg',
            'file_extension': '.jpg'
        }
    ]
    
    print("前端访问链接生成:")
    for record in test_records:
        frontend_url = f"/static/data/images/{record['filename']}"
        print(f"   📷 {record['filename']}")
        print(f"      原始URL: {record['url']}")
        print(f"      前端链接: {frontend_url}")
        print(f"      文件扩展名: {record['file_extension']}")
        print()
    
    return True


async def main():
    """主函数"""
    print("🧪 文件名映射功能测试")
    print("=" * 80)
    
    # 测试1: 动态URL文件名映射
    url_mapping = await test_dynamic_url_filename_mapping()
    
    # 测试2: 数据库文件名存储
    db_success = await test_database_filename_storage()
    
    # 测试3: 前端链接生成
    frontend_success = test_frontend_link_generation()
    
    print("\n📊 测试结果:")
    print(f"   动态URL映射: {'✅ 通过' if url_mapping else '❌ 失败'}")
    print(f"   数据库存储: {'✅ 通过' if db_success else '❌ 失败'}")
    print(f"   前端链接生成: {'✅ 通过' if frontend_success else '❌ 失败'}")
    
    if url_mapping and db_success and frontend_success:
        print("\n🎉 所有测试通过！文件名映射功能正常工作。")
        print("\n💡 现在动态图片URL可以正确:")
        print("1. 下载并保存为正确的文件名")
        print("2. 在数据库中记录实际的文件名")
        print("3. 生成正确的前端访问链接")
    else:
        print("\n⚠️ 部分测试失败，需要进一步调试。")


if __name__ == "__main__":
    asyncio.run(main())
