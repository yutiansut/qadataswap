#!/bin/bash

# QADataSwap Rust Examples Build Script

set -e

echo "Building QADataSwap Rust Examples"
echo "================================="

# Check if we're in the right directory
if [ ! -f "Cargo.toml" ]; then
    echo "Error: Cargo.toml not found. Please run this script from the examples/rust directory."
    exit 1
fi

echo "Building with Cargo..."
cargo build --release

echo ""
echo "Build completed successfully!"
echo ""
echo "Available executables:"
echo "  cargo run --bin basic_example -- writer   - Basic writer example"
echo "  cargo run --bin basic_example -- reader   - Basic reader example"
echo "  cargo run --bin rust_writer               - Cross-language writer"
echo "  cargo run --bin rust_reader               - Cross-language reader"
echo "  cargo run --bin performance_test          - Performance benchmarks"
echo ""
echo "Example usage:"
echo "  # Run basic example:"
echo "  cargo run --bin basic_example -- writer &"
echo "  cargo run --bin basic_example -- reader"
echo ""
echo "  # Run cross-language demo:"
echo "  cargo run --bin rust_writer cross_lang_demo &"
echo "  cargo run --bin rust_reader cross_lang_demo"
echo ""
echo "  # Or with C++:"
echo "  cargo run --bin rust_writer cpp_demo &"
echo "  ../cpp/build/cpp_reader cpp_demo"
echo ""
echo "  # Or with Python:"
echo "  cargo run --bin rust_writer python_demo &"
echo "  python ../python/cross_language_reader.py python_demo"
echo ""

# Check if executables were created
echo "Checking build artifacts:"
for exe in basic_example rust_writer rust_reader performance_test; do
    if [ -f "target/release/$exe" ]; then
        echo "  ✓ $exe"
    else
        echo "  ✗ $exe (not found)"
    fi
done

echo ""
echo "Ready to run examples!"