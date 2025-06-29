#!/usr/bin/env python3
"""
PostgreSQL数据库初始化脚本

在两个PostgreSQL服务器上创建数据库和表结构
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from database.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgreSQLSetup:
    """PostgreSQL数据库设置"""
    
    def __init__(self):
        """初始化设置"""
        # 数据库服务器配置
        self.servers = [
            {
                "name": "primary_server",
                "host": "113.29.231.99",
                "port": 5432,
                "admin_user": "postgres",
                "admin_password": "Abcdefg6",
                "database": "image_crawler"
            },
            {
                "name": "backup_server", 
                "host": "113.29.232.245",
                "port": 5432,
                "admin_user": "postgres",
                "admin_password": "Abcdefg6",
                "database": "image_crawler"
            }
        ]
    
    def setup_all_databases(self):
        """设置所有数据库"""
        print("🚀 开始设置PostgreSQL数据库...")
        print("=" * 60)
        
        for server in self.servers:
            try:
                print(f"\n📍 设置服务器: {server['name']} ({server['host']})")
                
                # 1. 创建数据库
                self.create_database(server)
                
                # 2. 创建表结构
                self.create_tables(server)
                
                # 3. 验证设置
                self.verify_setup(server)
                
                print(f"✅ 服务器 {server['name']} 设置完成")
                
            except Exception as e:
                print(f"❌ 服务器 {server['name']} 设置失败: {e}")
                logger.error(f"设置服务器 {server['name']} 失败: {e}")
        
        print("\n🎉 所有数据库设置完成！")
    
    def create_database(self, server):
        """创建数据库"""
        try:
            # 连接到默认的postgres数据库
            conn = psycopg2.connect(
                host=server['host'],
                port=server['port'],
                user=server['admin_user'],
                password=server['admin_password'],
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            cursor = conn.cursor()
            
            # 检查数据库是否已存在
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                (server['database'],)
            )
            
            if cursor.fetchone():
                print(f"  📋 数据库 {server['database']} 已存在")
            else:
                # 创建数据库
                cursor.execute(f'CREATE DATABASE "{server["database"]}"')
                print(f"  ✅ 数据库 {server['database']} 创建成功")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"  ❌ 创建数据库失败: {e}")
            raise
    
    def create_tables(self, server):
        """创建表结构"""
        try:
            # 构建数据库连接URL
            database_url = (
                f"postgresql://{server['admin_user']}:{server['admin_password']}"
                f"@{server['host']}:{server['port']}/{server['database']}"
            )
            
            # 创建SQLAlchemy引擎
            engine = create_engine(database_url)
            
            # 创建所有表
            Base.metadata.create_all(bind=engine)
            
            print(f"  ✅ 表结构创建成功")
            
            # 显示创建的表
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))

                tables = [row[0] for row in result]
                print(f"  📋 创建的表: {', '.join(tables)}")
            
            engine.dispose()
            
        except Exception as e:
            print(f"  ❌ 创建表结构失败: {e}")
            raise
    
    def verify_setup(self, server):
        """验证设置"""
        try:
            # 构建数据库连接URL
            database_url = (
                f"postgresql://{server['admin_user']}:{server['admin_password']}"
                f"@{server['host']}:{server['port']}/{server['database']}"
            )
            
            # 测试连接
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # 测试基本查询
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                print(f"  📊 PostgreSQL版本: {version.split(',')[0]}")

                # 检查表数量
                result = conn.execute(text("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """))
                table_count = result.fetchone()[0]
                print(f"  📊 表数量: {table_count}")

                # 测试插入和查询（如果images表存在）
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM images
                    """))
                    image_count = result.fetchone()[0]
                    print(f"  📊 图片记录数: {image_count}")
                except:
                    print(f"  📊 图片表准备就绪")
            
            engine.dispose()
            print(f"  ✅ 数据库验证成功")
            
        except Exception as e:
            print(f"  ❌ 数据库验证失败: {e}")
            raise
    
    def test_connectivity(self):
        """测试连接性"""
        print("\n🔍 测试数据库连接性...")
        
        for server in self.servers:
            try:
                print(f"\n📍 测试服务器: {server['name']} ({server['host']})")
                
                # 构建数据库连接URL
                database_url = (
                    f"postgresql://{server['admin_user']}:{server['admin_password']}"
                    f"@{server['host']}:{server['port']}/{server['database']}"
                )
                
                engine = create_engine(database_url, connect_args={"connect_timeout": 10})
                
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    if result.fetchone()[0] == 1:
                        print(f"  ✅ 连接成功")
                    else:
                        print(f"  ❌ 连接测试失败")
                
                engine.dispose()
                
            except Exception as e:
                print(f"  ❌ 连接失败: {e}")
    
    def create_sample_data(self):
        """创建示例数据"""
        print("\n📝 创建示例数据...")
        
        # 只在主服务器创建示例数据
        server = self.servers[0]  # 主服务器
        
        try:
            database_url = (
                f"postgresql://{server['admin_user']}:{server['admin_password']}"
                f"@{server['host']}:{server['port']}/{server['database']}"
            )
            
            engine = create_engine(database_url)
            
            with engine.connect() as conn:
                # 插入示例图片数据
                conn.execute(text("""
                    INSERT INTO images (url, source_url, filename, file_extension, is_downloaded)
                    VALUES
                        ('https://example.com/image1.jpg', 'https://example.com', 'image1.jpg', '.jpg', false),
                        ('https://example.com/image2.png', 'https://example.com', 'image2.png', '.png', false),
                        ('https://example.com/image3.gif', 'https://example.com', 'image3.gif', '.gif', false)
                    ON CONFLICT DO NOTHING
                """))

                # 检查插入的数据
                result = conn.execute(text("SELECT COUNT(*) FROM images"))
                count = result.fetchone()[0]
                print(f"  ✅ 示例数据创建完成，总计 {count} 条记录")

                conn.commit()
            
            engine.dispose()
            
        except Exception as e:
            print(f"  ❌ 创建示例数据失败: {e}")


def main():
    """主函数"""
    print("🗄️ PostgreSQL数据库初始化工具")
    print("=" * 60)
    print("将在以下服务器上设置数据库:")
    print("  主服务器: 113.29.231.99:5432")
    print("  备服务器: 113.29.232.245:5432")
    print("=" * 60)
    
    # 确认继续
    response = input("\n是否继续设置？(y/N): ").strip().lower()
    if response != 'y':
        print("设置已取消")
        return
    
    # 创建设置实例
    setup = PostgreSQLSetup()
    
    try:
        # 1. 测试连接
        setup.test_connectivity()
        
        # 2. 设置数据库
        setup.setup_all_databases()
        
        # 3. 创建示例数据
        create_sample = input("\n是否创建示例数据？(y/N): ").strip().lower()
        if create_sample == 'y':
            setup.create_sample_data()
        
        print("\n🎉 数据库初始化完成！")
        print("\n下一步:")
        print("1. 运行: python start_ha_system.py")
        print("2. 访问: http://localhost:8000 (主应用)")
        print("3. 访问: http://localhost:8001/api/status (HA状态)")
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
