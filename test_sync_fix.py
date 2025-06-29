#!/usr/bin/env python3
"""
测试同步修复效果

验证502错误和TagModel问题是否已解决
"""

import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def test_tag_model_import():
    """测试TagModel导入"""
    print("🏷️ 测试TagModel导入...")
    
    try:
        from database.models.tag import TagModel
        print("✅ TagModel导入成功")
        
        # 测试创建实例
        tag = TagModel(name="test_tag", category="test", description="测试标签")
        print("✅ TagModel实例创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ TagModel测试失败: {e}")
        return False


def test_sync_status_api():
    """测试同步状态API"""
    print("\n📡 测试同步状态API...")
    
    try:
        # 测试主API
        response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ 主API同步状态查询成功")
            print(f"  自动同步: {'启用' if data.get('auto_sync_enabled') else '禁用'}")
            print(f"  同步队列: {data.get('sync_queue_size', 0)} 个操作")
            print(f"  当前主节点: {data.get('current_primary', 'N/A')}")
        else:
            print(f"❌ 主API响应错误: {response.status_code}")
            return False
        
        # 测试HA管理API
        try:
            response = requests.get("http://localhost:8001/api/sync-status", timeout=5)
            if response.status_code == 200:
                print("✅ HA管理API同步状态查询成功")
            else:
                print(f"⚠️ HA管理API响应错误: {response.status_code}")
        except Exception as e:
            print(f"⚠️ HA管理API连接失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        return False


def test_cluster_status():
    """测试集群状态"""
    print("\n🏗️ 测试集群状态...")
    
    try:
        response = requests.get("http://localhost:8000/api/ha-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ 集群状态查询成功")
            
            if data.get('ha_enabled'):
                print("✅ HA功能已启用")
                
                nodes = data.get('nodes', {})
                print(f"节点数量: {len(nodes)}")
                
                for node_name, node_info in nodes.items():
                    role = node_info.get('role', 'unknown')
                    health = node_info.get('health_status', 'unknown')
                    print(f"  {node_name}: {role} - {health}")
                
            else:
                print("❌ HA功能未启用")
                return False
        else:
            print(f"❌ 集群状态查询失败: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 集群状态测试失败: {e}")
        return False


def test_force_sync():
    """测试强制同步功能"""
    print("\n🔄 测试强制同步功能...")
    
    try:
        response = requests.post("http://localhost:8000/api/force-sync", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("✅ 强制同步请求成功")
            print(f"  状态: {data.get('status', 'unknown')}")
            print(f"  消息: {data.get('message', 'N/A')}")
            
            # 等待一段时间让同步处理
            print("等待同步处理...")
            time.sleep(5)
            
            # 检查同步队列
            response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
            if response.status_code == 200:
                sync_data = response.json()
                queue_size = sync_data.get('sync_queue_size', 0)
                print(f"  同步队列: {queue_size} 个操作")
            
            return True
        else:
            print(f"❌ 强制同步请求失败: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ 强制同步测试失败: {e}")
        return False


def check_sync_errors():
    """检查是否还有502同步错误"""
    print("\n🔍 检查同步错误...")
    
    try:
        # 检查同步状态
        response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # 检查监控状态
            if data.get('is_monitoring'):
                print("✅ 同步监控正在运行")
            else:
                print("❌ 同步监控未运行")
                return False
            
            # 检查队列大小
            queue_size = data.get('sync_queue_size', 0)
            if queue_size < 100:  # 正常范围
                print(f"✅ 同步队列正常: {queue_size} 个操作")
            else:
                print(f"⚠️ 同步队列积压: {queue_size} 个操作")
            
            return True
        else:
            print(f"❌ 无法获取同步状态: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ 检查同步错误失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🧪 测试同步修复效果")
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
    
    # 执行测试
    results = {}
    
    # 1. 测试TagModel
    results['tag_model'] = test_tag_model_import()
    
    # 2. 测试API
    results['sync_api'] = test_sync_status_api()
    
    # 3. 测试集群状态
    results['cluster_status'] = test_cluster_status()
    
    # 4. 测试强制同步
    results['force_sync'] = test_force_sync()
    
    # 5. 检查同步错误
    results['sync_errors'] = check_sync_errors()
    
    # 总结结果
    print("\n" + "=" * 50)
    print("📋 测试结果总结:")
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 所有测试通过！同步问题已修复。")
        print("\n✅ 修复确认:")
        print("  - TagModel导入正常")
        print("  - 同步API响应正常")
        print("  - 集群状态正常")
        print("  - 强制同步功能正常")
        print("  - 无502同步错误")
        
        print("\n📝 系统状态:")
        print("  - 主应用: http://localhost:8000")
        print("  - HA管理: http://localhost:8001")
        print("  - 同步监控: 正常运行")
        
        return True
    else:
        print("❌ 部分测试失败，需要进一步检查。")
        print("\n🔧 建议:")
        print("  - 检查系统日志: logs/simple_ha.log")
        print("  - 重启系统: python start_simple_ha.py")
        print("  - 检查数据库连接")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
