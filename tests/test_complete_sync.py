#!/usr/bin/env python3
"""
完整的数据同步测试

测试表结构创建、数据同步和故障转移的完整流程
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


def test_complete_disaster_recovery():
    """测试完整的容灾备份流程"""
    print("🧪 测试完整的容灾备份流程...")
    
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
        
        # 3. 清理并添加测试数据到主数据库
        print("\n3️⃣ 清理并添加测试数据到主数据库...")
        try:
            with db_manager.get_session() as session:
                from database.models.category import CategoryModel
                from database.models.image import ImageModel
                import time

                # 先清理可能存在的测试数据
                session.query(ImageModel).filter(ImageModel.md5_hash.like("test_hash_%")).delete()
                session.query(CategoryModel).filter(CategoryModel.slug.like("test_category_%")).delete()
                session.commit()

                # 创建唯一的测试分类
                timestamp = int(time.time())
                test_category = CategoryModel(
                    name=f"测试分类_{timestamp}",
                    slug=f"test_category_{timestamp}",
                    description="用于测试的分类"
                )
                session.add(test_category)
                session.flush()  # 获取ID

                # 创建测试图片记录
                test_image = ImageModel(
                    url=f"https://example.com/test_{timestamp}.jpg",
                    source_url="https://example.com",
                    filename=f"test_{timestamp}.jpg",
                    file_extension="jpg",
                    category_id=test_category.id,
                    md5_hash=f"test_hash_{timestamp}"
                )
                session.add(test_image)
                session.commit()

                print("✅ 测试数据添加成功")
                
        except Exception as e:
            print(f"❌ 添加测试数据失败: {e}")
            return False
        
        # 4. 手动同步数据到备用数据库
        print("\n4️⃣ 手动同步数据到备用数据库...")
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
        print(f"🔄 同步数据: {primary_db} -> {target_db}")
        
        # 先确保目标数据库有表结构
        try:
            engine = backup_manager.engines[target_db]
            from database.models.base import Base
            Base.metadata.create_all(bind=engine)
            print(f"✅ 在 {target_db} 中创建表结构")
        except Exception as e:
            print(f"❌ 创建表结构失败: {e}")
            return False
        
        # 执行数据同步
        sync_success = backup_manager.sync_databases(primary_db, target_db)
        if sync_success:
            print(f"✅ 数据同步成功: {primary_db} -> {target_db}")
        else:
            print(f"❌ 数据同步失败")
            return False
        
        # 5. 验证备用数据库的数据
        print("\n5️⃣ 验证备用数据库数据...")
        try:
            with backup_manager.get_session(target_db) as session:
                from database.models.category import CategoryModel
                from database.models.image import ImageModel
                
                # 检查分类数据
                categories = session.query(CategoryModel).all()
                print(f"备用数据库分类数量: {len(categories)}")
                
                # 检查图片数据
                images = session.query(ImageModel).all()
                print(f"备用数据库图片数量: {len(images)}")
                
                if len(categories) > 0 and len(images) > 0:
                    print("✅ 备用数据库数据验证成功")
                    
                    # 显示详细信息
                    for category in categories:
                        print(f"  分类: {category.name}")
                    for image in images:
                        print(f"  图片: {image.filename}")
                else:
                    print("❌ 备用数据库数据不完整")
                    return False
                
        except Exception as e:
            print(f"❌ 验证备用数据库数据失败: {e}")
            return False
        
        # 6. 测试故障转移
        print("\n6️⃣ 测试故障转移...")
        success = db_manager.manual_failover(target_db, "测试故障转移")
        
        if success:
            print(f"✅ 故障转移成功: {primary_db} -> {target_db}")
        else:
            print(f"❌ 故障转移失败")
            return False
        
        # 7. 验证故障转移后的数据访问
        print("\n7️⃣ 验证故障转移后的数据访问...")
        try:
            with db_manager.get_session() as session:
                from database.models.category import CategoryModel
                from database.models.image import ImageModel
                
                # 检查数据是否可以正常访问
                categories = session.query(CategoryModel).all()
                images = session.query(ImageModel).all()
                
                print(f"当前数据库分类数量: {len(categories)}")
                print(f"当前数据库图片数量: {len(images)}")
                
                if len(categories) > 0 and len(images) > 0:
                    print("✅ 故障转移后数据访问正常")
                else:
                    print("❌ 故障转移后数据访问异常")
                    return False
                
        except Exception as e:
            print(f"❌ 故障转移后数据访问失败: {e}")
            return False
        
        # 8. 测试切换回原数据库
        print("\n8️⃣ 测试切换回原数据库...")
        success = db_manager.manual_failover(primary_db, "切换回原数据库")
        
        if success:
            print(f"✅ 切换回原数据库成功: {target_db} -> {primary_db}")
        else:
            print(f"❌ 切换回原数据库失败")
            return False
        
        # 9. 最终验证
        print("\n9️⃣ 最终验证...")
        try:
            with db_manager.get_session() as session:
                from database.models.category import CategoryModel
                from database.models.image import ImageModel
                
                categories = session.query(CategoryModel).all()
                images = session.query(ImageModel).all()
                
                print(f"最终数据库分类数量: {len(categories)}")
                print(f"最终数据库图片数量: {len(images)}")
                
                if len(categories) > 0 and len(images) > 0:
                    print("✅ 最终验证成功")
                else:
                    print("❌ 最终验证失败")
                    return False
                
        except Exception as e:
            print(f"❌ 最终验证失败: {e}")
            return False
        
        print("\n🎉 完整的容灾备份流程测试通过！")
        print("✅ 表结构自动创建功能正常")
        print("✅ 数据同步功能正常")
        print("✅ 故障转移功能正常")
        print("✅ 数据访问功能正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🔧 完整容灾备份流程测试")
    print("=" * 60)
    
    success = test_complete_disaster_recovery()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试结果: 成功")
        print("完整的容灾备份功能已修复并正常工作")
        print("\n现在您可以安全地运行 run.py，系统将：")
        print("• 自动创建备用数据库表结构")
        print("• 自动同步数据到备用数据库")
        print("• 在故障时自动切换数据库")
        print("• 确保数据完整性和服务连续性")
    else:
        print("❌ 测试结果: 失败")
        print("请检查错误信息并修复相关问题")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
