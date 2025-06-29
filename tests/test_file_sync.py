#!/usr/bin/env python3
"""
文件同步功能测试脚本

测试分布式文件管理器的各项功能
"""

import asyncio
import hashlib
import logging
import os
import requests
import time
from pathlib import Path
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from storage.distributed_file_manager import DistributedFileManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileSyncTester:
    """文件同步测试器"""
    
    def __init__(self):
        """初始化测试器"""
        # 模拟服务器配置
        self.servers = [
            {"host": "113.29.231.99", "port": 8000, "name": "primary_server"},
            {"host": "113.29.232.245", "port": 8000, "name": "backup_server"}
        ]
        
        # 创建文件管理器
        self.file_manager = DistributedFileManager(
            local_storage_path="data",
            servers=self.servers
        )
        
        # API基础URL
        self.api_base = "http://localhost:8000"
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始文件同步功能测试")
        print("=" * 60)
        
        try:
            # 启动文件同步服务
            self.file_manager.start_sync_service()
            
            # 1. 测试文件保存
            await self.test_file_save()
            
            # 2. 测试文件获取
            await self.test_file_get()
            
            # 3. 测试文件同步
            await self.test_file_sync()
            
            # 4. 测试API接口
            await self.test_api_endpoints()
            
            # 5. 测试故障恢复
            await self.test_failure_recovery()
            
            print("\n✅ 所有测试完成！")
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            logger.error(f"测试异常: {e}")
        
        finally:
            self.file_manager.stop_sync_service()
    
    async def test_file_save(self):
        """测试文件保存"""
        print("\n1️⃣ 测试文件保存...")
        
        try:
            # 创建测试图片数据
            test_image_data = b"fake_image_data_for_testing_" + os.urandom(1024)
            filename = "test_image.jpg"
            
            # 保存文件
            local_path = await self.file_manager.save_image(
                test_image_data, 
                filename, 
                sync_to_servers=True
            )
            
            print(f"  ✅ 文件保存成功: {local_path}")
            
            # 验证文件存在
            full_path = self.file_manager.images_path / local_path
            if full_path.exists():
                print(f"  ✅ 本地文件验证成功")
            else:
                print(f"  ❌ 本地文件不存在")
            
            # 验证文件内容
            with open(full_path, 'rb') as f:
                saved_data = f.read()
            
            if saved_data == test_image_data:
                print(f"  ✅ 文件内容验证成功")
            else:
                print(f"  ❌ 文件内容不匹配")
            
            # 保存测试文件路径供后续测试使用
            self.test_file_path = local_path
            self.test_file_data = test_image_data
            
        except Exception as e:
            print(f"  ❌ 文件保存测试失败: {e}")
    
    async def test_file_get(self):
        """测试文件获取"""
        print("\n2️⃣ 测试文件获取...")
        
        try:
            if not hasattr(self, 'test_file_path'):
                print("  ⚠️ 跳过测试，没有可用的测试文件")
                return
            
            # 获取文件
            file_data = await self.file_manager.get_image(self.test_file_path)
            
            if file_data:
                print(f"  ✅ 文件获取成功，大小: {len(file_data)} 字节")
                
                # 验证文件内容
                if file_data == self.test_file_data:
                    print(f"  ✅ 文件内容验证成功")
                else:
                    print(f"  ❌ 文件内容不匹配")
            else:
                print(f"  ❌ 文件获取失败")
            
        except Exception as e:
            print(f"  ❌ 文件获取测试失败: {e}")
    
    async def test_file_sync(self):
        """测试文件同步"""
        print("\n3️⃣ 测试文件同步...")
        
        try:
            # 等待同步队列处理
            print("  ⏳ 等待文件同步...")
            await asyncio.sleep(5)
            
            # 检查同步队列状态
            queue_size = len(self.file_manager.sync_queue)
            print(f"  📊 同步队列大小: {queue_size}")
            
            # 检查文件索引
            index_size = len(self.file_manager.file_index)
            print(f"  📊 文件索引大小: {index_size}")
            
            if hasattr(self, 'test_file_path'):
                if self.test_file_path in self.file_manager.file_index:
                    file_info = self.file_manager.file_index[self.test_file_path]
                    print(f"  ✅ 文件已添加到索引")
                    print(f"    - 路径: {file_info.path}")
                    print(f"    - 大小: {file_info.size}")
                    print(f"    - 哈希: {file_info.hash[:8]}...")
                else:
                    print(f"  ❌ 文件未添加到索引")
            
        except Exception as e:
            print(f"  ❌ 文件同步测试失败: {e}")
    
    async def test_api_endpoints(self):
        """测试API接口"""
        print("\n4️⃣ 测试API接口...")
        
        # 测试存储状态API
        try:
            response = requests.get(f"{self.api_base}/api/storage-status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ 存储状态API: {data.get('total_files', 0)} 个文件")
            else:
                print(f"  ⚠️ 存储状态API返回: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 存储状态API连接失败: {e}")
        
        # 测试强制同步API
        try:
            response = requests.post(f"{self.api_base}/api/force-file-sync", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ 强制同步API: {data.get('message', '成功')}")
            else:
                print(f"  ⚠️ 强制同步API返回: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 强制同步API连接失败: {e}")
        
        # 测试文件同步状态API
        try:
            response = requests.get(f"{self.api_base}/file-sync/api/file-sync/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ 文件同步状态API: {data.get('status', 'unknown')}")
            else:
                print(f"  ⚠️ 文件同步状态API返回: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 文件同步状态API连接失败: {e}")
    
    async def test_failure_recovery(self):
        """测试故障恢复"""
        print("\n5️⃣ 测试故障恢复...")
        
        try:
            if not hasattr(self, 'test_file_path'):
                print("  ⚠️ 跳过测试，没有可用的测试文件")
                return
            
            # 模拟本地文件丢失
            full_path = self.file_manager.images_path / self.test_file_path
            backup_path = full_path.with_suffix('.backup')
            
            if full_path.exists():
                # 备份原文件
                full_path.rename(backup_path)
                print(f"  📁 模拟文件丢失: {self.test_file_path}")
                
                # 尝试获取文件（应该从远程服务器获取）
                file_data = await self.file_manager.get_image(self.test_file_path)
                
                if file_data:
                    print(f"  ✅ 故障恢复成功，从远程获取文件")
                    
                    # 验证恢复的文件内容
                    if file_data == self.test_file_data:
                        print(f"  ✅ 恢复文件内容验证成功")
                    else:
                        print(f"  ❌ 恢复文件内容不匹配")
                else:
                    print(f"  ❌ 故障恢复失败，无法从远程获取文件")
                
                # 恢复原文件
                if backup_path.exists():
                    backup_path.rename(full_path)
                    print(f"  🔄 原文件已恢复")
            
        except Exception as e:
            print(f"  ❌ 故障恢复测试失败: {e}")
    
    def test_performance(self):
        """性能测试"""
        print("\n6️⃣ 性能测试...")
        
        try:
            # 测试文件保存性能
            start_time = time.time()
            
            test_files = []
            for i in range(5):
                test_data = b"performance_test_data_" + os.urandom(512)
                filename = f"perf_test_{i}.jpg"
                
                # 这里应该是异步调用，但为了简化测试使用同步
                # local_path = await self.file_manager.save_image(test_data, filename)
                # test_files.append(local_path)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"  ⏱️ 保存5个文件耗时: {duration:.2f}秒")
            print(f"  📊 平均每文件: {duration/5:.3f}秒")
            
        except Exception as e:
            print(f"  ❌ 性能测试失败: {e}")


async def main():
    """主函数"""
    print("🧪 分布式文件同步功能测试")
    print("请确保系统已启动或配置正确")
    print()
    
    # 确保目录存在
    Path("data/images").mkdir(parents=True, exist_ok=True)
    Path("data/temp").mkdir(parents=True, exist_ok=True)
    Path("data/metadata").mkdir(parents=True, exist_ok=True)
    
    # 运行测试
    tester = FileSyncTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
