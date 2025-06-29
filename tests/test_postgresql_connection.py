#!/usr/bin/env python3
"""
PostgreSQL连接测试脚本

快速测试两个PostgreSQL服务器的连接性
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from sqlalchemy import create_engine, text
import time


def test_postgresql_connections():
    """测试PostgreSQL连接"""
    
    # 数据库配置
    databases = [
        {
            "name": "主数据库",
            "host": "113.29.231.99",
            "port": 5432,
            "user": "postgres",
            "password": "Abcdefg6",
            "database": "postgres"  # 先连接默认数据库
        },
        {
            "name": "备数据库", 
            "host": "113.29.232.245",
            "port": 5432,
            "user": "postgres",
            "password": "Abcdefg6",
            "database": "postgres"  # 先连接默认数据库
        }
    ]
    
    print("🔗 PostgreSQL连接测试")
    print("=" * 50)
    
    for db_config in databases:
        print(f"\n📍 测试 {db_config['name']} ({db_config['host']})")
        
        # 1. 测试基本连接
        try:
            print("  🔍 测试基本连接...")
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database'],
                connect_timeout=10
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            print(f"  ✅ 连接成功")
            print(f"  📊 版本: {version.split(',')[0]}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"  ❌ 连接失败: {e}")
            continue
        
        # 2. 测试SQLAlchemy连接
        try:
            print("  🔍 测试SQLAlchemy连接...")
            database_url = (
                f"postgresql://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )
            
            engine = create_engine(database_url, connect_args={"connect_timeout": 10})
            
            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_database(), current_user"))
                db_name, user = result.fetchone()
                print(f"  ✅ SQLAlchemy连接成功")
                print(f"  📊 数据库: {db_name}, 用户: {user}")
            
            engine.dispose()
            
        except Exception as e:
            print(f"  ❌ SQLAlchemy连接失败: {e}")
            continue
        
        # 3. 检查image_crawler数据库
        try:
            print("  🔍 检查image_crawler数据库...")
            
            # 连接到默认数据库检查image_crawler是否存在
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database='postgres',
                connect_timeout=10
            )
            
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'image_crawler'"
            )
            
            if cursor.fetchone():
                print("  ✅ image_crawler数据库已存在")
                
                # 测试连接到image_crawler数据库
                cursor.close()
                conn.close()
                
                crawler_url = (
                    f"postgresql://{db_config['user']}:{db_config['password']}"
                    f"@{db_config['host']}:{db_config['port']}/image_crawler"
                )
                
                engine = create_engine(crawler_url, connect_args={"connect_timeout": 10})
                with engine.connect() as conn:
                    # 检查表
                    result = conn.execute(text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        ORDER BY table_name
                    """))
                    tables = [row[0] for row in result]
                    
                    if tables:
                        print(f"  📋 发现表: {', '.join(tables)}")
                    else:
                        print("  📋 数据库为空，需要创建表结构")
                
                engine.dispose()
                
            else:
                print("  ⚠️ image_crawler数据库不存在，需要创建")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"  ❌ 检查image_crawler数据库失败: {e}")
        
        # 4. 测试网络延迟
        try:
            print("  🔍 测试网络延迟...")
            
            start_time = time.time()
            conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database'],
                connect_timeout=10
            )
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000
            print(f"  ⏱️ 连接延迟: {latency:.2f}ms")
            
            conn.close()
            
        except Exception as e:
            print(f"  ❌ 延迟测试失败: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 测试完成")
    print("\n下一步建议:")
    print("1. 如果连接成功但数据库不存在，运行: python setup_postgresql_databases.py")
    print("2. 如果表结构不存在，运行数据库初始化")
    print("3. 启动HA系统: python start_postgresql_ha.py")


def test_ha_config():
    """测试HA配置"""
    print("\n🔧 测试HA配置文件")
    print("-" * 30)
    
    try:
        from config.ha_config_loader import load_ha_config
        
        nodes, local_node_name, config = load_ha_config()
        
        print(f"✅ 配置加载成功")
        print(f"📍 本地节点: {local_node_name}")
        print(f"📊 节点数量: {len(nodes)}")
        
        for node in nodes:
            print(f"  - {node.name}: {node.server.host}:{node.server.port} ({node.role.value})")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False


def main():
    """主函数"""
    print("🧪 PostgreSQL高可用系统连接测试")
    print("=" * 50)
    
    # 测试数据库连接
    test_postgresql_connections()
    
    # 测试HA配置
    test_ha_config()


if __name__ == "__main__":
    main()
