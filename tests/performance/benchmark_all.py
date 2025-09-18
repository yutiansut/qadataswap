#!/usr/bin/env python3
"""
QADataSwap 多语言性能基准测试
比较 C++, Python, Rust 的性能差异
"""

import os
import sys
import subprocess
import time
import json
import psutil
from pathlib import Path
import polars as pl

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src' / 'python'))

try:
    import qadataswap
except ImportError as e:
    print(f"无法导入 qadataswap: {e}")
    sys.exit(1)

class PerformanceBenchmark:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.cpp_examples = self.project_root / 'build' / 'cpp' / 'examples' / 'cpp'
        self.rust_examples = self.project_root / 'examples' / 'rust' / 'target' / 'release'
        self.results = {}

    def create_test_data(self, rows=10000):
        """创建测试数据"""
        return pl.DataFrame({
            'timestamp': [1640995200 + i for i in range(rows)],  # 2022-01-01 开始
            'symbol': ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA'][i % 5] for i in range(rows),
            'price': [100.0 + (i % 1000) * 0.01 for i in range(rows)],
            'volume': [1000 + (i % 10000) for i in range(rows)],
            'bid': [99.99 + (i % 1000) * 0.01 for i in range(rows)],
            'ask': [100.01 + (i % 1000) * 0.01 for i in range(rows)]
        })

    def benchmark_python_write_read(self, data_sizes):
        """Python 写入读取性能测试"""
        print("🐍 Python 性能测试")
        results = {}

        for size in data_sizes:
            print(f"  测试数据量: {size:,} 行")
            df = self.create_test_data(size)

            # 写入测试
            test_name = f"python_perf_{size}"
            start_time = time.time()

            try:
                writer = qadataswap.create_writer(test_name, max(50, size // 1000))
                writer.write_arrow(df.to_arrow())
                write_time = time.time() - start_time

                # 读取测试
                start_time = time.time()
                reader = qadataswap.create_reader(test_name)
                result_table = reader.read_arrow(10000)
                read_time = time.time() - start_time

                if result_table is not None:
                    result_df = pl.from_arrow(result_table)
                    throughput_write = size / write_time
                    throughput_read = size / read_time

                    results[size] = {
                        'write_time': write_time,
                        'read_time': read_time,
                        'write_throughput': throughput_write,
                        'read_throughput': throughput_read,
                        'rows_verified': len(result_df)
                    }

                    print(f"    写入: {write_time:.4f}s ({throughput_write:,.0f} 行/秒)")
                    print(f"    读取: {read_time:.4f}s ({throughput_read:,.0f} 行/秒)")
                else:
                    print(f"    ❌ 读取失败")

            except Exception as e:
                print(f"    ❌ 错误: {e}")

        return results

    def benchmark_cpp_performance(self, data_sizes):
        """C++ 性能测试"""
        print("⚡ C++ 性能测试")
        results = {}

        try:
            for size in [1000, 10000, 100000]:  # C++ 性能测试使用预定义大小
                print(f"  测试数据量: {size:,} 行")

                # 运行 C++ 性能测试
                start_time = time.time()
                result = subprocess.run([
                    str(self.cpp_examples / 'performance_test')
                ], capture_output=True, text=True, timeout=60)

                total_time = time.time() - start_time

                if result.returncode == 0:
                    # 解析输出中的性能数据
                    output = result.stdout
                    results[size] = {
                        'total_time': total_time,
                        'output': output,
                        'status': 'success'
                    }
                    print(f"    完成时间: {total_time:.4f}s")
                else:
                    print(f"    ❌ 错误: {result.stderr}")

        except Exception as e:
            print(f"  ❌ C++ 测试失败: {e}")

        return results

    def benchmark_rust_performance(self, data_sizes):
        """Rust 性能测试"""
        print("🦀 Rust 性能测试")
        results = {}

        try:
            # 运行 Rust 性能测试
            start_time = time.time()
            result = subprocess.run([
                str(self.rust_examples / 'performance_test')
            ], capture_output=True, text=True, timeout=60)

            total_time = time.time() - start_time

            if result.returncode == 0:
                # 解析输出中的性能数据
                output = result.stdout
                results['rust_performance'] = {
                    'total_time': total_time,
                    'output': output,
                    'status': 'success'
                }
                print(f"  完成时间: {total_time:.4f}s")
            else:
                print(f"  ❌ 错误: {result.stderr}")

        except Exception as e:
            print(f"  ❌ Rust 测试失败: {e}")

        return results

    def benchmark_memory_usage(self):
        """内存使用测试"""
        print("💾 内存使用测试")

        # 获取当前进程内存使用
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 创建大量数据测试内存使用
        df = self.create_test_data(100000)  # 100K 行
        data_memory = process.memory_info().rss / 1024 / 1024  # MB

        try:
            # 写入数据
            writer = qadataswap.create_writer("memory_test", 100)
            writer.write_arrow(df.to_arrow())
            write_memory = process.memory_info().rss / 1024 / 1024  # MB

            # 读取数据
            reader = qadataswap.create_reader("memory_test")
            result_table = reader.read_arrow(5000)
            read_memory = process.memory_info().rss / 1024 / 1024  # MB

            memory_results = {
                'initial_memory_mb': initial_memory,
                'data_creation_mb': data_memory,
                'after_write_mb': write_memory,
                'after_read_mb': read_memory,
                'peak_usage_mb': max(data_memory, write_memory, read_memory)
            }

            print(f"  初始内存: {initial_memory:.2f} MB")
            print(f"  数据创建后: {data_memory:.2f} MB")
            print(f"  写入后: {write_memory:.2f} MB")
            print(f"  读取后: {read_memory:.2f} MB")
            print(f"  峰值使用: {memory_results['peak_usage_mb']:.2f} MB")

            return memory_results

        except Exception as e:
            print(f"  ❌ 内存测试失败: {e}")
            return {}

    def run_all_benchmarks(self):
        """运行所有性能基准测试"""
        print("=" * 80)
        print("🏃 QADataSwap 多语言性能基准测试")
        print("=" * 80)

        data_sizes = [1000, 10000, 50000]  # 测试数据大小

        # Python 性能测试
        print(f"\n{'=' * 80}")
        self.results['python'] = self.benchmark_python_write_read(data_sizes)

        # C++ 性能测试
        print(f"\n{'=' * 80}")
        self.results['cpp'] = self.benchmark_cpp_performance(data_sizes)

        # Rust 性能测试
        print(f"\n{'=' * 80}")
        self.results['rust'] = self.benchmark_rust_performance(data_sizes)

        # 内存使用测试
        print(f"\n{'=' * 80}")
        self.results['memory'] = self.benchmark_memory_usage()

        # 保存结果
        self.save_results()

        # 生成报告
        self.generate_report()

    def save_results(self):
        """保存测试结果到文件"""
        results_file = self.project_root / 'benchmark_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📊 结果已保存到: {results_file}")

    def generate_report(self):
        """生成性能报告"""
        print(f"\n{'=' * 80}")
        print("📈 性能测试总结报告")
        print("=" * 80)

        # Python 结果总结
        if 'python' in self.results and self.results['python']:
            print("\n🐍 Python 性能:")
            for size, data in self.results['python'].items():
                print(f"  {size:,} 行:")
                print(f"    写入吞吐量: {data['write_throughput']:,.0f} 行/秒")
                print(f"    读取吞吐量: {data['read_throughput']:,.0f} 行/秒")

        # 内存使用总结
        if 'memory' in self.results and self.results['memory']:
            print(f"\n💾 内存使用:")
            mem = self.results['memory']
            print(f"  峰值内存使用: {mem.get('peak_usage_mb', 0):.2f} MB")

        print("\n🏆 基准测试完成!")

def main():
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()

if __name__ == "__main__":
    main()