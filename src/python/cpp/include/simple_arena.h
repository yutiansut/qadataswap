#pragma once

#include <memory>
#include <string>
#include <atomic>
#include <semaphore.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdint>

namespace qadataswap {

constexpr size_t CACHE_LINE_SIZE = 64;
constexpr uint32_t MAGIC_NUMBER = 0x51444153; // 'QDAS'
constexpr uint32_t VERSION = 1;

#pragma pack(push, 1)
struct alignas(CACHE_LINE_SIZE) SimpleHeader {
    uint32_t magic;
    uint32_t version;
    size_t total_size;
    size_t header_size;

    // Ring buffer configuration
    size_t buffer_count;
    size_t buffer_size;
    size_t buffers_offset;

    // Synchronization
    std::atomic<uint64_t> write_sequence{0};
    std::atomic<uint64_t> read_sequence{0};
    std::atomic<bool> writer_active{false};
    std::atomic<int32_t> reader_count{0};

    // POSIX named semaphores
    char write_sem_name[64];
    char read_sem_name[64];

    // Buffer states (one per buffer)
    struct BufferState {
        std::atomic<uint64_t> data_size{0};
        std::atomic<bool> ready{false};
        std::atomic<uint64_t> timestamp{0};
    };

    BufferState buffer_states[];
};
#pragma pack(pop)

class SimpleArena {
public:
    explicit SimpleArena(const std::string& name, size_t size, size_t buffer_count = 3);
    ~SimpleArena();

    // Writer interface
    bool CreateWriter();
    bool WriteBytes(const uint8_t* data, size_t size);

    // Reader interface
    bool AttachReader();
    bool ReadBytes(uint8_t* buffer, size_t buffer_size, size_t* out_size, int timeout_ms = -1);

    void Close();

    // Statistics
    struct Stats {
        uint64_t bytes_written = 0;
        uint64_t bytes_read = 0;
        uint64_t writes_count = 0;
        uint64_t reads_count = 0;
        uint64_t wait_timeouts = 0;
    };

    Stats GetStats() const { return stats_; }

private:
    std::string name_;
    size_t total_size_;
    size_t buffer_count_;
    size_t buffer_size_;

    int shm_fd_;
    void* mapped_memory_;
    SimpleHeader* header_;

    sem_t* write_sem_;
    sem_t* read_sem_;

    bool is_writer_;
    bool is_attached_;

    mutable Stats stats_;

    bool CreateSharedMemory();
    bool AttachSharedMemory();
    void InitializeHeader();
    size_t GetNextWriteBuffer();
    size_t GetCurrentReadBuffer();
};

} // namespace qadataswap