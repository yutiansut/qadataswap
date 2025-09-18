#include "../include/qadataswap_core.h"
#include <cstring>
#include <memory>
#include <thread>
#include <chrono>

using namespace qadataswap;

// Simplified FFI interface - for demonstration purposes
extern "C" {

void* qads_create_arena(const char* name, size_t size, size_t buffer_count) {
    try {
        auto arena = CreateSharedDataFrame(std::string(name), size / (1024 * 1024), buffer_count);
        return arena.release();
    } catch (...) {
        return nullptr;
    }
}

void qads_destroy_arena(void* arena) {
    if (arena) {
        auto arena_ptr = static_cast<SharedMemoryArena*>(arena);
        delete arena_ptr;
    }
}

int qads_create_writer(void* arena) {
    if (!arena) return -1;

    try {
        auto arena_ptr = static_cast<SharedMemoryArena*>(arena);
        if (arena_ptr->CreateWriter()) {
            return 0; // success
        }
        return -1;
    } catch (...) {
        return -1;
    }
}

int qads_attach_reader(void* arena) {
    if (!arena) return -1;

    try {
        auto arena_ptr = static_cast<SharedMemoryArena*>(arena);
        if (arena_ptr->AttachReader()) {
            return 0; // success
        }
        return -1;
    } catch (...) {
        return -1;
    }
}

int qads_write_data(void* arena, const uint8_t* data, size_t size) {
    if (!arena || !data) return -1;

    // Simplified implementation - in practice would deserialize Arrow data
    // For demonstration, we'll just return success
    return 0;
}

int qads_read_data(void* arena, uint8_t* data, size_t max_size, size_t* actual_size, int timeout_ms) {
    if (!arena || !data || !actual_size) return -1;

    // Simplified implementation - return dummy data
    const char* dummy_data = "dummy_arrow_data";
    *actual_size = std::min(strlen(dummy_data), max_size);
    std::memcpy(data, dummy_data, *actual_size);

    return 0; // success
}

int qads_wait_for_data(void* arena, int timeout_ms) {
    if (!arena) return -1;

    // Simple wait implementation
    std::this_thread::sleep_for(std::chrono::milliseconds(std::min(timeout_ms, 100)));
    return 0;
}

void qads_notify_data_ready(void* arena) {
    // Simplified implementation - no-op
    (void)arena;
}

void qads_close(void* arena) {
    if (arena) {
        auto arena_ptr = static_cast<SharedMemoryArena*>(arena);
        arena_ptr->Close();
    }
}

} // extern "C"