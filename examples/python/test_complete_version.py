#!/usr/bin/env python3
"""
测试完整版QADataSwap功能 - 包括Polars和Arrow支持
"""

import sys
import os
import time
import multiprocessing as mp

# 添加包路径
sys.path.insert(0, '/home/quantaxis/qadataswap/src/python')

def test_import():
    """测试导入功能"""
    print("Testing import...")

    try:
        import qadataswap
        print(f"✓ Import successful")
        print(f"✓ Version: {qadataswap.get_version()}")
        print(f"✓ Arrow support: {qadataswap.has_arrow_support()}")
        print(f"✓ Available classes: {[x for x in dir(qadataswap) if not x.startswith('_')]}")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functionality():
    """测试基本功能"""
    print("\n--- Testing Basic Functionality ---")

    try:
        import qadataswap
        import polars as pl

        # 创建测试数据
        df = pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
            "value": [10.5, 20.3, 30.1, 40.8, 50.2],
            "active": [True, False, True, True, False]
        })

        print(f"✓ Created test DataFrame with shape {df.shape}")
        print("Original data:")
        print(df)

        # 创建writer
        writer = qadataswap.SharedDataFrame.create_writer("test_basic", size_mb=50)
        print("✓ Writer created")

        # 写入数据
        writer.write(df)
        print("✓ Data written to shared memory")

        # 创建reader
        reader = qadataswap.SharedDataFrame.create_reader("test_basic")
        print("✓ Reader created")

        # 读取数据
        df_read = reader.read(timeout_ms=5000)
        print("✓ Data read from shared memory")

        if df_read is not None:
            print(f"✓ Read DataFrame with shape {df_read.shape}")
            print("Read data:")
            print(df_read)

            # 验证数据一致性
            if df.equals(df_read):
                print("✓ Data integrity verified!")
            else:
                print("✗ Data mismatch!")
                print("Differences:")
                print("Original:")
                print(df)
                print("Read:")
                print(df_read)
        else:
            print("✗ No data received")

        # 获取统计信息
        writer_stats = writer.get_stats()
        reader_stats = reader.get_stats()
        print(f"✓ Writer stats: {writer_stats}")
        print(f"✓ Reader stats: {reader_stats}")

        # 清理
        writer.close()
        reader.close()
        print("✓ Resources cleaned up")

        return True

    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def writer_process(shared_name, num_iterations=3):
    """写入进程"""
    try:
        import qadataswap
        import polars as pl
        import time

        print(f"Writer: Starting with {num_iterations} iterations")

        writer = qadataswap.SharedDataFrame.create_writer(shared_name, size_mb=100)

        for i in range(num_iterations):
            # 创建不同的数据
            df = pl.DataFrame({
                "iteration": [i] * 1000,
                "id": list(range(1000)),
                "value": [x * (i + 1) * 0.1 for x in range(1000)],
                "timestamp": [time.time()] * 1000
            })

            print(f"Writer: Sending iteration {i}, shape: {df.shape}")
            writer.write(df)
            print(f"Writer: Iteration {i} sent successfully")

            time.sleep(1)  # 间隔1秒

        print("Writer: All iterations completed")
        stats = writer.get_stats()
        print(f"Writer: Final stats: {stats}")

        writer.close()
        print("Writer: Closed")

    except Exception as e:
        print(f"Writer error: {e}")
        import traceback
        traceback.print_exc()

def reader_process(shared_name, num_iterations=3):
    """读取进程"""
    try:
        import qadataswap
        import time

        print("Reader: Starting")

        # 等待writer初始化
        time.sleep(0.5)

        reader = qadataswap.SharedDataFrame.create_reader(shared_name)

        for i in range(num_iterations):
            print(f"Reader: Waiting for iteration {i}")

            df = reader.read(timeout_ms=10000)  # 10秒超时

            if df is not None:
                print(f"Reader: Received iteration {i}, shape: {df.shape}")
                print(f"Reader: Sample data from iteration {i}:")
                print(df.head(3))

                # 验证数据
                expected_iteration = i
                actual_iteration = df["iteration"][0]
                if actual_iteration == expected_iteration:
                    print(f"✓ Iteration {i} data verified")
                else:
                    print(f"✗ Iteration mismatch: expected {expected_iteration}, got {actual_iteration}")

            else:
                print(f"✗ No data received for iteration {i}")

        print("Reader: All iterations completed")
        stats = reader.get_stats()
        print(f"Reader: Final stats: {stats}")

        reader.close()
        print("Reader: Closed")

    except Exception as e:
        print(f"Reader error: {e}")
        import traceback
        traceback.print_exc()

def test_multiprocess():
    """测试多进程通信"""
    print("\n--- Testing Multiprocess Communication ---")

    shared_name = "test_multiprocess"
    num_iterations = 3

    # 创建进程
    writer_proc = mp.Process(target=writer_process, args=(shared_name, num_iterations))
    reader_proc = mp.Process(target=reader_process, args=(shared_name, num_iterations))

    print("Starting writer and reader processes...")

    # 启动进程
    writer_proc.start()
    reader_proc.start()

    # 等待完成
    writer_proc.join(timeout=30)  # 30秒超时
    reader_proc.join(timeout=30)

    # 检查进程状态
    if writer_proc.is_alive():
        print("Warning: Writer process still running, terminating...")
        writer_proc.terminate()
        writer_proc.join()

    if reader_proc.is_alive():
        print("Warning: Reader process still running, terminating...")
        reader_proc.terminate()
        reader_proc.join()

    print("✓ Multiprocess test completed")

def test_performance():
    """性能测试"""
    print("\n--- Performance Test ---")

    try:
        import qadataswap
        import polars as pl
        import time

        # 创建大数据集
        num_rows = 100000
        df = pl.DataFrame({
            "id": list(range(num_rows)),
            "value1": [x * 0.1 for x in range(num_rows)],
            "value2": [x * 0.2 for x in range(num_rows)],
            "category": ["A", "B", "C", "D"] * (num_rows // 4),
        })

        data_size_mb = df.estimated_size("mb")
        print(f"Test data: {num_rows} rows, {data_size_mb:.2f} MB")

        # 测试写入性能
        writer = qadataswap.SharedDataFrame.create_writer("perf_test", size_mb=200)

        start_time = time.time()
        writer.write(df)
        write_time = time.time() - start_time

        print(f"Write time: {write_time:.4f} seconds")
        print(f"Write throughput: {data_size_mb / write_time:.2f} MB/s")

        # 测试读取性能
        reader = qadataswap.SharedDataFrame.create_reader("perf_test")

        start_time = time.time()
        df_read = reader.read(timeout_ms=5000)
        read_time = time.time() - start_time

        if df_read is not None:
            print(f"Read time: {read_time:.4f} seconds")
            print(f"Read throughput: {data_size_mb / read_time:.2f} MB/s")
            print(f"✓ Performance test completed")
        else:
            print("✗ Performance test failed - no data read")

        # 清理
        writer.close()
        reader.close()

    except Exception as e:
        print(f"✗ Performance test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试函数"""
    print("QADataSwap Complete Version Test")
    print("=" * 60)

    # 测试导入
    if not test_import():
        print("Cannot proceed without successful import")
        return

    # 测试基本功能
    if test_basic_functionality():
        print("\n✓ Basic functionality test passed")
    else:
        print("\n✗ Basic functionality test failed")
        return

    # 测试多进程
    test_multiprocess()

    # 性能测试
    test_performance()

    print("\n" + "=" * 60)
    print("All tests completed!")

if __name__ == "__main__":
    main()