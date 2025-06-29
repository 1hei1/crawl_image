"""
配置管理器测试用例
"""

import pytest
import tempfile
import os
from pathlib import Path
import yaml

from config.manager import ConfigManager
from config.settings import Settings


class TestConfigManager:
    """配置管理器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
    
    def teardown_method(self):
        """测试后的清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_config(self):
        """测试默认配置"""
        # 使用不存在的配置文件，应该使用默认配置
        manager = ConfigManager('nonexistent.yaml')
        settings = manager.get_settings()
        
        assert isinstance(settings, Settings)
        assert settings.database.type == "sqlite"
        assert settings.crawler.max_depth == 3
        assert settings.logging.level == "INFO"
    
    def test_load_from_yaml_file(self):
        """测试从YAML文件加载配置"""
        # 创建测试配置文件
        test_config = {
            'database': {
                'type': 'postgresql',
                'host': 'test_host',
                'port': 5433
            },
            'crawler': {
                'max_depth': 5,
                'max_images': 2000
            },
            'logging': {
                'level': 'DEBUG'
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)
        
        # 加载配置
        manager = ConfigManager(self.config_file)
        settings = manager.get_settings()
        
        assert settings.database.type == 'postgresql'
        assert settings.database.host == 'test_host'
        assert settings.database.port == 5433
        assert settings.crawler.max_depth == 5
        assert settings.crawler.max_images == 2000
        assert settings.logging.level == 'DEBUG'
    
    def test_load_from_environment(self):
        """测试从环境变量加载配置"""
        # 设置环境变量
        os.environ['DB_TYPE'] = 'postgresql'
        os.environ['DB_HOST'] = 'env_host'
        os.environ['CRAWLER_MAX_DEPTH'] = '7'
        os.environ['LOG_LEVEL'] = 'WARNING'
        
        try:
            manager = ConfigManager('nonexistent.yaml')
            settings = manager.get_settings()
            
            assert settings.database.type == 'postgresql'
            assert settings.database.host == 'env_host'
            assert settings.crawler.max_depth == 7
            assert settings.logging.level == 'WARNING'
            
        finally:
            # 清理环境变量
            for key in ['DB_TYPE', 'DB_HOST', 'CRAWLER_MAX_DEPTH', 'LOG_LEVEL']:
                os.environ.pop(key, None)
    
    def test_get_database_url_sqlite(self):
        """测试SQLite数据库URL生成"""
        manager = ConfigManager('nonexistent.yaml')
        url = manager.get_database_url()
        
        assert url.startswith('sqlite:///')
        assert 'data/images.db' in url
    
    def test_get_database_url_postgresql(self):
        """测试PostgreSQL数据库URL生成"""
        # 创建PostgreSQL配置
        test_config = {
            'database': {
                'type': 'postgresql',
                'host': 'localhost',
                'port': 5432,
                'database': 'test_db',
                'username': 'test_user',
                'password': 'test_pass'
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)
        
        manager = ConfigManager(self.config_file)
        url = manager.get_database_url()
        
        expected = 'postgresql://test_user:test_pass@localhost:5432/test_db'
        assert url == expected
    
    def test_save_config(self):
        """测试保存配置"""
        manager = ConfigManager('nonexistent.yaml')
        
        # 修改一些配置
        manager.update_setting('crawler', 'max_depth', 10)
        manager.update_setting('logging', 'level', 'ERROR')
        
        # 保存配置
        output_file = os.path.join(self.temp_dir, 'saved_config.yaml')
        manager.save_config(output_file)
        
        # 验证保存的文件
        assert os.path.exists(output_file)
        
        # 重新加载并验证
        new_manager = ConfigManager(output_file)
        settings = new_manager.get_settings()
        
        assert settings.crawler.max_depth == 10
        assert settings.logging.level == 'ERROR'
    
    def test_update_setting(self):
        """测试更新配置项"""
        manager = ConfigManager('nonexistent.yaml')
        
        # 更新配置
        manager.update_setting('crawler', 'max_images', 5000)
        manager.update_setting('database', 'type', 'postgresql')
        
        settings = manager.get_settings()
        assert settings.crawler.max_images == 5000
        assert settings.database.type == 'postgresql'
    
    def test_get_config_summary(self):
        """测试获取配置摘要"""
        manager = ConfigManager('nonexistent.yaml')
        summary = manager.get_config_summary()
        
        assert 'database_type' in summary
        assert 'max_depth' in summary
        assert 'max_images' in summary
        assert 'max_concurrent' in summary
        assert 'download_path' in summary
        assert 'log_level' in summary
        assert 'environment' in summary
        assert 'debug' in summary
    
    def test_config_validation(self):
        """测试配置验证"""
        # 创建无效配置
        test_config = {
            'database': {
                'type': 'invalid_db_type'  # 无效的数据库类型
            },
            'crawler': {
                'max_depth': -1,  # 无效的深度
                'max_concurrent': 0  # 无效的并发数
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_config, f)
        
        # 应该抛出验证错误
        with pytest.raises(ValueError):
            ConfigManager(self.config_file)


if __name__ == '__main__':
    pytest.main([__file__])
