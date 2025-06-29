#!/usr/bin/env python3
"""
测试实际同步功能

验证数据是否真正同步到备用数据库
"""

import sys
import time
import psycopg2
import requests
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


def get_table_count(conn, table_name):
    """获取表记录数"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        cursor.close()
        return count
    except Exception as e:
        print(f"获取表 {table_name} 记录数失败: {e}")
        return 0


def get_latest_records(conn, table_name, limit=3):
    """获取最新的几条记录"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, created_at FROM {table_name} ORDER BY id DESC LIMIT %s", (limit,))
        records = cursor.fetchall()
        cursor.close()
        return records
    except Exception as e:
        print(f"获取表 {table_name} 最新记录失败: {e}")
        return []


def check_database_consistency():
    """检查数据库一致性"""
    print("🔍 检查数据库一致性...")
    
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
    
    # 检查表一致性
    tables = ['images', 'crawl_sessions', 'categories', 'tags']
    inconsistent_tables = []
    
    print("\n📊 数据库记录数对比:")
    print("表名           主数据库    备数据库    差异")
    print("-" * 50)
    
    for table_name in tables:
        primary_count = get_table_count(primary_conn, table_name)
        secondary_count = get_table_count(secondary_conn, table_name)
        diff = primary_count - secondary_count
        
        status = "✅" if diff == 0 else "❌"
        print(f"{table_name:<12} {primary_count:>8} {secondary_count:>10} {diff:>8} {status}")
        
        if diff != 0:
            inconsistent_tables.append(table_name)
    
    # 显示最新记录对比
    if inconsistent_tables:
        print(f"\n📋 不一致的表详情:")
        for table_name in inconsistent_tables:
            print(f"\n{table_name} 表最新记录:")
            
            primary_records = get_latest_records(primary_conn, table_name)
            secondary_records = get_latest_records(secondary_conn, table_name)
            
            print("  主数据库最新记录:")
            for record in primary_records:
                print(f"    ID: {record[0]}, 时间: {record[1]}")
            
            print("  备数据库最新记录:")
            for record in secondary_records:
                print(f"    ID: {record[0]}, 时间: {record[1]}")
    
    primary_conn.close()
    secondary_conn.close()
    
    return len(inconsistent_tables) == 0


def trigger_force_sync():
    """触发强制同步"""
    print("\n🔄 触发强制同步...")
    
    try:
        response = requests.post("http://localhost:8000/api/force-sync", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 强制同步请求成功: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"❌ 强制同步请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 强制同步请求异常: {e}")
        return False


def wait_for_sync():
    """等待同步完成"""
    print("\n⏳ 等待同步完成...")
    
    for i in range(30):  # 等待最多30秒
        try:
            response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                queue_size = data.get('sync_queue_size', 0)
                print(f"同步队列: {queue_size} 个操作", end='\r')
                
                if queue_size == 0 and i > 5:  # 等待至少5秒
                    print("\n✅ 同步队列已清空")
                    break
            
            time.sleep(1)
        except Exception as e:
            print(f"检查同步状态失败: {e}")
            break
    
    # 额外等待5秒确保同步完成
    print("等待额外5秒确保同步完成...")
    time.sleep(5)


def main():
    """主测试函数"""
    print("🧪 测试实际同步功能")
    print("=" * 60)
    
    # 检查系统是否运行
    try:
        response = requests.get("http://localhost:8000/api/ha-status", timeout=5)
        if response.status_code != 200:
            print("❌ 系统未运行，请先启动: python start_simple_ha.py")
            return False
    except Exception:
        print("❌ 系统未运行，请先启动: python start_simple_ha.py")
        return False
    
    print("✅ 系统正在运行")
    
    # 1. 检查初始状态
    print("\n1️⃣ 检查初始数据库状态...")
    initial_consistent = check_database_consistency()
    
    if initial_consistent:
        print("✅ 数据库已经一致，无需同步")
        return True
    
    # 2. 触发强制同步
    print("\n2️⃣ 触发强制同步...")
    sync_triggered = trigger_force_sync()
    
    if not sync_triggered:
        print("❌ 无法触发强制同步")
        return False
    
    # 3. 等待同步完成
    print("\n3️⃣ 等待同步完成...")
    wait_for_sync()
    
    # 4. 检查同步后状态
    print("\n4️⃣ 检查同步后数据库状态...")
    final_consistent = check_database_consistency()
    
    # 5. 总结结果
    print("\n" + "=" * 60)
    if final_consistent:
        print("🎉 同步测试成功！数据库现在一致了。")
        print("\n✅ 确认:")
        print("  - 强制同步功能正常")
        print("  - 数据成功同步到备用数据库")
        print("  - 主备数据库数据一致")
        return True
    else:
        print("❌ 同步测试失败！数据库仍不一致。")
        print("\n🔧 建议检查:")
        print("  - 查看系统日志: logs/simple_ha.log")
        print("  - 检查网络连接")
        print("  - 检查数据库权限")
        print("  - 手动运行: python sync_all_tables.py")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
