#!/usr/bin/env python3
"""测试 openbot 配置模块的基本功能"""

import sys
import os
import traceback
from pathlib import Path

# 添加项目源路径到 Python 路径
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.executable}")
print(f"项目根目录: {project_root}")
print(f"源文件路径: {src_path}")

def test_1_import_config():
    """测试 1: 导入 openbot.config 模块"""
    print("=" * 60)
    print("测试 1: 导入 openbot.config 模块")
    print("-" * 60)
    
    try:
        import openbot.config
        from openbot.config import ConfigManager, OpenbotConfig
        print("✓ 成功导入 openbot.config 模块")
        print(f"  - ConfigManager 类可用: {ConfigManager is not None}")
        print(f"  - OpenbotConfig 类可用: {OpenbotConfig is not None}")
        return True, "成功导入模块"
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        traceback.print_exc()
        return False, str(e)

def test_2_create_config_manager():
    """测试 2: 创建 ConfigManager 并加载默认配置"""
    print("\n" + "=" * 60)
    print("测试 2: 创建 ConfigManager 并加载默认配置")
    print("-" * 60)
    
    try:
        from openbot.config import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.get()
        
        print("✓ 成功创建 ConfigManager 并加载默认配置")
        print(f"  - 配置类型: {type(config).__name__}")
        print(f"  - Agent 名称: {config.agent_config.name}")
        print(f"  - 默认 Channels: {list(config.channels.keys())}")
        print(f"  - Evolution 启用: {config.evolution.enabled}")
        
        return True, "成功加载默认配置"
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False, str(e)

def test_3_load_examples_config():
    """测试 3: 从 examples/config.json 加载配置"""
    print("\n" + "=" * 60)
    print("测试 3: 从 examples/config.json 加载配置")
    print("-" * 60)
    
    try:
        from openbot.config import ConfigManager
        
        config_path = project_root / "examples" / "config.json"
        
        if not config_path.exists():
            return False, f"配置文件不存在: {config_path}"
        
        print(f"配置文件路径: {config_path}")
        
        # 设置环境变量
        os.environ["DOUBAO_API_KEY"] = "test_doubao_key_123"
        os.environ["MIMO_API_KEY"] = "test_mimo_key_456"
        
        config_manager = ConfigManager(str(config_path))
        config = config_manager.get()
        
        print("✓ 成功从 examples/config.json 加载配置")
        print(f"  - 模型配置数量: {len(config.model_configs)}")
        print(f"  - 模型配置: {list(config.model_configs.keys())}")
        
        # 验证环境变量是否正确解析
        for model_name, model_config in config.model_configs.items():
            print(f"  - {model_name} API Key 已设置: {model_config.api_key is not None}")
        
        return True, "成功加载示例配置"
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        traceback.print_exc()
        return False, str(e)

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("OPENBOT 配置模块测试")
    print("=" * 60)
    
    results = []
    
    # 执行所有测试
    results.append(("导入测试", test_1_import_config()))
    results.append(("默认配置测试", test_2_create_config_manager()))
    results.append(("示例配置加载测试", test_3_load_examples_config()))
    
    # 打印结果总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, (success, message) in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{test_name}: {status}")
        print(f"  详情: {message}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-" * 60)
    print(f"总计: {passed} 个通过, {failed} 个失败")
    print("=" * 60 + "\n")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
