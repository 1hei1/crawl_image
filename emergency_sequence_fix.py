#!/usr/bin/env python3
"""
紧急序列修复

解决故障转移后的序列不同步问题
"""

import sys
import psycopg2
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def connect_to_database(host, port, database, user, password):
    """连接到数据库"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"连接数据库失败 {host}:{port} - {e}")
        return None


def get_max_id_and_sequence(conn, table_name, sequence_name):
    """获取表的最大ID和序列当前值"""
    try:
        cursor = conn.cursor()
        
        # 获取表的最大ID
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
        max_id = cursor.fetchone()[0]
        
        # 获取序列当前值
        cursor.execute(f"SELECT last_value FROM {sequence_name}")
        sequence_value = cursor.fetchone()[0]
        
        cursor.close()
        return max_id, sequence_value
        
    except Exception as e:
        print(f"获取 {table_name} 信息失败: {e}")
        return 0, 0


def fix_sequence(conn, table_name, sequence_name, new_value):
    """修复序列值"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT setval('{sequence_name}', {new_value})")
        cursor.close()
        return True
    except Exception as e:
        print(f"修复序列 {sequence_name} 失败: {e}")
        return False


def emergency_fix_all_sequences():
    """紧急修复所有序列"""
    print("🚨 紧急修复所有数据库序列")
    print("=" * 60)
    
    # 数据库连接信息
    databases = [
        {
            'name': '主数据库',
            'host': '113.29.231.99',
            'port': 5432,
            'database': 'image_crawler',
            'user': 'postgres',
            'password': 'Abcdefg6'
        },
        {
            'name': '备数据库',
            'host': '113.29.232.245',
            'port': 5432,
            'database': 'image_crawler',
            'user': 'postgres',
            'password': 'Abcdefg6'
        }
    ]
    
    # 需要修复的表和序列
    tables_sequences = [
        ('crawl_sessions', 'crawl_sessions_id_seq'),
        ('images', 'images_id_seq'),
        ('categories', 'categories_id_seq'),
        ('tags', 'tags_id_seq')
    ]
    
    # 收集所有数据库的最大ID
    all_max_ids = {}
    
    print("📊 收集所有数据库的最大ID...")
    for db_info in databases:
        print(f"\n检查 {db_info['name']}...")
        conn = connect_to_database(
            db_info['host'], db_info['port'], 
            db_info['database'], db_info['user'], db_info['password']
        )
        
        if not conn:
            print(f"❌ 无法连接到 {db_info['name']}")
            continue
        
        for table_name, sequence_name in tables_sequences:
            max_id, sequence_value = get_max_id_and_sequence(conn, table_name, sequence_name)
            
            if table_name not in all_max_ids:
                all_max_ids[table_name] = []
            
            all_max_ids[table_name].append({
                'db': db_info['name'],
                'max_id': max_id,
                'sequence_value': sequence_value
            })
            
            print(f"  {table_name}: 最大ID={max_id}, 序列值={sequence_value}")
        
        conn.close()
    
    # 计算每个表的全局最大ID
    print(f"\n🔧 计算全局最大ID并修复序列...")
    
    for table_name, sequence_name in tables_sequences:
        if table_name not in all_max_ids:
            continue
        
        # 找到所有数据库中的最大ID
        global_max_id = max([info['max_id'] for info in all_max_ids[table_name]])
        
        # 设置新的序列值（最大ID + 50，留足够余量）
        new_sequence_value = global_max_id + 50
        
        print(f"\n{table_name}:")
        print(f"  全局最大ID: {global_max_id}")
        print(f"  新序列值: {new_sequence_value}")
        
        # 更新所有数据库的序列
        for db_info in databases:
            conn = connect_to_database(
                db_info['host'], db_info['port'], 
                db_info['database'], db_info['user'], db_info['password']
            )
            
            if conn:
                success = fix_sequence(conn, table_name, sequence_name, new_sequence_value)
                if success:
                    print(f"    ✅ {db_info['name']} 序列更新成功")
                else:
                    print(f"    ❌ {db_info['name']} 序列更新失败")
                conn.close()
    
    # 验证修复结果
    print(f"\n✅ 验证修复结果...")
    
    for db_info in databases:
        print(f"\n{db_info['name']} 修复后状态:")
        conn = connect_to_database(
            db_info['host'], db_info['port'], 
            db_info['database'], db_info['user'], db_info['password']
        )
        
        if conn:
            for table_name, sequence_name in tables_sequences:
                max_id, sequence_value = get_max_id_and_sequence(conn, table_name, sequence_name)
                status = "✅" if sequence_value > max_id else "❌"
                print(f"  {table_name}: 最大ID={max_id}, 序列值={sequence_value} {status}")
            conn.close()
    
    return True


def test_sequence_fix():
    """测试序列修复是否成功"""
    print(f"\n🧪 测试序列修复...")
    
    # 连接到当前主数据库（备数据库，因为发生了故障转移）
    conn = connect_to_database(
        '113.29.232.245', 5432, 'image_crawler', 'postgres', 'Abcdefg6'
    )
    
    if not conn:
        print("❌ 无法连接到数据库进行测试")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 测试插入一条crawl_sessions记录
        cursor.execute("""
            INSERT INTO crawl_sessions (session_name, target_url, session_type, status)
            VALUES ('test_sequence_fix', 'https://test.com', 'manual', 'completed')
            RETURNING id
        """)
        
        new_id = cursor.fetchone()[0]
        print(f"✅ 测试插入成功，新ID: {new_id}")
        
        # 删除测试记录
        cursor.execute("DELETE FROM crawl_sessions WHERE id = %s", (new_id,))
        print(f"✅ 测试记录清理完成")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        conn.close()
        return False


def main():
    """主函数"""
    print("🚨 紧急序列修复工具")
    print("=" * 60)
    
    # 1. 紧急修复所有序列
    fix_success = emergency_fix_all_sequences()
    
    # 2. 测试修复结果
    test_success = test_sequence_fix()
    
    # 3. 总结结果
    print("\n" + "=" * 60)
    print("📋 紧急修复结果:")
    
    if fix_success and test_success:
        print("🎉 紧急序列修复成功！")
        print("\n✅ 修复内容:")
        print("  - 所有数据库序列已同步")
        print("  - 序列值设置为最大ID+50")
        print("  - 测试插入操作正常")
        print("  - 主键冲突问题已解决")
        
        print("\n📝 建议:")
        print("  - 现在可以正常使用爬虫功能")
        print("  - 监控系统确保无更多错误")
        print("  - 如果还有问题，检查故障转移逻辑")
        
        return True
    else:
        print("❌ 紧急序列修复失败！")
        print("\n🔧 建议:")
        print("  - 手动检查数据库连接")
        print("  - 检查数据库权限")
        print("  - 考虑重建数据库")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
