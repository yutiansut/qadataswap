cmake_minimum_required(VERSION 3.16)
project(QADataSwap
    VERSION 0.1.0
    DESCRIPTION "High-performance cross-language zero-copy data transfer framework"
    LANGUAGES CXX)

# C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build configuration
set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type")
set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "RelWithDebInfo")

# Options
option(BUILD_TESTS "Build tests" ON)
option(BUILD_BENCHMARKS "Build benchmarks" ON)
option(BUILD_EXAMPLES "Build examples" ON)
option(BUILD_PYTHON_BINDINGS "Build Python bindings" ON)

# Find dependencies
find_package(PkgConfig REQUIRED)
pkg_check_modules(ARROW REQUIRED arrow)

# Include directories
include_directories(src/cpp/include)
include_directories(${ARROW_INCLUDE_DIRS})

# Compiler flags
add_compile_options(-Wall -Wextra -O3 -fPIC)
# Note: Skip problematic Arrow compile definitions that may contain invalid macro names

# Core library
add_library(qadataswap_core SHARED
    src/cpp/src/shared_memory_arena.cpp
)

target_link_libraries(qadataswap_core
    ${ARROW_LIBRARIES}
    rt
    pthread
)

target_include_directories(qadataswap_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/cpp/include>
    $<INSTALL_INTERFACE:include>
)

# Examples
if(BUILD_EXAMPLES AND EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/examples/cpp/CMakeLists.txt)
    add_subdirectory(examples/cpp)
endif()

# Tests
if(BUILD_TESTS AND EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/tests/unit/CMakeLists.txt)
    enable_testing()
    add_subdirectory(tests/unit)
endif()

# Installation
install(TARGETS qadataswap_core
    EXPORT QADataSwapTargets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
    INCLUDES DESTINATION include
)

install(DIRECTORY src/cpp/include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)

# Export configuration
install(EXPORT QADataSwapTargets
    FILE QADataSwapTargets.cmake
    NAMESPACE QADataSwap::
    DESTINATION lib/cmake/QADataSwap
)

# Generate config file
include(CMakePackageConfigHelpers)
write_basic_package_version_file(
    QADataSwapConfigVersion.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY AnyNewerVersion
)

install(FILES
    cmake/QADataSwapConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/QADataSwapConfigVersion.cmake
    DESTINATION lib/cmake/QADataSwap
)