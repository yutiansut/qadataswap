#!/bin/bash

# QADataSwap C++ Examples Build Script

set -e

echo "Building QADataSwap C++ Examples"
echo "================================="

# Check if we're in the right directory
if [ ! -f "CMakeLists.txt" ]; then
    echo "Error: CMakeLists.txt not found. Please run this script from the examples/cpp directory."
    exit 1
fi

# Create build directory
mkdir -p build
cd build

echo "Configuring with CMake..."
cmake .. -DCMAKE_BUILD_TYPE=Release

echo "Building..."
make -j$(nproc)

echo ""
echo "Build completed successfully!"
echo ""
echo "Available executables:"
echo "  ./basic_example         - Basic writer/reader example"
echo "  ./cpp_writer           - Cross-language writer"
echo "  ./cpp_reader           - Cross-language reader"
echo "  ./performance_test     - Performance benchmarks"
echo ""
echo "Example usage:"
echo "  # Run basic example:"
echo "  ./basic_example"
echo ""
echo "  # Run cross-language demo:"
echo "  ./cpp_writer cross_lang_demo &"
echo "  ./cpp_reader cross_lang_demo"
echo ""
echo "  # Or with Python:"
echo "  ./cpp_writer python_demo &"
echo "  python ../../python/cross_language_reader.py python_demo"
echo ""

# Check if executables were created
echo "Checking executables:"
for exe in basic_example cpp_writer cpp_reader performance_test; do
    if [ -f "$exe" ]; then
        echo "  ✓ $exe"
    else
        echo "  ✗ $exe (not found)"
    fi
done

echo ""
echo "Ready to run examples!"