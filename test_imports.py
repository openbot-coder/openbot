#!/usr/bin/env python3
"""
Test script to verify all modules can be imported successfully
"""

import sys
import traceback

modules_to_test = [
    "openbot.config",
    "openbot.botflow.core",
    "openbot.botflow.session",
    "openbot.botflow.task",
    "openbot.botflow.processor",
    "openbot.botflow.evolution",
    "openbot.agents.core",
    "openbot.channels.base",
    "openbot.channels.console",
]

print("Testing module imports...")
print("=" * 50)

all_passed = True

for module_name in modules_to_test:
    try:
        __import__(module_name)
        print(f"✓ {module_name} imported successfully")
    except Exception as e:
        all_passed = False
        print(f"✗ {module_name} failed to import")
        print(f"  Error: {e}")
        traceback.print_exc()
    print("-" * 50)

print("=" * 50)
if all_passed:
    print("All modules imported successfully!")
    sys.exit(0)
else:
    print("Some modules failed to import.")
    sys.exit(1)
