cmake_minimum_required(VERSION 3.16)
project(QADataSwap_Examples)

# C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(PkgConfig REQUIRED)
pkg_check_modules(ARROW REQUIRED arrow)

# Include directories
include_directories(../../src/cpp/include)
include_directories(${ARROW_INCLUDE_DIRS})

# Compiler flags
add_compile_options(-Wall -Wextra -O2)

# Link directories
link_directories(${ARROW_LIBRARY_DIRS})

# Basic example
add_executable(basic_example basic_example.cpp ../../src/cpp/src/shared_memory_arena.cpp)
target_link_libraries(basic_example ${ARROW_LIBRARIES} rt pthread)

# Cross-language example (writer only)
add_executable(cpp_writer cross_language_writer.cpp ../../src/cpp/src/shared_memory_arena.cpp)
target_link_libraries(cpp_writer ${ARROW_LIBRARIES} rt pthread)

# Cross-language example (reader only)
add_executable(cpp_reader cross_language_reader.cpp ../../src/cpp/src/shared_memory_arena.cpp)
target_link_libraries(cpp_reader ${ARROW_LIBRARIES} rt pthread)

# Performance benchmark
add_executable(performance_test performance_test.cpp ../../src/cpp/src/shared_memory_arena.cpp)
target_link_libraries(performance_test ${ARROW_LIBRARIES} rt pthread)

# Install targets
install(TARGETS basic_example cpp_writer cpp_reader performance_test
        RUNTIME DESTINATION bin)