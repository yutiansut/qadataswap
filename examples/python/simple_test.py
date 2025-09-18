#!/usr/bin/env python3
"""
简单测试QADataSwap功能
"""

import sys
import os
import time

# 添加路径
sys.path.insert(0, '/home/quantaxis/qadataswap/src/python')

def test_simple_version():
    """测试简化版本"""
    print("Testing simple version...")

    try:
        import qadataswap
        print(f"✓ Import successful, version: {qadataswap.get_version()}")
        print(f"✓ Arrow support: {qadataswap.has_arrow_support()}")

        # 测试基本功能
        print("\n--- Testing basic functionality ---")

        # 创建writer
        writer = qadataswap.SimpleSharedMemory.create_writer("test_simple", size_mb=10)
        print("✓ Writer created")

        # 写入数据
        test_data = b"Hello, QADataSwap! This is a test message."
        success = writer.write_bytes(test_data)
        print(f"✓ Write data: {success}")

        # 创建reader
        reader = qadataswap.SimpleSharedMemory.create_reader("test_simple")
        print("✓ Reader created")

        # 读取数据
        received_data = reader.read_bytes(timeout_ms=1000)
        print(f"✓ Read data: {len(received_data) if received_data else 0} bytes")

        if received_data:
            print(f"✓ Data match: {received_data == test_data}")
            print(f"✓ Received: {received_data.decode()}")
        else:
            print("✗ No data received")

        # 统计信息
        stats = writer.get_stats()
        print(f"✓ Writer stats: {stats}")

        stats = reader.get_stats()
        print(f"✓ Reader stats: {stats}")

        # 清理
        writer.close()
        reader.close()
        print("✓ Cleaned up")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

def test_multiprocess():
    """测试多进程"""
    import multiprocessing as mp

    def writer_func():
        try:
            import qadataswap
            writer = qadataswap.SimpleSharedMemory.create_writer("test_mp", size_mb=5)

            for i in range(5):
                data = f"Message {i}: {time.time()}".encode()
                success = writer.write_bytes(data)
                print(f"Writer: Sent message {i}, success: {success}")
                time.sleep(0.5)

            writer.close()
            print("Writer: Finished")
        except Exception as e:
            print(f"Writer error: {e}")

    def reader_func():
        try:
            import qadataswap
            time.sleep(0.2)  # Wait for writer to initialize
            reader = qadataswap.SimpleSharedMemory.create_reader("test_mp")

            for i in range(5):
                data = reader.read_bytes(timeout_ms=2000)
                if data:
                    print(f"Reader: Received: {data.decode()}")
                else:
                    print(f"Reader: No data for message {i}")
                    break

            reader.close()
            print("Reader: Finished")
        except Exception as e:
            print(f"Reader error: {e}")

    print("\n--- Testing multiprocess ---")

    writer_proc = mp.Process(target=writer_func)
    reader_proc = mp.Process(target=reader_func)

    writer_proc.start()
    reader_proc.start()

    writer_proc.join()
    reader_proc.join()

    print("✓ Multiprocess test completed")

if __name__ == "__main__":
    print("QADataSwap Simple Test")
    print("=" * 50)

    test_simple_version()
    test_multiprocess()

    print("\n" + "=" * 50)
    print("All tests completed!")