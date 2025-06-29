#!/usr/bin/env python3
"""
测试TagModel修复

验证TagModel重复定义问题是否解决
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def test_tagmodel_import():
    """测试TagModel导入"""
    print("🏷️ 测试TagModel导入...")
    
    try:
        # 清理已导入的模块
        modules_to_remove = []
        for module_name in sys.modules:
            if 'database.models' in module_name:
                modules_to_remove.append(module_name)
        
        for module_name in modules_to_remove:
            del sys.modules[module_name]
        
        print("✅ 清理了模块缓存")
        
        # 重新导入
        from database.models.tag import TagModel
        print("✅ TagModel导入成功")
        
        # 测试创建实例
        tag = TagModel(name="test_tag", category="test", description="测试标签")
        print("✅ TagModel实例创建成功")
        print(f"TagModel类: {TagModel}")
        print(f"TagModel表名: {TagModel.__tablename__}")
        
        return True
        
    except Exception as e:
        print(f"❌ TagModel测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_models_import():
    """测试所有模型导入"""
    print("\n📦 测试所有模型导入...")
    
    try:
        from database.models.image import ImageModel
        print("✅ ImageModel导入成功")
        
        from database.models.category import CategoryModel
        print("✅ CategoryModel导入成功")
        
        from database.models.tag import TagModel
        print("✅ TagModel导入成功")
        
        from database.models.crawl_session import CrawlSessionModel
        print("✅ CrawlSessionModel导入成功")
        
        # 检查表名是否唯一
        table_names = [
            ImageModel.__tablename__,
            CategoryModel.__tablename__,
            TagModel.__tablename__,
            CrawlSessionModel.__tablename__
        ]
        
        print(f"表名列表: {table_names}")
        
        if len(table_names) == len(set(table_names)):
            print("✅ 所有表名唯一")
        else:
            print("❌ 发现重复表名")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 模型导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_manager_import():
    """测试数据库管理器导入"""
    print("\n🗄️ 测试数据库管理器导入...")
    
    try:
        from database.manager import DatabaseManager
        print("✅ DatabaseManager导入成功")
        
        # 测试创建实例（使用SQLite避免连接问题）
        db_manager = DatabaseManager('sqlite:///test_temp.db')
        print("✅ DatabaseManager实例创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🧪 测试TagModel修复效果")
    print("=" * 50)
    
    results = {}
    
    # 1. 测试TagModel导入
    results['tagmodel_import'] = test_tagmodel_import()
    
    # 2. 测试所有模型导入
    results['all_models_import'] = test_all_models_import()
    
    # 3. 测试数据库管理器导入
    results['database_manager'] = test_database_manager_import()
    
    # 总结结果
    print("\n" + "=" * 50)
    print("📋 测试结果总结:")
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 TagModel修复成功！")
        print("\n✅ 修复确认:")
        print("  - TagModel重复定义问题已解决")
        print("  - 所有模型导入正常")
        print("  - 数据库管理器工作正常")
        
        print("\n📝 建议:")
        print("  - 重启系统应用修复: 停止当前系统并重新运行 python start_simple_ha.py")
        print("  - 系统重启后应该不再出现TagModel相关错误")
        
        return True
    else:
        print("❌ TagModel修复失败，需要进一步检查")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
