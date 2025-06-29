#!/usr/bin/env python3
"""
诊断数据库连接问题

检查网络连接、数据库服务状态和配置问题
"""

import sys
import socket
import time
import psycopg2
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def test_network_connectivity(host, port, timeout=10):
    """测试网络连接"""
    print(f"🌐 测试网络连接: {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ 网络连接正常")
            return True
        else:
            print(f"❌ 网络连接失败，错误代码: {result}")
            return False
            
    except Exception as e:
        print(f"❌ 网络连接异常: {e}")
        return False


def test_database_connection(host, port, database, user, password, timeout=10):
    """测试数据库连接"""
    print(f"🗄️ 测试数据库连接: {user}@{host}:{port}/{database}")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=timeout
        )
        
        # 测试简单查询
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        print(f"✅ 数据库连接成功")
        print(f"   版本: {version}")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 数据库连接异常: {e}")
        return False


def test_database_permissions(host, port, database, user, password):
    """测试数据库权限"""
    print(f"🔐 测试数据库权限...")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        
        # 测试基本权限
        tests = [
            ("SELECT", "SELECT 1"),
            ("CREATE TABLE", "CREATE TEMP TABLE test_table (id INT)"),
            ("INSERT", "INSERT INTO test_table VALUES (1)"),
            ("UPDATE", "UPDATE test_table SET id = 2"),
            ("DELETE", "DELETE FROM test_table"),
            ("DROP TABLE", "DROP TABLE test_table")
        ]
        
        permissions = {}
        for test_name, sql in tests:
            try:
                cursor.execute(sql)
                permissions[test_name] = True
                print(f"   ✅ {test_name}")
            except Exception as e:
                permissions[test_name] = False
                print(f"   ❌ {test_name}: {e}")
        
        cursor.close()
        conn.close()
        
        return permissions
        
    except Exception as e:
        print(f"❌ 权限测试失败: {e}")
        return {}


def check_database_tables(host, port, database, user, password):
    """检查数据库表结构"""
    print(f"📋 检查数据库表结构...")
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"   发现 {len(tables)} 个表:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"     {table}: {count} 条记录")
        
        cursor.close()
        conn.close()
        
        return tables
        
    except Exception as e:
        print(f"❌ 表结构检查失败: {e}")
        return []


def diagnose_database(name, host, port, database, user, password):
    """诊断单个数据库"""
    print(f"\n🔍 诊断{name} ({host}:{port})")
    print("=" * 60)
    
    results = {}
    
    # 1. 网络连接测试
    results['network'] = test_network_connectivity(host, port)
    
    if not results['network']:
        print(f"\n❌ {name}网络连接失败，跳过后续测试")
        return results
    
    # 2. 数据库连接测试
    results['database'] = test_database_connection(host, port, database, user, password)
    
    if not results['database']:
        print(f"\n❌ {name}数据库连接失败，跳过后续测试")
        return results
    
    # 3. 权限测试
    results['permissions'] = test_database_permissions(host, port, database, user, password)
    
    # 4. 表结构检查
    results['tables'] = check_database_tables(host, port, database, user, password)
    
    return results


def suggest_solutions(primary_results, secondary_results):
    """根据诊断结果提供解决方案"""
    print(f"\n💡 解决方案建议:")
    print("=" * 60)
    
    # 检查主数据库问题
    if not primary_results.get('network'):
        print("🔧 主数据库网络问题:")
        print("   1. 检查网络连接: ping 113.29.231.99")
        print("   2. 检查防火墙设置，确保5432端口开放")
        print("   3. 检查VPN或代理设置")
        print("   4. 联系网络管理员检查网络路由")
    
    if primary_results.get('network') and not primary_results.get('database'):
        print("🔧 主数据库服务问题:")
        print("   1. 检查PostgreSQL服务是否运行")
        print("   2. 检查数据库配置文件 postgresql.conf")
        print("   3. 检查 pg_hba.conf 允许远程连接")
        print("   4. 重启PostgreSQL服务")
    
    # 检查备数据库问题
    if not secondary_results.get('network'):
        print("🔧 备数据库网络问题:")
        print("   1. 检查网络连接: ping 113.29.232.245")
        print("   2. 检查防火墙设置，确保5432端口开放")
    
    # 权限问题
    primary_perms = primary_results.get('permissions', {})
    secondary_perms = secondary_results.get('permissions', {})
    
    if primary_perms and not all(primary_perms.values()):
        print("🔧 主数据库权限问题:")
        print("   1. 确保用户有足够权限")
        print("   2. 运行: GRANT ALL PRIVILEGES ON DATABASE image_crawler TO postgres;")
    
    # 表结构问题
    primary_tables = primary_results.get('tables', [])
    secondary_tables = secondary_results.get('tables', [])
    
    if not primary_tables:
        print("🔧 主数据库表结构问题:")
        print("   1. 运行数据库初始化: python setup_postgresql_databases.py")
        print("   2. 检查数据库迁移脚本")
    
    # 临时解决方案
    print("\n🚀 临时解决方案:")
    if not primary_results.get('network') or not primary_results.get('database'):
        print("   1. 使用本地SQLite数据库:")
        print("      修改配置文件使用 sqlite:///data/crawler.db")
        print("   2. 或者暂时禁用HA功能，使用单机模式")


def main():
    """主诊断函数"""
    print("🔍 数据库连接诊断工具")
    print("=" * 60)
    
    # 数据库配置
    databases = [
        {
            'name': '主数据库',
            'host': '113.29.231.99',
            'port': 5432,
            'database': 'image_crawler',
            'user': 'postgres',
            'password': 'Abcdefg6'
        },
        {
            'name': '备数据库',
            'host': '113.29.232.245',
            'port': 5432,
            'database': 'image_crawler',
            'user': 'postgres',
            'password': 'Abcdefg6'
        }
    ]
    
    # 诊断每个数据库
    results = {}
    for db_config in databases:
        results[db_config['name']] = diagnose_database(**db_config)
    
    # 总结结果
    print(f"\n📊 诊断结果总结:")
    print("=" * 60)
    
    for db_name, db_results in results.items():
        print(f"\n{db_name}:")
        print(f"  网络连接: {'✅' if db_results.get('network') else '❌'}")
        print(f"  数据库连接: {'✅' if db_results.get('database') else '❌'}")
        
        perms = db_results.get('permissions', {})
        if perms:
            perm_ok = all(perms.values())
            print(f"  数据库权限: {'✅' if perm_ok else '❌'}")
        
        tables = db_results.get('tables', [])
        print(f"  表结构: {'✅' if tables else '❌'} ({len(tables)} 个表)")
    
    # 提供解决方案
    suggest_solutions(
        results.get('主数据库', {}),
        results.get('备数据库', {})
    )
    
    # 检查是否可以启动系统
    primary_ok = (results.get('主数据库', {}).get('network') and 
                  results.get('主数据库', {}).get('database'))
    secondary_ok = (results.get('备数据库', {}).get('network') and 
                    results.get('备数据库', {}).get('database'))
    
    print(f"\n🎯 系统启动建议:")
    if primary_ok and secondary_ok:
        print("✅ 可以启动完整的HA系统")
    elif primary_ok:
        print("⚠️ 可以启动单机模式（主数据库）")
    elif secondary_ok:
        print("⚠️ 可以启动单机模式（备数据库）")
    else:
        print("❌ 建议使用本地SQLite数据库")


if __name__ == "__main__":
    main()
