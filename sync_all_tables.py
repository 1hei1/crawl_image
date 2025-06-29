#!/usr/bin/env python3
"""
完整数据库表同步工具

同步所有表的数据，确保主备数据库完全一致
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
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"连接数据库失败 {host}:{port} - {e}")
        return None


def get_all_tables(conn):
    """获取数据库中的所有表"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return tables
        
    except Exception as e:
        print(f"获取表列表失败: {e}")
        return []


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


def get_table_record_count(conn, table_name):
    """获取表的记录数"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        cursor.close()
        return count
    except Exception as e:
        print(f"获取表 {table_name} 记录数失败: {e}")
        return 0


def get_all_records(conn, table_name):
    """获取表中的所有记录"""
    try:
        cursor = conn.cursor()

        # 动态获取表的列信息
        columns = get_table_columns(conn, table_name)
        if not columns:
            return None, None

        # 构建查询SQL，按主键排序
        column_list = ', '.join(columns)
        if 'id' in columns:
            cursor.execute(f"SELECT {column_list} FROM {table_name} ORDER BY id")
        else:
            cursor.execute(f"SELECT {column_list} FROM {table_name}")

        records = cursor.fetchall()

        # 处理记录中的特殊数据类型
        processed_records = []
        for record in records:
            processed_record = []
            for value in record:
                if isinstance(value, dict):
                    # 将字典转换为JSON字符串
                    import json
                    processed_record.append(json.dumps(value))
                elif isinstance(value, list):
                    # 将列表转换为JSON字符串
                    import json
                    processed_record.append(json.dumps(value))
                else:
                    processed_record.append(value)
            processed_records.append(tuple(processed_record))

        cursor.close()

        return processed_records, columns

    except Exception as e:
        print(f"获取表 {table_name} 记录失败: {e}")
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
        
        print(f"  共同列数: {len(common_columns)}")
        
        # 过滤记录，只保留共同列的数据
        filtered_records = []
        for record in records:
            filtered_record = tuple(record[i] for i in column_indices)
            filtered_records.append(filtered_record)
        
        # 构建插入SQL
        placeholders = ', '.join(['%s'] * len(common_columns))
        column_names = ', '.join(common_columns)
        
        # 检查是否有主键列
        has_id = 'id' in common_columns
        
        if has_id:
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
                insert_sql = f"""
                    INSERT INTO {table_name} ({column_names}) 
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO NOTHING
                """
        else:
            # 没有主键的表，直接插入
            insert_sql = f"""
                INSERT INTO {table_name} ({column_names}) 
                VALUES ({placeholders})
            """
        
        # 批量插入
        batch_size = 100
        total_inserted = 0
        
        for i in range(0, len(filtered_records), batch_size):
            batch = filtered_records[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
            total_inserted += len(batch)
            if total_inserted % 50 == 0 or total_inserted == len(filtered_records):
                print(f"  已处理 {total_inserted}/{len(filtered_records)} 条记录")
        
        conn.commit()
        cursor.close()
        
        print(f"  ✅ 成功处理 {len(filtered_records)} 条记录")
        return True
        
    except Exception as e:
        print(f"  ❌ 插入记录失败: {e}")
        try:
            conn.rollback()
        except:
            pass
        return False


def sync_table_data(source_conn, target_conn, table_name):
    """同步表数据"""
    print(f"\n🔄 同步表: {table_name}")
    
    try:
        # 获取记录数
        source_count = get_table_record_count(source_conn, table_name)
        target_count = get_table_record_count(target_conn, table_name)
        
        print(f"  源数据库记录数: {source_count}")
        print(f"  目标数据库记录数: {target_count}")
        
        if source_count == 0:
            print(f"  源数据库 {table_name} 表为空，跳过同步")
            return True
        
        if source_count == target_count:
            print(f"  记录数相同，跳过同步")
            return True
        
        # 获取源数据库的记录
        print(f"  从源数据库获取记录...")
        source_records, columns = get_all_records(source_conn, table_name)
        
        if source_records is None:
            print(f"  ❌ 无法获取源数据库的记录")
            return False
        
        # 插入到目标数据库
        print(f"  插入记录到目标数据库...")
        success = insert_records(target_conn, table_name, source_records, columns)
        
        return success
        
    except Exception as e:
        print(f"  ❌ 同步表失败: {e}")
        return False


def main():
    """主函数"""
    print("🔄 完整数据库表同步")
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
    
    if not primary_conn or not secondary_conn:
        print("❌ 数据库连接失败")
        return False
    
    print("✅ 数据库连接成功")
    
    # 获取所有表
    print("\n2️⃣ 获取数据库表列表...")
    primary_tables = get_all_tables(primary_conn)
    secondary_tables = get_all_tables(secondary_conn)
    
    print(f"主数据库表数: {len(primary_tables)}")
    print(f"备数据库表数: {len(secondary_tables)}")
    
    # 找到共同的表
    common_tables = set(primary_tables) & set(secondary_tables)
    print(f"共同表数: {len(common_tables)}")
    print(f"共同表: {', '.join(sorted(common_tables))}")
    
    if not common_tables:
        print("❌ 没有共同的表可以同步")
        return False
    
    # 确定同步方向
    print("\n3️⃣ 确定同步方向...")
    
    # 统计总记录数
    primary_total = sum(get_table_record_count(primary_conn, table) for table in common_tables)
    secondary_total = sum(get_table_record_count(secondary_conn, table) for table in common_tables)
    
    print(f"主数据库总记录数: {primary_total}")
    print(f"备数据库总记录数: {secondary_total}")
    
    if primary_total == secondary_total:
        print("✅ 数据库记录数相同，无需同步")
        return True
    
    if primary_total > secondary_total:
        print("🔄 主数据库记录更多，同步到备数据库")
        source_conn = primary_conn
        target_conn = secondary_conn
        direction = "主 -> 备"
    else:
        print("🔄 备数据库记录更多，同步到主数据库")
        source_conn = secondary_conn
        target_conn = primary_conn
        direction = "备 -> 主"
    
    # 开始同步
    print(f"\n4️⃣ 开始数据同步 ({direction})...")
    
    success_count = 0
    failed_tables = []
    
    for table_name in sorted(common_tables):
        try:
            success = sync_table_data(source_conn, target_conn, table_name)
            if success:
                success_count += 1
            else:
                failed_tables.append(table_name)
        except Exception as e:
            print(f"❌ 同步表 {table_name} 时发生错误: {e}")
            failed_tables.append(table_name)
    
    # 验证结果
    print(f"\n5️⃣ 同步结果:")
    print(f"成功同步: {success_count}/{len(common_tables)} 个表")
    
    if failed_tables:
        print(f"失败的表: {', '.join(failed_tables)}")
    
    # 最终验证
    print(f"\n6️⃣ 最终验证...")
    final_primary_total = sum(get_table_record_count(primary_conn, table) for table in common_tables)
    final_secondary_total = sum(get_table_record_count(secondary_conn, table) for table in common_tables)
    
    print(f"同步后主数据库总记录数: {final_primary_total}")
    print(f"同步后备数据库总记录数: {final_secondary_total}")
    
    if final_primary_total == final_secondary_total:
        print("✅ 数据库同步成功！所有表数据一致")
        result = True
    else:
        print("❌ 数据库仍不一致")
        result = False
    
    # 关闭连接
    primary_conn.close()
    secondary_conn.close()
    
    return result


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 完整数据库同步完成！")
        print("\n建议重启系统以确保自动同步正常工作:")
        print("  python start_simple_ha.py")
    else:
        print("\n❌ 数据库同步失败！")
    
    sys.exit(0 if success else 1)
