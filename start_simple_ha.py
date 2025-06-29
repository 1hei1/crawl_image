#!/usr/bin/env python3
"""
简化的PostgreSQL高可用系统启动脚本

专门用于启动基于PostgreSQL的分布式高可用系统
避免复杂的emoji字符和异步问题
"""

import logging
import signal
import sys
import threading
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志 - 使用简单格式避免编码问题
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/simple_ha.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def start_ha_system():
    """启动HA系统"""
    try:
        print("启动PostgreSQL分布式高可用数据库系统")
        print("=" * 60)
        
        # 确保日志目录存在
        Path("logs").mkdir(exist_ok=True)
        
        # 1. 加载配置
        print("加载配置文件...")
        from config.ha_config_loader import load_ha_config
        nodes, local_node_name, config = load_ha_config()
        print(f"配置加载成功，本地节点: {local_node_name}")
        print(f"发现 {len(nodes)} 个数据库节点")
        
        # 2. 创建HA管理器
        print("初始化HA管理器...")
        from database.distributed_ha_manager import DistributedHAManager
        ha_manager = DistributedHAManager(nodes, local_node_name, config)
        ha_manager.start_monitoring()
        print(f"HA管理器启动成功，当前主节点: {ha_manager.current_primary}")

        # 显示同步配置
        sync_config = config.get('synchronization', {})
        print(f"自动同步: {'启用' if sync_config.get('auto_sync_enabled', True) else '禁用'}")
        print(f"全量同步间隔: {sync_config.get('full_sync_interval', 300)}秒")
        
        # 3. 启动HA API服务器
        print("启动HA API服务器...")
        from database.ha_api_server import HAAPIServer
        api_config = config.get('api_server', {})
        ha_api_port = api_config.get('port', 8001)
        
        ha_api_server = HAAPIServer(ha_manager, ha_api_port)
        
        def start_ha_api():
            try:
                ha_api_server.start(api_config.get('host', '0.0.0.0'))
            except Exception as e:
                logger.error(f"HA API服务器启动失败: {e}")
        
        ha_api_thread = threading.Thread(target=start_ha_api, daemon=True)
        ha_api_thread.start()
        print(f"HA API服务器启动成功 (端口: {ha_api_port})")
        
        # 4. 启动主应用API服务器
        print("启动主应用API服务器...")
        
        def start_main_api():
            try:
                import uvicorn
                from api import app
                uvicorn.run(
                    app,
                    host="0.0.0.0",
                    port=8000,
                    log_level="info",
                    access_log=False
                )
            except Exception as e:
                logger.error(f"主API服务器启动失败: {e}")
        
        main_api_thread = threading.Thread(target=start_main_api, daemon=True)
        main_api_thread.start()
        print("主API服务器启动成功 (端口: 8000)")
        
        # 5. 显示系统状态
        time.sleep(2)  # 等待服务器启动
        display_system_status(ha_manager)
        
        print("\n系统启动完成！")
        print("按 Ctrl+C 停止系统")
        
        # 6. 保持运行
        def signal_handler(signum, frame):
            print("\n收到停止信号，正在关闭系统...")
            ha_manager.stop_monitoring()
            print("系统已停止")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 保持主线程运行
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"系统启动失败: {e}")
        logger.error(f"系统启动失败: {e}")
        sys.exit(1)


def display_system_status(ha_manager):
    """显示系统状态"""
    try:
        print("\n" + "="*60)
        print("PostgreSQL分布式高可用数据库系统状态")
        print("="*60)
        
        status = ha_manager.get_cluster_status()
        
        print(f"当前主节点: {status['current_primary']}")
        print(f"本地节点: {status['local_node']}")
        print(f"监控状态: {'运行中' if status['is_monitoring'] else '已停止'}")
        print(f"同步队列: {status['sync_queue_size']} 个操作")
        print()
        
        print("数据库节点:")
        for node_name, node_info in status['nodes'].items():
            role_text = "主节点" if node_info['role'] == 'primary' else "备节点"
            health_text = "健康" if node_info['health_status'] == 'healthy' else "离线"
            
            print(f"  {role_text}: {node_name}")
            print(f"    状态: {health_text}")
            print(f"    服务器: {node_info['server']['host']}:{node_info['server']['port']}")
            print(f"    优先级: {node_info['priority']}")
            
            if node_info['replication_lag'] > 0:
                print(f"    复制延迟: {node_info['replication_lag']:.2f}秒")
            
            if node_info['last_error']:
                print(f"    最后错误: {node_info['last_error']}")
            print()
        
        print("API服务:")
        print("  主应用: http://localhost:8000")
        print("  HA管理: http://localhost:8001/api/status")
        print("  集群状态: http://localhost:8000/api/ha-status")
        print("="*60)
        
    except Exception as e:
        print(f"显示系统状态失败: {e}")


def test_connections():
    """测试数据库连接"""
    try:
        print("测试数据库连接...")
        
        from config.ha_config_loader import load_ha_config
        from sqlalchemy import create_engine, text
        
        nodes, local_node_name, config = load_ha_config()
        
        for node in nodes:
            try:
                engine = create_engine(node.database_url, connect_args={"connect_timeout": 5})
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print(f"  连接成功: {node.name} ({node.server.host})")
                engine.dispose()
            except Exception as e:
                print(f"  连接失败: {node.name} - {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"连接测试失败: {e}")
        return False


def main():
    """主函数"""
    print("PostgreSQL分布式高可用数据库系统")
    print("=" * 60)
    print("主数据库: 113.29.231.99:5432")
    print("备数据库: 113.29.232.245:5432")
    print("=" * 60)
    
    # 测试连接
    if not test_connections():
        print("\n数据库连接测试失败，请检查:")
        print("1. 网络连接和防火墙设置")
        print("2. 数据库服务是否运行")
        print("3. 用户名密码是否正确")
        print("4. 运行: python setup_postgresql_databases.py")
        sys.exit(1)
    
    print("\n数据库连接测试通过")
    
    # 启动系统
    start_ha_system()


if __name__ == "__main__":
    main()
