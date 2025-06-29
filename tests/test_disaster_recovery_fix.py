#!/usr/bin/env python3
"""
容灾备份修复测试脚本

测试修复后的容灾备份功能
"""

import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config.manager import ConfigManager
from database.enhanced_manager import EnhancedDatabaseManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_disaster_recovery():
    """测试容灾备份功能"""
    print("🧪 开始测试容灾备份功能...")
    
    try:
        # 1. 加载配置
        print("\n1️⃣ 加载配置...")
        config_manager = ConfigManager("config/config.yaml")
        settings = config_manager.get_settings()
        
        if not settings.disaster_recovery.enabled:
            print("❌ 容灾备份功能未启用，请在配置文件中启用")
            return False
        
        print("✅ 配置加载成功")
        
        # 2. 初始化增强数据库管理器
        print("\n2️⃣ 初始化数据库管理器...")
        database_url = config_manager.get_database_url()
        db_manager = EnhancedDatabaseManager(
            database_url, 
            settings.disaster_recovery
        )
        
        if db_manager.is_disaster_recovery_enabled():
            print("✅ 容灾备份功能已启用")
        else:
            print("❌ 容灾备份功能初始化失败")
            return False
        
        # 3. 测试数据库连接
        print("\n3️⃣ 测试数据库连接...")
        if db_manager.test_connection():
            print("✅ 数据库连接正常")
        else:
            print("❌ 数据库连接失败")
            return False
        
        # 4. 创建数据库表
        print("\n4️⃣ 创建数据库表...")
        try:
            db_manager.create_tables()
            print("✅ 数据库表创建成功")
        except Exception as e:
            print(f"❌ 数据库表创建失败: {e}")
            return False
        
        # 5. 测试备份功能
        print("\n5️⃣ 测试备份功能...")
        try:
            backup_path = db_manager.create_backup("test_backup")
            if backup_path:
                print(f"✅ 备份创建成功: {backup_path}")
            else:
                print("❌ 备份创建失败")
                return False
        except Exception as e:
            print(f"❌ 备份创建失败: {e}")
            return False
        
        # 6. 测试健康监控
        print("\n6️⃣ 测试健康监控...")
        try:
            health_status = db_manager.get_health_status()
            print(f"✅ 健康状态获取成功: {health_status}")
        except Exception as e:
            print(f"❌ 健康状态获取失败: {e}")
            return False
        
        # 7. 测试故障转移状态
        print("\n7️⃣ 测试故障转移状态...")
        try:
            failover_status = db_manager.get_failover_status()
            print(f"✅ 故障转移状态获取成功: {failover_status}")
        except Exception as e:
            print(f"❌ 故障转移状态获取失败: {e}")
            return False
        
        # 8. 启动监控服务（短时间测试）
        print("\n8️⃣ 测试监控服务...")
        try:
            db_manager.start_monitoring()
            print("✅ 监控服务启动成功")
            
            # 等待几秒钟让监控运行
            print("⏳ 等待监控服务运行...")
            time.sleep(3)
            
            # 停止监控服务
            db_manager.stop_monitoring()
            print("✅ 监控服务停止成功")
        except Exception as e:
            print(f"❌ 监控服务测试失败: {e}")
            return False
        
        # 9. 测试数据库信息获取
        print("\n9️⃣ 测试数据库信息获取...")
        try:
            db_info = db_manager.get_database_info()
            print("✅ 数据库信息获取成功")
            
            # 显示关键信息
            if 'disaster_recovery' in db_info:
                dr_info = db_info['disaster_recovery']
                print(f"  当前主数据库: {dr_info.get('current_primary', 'N/A')}")
                print(f"  备份功能: {'启用' if dr_info.get('backup_enabled') else '禁用'}")
                print(f"  监控功能: {'启用' if dr_info.get('monitoring_enabled') else '禁用'}")
                print(f"  故障转移: {'启用' if dr_info.get('failover_enabled') else '禁用'}")
        except Exception as e:
            print(f"❌ 数据库信息获取失败: {e}")
            return False
        
        print("\n🎉 所有测试通过！容灾备份功能工作正常")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🛡️ 容灾备份功能修复测试")
    print("=" * 60)
    
    success = test_disaster_recovery()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试结果: 成功")
        print("容灾备份功能已修复并正常工作")
    else:
        print("❌ 测试结果: 失败")
        print("请检查错误信息并修复相关问题")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
