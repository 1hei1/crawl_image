#!/usr/bin/env python3
"""
完整自动同步功能测试

测试所有表的自动同步功能，包括JSON字段处理
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel
from database.models.crawl_session import CrawlSessionModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_image_sync():
    """测试图片表同步"""
    print("📸 测试图片表同步...")
    
    try:
        db_manager = EnhancedDatabaseManager()
        ha_manager = db_manager.ha_manager
        
        if not ha_manager:
            print("❌ HA管理器未启用")
            return False
        
        timestamp = int(time.time())
        
        # 添加测试图片
        with ha_manager.get_session() as session:
            test_image = ImageModel(
                url=f"https://example.com/test_sync_{timestamp}.jpg",
                source_url="https://example.com",
                filename=f"test_sync_{timestamp}.jpg",
                file_extension="jpg",
                md5_hash=f"sync_hash_{timestamp}"
            )
            session.add(test_image)
            session.commit()
            test_image_id = test_image.id
        
        print(f"✅ 添加测试图片，ID: {test_image_id}")
        
        # 等待同步
        time.sleep(5)
        
        # 检查备用数据库
        secondary_nodes = [
            name for name, node in ha_manager.nodes.items()
            if node.role.value == 'secondary'
        ]
        
        sync_success = True
        for secondary_node in secondary_nodes:
            try:
                secondary_session = ha_manager.session_makers[secondary_node]()
                try:
                    synced_image = secondary_session.query(ImageModel).filter(
                        ImageModel.id == test_image_id
                    ).first()
                    
                    if synced_image:
                        print(f"✅ 备用节点 {secondary_node} 图片同步成功")
                    else:
                        print(f"❌ 备用节点 {secondary_node} 图片同步失败")
                        sync_success = False
                        
                finally:
                    secondary_session.close()
                    
            except Exception as e:
                print(f"❌ 检查备用节点 {secondary_node} 失败: {e}")
                sync_success = False
        
        # 清理测试数据
        with ha_manager.get_session() as session:
            test_image = session.query(ImageModel).filter(
                ImageModel.id == test_image_id
            ).first()
            if test_image:
                session.delete(test_image)
                session.commit()
        
        return sync_success
        
    except Exception as e:
        print(f"❌ 图片同步测试失败: {e}")
        return False


def test_crawl_session_sync():
    """测试爬取会话表同步（包含JSON字段）"""
    print("\n🕷️ 测试爬取会话表同步...")
    
    try:
        db_manager = EnhancedDatabaseManager()
        ha_manager = db_manager.ha_manager
        
        if not ha_manager:
            print("❌ HA管理器未启用")
            return False
        
        timestamp = int(time.time())
        
        # 添加测试爬取会话（包含JSON字段）
        with ha_manager.get_session() as session:
            test_session = CrawlSessionModel(
                url=f"https://example.com/test_{timestamp}",
                status="completed",
                total_images=10,
                downloaded_images=8,
                failed_images=2,
                config={
                    "max_depth": 2,
                    "max_images": 100,
                    "test_field": f"test_value_{timestamp}"
                },
                statistics={
                    "start_time": f"2025-06-26T{timestamp % 24:02d}:00:00",
                    "end_time": f"2025-06-26T{(timestamp % 24) + 1:02d}:00:00",
                    "duration": 3600
                },
                errors=[
                    {"error": "timeout", "count": 1},
                    {"error": "404", "count": 1}
                ]
            )
            session.add(test_session)
            session.commit()
            test_session_id = test_session.id
        
        print(f"✅ 添加测试爬取会话，ID: {test_session_id}")
        
        # 等待同步
        time.sleep(5)
        
        # 检查备用数据库
        secondary_nodes = [
            name for name, node in ha_manager.nodes.items()
            if node.role.value == 'secondary'
        ]
        
        sync_success = True
        for secondary_node in secondary_nodes:
            try:
                secondary_session = ha_manager.session_makers[secondary_node]()
                try:
                    synced_session = secondary_session.query(CrawlSessionModel).filter(
                        CrawlSessionModel.id == test_session_id
                    ).first()
                    
                    if synced_session:
                        print(f"✅ 备用节点 {secondary_node} 爬取会话同步成功")
                        
                        # 验证JSON字段
                        if (synced_session.config and 
                            synced_session.config.get('test_field') == f"test_value_{timestamp}"):
                            print(f"✅ JSON字段同步正确")
                        else:
                            print(f"❌ JSON字段同步错误")
                            sync_success = False
                    else:
                        print(f"❌ 备用节点 {secondary_node} 爬取会话同步失败")
                        sync_success = False
                        
                finally:
                    secondary_session.close()
                    
            except Exception as e:
                print(f"❌ 检查备用节点 {secondary_node} 失败: {e}")
                sync_success = False
        
        # 清理测试数据
        with ha_manager.get_session() as session:
            test_session = session.query(CrawlSessionModel).filter(
                CrawlSessionModel.id == test_session_id
            ).first()
            if test_session:
                session.delete(test_session)
                session.commit()
        
        return sync_success
        
    except Exception as e:
        print(f"❌ 爬取会话同步测试失败: {e}")
        return False


def test_sync_status():
    """测试同步状态查询"""
    print("\n📊 测试同步状态查询...")
    
    try:
        db_manager = EnhancedDatabaseManager()
        ha_manager = db_manager.ha_manager
        
        if not ha_manager:
            print("❌ HA管理器未启用")
            return False
        
        # 获取同步状态
        sync_status = ha_manager.get_sync_status()
        
        print(f"自动同步: {'启用' if sync_status.get('auto_sync_enabled') else '禁用'}")
        print(f"同步队列: {sync_status.get('sync_queue_size')} 个操作")
        print(f"当前主节点: {sync_status.get('current_primary')}")
        print(f"监控状态: {'运行中' if sync_status.get('is_monitoring') else '已停止'}")
        
        # 获取数据库统计
        primary_stats = ha_manager._get_database_stats(ha_manager.current_primary)
        if primary_stats:
            print("数据库统计:")
            for table_name, count in primary_stats.items():
                print(f"  {table_name}: {count} 条记录")
        
        return True
        
    except Exception as e:
        print(f"❌ 同步状态查询失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 完整自动同步功能测试")
    print("=" * 60)
    
    # 测试结果
    results = {}
    
    # 1. 测试图片同步
    results['image_sync'] = test_image_sync()
    
    # 2. 测试爬取会话同步（JSON字段）
    results['session_sync'] = test_crawl_session_sync()
    
    # 3. 测试同步状态
    results['status_query'] = test_sync_status()
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📋 测试结果总结:")
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！自动同步功能正常工作。")
        print("\n📝 功能确认:")
        print("  ✅ 图片表自动同步")
        print("  ✅ 爬取会话表自动同步")
        print("  ✅ JSON字段正确处理")
        print("  ✅ 同步状态查询")
        print("  ✅ 主备数据库一致性")
        
        print("\n🔗 管理地址:")
        print("  - 主应用: http://localhost:8000")
        print("  - HA管理: http://localhost:8001")
        print("  - 同步状态: http://localhost:8000/api/sync-status")
        
        return True
    else:
        print("❌ 部分测试失败，请检查系统配置。")
        print("\n🔧 建议检查:")
        print("  - 确保系统已启动: python start_simple_ha.py")
        print("  - 检查网络连接")
        print("  - 查看日志: logs/simple_ha.log")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
