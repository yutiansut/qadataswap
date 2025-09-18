#!/bin/bash

# QADataSwap 统一编译脚本
# 编译所有语言的库和示例

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "\n${PURPLE}================================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================================${NC}\n"
}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

log_section "🚀 QADataSwap 统一编译脚本"

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."

    # 检查 C++ 编译工具
    if ! command -v cmake &> /dev/null; then
        log_error "cmake 未安装，请先安装 cmake"
        exit 1
    fi

    if ! command -v g++ &> /dev/null; then
        log_error "g++ 未安装，请先安装 g++"
        exit 1
    fi

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "python3 未安装，请先安装 python3"
        exit 1
    fi

    # 检查 Rust
    if ! command -v cargo &> /dev/null; then
        log_error "cargo 未安装，请先安装 Rust (https://rustup.rs/)"
        exit 1
    fi

    # 检查 Arrow 库
    if ! pkg-config --exists arrow; then
        log_error "Arrow 库未安装，请先安装 libarrow-dev"
        exit 1
    fi

    log_success "所有依赖检查完成"
}

# 清理构建目录
clean_build() {
    log_info "清理构建目录..."

    # 清理 C++ 构建
    if [ -d "build" ]; then
        rm -rf build
        log_info "已清理 C++ build 目录"
    fi

    # 清理 Python 构建
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    cd src/python && rm -rf build/ dist/ *.egg-info/ 2>/dev/null || true
    cd "$PROJECT_ROOT"
    log_info "已清理 Python 构建文件"

    # 清理 Rust 构建
    if [ -d "target" ]; then
        cargo clean 2>/dev/null || true
    fi
    if [ -d "src/rust/target" ]; then
        cd src/rust && cargo clean && cd "$PROJECT_ROOT"
    fi
    if [ -d "examples/rust/target" ]; then
        cd examples/rust && cargo clean && cd "$PROJECT_ROOT"
    fi
    log_info "已清理 Rust 构建文件"

    log_success "构建目录清理完成"
}

# 编译 C++ 核心库
build_cpp() {
    log_section "⚡ 编译 C++ 核心库和示例"

    mkdir -p build/cpp
    cd build/cpp

    log_info "配置 CMake..."
    cmake -DCMAKE_BUILD_TYPE=Release \
          -DBUILD_EXAMPLES=ON \
          -DBUILD_TESTS=ON \
          ../.. || {
        log_error "CMake 配置失败"
        exit 1
    }

    log_info "编译 C++ 库..."
    make -j$(nproc) || {
        log_error "C++ 编译失败"
        exit 1
    }

    cd "$PROJECT_ROOT"

    # 验证编译结果
    if [ -f "build/cpp/libqadataswap_core.so" ]; then
        log_success "C++ 核心库编译成功: build/cpp/libqadataswap_core.so"
    else
        log_error "C++ 核心库编译失败"
        exit 1
    fi

    # 检查示例程序
    local cpp_examples=("basic_example" "cpp_writer" "cpp_reader" "performance_test")
    for exe in "${cpp_examples[@]}"; do
        if [ -f "build/cpp/examples/cpp/$exe" ]; then
            log_success "C++ 示例编译成功: $exe"
        else
            log_warning "C++ 示例编译失败: $exe"
        fi
    done
}

# 编译 Python 绑定
build_python() {
    log_section "🐍 编译 Python 绑定"

    cd src/python

    log_info "编译 Python 绑定..."
    python3 setup.py build_ext --inplace || {
        log_error "Python 绑定编译失败"
        exit 1
    }

    cd "$PROJECT_ROOT"

    # 验证编译结果
    if [ -f "src/python/qadataswap/qadataswap.cpython-"*".so" ]; then
        log_success "Python 绑定编译成功"
    else
        log_error "Python 绑定编译失败"
        exit 1
    fi

    # 测试导入
    log_info "测试 Python 导入..."
    cd src/python
    if python3 -c "import qadataswap; print('Python 绑定导入成功')"; then
        log_success "Python 绑定可以正常导入"
    else
        log_warning "Python 绑定导入测试失败"
    fi
    cd "$PROJECT_ROOT"
}

# 编译 Rust 库
build_rust() {
    log_section "🦀 编译 Rust 库和示例"

    # 编译主库
    log_info "编译 Rust 主库..."
    cd src/rust
    cargo build --release || {
        log_error "Rust 主库编译失败"
        exit 1
    }
    cd "$PROJECT_ROOT"

    # 验证主库编译结果
    if [ -f "target/release/libqadataswap.so" ]; then
        log_success "Rust 主库编译成功: target/release/libqadataswap.so"
    else
        log_warning "Rust 主库动态库未生成（可能正常）"
    fi

    # 编译示例
    log_info "编译 Rust 示例..."
    cd examples/rust
    ./build.sh || {
        log_error "Rust 示例编译失败"
        exit 1
    }
    cd "$PROJECT_ROOT"

    # 检查示例程序
    local rust_examples=("basic_example" "rust_writer" "rust_reader" "performance_test")
    for exe in "${rust_examples[@]}"; do
        if [ -f "examples/rust/target/release/$exe" ]; then
            log_success "Rust 示例编译成功: $exe"
        else
            log_warning "Rust 示例编译失败: $exe"
        fi
    done

    # 运行 Rust 测试
    log_info "运行 Rust 单元测试..."
    cd src/rust
    if cargo test --lib; then
        log_success "Rust 单元测试通过"
    else
        log_warning "Rust 单元测试失败"
    fi
    cd "$PROJECT_ROOT"
}

# 构建 Python wheel
build_python_wheel() {
    log_section "📦 构建 Python wheel 包"

    cd src/python

    log_info "构建 wheel 包..."
    python3 setup.py bdist_wheel || {
        log_warning "Python wheel 构建失败"
        return 1
    }

    if [ -d "dist/" ] && [ "$(ls -A dist/)" ]; then
        log_success "Python wheel 构建成功:"
        ls -la dist/
    else
        log_warning "Python wheel 构建未生成文件"
    fi

    cd "$PROJECT_ROOT"
}

# 验证构建结果
verify_build() {
    log_section "✅ 验证构建结果"

    local all_good=true

    # 检查 C++ 构建结果
    log_info "检查 C++ 构建结果..."
    if [ -f "build/cpp/libqadataswap_core.so" ]; then
        log_success "✓ C++ 核心库: build/cpp/libqadataswap_core.so"

        # 检查导出符号
        if nm -D build/cpp/libqadataswap_core.so | grep -q "qads_"; then
            log_success "✓ C++ FFI 符号导出正常"
        else
            log_warning "⚠ C++ FFI 符号可能未导出"
            all_good=false
        fi
    else
        log_error "✗ C++ 核心库编译失败"
        all_good=false
    fi

    # 检查 Python 构建结果
    log_info "检查 Python 构建结果..."
    if [ -f "src/python/qadataswap/qadataswap.cpython-"*".so" ]; then
        log_success "✓ Python 绑定库存在"
    else
        log_error "✗ Python 绑定库不存在"
        all_good=false
    fi

    # 检查 Rust 构建结果
    log_info "检查 Rust 构建结果..."
    local rust_examples=("basic_example" "rust_writer" "rust_reader" "performance_test")
    local rust_ok=true
    for exe in "${rust_examples[@]}"; do
        if [ -f "examples/rust/target/release/$exe" ]; then
            log_success "✓ Rust 示例: $exe"
        else
            log_error "✗ Rust 示例缺失: $exe"
            rust_ok=false
        fi
    done

    if $rust_ok; then
        log_success "✓ Rust 示例编译完整"
    else
        log_warning "⚠ 部分 Rust 示例编译失败"
        all_good=false
    fi

    # 总体结果
    if $all_good; then
        log_success "🎉 所有组件构建成功！"
        return 0
    else
        log_warning "⚠ 部分组件构建有问题，但可以继续使用"
        return 1
    fi
}

# 显示构建后的使用说明
show_usage() {
    log_section "📖 使用说明"

    echo "构建完成后，您可以："
    echo ""
    echo "1. 运行 C++ 示例："
    echo "   cd build/cpp/examples/cpp"
    echo "   ./basic_example"
    echo "   ./performance_test"
    echo ""
    echo "2. 运行 Rust 示例："
    echo "   cd examples/rust"
    echo "   cargo run --bin basic_example -- writer"
    echo "   cargo run --bin rust_writer demo_name"
    echo ""
    echo "3. 使用 Python 库："
    echo "   cd src/python"
    echo "   python3 -c \"import qadataswap; print('QADataSwap ready!')\""
    echo ""
    echo "4. 运行跨语言测试："
    echo "   python3 tests/integration/test_cross_language.py"
    echo ""
    echo "5. 运行性能基准测试："
    echo "   python3 tests/performance/benchmark_all.py"
    echo ""
}

# 主函数
main() {
    local start_time=$(date +%s)

    # 解析命令行参数
    local clean_flag=false
    local build_cpp=true
    local build_python=true
    local build_rust=true
    local build_wheel=false
    local skip_tests=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                clean_flag=true
                shift
                ;;
            --cpp-only)
                build_python=false
                build_rust=false
                shift
                ;;
            --python-only)
                build_cpp=false
                build_rust=false
                shift
                ;;
            --rust-only)
                build_cpp=false
                build_python=false
                shift
                ;;
            --wheel)
                build_wheel=true
                shift
                ;;
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --help)
                echo "用法: $0 [选项]"
                echo "选项:"
                echo "  --clean       清理所有构建文件"
                echo "  --cpp-only    只编译 C++"
                echo "  --python-only 只编译 Python"
                echo "  --rust-only   只编译 Rust"
                echo "  --wheel       构建 Python wheel"
                echo "  --skip-tests  跳过测试"
                echo "  --help        显示此帮助信息"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看帮助"
                exit 1
                ;;
        esac
    done

    # 检查依赖
    check_dependencies

    # 清理构建（如果需要）
    if $clean_flag; then
        clean_build
    fi

    # 构建各组件
    if $build_cpp; then
        build_cpp
    fi

    if $build_python; then
        build_python

        if $build_wheel; then
            build_python_wheel
        fi
    fi

    if $build_rust; then
        build_rust
    fi

    # 验证构建结果
    verify_build

    # 计算构建时间
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_section "🎯 构建完成"
    log_success "总构建时间: ${duration}s"

    # 显示使用说明
    show_usage
}

# 运行主函数
main "$@"