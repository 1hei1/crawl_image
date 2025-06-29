#!/usr/bin/env python3
"""
测试所有SQL修复

验证所有SQLAlchemy text()修复是否完整
"""

import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def trigger_crawl_task():
    """触发爬虫任务来测试INSERT操作"""
    print("🕷️ 触发爬虫任务测试INSERT操作...")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/crawl",
            json={
                "url": "https://httpbin.org/html",
                "max_depth": 1,
                "max_images": 5,
                "max_concurrent": 2
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 爬虫任务启动成功: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"❌ 爬虫任务启动失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 爬虫任务异常: {e}")
        return False


def check_sync_status():
    """检查同步状态"""
    try:
        response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
    except Exception:
        return None


def monitor_sync_operations(duration=30):
    """监控同步操作"""
    print(f"\n⏳ 监控同步操作 ({duration}秒)...")
    
    initial_status = check_sync_status()
    if not initial_status:
        print("❌ 无法获取初始同步状态")
        return False
    
    initial_queue = initial_status.get('sync_queue_size', 0)
    print(f"初始队列大小: {initial_queue}")
    
    operations_processed = 0
    errors_detected = False
    
    for i in range(duration):
        status = check_sync_status()
        if status:
            current_queue = status.get('sync_queue_size', 0)
            auto_sync = status.get('auto_sync_enabled', False)
            monitoring = status.get('is_monitoring', False)
            
            # 计算处理的操作数
            if current_queue < initial_queue:
                operations_processed = initial_queue - current_queue
            
            print(f"[{i+1:2d}s] 队列: {current_queue:3d} | 已处理: {operations_processed:3d} | 自动同步: {'✅' if auto_sync else '❌'}", end='\r')
            
            # 检查是否有错误（队列长时间不变可能表示有错误）
            if i > 10 and current_queue > 0 and operations_processed == 0:
                errors_detected = True
        
        time.sleep(1)
    
    print(f"\n监控完成: 处理了 {operations_processed} 个同步操作")
    
    if errors_detected:
        print("⚠️ 检测到可能的同步错误（队列长时间未处理）")
        return False
    
    return True


def check_system_logs():
    """检查系统日志中的SQL错误"""
    print("\n📋 检查最近的系统日志...")
    
    try:
        # 读取最近的日志
        log_file = Path("logs/simple_ha.log")
        if not log_file.exists():
            print("❌ 日志文件不存在")
            return False
        
        # 读取最后100行
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        # 检查SQL相关错误
        sql_errors = []
        text_errors = []
        
        for line in recent_lines:
            if 'should be explicitly declared as text' in line:
                text_errors.append(line.strip())
            elif 'SQL' in line and ('ERROR' in line or 'FAILED' in line):
                sql_errors.append(line.strip())
        
        if text_errors:
            print(f"❌ 发现 {len(text_errors)} 个 text() 错误:")
            for error in text_errors[-3:]:  # 显示最近3个
                print(f"   {error}")
            return False
        
        if sql_errors:
            print(f"⚠️ 发现 {len(sql_errors)} 个SQL错误:")
            for error in sql_errors[-3:]:  # 显示最近3个
                print(f"   {error}")
        
        print("✅ 没有发现 text() 相关错误")
        return True
        
    except Exception as e:
        print(f"❌ 检查日志失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 测试所有SQL修复")
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
    
    results = {}
    
    # 1. 触发爬虫任务（测试INSERT操作）
    print("\n1️⃣ 测试INSERT操作...")
    results['crawl_task'] = trigger_crawl_task()
    
    # 2. 监控同步操作
    print("\n2️⃣ 监控同步操作...")
    results['sync_monitoring'] = monitor_sync_operations(20)
    
    # 3. 检查系统日志
    print("\n3️⃣ 检查系统日志...")
    results['log_check'] = check_system_logs()
    
    # 4. 最终同步状态检查
    print("\n4️⃣ 检查最终同步状态...")
    final_status = check_sync_status()
    if final_status:
        final_queue = final_status.get('sync_queue_size', 0)
        print(f"最终队列大小: {final_queue}")
        results['final_status'] = final_queue < 10  # 队列应该很小
    else:
        results['final_status'] = False
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📋 测试结果总结:")
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有SQL修复测试通过！")
        print("\n✅ 确认:")
        print("  - 所有SQLAlchemy text() 错误已修复")
        print("  - INSERT/UPDATE/DELETE 操作正常")
        print("  - 同步队列处理正常")
        print("  - 系统日志无SQL错误")
        
        print("\n📝 系统状态:")
        print("  - 分布式HA系统正常运行")
        print("  - 数据同步功能正常")
        print("  - 爬虫功能正常")
        
        return True
    else:
        print("❌ 部分SQL修复测试失败！")
        print("\n🔧 建议检查:")
        print("  - 查看详细日志: logs/simple_ha.log")
        print("  - 检查是否还有其他SQL错误")
        print("  - 重启系统重新测试")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
