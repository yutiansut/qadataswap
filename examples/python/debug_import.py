#!/usr/bin/env python3
"""
调试导入问题
"""

import sys
sys.path.insert(0, '/home/quantaxis/qadataswap/src/python')

print("Step 1: Basic Python import")

print("Step 2: Importing qadataswap module...")
try:
    import qadataswap
    print("✓ qadataswap imported successfully")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Step 3: Checking module attributes...")
try:
    print(f"Available: {dir(qadataswap)}")
except Exception as e:
    print(f"✗ Error checking attributes: {e}")

print("Step 4: Getting version...")
try:
    version = qadataswap.get_version()
    print(f"✓ Version: {version}")
except Exception as e:
    print(f"✗ Error getting version: {e}")

print("Step 5: Checking Arrow support...")
try:
    has_arrow = qadataswap.has_arrow_support()
    print(f"✓ Arrow support: {has_arrow}")
except Exception as e:
    print(f"✗ Error checking Arrow support: {e}")

print("Step 6: Accessing SharedDataFrame...")
try:
    SharedDataFrame = qadataswap.SharedDataFrame
    print(f"✓ SharedDataFrame class: {SharedDataFrame}")
except Exception as e:
    print(f"✗ Error accessing SharedDataFrame: {e}")

print("Step 7: Creating writer (this might crash)...")
try:
    writer = qadataswap.SharedDataFrame.create_writer("debug_test", size_mb=10)
    print("✓ Writer created successfully")
    writer.close()
    print("✓ Writer closed successfully")
except Exception as e:
    print(f"✗ Error creating writer: {e}")
    import traceback
    traceback.print_exc()

print("Debug completed successfully!")