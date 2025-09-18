# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QADataSwap is a high-performance cross-language zero-copy data transfer framework designed for sharing data between C++, Python (with Polars), and Rust (with Polars) processes using shared memory and Apache Arrow format.

## Architecture

The project is structured in three main layers:

1. **Core C++ Library** (`core/`): Implements shared memory management, Arrow serialization, and synchronization primitives
2. **Language Bindings**: Python (`bindings/python/`) and Rust (`bindings/rust/`) wrappers that provide native APIs
3. **Examples and Benchmarks**: Comprehensive testing and performance validation

### Key Design Principles

- **Zero-Copy Transfer**: Data is shared via memory-mapped files without serialization overhead
- **Arrow-Native**: All data uses Apache Arrow format for maximum compatibility
- **Polars-Optimized**: Direct integration with polars-py and polars-rs for seamless DataFrame operations
- **Process-Safe**: Uses POSIX semaphores and atomic operations for cross-process synchronization

## Common Development Commands

### Building the Project

```bash
# Build all components
make all

# Build individual components
make core          # C++ core library
make python        # Python bindings
make python-install # Install Python package in dev mode
make rust          # Rust library

# Run tests
make tests         # All tests
make tests-python  # Python tests only
make tests-rust    # Rust tests only

# Run benchmarks
make benchmark     # All benchmarks
make benchmark-all # Benchmarks with comparison
```

### Development Workflow

```bash
# Setup development environment
make dev-setup

# Format code
make format

# Lint code
make lint

# Clean build artifacts
make clean
```

### Testing Individual Components

```bash
# Test C++ core
make test-cpp

# Test Python with Polars
make test-python

# Test Rust with Polars
make test-rust

# Run cross-language integration tests
make test-integration
```

## Code Architecture

### Core Components

- **SharedMemoryArena** (`src/cpp/src/shared_memory_arena.cpp`): Main class handling shared memory allocation and management
- **SharedMemoryHeader** (`src/cpp/include/qadataswap_core.h`): Memory layout definition with atomic synchronization
- **Python Bindings** (`src/python/qadataswap_py.cpp`): pybind11-based Python interface with Polars integration
- **Rust Library** (`src/rust/src/lib.rs`): Native Rust interface with polars-rs integration

### Memory Layout

```
Shared Memory Region:
├── Header (metadata + synchronization)
│   ├── Magic number & version
│   ├── Buffer configuration
│   ├── Atomic counters (read/write sequence)
│   └── POSIX semaphores
└── Data Buffers (ring buffer)
    ├── Buffer 0 (Arrow format data)
    ├── Buffer 1 (Arrow format data)
    └── Buffer N (configurable count)
```

### Synchronization Mechanism

- **Ring Buffer**: Multiple buffers allow concurrent read/write operations
- **Atomic Counters**: Lock-free sequence tracking for buffer management
- **POSIX Semaphores**: Cross-process signaling for data availability
- **Memory Barriers**: Ensure consistency across different CPU architectures

## Language-Specific Notes

### Python (with Polars)

- Uses pybind11 for C++ integration
- Automatic conversion between Polars DataFrame and Arrow format
- Zero-copy access to underlying Arrow buffers
- Async support available with `qadataswap.async` module

Key APIs:
```python
from qadataswap import SharedDataFrame

# Writer
writer = SharedDataFrame.create_writer("mydata", size_mb=100)
writer.write(polars_df)  # Zero-copy write

# Reader
reader = SharedDataFrame.create_reader("mydata")
df = reader.read()  # Zero-copy read, returns Polars DataFrame
```

### Rust (with Polars)

- Direct FFI bindings to C++ core
- Native polars-rs integration
- Memory-safe wrappers around raw pointers
- Optional async support with tokio

Key APIs:
```rust
use qadataswap::{SharedDataFrame, SharedMemoryConfig};

// Writer
let config = SharedMemoryConfig::new("mydata").with_size_mb(100);
let writer = SharedDataFrame::create_writer(config)?;
writer.write(&polars_df)?;  // Zero-copy write

// Reader
let reader = SharedDataFrame::create_reader(config)?;
let df = reader.read(None)?;  // Zero-copy read, returns Option<DataFrame>
```

### C++ Core

- Modern C++17 with Arrow C++ library
- RAII for automatic resource management
- Template-based design for type safety
- Cross-platform support (Linux, macOS)

## Performance Characteristics

- **Latency**: < 1μs for data access (memory-bound)
- **Throughput**: > 10GB/s (limited by memory bandwidth)
- **Memory Overhead**: Zero additional copies, shared memory only
- **Scalability**: Supports multiple readers per writer

## Dependencies

### Core Dependencies
- Apache Arrow C++ (≥10.0.0)
- POSIX-compliant system (Linux, macOS)
- C++17 compiler

### Python Dependencies
- pyarrow (≥10.0.0)
- polars (≥0.18.0)
- pybind11
- numpy

### Rust Dependencies
- polars (≥0.33)
- arrow (≥51.0)
- tokio (optional, for async support)

## Common Issues and Solutions

### Build Issues

1. **Arrow not found**: Ensure Arrow is installed via package manager or conda
2. **Shared memory errors**: Check system limits (`ulimit -a`, `/proc/sys/kernel/sem`)
3. **Permission denied**: Verify user has access to `/dev/shm` or equivalent

### Runtime Issues

1. **Timeout errors**: Increase timeout or check process synchronization
2. **Memory corruption**: Verify schema compatibility between writer/reader
3. **Resource leaks**: Ensure proper cleanup by calling `.close()` or using RAII

### Performance Issues

1. **Slow transfers**: Check buffer count and size configuration
2. **High CPU usage**: Verify polling intervals and synchronization settings
3. **Memory fragmentation**: Use appropriate buffer sizes for data patterns

## Testing Strategy

- **Unit Tests**: Each component tested independently
- **Integration Tests**: Cross-language data transfer validation
- **Performance Tests**: Benchmarks against traditional serialization
- **Stress Tests**: High-throughput and concurrent access scenarios

## Debugging

Enable debug mode with:
```bash
export QADATASWAP_DEBUG=1
export QADATASWAP_LOG_LEVEL=DEBUG
```

Use `gdb` for C++ core, `pdb` for Python, and `rust-gdb` for Rust debugging.

## Contributing

When modifying the core C++ library, ensure:
1. Thread safety for all shared data structures
2. Proper memory alignment for cross-platform compatibility
3. Error handling that's safely propagated to language bindings
4. Documentation updates for API changes

For language bindings:
1. Maintain zero-copy semantics where possible
2. Provide idiomatic APIs for each language
3. Include comprehensive error handling
4. Add appropriate type hints (Python) or trait bounds (Rust)