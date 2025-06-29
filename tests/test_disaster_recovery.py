"""
容灾备份功能测试

测试数据库备份、恢复、故障转移等功能
"""

import unittest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch

from database.backup_manager import (
    DatabaseBackupManager, DatabaseConfig, BackupConfig, FailoverConfig
)
from database.health_monitor import DatabaseHealthMonitor, AlertRule
from database.failover_manager import DatabaseFailoverManager
from database.enhanced_manager import EnhancedDatabaseManager
from config.settings import DisasterRecoveryConfig


class TestDatabaseBackupManager(unittest.TestCase):
    """测试数据库备份管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试数据库配置
        self.databases = [
            DatabaseConfig(
                name="primary",
                type="primary",
                url=f"sqlite:///{self.temp_dir}/primary.db",
                priority=0
            ),
            DatabaseConfig(
                name="secondary",
                type="secondary", 
                url=f"sqlite:///{self.temp_dir}/secondary.db",
                priority=1
            )
        ]
        
        self.backup_config = BackupConfig(
            backup_dir=f"{self.temp_dir}/backups",
            max_backups=5,
            backup_interval=60,
            enable_auto_backup=False  # 测试时禁用自动备份
        )
        
        self.failover_config = FailoverConfig(
            enable_auto_failover=False,  # 测试时禁用自动故障转移
            health_check_interval=10
        )
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_backup_manager_initialization(self):
        """测试备份管理器初始化"""
        manager = DatabaseBackupManager(
            self.databases, self.backup_config, self.failover_config
        )
        
        self.assertIsNotNone(manager.current_primary)
        self.assertEqual(manager.current_primary, "primary")
        self.assertTrue(Path(self.backup_config.backup_dir).exists())
    
    def test_database_connection_test(self):
        """测试数据库连接测试"""
        manager = DatabaseBackupManager(
            self.databases, self.backup_config, self.failover_config
        )
        
        # 测试有效连接
        self.assertTrue(manager._test_database_connection("primary"))
        
        # 测试无效连接
        invalid_db = DatabaseConfig(
            name="invalid",
            type="secondary",
            url="sqlite:///nonexistent/path/db.db",
            priority=2
        )
        manager.databases["invalid"] = invalid_db
        manager._initialize_engines()
        
        self.assertFalse(manager._test_database_connection("invalid"))
    
    def test_create_backup(self):
        """测试创建备份"""
        manager = DatabaseBackupManager(
            self.databases, self.backup_config, self.failover_config
        )
        
        # 创建表结构
        manager.create_tables()
        
        # 创建备份
        backup_path = manager.create_backup("test_backup")
        
        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).exists())
    
    def test_failover_to_database(self):
        """测试故障转移"""
        manager = DatabaseBackupManager(
            self.databases, self.backup_config, self.failover_config
        )
        
        # 初始状态
        self.assertEqual(manager.current_primary, "primary")
        
        # 执行故障转移
        success = manager.failover_to_database("secondary")
        
        self.assertTrue(success)
        self.assertEqual(manager.current_primary, "secondary")


class TestHealthMonitor(unittest.TestCase):
    """测试健康监控器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        databases = [
            DatabaseConfig(
                name="test_db",
                type="primary",
                url=f"sqlite:///{self.temp_dir}/test.db",
                priority=0
            )
        ]
        
        backup_config = BackupConfig(backup_dir=f"{self.temp_dir}/backups")
        failover_config = FailoverConfig(enable_auto_failover=False)
        
        self.backup_manager = DatabaseBackupManager(
            databases, backup_config, failover_config
        )
        
        self.health_monitor = DatabaseHealthMonitor(self.backup_manager)
    
    def tearDown(self):
        """清理测试环境"""
        if self.health_monitor.is_monitoring:
            self.health_monitor.stop_monitoring()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_health_monitor_initialization(self):
        """测试健康监控器初始化"""
        self.assertIsNotNone(self.health_monitor)
        self.assertFalse(self.health_monitor.is_monitoring)
        self.assertTrue(len(self.health_monitor.alert_rules) > 0)
    
    def test_add_alert_rule(self):
        """测试添加告警规则"""
        rule = AlertRule(
            name="test_rule",
            metric="response_time",
            operator=">",
            threshold=1000.0
        )
        
        initial_count = len(self.health_monitor.alert_rules)
        self.health_monitor.add_alert_rule(rule)
        
        self.assertEqual(len(self.health_monitor.alert_rules), initial_count + 1)
    
    def test_collect_health_metrics(self):
        """测试收集健康指标"""
        metrics = self.health_monitor._collect_health_metrics("test_db")
        
        self.assertIsNotNone(metrics)
        self.assertGreater(metrics.response_time, 0)
    
    def test_start_stop_monitoring(self):
        """测试启动和停止监控"""
        self.health_monitor.start_monitoring()
        self.assertTrue(self.health_monitor.is_monitoring)
        
        time.sleep(0.1)  # 等待线程启动
        
        self.health_monitor.stop_monitoring()
        self.assertFalse(self.health_monitor.is_monitoring)


class TestFailoverManager(unittest.TestCase):
    """测试故障转移管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        
        databases = [
            DatabaseConfig(
                name="primary",
                type="primary",
                url=f"sqlite:///{self.temp_dir}/primary.db",
                priority=0
            ),
            DatabaseConfig(
                name="secondary",
                type="secondary",
                url=f"sqlite:///{self.temp_dir}/secondary.db",
                priority=1
            )
        ]
        
        backup_config = BackupConfig(backup_dir=f"{self.temp_dir}/backups")
        failover_config = FailoverConfig(enable_auto_failover=False)
        
        self.backup_manager = DatabaseBackupManager(
            databases, backup_config, failover_config
        )
        
        self.health_monitor = DatabaseHealthMonitor(self.backup_manager)
        
        self.failover_manager = DatabaseFailoverManager(
            self.backup_manager, self.health_monitor
        )
    
    def tearDown(self):
        """清理测试环境"""
        if self.failover_manager.is_monitoring:
            self.failover_manager.stop_monitoring()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_failover_manager_initialization(self):
        """测试故障转移管理器初始化"""
        self.assertIsNotNone(self.failover_manager)
        self.assertFalse(self.failover_manager.is_monitoring)
    
    def test_manual_failover(self):
        """测试手动故障转移"""
        # 初始状态
        self.assertEqual(self.backup_manager.current_primary, "primary")
        
        # 执行手动故障转移
        success = self.failover_manager.manual_failover("secondary", "测试故障转移")
        
        self.assertTrue(success)
        self.assertEqual(self.backup_manager.current_primary, "secondary")
        
        # 检查历史记录
        history = self.failover_manager.get_failover_history(1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['target_db'], "secondary")
    
    def test_enable_disable_auto_failover(self):
        """测试启用/禁用自动故障转移"""
        self.failover_manager.disable_auto_failover()
        self.assertFalse(self.failover_manager.auto_failover_enabled)
        
        self.failover_manager.enable_auto_failover()
        self.assertTrue(self.failover_manager.auto_failover_enabled)


class TestEnhancedDatabaseManager(unittest.TestCase):
    """测试增强数据库管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.database_url = f"sqlite:///{self.temp_dir}/test.db"
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_enhanced_manager_without_disaster_recovery(self):
        """测试不启用容灾功能的增强管理器"""
        manager = EnhancedDatabaseManager(self.database_url)
        
        self.assertIsNotNone(manager)
        self.assertFalse(manager.is_disaster_recovery_enabled())
        self.assertTrue(manager.test_connection())
    
    def test_enhanced_manager_with_disaster_recovery(self):
        """测试启用容灾功能的增强管理器"""
        # 创建容灾配置
        from config.settings import (
            DisasterRecoveryConfig, DisasterRecoveryDatabaseConfig,
            DisasterRecoveryBackupConfig, DisasterRecoveryFailoverConfig,
            DisasterRecoveryMonitoringConfig
        )
        
        dr_config = DisasterRecoveryConfig(
            enabled=True,
            databases={
                "primary": DisasterRecoveryDatabaseConfig(
                    name="primary",
                    type="primary",
                    url=f"sqlite:///{self.temp_dir}/primary.db",
                    priority=0
                ),
                "secondary": DisasterRecoveryDatabaseConfig(
                    name="secondary",
                    type="secondary",
                    url=f"sqlite:///{self.temp_dir}/secondary.db",
                    priority=1
                )
            },
            backup=DisasterRecoveryBackupConfig(
                backup_dir=f"{self.temp_dir}/backups",
                enable_auto_backup=False
            ),
            failover=DisasterRecoveryFailoverConfig(
                enable_auto_failover=False
            ),
            monitoring=DisasterRecoveryMonitoringConfig(
                enable_health_monitoring=False
            )
        )
        
        manager = EnhancedDatabaseManager(self.database_url, dr_config)
        
        self.assertIsNotNone(manager)
        self.assertTrue(manager.is_disaster_recovery_enabled())
        
        # 测试基本功能
        manager.create_tables()
        self.assertTrue(manager.test_connection())
        
        # 测试容灾功能
        backup_path = manager.create_backup("test_backup")
        self.assertIsNotNone(backup_path)
        
        # 测试故障转移
        success = manager.manual_failover("secondary", "测试")
        self.assertTrue(success)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestDatabaseBackupManager,
        TestHealthMonitor,
        TestFailoverManager,
        TestEnhancedDatabaseManager
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
