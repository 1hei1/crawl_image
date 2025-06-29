#!/usr/bin/env python3
"""
测试TagModel与数据库匹配

验证修复后的TagModel是否与数据库结构匹配
"""

import sys
import psycopg2
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def test_tagmodel_import():
    """测试TagModel导入"""
    print("🏷️ 测试TagModel导入...")
    
    try:
        # 清理模块缓存
        modules_to_remove = []
        for module_name in sys.modules:
            if 'database.models' in module_name:
                modules_to_remove.append(module_name)
        
        for module_name in modules_to_remove:
            del sys.modules[module_name]
        
        # 重新导入
        from database.models.tag import TagModel
        print("✅ TagModel导入成功")
        
        # 显示字段
        print("📋 TagModel字段:")
        for column in TagModel.__table__.columns:
            print(f"  {column.name}: {column.type}")
        
        return True
        
    except Exception as e:
        print(f"❌ TagModel导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tagmodel_query():
    """测试TagModel数据库查询"""
    print("\n🗄️ 测试TagModel数据库查询...")
    
    try:
        from database.models.tag import TagModel
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # 连接到主数据库
        engine = create_engine('postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # 测试查询
            count = session.query(TagModel).count()
            print(f"✅ 查询成功，tags表记录数: {count}")
            
            # 如果有记录，显示前几条
            if count > 0:
                tags = session.query(TagModel).limit(3).all()
                print("📋 前3条记录:")
                for tag in tags:
                    print(f"  ID: {tag.id}, Name: {tag.name}, Group: {tag.group_name}")
            
            return True
            
        finally:
            session.close()
        
    except Exception as e:
        print(f"❌ TagModel查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tagmodel_create():
    """测试TagModel创建记录"""
    print("\n➕ 测试TagModel创建记录...")
    
    try:
        from database.models.tag import TagModel
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import time
        
        # 连接到主数据库
        engine = create_engine('postgresql://postgres:Abcdefg6@113.29.231.99:5432/image_crawler')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # 创建测试标签
            timestamp = int(time.time())
            test_tag = TagModel(
                name=f"test_tag_{timestamp}",
                slug=f"test-tag-{timestamp}",
                description="测试标签",
                group_name="test",
                tag_type="manual",
                usage_count=0,
                status="active"
            )
            
            session.add(test_tag)
            session.commit()
            
            test_tag_id = test_tag.id
            print(f"✅ 创建测试标签成功，ID: {test_tag_id}")
            
            # 验证创建
            created_tag = session.query(TagModel).filter(TagModel.id == test_tag_id).first()
            if created_tag:
                print(f"✅ 验证成功: {created_tag.name}")
            else:
                print("❌ 验证失败：未找到创建的标签")
                return False
            
            # 清理测试数据
            session.delete(created_tag)
            session.commit()
            print("✅ 测试数据清理完成")
            
            return True
            
        finally:
            session.close()
        
    except Exception as e:
        print(f"❌ TagModel创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🧪 测试TagModel与数据库匹配")
    print("=" * 50)
    
    results = {}
    
    # 1. 测试导入
    results['import'] = test_tagmodel_import()
    
    # 2. 测试查询
    results['query'] = test_tagmodel_query()
    
    # 3. 测试创建
    results['create'] = test_tagmodel_create()
    
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
        print("  - TagModel字段与数据库表结构匹配")
        print("  - 可以正常查询tags表")
        print("  - 可以正常创建和删除记录")
        
        print("\n📝 建议:")
        print("  - 重启系统应用修复")
        print("  - 系统重启后应该不再出现TagModel相关错误")
        
        return True
    else:
        print("❌ TagModel修复失败")
        print("\n🔧 需要进一步检查:")
        print("  - 数据库连接是否正常")
        print("  - 表结构是否完全匹配")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
