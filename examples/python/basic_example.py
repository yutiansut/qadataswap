#!/usr/bin/env python3
"""
QADataSwap Python Basic Example with Polars

This example demonstrates basic zero-copy data transfer between processes
using Polars DataFrames.
"""

import polars as pl
import time
import multiprocessing as mp
from qadataswap import SharedDataFrame


def writer_process(name: str, num_rows: int = 1000000):
    """Writer process that generates and writes data"""
    print(f"Writer: Starting with {num_rows} rows")

    # Create writer
    writer = SharedDataFrame.create_writer(name, size_mb=100)

    # Generate test data
    df = pl.DataFrame({
        "id": pl.arange(0, num_rows, eager=True),
        "price": pl.arange(0, num_rows, eager=True).cast(pl.Float64) * 1.5 + 100.0,
        "volume": pl.arange(0, num_rows, eager=True) * 10,
        "symbol": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"] * (num_rows // 5),
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1),
            end=pl.datetime(2024, 12, 31),
            interval="1m",
            eager=True
        ).head(num_rows)
    })

    print(f"Writer: Generated DataFrame with shape {df.shape}")
    print("Writer: Sample data:")
    print(df.head())

    # Write data (zero-copy)
    start_time = time.time()
    writer.write(df)
    write_time = time.time() - start_time

    print(f"Writer: Data written in {write_time:.4f} seconds")

    # Get statistics
    stats = writer.get_stats()
    print(f"Writer: Statistics: {stats}")

    writer.close()
    print("Writer: Finished")


def reader_process(name: str, expected_rows: int = 1000000):
    """Reader process that reads and verifies data"""
    print("Reader: Starting")

    # Wait a bit for writer to initialize
    time.sleep(0.5)

    # Create reader
    reader = SharedDataFrame.create_reader(name)

    # Read data (zero-copy)
    start_time = time.time()
    df = reader.read(timeout_ms=10000)  # 10 second timeout
    read_time = time.time() - start_time

    if df is None:
        print("Reader: No data received (timeout)")
        return

    print(f"Reader: Data read in {read_time:.4f} seconds")
    print(f"Reader: Received DataFrame with shape {df.shape}")

    # Verify data integrity
    assert df.height == expected_rows, f"Expected {expected_rows} rows, got {df.height}"
    assert df.width == 5, f"Expected 5 columns, got {df.width}"

    print("Reader: Sample data:")
    print(df.head())

    # Perform some operations
    result = (df
              .filter(pl.col("price") > 500)
              .group_by("symbol")
              .agg([
                  pl.col("volume").sum().alias("total_volume"),
                  pl.col("price").mean().alias("avg_price"),
                  pl.col("id").count().alias("count")
              ])
              .sort("total_volume", descending=True))

    print("Reader: Aggregation result:")
    print(result)

    # Get statistics
    stats = reader.get_stats()
    print(f"Reader: Statistics: {stats}")

    reader.close()
    print("Reader: Finished")


def benchmark_comparison():
    """Compare performance with traditional methods"""
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)

    num_rows = 1000000
    df = pl.DataFrame({
        "id": pl.arange(0, num_rows, eager=True),
        "value": pl.arange(0, num_rows, eager=True).cast(pl.Float64) * 1.5,
    })

    # QADataSwap method
    print("Testing QADataSwap (zero-copy)...")

    def qads_write():
        writer = SharedDataFrame.create_writer("benchmark", size_mb=50)
        start = time.time()
        writer.write(df)
        return time.time() - start

    def qads_read():
        time.sleep(0.1)  # Ensure writer is ready
        reader = SharedDataFrame.create_reader("benchmark")
        start = time.time()
        result = reader.read(timeout_ms=5000)
        elapsed = time.time() - start
        return elapsed, result.height if result else 0

    write_time = qads_write()
    read_time, rows_read = qads_read()

    print(f"QADataSwap write: {write_time:.4f}s")
    print(f"QADataSwap read:  {read_time:.4f}s ({rows_read} rows)")

    # Traditional method (serialization)
    print("\nTesting traditional serialization...")

    start = time.time()
    serialized = df.write_ipc(None)
    serialize_time = time.time() - start

    start = time.time()
    df_restored = pl.read_ipc(serialized)
    deserialize_time = time.time() - start

    print(f"Serialize:   {serialize_time:.4f}s")
    print(f"Deserialize: {deserialize_time:.4f}s")

    # Memory usage comparison
    memory_original = df.estimated_size("mb")
    memory_serialized = len(serialized) / 1024 / 1024

    print(f"\nMemory usage:")
    print(f"Original DataFrame: {memory_original:.2f} MB")
    print(f"Serialized size:    {memory_serialized:.2f} MB")
    print(f"QADataSwap overhead: ~0 MB (zero-copy)")

    # Performance summary
    total_qads = write_time + read_time
    total_traditional = serialize_time + deserialize_time
    speedup = total_traditional / total_qads if total_qads > 0 else float('inf')

    print(f"\nPerformance Summary:")
    print(f"QADataSwap total:   {total_qads:.4f}s")
    print(f"Traditional total:  {total_traditional:.4f}s")
    print(f"Speedup:           {speedup:.1f}x")


def main():
    """Main function demonstrating basic usage"""
    print("QADataSwap Python Basic Example with Polars")
    print("=" * 50)

    shared_name = "basic_example"
    num_rows = 1000000

    # Start writer and reader processes
    writer_proc = mp.Process(target=writer_process, args=(shared_name, num_rows))
    reader_proc = mp.Process(target=reader_process, args=(shared_name, num_rows))

    print("Starting writer and reader processes...")
    writer_proc.start()
    reader_proc.start()

    # Wait for both processes to complete
    writer_proc.join()
    reader_proc.join()

    print("\nBasic example completed successfully!")

    # Run performance comparison
    benchmark_comparison()


if __name__ == "__main__":
    main()