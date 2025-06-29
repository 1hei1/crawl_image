#!/usr/bin/env python3
"""
分布式高可用数据库系统启动脚本

启动包含以下组件的完整高可用系统：
1. 分布式数据库管理器
2. API服务器（用于节点间通信）
3. 主应用程序（图片爬虫API）
4. 监控和故障转移
"""

import asyncio
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
from api import app as main_app
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ha_system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class HASystemManager:
    """高可用系统管理器"""
    
    def __init__(self, config_path: str = "config/distributed_ha_config.yaml"):
        """
        初始化系统管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.ha_manager: DistributedHAManager = None
        self.ha_api_server: HAAPIServer = None
        self.main_api_server = None
        self.is_running = False
        
        # 加载配置
        self.nodes, self.local_node_name, self.config = load_ha_config(config_path)
        
        logger.info("高可用系统管理器初始化完成")
    
    def start(self):
        """启动高可用系统"""
        try:
            logger.info("正在启动分布式高可用数据库系统...")
            
            # 1. 创建并启动HA管理器
            self.ha_manager = DistributedHAManager(self.nodes, self.local_node_name)
            
            # 添加故障转移回调
            self.ha_manager.add_failover_callback(self._on_failover)
            
            # 启动监控
            self.ha_manager.start_monitoring()
            logger.info("HA管理器启动成功")

            # 2. 创建HA API服务器
            api_config = self.config.get('api_server', {})
            ha_api_port = api_config.get('port', 8001)

            self.ha_api_server = HAAPIServer(self.ha_manager, ha_api_port)

            # 在单独线程中启动HA API服务器
            ha_api_thread = threading.Thread(
                target=self._start_ha_api_server,
                args=(api_config.get('host', '0.0.0.0'),),
                daemon=True
            )
            ha_api_thread.start()
            logger.info(f"HA API服务器启动成功 (端口: {ha_api_port})")

            # 3. 修改主应用程序使用HA管理器
            self._integrate_ha_with_main_app()

            # 4. 启动主应用程序API服务器
            main_api_port = 8000
            main_api_thread = threading.Thread(
                target=self._start_main_api_server,
                args=('0.0.0.0', main_api_port),
                daemon=True
            )
            main_api_thread.start()
            logger.info(f"主API服务器启动成功 (端口: {main_api_port})")
            
            self.is_running = True
            
            # 显示系统状态
            self._display_system_status()
            
            # 设置信号处理
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            logger.info("分布式高可用数据库系统启动完成！")
            
            # 保持主线程运行
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
    
    def _start_main_api_server(self, host: str, port: int):
        """启动主API服务器"""
        try:
            uvicorn.run(
                main_app,
                host=host,
                port=port,
                log_level="info",
                access_log=False
            )
        except Exception as e:
            logger.error(f"主API服务器启动失败: {e}")
    
    def _integrate_ha_with_main_app(self):
        """将HA管理器集成到主应用程序"""
        # 这里可以修改主应用程序的数据库连接
        # 使其使用HA管理器提供的连接
        
        # 将HA管理器设置为全局变量，供主应用使用
        import api
        if hasattr(api, 'image_crawler') and api.image_crawler:
            # 替换数据库管理器
            api.image_crawler.db_manager = self.ha_manager
            logger.info("主应用程序已集成HA管理器")
    
    def _on_failover(self, failed_node: str, new_primary: str):
        """故障转移回调函数"""
        logger.warning(f"🔄 故障转移完成: {failed_node} -> {new_primary}")
        
        # 这里可以添加故障转移后的处理逻辑
        # 例如：发送通知、更新配置等
        
        # 发送通知（如果配置了）
        notification_config = self.config.get('notifications', {})
        if notification_config.get('enabled', False):
            self._send_failover_notification(failed_node, new_primary)
    
    def _send_failover_notification(self, failed_node: str, new_primary: str):
        """发送故障转移通知"""
        try:
            message = f"数据库故障转移通知：{failed_node} -> {new_primary}"
            
            # 邮件通知
            email_config = self.config.get('notifications', {}).get('email', {})
            if email_config.get('enabled', False):
                # 实现邮件发送逻辑
                logger.info(f"📧 发送邮件通知: {message}")
            
            # Webhook通知
            webhook_config = self.config.get('notifications', {}).get('webhook', {})
            if webhook_config.get('enabled', False):
                # 实现Webhook发送逻辑
                logger.info(f"🔗 发送Webhook通知: {message}")
                
        except Exception as e:
            logger.error(f"发送故障转移通知失败: {e}")
    
    def _display_system_status(self):
        """显示系统状态"""
        print("\n" + "="*60)
        print("🚀 分布式高可用数据库系统状态")
        print("="*60)
        
        status = self.ha_manager.get_cluster_status()
        
        print(f"当前主节点: {status['current_primary']}")
        print(f"本地节点: {status['local_node']}")
        print(f"监控状态: {'运行中' if status['is_monitoring'] else '已停止'}")
        print(f"同步队列: {status['sync_queue_size']} 个操作")
        print()
        
        print("节点状态:")
        for node_name, node_info in status['nodes'].items():
            role_icon = "👑" if node_info['role'] == 'primary' else "🔄"
            health_icon = "🟢" if node_info['health_status'] == 'healthy' else "🔴"
            
            print(f"  {role_icon} {node_name} ({node_info['role']})")
            print(f"    状态: {health_icon} {node_info['health_status']}")
            print(f"    服务器: {node_info['server']['host']}:{node_info['server']['port']}")
            print(f"    优先级: {node_info['priority']}")
            
            if node_info['replication_lag'] > 0:
                print(f"    复制延迟: {node_info['replication_lag']:.2f}秒")
            
            if node_info['last_error']:
                print(f"    最后错误: {node_info['last_error']}")
            print()
        
        print("API服务:")
        print(f"  🌐 主API: http://localhost:8000")
        print(f"  🔧 HA API: http://localhost:8001")
        print("="*60)
    
    def _keep_alive(self):
        """保持主线程运行"""
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
        """停止高可用系统"""
        logger.info("正在停止分布式高可用数据库系统...")
        
        self.is_running = False
        
        if self.ha_manager:
            self.ha_manager.stop_monitoring()
            logger.info("HA管理器已停止")

        logger.info("系统已停止")


def main():
    """主函数"""
    print("🚀 启动分布式高可用数据库系统")
    print("按 Ctrl+C 停止系统")
    print()
    
    # 确保日志目录存在
    Path("logs").mkdir(exist_ok=True)
    
    # 创建并启动系统管理器
    system_manager = HASystemManager()
    system_manager.start()


if __name__ == "__main__":
    main()
