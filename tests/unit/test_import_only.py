print("Test started")

# 测试基本导入
try:
    import sys
    import os

    print("Basic imports ok")
except Exception as e:
    print(f"Basic imports failed: {e}")

# 添加src路径
try:
    sys.path.insert(0, os.path.abspath("./src"))
    print("Added src to path")
except Exception as e:
    print(f"Failed to add src to path: {e}")

# 测试openbot包导入
try:
    import openbot

    print("Openbot package imported")
except Exception as e:
    print(f"Openbot import failed: {e}")
    import traceback

    traceback.print_exc()

print("Test completed")
