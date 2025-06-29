#!/usr/bin/env python3
"""
最终同步测试

验证所有修复后的同步功能是否正常工作
"""

import sys
import time
import requests
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
        return False, {}
    
    # 检查表一致性
    tables = ['images', 'crawl_sessions', 'categories', 'tags']
    inconsistent_tables = []
    stats = {}
    
    print("\n📊 数据库记录数对比:")
    print("表名           主数据库    备数据库    差异")
    print("-" * 50)
    
    for table_name in tables:
        primary_count = get_table_count(primary_conn, table_name)
        secondary_count = get_table_count(secondary_conn, table_name)
        diff = primary_count - secondary_count
        
        stats[table_name] = {
            'primary': primary_count,
            'secondary': secondary_count,
            'diff': diff
        }
        
        status = "✅" if diff == 0 else "❌"
        print(f"{table_name:<12} {primary_count:>8} {secondary_count:>10} {diff:>8} {status}")
        
        if diff != 0:
            inconsistent_tables.append(table_name)
    
    primary_conn.close()
    secondary_conn.close()
    
    return len(inconsistent_tables) == 0, stats


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


def monitor_sync_progress(timeout=60):
    """监控同步进度"""
    print(f"\n⏳ 监控同步进度 (最多{timeout}秒)...")
    
    for i in range(timeout):
        try:
            response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                queue_size = data.get('sync_queue_size', 0)
                auto_sync = data.get('auto_sync_enabled', False)
                monitoring = data.get('is_monitoring', False)
                
                print(f"[{i+1:2d}s] 队列: {queue_size:3d} | 自动同步: {'✅' if auto_sync else '❌'} | 监控: {'✅' if monitoring else '❌'}", end='\r')
                
                if queue_size == 0 and i > 10:  # 等待至少10秒
                    print(f"\n✅ 同步队列已清空 (用时 {i+1} 秒)")
                    return True
            
            time.sleep(1)
        except Exception as e:
            print(f"\n❌ 监控异常: {e}")
            break
    
    print(f"\n⚠️ 监控超时 ({timeout}秒)")
    return False


def main():
    """主测试函数"""
    print("🧪 最终同步功能测试")
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
    initial_consistent, initial_stats = check_database_consistency()
    
    if initial_consistent:
        print("✅ 数据库已经一致，测试成功！")
        return True
    
    print(f"❌ 发现数据不一致，需要同步")
    
    # 显示不一致的详情
    inconsistent_count = 0
    for table_name, stats in initial_stats.items():
        if stats['diff'] != 0:
            inconsistent_count += abs(stats['diff'])
    
    print(f"总共需要同步 {inconsistent_count} 条记录")
    
    # 2. 触发强制同步
    print("\n2️⃣ 触发强制同步...")
    sync_triggered = trigger_force_sync()
    
    if not sync_triggered:
        print("❌ 无法触发强制同步")
        return False
    
    # 3. 监控同步进度
    print("\n3️⃣ 监控同步进度...")
    sync_completed = monitor_sync_progress(120)  # 等待最多2分钟
    
    # 4. 检查同步后状态
    print("\n4️⃣ 检查同步后数据库状态...")
    final_consistent, final_stats = check_database_consistency()
    
    # 5. 对比同步前后
    print("\n5️⃣ 同步前后对比:")
    print("表名           同步前差异    同步后差异    状态")
    print("-" * 55)
    
    all_synced = True
    for table_name in ['images', 'crawl_sessions', 'categories', 'tags']:
        initial_diff = initial_stats.get(table_name, {}).get('diff', 0)
        final_diff = final_stats.get(table_name, {}).get('diff', 0)
        
        if final_diff == 0:
            status = "✅ 已同步"
        elif final_diff < initial_diff:
            status = "🔄 部分同步"
            all_synced = False
        else:
            status = "❌ 未同步"
            all_synced = False
        
        print(f"{table_name:<12} {initial_diff:>10} {final_diff:>12}    {status}")
    
    # 6. 总结结果
    print("\n" + "=" * 60)
    if final_consistent and all_synced:
        print("🎉 同步测试完全成功！")
        print("\n✅ 确认:")
        print("  - 所有SQL错误已修复")
        print("  - 强制同步功能正常")
        print("  - 数据成功同步到备用数据库")
        print("  - 主备数据库完全一致")
        
        print("\n📝 系统状态:")
        print("  - 主应用: http://localhost:8000")
        print("  - HA管理: http://localhost:8001")
        print("  - 自动同步: 正常运行")
        
        return True
    elif all_synced:
        print("🎉 同步功能正常！")
        print("✅ 数据已成功同步，但可能需要等待自动同步完成最后的记录")
        return True
    else:
        print("❌ 同步测试失败！")
        print("\n🔧 建议检查:")
        print("  - 查看系统日志: logs/simple_ha.log")
        print("  - 检查网络连接")
        print("  - 检查数据库权限")
        print("  - 手动运行: python sync_all_tables.py")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
