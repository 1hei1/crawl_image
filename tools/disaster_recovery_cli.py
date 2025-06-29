#!/usr/bin/env python3
"""
容灾备份命令行工具

提供数据库备份、恢复、故障转移等操作的命令行接口
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.manager import ConfigManager
from database.enhanced_manager import EnhancedDatabaseManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DisasterRecoveryCLI:
    """容灾备份命令行工具"""
    
    def __init__(self, config_file: Optional[str] = None):
        """初始化CLI工具"""
        try:
            # 加载配置
            self.config_manager = ConfigManager(config_file)
            self.settings = self.config_manager.get_settings()
            
            # 初始化数据库管理器
            database_url = self.config_manager.get_database_url()
            self.db_manager = EnhancedDatabaseManager(
                database_url, 
                self.settings.disaster_recovery
            )
            
            logger.info("容灾备份CLI工具初始化完成")
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            sys.exit(1)
    
    def status(self):
        """显示系统状态"""
        print("=== 容灾备份系统状态 ===")
        
        # 基本信息
        print(f"容灾备份功能: {'启用' if self.db_manager.is_disaster_recovery_enabled() else '禁用'}")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用，请检查配置文件")
            return
        
        # 数据库状态
        print("\n--- 数据库状态 ---")
        db_status = self.db_manager.get_database_info()
        
        if 'disaster_recovery' in db_status:
            dr_info = db_status['disaster_recovery']
            print(f"当前主数据库: {dr_info.get('current_primary', 'N/A')}")
            print(f"自动备份: {'启用' if dr_info.get('backup_enabled') else '禁用'}")
            print(f"健康监控: {'启用' if dr_info.get('monitoring_enabled') else '禁用'}")
            print(f"自动故障转移: {'启用' if dr_info.get('failover_enabled') else '禁用'}")
        
        # 显示所有数据库实例
        for db_name, info in db_status.items():
            if db_name != 'disaster_recovery' and isinstance(info, dict):
                status_icon = "🟢" if info.get('is_connected') else "🔴"
                primary_icon = "👑" if info.get('is_primary') else ""
                print(f"  {status_icon} {db_name} {primary_icon}")
                print(f"    类型: {info.get('type', 'N/A')}")
                print(f"    优先级: {info.get('priority', 'N/A')}")
                print(f"    连接状态: {'正常' if info.get('is_connected') else '异常'}")
                if info.get('last_error'):
                    print(f"    最后错误: {info['last_error']}")
        
        # 健康状态
        print("\n--- 健康状态 ---")
        health_status = self.db_manager.get_health_status()
        if isinstance(health_status, dict) and 'status' in health_status:
            print(f"整体状态: {health_status['status']}")
        else:
            for db_name, status in health_status.items():
                if isinstance(status, dict):
                    print(f"  {db_name}: {status.get('status', 'unknown')}")
                    if 'response_time' in status:
                        print(f"    响应时间: {status['response_time']:.2f}ms")
        
        # 故障转移状态
        print("\n--- 故障转移状态 ---")
        failover_status = self.db_manager.get_failover_status()
        if failover_status.get('enabled', False):
            print(f"当前状态: {failover_status.get('current_status', 'unknown')}")
            print(f"自动故障转移: {'启用' if failover_status.get('auto_failover_enabled') else '禁用'}")
            print(f"检测阈值: {failover_status.get('detection_threshold', 'N/A')}")
            
            failure_counts = failover_status.get('failure_counts', {})
            if failure_counts:
                print("失败计数:")
                for db_name, count in failure_counts.items():
                    print(f"  {db_name}: {count}")
        else:
            print("故障转移功能未启用")
    
    def backup(self, name: Optional[str] = None):
        """创建备份"""
        print("=== 创建数据库备份 ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        try:
            backup_path = self.db_manager.create_backup(name)
            if backup_path:
                print(f"✅ 备份创建成功: {backup_path}")
            else:
                print("❌ 备份创建失败")
        except Exception as e:
            print(f"❌ 备份创建失败: {e}")
    
    def restore(self, backup_path: str):
        """恢复备份"""
        print(f"=== 恢复数据库备份: {backup_path} ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        if not Path(backup_path).exists():
            print(f"❌ 备份文件不存在: {backup_path}")
            return
        
        # 确认操作
        confirm = input("⚠️  此操作将覆盖当前数据库，是否继续？(y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        
        try:
            success = self.db_manager.restore_backup(backup_path)
            if success:
                print("✅ 数据库恢复成功")
            else:
                print("❌ 数据库恢复失败")
        except Exception as e:
            print(f"❌ 数据库恢复失败: {e}")
    
    def failover(self, target_db: str, reason: str = "手动故障转移"):
        """手动故障转移"""
        print(f"=== 手动故障转移到: {target_db} ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        # 确认操作
        confirm = input(f"⚠️  确认要切换到数据库 '{target_db}'？(y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return
        
        try:
            success = self.db_manager.manual_failover(target_db, reason)
            if success:
                print(f"✅ 故障转移成功: {target_db}")
            else:
                print(f"❌ 故障转移失败: {target_db}")
        except Exception as e:
            print(f"❌ 故障转移失败: {e}")
    
    def history(self, limit: int = 10):
        """显示故障转移历史"""
        print("=== 故障转移历史 ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        history = self.db_manager.get_failover_history(limit)
        
        if not history:
            print("暂无故障转移记录")
            return
        
        for i, event in enumerate(history, 1):
            print(f"\n{i}. {event['timestamp']}")
            print(f"   {event['source_db']} -> {event['target_db']}")
            print(f"   原因: {event['reason']}")
            print(f"   状态: {event['status']}")
            if event.get('duration'):
                print(f"   耗时: {event['duration']:.2f}秒")
            if event.get('error_message'):
                print(f"   错误: {event['error_message']}")
    
    def enable_auto_failover(self):
        """启用自动故障转移"""
        print("=== 启用自动故障转移 ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        try:
            self.db_manager.enable_auto_failover()
            print("✅ 自动故障转移已启用")
        except Exception as e:
            print(f"❌ 启用自动故障转移失败: {e}")
    
    def disable_auto_failover(self):
        """禁用自动故障转移"""
        print("=== 禁用自动故障转移 ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        try:
            self.db_manager.disable_auto_failover()
            print("✅ 自动故障转移已禁用")
        except Exception as e:
            print(f"❌ 禁用自动故障转移失败: {e}")
    
    def start_monitoring(self):
        """启动监控服务"""
        print("=== 启动监控服务 ===")
        
        if not self.db_manager.is_disaster_recovery_enabled():
            print("容灾备份功能未启用")
            return
        
        try:
            self.db_manager.start_monitoring()
            print("✅ 监控服务已启动")
            print("监控服务将在后台运行，按 Ctrl+C 停止")
            
            # 保持程序运行
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n正在停止监控服务...")
                self.db_manager.stop_monitoring()
                print("✅ 监控服务已停止")
                
        except Exception as e:
            print(f"❌ 启动监控服务失败: {e}")
    
    def test_connection(self):
        """测试数据库连接"""
        print("=== 测试数据库连接 ===")
        
        try:
            success = self.db_manager.test_connection()
            if success:
                print("✅ 数据库连接正常")
            else:
                print("❌ 数据库连接失败")
        except Exception as e:
            print(f"❌ 数据库连接测试失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="图片爬虫容灾备份管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s status                    # 显示系统状态
  %(prog)s backup                    # 创建备份
  %(prog)s backup --name my_backup   # 创建指定名称的备份
  %(prog)s restore backup.sql        # 恢复备份
  %(prog)s failover secondary1       # 故障转移到secondary1
  %(prog)s history                   # 显示故障转移历史
  %(prog)s enable-auto-failover      # 启用自动故障转移
  %(prog)s disable-auto-failover     # 禁用自动故障转移
  %(prog)s start-monitoring          # 启动监控服务
  %(prog)s test                      # 测试数据库连接
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        help='配置文件路径',
        default='config/config.yaml'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # status命令
    subparsers.add_parser('status', help='显示系统状态')
    
    # backup命令
    backup_parser = subparsers.add_parser('backup', help='创建数据库备份')
    backup_parser.add_argument('--name', help='备份名称')
    
    # restore命令
    restore_parser = subparsers.add_parser('restore', help='恢复数据库备份')
    restore_parser.add_argument('backup_path', help='备份文件路径')
    
    # failover命令
    failover_parser = subparsers.add_parser('failover', help='手动故障转移')
    failover_parser.add_argument('target_db', help='目标数据库名称')
    failover_parser.add_argument('--reason', default='手动故障转移', help='故障转移原因')
    
    # history命令
    history_parser = subparsers.add_parser('history', help='显示故障转移历史')
    history_parser.add_argument('--limit', type=int, default=10, help='显示记录数量')
    
    # 其他命令
    subparsers.add_parser('enable-auto-failover', help='启用自动故障转移')
    subparsers.add_parser('disable-auto-failover', help='禁用自动故障转移')
    subparsers.add_parser('start-monitoring', help='启动监控服务')
    subparsers.add_parser('test', help='测试数据库连接')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 初始化CLI工具
    cli = DisasterRecoveryCLI(args.config)
    
    # 执行命令
    try:
        if args.command == 'status':
            cli.status()
        elif args.command == 'backup':
            cli.backup(args.name)
        elif args.command == 'restore':
            cli.restore(args.backup_path)
        elif args.command == 'failover':
            cli.failover(args.target_db, args.reason)
        elif args.command == 'history':
            cli.history(args.limit)
        elif args.command == 'enable-auto-failover':
            cli.enable_auto_failover()
        elif args.command == 'disable-auto-failover':
            cli.disable_auto_failover()
        elif args.command == 'start-monitoring':
            cli.start_monitoring()
        elif args.command == 'test':
            cli.test_connection()
        else:
            print(f"未知命令: {args.command}")
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n操作已取消")
    except Exception as e:
        logger.error(f"执行命令失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
