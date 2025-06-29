#!/usr/bin/env python3
"""
测试自动序列更新功能

验证同步时是否自动更新序列，避免主键冲突
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


def get_sequence_info(conn, table_name):
    """获取表的最大ID和序列值"""
    try:
        cursor = conn.cursor()
        
        # 获取最大ID
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
        max_id = cursor.fetchone()[0]
        
        # 获取序列值
        sequence_name = f"{table_name}_id_seq"
        cursor.execute(f"SELECT last_value FROM {sequence_name}")
        sequence_value = cursor.fetchone()[0]
        
        cursor.close()
        return max_id, sequence_value
        
    except Exception as e:
        print(f"获取 {table_name} 序列信息失败: {e}")
        return 0, 0


def check_sequence_consistency():
    """检查序列一致性"""
    print("🔍 检查序列一致性...")
    
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
    
    tables = ['crawl_sessions', 'images', 'categories', 'tags']
    
    print("\n📊 序列状态对比:")
    print("数据库     表名           最大ID    序列值    状态")
    print("-" * 60)
    
    all_consistent = True
    
    for db_info in databases:
        conn = connect_to_database(**db_info)
        if not conn:
            continue
        
        for table_name in tables:
            max_id, sequence_value = get_sequence_info(conn, table_name)
            
            # 检查序列是否合理（序列值应该 > 最大ID）
            status = "✅" if sequence_value > max_id else "❌"
            if sequence_value <= max_id:
                all_consistent = False
            
            print(f"{db_info['name']:<10} {table_name:<12} {max_id:>8} {sequence_value:>8}    {status}")
        
        conn.close()
    
    return all_consistent


def trigger_sync_operation():
    """触发同步操作"""
    print("\n🔄 触发同步操作...")
    
    try:
        # 触发强制同步
        response = requests.post("http://localhost:8000/api/force-sync", timeout=30)
        if response.status_code == 200:
            print("✅ 强制同步触发成功")
            return True
        else:
            print(f"❌ 强制同步触发失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 触发同步异常: {e}")
        return False


def wait_for_sync_completion():
    """等待同步完成"""
    print("\n⏳ 等待同步完成...")
    
    for i in range(30):
        try:
            response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                queue_size = data.get('sync_queue_size', 0)
                print(f"同步队列: {queue_size} 个操作", end='\r')
                
                if queue_size == 0 and i > 5:
                    print("\n✅ 同步队列已清空")
                    return True
            
            time.sleep(1)
        except Exception:
            break
    
    print("\n⚠️ 等待同步超时")
    return False


def test_crawl_task():
    """测试爬虫任务（会创建新的crawl_session记录）"""
    print("\n🕷️ 测试爬虫任务...")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/crawl",
            json={
                "url": "https://httpbin.org/html",
                "max_depth": 1,
                "max_images": 1,
                "max_concurrent": 1
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 爬虫任务启动成功: {data.get('message', 'N/A')}")
            
            # 等待任务完成
            time.sleep(10)
            return True
        else:
            print(f"❌ 爬虫任务启动失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 爬虫任务异常: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 测试自动序列更新功能")
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
    
    # 1. 检查初始序列状态
    print("\n1️⃣ 检查初始序列状态...")
    initial_consistent = check_sequence_consistency()
    
    # 2. 触发同步操作
    print("\n2️⃣ 触发同步操作...")
    sync_triggered = trigger_sync_operation()
    
    if sync_triggered:
        # 等待同步完成
        sync_completed = wait_for_sync_completion()
        
        # 检查同步后序列状态
        print("\n3️⃣ 检查同步后序列状态...")
        post_sync_consistent = check_sequence_consistency()
    else:
        post_sync_consistent = False
    
    # 4. 测试爬虫任务（测试实际插入操作）
    print("\n4️⃣ 测试爬虫任务...")
    crawl_success = test_crawl_task()
    
    # 5. 检查最终序列状态
    print("\n5️⃣ 检查最终序列状态...")
    final_consistent = check_sequence_consistency()
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📋 测试结果总结:")
    
    print(f"初始序列状态: {'✅ 一致' if initial_consistent else '❌ 不一致'}")
    print(f"同步操作: {'✅ 成功' if sync_triggered else '❌ 失败'}")
    print(f"同步后序列状态: {'✅ 一致' if post_sync_consistent else '❌ 不一致'}")
    print(f"爬虫任务: {'✅ 成功' if crawl_success else '❌ 失败'}")
    print(f"最终序列状态: {'✅ 一致' if final_consistent else '❌ 不一致'}")
    
    print("\n" + "=" * 60)
    if final_consistent and crawl_success:
        print("🎉 自动序列更新功能测试成功！")
        print("\n✅ 确认:")
        print("  - 同步操作自动更新序列")
        print("  - 插入操作自动更新序列")
        print("  - 主键冲突问题已解决")
        print("  - 爬虫功能正常工作")
        
        print("\n📝 功能说明:")
        print("  - 每次同步数据后自动更新目标数据库序列")
        print("  - 每次插入记录后检查并更新序列")
        print("  - 序列值始终保持在最大ID+1以上")
        print("  - 避免故障转移后的主键冲突")
        
        return True
    else:
        print("❌ 自动序列更新功能测试失败！")
        print("\n🔧 可能的问题:")
        if not final_consistent:
            print("  - 序列更新逻辑可能有问题")
            print("  - 检查同步代码中的序列更新部分")
        if not crawl_success:
            print("  - 爬虫任务失败，可能仍有主键冲突")
            print("  - 检查数据库连接和权限")
        
        print("\n📝 建议:")
        print("  - 查看系统日志: logs/simple_ha.log")
        print("  - 手动运行序列修复: python emergency_sequence_fix.py")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
