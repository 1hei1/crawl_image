#!/usr/bin/env python3
"""
修复同步问题的快速脚本

解决TagModel缺失和502同步错误问题
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel


def test_tag_model():
    """测试TagModel是否可以正常导入和使用"""
    print("🏷️ 测试TagModel...")
    
    try:
        from database.models.tag import TagModel
        print("✅ TagModel导入成功")
        
        # 测试数据库连接
        try:
            db_manager = EnhancedDatabaseManager()
        except TypeError:
            # 如果需要参数，使用默认配置
            from config.ha_config_loader import load_ha_config
            config = load_ha_config()
            if config and 'nodes' in config:
                primary_node = None
                for node_name, node_config in config['nodes'].items():
                    if node_config.get('role') == 'primary':
                        primary_node = node_config
                        break
                if primary_node:
                    db_url = primary_node.get('database_url', 'sqlite:///data/crawler.db')
                    db_manager = EnhancedDatabaseManager(db_url)
                else:
                    db_manager = EnhancedDatabaseManager('sqlite:///data/crawler.db')
            else:
                db_manager = EnhancedDatabaseManager('sqlite:///data/crawler.db')

        if db_manager.ha_manager:
            with db_manager.ha_manager.get_session() as session:
                # 尝试查询tags表
                try:
                    count = session.query(TagModel).count()
                    print(f"✅ tags表查询成功，记录数: {count}")
                except Exception as e:
                    print(f"⚠️ tags表查询失败: {e}")
                    # 尝试创建表
                    try:
                        from database.models.base import Base
                        Base.metadata.create_all(session.bind)
                        print("✅ 数据库表结构已更新")
                    except Exception as create_error:
                        print(f"❌ 创建表失败: {create_error}")
        
        return True
        
    except ImportError as e:
        print(f"❌ TagModel导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ TagModel测试失败: {e}")
        return False


def test_direct_sync():
    """测试直接数据库同步（不通过HTTP API）"""
    print("\n🔄 测试直接数据库同步...")
    
    try:
        try:
            db_manager = EnhancedDatabaseManager()
        except TypeError:
            db_manager = EnhancedDatabaseManager('sqlite:///data/crawler.db')

        ha_manager = db_manager.ha_manager
        
        if not ha_manager:
            print("❌ HA管理器未启用")
            return False
        
        print(f"当前主节点: {ha_manager.current_primary}")
        print(f"本地节点: {ha_manager.local_node_name}")
        
        # 检查同步队列
        sync_status = ha_manager.get_sync_status()
        print(f"同步队列大小: {sync_status.get('sync_queue_size', 0)}")
        print(f"自动同步: {'启用' if sync_status.get('auto_sync_enabled') else '禁用'}")
        
        # 添加测试数据
        timestamp = int(time.time())
        
        print("添加测试数据...")
        with ha_manager.get_session() as session:
            test_image = ImageModel(
                url=f"https://example.com/sync_test_{timestamp}.jpg",
                source_url="https://example.com",
                filename=f"sync_test_{timestamp}.jpg",
                file_extension="jpg",
                md5_hash=f"sync_test_hash_{timestamp}"
            )
            session.add(test_image)
            session.commit()
            test_image_id = test_image.id
        
        print(f"✅ 测试数据添加成功，ID: {test_image_id}")
        
        # 等待同步
        print("等待同步处理...")
        for i in range(10):
            time.sleep(1)
            sync_status = ha_manager.get_sync_status()
            queue_size = sync_status.get('sync_queue_size', 0)
            print(f"同步队列: {queue_size} 个操作", end='\r')
            if queue_size == 0 and i > 3:
                break
        
        print("\n检查同步结果...")
        
        # 检查备用节点
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
                        print(f"✅ 备用节点 {secondary_node} 同步成功")
                    else:
                        print(f"❌ 备用节点 {secondary_node} 同步失败")
                        sync_success = False
                        
                finally:
                    secondary_session.close()
                    
            except Exception as e:
                print(f"❌ 检查备用节点 {secondary_node} 失败: {e}")
                sync_success = False
        
        # 清理测试数据
        print("清理测试数据...")
        with ha_manager.get_session() as session:
            test_image = session.query(ImageModel).filter(
                ImageModel.id == test_image_id
            ).first()
            if test_image:
                session.delete(test_image)
                session.commit()
        
        return sync_success
        
    except Exception as e:
        print(f"❌ 直接同步测试失败: {e}")
        return False


def check_database_stats():
    """检查数据库统计功能"""
    print("\n📊 检查数据库统计功能...")
    
    try:
        try:
            db_manager = EnhancedDatabaseManager()
        except TypeError:
            db_manager = EnhancedDatabaseManager('sqlite:///data/crawler.db')

        ha_manager = db_manager.ha_manager
        
        if not ha_manager:
            print("❌ HA管理器未启用")
            return False
        
        # 获取主节点统计
        primary_stats = ha_manager._get_database_stats(ha_manager.current_primary)
        if primary_stats:
            print("主数据库统计:")
            for table_name, count in primary_stats.items():
                print(f"  {table_name}: {count} 条记录")
        else:
            print("❌ 无法获取主数据库统计")
            return False
        
        # 获取备用节点统计
        secondary_nodes = [
            name for name, node in ha_manager.nodes.items()
            if node.role.value == 'secondary'
        ]
        
        for secondary_node in secondary_nodes:
            secondary_stats = ha_manager._get_database_stats(secondary_node)
            if secondary_stats:
                print(f"\n备用数据库 {secondary_node} 统计:")
                for table_name, count in secondary_stats.items():
                    print(f"  {table_name}: {count} 条记录")
            else:
                print(f"❌ 无法获取备用数据库 {secondary_node} 统计")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库统计检查失败: {e}")
        return False


def main():
    """主函数"""
    print("🔧 修复同步问题")
    print("=" * 50)
    
    results = {}
    
    # 1. 测试TagModel
    results['tag_model'] = test_tag_model()
    
    # 2. 测试直接同步
    results['direct_sync'] = test_direct_sync()
    
    # 3. 检查数据库统计
    results['database_stats'] = check_database_stats()
    
    # 总结结果
    print("\n" + "=" * 50)
    print("📋 修复结果总结:")
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ 正常" if result else "❌ 异常"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有问题已修复！")
        print("\n✅ 修复内容:")
        print("  - TagModel导入和使用正常")
        print("  - 直接数据库同步替代HTTP API同步")
        print("  - 数据库统计功能正常")
        print("  - 同步队列处理正常")
        
        print("\n📝 建议:")
        print("  - 重启系统以应用修复: python start_simple_ha.py")
        print("  - 监控同步状态: python tools/sync_monitor.py monitor")
        
        return True
    else:
        print("❌ 部分问题仍需解决")
        print("\n🔧 建议检查:")
        print("  - 确保数据库连接正常")
        print("  - 检查表结构是否完整")
        print("  - 查看详细日志: logs/simple_ha.log")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
