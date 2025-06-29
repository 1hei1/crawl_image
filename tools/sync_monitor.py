#!/usr/bin/env python3
"""
数据同步监控工具

实时监控主备数据库之间的数据同步状态
"""

import sys
import time
import requests
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class SyncMonitor:
    """数据同步监控器"""
    
    def __init__(self, ha_api_url="http://localhost:8001", main_api_url="http://localhost:8000"):
        self.ha_api_url = ha_api_url
        self.main_api_url = main_api_url
    
    def get_sync_status(self):
        """获取同步状态"""
        try:
            response = requests.get(f"{self.ha_api_url}/api/sync-status", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"获取同步状态失败: {e}")
            return None
    
    def get_cluster_status(self):
        """获取集群状态"""
        try:
            response = requests.get(f"{self.ha_api_url}/api/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"获取集群状态失败: {e}")
            return None
    
    def force_sync(self):
        """强制执行全量同步"""
        try:
            response = requests.post(f"{self.main_api_url}/api/force-sync", timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"强制同步失败: {e}")
            return None
    
    def display_status(self):
        """显示当前状态"""
        print("\n" + "="*80)
        print(f"数据同步状态监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # 获取同步状态
        sync_status = self.get_sync_status()
        if sync_status:
            print("📊 同步状态:")
            print(f"  自动同步: {'✅ 启用' if sync_status.get('auto_sync_enabled') else '❌ 禁用'}")
            print(f"  同步队列: {sync_status.get('sync_queue_size', 0)} 个操作")
            print(f"  当前主节点: {sync_status.get('current_primary', 'N/A')}")
            print(f"  本地节点: {sync_status.get('local_node', 'N/A')}")
            print(f"  监控状态: {'🟢 运行中' if sync_status.get('is_monitoring') else '🔴 已停止'}")
            
            last_sync = sync_status.get('last_full_sync')
            if last_sync:
                last_sync_time = datetime.fromtimestamp(last_sync)
                print(f"  最后全量同步: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            sync_interval = sync_status.get('full_sync_interval', 300)
            print(f"  全量同步间隔: {sync_interval}秒 ({sync_interval//60}分钟)")
        else:
            print("❌ 无法获取同步状态")
        
        # 获取集群状态
        cluster_status = self.get_cluster_status()
        if cluster_status:
            print("\n🏗️ 集群状态:")
            nodes = cluster_status.get('nodes', {})
            for node_name, node_info in nodes.items():
                role = "主节点" if node_info.get('role') == 'primary' else "备节点"
                health = "健康" if node_info.get('health_status') == 'healthy' else "异常"
                server = node_info.get('server', {})
                
                print(f"  {role}: {node_name}")
                print(f"    状态: {health}")
                print(f"    地址: {server.get('host', 'N/A')}:{server.get('port', 'N/A')}")
                
                if node_info.get('replication_lag', 0) > 0:
                    print(f"    复制延迟: {node_info['replication_lag']:.2f}秒")
        else:
            print("❌ 无法获取集群状态")
        
        print("="*80)
    
    def monitor_continuous(self, interval=10):
        """持续监控"""
        print("🔄 开始持续监控数据同步状态...")
        print(f"监控间隔: {interval}秒")
        print("按 Ctrl+C 停止监控")
        
        try:
            while True:
                self.display_status()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n👋 监控已停止")
    
    def check_sync_health(self):
        """检查同步健康状态"""
        print("🔍 检查数据同步健康状态...")
        
        sync_status = self.get_sync_status()
        cluster_status = self.get_cluster_status()
        
        issues = []
        
        if not sync_status:
            issues.append("无法获取同步状态")
        else:
            if not sync_status.get('auto_sync_enabled'):
                issues.append("自动同步已禁用")
            
            if not sync_status.get('is_monitoring'):
                issues.append("监控服务未运行")
            
            queue_size = sync_status.get('sync_queue_size', 0)
            if queue_size > 100:
                issues.append(f"同步队列积压严重 ({queue_size} 个操作)")
        
        if not cluster_status:
            issues.append("无法获取集群状态")
        else:
            nodes = cluster_status.get('nodes', {})
            healthy_nodes = sum(1 for node in nodes.values() 
                              if node.get('health_status') == 'healthy')
            total_nodes = len(nodes)
            
            if healthy_nodes < total_nodes:
                issues.append(f"部分节点不健康 ({healthy_nodes}/{total_nodes})")
        
        if issues:
            print("⚠️ 发现以下问题:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ 数据同步状态正常")
            return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据同步监控工具")
    parser.add_argument("--ha-api", default="http://localhost:8001", 
                       help="HA API地址 (默认: http://localhost:8001)")
    parser.add_argument("--main-api", default="http://localhost:8000",
                       help="主API地址 (默认: http://localhost:8000)")
    parser.add_argument("--interval", type=int, default=10,
                       help="监控间隔(秒) (默认: 10)")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 状态命令
    subparsers.add_parser("status", help="显示当前状态")
    
    # 监控命令
    monitor_parser = subparsers.add_parser("monitor", help="持续监控")
    monitor_parser.add_argument("--interval", type=int, default=10,
                               help="监控间隔(秒)")
    
    # 健康检查命令
    subparsers.add_parser("health", help="检查同步健康状态")
    
    # 强制同步命令
    subparsers.add_parser("force-sync", help="强制执行全量同步")
    
    args = parser.parse_args()
    
    monitor = SyncMonitor(args.ha_api, args.main_api)
    
    if args.command == "status":
        monitor.display_status()
    elif args.command == "monitor":
        interval = getattr(args, 'interval', 10)
        monitor.monitor_continuous(interval)
    elif args.command == "health":
        healthy = monitor.check_sync_health()
        sys.exit(0 if healthy else 1)
    elif args.command == "force-sync":
        print("🔄 执行强制全量同步...")
        result = monitor.force_sync()
        if result:
            print("✅ 强制同步已启动")
            print(f"状态: {result.get('status')}")
            print(f"消息: {result.get('message')}")
        else:
            print("❌ 强制同步失败")
            sys.exit(1)
    else:
        # 默认显示状态
        monitor.display_status()


if __name__ == "__main__":
    main()
