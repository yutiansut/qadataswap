#include "qadataswap_core.h"
#include <chrono>
#include <cstring>
#include <iostream>
#include <arrow/ipc/writer.h>
#include <arrow/ipc/reader.h>

namespace qadataswap {

SharedMemoryArena::SharedMemoryArena(const std::string& name, size_t size, size_t buffer_count)
    : name_(name), total_size_(size), buffer_count_(buffer_count), shm_fd_(-1),
      mapped_memory_(nullptr), header_(nullptr), write_sem_(nullptr), read_sem_(nullptr),
      is_writer_(false), is_attached_(false) {

    // Calculate buffer size
    size_t header_size = sizeof(SharedMemoryHeader) +
                        sizeof(SharedMemoryHeader::BufferState) * buffer_count;
    header_size = (header_size + CACHE_LINE_SIZE - 1) & ~(CACHE_LINE_SIZE - 1); // Align

    buffer_size_ = (total_size_ - header_size) / buffer_count;
    buffer_size_ = buffer_size_ & ~(CACHE_LINE_SIZE - 1); // Align buffer size
}

SharedMemoryArena::~SharedMemoryArena() {
    Close();
}

bool SharedMemoryArena::CreateWriter() {
    if (is_attached_) return false;

    if (!CreateSharedMemory()) return false;

    InitializeHeader();
    is_writer_ = true;
    is_attached_ = true;

    // Create semaphores
    snprintf(header_->write_sem_name, sizeof(header_->write_sem_name),
             "/qads_w_%s", name_.c_str());
    snprintf(header_->read_sem_name, sizeof(header_->read_sem_name),
             "/qads_r_%s", name_.c_str());

    sem_unlink(header_->write_sem_name);
    sem_unlink(header_->read_sem_name);

    write_sem_ = sem_open(header_->write_sem_name, O_CREAT | O_EXCL, 0644, buffer_count_);
    read_sem_ = sem_open(header_->read_sem_name, O_CREAT | O_EXCL, 0644, 0);

    if (write_sem_ == SEM_FAILED || read_sem_ == SEM_FAILED) {
        std::cerr << "Failed to create semaphores\n";
        return false;
    }

    header_->writer_active.store(true);
    return true;
}

bool SharedMemoryArena::AttachReader() {
    if (is_attached_) return false;

    if (!AttachSharedMemory()) return false;

    is_writer_ = false;
    is_attached_ = true;

    // Open existing semaphores
    write_sem_ = sem_open(header_->write_sem_name, 0);
    read_sem_ = sem_open(header_->read_sem_name, 0);

    if (write_sem_ == SEM_FAILED || read_sem_ == SEM_FAILED) {
        std::cerr << "Failed to open semaphores\n";
        return false;
    }

    header_->reader_count.fetch_add(1);
    return true;
}

bool SharedMemoryArena::CreateSharedMemory() {
    std::string shm_name = "/qads_" + name_;
    shm_fd_ = shm_open(shm_name.c_str(), O_CREAT | O_EXCL | O_RDWR, 0644);

    if (shm_fd_ == -1) {
        std::cerr << "Failed to create shared memory: " << strerror(errno) << std::endl;
        return false;
    }

    if (ftruncate(shm_fd_, total_size_) == -1) {
        std::cerr << "Failed to set shared memory size\n";
        close(shm_fd_);
        shm_unlink(shm_name.c_str());
        return false;
    }

    mapped_memory_ = mmap(nullptr, total_size_, PROT_READ | PROT_WRITE,
                         MAP_SHARED, shm_fd_, 0);

    if (mapped_memory_ == MAP_FAILED) {
        std::cerr << "Failed to map shared memory\n";
        close(shm_fd_);
        shm_unlink(shm_name.c_str());
        return false;
    }

    header_ = static_cast<SharedMemoryHeader*>(mapped_memory_);
    return true;
}

bool SharedMemoryArena::AttachSharedMemory() {
    std::string shm_name = "/qads_" + name_;
    shm_fd_ = shm_open(shm_name.c_str(), O_RDWR, 0644);

    if (shm_fd_ == -1) {
        std::cerr << "Failed to open shared memory\n";
        return false;
    }

    // Get the size first
    struct stat st;
    if (fstat(shm_fd_, &st) == -1) {
        std::cerr << "Failed to get shared memory size\n";
        close(shm_fd_);
        return false;
    }

    total_size_ = st.st_size;

    mapped_memory_ = mmap(nullptr, total_size_, PROT_READ | PROT_WRITE,
                         MAP_SHARED, shm_fd_, 0);

    if (mapped_memory_ == MAP_FAILED) {
        std::cerr << "Failed to map shared memory\n";
        close(shm_fd_);
        return false;
    }

    header_ = static_cast<SharedMemoryHeader*>(mapped_memory_);

    // Verify header
    if (header_->magic != MAGIC_NUMBER || header_->version != VERSION) {
        std::cerr << "Invalid shared memory header\n";
        munmap(mapped_memory_, total_size_);
        close(shm_fd_);
        return false;
    }

    buffer_count_ = header_->buffer_count;
    buffer_size_ = header_->buffer_size;

    return true;
}

void SharedMemoryArena::InitializeHeader() {
    // Use placement new for proper initialization
    new (header_) SharedMemoryHeader();

    // Initialize the flexible array member
    for (size_t i = 0; i < buffer_count_; ++i) {
        new (&header_->buffer_states[i]) SharedMemoryHeader::BufferState();
    }

    header_->magic = MAGIC_NUMBER;
    header_->version = VERSION;
    header_->total_size = total_size_;
    header_->header_size = sizeof(SharedMemoryHeader) +
                          sizeof(SharedMemoryHeader::BufferState) * buffer_count_;

    header_->buffer_count = buffer_count_;
    header_->buffer_size = buffer_size_;
    header_->buffers_offset = (header_->header_size + CACHE_LINE_SIZE - 1) &
                             ~(CACHE_LINE_SIZE - 1);

    header_->schema_offset = 0;
    header_->schema_size = 0;

    // Initialize buffer states
    for (size_t i = 0; i < buffer_count_; ++i) {
        header_->buffer_states[i].data_size.store(0);
        header_->buffer_states[i].ready.store(false);
        header_->buffer_states[i].timestamp.store(0);
    }
}

arrow::Status SharedMemoryArena::WriteTable(const std::shared_ptr<arrow::Table>& table) {
    // Convert table to record batch
    auto batches_result = table->CombineChunksToBatch();
    if (!batches_result.ok()) {
        return batches_result.status();
    }
    return WriteRecordBatch(batches_result.ValueOrDie());
}

arrow::Status SharedMemoryArena::WriteRecordBatch(
    const std::shared_ptr<arrow::RecordBatch>& batch) {

    if (!is_writer_ || !is_attached_) {
        return arrow::Status::Invalid("Not attached as writer");
    }

    // Wait for available write buffer
    if (sem_wait(write_sem_) != 0) {
        return arrow::Status::IOError("Failed to wait for write semaphore");
    }

    size_t buffer_idx = GetNextWriteBuffer();
    size_t buffer_offset = header_->buffers_offset + buffer_idx * buffer_size_;
    uint8_t* buffer = static_cast<uint8_t*>(mapped_memory_) + buffer_offset;

    size_t serialized_size;
    ARROW_RETURN_NOT_OK(SerializeRecordBatch(batch, buffer, buffer_size_, &serialized_size));

    // Update buffer state
    auto now = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();

    header_->buffer_states[buffer_idx].data_size.store(serialized_size);
    header_->buffer_states[buffer_idx].timestamp.store(now);
    header_->buffer_states[buffer_idx].ready.store(true);

    header_->write_sequence.fetch_add(1);

    // Signal readers
    sem_post(read_sem_);

    stats_.bytes_written += serialized_size;
    stats_.writes_count++;

    return arrow::Status::OK();
}

arrow::Result<std::shared_ptr<arrow::RecordBatch>> SharedMemoryArena::ReadRecordBatch(
    int timeout_ms) {

    if (is_writer_ || !is_attached_) {
        return arrow::Status::Invalid("Not attached as reader");
    }

    // Wait for data
    if (timeout_ms >= 0) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_sec += timeout_ms / 1000;
        ts.tv_nsec += (timeout_ms % 1000) * 1000000;
        if (ts.tv_nsec >= 1000000000) {
            ts.tv_sec += 1;
            ts.tv_nsec -= 1000000000;
        }

        if (sem_timedwait(read_sem_, &ts) != 0) {
            if (errno == ETIMEDOUT) {
                stats_.wait_timeouts++;
                return arrow::Status::IOError("Timeout waiting for data");
            }
            return arrow::Status::IOError("Failed to wait for read semaphore");
        }
    } else {
        if (sem_wait(read_sem_) != 0) {
            return arrow::Status::IOError("Failed to wait for read semaphore");
        }
    }

    size_t buffer_idx = GetCurrentReadBuffer();

    if (!header_->buffer_states[buffer_idx].ready.load()) {
        sem_post(write_sem_); // Return write token
        return arrow::Status::IOError("Buffer not ready");
    }

    size_t buffer_offset = header_->buffers_offset + buffer_idx * buffer_size_;
    const uint8_t* buffer = static_cast<const uint8_t*>(mapped_memory_) + buffer_offset;
    size_t data_size = header_->buffer_states[buffer_idx].data_size.load();

    auto result = DeserializeRecordBatch(buffer, data_size);

    // Mark buffer as read
    header_->buffer_states[buffer_idx].ready.store(false);
    header_->read_sequence.fetch_add(1);

    // Return write token
    sem_post(write_sem_);

    if (result.ok()) {
        stats_.bytes_read += data_size;
        stats_.reads_count++;
    }

    return result;
}

arrow::Result<std::shared_ptr<arrow::Table>> SharedMemoryArena::ReadTable(int timeout_ms) {
    auto batch_result = ReadRecordBatch(timeout_ms);
    if (!batch_result.ok()) {
        return batch_result.status();
    }
    auto batch = batch_result.ValueOrDie();
    return arrow::Table::FromRecordBatches({batch});
}

size_t SharedMemoryArena::GetNextWriteBuffer() {
    return header_->write_sequence.load() % buffer_count_;
}

size_t SharedMemoryArena::GetCurrentReadBuffer() {
    return header_->read_sequence.load() % buffer_count_;
}

arrow::Status SharedMemoryArena::SerializeRecordBatch(
    const std::shared_ptr<arrow::RecordBatch>& batch,
    uint8_t* buffer, size_t buffer_size, size_t* out_size) {

    auto output_stream = std::make_shared<arrow::io::FixedSizeBufferWriter>(
        arrow::MutableBuffer::Wrap(buffer, buffer_size));

    ARROW_ASSIGN_OR_RAISE(auto writer,
        arrow::ipc::MakeStreamWriter(output_stream, batch->schema()));

    ARROW_RETURN_NOT_OK(writer->WriteRecordBatch(*batch));
    ARROW_RETURN_NOT_OK(writer->Close());

    *out_size = output_stream->Tell().ValueOrDie();
    return arrow::Status::OK();
}

arrow::Result<std::shared_ptr<arrow::RecordBatch>> SharedMemoryArena::DeserializeRecordBatch(
    const uint8_t* buffer, size_t size) {

    auto input_stream = std::make_shared<arrow::io::BufferReader>(buffer, size);

    ARROW_ASSIGN_OR_RAISE(auto reader,
        arrow::ipc::RecordBatchStreamReader::Open(input_stream));

    std::shared_ptr<arrow::RecordBatch> batch;
    ARROW_RETURN_NOT_OK(reader->ReadNext(&batch));

    return batch;
}

arrow::Result<std::shared_ptr<arrow::RecordBatch>> SharedMemoryArena::ReadRecordBatchNoWait() {
    return ReadRecordBatch(0);  // 0 timeout for no wait
}

arrow::Status SharedMemoryArena::WaitForData(int timeout_ms) {
    if (timeout_ms >= 0) {
        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_sec += timeout_ms / 1000;
        ts.tv_nsec += (timeout_ms % 1000) * 1000000;
        if (ts.tv_nsec >= 1000000000) {
            ts.tv_sec += 1;
            ts.tv_nsec -= 1000000000;
        }

        if (sem_timedwait(read_sem_, &ts) != 0) {
            if (errno == ETIMEDOUT) {
                return arrow::Status::IOError("Timeout waiting for data");
            }
            return arrow::Status::IOError("Failed to wait for read semaphore");
        }
    } else {
        if (sem_wait(read_sem_) != 0) {
            return arrow::Status::IOError("Failed to wait for read semaphore");
        }
    }

    // Put back the semaphore since we were only checking
    sem_post(read_sem_);
    return arrow::Status::OK();
}

void SharedMemoryArena::NotifyDataReady() {
    sem_post(read_sem_);
}

std::unique_ptr<SharedMemoryArena::Writer> SharedMemoryArena::GetWriter() {
    if (!is_writer_) return nullptr;
    return std::make_unique<Writer>(this);
}

std::unique_ptr<SharedMemoryArena::Reader> SharedMemoryArena::GetReader() {
    if (is_writer_) return nullptr;
    return std::make_unique<Reader>(this);
}

void SharedMemoryArena::Close() {
    if (mapped_memory_) {
        if (is_writer_) {
            header_->writer_active.store(false);
        } else {
            header_->reader_count.fetch_sub(1);
        }

        munmap(mapped_memory_, total_size_);
        mapped_memory_ = nullptr;
    }

    if (shm_fd_ != -1) {
        close(shm_fd_);
        shm_fd_ = -1;
    }

    if (write_sem_ && write_sem_ != SEM_FAILED) {
        sem_close(write_sem_);
        if (is_writer_) {
            sem_unlink(header_->write_sem_name);
        }
    }

    if (read_sem_ && read_sem_ != SEM_FAILED) {
        sem_close(read_sem_);
        if (is_writer_) {
            sem_unlink(header_->read_sem_name);
        }
    }

    if (is_writer_) {
        std::string shm_name = "/qads_" + name_;
        shm_unlink(shm_name.c_str());
    }

    is_attached_ = false;
}

// Writer implementation
SharedMemoryArena::Writer::Writer(SharedMemoryArena* arena)
    : arena_(arena), finished_(false) {
}

SharedMemoryArena::Writer::~Writer() {
    if (!finished_) {
        (void)Finish(); // Ignore return value in destructor
    }
}

arrow::Status SharedMemoryArena::Writer::WriteChunk(const std::shared_ptr<arrow::RecordBatch>& batch) {
    if (finished_) {
        return arrow::Status::Invalid("Writer has been finished");
    }
    return arena_->WriteRecordBatch(batch);
}

arrow::Status SharedMemoryArena::Writer::WriteChunk(const std::shared_ptr<arrow::Table>& table) {
    if (finished_) {
        return arrow::Status::Invalid("Writer has been finished");
    }
    return arena_->WriteTable(table);
}

arrow::Status SharedMemoryArena::Writer::Flush() {
    // For shared memory, data is immediately available
    return arrow::Status::OK();
}

arrow::Status SharedMemoryArena::Writer::Finish() {
    finished_ = true;
    return arrow::Status::OK();
}

// Reader implementation
SharedMemoryArena::Reader::Reader(SharedMemoryArena* arena)
    : arena_(arena) {
}

SharedMemoryArena::Reader::~Reader() {
}

arrow::Result<std::shared_ptr<arrow::RecordBatch>> SharedMemoryArena::Reader::ReadChunk(int timeout_ms) {
    return arena_->ReadRecordBatch(timeout_ms);
}

arrow::Result<std::shared_ptr<arrow::Table>> SharedMemoryArena::Reader::ReadTable(int timeout_ms) {
    return arena_->ReadTable(timeout_ms);
}

// Iterator implementation
SharedMemoryArena::Reader::Iterator::Iterator(Reader* reader, bool end)
    : reader_(reader), is_end_(end) {
    if (!is_end_) {
        LoadNext();
    }
}

std::shared_ptr<arrow::RecordBatch> SharedMemoryArena::Reader::Iterator::operator*() {
    return current_batch_;
}

SharedMemoryArena::Reader::Iterator& SharedMemoryArena::Reader::Iterator::operator++() {
    LoadNext();
    return *this;
}

bool SharedMemoryArena::Reader::Iterator::operator!=(const Iterator& other) const {
    return is_end_ != other.is_end_;
}

void SharedMemoryArena::Reader::Iterator::LoadNext() {
    auto result = reader_->ReadChunk(100); // 100ms timeout
    if (!result.ok() || !result.ValueOrDie()) {
        is_end_ = true;
        current_batch_ = nullptr;
    } else {
        current_batch_ = result.ValueOrDie();
    }
}

SharedMemoryArena::Reader::Iterator SharedMemoryArena::Reader::begin() {
    return Iterator(this, false);
}

SharedMemoryArena::Reader::Iterator SharedMemoryArena::Reader::end() {
    return Iterator(this, true);
}

std::unique_ptr<SharedMemoryArena> CreateSharedDataFrame(
    const std::string& name, size_t size_mb, size_t buffer_count) {
    return std::make_unique<SharedMemoryArena>(name, size_mb * 1024 * 1024, buffer_count);
}

} // namespace qadataswap