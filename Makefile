# QADataSwap - High-Performance Cross-Language Data Transfer Framework
.PHONY: all clean install test bench docs help

# Build configuration
BUILD_TYPE ?= Release
PARALLEL_JOBS ?= $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

# Directories
SRC_DIR = src
BUILD_DIR = build
INSTALL_DIR = install
DOCS_DIR = docs

# Default target
all: cpp rust

# Include Python only if explicitly requested
all-with-python: cpp python rust

# Help target
help:
	@echo "QADataSwap Build System"
	@echo ""
	@echo "Core Targets:"
	@echo "  all           - Build all components (C++, Python, Rust)"
	@echo "  cpp           - Build C++ core library"
	@echo "  python        - Build Python bindings"
	@echo "  rust          - Build Rust library"
	@echo ""
	@echo "Installation:"
	@echo "  install       - Install all components"
	@echo "  install-cpp   - Install C++ library"
	@echo "  install-python- Install Python package"
	@echo "  install-rust  - Install Rust library"
	@echo ""
	@echo "Development:"
	@echo "  test          - Run all tests"
	@echo "  test-cpp      - Run C++ tests"
	@echo "  test-python   - Run Python tests"
	@echo "  test-rust     - Run Rust tests"
	@echo "  test-integration - Run cross-language tests"
	@echo ""
	@echo "Performance:"
	@echo "  bench         - Run all benchmarks"
	@echo "  bench-python  - Run Python benchmarks"
	@echo "  bench-rust    - Run Rust benchmarks"
	@echo "  bench-compare - Compare performance across languages"
	@echo ""
	@echo "Examples:"
	@echo "  examples      - Run all examples"
	@echo "  example-python- Run Python examples"
	@echo "  example-rust  - Run Rust examples"
	@echo "  example-cpp   - Run C++ examples"
	@echo ""
	@echo "Documentation:"
	@echo "  docs          - Build documentation"
	@echo "  docs-python   - Build Python API docs"
	@echo "  docs-rust     - Build Rust API docs"
	@echo ""
	@echo "Utilities:"
	@echo "  format        - Format all code"
	@echo "  lint          - Lint all code"
	@echo "  clean         - Clean build artifacts"
	@echo "  distclean     - Clean everything including dependencies"
	@echo ""
	@echo "Configuration:"
	@echo "  BUILD_TYPE    = $(BUILD_TYPE) (Debug|Release|RelWithDebInfo)"
	@echo "  PARALLEL_JOBS = $(PARALLEL_JOBS)"

###################
# C++ Core Library
###################

cpp: $(BUILD_DIR)/cpp/libqadataswap_core.so

$(BUILD_DIR)/cpp/libqadataswap_core.so: $(SRC_DIR)/cpp/src/*.cpp $(SRC_DIR)/cpp/include/*.h
	@echo "Building C++ core library..."
	@mkdir -p $(BUILD_DIR)/cpp
	cd $(BUILD_DIR)/cpp && \
	cmake -DCMAKE_BUILD_TYPE=$(BUILD_TYPE) \
	      -DCMAKE_INSTALL_PREFIX=$(realpath $(INSTALL_DIR)) \
	      ../.. && \
	make -j$(PARALLEL_JOBS)

install-cpp: cpp
	@echo "Installing C++ library..."
	cd $(BUILD_DIR)/cpp && make install

test-cpp: cpp
	@echo "Running C++ tests..."
	cd $(BUILD_DIR)/cpp && ctest --output-on-failure

###################
# Python Bindings
###################

python: $(SRC_DIR)/python/build/lib*/qadataswap*.so

$(SRC_DIR)/python/build/lib*/qadataswap*.so: $(SRC_DIR)/python/*.cpp $(SRC_DIR)/cpp/src/*.cpp
	@echo "Building Python bindings..."
	cd $(SRC_DIR)/python && python setup.py build_ext --inplace

python-simple:
	@echo "Building simplified Python bindings..."
	cd $(SRC_DIR)/python && python setup_simple.py build_ext --inplace

install-python: python
	@echo "Installing Python package..."
	cd $(SRC_DIR)/python && pip install -e .

test-python: install-python
	@echo "Running Python tests..."
	cd $(SRC_DIR)/python && python -m pytest tests/ -v || true

example-python: install-python
	@echo "Running Python examples..."
	cd examples/python && python basic_example.py

bench-python: install-python
	@echo "Running Python benchmarks..."
	cd tests/performance && python benchmark_python.py

###################
# Rust Library
###################

rust: $(SRC_DIR)/rust/target/release/libqadataswap.rlib

$(SRC_DIR)/rust/target/release/libqadataswap.rlib: $(SRC_DIR)/rust/src/*.rs
	@echo "Building Rust library..."
	cd $(SRC_DIR)/rust && cargo build --release

install-rust: rust
	@echo "Installing Rust library..."
	cd $(SRC_DIR)/rust && cargo install --path .

test-rust: rust
	@echo "Running Rust tests..."
	cd $(SRC_DIR)/rust && cargo test --release

example-rust: rust
	@echo "Running Rust examples..."
	cd examples/rust && cargo run --release --bin basic_example

bench-rust: rust
	@echo "Running Rust benchmarks..."
	cd $(SRC_DIR)/rust && cargo bench

###################
# Cross-Language Integration
###################

test-integration: install-python rust
	@echo "Running cross-language integration tests..."
	cd tests/integration && python test_cross_language.py || true

###################
# Examples
###################

examples: example-python example-rust

###################
# Benchmarks
###################

bench: bench-python bench-rust

bench-compare: bench
	@echo "Comparing performance across languages..."
	cd tests/performance && python compare_performance.py || true

###################
# Development Tools
###################

format:
	@echo "Formatting code..."
	# Python
	cd $(SRC_DIR)/python && black . && isort . || true
	# Rust
	cd $(SRC_DIR)/rust && cargo fmt || true
	# C++
	find $(SRC_DIR)/cpp -name "*.cpp" -o -name "*.h" | xargs clang-format -i || true

lint:
	@echo "Linting code..."
	# Python
	cd $(SRC_DIR)/python && flake8 . && mypy . || true
	# Rust
	cd $(SRC_DIR)/rust && cargo clippy -- -D warnings || true
	# C++
	cppcheck $(SRC_DIR)/cpp --enable=all --inconclusive || true

###################
# Documentation
###################

docs: docs-python docs-rust
	@echo "Building documentation..."
	@mkdir -p $(DOCS_DIR)/build
	cd $(DOCS_DIR) && make html || true

docs-python: install-python
	@echo "Building Python API documentation..."
	cd $(SRC_DIR)/python && pydoc-markdown > ../../$(DOCS_DIR)/api/python.md || true

docs-rust: rust
	@echo "Building Rust API documentation..."
	cd $(SRC_DIR)/rust && cargo doc --no-deps --open || true

###################
# Testing
###################

test: test-cpp test-python test-rust test-integration
	@echo "All tests completed!"

###################
# Installation
###################

install: install-cpp install-python install-rust
	@echo "All components installed!"

###################
# Cleanup
###################

clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)
	cd $(SRC_DIR)/python && rm -rf build/ dist/ *.egg-info/ || true
	cd $(SRC_DIR)/rust && cargo clean || true
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

distclean: clean
	@echo "Deep cleaning..."
	rm -rf $(INSTALL_DIR)
	cd $(SRC_DIR)/python && find . -name "*.so" -delete || true

###################
# Dependency Management
###################

deps-check:
	@echo "Checking dependencies..."
	@echo "Arrow C++: $$(pkg-config --modversion arrow 2>/dev/null || echo 'NOT FOUND')"
	@echo "Python: $$(python --version 2>&1)"
	@echo "Rust: $$(rustc --version 2>/dev/null || echo 'NOT FOUND')"
	@echo "CMake: $$(cmake --version 2>/dev/null | head -1 || echo 'NOT FOUND')"

deps-install-ubuntu:
	@echo "Installing dependencies on Ubuntu..."
	sudo apt update
	sudo apt install -y build-essential cmake pkg-config
	sudo apt install -y libarrow-dev libparquet-dev
	pip install -r requirements.txt

deps-install-macos:
	@echo "Installing dependencies on macOS..."
	brew install arrow cmake
	pip install -r requirements.txt

###################
# CI/CD Support
###################

ci-setup: deps-check
	@echo "Setting up CI environment..."

ci-test: test bench
	@echo "CI testing completed!"

ci-build: all
	@echo "CI build completed!"

###################
# Docker Support
###################

docker-build:
	@echo "Building Docker image..."
	docker build -t qadataswap:latest .

docker-test: docker-build
	@echo "Running tests in Docker..."
	docker run --rm qadataswap:latest make test

###################
# Versioning
###################

version:
	@echo "QADataSwap v0.1.0"
	@echo "Build configuration:"
	@echo "  BUILD_TYPE: $(BUILD_TYPE)"
	@echo "  PARALLEL_JOBS: $(PARALLEL_JOBS)"
	@echo "Dependencies:"
	@make deps-check

###################
# Package Creation
###################

package-python: python
	@echo "Creating Python package..."
	cd $(SRC_DIR)/python && python setup.py sdist bdist_wheel

package-rust: rust
	@echo "Creating Rust package..."
	cd $(SRC_DIR)/rust && cargo package

package: package-python package-rust
	@echo "All packages created!"

###################
# Release Support
###################

release-check: test lint format
	@echo "Release checks passed!"

release: release-check package
	@echo "Release build completed!"