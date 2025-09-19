#!/usr/bin/env python3
"""
QADataSwap 跨语言集成测试
测试 C++, Python, Rust 之间的数据传输
"""

import os
import sys
import subprocess
import time
import signal
import polars as pl
from pathlib import Path

# 添加Python库路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src' / 'python'))

try:
    import qadataswap
except ImportError as e:
    print(f"无法导入 qadataswap: {e}")
    print("请确保已编译Python绑定")
    sys.exit(1)

class CrossLanguageTest:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.cpp_examples = self.project_root / 'build' / 'cpp' / 'examples' / 'cpp'
        self.rust_examples = self.project_root / 'examples' / 'rust' / 'target' / 'release'
        self.test_name = "cross_lang_integration_test"

    def check_executables(self):
        """检查所有可执行文件是否存在"""
        cpp_files = ['cpp_writer', 'cpp_reader']
        rust_files = ['rust_writer', 'rust_reader']

        print("检查可执行文件...")

        for exe in cpp_files:
            path = self.cpp_examples / exe
            if not path.exists():
                print(f"❌ 未找到 C++ 可执行文件: {path}")
                return False
            print(f"✅ 找到 C++ 可执行文件: {exe}")

        for exe in rust_files:
            path = self.rust_examples / exe
            if not path.exists():
                print(f"❌ 未找到 Rust 可执行文件: {path}")
                return False
            print(f"✅ 找到 Rust 可执行文件: {exe}")

        print("✅ 所有可执行文件检查完成\n")
        return True

    def test_python_to_cpp(self):
        """测试 Python -> C++ 数据传输"""
        print("🔄 测试 Python -> C++ 数据传输")

        try:
            # Python 写入数据
            df = pl.DataFrame({
                'timestamp': [1234567890 + i for i in range(1000)],
                'symbol': ['AAPL'] * 1000,
                'price': [100.0 + i * 0.1 for i in range(1000)],
                'volume': [1000 + i for i in range(1000)]
            })

            print("  📝 Python 创建数据...")
            writer = qadataswap.create_writer(self.test_name + "_py_to_cpp", 50)
            writer.write_arrow(df.to_arrow())
            print("  ✅ Python 数据写入完成")

            # 启动 C++ 读取器并让它在后台运行
            print("  📖 启动 C++ 读取器...")
            cpp_reader_process = subprocess.Popen([
                str(self.cpp_examples / 'cpp_reader'),
                self.test_name + "_py_to_cpp"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # 等待一段时间让C++读取器处理第一批数据
            print("  ⏳ 等待 C++ 读取器处理数据...")
            import time
            time.sleep(3)  # 给足够时间处理第一批数据

            # 检查进程是否还在运行
            if cpp_reader_process.poll() is None:
                # 进程仍在运行，说明它在等待更多数据，这是正常的
                print("  ✅ C++ 读取器正在处理数据...")
                
                # 等待一小段时间后终止进程
                time.sleep(2)
                cpp_reader_process.terminate()
                
                try:
                    stdout, stderr = cpp_reader_process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    cpp_reader_process.kill()
                    stdout, stderr = cpp_reader_process.communicate()
                
                # 检查输出中是否有成功读取的证据
                if "Reader attached successfully" in stdout and "Batch 1 received" in stdout:
                    print("  ✅ C++ 成功读取 Python 数据")
                    print(f"  📊 C++ 读取到数据并处理成功")
                    return True
                else:
                    print(f"  ❌ C++ 读取不完整:")
                    print(f"    stdout: {stdout[:500]}...")
                    return False
            else:
                # 进程已经结束
                stdout, stderr = cpp_reader_process.communicate()
                if cpp_reader_process.returncode == 0:
                    print("  ✅ C++ 成功读取 Python 数据")
                    return True
                else:
                    print(f"  ❌ C++ 读取失败: {stderr}")
                    return False

        except Exception as e:
            print(f"  ❌ Python -> C++ 测试失败: {e}")
            return False
        finally:
            # 清理
            try:
                writer.close()
            except:
                pass

    def test_cpp_to_python(self):
        """测试 C++ -> Python 数据传输"""
        print("🔄 测试 C++ -> Python 数据传输")

        try:
            # 启动 C++ 写入器
            print("  📝 启动 C++ 写入器...")
            cpp_writer = subprocess.Popen([
                str(self.cpp_examples / 'cpp_writer'),
                self.test_name + "_cpp_to_py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 等待数据写入
            time.sleep(2)

            # Python 读取数据
            print("  📖 Python 读取数据...")
            reader = qadataswap.create_reader(self.test_name + "_cpp_to_py")
            arrow_table = reader.read_arrow(5000)  # 5秒超时

            if arrow_table is not None:
                df = pl.from_arrow(arrow_table)
                print(f"  ✅ Python 成功读取 C++ 数据: {df.shape[0]} 行")

                # 清理进程
                cpp_writer.terminate()
                cpp_writer.wait()
                return True
            else:
                print("  ❌ Python 读取数据失败")
                cpp_writer.terminate()
                return False

        except Exception as e:
            print(f"  ❌ C++ -> Python 测试失败: {e}")
            if 'cpp_writer' in locals():
                cpp_writer.terminate()
            return False

    def test_python_to_rust(self):
        """测试 Python -> Rust 数据传输"""
        print("🔄 测试 Python -> Rust 数据传输")

        try:
            # Python 写入数据
            df = pl.DataFrame({
                'id': list(range(500)),
                'value': [i * 2.5 for i in range(500)],
                'category': [f'cat_{i % 5}' for i in range(500)]
            })

            print("  📝 Python 创建数据...")
            writer = qadataswap.create_writer(self.test_name + "_py_to_rust", 30)
            writer.write_arrow(df.to_arrow())
            print("  ✅ Python 数据写入完成")

            # Rust 读取数据
            print("  📖 启动 Rust 读取器...")
            rust_reader = subprocess.run([
                str(self.rust_examples / 'rust_reader'),
                self.test_name + "_py_to_rust"
            ], capture_output=True, text=True, timeout=10)

            if rust_reader.returncode == 0:
                print("  ✅ Rust 成功读取 Python 数据")
                return True
            else:
                print(f"  ❌ Rust 读取失败: {rust_reader.stderr}")
                return False

        except Exception as e:
            print(f"  ❌ Python -> Rust 测试失败: {e}")
            return False

    def test_rust_to_python(self):
        """测试 Rust -> Python 数据传输"""
        print("🔄 测试 Rust -> Python 数据传输")

        try:
            # 启动 Rust 写入器
            print("  📝 启动 Rust 写入器...")
            rust_writer = subprocess.Popen([
                str(self.rust_examples / 'rust_writer'),
                self.test_name + "_rust_to_py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 等待数据写入
            time.sleep(3)

            # Python 读取数据
            print("  📖 Python 读取数据...")
            reader = qadataswap.create_reader(self.test_name + "_rust_to_py")
            arrow_table = reader.read_arrow(10000)  # 10秒超时

            if arrow_table is not None:
                df = pl.from_arrow(arrow_table)
                print(f"  ✅ Python 成功读取 Rust 数据: {df.shape[0]} 行")

                # 清理进程
                rust_writer.terminate()
                rust_writer.wait()
                return True
            else:
                print("  ❌ Python 读取数据失败")
                rust_writer.terminate()
                return False

        except Exception as e:
            print(f"  ❌ Rust -> Python 测试失败: {e}")
            if 'rust_writer' in locals():
                rust_writer.terminate()
            return False

    def test_cpp_to_rust(self):
        """测试 C++ -> Rust 跨语言通信"""
        print("🔄 测试 C++ -> Rust 数据传输")

        try:
            # 启动 C++ 写入器
            print("  📝 启动 C++ 写入器...")
            cpp_writer = subprocess.Popen([
                str(self.cpp_examples / 'cpp_writer'),
                self.test_name + "_cpp_to_rust"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 等待数据写入
            time.sleep(2)

            # Rust 读取数据
            print("  📖 启动 Rust 读取器...")
            rust_reader = subprocess.run([
                str(self.rust_examples / 'rust_reader'),
                self.test_name + "_cpp_to_rust"
            ], capture_output=True, text=True, timeout=15)

            # 清理进程
            cpp_writer.terminate()
            cpp_writer.wait()

            if rust_reader.returncode == 0:
                print("  ✅ Rust 成功读取 C++ 数据")
                return True
            else:
                print(f"  ❌ Rust 读取失败: {rust_reader.stderr}")
                return False

        except Exception as e:
            print(f"  ❌ C++ -> Rust 测试失败: {e}")
            if 'cpp_writer' in locals():
                cpp_writer.terminate()
            return False

    def run_all_tests(self):
        """运行所有跨语言测试"""
        print("=" * 60)
        print("🚀 QADataSwap 跨语言集成测试")
        print("=" * 60)

        if not self.check_executables():
            print("❌ 预检查失败，请确保所有组件已编译")
            return False

        tests = [
            ("Python -> C++", self.test_python_to_cpp),
            ("C++ -> Python", self.test_cpp_to_python),
            ("Python -> Rust", self.test_python_to_rust),
            ("Rust -> Python", self.test_rust_to_python),
            ("C++ -> Rust", self.test_cpp_to_rust),
        ]

        results = []

        for test_name, test_func in tests:
            print(f"\n{'=' * 60}")
            try:
                result = test_func()
                results.append((test_name, result))
                print(f"📊 {test_name}: {'✅ 通过' if result else '❌ 失败'}")
            except Exception as e:
                print(f"📊 {test_name}: ❌ 异常 - {e}")
                results.append((test_name, False))

            # 清理共享内存
            time.sleep(1)

        # 总结
        print(f"\n{'=' * 60}")
        print("📈 测试结果总结")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"  {test_name:20} {status}")

        print(f"\n总体结果: {passed}/{total} 通过")

        if passed == total:
            print("🎉 所有跨语言测试通过！")
            return True
        else:
            print("⚠️  部分测试失败，请检查实现")
            return False

def main():
    test_runner = CrossLanguageTest()
    success = test_runner.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()