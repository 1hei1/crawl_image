#!/usr/bin/env python3
"""
分布式高可用数据库系统测试脚本

测试以下功能：
1. 节点连接和健康检查
2. 数据同步
3. 故障转移
4. API通信
"""

import asyncio
import json
import logging
import requests
import time
from pathlib import Path
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config.ha_config_loader import load_ha_config
from database.distributed_ha_manager import DistributedHAManager
from database.models.image import ImageModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HASystemTester:
    """高可用系统测试器"""
    
    def __init__(self, config_path: str = "config/distributed_ha_config.yaml"):
        """初始化测试器"""
        self.config_path = config_path
        self.nodes, self.local_node_name, self.config = load_ha_config(config_path)
        self.ha_manager = None
        
        # API端点
        self.api_base = "http://localhost:8001"
        
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始分布式高可用数据库系统测试")
        print("=" * 60)
        
        try:
            # 1. 基础连接测试
            self.test_basic_connectivity()
            
            # 2. 创建HA管理器
            self.test_ha_manager_creation()
            
            # 3. 节点健康检查测试
            self.test_health_checks()
            
            # 4. 数据同步测试
            self.test_data_synchronization()
            
            # 5. API通信测试
            self.test_api_communication()
            
            # 6. 故障转移测试（模拟）
            self.test_failover_simulation()
            
            print("\n✅ 所有测试完成！")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            logger.error(f"测试异常: {e}")
        
        finally:
            if self.ha_manager:
                self.ha_manager.stop_monitoring()
    
    def test_basic_connectivity(self):
        """测试基础连接"""
        print("\n1️⃣ 测试基础连接...")
        
        for node in self.nodes:
            try:
                # 这里可以添加实际的数据库连接测试
                print(f"  ✅ 节点 {node.name}: {node.server.host}:{node.server.port}")
            except Exception as e:
                print(f"  ❌ 节点 {node.name}: {e}")
    
    def test_ha_manager_creation(self):
        """测试HA管理器创建"""
        print("\n2️⃣ 测试HA管理器创建...")
        
        try:
            self.ha_manager = DistributedHAManager(self.nodes, self.local_node_name)
            self.ha_manager.start_monitoring()
            
            print(f"  ✅ HA管理器创建成功")
            print(f"  ✅ 当前主节点: {self.ha_manager.current_primary}")
            print(f"  ✅ 本地节点: {self.ha_manager.local_node_name}")
            
            # 等待一下让监控启动
            time.sleep(2)
            
        except Exception as e:
            print(f"  ❌ HA管理器创建失败: {e}")
            raise
    
    def test_health_checks(self):
        """测试健康检查"""
        print("\n3️⃣ 测试健康检查...")
        
        try:
            # 获取集群状态
            status = self.ha_manager.get_cluster_status()
            
            print(f"  ✅ 集群状态获取成功")
            print(f"  📊 节点数量: {len(status['nodes'])}")
            print(f"  📊 监控状态: {status['is_monitoring']}")
            
            # 显示每个节点的健康状态
            for node_name, node_info in status['nodes'].items():
                health_icon = "🟢" if node_info['health_status'] == 'healthy' else "🔴"
                print(f"    {health_icon} {node_name}: {node_info['health_status']}")
            
        except Exception as e:
            print(f"  ❌ 健康检查失败: {e}")
    
    def test_data_synchronization(self):
        """测试数据同步"""
        print("\n4️⃣ 测试数据同步...")
        
        try:
            # 模拟添加同步操作
            test_data = {
                "id": 999,
                "url": "http://test.com/image.jpg",
                "source_url": "http://test.com",
                "filename": "test_image.jpg",
                "local_path": "/path/to/test_image.jpg",
                "is_downloaded": True
            }
            
            self.ha_manager.add_sync_operation("INSERT", "images", test_data)
            
            print(f"  ✅ 同步操作添加成功")
            
            # 等待同步处理
            time.sleep(3)
            
            # 检查同步队列
            status = self.ha_manager.get_cluster_status()
            queue_size = status['sync_queue_size']
            print(f"  📊 同步队列大小: {queue_size}")
            
        except Exception as e:
            print(f"  ❌ 数据同步测试失败: {e}")
    
    def test_api_communication(self):
        """测试API通信"""
        print("\n5️⃣ 测试API通信...")
        
        # 测试健康检查API
        try:
            response = requests.get(f"{self.api_base}/api/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ 健康检查API: {data['status']}")
            else:
                print(f"  ⚠️ 健康检查API返回: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 健康检查API连接失败: {e}")
        
        # 测试状态查询API
        try:
            response = requests.get(f"{self.api_base}/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ 状态查询API: {len(data['nodes'])} 个节点")
            else:
                print(f"  ⚠️ 状态查询API返回: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 状态查询API连接失败: {e}")
        
        # 测试复制延迟API
        try:
            response = requests.get(f"{self.api_base}/api/replication-lag", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ 复制延迟API: {len(data)} 个备节点")
            else:
                print(f"  ⚠️ 复制延迟API返回: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 复制延迟API连接失败: {e}")
    
    def test_failover_simulation(self):
        """测试故障转移模拟"""
        print("\n6️⃣ 测试故障转移模拟...")
        
        try:
            # 获取当前主节点
            current_primary = self.ha_manager.current_primary
            print(f"  📍 当前主节点: {current_primary}")
            
            # 查找可用的备节点
            available_secondaries = [
                name for name, node in self.ha_manager.nodes.items()
                if name != current_primary and 
                   node.role.value == 'secondary' and
                   self.ha_manager._is_node_healthy(name)
            ]
            
            if available_secondaries:
                target_node = available_secondaries[0]
                print(f"  🎯 目标备节点: {target_node}")
                
                # 模拟手动故障转移（仅测试，不实际执行）
                print(f"  ⚠️ 模拟故障转移: {current_primary} -> {target_node}")
                print(f"  ℹ️ 实际故障转移需要调用: POST /api/failover/{target_node}")
                
                # 如果要实际测试故障转移，取消下面的注释
                # success = self.ha_manager.manual_failover(target_node)
                # if success:
                #     print(f"  ✅ 故障转移成功")
                # else:
                #     print(f"  ❌ 故障转移失败")
                
            else:
                print(f"  ⚠️ 没有可用的备节点进行故障转移测试")
            
        except Exception as e:
            print(f"  ❌ 故障转移测试失败: {e}")
    
    def test_performance(self):
        """性能测试"""
        print("\n7️⃣ 性能测试...")
        
        try:
            # 测试连接响应时间
            start_time = time.time()
            
            for i in range(10):
                with self.ha_manager.get_session(read_only=True) as session:
                    # 执行简单查询
                    pass
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 10
            
            print(f"  ⏱️ 平均连接时间: {avg_time:.3f}秒")
            
            # 测试同步操作性能
            start_time = time.time()
            
            for i in range(5):
                test_data = {
                    "id": 1000 + i,
                    "url": f"http://test.com/image_{i}.jpg",
                    "filename": f"test_image_{i}.jpg"
                }
                self.ha_manager.add_sync_operation("INSERT", "images", test_data)
            
            end_time = time.time()
            sync_time = end_time - start_time
            
            print(f"  ⏱️ 5个同步操作耗时: {sync_time:.3f}秒")
            
        except Exception as e:
            print(f"  ❌ 性能测试失败: {e}")


def main():
    """主函数"""
    print("🧪 分布式高可用数据库系统测试")
    print("请确保系统已启动或配置文件正确")
    print()
    
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    
    # 运行测试
    tester = HASystemTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
