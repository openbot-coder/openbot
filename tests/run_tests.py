import sys
import os

# 添加项目根目录和src目录到Python路径
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./src"))

try:
    from tests.unit.test_config import (
        test_config_manager_default,
        test_config_manager_load_file,
    )

    print("Running test_config_manager_default...")
    test_config_manager_default()
    print("✓ test_config_manager_default passed")

    print("Running test_config_manager_load_file...")
    test_config_manager_load_file()
    print("✓ test_config_manager_load_file passed")

    print("\nAll tests passed!")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
