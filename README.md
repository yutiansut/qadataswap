# QADataSwap - 高性能跨语言零拷贝数据传输框架

基于Apache Arrow和共享内存的跨进程、跨语言零拷贝数据传输库，专门优化支持Polars DataFrame。

## 🚀 核心特性

- **零拷贝传输**: 基于共享内存的真正零拷贝数据交换
- **跨语言支持**: C++, Python (Polars), Rust (Polars)
- **Arrow原生**: 完全兼容Apache Arrow生态系统
- **Polars优化**: 原生支持polars-py和polars-rs
- **高性能同步**: 基于信号量和原子操作的高效同步机制
- **内存安全**: Rust风格的内存安全保证
- **流式传输**: 支持大数据集的流式处理

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                 共享内存区域 (mmap)                      │
├─────────────────────────────────────────────────────────┤
│ Header (元数据)                                         │
│ ├─ Schema (Arrow Schema序列化)                         │
│ ├─ Sync (原子计数器 + 信号量)                          │
│ └─ Config (缓冲区配置)                                 │
├─────────────────────────────────────────────────────────┤
│ Data Buffers (Arrow格式数据)                           │
│ ├─ Buffer 0 (可写)                                     │
│ ├─ Buffer 1 (可读)                                     │
│ └─ Buffer N (环形缓冲)                                 │
└─────────────────────────────────────────────────────────┘
```

## 🎯 零拷贝原理

1. **共享内存映射**: 使用mmap创建跨进程共享的内存区域
2. **Arrow格式**: 数据以Arrow格式存储，确保列式存储和类型安全
3. **直接指针访问**: Polars直接访问Arrow缓冲区指针，无需拷贝
4. **引用计数**: 智能指针管理内存生命周期

## 📦 支持的数据类型

- 所有Arrow原生类型 (int8-64, float32/64, string, binary等)
- 复杂类型 (struct, list, map)
- Polars DataFrame/LazyFrame
- 自定义Schema

## 🛠️ 安装构建

### 依赖要求

```bash
# Ubuntu/Debian
sudo apt install libarrow-dev cmake g++ python3-dev

# Python 依赖
pip install polars pyarrow pybind11

# Rust (如需要)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs/ | sh
```

### 统一构建

```bash
# 构建所有组件 (推荐)
./scripts/build_all.sh

# 清理后重新构建
./scripts/build_all.sh --clean

# 仅构建特定语言
./scripts/build_all.sh --cpp-only
./scripts/build_all.sh --python-only
./scripts/build_all.sh --rust-only

# 构建 Python wheel 包
./scripts/build_all.sh --wheel

# 查看帮助
./scripts/build_all.sh --help
```

### 运行测试

```bash
# 运行所有测试
./scripts/test_all.sh

# 运行特定测试
./scripts/test_all.sh --python-only
./scripts/test_all.sh --cpp-only
./scripts/test_all.sh --rust-only
./scripts/test_all.sh --cross-lang-only

# 包含性能测试
./scripts/test_all.sh --with-performance

# 查看测试帮助
./scripts/test_all.sh --help
```

## 📚 快速开始

### Python (使用Polars)

```python
import polars as pl
import sys
sys.path.append('src/python')
import qadataswap

# 写入端
writer = qadataswap.create_writer("test_data", 50)
df = pl.DataFrame({
    'timestamp': [1640995200 + i for i in range(1000)],
    'symbol': ['AAPL', 'MSFT', 'GOOGL'][i % 3] for i in range(1000),
    'price': [100.0 + i * 0.1 for i in range(1000)],
    'volume': [1000 + i for i in range(1000)]
})
writer.write_arrow(df.to_arrow())  # 写入Arrow格式

# 读取端
reader = qadataswap.create_reader("test_data")
arrow_table = reader.read_arrow(5000)  # 5秒超时
if arrow_table:
    df = pl.from_arrow(arrow_table)  # 转换为Polars DataFrame
    print(df)
```

### Rust (使用Polars)

```rust
use qadataswap::{create_writer, create_reader};
use polars::prelude::*;

// 写入端 - 运行示例
// cargo run --bin rust_writer test_data

// 读取端 - 运行示例
// cargo run --bin rust_reader test_data

// 或查看 examples/rust/src/bin/ 中的完整示例
```

### C++ (原生Arrow)

```cpp
#include "qadataswap_core.h"

// 编译后运行示例
// ./build/cpp/examples/cpp/cpp_writer test_data
// ./build/cpp/examples/cpp/cpp_reader test_data

// 或查看 examples/cpp/ 中的完整示例
```

### 运行示例

```bash
# C++ 示例
cd build/cpp/examples/cpp
./basic_example
./performance_test

# Python 示例
cd examples/python
python3 basic_example.py
python3 polars_integration.py

# Rust 示例
cd examples/rust
cargo run --bin basic_example writer
cargo run --bin rust_writer demo_name

# 跨语言集成测试
python3 tests/integration/test_cross_language.py

# 性能基准测试
python3 tests/performance/benchmark_all.py
```

## 📊 性能特点

- **延迟**: < 1μs (微秒级别的数据访问)
- **吞吐量**: > 10GB/s (受内存带宽限制)
- **内存效率**: 零额外拷贝，直接指针访问
- **并发**: 支持多读者单写者模式

## 🏗️ 项目结构

```
qadataswap/
├── src/
│   ├── cpp/              # C++ 核心实现
│   │   ├── include/       # 头文件
│   │   └── src/           # 源文件 + FFI接口
│   ├── python/            # Python绑定 (pybind11)
│   └── rust/              # Rust实现 + FFI调用
├── examples/
│   ├── cpp/               # C++ 示例
│   ├── python/            # Python 示例
│   └── rust/              # Rust 示例
├── tests/
│   ├── integration/       # 跨语言集成测试
│   └── performance/       # 性能基准测试
├── scripts/
│   ├── build_all.sh       # 统一构建脚本
│   └── test_all.sh        # 统一测试脚本
└── build/                 # 构建输出目录
```

## 🔧 核心API

### Writer API

```python
# Python
writer = qadataswap.create_writer(name, buffer_count)
writer.write_arrow(arrow_table)

# Rust
let writer = create_writer(name, buffer_count);
writer.write_arrow(&arrow_table);

# C++ (通过FFI)
qads_create_writer(arena, name);
```

### Reader API

```python
# Python
reader = qadataswap.create_reader(name)
arrow_table = reader.read_arrow(timeout_ms)

# Rust
let reader = create_reader(name);
let arrow_table = reader.read_arrow(timeout_ms);

# C++ (通过FFI)
qads_attach_reader(arena, name);
```

## 📈 性能测试

运行性能基准测试：

```bash
# 完整性能测试
./scripts/test_all.sh --with-performance

# 或直接运行
python3 tests/performance/benchmark_all.py
```

### 测试覆盖

- **C++ 组件测试**: 基础示例、性能测试
- **Python 组件测试**: Polars集成、Arrow转换、内存使用
- **Rust 组件测试**: 单元测试、示例运行、性能基准
- **跨语言测试**: Python↔C++, Python↔Rust, C++↔Rust
- **内存分析**: 峰值使用量、泄漏检测

### 实际性能特点

- **低延迟**: 微秒级数据访问
- **高吞吐**: 受内存带宽限制
- **零拷贝**: 直接共享内存访问
- **跨语言**: 无序列化开销

## 🐛 故障排除

### 构建问题

```bash
# 检查依赖
./scripts/build_all.sh --help

# 清理重建
./scripts/build_all.sh --clean

# 检查库链接
nm -D build/cpp/libqadataswap_core.so | grep qads
```

### 运行时问题

```bash
# 清理共享内存
find /dev/shm -name "qads_*" -delete

# 检查权限
ls -la /dev/shm/

# 查看详细错误
export RUST_BACKTRACE=1
```

### 测试失败

```bash
# 逐个测试
./scripts/test_all.sh --cpp-only
./scripts/test_all.sh --python-only
./scripts/test_all.sh --rust-only

# 查看详细日志
./scripts/test_all.sh --no-report
```

## 🤝 贡献

1. Fork 本项目
2. 创建特性分支
3. 运行完整测试：`./scripts/test_all.sh`
4. 提交 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。