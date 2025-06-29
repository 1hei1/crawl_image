#!/usr/bin/env python3
"""
PostgreSQL高可用系统启动脚本

专门用于启动基于PostgreSQL的分布式高可用系统
"""

import logging
import signal
import sys
import threading
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config.ha_config_loader import load_ha_config
from database.distributed_ha_manager import DistributedHAManager
from database.ha_api_server import HAAPIServer
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/postgresql_ha.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class PostgreSQLHASystem:
    """PostgreSQL高可用系统"""
    
    def __init__(self):
        """初始化系统"""
        self.ha_manager = None
        self.ha_api_server = None
        self.main_api_thread = None
        self.ha_api_thread = None
        self.is_running = False
        
        # 确保日志目录存在
        Path("logs").mkdir(exist_ok=True)
        
        logger.info("PostgreSQL高可用系统初始化")
    
    def start(self):
        """启动系统"""
        try:
            print("🚀 启动PostgreSQL分布式高可用数据库系统")
            print("=" * 60)
            
            # 1. 加载配置
            print("📋 加载配置文件...")
            nodes, local_node_name, config = load_ha_config()
            print(f"✅ 配置加载成功，本地节点: {local_node_name}")
            
            # 2. 创建HA管理器
            print("🔧 初始化HA管理器...")
            self.ha_manager = DistributedHAManager(nodes, local_node_name)
            self.ha_manager.start_monitoring()
            print(f"✅ HA管理器启动成功，当前主节点: {self.ha_manager.current_primary}")
            
            # 3. 启动HA API服务器
            print("🌐 启动HA API服务器...")
            api_config = config.get('api_server', {})
            ha_api_port = api_config.get('port', 8001)
            
            self.ha_api_server = HAAPIServer(self.ha_manager, ha_api_port)
            self.ha_api_thread = threading.Thread(
                target=self._start_ha_api_server,
                args=(api_config.get('host', '0.0.0.0'),),
                daemon=True
            )
            self.ha_api_thread.start()
            print(f"✅ HA API服务器启动成功 (端口: {ha_api_port})")
            
            # 4. 启动主应用API服务器
            print("🎯 启动主应用API服务器...")
            self.main_api_thread = threading.Thread(
                target=self._start_main_api_server,
                daemon=True
            )
            self.main_api_thread.start()
            print("✅ 主应用API服务器启动成功 (端口: 8000)")
            
            self.is_running = True
            
            # 显示系统状态
            self._display_system_info()
            
            # 设置信号处理
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            print("\n🎉 PostgreSQL高可用系统启动完成！")
            print("按 Ctrl+C 停止系统")
            
            # 保持运行
            self._keep_alive()
            
        except Exception as e:
            logger.error(f"❌ 系统启动失败: {e}")
            self.stop()
            sys.exit(1)
    
    def _start_ha_api_server(self, host: str):
        """启动HA API服务器"""
        try:
            self.ha_api_server.start(host)
        except Exception as e:
            logger.error(f"HA API服务器启动失败: {e}")
    
    def _start_main_api_server(self):
        """启动主应用API服务器"""
        try:
            # 导入主应用
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
    
    def _display_system_info(self):
        """显示系统信息"""
        print("\n" + "="*60)
        print("🗄️ PostgreSQL分布式高可用数据库系统")
        print("="*60)
        
        status = self.ha_manager.get_cluster_status()
        
        print(f"当前主节点: {status['current_primary']}")
        print(f"本地节点: {status['local_node']}")
        print(f"监控状态: {'运行中' if status['is_monitoring'] else '已停止'}")
        print()
        
        print("数据库节点:")
        for node_name, node_info in status['nodes'].items():
            role_icon = "👑" if node_info['role'] == 'primary' else "🔄"
            health_icon = "🟢" if node_info['health_status'] == 'healthy' else "🔴"
            
            print(f"  {role_icon} {node_name} ({node_info['role']})")
            print(f"    状态: {health_icon} {node_info['health_status']}")
            print(f"    服务器: {node_info['server']['host']}:{node_info['server']['port']}")
            
            if node_info['replication_lag'] > 0:
                print(f"    复制延迟: {node_info['replication_lag']:.2f}秒")
            print()
        
        print("API服务:")
        print(f"  🌐 主应用: http://localhost:8000")
        print(f"  🔧 HA管理: http://localhost:8001/api/status")
        print(f"  📊 集群状态: http://localhost:8000/api/ha-status")
        print("="*60)
    
    def _keep_alive(self):
        """保持系统运行"""
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭系统...")
            self.stop()
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，正在关闭系统...")
        self.stop()
        sys.exit(0)
    
    def stop(self):
        """停止系统"""
        logger.info("正在停止PostgreSQL高可用系统...")
        
        self.is_running = False
        
        if self.ha_manager:
            self.ha_manager.stop_monitoring()
            logger.info("✅ HA管理器已停止")
        
        logger.info("🛑 系统已停止")


def check_prerequisites():
    """检查先决条件"""
    print("🔍 检查系统先决条件...")
    
    # 检查配置文件
    config_file = Path("config/distributed_ha_config.yaml")
    if not config_file.exists():
        print("❌ 配置文件不存在: config/distributed_ha_config.yaml")
        return False
    
    # 检查数据库连接
    try:
        from config.ha_config_loader import load_ha_config
        nodes, local_node_name, config = load_ha_config()
        print(f"✅ 配置文件有效，发现 {len(nodes)} 个节点")
        
        # 测试数据库连接
        print("🔗 测试数据库连接...")
        for node in nodes:
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(node.database_url, connect_args={"connect_timeout": 5})
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print(f"  ✅ {node.name}: {node.server.host}")
                engine.dispose()
            except Exception as e:
                print(f"  ❌ {node.name}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False


def main():
    """主函数"""
    print("🗄️ PostgreSQL分布式高可用数据库系统")
    print("=" * 60)
    print("主数据库: 113.29.231.99:5432")
    print("备数据库: 113.29.232.245:5432")
    print("=" * 60)
    
    # 检查先决条件
    if not check_prerequisites():
        print("\n❌ 先决条件检查失败，请检查配置和数据库连接")
        print("\n建议步骤:")
        print("1. 运行: python setup_postgresql_databases.py")
        print("2. 检查网络连接和防火墙设置")
        print("3. 验证数据库用户权限")
        sys.exit(1)
    
    print("\n✅ 先决条件检查通过")
    
    # 启动系统
    system = PostgreSQLHASystem()
    system.start()


if __name__ == "__main__":
    main()
