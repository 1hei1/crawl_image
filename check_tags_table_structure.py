#!/usr/bin/env python3
"""
检查tags表结构

查看数据库中实际的tags表结构，并与TagModel定义对比
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
        return conn
    except Exception as e:
        print(f"连接数据库失败 {host}:{port} - {e}")
        return None


def get_table_structure(conn, table_name):
    """获取表结构"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s 
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        cursor.close()
        return columns
        
    except Exception as e:
        print(f"获取表 {table_name} 结构失败: {e}")
        return None


def check_table_exists(conn, table_name):
    """检查表是否存在"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists
        
    except Exception as e:
        print(f"检查表 {table_name} 是否存在失败: {e}")
        return False


def main():
    """主函数"""
    print("🔍 检查tags表结构")
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
    
    for db_info in databases:
        print(f"\n📊 检查{db_info['name']} ({db_info['host']})...")
        
        conn = connect_to_database(
            db_info['host'], db_info['port'], 
            db_info['database'], db_info['user'], db_info['password']
        )
        
        if not conn:
            print(f"❌ 无法连接到{db_info['name']}")
            continue
        
        # 检查tags表是否存在
        if check_table_exists(conn, 'tags'):
            print("✅ tags表存在")
            
            # 获取表结构
            columns = get_table_structure(conn, 'tags')
            if columns:
                print("📋 tags表结构:")
                print("  列名                数据类型        可空    默认值")
                print("  " + "-" * 60)
                for col in columns:
                    column_name, data_type, is_nullable, column_default = col
                    nullable = "YES" if is_nullable == "YES" else "NO"
                    default = str(column_default) if column_default else "NULL"
                    print(f"  {column_name:<18} {data_type:<12} {nullable:<6} {default}")
            else:
                print("❌ 无法获取tags表结构")
        else:
            print("❌ tags表不存在")
        
        conn.close()
    
    # 显示新TagModel定义的字段
    print(f"\n📝 新TagModel定义的字段:")
    print("  " + "-" * 60)
    
    try:
        from database.models.tag import TagModel
        
        print("  字段名              类型            说明")
        print("  " + "-" * 60)
        for column in TagModel.__table__.columns:
            col_name = column.name
            col_type = str(column.type)
            col_comment = getattr(column, 'comment', '') or ''
            print(f"  {col_name:<18} {col_type:<12} {col_comment}")
            
    except Exception as e:
        print(f"❌ 无法获取TagModel定义: {e}")
    
    print(f"\n💡 建议解决方案:")
    print("1. 如果tags表结构与TagModel不匹配，需要:")
    print("   - 删除现有的tags表")
    print("   - 重新创建符合TagModel定义的tags表")
    print("   - 或者修改TagModel定义以匹配现有表结构")
    
    print("\n2. 执行修复:")
    print("   python fix_tags_table_structure.py")


if __name__ == "__main__":
    main()
