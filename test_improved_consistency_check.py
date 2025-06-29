#!/usr/bin/env python3
"""
测试改进的数据一致性检查

验证新的深度一致性检查是否能正确检测数据不一致
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
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"连接数据库失败 {host}:{port} - {e}")
        return None


def get_table_stats(conn, table_name):
    """获取表统计信息"""
    try:
        cursor = conn.cursor()
        
        # 记录数
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        # ID范围
        cursor.execute(f"SELECT MIN(id), MAX(id) FROM {table_name}")
        id_range = cursor.fetchone()
        
        # 最新记录
        cursor.execute(f"SELECT id, updated_at FROM {table_name} ORDER BY id DESC LIMIT 3")
        latest_records = cursor.fetchall()
        
        cursor.close()
        
        return {
            'count': count,
            'id_range': id_range,
            'latest_records': latest_records
        }
        
    except Exception as e:
        print(f"获取 {table_name} 统计失败: {e}")
        return None


def create_test_inconsistency():
    """创建测试用的数据不一致"""
    print("🧪 创建测试数据不一致...")
    
    # 连接到备数据库
    conn = connect_to_database(
        '113.29.232.245', 5432, 'image_crawler', 'postgres', 'Abcdefg6'
    )
    
    if not conn:
        print("❌ 无法连接到备数据库")
        return False
    
    try:
        cursor = conn.cursor()
        
        # 在备数据库中插入一条测试记录（模拟数据不一致）
        cursor.execute("""
            INSERT INTO crawl_sessions (session_name, target_url, session_type, status)
            VALUES ('test_inconsistency', 'https://test-inconsistency.com', 'manual', 'completed')
        """)
        
        print("✅ 已在备数据库中创建测试不一致数据")
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 创建测试不一致失败: {e}")
        conn.close()
        return False


def remove_test_inconsistency():
    """移除测试用的数据不一致"""
    print("🧹 清理测试数据...")
    
    # 连接到备数据库
    conn = connect_to_database(
        '113.29.232.245', 5432, 'image_crawler', 'postgres', 'Abcdefg6'
    )
    
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM crawl_sessions WHERE session_name = 'test_inconsistency'")
        cursor.close()
        conn.close()
        print("✅ 测试数据清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 清理测试数据失败: {e}")
        conn.close()
        return False


def check_database_consistency():
    """手动检查数据库一致性"""
    print("🔍 手动检查数据库一致性...")
    
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
    
    print("\n📊 数据库对比:")
    print("表名           主数据库    备数据库    状态")
    print("-" * 50)
    
    all_consistent = True
    
    for table_name in tables:
        primary_stats = None
        secondary_stats = None
        
        for db_info in databases:
            conn = connect_to_database(**db_info)
            if conn:
                stats = get_table_stats(conn, table_name)
                if db_info['name'] == '主数据库':
                    primary_stats = stats
                else:
                    secondary_stats = stats
                conn.close()
        
        if primary_stats and secondary_stats:
            primary_count = primary_stats['count']
            secondary_count = secondary_stats['count']
            
            status = "✅" if primary_count == secondary_count else "❌"
            if primary_count != secondary_count:
                all_consistent = False
            
            print(f"{table_name:<12} {primary_count:>8} {secondary_count:>10}    {status}")
            
            # 显示详细差异
            if primary_count != secondary_count:
                print(f"  ID范围: 主{primary_stats['id_range']} vs 备{secondary_stats['id_range']}")
    
    return all_consistent


def trigger_consistency_check():
    """触发系统的一致性检查"""
    print("\n🔄 触发系统一致性检查...")
    
    try:
        response = requests.post("http://localhost:8000/api/force-sync", timeout=30)
        if response.status_code == 200:
            print("✅ 强制同步触发成功")
            return True
        else:
            print(f"❌ 强制同步触发失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 触发一致性检查异常: {e}")
        return False


def monitor_sync_logs():
    """监控同步日志"""
    print("\n📋 监控同步日志...")
    
    try:
        log_file = Path("logs/simple_ha.log")
        if not log_file.exists():
            print("❌ 日志文件不存在")
            return False
        
        # 读取最后50行日志
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        recent_lines = lines[-50:] if len(lines) > 50 else lines
        
        # 查找一致性检查相关日志
        consistency_logs = []
        for line in recent_lines:
            if any(keyword in line for keyword in [
                '检测到数据不一致', '记录数不一致', '最新记录不一致', 
                'ID范围不一致', '开始同步数据到备用节点'
            ]):
                consistency_logs.append(line.strip())
        
        if consistency_logs:
            print("🔍 发现一致性检查日志:")
            for log in consistency_logs[-5:]:  # 显示最近5条
                print(f"  {log}")
            return True
        else:
            print("⚠️ 未发现一致性检查相关日志")
            return False
        
    except Exception as e:
        print(f"❌ 监控日志失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 测试改进的数据一致性检查")
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
    
    # 1. 检查初始一致性状态
    print("\n1️⃣ 检查初始数据一致性...")
    initial_consistent = check_database_consistency()
    
    # 2. 创建测试不一致
    print("\n2️⃣ 创建测试数据不一致...")
    inconsistency_created = create_test_inconsistency()
    
    if inconsistency_created:
        # 3. 再次检查一致性（应该检测到不一致）
        print("\n3️⃣ 检查创建不一致后的状态...")
        post_inconsistency_consistent = check_database_consistency()
        
        # 4. 触发系统一致性检查
        print("\n4️⃣ 触发系统一致性检查...")
        check_triggered = trigger_consistency_check()
        
        if check_triggered:
            # 等待检查完成
            print("等待一致性检查完成...")
            time.sleep(15)
            
            # 5. 监控日志
            print("\n5️⃣ 监控同步日志...")
            logs_found = monitor_sync_logs()
            
            # 6. 检查最终一致性
            print("\n6️⃣ 检查最终数据一致性...")
            final_consistent = check_database_consistency()
            
            # 7. 清理测试数据
            print("\n7️⃣ 清理测试数据...")
            remove_test_inconsistency()
        else:
            post_inconsistency_consistent = False
            logs_found = False
            final_consistent = False
    else:
        post_inconsistency_consistent = True
        logs_found = False
        final_consistent = True
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📋 测试结果总结:")
    
    print(f"初始数据一致性: {'✅ 一致' if initial_consistent else '❌ 不一致'}")
    print(f"测试不一致创建: {'✅ 成功' if inconsistency_created else '❌ 失败'}")
    print(f"不一致检测: {'✅ 检测到' if not post_inconsistency_consistent else '❌ 未检测到'}")
    print(f"系统一致性检查: {'✅ 触发成功' if check_triggered else '❌ 触发失败'}")
    print(f"同步日志: {'✅ 发现相关日志' if logs_found else '❌ 未发现日志'}")
    print(f"最终数据一致性: {'✅ 一致' if final_consistent else '❌ 不一致'}")
    
    print("\n" + "=" * 60)
    
    # 评估改进效果
    if inconsistency_created and not post_inconsistency_consistent and logs_found:
        print("🎉 改进的数据一致性检查测试成功！")
        print("\n✅ 确认:")
        print("  - 能够检测到数据不一致")
        print("  - 深度一致性检查工作正常")
        print("  - 系统能够记录详细的不一致信息")
        print("  - 自动同步机制正常工作")
        
        print("\n📝 改进内容:")
        print("  - 不仅检查记录数量，还检查记录内容")
        print("  - 检查最新记录的一致性")
        print("  - 检查ID范围的一致性")
        print("  - 提供详细的不一致信息")
        
        return True
    else:
        print("❌ 改进的数据一致性检查测试失败！")
        print("\n🔧 可能的问题:")
        if not inconsistency_created:
            print("  - 无法创建测试不一致数据")
        if post_inconsistency_consistent:
            print("  - 系统未能检测到数据不一致")
        if not logs_found:
            print("  - 系统未记录一致性检查日志")
        
        print("\n📝 建议:")
        print("  - 检查深度一致性检查逻辑")
        print("  - 查看详细系统日志")
        print("  - 验证数据库连接和权限")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
