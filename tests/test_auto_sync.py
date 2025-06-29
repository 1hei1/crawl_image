#!/usr/bin/env python3
"""
测试自动数据同步功能

验证主数据库到备份数据库的自动同步机制
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel
from database.models.category import CategoryModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_auto_sync():
    """测试自动数据同步功能"""
    print("🔄 开始测试自动数据同步功能")
    print("=" * 60)
    
    try:
        # 1. 初始化数据库管理器
        print("1️⃣ 初始化数据库管理器...")
        db_manager = EnhancedDatabaseManager()
        
        if not db_manager.ha_manager:
            print("❌ HA管理器未启用，无法测试自动同步")
            return False
        
        ha_manager = db_manager.ha_manager
        print(f"✅ HA管理器已启用，当前主节点: {ha_manager.current_primary}")
        
        # 2. 检查同步状态
        print("\n2️⃣ 检查同步状态...")
        sync_status = ha_manager.get_sync_status()
        print(f"自动同步状态: {'启用' if sync_status['auto_sync_enabled'] else '禁用'}")
        print(f"同步队列大小: {sync_status['sync_queue_size']}")
        print(f"当前主节点: {sync_status['current_primary']}")
        
        # 3. 添加测试数据到主数据库
        print("\n3️⃣ 添加测试数据到主数据库...")
        timestamp = int(time.time())
        
        with ha_manager.get_session() as session:
            # 创建测试分类
            test_category = CategoryModel(
                name=f"自动同步测试_{timestamp}",
                description="用于测试自动同步功能的分类"
            )
            session.add(test_category)
            session.flush()  # 获取ID
            
            # 创建测试图片记录
            test_image = ImageModel(
                url=f"https://example.com/auto_sync_test_{timestamp}.jpg",
                source_url="https://example.com",
                filename=f"auto_sync_test_{timestamp}.jpg",
                file_extension="jpg",
                category_id=test_category.id,
                md5_hash=f"auto_sync_hash_{timestamp}"
            )
            session.add(test_image)
            session.commit()
            
            test_image_id = test_image.id
            print(f"✅ 测试数据添加成功，图片ID: {test_image_id}")
        
        # 4. 等待自动同步
        print("\n4️⃣ 等待自动同步...")
        print("等待10秒让同步机制处理数据...")
        
        for i in range(10):
            time.sleep(1)
            sync_status = ha_manager.get_sync_status()
            print(f"同步队列大小: {sync_status['sync_queue_size']}", end='\r')
        
        print("\n")
        
        # 5. 检查备用数据库中的数据
        print("5️⃣ 检查备用数据库中的数据...")
        
        # 获取所有备用节点
        secondary_nodes = [
            name for name, node in ha_manager.nodes.items()
            if node.role.value == 'secondary' and name != ha_manager.current_primary
        ]
        
        if not secondary_nodes:
            print("❌ 没有备用节点可供测试")
            return False
        
        sync_success = True
        for secondary_node in secondary_nodes:
            try:
                # 直接连接到备用数据库检查数据
                secondary_session = ha_manager.session_makers[secondary_node]()
                try:
                    # 查找测试图片
                    synced_image = secondary_session.query(ImageModel).filter(
                        ImageModel.id == test_image_id
                    ).first()
                    
                    if synced_image:
                        print(f"✅ 备用节点 {secondary_node} 数据同步成功")
                        print(f"   图片URL: {synced_image.url}")
                        print(f"   文件名: {synced_image.filename}")
                    else:
                        print(f"❌ 备用节点 {secondary_node} 数据同步失败 - 未找到测试图片")
                        sync_success = False
                        
                finally:
                    secondary_session.close()
                    
            except Exception as e:
                print(f"❌ 检查备用节点 {secondary_node} 失败: {e}")
                sync_success = False
        
        # 6. 测试强制全量同步
        print("\n6️⃣ 测试强制全量同步...")
        force_sync_result = ha_manager.force_sync_all()
        if force_sync_result:
            print("✅ 强制全量同步启动成功")
        else:
            print("❌ 强制全量同步启动失败")
        
        # 7. 显示最终同步状态
        print("\n7️⃣ 最终同步状态...")
        final_sync_status = ha_manager.get_sync_status()
        print(f"同步队列大小: {final_sync_status['sync_queue_size']}")
        print(f"最后全量同步时间: {time.ctime(final_sync_status['last_full_sync'])}")
        
        # 8. 清理测试数据
        print("\n8️⃣ 清理测试数据...")
        try:
            with ha_manager.get_session() as session:
                # 删除测试图片
                test_image = session.query(ImageModel).filter(
                    ImageModel.id == test_image_id
                ).first()
                if test_image:
                    session.delete(test_image)
                
                # 删除测试分类
                test_category = session.query(CategoryModel).filter(
                    CategoryModel.name == f"自动同步测试_{timestamp}"
                ).first()
                if test_category:
                    session.delete(test_category)
                
                session.commit()
                print("✅ 测试数据清理完成")
        except Exception as e:
            print(f"⚠️ 清理测试数据失败: {e}")
        
        print("\n" + "=" * 60)
        if sync_success:
            print("🎉 自动数据同步测试通过！")
        else:
            print("❌ 自动数据同步测试失败！")
        
        return sync_success
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        logger.error(f"自动同步测试失败: {e}")
        return False


def test_sync_performance():
    """测试同步性能"""
    print("\n🚀 开始测试同步性能...")
    
    try:
        db_manager = EnhancedDatabaseManager()
        ha_manager = db_manager.ha_manager
        
        if not ha_manager:
            print("❌ HA管理器未启用")
            return False
        
        # 批量添加测试数据
        batch_size = 50
        start_time = time.time()
        
        print(f"添加 {batch_size} 条测试记录...")
        
        with ha_manager.get_session() as session:
            for i in range(batch_size):
                test_image = ImageModel(
                    url=f"https://example.com/perf_test_{i}_{int(time.time())}.jpg",
                    source_url="https://example.com",
                    filename=f"perf_test_{i}_{int(time.time())}.jpg",
                    file_extension="jpg",
                    md5_hash=f"perf_hash_{i}_{int(time.time())}"
                )
                session.add(test_image)
            
            session.commit()
        
        add_time = time.time() - start_time
        print(f"✅ 数据添加完成，耗时: {add_time:.2f}秒")
        
        # 等待同步完成
        print("等待同步完成...")
        sync_start_time = time.time()
        
        while True:
            sync_status = ha_manager.get_sync_status()
            if sync_status['sync_queue_size'] == 0:
                break
            time.sleep(0.5)
            
            # 超时保护
            if time.time() - sync_start_time > 60:
                print("⚠️ 同步超时")
                break
        
        sync_time = time.time() - sync_start_time
        print(f"✅ 同步完成，耗时: {sync_time:.2f}秒")
        print(f"平均每条记录同步时间: {(sync_time/batch_size)*1000:.2f}毫秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False


if __name__ == "__main__":
    print("🧪 自动数据同步功能测试")
    print("=" * 60)
    
    # 基本功能测试
    basic_test_result = test_auto_sync()
    
    # 性能测试
    if basic_test_result:
        perf_test_result = test_sync_performance()
    else:
        perf_test_result = False
    
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    print(f"基本功能测试: {'✅ 通过' if basic_test_result else '❌ 失败'}")
    print(f"性能测试: {'✅ 通过' if perf_test_result else '❌ 失败'}")
    
    if basic_test_result and perf_test_result:
        print("\n🎉 所有测试通过！自动数据同步功能正常工作。")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败，请检查系统配置。")
        sys.exit(1)
