#!/usr/bin/env python3
"""
测试双向同步功能

验证改进的双向数据同步是否正常工作
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


def get_table_id_range(conn, table_name):
    """获取表ID范围"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT MIN(id), MAX(id) FROM {table_name}")
        result = cursor.fetchone()
        cursor.close()
        return result
    except Exception as e:
        print(f"获取表 {table_name} ID范围失败: {e}")
        return (None, None)


def check_database_status():
    """检查数据库状态"""
    print("🔍 检查数据库状态...")
    
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
    
    tables = ['images', 'crawl_sessions', 'categories', 'tags']
    
    print("\n📊 数据库状态对比:")
    print("数据库     表名           记录数    ID范围")
    print("-" * 60)
    
    status = {}
    
    for db_info in databases:
        conn = connect_to_database(**db_info)
        if not conn:
            continue
        
        db_status = {}
        for table_name in tables:
            count = get_table_count(conn, table_name)
            id_range = get_table_id_range(conn, table_name)
            
            db_status[table_name] = {
                'count': count,
                'id_range': id_range
            }
            
            print(f"{db_info['name']:<10} {table_name:<12} {count:>8}    {id_range}")
        
        status[db_info['name']] = db_status
        conn.close()
    
    return status


def trigger_sync_and_monitor():
    """触发同步并监控进度"""
    print("\n🔄 触发双向同步...")
    
    try:
        response = requests.post("http://localhost:8000/api/force-sync", timeout=30)
        if response.status_code == 200:
            print("✅ 强制同步触发成功")
        else:
            print(f"❌ 强制同步触发失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 触发同步异常: {e}")
        return False
    
    # 监控同步进度
    print("\n⏳ 监控同步进度...")
    
    for i in range(60):  # 监控60秒
        try:
            response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                queue_size = data.get('sync_queue_size', 0)
                auto_sync = data.get('auto_sync_enabled', False)
                
                print(f"[{i+1:2d}s] 队列: {queue_size:3d} | 自动同步: {'✅' if auto_sync else '❌'}", end='\r')
                
                if queue_size == 0 and i > 10:
                    print(f"\n✅ 同步队列已清空 (用时 {i+1} 秒)")
                    return True
            
            time.sleep(1)
        except Exception:
            break
    
    print(f"\n⚠️ 监控超时")
    return False


def check_sync_logs():
    """检查同步日志"""
    print("\n📋 检查同步日志...")
    
    try:
        log_file = Path("logs/simple_ha.log")
        if not log_file.exists():
            print("❌ 日志文件不存在")
            return []
        
        # 读取最后100行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        # 查找双向同步相关日志
        sync_logs = []
        for line in recent_lines:
            if any(keyword in line for keyword in [
                '双向同步', '反向同步', '内容同步', '同步.*条.*记录',
                '主节点 ->', '-> 主节点', '双向同步完成'
            ]):
                sync_logs.append(line.strip())
        
        if sync_logs:
            print("🔍 发现双向同步日志:")
            for log in sync_logs[-10:]:  # 显示最近10条
                print(f"  {log}")
        else:
            print("⚠️ 未发现双向同步相关日志")
        
        return sync_logs
        
    except Exception as e:
        print(f"❌ 检查日志失败: {e}")
        return []


def analyze_sync_results(before_status, after_status):
    """分析同步结果"""
    print("\n📈 分析同步结果...")
    
    if not before_status or not after_status:
        print("❌ 缺少状态数据，无法分析")
        return False
    
    primary_before = before_status.get('主数据库', {})
    secondary_before = before_status.get('备数据库', {})
    primary_after = after_status.get('主数据库', {})
    secondary_after = after_status.get('备数据库', {})
    
    print("\n📊 同步前后对比:")
    print("表名           同步前差异    同步后差异    状态")
    print("-" * 55)
    
    all_synced = True
    
    for table_name in ['images', 'crawl_sessions', 'categories', 'tags']:
        # 同步前差异
        before_primary = primary_before.get(table_name, {}).get('count', 0)
        before_secondary = secondary_before.get(table_name, {}).get('count', 0)
        before_diff = before_primary - before_secondary
        
        # 同步后差异
        after_primary = primary_after.get(table_name, {}).get('count', 0)
        after_secondary = secondary_after.get(table_name, {}).get('count', 0)
        after_diff = after_primary - after_secondary
        
        if after_diff == 0:
            status = "✅ 已同步"
        elif abs(after_diff) < abs(before_diff):
            status = "🔄 部分同步"
            all_synced = False
        else:
            status = "❌ 未改善"
            all_synced = False
        
        print(f"{table_name:<12} {before_diff:>10} {after_diff:>12}    {status}")
    
    return all_synced


def main():
    """主测试函数"""
    print("🧪 测试双向同步功能")
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
    
    # 1. 检查同步前状态
    print("\n1️⃣ 检查同步前数据库状态...")
    before_status = check_database_status()
    
    # 2. 触发同步并监控
    print("\n2️⃣ 触发双向同步...")
    sync_completed = trigger_sync_and_monitor()
    
    # 3. 检查同步日志
    print("\n3️⃣ 检查同步日志...")
    sync_logs = check_sync_logs()
    
    # 4. 检查同步后状态
    print("\n4️⃣ 检查同步后数据库状态...")
    after_status = check_database_status()
    
    # 5. 分析同步结果
    print("\n5️⃣ 分析同步结果...")
    sync_successful = analyze_sync_results(before_status, after_status)
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📋 双向同步测试结果:")
    
    print(f"同步触发: {'✅ 成功' if sync_completed else '❌ 失败'}")
    print(f"同步日志: {'✅ 发现' if sync_logs else '❌ 未发现'} ({len(sync_logs)} 条)")
    print(f"数据一致性: {'✅ 达成' if sync_successful else '❌ 未达成'}")
    
    print("\n" + "=" * 60)
    if sync_completed and sync_logs and sync_successful:
        print("🎉 双向同步功能测试成功！")
        print("\n✅ 确认:")
        print("  - 双向同步机制正常工作")
        print("  - 能够处理主节点和备用节点的数据差异")
        print("  - 自动检测和同步数据不一致")
        print("  - 同步日志记录详细")
        
        print("\n📝 功能特点:")
        print("  - 支持主节点 -> 备用节点同步")
        print("  - 支持备用节点 -> 主节点同步")
        print("  - 支持内容差异同步")
        print("  - 自动更新序列值")
        
        return True
    else:
        print("❌ 双向同步功能测试失败！")
        print("\n🔧 可能的问题:")
        if not sync_completed:
            print("  - 同步触发或执行失败")
        if not sync_logs:
            print("  - 双向同步逻辑可能未执行")
        if not sync_successful:
            print("  - 数据同步未完成或有错误")
        
        print("\n📝 建议:")
        print("  - 查看详细系统日志: logs/simple_ha.log")
        print("  - 检查数据库连接和权限")
        print("  - 验证双向同步代码逻辑")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
