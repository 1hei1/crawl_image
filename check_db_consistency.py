#!/usr/bin/env python3
"""
检查数据库一致性工具

比较主备数据库的数据一致性并提供修复建议
"""

import sys
import psycopg2
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel
from database.models.category import CategoryModel


def connect_to_database(host, port, database, user, password):
    """直接连接到数据库"""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        print(f"连接数据库失败 {host}:{port} - {e}")
        return None


def get_table_stats(conn, table_name):
    """获取表的统计信息"""
    try:
        cursor = conn.cursor()
        
        # 获取记录总数
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_count = cursor.fetchone()[0]
        
        # 获取最新记录的ID和时间
        cursor.execute(f"""
            SELECT id, created_at 
            FROM {table_name} 
            ORDER BY id DESC 
            LIMIT 1
        """)
        latest_record = cursor.fetchone()
        
        # 获取最早记录的ID和时间
        cursor.execute(f"""
            SELECT id, created_at 
            FROM {table_name} 
            ORDER BY id ASC 
            LIMIT 1
        """)
        earliest_record = cursor.fetchone()
        
        cursor.close()
        
        return {
            'total_count': total_count,
            'latest_id': latest_record[0] if latest_record else None,
            'latest_time': latest_record[1] if latest_record else None,
            'earliest_id': earliest_record[0] if earliest_record else None,
            'earliest_time': earliest_record[1] if earliest_record else None
        }
        
    except Exception as e:
        print(f"获取表 {table_name} 统计信息失败: {e}")
        return None


def get_missing_records(primary_conn, secondary_conn, table_name):
    """获取备用数据库中缺失的记录"""
    try:
        primary_cursor = primary_conn.cursor()
        secondary_cursor = secondary_conn.cursor()
        
        # 获取主数据库中的所有ID
        primary_cursor.execute(f"SELECT id FROM {table_name} ORDER BY id")
        primary_ids = set(row[0] for row in primary_cursor.fetchall())
        
        # 获取备用数据库中的所有ID
        secondary_cursor.execute(f"SELECT id FROM {table_name} ORDER BY id")
        secondary_ids = set(row[0] for row in secondary_cursor.fetchall())
        
        # 找出缺失的ID
        missing_ids = primary_ids - secondary_ids
        extra_ids = secondary_ids - primary_ids
        
        primary_cursor.close()
        secondary_cursor.close()
        
        return {
            'missing_in_secondary': sorted(missing_ids),
            'extra_in_secondary': sorted(extra_ids),
            'primary_total': len(primary_ids),
            'secondary_total': len(secondary_ids)
        }
        
    except Exception as e:
        print(f"比较表 {table_name} 记录失败: {e}")
        return None


def main():
    """主函数"""
    print("🔍 检查数据库一致性")
    print("=" * 60)
    
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
    
    # 连接到数据库
    print("1️⃣ 连接到数据库...")
    primary_conn = connect_to_database(**primary_db)
    secondary_conn = connect_to_database(**secondary_db)
    
    if not primary_conn:
        print("❌ 无法连接到主数据库")
        return False
    
    if not secondary_conn:
        print("❌ 无法连接到备用数据库")
        return False
    
    print("✅ 数据库连接成功")
    
    # 获取所有表
    print("2️⃣ 获取数据库表列表...")
    try:
        primary_cursor = primary_conn.cursor()
        primary_cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables_to_check = [row[0] for row in primary_cursor.fetchall()]
        primary_cursor.close()

        print(f"发现 {len(tables_to_check)} 个表: {', '.join(tables_to_check)}")
    except Exception as e:
        print(f"获取表列表失败: {e}")
        tables_to_check = ['images', 'categories', 'crawl_sessions', 'tags']

    # 检查表一致性
    inconsistent_tables = []

    for table_name in tables_to_check:
        print(f"\n3️⃣ 检查表: {table_name}")
        
        # 获取统计信息
        primary_stats = get_table_stats(primary_conn, table_name)
        secondary_stats = get_table_stats(secondary_conn, table_name)
        
        if not primary_stats or not secondary_stats:
            print(f"❌ 无法获取表 {table_name} 的统计信息")
            continue
        
        print(f"主数据库记录数: {primary_stats['total_count']}")
        print(f"备数据库记录数: {secondary_stats['total_count']}")
        
        if primary_stats['total_count'] != secondary_stats['total_count']:
            print(f"⚠️ 记录数不一致！差异: {primary_stats['total_count'] - secondary_stats['total_count']}")
            inconsistent_tables.append(table_name)
            
            # 详细分析缺失记录
            missing_info = get_missing_records(primary_conn, secondary_conn, table_name)
            if missing_info:
                print(f"备用数据库缺失记录: {len(missing_info['missing_in_secondary'])} 条")
                print(f"备用数据库多余记录: {len(missing_info['extra_in_secondary'])} 条")
                
                if missing_info['missing_in_secondary']:
                    print(f"缺失的ID范围: {min(missing_info['missing_in_secondary'])} - {max(missing_info['missing_in_secondary'])}")
                
        else:
            print("✅ 记录数一致")
        
        # 显示最新记录信息
        if primary_stats['latest_id'] and secondary_stats['latest_id']:
            print(f"主数据库最新ID: {primary_stats['latest_id']} ({primary_stats['latest_time']})")
            print(f"备数据库最新ID: {secondary_stats['latest_id']} ({secondary_stats['latest_time']})")
    
    # 总结和建议
    print("\n" + "=" * 60)
    if inconsistent_tables:
        print("❌ 发现数据不一致问题！")
        print(f"不一致的表: {', '.join(inconsistent_tables)}")
        
        print("\n🔧 修复建议:")
        print("1. 执行强制全量同步:")
        print("   python tools/sync_monitor.py force-sync")
        
        print("\n2. 或者使用API强制同步:")
        print("   curl -X POST http://localhost:8000/api/force-sync")
        
        print("\n3. 检查同步日志:")
        print("   tail -f logs/simple_ha.log | grep sync")
        
        print("\n4. 如果问题持续，可以手动同步:")
        print("   python manual_sync_fix.py")
        
        # 关闭连接
        primary_conn.close()
        secondary_conn.close()
        return False
        
    else:
        print("✅ 所有表数据一致！")
        
        # 关闭连接
        primary_conn.close()
        secondary_conn.close()
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
