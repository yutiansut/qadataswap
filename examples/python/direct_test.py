#!/usr/bin/env python3
"""
直接测试.so文件
"""

import sys
import os

# 直接添加.so文件路径
sys.path.insert(0, '/home/quantaxis/qadataswap/src/python')

print("Testing direct .so import...")

try:
    # 直接导入编译的模块
    import qadataswap as qs_module
    print("✓ Module imported")
    print(f"Module: {qs_module}")
    print(f"Module file: {qs_module.__file__}")
    print(f"Dir: {dir(qs_module)}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Import successful!")