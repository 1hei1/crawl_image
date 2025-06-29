#!/usr/bin/env python3
"""
快速验证自动同步功能

这个脚本用于快速验证主备数据库的自动同步功能是否正常工作
"""

import sys
import time
import requests
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel


def main():
    """主验证函数"""
    print("🔍 快速验证自动数据同步功能")
    print("=" * 50)
    
    try:
        # 1. 检查系统状态
        print("1️⃣ 检查系统状态...")
        
        # 检查API是否可用
        try:
            response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
            if response.status_code == 200:
                sync_status = response.json()
                print(f"✅ 主API可用，自动同步: {'启用' if sync_status.get('auto_sync_enabled') else '禁用'}")
            else:
                print("❌ 主API不可用")
                return False
        except Exception as e:
            print(f"❌ 无法连接到主API: {e}")
            return False
        
        try:
            response = requests.get("http://localhost:8001/api/sync-status", timeout=5)
            if response.status_code == 200:
                print("✅ HA管理API可用")
            else:
                print("❌ HA管理API不可用")
        except Exception as e:
            print(f"⚠️ HA管理API连接失败: {e}")
        
        # 2. 检查数据库连接
        print("\n2️⃣ 检查数据库连接...")
        
        try:
            db_manager = EnhancedDatabaseManager()
            if db_manager.ha_manager:
                ha_manager = db_manager.ha_manager
                print(f"✅ HA管理器已启用，当前主节点: {ha_manager.current_primary}")
                
                # 检查节点状态
                cluster_status = ha_manager.get_cluster_status()
                nodes = cluster_status.get('nodes', {})
                healthy_nodes = sum(1 for node in nodes.values() 
                                  if node.get('health_status') == 'healthy')
                print(f"✅ 集群状态: {healthy_nodes}/{len(nodes)} 个节点健康")
                
            else:
                print("❌ HA管理器未启用")
                return False
                
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False
        
        # 3. 测试数据同步
        print("\n3️⃣ 测试数据同步...")
        
        # 添加测试数据
        timestamp = int(time.time())
        test_url = f"https://example.com/verify_sync_{timestamp}.jpg"
        
        try:
            with ha_manager.get_session() as session:
                test_image = ImageModel(
                    url=test_url,
                    source_url="https://example.com",
                    filename=f"verify_sync_{timestamp}.jpg",
                    file_extension="jpg",
                    md5_hash=f"verify_hash_{timestamp}"
                )
                session.add(test_image)
                session.commit()
                test_image_id = test_image.id
                
            print(f"✅ 测试数据已添加，图片ID: {test_image_id}")
            
        except Exception as e:
            print(f"❌ 添加测试数据失败: {e}")
            return False
        
        # 4. 检查同步状态
        print("\n4️⃣ 检查同步状态...")
        
        for i in range(10):
            try:
                response = requests.get("http://localhost:8000/api/sync-status", timeout=5)
                if response.status_code == 200:
                    sync_status = response.json()
                    queue_size = sync_status.get('sync_queue_size', 0)
                    print(f"同步队列: {queue_size} 个操作", end='\r')
                    
                    if queue_size == 0 and i > 3:  # 等待几秒后检查
                        print("\n✅ 同步队列已清空")
                        break
                        
                time.sleep(1)
            except Exception as e:
                print(f"检查同步状态失败: {e}")
                break
        
        # 5. 验证数据一致性
        print("\n5️⃣ 验证数据一致性...")
        
        try:
            # 检查主数据库
            with ha_manager.get_session(read_only=True) as session:
                primary_image = session.query(ImageModel).filter(
                    ImageModel.id == test_image_id
                ).first()
                
            if primary_image:
                print(f"✅ 主数据库包含测试数据: {primary_image.filename}")
            else:
                print("❌ 主数据库中未找到测试数据")
                return False
            
            # 检查备用数据库
            secondary_nodes = [
                name for name, node in ha_manager.nodes.items()
                if node.role.value == 'secondary'
            ]
            
            sync_success = True
            for secondary_node in secondary_nodes:
                try:
                    secondary_session = ha_manager.session_makers[secondary_node]()
                    try:
                        secondary_image = secondary_session.query(ImageModel).filter(
                            ImageModel.id == test_image_id
                        ).first()
                        
                        if secondary_image:
                            print(f"✅ 备用节点 {secondary_node} 数据同步成功")
                        else:
                            print(f"❌ 备用节点 {secondary_node} 数据同步失败")
                            sync_success = False
                            
                    finally:
                        secondary_session.close()
                        
                except Exception as e:
                    print(f"❌ 检查备用节点 {secondary_node} 失败: {e}")
                    sync_success = False
            
            if not sync_success:
                print("⚠️ 部分备用节点同步失败，可能需要手动同步")
                
        except Exception as e:
            print(f"❌ 验证数据一致性失败: {e}")
            return False
        
        # 6. 清理测试数据
        print("\n6️⃣ 清理测试数据...")
        
        try:
            with ha_manager.get_session() as session:
                test_image = session.query(ImageModel).filter(
                    ImageModel.id == test_image_id
                ).first()
                if test_image:
                    session.delete(test_image)
                    session.commit()
                    print("✅ 测试数据清理完成")
                    
        except Exception as e:
            print(f"⚠️ 清理测试数据失败: {e}")
        
        # 7. 最终结果
        print("\n" + "=" * 50)
        if sync_success:
            print("🎉 自动数据同步功能验证通过！")
            print("\n📋 系统状态:")
            print(f"  - 主节点: {ha_manager.current_primary}")
            print(f"  - 备用节点: {len(secondary_nodes)} 个")
            print(f"  - 自动同步: 启用")
            print(f"  - 数据一致性: 正常")
            
            print("\n🔗 管理地址:")
            print("  - 主应用: http://localhost:8000")
            print("  - HA管理: http://localhost:8001")
            print("  - 同步状态: http://localhost:8000/api/sync-status")
            
            return True
        else:
            print("❌ 自动数据同步功能验证失败！")
            print("\n🔧 建议检查:")
            print("  - 网络连接是否正常")
            print("  - 备用数据库是否可访问")
            print("  - 同步配置是否正确")
            print("  - 查看日志: logs/simple_ha.log")
            
            return False
            
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
