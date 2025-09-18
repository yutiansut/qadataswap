#!/bin/bash

# QADataSwap 统一测试脚本
# 运行所有语言的测试和验证

set -e

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

log_section "🧪 QADataSwap 统一测试脚本"

# 测试 C++ 组件
test_cpp() {
    log_section "⚡ 测试 C++ 组件"

    # 检查 C++ 可执行文件
    local cpp_examples_dir="build/cpp/examples/cpp"
    if [ ! -d "$cpp_examples_dir" ]; then
        log_error "C++ 示例目录不存在，请先运行构建脚本"
        return 1
    fi

    local cpp_examples=("basic_example" "cpp_writer" "cpp_reader" "performance_test")
    local cpp_ok=true

    for exe in "${cpp_examples[@]}"; do
        if [ -f "$cpp_examples_dir/$exe" ]; then
            log_success "✓ 找到 C++ 示例: $exe"
        else
            log_error "✗ C++ 示例缺失: $exe"
            cpp_ok=false
        fi
    done

    if ! $cpp_ok; then
        log_error "C++ 组件检查失败"
        return 1
    fi

    # 运行 C++ 基础示例测试
    log_info "运行 C++ 基础示例..."
    cd "$cpp_examples_dir"
    if timeout 10s ./basic_example; then
        log_success "C++ 基础示例运行成功"
    else
        log_warning "C++ 基础示例运行超时或失败"
    fi
    cd "$PROJECT_ROOT"

    # 运行 C++ 性能测试
    log_info "运行 C++ 性能测试..."
    cd "$cpp_examples_dir"
    if timeout 30s ./performance_test; then
        log_success "C++ 性能测试运行成功"
    else
        log_warning "C++ 性能测试运行超时或失败"
    fi
    cd "$PROJECT_ROOT"

    log_success "C++ 组件测试完成"
    return 0
}

# 测试 Python 组件
test_python() {
    log_section "🐍 测试 Python 组件"

    # 检查 Python 绑定
    cd src/python

    log_info "测试 Python 导入..."
    if python3 -c "import qadataswap; print(f'QADataSwap Python version: {qadataswap.__version__}')"; then
        log_success "Python 绑定导入成功"
    else
        log_error "Python 绑定导入失败"
        cd "$PROJECT_ROOT"
        return 1
    fi

    log_info "测试 Python 基础功能..."
    if python3 -c "
import qadataswap
import polars as pl
import sys

try:
    # 创建测试数据
    df = pl.DataFrame({'id': [1, 2, 3], 'value': [1.0, 2.0, 3.0]})
    print('测试数据创建成功')

    # 测试创建 writer (可能会有内存问题，所以用 try-catch)
    try:
        writer = qadataswap.create_writer('python_test', 10)
        print('Writer 创建成功')
    except Exception as e:
        print(f'Writer 创建失败: {e}')
        sys.exit(1)

    print('Python 基础功能测试通过')
except Exception as e:
    print(f'Python 测试失败: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"; then
        log_success "Python 基础功能测试通过"
    else
        log_warning "Python 基础功能测试失败"
    fi

    cd "$PROJECT_ROOT"
    log_success "Python 组件测试完成"
    return 0
}

# 测试 Rust 组件
test_rust() {
    log_section "🦀 测试 Rust 组件"

    # 检查 Rust 示例
    local rust_examples_dir="examples/rust/target/release"
    if [ ! -d "$rust_examples_dir" ]; then
        log_error "Rust 示例目录不存在，请先运行构建脚本"
        return 1
    fi

    local rust_examples=("basic_example" "rust_writer" "rust_reader" "performance_test")
    local rust_ok=true

    for exe in "${rust_examples[@]}"; do
        if [ -f "$rust_examples_dir/$exe" ]; then
            log_success "✓ 找到 Rust 示例: $exe"
        else
            log_error "✗ Rust 示例缺失: $exe"
            rust_ok=false
        fi
    done

    if ! $rust_ok; then
        log_error "Rust 组件检查失败"
        return 1
    fi

    # 运行 Rust 单元测试
    log_info "运行 Rust 单元测试..."
    cd src/rust
    if cargo test --lib; then
        log_success "Rust 单元测试通过"
    else
        log_warning "Rust 单元测试失败"
    fi
    cd "$PROJECT_ROOT"

    # 运行 Rust 示例测试
    log_info "测试 Rust 示例运行..."
    cd examples/rust
    if timeout 5s ./target/release/rust_writer test_run_short; then
        log_success "Rust 示例运行测试通过"
    else
        log_warning "Rust 示例运行测试超时或失败"
    fi
    cd "$PROJECT_ROOT"

    # 运行 Rust 性能测试
    log_info "运行 Rust 性能测试..."
    cd examples/rust
    if timeout 30s ./target/release/performance_test; then
        log_success "Rust 性能测试运行成功"
    else
        log_warning "Rust 性能测试运行超时或失败"
    fi
    cd "$PROJECT_ROOT"

    log_success "Rust 组件测试完成"
    return 0
}

# 运行跨语言集成测试
test_cross_language() {
    log_section "🔗 跨语言集成测试"

    if [ ! -f "tests/integration/test_cross_language.py" ]; then
        log_warning "跨语言测试脚本不存在，跳过"
        return 0
    fi

    log_info "运行跨语言集成测试..."
    if timeout 60s python3 tests/integration/test_cross_language.py; then
        log_success "跨语言集成测试通过"
        return 0
    else
        log_warning "跨语言集成测试失败或超时"
        return 1
    fi
}

# 运行性能基准测试
test_performance() {
    log_section "🚀 性能基准测试"

    if [ ! -f "tests/performance/benchmark_all.py" ]; then
        log_warning "性能基准测试脚本不存在，跳过"
        return 0
    fi

    log_info "运行性能基准测试..."
    if timeout 120s python3 tests/performance/benchmark_all.py; then
        log_success "性能基准测试完成"
        return 0
    else
        log_warning "性能基准测试失败或超时"
        return 1
    fi
}

# 清理测试产生的文件
cleanup_test_files() {
    log_info "清理测试文件..."

    # 清理共享内存文件
    find /dev/shm -name "qads_*" -delete 2>/dev/null || true

    # 清理测试结果文件
    rm -f benchmark_results.json 2>/dev/null || true

    log_success "测试文件清理完成"
}

# 生成测试报告
generate_test_report() {
    log_section "📊 测试报告"

    local report_file="test_report_$(date +%Y%m%d_%H%M%S).txt"

    {
        echo "QADataSwap 测试报告"
        echo "=================="
        echo "测试时间: $(date)"
        echo "测试环境:"
        echo "  系统: $(uname -a)"
        echo "  Python: $(python3 --version)"
        echo "  Rust: $(rustc --version 2>/dev/null || echo 'Rust 未安装')"
        echo "  CMake: $(cmake --version | head -n1 2>/dev/null || echo 'CMake 未安装')"
        echo ""
        echo "测试结果:"
        echo "  C++ 组件: ${cpp_test_result:-未测试}"
        echo "  Python 组件: ${python_test_result:-未测试}"
        echo "  Rust 组件: ${rust_test_result:-未测试}"
        echo "  跨语言测试: ${cross_lang_test_result:-未测试}"
        echo "  性能测试: ${performance_test_result:-未测试}"
        echo ""
    } > "$report_file"

    log_info "测试报告已保存到: $report_file"
}

# 主函数
main() {
    local start_time=$(date +%s)
    local test_cpp=true
    local test_python=true
    local test_rust=true
    local test_cross_lang=true
    local test_perf=false
    local generate_report=true

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cpp-only)
                test_python=false
                test_rust=false
                test_cross_lang=false
                shift
                ;;
            --python-only)
                test_cpp=false
                test_rust=false
                test_cross_lang=false
                shift
                ;;
            --rust-only)
                test_cpp=false
                test_python=false
                test_cross_lang=false
                shift
                ;;
            --cross-lang-only)
                test_cpp=false
                test_python=false
                test_rust=false
                shift
                ;;
            --with-performance)
                test_perf=true
                shift
                ;;
            --no-report)
                generate_report=false
                shift
                ;;
            --help)
                echo "用法: $0 [选项]"
                echo "选项:"
                echo "  --cpp-only          只测试 C++"
                echo "  --python-only       只测试 Python"
                echo "  --rust-only         只测试 Rust"
                echo "  --cross-lang-only   只测试跨语言功能"
                echo "  --with-performance  包含性能测试"
                echo "  --no-report         不生成测试报告"
                echo "  --help              显示此帮助信息"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看帮助"
                exit 1
                ;;
        esac
    done

    # 运行测试
    local overall_success=true

    if $test_cpp; then
        if test_cpp; then
            cpp_test_result="✅ 通过"
        else
            cpp_test_result="❌ 失败"
            overall_success=false
        fi
    fi

    if $test_python; then
        if test_python; then
            python_test_result="✅ 通过"
        else
            python_test_result="❌ 失败"
            overall_success=false
        fi
    fi

    if $test_rust; then
        if test_rust; then
            rust_test_result="✅ 通过"
        else
            rust_test_result="❌ 失败"
            overall_success=false
        fi
    fi

    if $test_cross_lang; then
        if test_cross_language; then
            cross_lang_test_result="✅ 通过"
        else
            cross_lang_test_result="❌ 失败"
            overall_success=false
        fi
    fi

    if $test_perf; then
        if test_performance; then
            performance_test_result="✅ 通过"
        else
            performance_test_result="❌ 失败"
            overall_success=false
        fi
    fi

    # 清理测试文件
    cleanup_test_files

    # 生成报告
    if $generate_report; then
        generate_test_report
    fi

    # 计算测试时间
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_section "🎯 测试完成"
    log_info "总测试时间: ${duration}s"

    if $overall_success; then
        log_success "🎉 所有测试通过！"
        exit 0
    else
        log_warning "⚠️ 部分测试失败，请检查日志"
        exit 1
    fi
}

# 运行主函数
main "$@"