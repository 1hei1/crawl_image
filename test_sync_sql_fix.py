#!/usr/bin/env python3
"""
测试SQL修复效果

验证SQLAlchemy text()修复是否解决了同步问题
"""

import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def check_sync_status():
    """检查同步状态"""
    try:
        response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"❌ 获取同步状态失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 检查同步状态异常: {e}")
        return None


def trigger_force_sync():
    """触发强制同步"""
    print("🔄 触发强制同步...")
    
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


def monitor_sync_progress():
    """监控同步进度"""
    print("\n⏳ 监控同步进度...")
    
    for i in range(60):  # 监控60秒
        sync_status = check_sync_status()
        if sync_status:
            queue_size = sync_status.get('sync_queue_size', 0)
            auto_sync = sync_status.get('auto_sync_enabled', False)
            monitoring = sync_status.get('is_monitoring', False)
            
            print(f"[{i+1:2d}s] 队列: {queue_size:3d} | 自动同步: {'✅' if auto_sync else '❌'} | 监控: {'✅' if monitoring else '❌'}", end='\r')
            
            if queue_size == 0 and i > 10:  # 等待至少10秒
                print(f"\n✅ 同步队列已清空 (用时 {i+1} 秒)")
                break
        
        time.sleep(1)
    else:
        print(f"\n⚠️ 监控超时 (60秒)")


def check_ha_status():
    """检查HA状态"""
    print("\n🏗️ 检查HA集群状态...")
    
    try:
        response = requests.get("http://localhost:8000/api/ha-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ha_enabled'):
                print("✅ HA功能已启用")
                
                nodes = data.get('nodes', {})
                print(f"节点数量: {len(nodes)}")
                
                for node_name, node_info in nodes.items():
                    role = node_info.get('role', 'unknown')
                    health = node_info.get('health_status', 'unknown')
                    print(f"  {node_name}: {role} - {health}")
                
                return True
            else:
                print("❌ HA功能未启用")
                return False
        else:
            print(f"❌ 获取HA状态失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 检查HA状态异常: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 测试SQL修复效果")
    print("=" * 50)
    
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
    
    # 1. 检查HA状态
    ha_ok = check_ha_status()
    if not ha_ok:
        print("❌ HA系统状态异常")
        return False
    
    # 2. 检查初始同步状态
    print("\n📊 检查初始同步状态...")
    initial_status = check_sync_status()
    if initial_status:
        print(f"初始队列大小: {initial_status.get('sync_queue_size', 0)}")
        print(f"自动同步: {'启用' if initial_status.get('auto_sync_enabled') else '禁用'}")
        print(f"监控状态: {'运行中' if initial_status.get('is_monitoring') else '已停止'}")
    
    # 3. 触发强制同步
    print("\n🚀 触发强制同步...")
    sync_triggered = trigger_force_sync()
    
    if not sync_triggered:
        print("❌ 无法触发强制同步")
        return False
    
    # 4. 监控同步进度
    monitor_sync_progress()
    
    # 5. 检查最终状态
    print("\n📋 检查最终同步状态...")
    final_status = check_sync_status()
    if final_status:
        final_queue = final_status.get('sync_queue_size', 0)
        print(f"最终队列大小: {final_queue}")
        
        if final_queue == 0:
            print("✅ 同步队列已清空")
        else:
            print(f"⚠️ 同步队列仍有 {final_queue} 个操作")
    
    # 6. 总结结果
    print("\n" + "=" * 50)
    print("📋 测试结果总结:")
    
    if final_status and final_status.get('sync_queue_size', 0) == 0:
        print("🎉 SQL修复成功！")
        print("\n✅ 确认:")
        print("  - SQLAlchemy text() 修复生效")
        print("  - 强制同步功能正常")
        print("  - 同步队列处理正常")
        
        print("\n📝 建议:")
        print("  - 继续观察系统日志确认同步正常")
        print("  - 检查数据库一致性: python check_db_consistency.py")
        
        return True
    else:
        print("❌ 可能仍有问题需要解决")
        print("\n🔧 建议检查:")
        print("  - 查看系统日志: logs/simple_ha.log")
        print("  - 检查是否还有其他SQL错误")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
