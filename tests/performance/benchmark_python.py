#!/usr/bin/env python3
"""
QADataSwap Python Performance Benchmark

Comprehensive benchmarking suite comparing QADataSwap zero-copy transfer
with traditional serialization methods using Polars DataFrames.
"""

import polars as pl
import time
import multiprocessing as mp
import numpy as np
import psutil
import pickle
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from qadataswap import SharedDataFrame, SharedDataStream
except ImportError:
    print("QADataSwap not installed. Please run 'make python-install' first.")
    exit(1)


@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""
    method: str
    data_size_mb: float
    rows: int
    cols: int
    write_time: float
    read_time: float
    total_time: float
    memory_usage_mb: float
    throughput_mb_s: float
    operations_per_sec: float


class PerformanceBenchmark:
    """Comprehensive performance benchmark suite"""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    def generate_test_data(self, rows: int, complexity: str = "simple") -> pl.DataFrame:
        """Generate test data with varying complexity"""
        if complexity == "simple":
            return pl.DataFrame({
                "id": pl.arange(0, rows, eager=True),
                "value": pl.arange(0, rows, eager=True).cast(pl.Float64) * 1.5,
            })
        elif complexity == "medium":
            return pl.DataFrame({
                "id": pl.arange(0, rows, eager=True),
                "price": pl.arange(0, rows, eager=True).cast(pl.Float64) * 1.5 + 100.0,
                "volume": pl.arange(0, rows, eager=True) * 10,
                "symbol": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"] * (rows // 5),
                "is_buy": [True, False] * (rows // 2),
            })
        else:  # complex
            return pl.DataFrame({
                "id": pl.arange(0, rows, eager=True),
                "price": pl.arange(0, rows, eager=True).cast(pl.Float64) * 1.5 + 100.0,
                "volume": pl.arange(0, rows, eager=True) * 10,
                "symbol": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"] * (rows // 5),
                "timestamp": pl.datetime_range(
                    start=pl.datetime(2024, 1, 1),
                    end=pl.datetime(2024, 12, 31),
                    interval="1m",
                    eager=True
                ).head(rows),
                "description": [f"Trade #{i} with complex string data" for i in range(rows)],
                "metadata": [{"key": i, "nested": {"value": i * 2}} for i in range(rows)],
                "binary_data": [bytes(f"binary_{i}", "utf-8") for i in range(rows)],
            })

    def benchmark_qadataswap(self, df: pl.DataFrame, shared_name: str) -> tuple[float, float]:
        """Benchmark QADataSwap zero-copy transfer"""

        def writer_func():
            writer = SharedDataFrame.create_writer(shared_name, size_mb=max(100, int(df.estimated_size("mb") * 2)))
            start = time.time()
            writer.write(df)
            return time.time() - start

        def reader_func():
            time.sleep(0.1)  # Ensure writer is ready
            reader = SharedDataFrame.create_reader(shared_name)
            start = time.time()
            result = reader.read(timeout_ms=10000)
            elapsed = time.time() - start
            return elapsed, result

        write_time = writer_func()
        read_time, result_df = reader_func()

        if result_df is None:
            raise ValueError("Failed to read data")

        return write_time, read_time

    def benchmark_polars_ipc(self, df: pl.DataFrame) -> tuple[float, float]:
        """Benchmark Polars IPC serialization"""
        # Write (serialize)
        start = time.time()
        buffer = df.write_ipc(None)
        write_time = time.time() - start

        # Read (deserialize)
        start = time.time()
        df_restored = pl.read_ipc(buffer)
        read_time = time.time() - start

        return write_time, read_time

    def benchmark_polars_parquet(self, df: pl.DataFrame) -> tuple[float, float]:
        """Benchmark Polars Parquet serialization"""
        # Write
        start = time.time()
        buffer = df.write_parquet(None)
        write_time = time.time() - start

        # Read
        start = time.time()
        df_restored = pl.read_parquet(buffer)
        read_time = time.time() - start

        return write_time, read_time

    def benchmark_pickle(self, df: pl.DataFrame) -> tuple[float, float]:
        """Benchmark Python pickle serialization"""
        # Write
        start = time.time()
        buffer = pickle.dumps(df)
        write_time = time.time() - start

        # Read
        start = time.time()
        df_restored = pickle.loads(buffer)
        read_time = time.time() - start

        return write_time, read_time

    def run_single_benchmark(self, method: str, df: pl.DataFrame, shared_name: str = None) -> BenchmarkResult:
        """Run a single benchmark"""
        print(f"Running {method} benchmark...")

        # Measure memory before
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024

        # Run benchmark
        if method == "QADataSwap":
            write_time, read_time = self.benchmark_qadataswap(df, shared_name or "benchmark")
        elif method == "Polars IPC":
            write_time, read_time = self.benchmark_polars_ipc(df)
        elif method == "Polars Parquet":
            write_time, read_time = self.benchmark_polars_parquet(df)
        elif method == "Pickle":
            write_time, read_time = self.benchmark_pickle(df)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Measure memory after
        memory_after = process.memory_info().rss / 1024 / 1024
        memory_usage = memory_after - memory_before

        # Calculate metrics
        data_size_mb = df.estimated_size("mb")
        total_time = write_time + read_time
        throughput = data_size_mb / total_time if total_time > 0 else 0
        ops_per_sec = 1.0 / total_time if total_time > 0 else 0

        return BenchmarkResult(
            method=method,
            data_size_mb=data_size_mb,
            rows=df.height,
            cols=df.width,
            write_time=write_time,
            read_time=read_time,
            total_time=total_time,
            memory_usage_mb=memory_usage,
            throughput_mb_s=throughput,
            operations_per_sec=ops_per_sec
        )

    def run_size_scaling_benchmark(self):
        """Benchmark performance scaling with data size"""
        print("\n" + "="*60)
        print("SIZE SCALING BENCHMARK")
        print("="*60)

        row_counts = [10000, 100000, 1000000, 5000000]
        methods = ["QADataSwap", "Polars IPC", "Polars Parquet"]

        for rows in row_counts:
            print(f"\nTesting with {rows:,} rows...")
            df = self.generate_test_data(rows, "medium")

            for method in methods:
                try:
                    result = self.run_single_benchmark(method, df, f"scale_{rows}")
                    self.results.append(result)
                    print(f"  {method:15}: {result.total_time:.4f}s ({result.throughput_mb_s:.1f} MB/s)")
                except Exception as e:
                    print(f"  {method:15}: FAILED ({e})")

    def run_complexity_benchmark(self):
        """Benchmark performance with different data complexities"""
        print("\n" + "="*60)
        print("DATA COMPLEXITY BENCHMARK")
        print("="*60)

        complexities = ["simple", "medium", "complex"]
        rows = 1000000
        methods = ["QADataSwap", "Polars IPC", "Polars Parquet"]

        for complexity in complexities:
            print(f"\nTesting {complexity} data structure...")
            df = self.generate_test_data(rows, complexity)

            for method in methods:
                try:
                    result = self.run_single_benchmark(method, df, f"complex_{complexity}")
                    self.results.append(result)
                    print(f"  {method:15}: {result.total_time:.4f}s ({result.throughput_mb_s:.1f} MB/s)")
                except Exception as e:
                    print(f"  {method:15}: FAILED ({e})")

    def run_concurrent_benchmark(self):
        """Benchmark concurrent read/write performance"""
        print("\n" + "="*60)
        print("CONCURRENT ACCESS BENCHMARK")
        print("="*60)

        rows = 1000000
        df = self.generate_test_data(rows, "medium")
        shared_name = "concurrent_test"

        # Single writer, multiple readers
        num_readers = [1, 2, 4, 8]

        for readers in num_readers:
            print(f"\nTesting 1 writer + {readers} readers...")

            def writer_process():
                writer = SharedDataFrame.create_writer(shared_name, size_mb=200)
                start = time.time()
                for i in range(5):  # Write 5 times
                    writer.write(df)
                    time.sleep(0.1)
                return time.time() - start

            def reader_process(reader_id):
                time.sleep(0.2)  # Wait for writer
                reader = SharedDataFrame.create_reader(shared_name)
                times = []
                for i in range(5):
                    start = time.time()
                    result = reader.read(timeout_ms=5000)
                    if result is not None:
                        times.append(time.time() - start)
                return times

            # Start processes
            writer_proc = mp.Process(target=writer_process)
            reader_procs = [mp.Process(target=reader_process, args=(i,)) for i in range(readers)]

            start_time = time.time()
            writer_proc.start()
            for proc in reader_procs:
                proc.start()

            writer_proc.join()
            for proc in reader_procs:
                proc.join()

            total_time = time.time() - start_time
            print(f"  Total time: {total_time:.4f}s")
            print(f"  Throughput: {(df.estimated_size('mb') * 5 * readers) / total_time:.1f} MB/s")

    def run_streaming_benchmark(self):
        """Benchmark streaming performance"""
        print("\n" + "="*60)
        print("STREAMING BENCHMARK")
        print("="*60)

        chunk_size = 100000
        num_chunks = 10
        shared_name = "streaming_test"

        def writer_process():
            writer = SharedDataStream.create_writer(shared_name, size_mb=500, buffer_count=8)
            total_time = 0
            for i in range(num_chunks):
                df = self.generate_test_data(chunk_size, "medium")
                start = time.time()
                writer.write_chunk(df)
                total_time += time.time() - start
            writer.finish()
            return total_time

        def reader_process():
            time.sleep(0.2)  # Wait for writer
            reader = SharedDataStream.create_reader(shared_name)
            total_time = 0
            chunks_read = 0
            for chunk in reader.iter_chunks():
                start = time.time()
                # Simulate processing
                _ = chunk.shape
                total_time += time.time() - start
                chunks_read += 1
                if chunks_read >= num_chunks:
                    break
            return total_time, chunks_read

        # Run streaming test
        writer_proc = mp.Process(target=writer_process)
        reader_proc = mp.Process(target=reader_process)

        start_time = time.time()
        writer_proc.start()
        reader_proc.start()

        writer_proc.join()
        reader_proc.join()

        total_time = time.time() - start_time
        total_data_mb = self.generate_test_data(chunk_size, "medium").estimated_size("mb") * num_chunks

        print(f"Streamed {num_chunks} chunks of {chunk_size:,} rows each")
        print(f"Total data: {total_data_mb:.1f} MB")
        print(f"Total time: {total_time:.4f}s")
        print(f"Throughput: {total_data_mb / total_time:.1f} MB/s")

    def generate_report(self):
        """Generate comprehensive performance report"""
        print("\n" + "="*80)
        print("PERFORMANCE REPORT")
        print("="*80)

        if not self.results:
            print("No benchmark results available.")
            return

        # Group results by method
        by_method = {}
        for result in self.results:
            if result.method not in by_method:
                by_method[result.method] = []
            by_method[result.method].append(result)

        # Print summary table
        print(f"{'Method':<15} {'Avg Time (s)':<12} {'Avg Throughput (MB/s)':<20} {'Tests':<6}")
        print("-" * 60)

        for method, results in by_method.items():
            avg_time = sum(r.total_time for r in results) / len(results)
            avg_throughput = sum(r.throughput_mb_s for r in results) / len(results)
            count = len(results)
            print(f"{method:<15} {avg_time:<12.4f} {avg_throughput:<20.1f} {count:<6}")

        # Find best performing method
        if "QADataSwap" in by_method:
            qads_results = by_method["QADataSwap"]
            qads_avg_time = sum(r.total_time for r in qads_results) / len(qads_results)

            print(f"\nSpeedup over other methods:")
            for method, results in by_method.items():
                if method != "QADataSwap":
                    avg_time = sum(r.total_time for r in results) / len(results)
                    speedup = avg_time / qads_avg_time if qads_avg_time > 0 else float('inf')
                    print(f"  vs {method}: {speedup:.1f}x faster")

        # Memory efficiency
        print(f"\nMemory Usage Summary:")
        for method, results in by_method.items():
            avg_memory = sum(r.memory_usage_mb for r in results) / len(results)
            print(f"  {method}: {avg_memory:.1f} MB average")

    def save_results(self, filename: str = "benchmark_results.json"):
        """Save results to JSON file"""
        data = []
        for result in self.results:
            data.append({
                "method": result.method,
                "data_size_mb": result.data_size_mb,
                "rows": result.rows,
                "cols": result.cols,
                "write_time": result.write_time,
                "read_time": result.read_time,
                "total_time": result.total_time,
                "memory_usage_mb": result.memory_usage_mb,
                "throughput_mb_s": result.throughput_mb_s,
                "operations_per_sec": result.operations_per_sec,
            })

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\nResults saved to {filename}")


def main():
    """Main benchmark execution"""
    print("QADataSwap Python Performance Benchmark")
    print("="*50)

    benchmark = PerformanceBenchmark()

    try:
        # Run all benchmark suites
        benchmark.run_size_scaling_benchmark()
        benchmark.run_complexity_benchmark()
        benchmark.run_concurrent_benchmark()
        benchmark.run_streaming_benchmark()

        # Generate final report
        benchmark.generate_report()
        benchmark.save_results()

    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()