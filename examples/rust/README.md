# QADataSwap Rust Examples

This directory contains comprehensive examples for using QADataSwap with Rust and Polars.

## Building

```bash
# Build all examples
./build.sh

# Or manually
cargo build --release
```

## Examples

### 1. Basic Example
Demonstrates basic writer/reader functionality with Polars DataFrames.

```bash
# Terminal 1 (Writer)
cargo run --bin basic_example -- writer

# Terminal 2 (Reader)
cargo run --bin basic_example -- reader
```

### 2. Cross-Language Writer
Generates simulated market data for cross-language communication.

```bash
# Start Rust writer
cargo run --bin rust_writer [shared_name]

# Read from C++
../cpp/build/cpp_reader [shared_name]

# Or read from Python
python ../python/cross_language_reader.py [shared_name]
```

### 3. Cross-Language Reader
Reads data written by C++ or Python writers.

```bash
# Start C++ writer
../cpp/build/cpp_writer demo_name &

# Read with Rust
cargo run --bin rust_reader demo_name
```

### 4. Performance Tests
Comprehensive benchmarks for throughput, latency, and concurrent access.

```bash
cargo run --bin performance_test
```

## Features Demonstrated

- **Zero-copy data transfer** using shared memory
- **Polars DataFrame integration** for high-performance data processing
- **Cross-language compatibility** with C++ and Python
- **Real-time data streaming** for financial market data
- **Performance benchmarking** with detailed metrics
- **Concurrent access patterns** with multiple readers/writers

## Data Formats

All examples use Apache Arrow format via Polars, enabling:
- Columnar data layout for efficient processing
- Schema validation and type safety
- Seamless interoperability between languages
- Memory-efficient zero-copy operations