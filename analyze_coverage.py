import os
import re

# 定义源代码和测试目录
SOURCE_DIR = os.path.join('src', 'openbot')
TEST_DIR = os.path.join('tests', 'unit')

# 统计源代码文件
source_files = []
for root, dirs, files in os.walk(SOURCE_DIR):
    for file in files:
        if file.endswith('.py'):
            source_files.append(os.path.join(root, file))

# 统计测试文件
test_files = []
for root, dirs, files in os.walk(TEST_DIR):
    for file in files:
        if file.endswith('.py'):
            test_files.append(os.path.join(root, file))

# 分析测试覆盖率
def analyze_coverage():
    print("=== 测试覆盖率分析 ===")
    print(f"源代码文件数量: {len(source_files)}")
    print(f"测试文件数量: {len(test_files)}")
    print()
    
    # 按模块分析
    modules = {}
    for source_file in source_files:
        # 获取模块路径
        module_path = os.path.relpath(source_file, SOURCE_DIR)
        module_name = module_path.replace('\\', '.').replace('.py', '')
        modules[module_name] = {
            'source_file': source_file,
            'test_file': None,
            'covered': False
        }
    
    # 匹配测试文件
    for test_file in test_files:
        test_name = os.path.basename(test_file).replace('test_', '').replace('.py', '')
        for module_name, info in modules.items():
            if test_name in module_name:
                info['test_file'] = test_file
                info['covered'] = True
                break
    
    # 输出覆盖率分析
    covered_count = sum(1 for info in modules.values() if info['covered'])
    total_count = len(modules)
    coverage_percent = (covered_count / total_count) * 100 if total_count > 0 else 0
    
    print(f"模块覆盖率: {covered_count}/{total_count} ({coverage_percent:.1f}%)")
    print()
    
    # 输出未覆盖的模块
    print("未覆盖的模块:")
    uncovered_modules = [name for name, info in modules.items() if not info['covered']]
    if uncovered_modules:
        for module in uncovered_modules:
            print(f"  - {module}")
    else:
        print("  所有模块都有测试覆盖")
    
    print()
    
    # 输出已覆盖的模块
    print("已覆盖的模块:")
    covered_modules = [(name, info['test_file']) for name, info in modules.items() if info['covered']]
    for module, test_file in covered_modules:
        test_rel_path = os.path.relpath(test_file, TEST_DIR)
        print(f"  - {module} (测试文件: {test_rel_path})")

if __name__ == "__main__":
    analyze_coverage()
