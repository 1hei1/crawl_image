#!/usr/bin/env python3
"""
修复数据库同步问题

将备用数据库的数据同步到主数据库，确保数据一致性
"""

import sys
import psycopg2
import json
from pathlib import Path
from datetime import datetime

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
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"连接数据库失败 {host}:{port} - {e}")
        return None


def get_table_columns(conn, table_name):
    """获取表的列信息"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))

        columns_info = cursor.fetchall()
        cursor.close()

        return [col[0] for col in columns_info]

    except Exception as e:
        print(f"获取表 {table_name} 列信息失败: {e}")
        return None


def get_all_records(conn, table_name):
    """获取表中的所有记录"""
    try:
        cursor = conn.cursor()

        # 动态获取表的列信息
        columns = get_table_columns(conn, table_name)
        if not columns:
            return None, None

        # 构建查询SQL
        column_list = ', '.join(columns)
        cursor.execute(f"SELECT {column_list} FROM {table_name} ORDER BY id")

        records = cursor.fetchall()
        cursor.close()

        return records, columns

    except Exception as e:
        print(f"获取表 {table_name} 记录失败: {e}")
        # 如果事务失败，回滚并重新连接
        try:
            conn.rollback()
        except:
            pass
        return None, None


def insert_records(conn, table_name, records, source_columns):
    """插入记录到表中"""
    if not records:
        return True

    try:
        cursor = conn.cursor()

        # 获取目标表的列信息
        target_columns = get_table_columns(conn, table_name)
        if not target_columns:
            print(f"❌ 无法获取目标表 {table_name} 的列信息")
            return False

        # 找到源表和目标表的共同列
        common_columns = []
        column_indices = []

        for i, source_col in enumerate(source_columns):
            if source_col in target_columns:
                common_columns.append(source_col)
                column_indices.append(i)

        if not common_columns:
            print(f"❌ 源表和目标表 {table_name} 没有共同列")
            return False

        print(f"共同列: {', '.join(common_columns)}")

        # 过滤记录，只保留共同列的数据
        filtered_records = []
        for record in records:
            filtered_record = tuple(record[i] for i in column_indices)
            filtered_records.append(filtered_record)

        # 构建插入SQL
        placeholders = ', '.join(['%s'] * len(common_columns))
        column_names = ', '.join(common_columns)

        insert_sql = f"""
            INSERT INTO {table_name} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET
        """

        # 添加更新子句
        update_clauses = []
        for col in common_columns:
            if col != 'id':
                update_clauses.append(f"{col} = EXCLUDED.{col}")

        if update_clauses:
            insert_sql += ', '.join(update_clauses)
        else:
            # 如果只有id列，使用DO NOTHING
            insert_sql = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT (id) DO NOTHING
            """

        # 批量插入
        batch_size = 50
        total_inserted = 0

        for i in range(0, len(filtered_records), batch_size):
            batch = filtered_records[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
            total_inserted += len(batch)
            print(f"已处理 {total_inserted}/{len(filtered_records)} 条记录到 {table_name}")

        conn.commit()
        cursor.close()

        print(f"✅ 成功处理 {len(filtered_records)} 条记录到 {table_name}")
        return True

    except Exception as e:
        print(f"❌ 插入记录到 {table_name} 失败: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False


def sync_table_data(source_conn, target_conn, table_name):
    """同步表数据"""
    print(f"\n🔄 同步表: {table_name}")

    try:
        # 检查表是否存在
        source_cursor = source_conn.cursor()
        source_cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (table_name,))
        source_exists = source_cursor.fetchone()[0]
        source_cursor.close()

        target_cursor = target_conn.cursor()
        target_cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (table_name,))
        target_exists = target_cursor.fetchone()[0]
        target_cursor.close()

        if not source_exists:
            print(f"⚠️ 源数据库中不存在表 {table_name}，跳过")
            return True

        if not target_exists:
            print(f"⚠️ 目标数据库中不存在表 {table_name}，跳过")
            return True

        # 获取源数据库的记录
        print(f"从源数据库获取 {table_name} 记录...")
        source_records, columns = get_all_records(source_conn, table_name)

        if source_records is None:
            print(f"❌ 无法获取源数据库的 {table_name} 记录")
            return False

        print(f"源数据库有 {len(source_records)} 条记录")

        if len(source_records) == 0:
            print(f"源数据库 {table_name} 表为空，跳过同步")
            return True

        # 插入到目标数据库
        print(f"插入记录到目标数据库...")
        success = insert_records(target_conn, table_name, source_records, columns)

        return success

    except Exception as e:
        print(f"❌ 同步表 {table_name} 失败: {e}")
        return False


def main():
    """主函数"""
    print("🔧 修复数据库同步问题")
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
    
    # 检查当前状态
    print("\n2️⃣ 检查当前数据状态...")
    
    try:
        # 检查主数据库
        primary_cursor = primary_conn.cursor()
        primary_cursor.execute("SELECT COUNT(*) FROM images")
        primary_count = primary_cursor.fetchone()[0]
        primary_cursor.close()
        
        # 检查备用数据库
        secondary_cursor = secondary_conn.cursor()
        secondary_cursor.execute("SELECT COUNT(*) FROM images")
        secondary_count = secondary_cursor.fetchone()[0]
        secondary_cursor.close()
        
        print(f"主数据库 images 记录数: {primary_count}")
        print(f"备数据库 images 记录数: {secondary_count}")
        
        if primary_count == 0 and secondary_count > 0:
            print("🔄 检测到主数据库为空，备用数据库有数据")
            print("将从备用数据库同步数据到主数据库...")
            
            # 从备用数据库同步到主数据库
            source_conn = secondary_conn
            target_conn = primary_conn
            direction = "备用 -> 主"
            
        elif primary_count > 0 and secondary_count == 0:
            print("🔄 检测到备用数据库为空，主数据库有数据")
            print("将从主数据库同步数据到备用数据库...")
            
            # 从主数据库同步到备用数据库
            source_conn = primary_conn
            target_conn = secondary_conn
            direction = "主 -> 备用"
            
        elif primary_count != secondary_count:
            print("🔄 检测到数据不一致")
            if primary_count > secondary_count:
                print("主数据库记录更多，将同步到备用数据库...")
                source_conn = primary_conn
                target_conn = secondary_conn
                direction = "主 -> 备用"
            else:
                print("备用数据库记录更多，将同步到主数据库...")
                source_conn = secondary_conn
                target_conn = primary_conn
                direction = "备用 -> 主"
        else:
            print("✅ 数据库记录数一致，无需同步")
            primary_conn.close()
            secondary_conn.close()
            return True
        
        print(f"\n3️⃣ 开始数据同步 ({direction})...")
        
        # 同步 categories 表（如果存在）
        try:
            success = sync_table_data(source_conn, target_conn, 'categories')
            if not success:
                print("❌ categories 表同步失败")
        except Exception as e:
            print(f"⚠️ categories 表同步跳过: {e}")
        
        # 同步 images 表
        success = sync_table_data(source_conn, target_conn, 'images')
        
        if success:
            print("\n4️⃣ 验证同步结果...")
            
            # 重新检查记录数
            primary_cursor = primary_conn.cursor()
            primary_cursor.execute("SELECT COUNT(*) FROM images")
            new_primary_count = primary_cursor.fetchone()[0]
            primary_cursor.close()
            
            secondary_cursor = secondary_conn.cursor()
            secondary_cursor.execute("SELECT COUNT(*) FROM images")
            new_secondary_count = secondary_cursor.fetchone()[0]
            secondary_cursor.close()
            
            print(f"同步后主数据库记录数: {new_primary_count}")
            print(f"同步后备数据库记录数: {new_secondary_count}")
            
            if new_primary_count == new_secondary_count:
                print("✅ 数据同步成功！数据库现在一致了")
                
                print("\n5️⃣ 重启自动同步...")
                print("建议重启系统以确保自动同步正常工作:")
                print("  python start_simple_ha.py")
                
                result = True
            else:
                print("❌ 同步后数据仍不一致")
                result = False
        else:
            print("❌ 数据同步失败")
            result = False
        
    except Exception as e:
        print(f"❌ 同步过程中发生错误: {e}")
        result = False
    
    finally:
        primary_conn.close()
        secondary_conn.close()
    
    return result


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 数据库同步修复完成！")
    else:
        print("\n❌ 数据库同步修复失败！")
    
    sys.exit(0 if success else 1)
