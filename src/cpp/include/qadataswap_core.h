#pragma once

#include <memory>
#include <string>
#include <vector>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <semaphore.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#include <arrow/api.h>
#include <arrow/ipc/api.h>
#include <arrow/memory_pool.h>
#include <arrow/buffer.h>
#include <arrow/io/memory.h>

namespace qadataswap {

constexpr size_t CACHE_LINE_SIZE = 64;
constexpr uint32_t MAGIC_NUMBER = 0x51444153; // 'QDAS'
constexpr uint32_t VERSION = 1;

#pragma pack(push, 1)
struct alignas(CACHE_LINE_SIZE) SharedMemoryHeader {
    uint32_t magic;
    uint32_t version;
    size_t total_size;
    size_t header_size;

    // Schema information
    size_t schema_offset;
    size_t schema_size;

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

struct BufferDescriptor {
    size_t offset;
    size_t size;
    uint64_t sequence;
    uint64_t timestamp;
};
#pragma pack(pop)

class SharedMemoryArena {
public:
    explicit SharedMemoryArena(const std::string& name, size_t size,
                              size_t buffer_count = 3);
    ~SharedMemoryArena();

    // Writer interface
    bool CreateWriter();
    arrow::Status WriteRecordBatch(const std::shared_ptr<arrow::RecordBatch>& batch);
    arrow::Status WriteTable(const std::shared_ptr<arrow::Table>& table);

    // Reader interface
    bool AttachReader();
    arrow::Result<std::shared_ptr<arrow::RecordBatch>> ReadRecordBatch(int timeout_ms = -1);
    arrow::Result<std::shared_ptr<arrow::Table>> ReadTable(int timeout_ms = -1);

    // Advanced features
    arrow::Result<std::shared_ptr<arrow::RecordBatch>> ReadRecordBatchNoWait();
    arrow::Status WaitForData(int timeout_ms = -1);
    void NotifyDataReady();

    // Streaming interface
    class Writer;
    class Reader;

    std::unique_ptr<Writer> GetWriter();
    std::unique_ptr<Reader> GetReader();

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
    SharedMemoryHeader* header_;

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

    arrow::Status SerializeRecordBatch(const std::shared_ptr<arrow::RecordBatch>& batch,
                                      uint8_t* buffer, size_t buffer_size, size_t* out_size);
    arrow::Result<std::shared_ptr<arrow::RecordBatch>> DeserializeRecordBatch(
        const uint8_t* buffer, size_t size);

    arrow::Status SerializeSchema(const std::shared_ptr<arrow::Schema>& schema,
                                 uint8_t* buffer, size_t buffer_size, size_t* out_size);
    arrow::Result<std::shared_ptr<arrow::Schema>> DeserializeSchema(
        const uint8_t* buffer, size_t size);
};

// Streaming writer for large datasets
class SharedMemoryArena::Writer {
public:
    explicit Writer(SharedMemoryArena* arena);
    ~Writer();

    arrow::Status WriteChunk(const std::shared_ptr<arrow::RecordBatch>& batch);
    arrow::Status WriteChunk(const std::shared_ptr<arrow::Table>& table);
    arrow::Status Flush();
    arrow::Status Finish();

private:
    SharedMemoryArena* arena_;
    std::shared_ptr<arrow::Schema> current_schema_;
    bool finished_;
};

// Streaming reader for large datasets
class SharedMemoryArena::Reader {
public:
    explicit Reader(SharedMemoryArena* arena);
    ~Reader();

    arrow::Result<std::shared_ptr<arrow::RecordBatch>> ReadChunk(int timeout_ms = -1);
    arrow::Result<std::shared_ptr<arrow::Table>> ReadTable(int timeout_ms = -1);

    // Iterator interface
    class Iterator {
    public:
        Iterator(Reader* reader, bool end = false);

        std::shared_ptr<arrow::RecordBatch> operator*();
        Iterator& operator++();
        bool operator!=(const Iterator& other) const;

    private:
        Reader* reader_;
        std::shared_ptr<arrow::RecordBatch> current_batch_;
        bool is_end_;

        void LoadNext();
    };

    Iterator begin();
    Iterator end();

private:
    SharedMemoryArena* arena_;
    std::shared_ptr<arrow::Schema> cached_schema_;
};

// Factory functions for easier usage
std::unique_ptr<SharedMemoryArena> CreateSharedDataFrame(
    const std::string& name, size_t size_mb = 100, size_t buffer_count = 3);

// Utility functions for Polars integration
arrow::Result<std::shared_ptr<arrow::Table>> ArrowTableFromPolarsBytes(
    const uint8_t* data, size_t size);

arrow::Status PolarsTableToArrowBytes(
    const std::shared_ptr<arrow::Table>& table,
    std::vector<uint8_t>* out_bytes);

} // namespace qadataswap