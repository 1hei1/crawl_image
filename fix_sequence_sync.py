#!/usr/bin/env python3
"""
修复数据库序列同步问题

解决故障转移后主键冲突的问题
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


def get_max_id(conn, table_name):
    """获取表的最大ID"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
        max_id = cursor.fetchone()[0]
        cursor.close()
        return max_id
    except Exception as e:
        print(f"获取表 {table_name} 最大ID失败: {e}")
        return 0


def get_sequence_value(conn, sequence_name):
    """获取序列当前值"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT last_value FROM {sequence_name}")
        last_value = cursor.fetchone()[0]
        cursor.close()
        return last_value
    except Exception as e:
        print(f"获取序列 {sequence_name} 值失败: {e}")
        return 0


def set_sequence_value(conn, sequence_name, value):
    """设置序列值"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT setval('{sequence_name}', {value})")
        cursor.close()
        return True
    except Exception as e:
        print(f"设置序列 {sequence_name} 值失败: {e}")
        return False


def get_table_sequences(conn):
    """获取所有表的序列信息"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                t.table_name,
                c.column_name,
                s.sequence_name
            FROM information_schema.tables t
            JOIN information_schema.columns c ON t.table_name = c.table_name
            JOIN information_schema.sequences s ON s.sequence_name = t.table_name || '_' || c.column_name || '_seq'
            WHERE t.table_schema = 'public' 
            AND c.column_default LIKE 'nextval%'
            ORDER BY t.table_name
        """)
        
        sequences = cursor.fetchall()
        cursor.close()
        return sequences
    except Exception as e:
        print(f"获取序列信息失败: {e}")
        return []


def sync_sequences_between_databases():
    """同步两个数据库之间的序列"""
    print("🔄 同步数据库序列...")
    
    # 数据库连接信息
    primary_db = {
        'host': '113.29.231.99',
        'port': 5432,
        'database': 'image_crawler',
        'user': 'postgres',
        'password': 'Abcdefg6'
    }
    
    secondary_db = {
        'host': '113.29.232.245',
        'port': 5432,
        'database': 'image_crawler',
        'user': 'postgres',
        'password': 'Abcdefg6'
    }
    
    # 连接数据库
    primary_conn = connect_to_database(**primary_db)
    secondary_conn = connect_to_database(**secondary_db)
    
    if not primary_conn or not secondary_conn:
        print("❌ 数据库连接失败")
        return False
    
    # 获取序列信息
    sequences = get_table_sequences(primary_conn)
    if not sequences:
        print("❌ 无法获取序列信息")
        return False
    
    print(f"发现 {len(sequences)} 个序列需要同步")
    
    # 同步每个序列
    success_count = 0
    for table_name, column_name, sequence_name in sequences:
        print(f"\n🔄 同步序列: {sequence_name} ({table_name}.{column_name})")
        
        # 获取两个数据库的最大ID
        primary_max_id = get_max_id(primary_conn, table_name)
        secondary_max_id = get_max_id(secondary_conn, table_name)
        
        print(f"  主数据库最大ID: {primary_max_id}")
        print(f"  备数据库最大ID: {secondary_max_id}")
        
        # 使用较大的ID作为新的序列值
        max_id = max(primary_max_id, secondary_max_id)
        new_sequence_value = max_id + 1
        
        print(f"  设置序列值为: {new_sequence_value}")
        
        # 更新两个数据库的序列
        primary_success = set_sequence_value(primary_conn, sequence_name, new_sequence_value)
        secondary_success = set_sequence_value(secondary_conn, sequence_name, new_sequence_value)
        
        if primary_success and secondary_success:
            print(f"  ✅ 序列同步成功")
            success_count += 1
        else:
            print(f"  ❌ 序列同步失败")
    
    primary_conn.close()
    secondary_conn.close()
    
    print(f"\n📊 同步结果: {success_count}/{len(sequences)} 个序列同步成功")
    return success_count == len(sequences)


def fix_specific_sequence_issue():
    """修复特定的crawl_sessions序列问题"""
    print("\n🔧 修复crawl_sessions序列问题...")
    
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
    
    max_id_overall = 0
    
    # 获取两个数据库中crawl_sessions表的最大ID
    for db_info in databases:
        conn = connect_to_database(
            db_info['host'], db_info['port'], 
            db_info['database'], db_info['user'], db_info['password']
        )
        
        if conn:
            max_id = get_max_id(conn, 'crawl_sessions')
            print(f"{db_info['name']} crawl_sessions 最大ID: {max_id}")
            max_id_overall = max(max_id_overall, max_id)
            conn.close()
    
    # 设置新的序列值
    new_sequence_value = max_id_overall + 10  # 留一些余量
    print(f"\n设置新的序列值: {new_sequence_value}")
    
    # 更新两个数据库的序列
    success_count = 0
    for db_info in databases:
        conn = connect_to_database(
            db_info['host'], db_info['port'], 
            db_info['database'], db_info['user'], db_info['password']
        )
        
        if conn:
            success = set_sequence_value(conn, 'crawl_sessions_id_seq', new_sequence_value)
            if success:
                print(f"✅ {db_info['name']} 序列更新成功")
                success_count += 1
            else:
                print(f"❌ {db_info['name']} 序列更新失败")
            conn.close()
    
    return success_count == 2


def main():
    """主函数"""
    print("🔧 修复数据库序列同步问题")
    print("=" * 60)
    
    # 1. 修复特定的crawl_sessions问题
    crawl_sessions_fixed = fix_specific_sequence_issue()
    
    # 2. 全面同步所有序列
    all_sequences_synced = sync_sequences_between_databases()
    
    # 3. 总结结果
    print("\n" + "=" * 60)
    print("📋 修复结果总结:")
    
    if crawl_sessions_fixed:
        print("✅ crawl_sessions序列修复成功")
    else:
        print("❌ crawl_sessions序列修复失败")
    
    if all_sequences_synced:
        print("✅ 所有序列同步成功")
    else:
        print("❌ 部分序列同步失败")
    
    if crawl_sessions_fixed and all_sequences_synced:
        print("\n🎉 序列同步修复完成！")
        print("\n✅ 修复内容:")
        print("  - 解决了主键冲突问题")
        print("  - 同步了所有数据库序列")
        print("  - 确保故障转移后的数据一致性")
        
        print("\n📝 建议:")
        print("  - 重启系统以应用修复")
        print("  - 测试爬虫功能是否正常")
        print("  - 监控系统日志确认无错误")
        
        return True
    else:
        print("\n❌ 序列同步修复失败！")
        print("\n🔧 建议检查:")
        print("  - 数据库连接权限")
        print("  - 序列是否存在")
        print("  - 手动检查数据库状态")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
