#!/usr/bin/env python3
import subprocess
import sys
import os

def run_command(cmd, cwd):
    """运行命令并返回输出"""
    print(f"\n{'='*60}")
    print(f"执行命令: {cmd}")
    print(f"工作目录: {cwd}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        print("标准输出:")
        print(result.stdout)
        
        if result.stderr:
            print("\n标准错误:")
            print(result.stderr)
        
        print(f"\n返回码: {result.returncode}")
        
        return {
            'command': cmd,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'success': result.returncode == 0
        }
    except Exception as e:
        print(f"执行命令时出错: {e}")
        return {
            'command': cmd,
            'error': str(e),
            'success': False
        }

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 测试命令列表
    commands = [
        'uv run python tests/run_tests.py',
        'uv run pytest tests/unit/test_config.py -v'
    ]
    
    results = []
    
    for cmd in commands:
        result = run_command(cmd, project_dir)
        results.append(result)
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    
    for i, result in enumerate(results, 1):
        status = "✓ 通过" if result.get('success') else "✗ 失败"
        print(f"{i}. {result['command']}: {status}")
    
    print(f"\n总计: {len(results)} 个命令")
    passed = sum(1 for r in results if r.get('success'))
    print(f"通过: {passed}")
    print(f"失败: {len(results) - passed}")

if __name__ == "__main__":
    main()
