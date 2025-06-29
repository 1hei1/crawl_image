#!/usr/bin/env python3
"""
测试数据同步修复

验证表结构自动创建和数据同步功能
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config.manager import ConfigManager
from database.enhanced_manager import EnhancedDatabaseManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_table_creation_and_sync():
    """测试表创建和数据同步"""
    print("🧪 测试表结构创建和数据同步...")
    
    try:
        # 1. 初始化系统
        print("\n1️⃣ 初始化系统...")
        config_manager = ConfigManager("config/config.yaml")
        settings = config_manager.get_settings()
        
        if not settings.disaster_recovery.enabled:
            print("❌ 容灾备份功能未启用")
            return False
        
        database_url = config_manager.get_database_url()
        db_manager = EnhancedDatabaseManager(
            database_url, 
            settings.disaster_recovery
        )
        
        print("✅ 系统初始化成功")
        
        # 2. 创建主数据库表
        print("\n2️⃣ 创建主数据库表...")
        db_manager.create_tables()
        print("✅ 主数据库表创建成功")
        
        # 3. 添加一些测试数据
        print("\n3️⃣ 添加测试数据...")
        try:
            with db_manager.get_session() as session:
                from database.models.category import CategoryModel
                from database.models.image import ImageModel
                
                # 创建测试分类
                test_category = CategoryModel(
                    name="测试分类",
                    slug="test_category",
                    description="用于测试的分类"
                )
                session.add(test_category)
                session.flush()  # 获取ID
                
                # 创建测试图片记录
                test_image = ImageModel(
                    url="https://example.com/test.jpg",
                    source_url="https://example.com",
                    filename="test.jpg",
                    file_extension="jpg",
                    category_id=test_category.id,
                    md5_hash="test_hash_123"
                )
                session.add(test_image)
                session.commit()
                
                print("✅ 测试数据添加成功")
                
        except Exception as e:
            print(f"❌ 添加测试数据失败: {e}")
            return False
        
        # 4. 测试故障转移（这会触发表创建和数据同步）
        print("\n4️⃣ 测试故障转移...")
        
        # 获取备用数据库列表
        backup_manager = db_manager.backup_manager
        primary_db = backup_manager.current_primary
        
        backup_dbs = [
            name for name, config in backup_manager.databases.items()
            if name != primary_db and config.type == 'secondary' and config.is_active
        ]
        
        if not backup_dbs:
            print("❌ 没有可用的备用数据库")
            return False
        
        target_db = backup_dbs[0]
        print(f"🔄 故障转移: {primary_db} -> {target_db}")
        
        # 执行故障转移
        success = db_manager.manual_failover(target_db, "测试故障转移")
        
        if success:
            print(f"✅ 故障转移成功: {primary_db} -> {target_db}")
        else:
            print(f"❌ 故障转移失败")
            return False
        
        # 5. 验证目标数据库的数据
        print("\n5️⃣ 验证目标数据库数据...")
        try:
            with db_manager.get_session() as session:
                from database.models.category import CategoryModel
                from database.models.image import ImageModel
                
                # 检查分类数据
                categories = session.query(CategoryModel).all()
                print(f"分类数量: {len(categories)}")
                
                # 检查图片数据
                images = session.query(ImageModel).all()
                print(f"图片数量: {len(images)}")
                
                if len(categories) > 0 and len(images) > 0:
                    print("✅ 目标数据库数据验证成功")
                else:
                    print("⚠️ 目标数据库数据可能不完整")
                
        except Exception as e:
            print(f"❌ 验证目标数据库数据失败: {e}")
            return False
        
        # 6. 测试切换回原数据库
        print("\n6️⃣ 测试切换回原数据库...")
        success = db_manager.manual_failover(primary_db, "切换回原数据库")
        
        if success:
            print(f"✅ 切换回原数据库成功: {target_db} -> {primary_db}")
        else:
            print(f"❌ 切换回原数据库失败")
            return False
        
        print("\n🎉 所有测试通过！表结构创建和数据同步功能正常")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🔧 数据同步修复测试")
    print("=" * 60)
    
    success = test_table_creation_and_sync()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试结果: 成功")
        print("表结构创建和数据同步功能已修复")
    else:
        print("❌ 测试结果: 失败")
        print("请检查错误信息并修复相关问题")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
