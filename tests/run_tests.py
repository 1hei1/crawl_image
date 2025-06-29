#!/usr/bin/env python3
"""
测试运行脚本

运行所有测试用例并生成报告
"""

import sys
import os
from pathlib import Path
import pytest
import subprocess

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_tests():
    """运行所有测试"""
    print("🧪 开始运行测试用例...")
    print("=" * 60)
    
    # 测试参数
    test_args = [
        '--verbose',           # 详细输出
        '--tb=short',         # 简短的错误回溯
        '--color=yes',        # 彩色输出
        '--durations=10',     # 显示最慢的10个测试
        '--cov=crawler',      # 代码覆盖率（如果安装了pytest-cov）
        '--cov=config',
        '--cov=database',
        '--cov-report=term-missing',  # 显示未覆盖的行
        str(Path(__file__).parent)    # 测试目录
    ]
    
    try:
        # 运行pytest
        result = pytest.main(test_args)
        
        if result == 0:
            print("\n✅ 所有测试通过!")
        else:
            print(f"\n❌ 测试失败，退出代码: {result}")
            
        return result
        
    except Exception as e:
        print(f"❌ 运行测试时发生错误: {e}")
        return 1


def check_dependencies():
    """检查测试依赖"""
    print("🔍 检查测试依赖...")
    
    required_packages = [
        'pytest',
        'pytest-asyncio',
    ]
    
    optional_packages = [
        'pytest-cov',      # 代码覆盖率
        'pytest-html',     # HTML报告
        'pytest-xdist',    # 并行测试
    ]
    
    missing_required = []
    missing_optional = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            missing_required.append(package)
            print(f"❌ {package} (必需)")
    
    for package in optional_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            missing_optional.append(package)
            print(f"⚠️  {package} (可选)")
    
    if missing_required:
        print(f"\n❌ 缺少必需的测试依赖: {', '.join(missing_required)}")
        print("请运行: pip install " + " ".join(missing_required))
        return False
    
    if missing_optional:
        print(f"\n⚠️  缺少可选的测试依赖: {', '.join(missing_optional)}")
        print("建议运行: pip install " + " ".join(missing_optional))
    
    print("✅ 依赖检查完成\n")
    return True


def run_specific_test(test_file):
    """运行特定的测试文件"""
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        print(f"❌ 测试文件不存在: {test_file}")
        return 1
    
    print(f"🧪 运行测试文件: {test_file}")
    
    result = pytest.main([
        '--verbose',
        '--tb=short',
        '--color=yes',
        str(test_path)
    ])
    
    return result


def generate_html_report():
    """生成HTML测试报告"""
    try:
        import pytest_html
        
        print("📊 生成HTML测试报告...")
        
        report_path = Path(__file__).parent / 'reports' / 'test_report.html'
        report_path.parent.mkdir(exist_ok=True)
        
        result = pytest.main([
            '--html=' + str(report_path),
            '--self-contained-html',
            str(Path(__file__).parent)
        ])
        
        if result == 0:
            print(f"✅ HTML报告已生成: {report_path}")
        
        return result
        
    except ImportError:
        print("⚠️  pytest-html 未安装，跳过HTML报告生成")
        return 0


def run_coverage_report():
    """运行代码覆盖率报告"""
    try:
        import pytest_cov
        
        print("📈 生成代码覆盖率报告...")
        
        # 生成HTML覆盖率报告
        coverage_dir = Path(__file__).parent / 'reports' / 'coverage'
        coverage_dir.mkdir(parents=True, exist_ok=True)
        
        result = pytest.main([
            '--cov=crawler',
            '--cov=config',
            '--cov=database',
            '--cov-report=html:' + str(coverage_dir),
            '--cov-report=term',
            str(Path(__file__).parent)
        ])
        
        if result == 0:
            print(f"✅ 覆盖率报告已生成: {coverage_dir}/index.html")
        
        return result
        
    except ImportError:
        print("⚠️  pytest-cov 未安装，跳过覆盖率报告生成")
        return 0


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='运行图片爬虫测试用例')
    parser.add_argument('--check-deps', action='store_true', help='只检查依赖')
    parser.add_argument('--file', help='运行特定的测试文件')
    parser.add_argument('--html', action='store_true', help='生成HTML报告')
    parser.add_argument('--coverage', action='store_true', help='生成覆盖率报告')
    parser.add_argument('--all', action='store_true', help='运行所有测试和报告')
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    if args.check_deps:
        return 0
    
    # 运行特定测试文件
    if args.file:
        return run_specific_test(args.file)
    
    # 运行所有测试和报告
    if args.all:
        result = run_tests()
        if result == 0:
            generate_html_report()
            run_coverage_report()
        return result
    
    # 生成HTML报告
    if args.html:
        return generate_html_report()
    
    # 生成覆盖率报告
    if args.coverage:
        return run_coverage_report()
    
    # 默认运行所有测试
    return run_tests()


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行测试时发生未知错误: {e}")
        sys.exit(1)
