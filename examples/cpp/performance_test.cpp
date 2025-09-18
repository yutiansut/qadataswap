#include "qadataswap_core.h"
#include <iostream>
#include <vector>
#include <chrono>
#include <thread>
#include <arrow/api.h>

using namespace qadataswap;

void benchmark_throughput() {
    std::cout << "=== Throughput Benchmark ===" << std::endl;

    std::vector<size_t> test_sizes = {1000, 10000, 100000, 1000000};

    for (auto num_rows : test_sizes) {
        std::cout << "\nTesting with " << num_rows << " rows:" << std::endl;

        // Create arena
        auto arena = CreateSharedDataFrame("perf_test_" + std::to_string(num_rows), 500, 3);
        if (!arena->CreateWriter()) {
            std::cerr << "Failed to create writer" << std::endl;
            continue;
        }

        // Create test data
        auto schema = arrow::schema({
            arrow::field("id", arrow::int64()),
            arrow::field("value1", arrow::float64()),
            arrow::field("value2", arrow::float64()),
            arrow::field("category", arrow::utf8())
        });

        arrow::Int64Builder id_builder;
        arrow::DoubleBuilder value1_builder;
        arrow::DoubleBuilder value2_builder;
        arrow::StringBuilder category_builder;

        for (size_t i = 0; i < num_rows; ++i) {
            id_builder.Append(static_cast<int64_t>(i));
            value1_builder.Append(i * 3.14);
            value2_builder.Append(i * 2.71);
            category_builder.Append("cat_" + std::to_string(i % 10));
        }

        std::shared_ptr<arrow::Array> id_array, value1_array, value2_array, category_array;
        id_builder.Finish(&id_array);
        value1_builder.Finish(&value1_array);
        value2_builder.Finish(&value2_array);
        category_builder.Finish(&category_array);

        auto record_batch = arrow::RecordBatch::Make(
            schema, num_rows, {id_array, value1_array, value2_array, category_array});

        // Measure write performance
        auto start_time = std::chrono::high_resolution_clock::now();
        auto write_status = arena->WriteRecordBatch(record_batch);
        auto end_time = std::chrono::high_resolution_clock::now();

        if (!write_status.ok()) {
            std::cerr << "Write failed: " << write_status.ToString() << std::endl;
            continue;
        }

        auto write_duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);

        // Estimate data size
        size_t estimated_size = num_rows * (8 + 8 + 8 + 10); // rough estimate
        double write_throughput = (estimated_size / 1024.0 / 1024.0) / (write_duration.count() / 1000000.0);

        std::cout << "Write: " << write_duration.count() << " μs, "
                  << write_throughput << " MB/s" << std::endl;

        // Test reader performance
        auto reader_arena = CreateSharedDataFrame("perf_test_" + std::to_string(num_rows));
        if (!reader_arena->AttachReader()) {
            std::cerr << "Failed to attach reader" << std::endl;
            continue;
        }

        start_time = std::chrono::high_resolution_clock::now();
        auto read_result = reader_arena->ReadRecordBatch(5000);
        end_time = std::chrono::high_resolution_clock::now();

        if (!read_result.ok()) {
            std::cerr << "Read failed: " << read_result.status().ToString() << std::endl;
            continue;
        }

        auto read_duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
        double read_throughput = (estimated_size / 1024.0 / 1024.0) / (read_duration.count() / 1000000.0);

        std::cout << "Read:  " << read_duration.count() << " μs, "
                  << read_throughput << " MB/s" << std::endl;

        arena->Close();
        reader_arena->Close();
    }
}

void benchmark_latency() {
    std::cout << "\n=== Latency Benchmark ===" << std::endl;

    auto arena = CreateSharedDataFrame("latency_test", 100, 10);
    if (!arena->CreateWriter()) {
        std::cerr << "Failed to create writer" << std::endl;
        return;
    }

    // Small message for latency test
    auto schema = arrow::schema({arrow::field("timestamp", arrow::int64())});

    std::vector<double> latencies;
    int num_tests = 1000;

    for (int i = 0; i < num_tests; ++i) {
        arrow::Int64Builder builder;
        auto now = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::high_resolution_clock::now().time_since_epoch()).count();

        builder.Append(now);

        std::shared_ptr<arrow::Array> array;
        builder.Finish(&array);

        auto record_batch = arrow::RecordBatch::Make(schema, 1, {array});

        auto start_time = std::chrono::high_resolution_clock::now();
        auto status = arena->WriteRecordBatch(record_batch);
        auto end_time = std::chrono::high_resolution_clock::now();

        if (status.ok()) {
            auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
            latencies.push_back(duration.count());
        }

        // Small delay between tests
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    }

    // Calculate statistics
    if (!latencies.empty()) {
        std::sort(latencies.begin(), latencies.end());

        double sum = 0;
        for (auto latency : latencies) sum += latency;
        double mean = sum / latencies.size();

        std::cout << "Latency statistics (" << latencies.size() << " samples):" << std::endl;
        std::cout << "  Mean: " << mean << " μs" << std::endl;
        std::cout << "  Min:  " << latencies.front() << " μs" << std::endl;
        std::cout << "  Max:  " << latencies.back() << " μs" << std::endl;
        std::cout << "  P50:  " << latencies[latencies.size() / 2] << " μs" << std::endl;
        std::cout << "  P95:  " << latencies[latencies.size() * 95 / 100] << " μs" << std::endl;
        std::cout << "  P99:  " << latencies[latencies.size() * 99 / 100] << " μs" << std::endl;
    }

    arena->Close();
}

void benchmark_concurrent() {
    std::cout << "\n=== Concurrent Access Benchmark ===" << std::endl;

    const std::string shared_name = "concurrent_test";
    const int num_writers = 4;
    const int num_readers = 2;
    const int messages_per_writer = 100;

    std::vector<std::thread> threads;
    std::atomic<int> total_writes{0};
    std::atomic<int> total_reads{0};

    auto start_time = std::chrono::high_resolution_clock::now();

    // Start writers
    for (int w = 0; w < num_writers; ++w) {
        threads.emplace_back([w, messages_per_writer, &total_writes, &shared_name]() {
            auto arena = CreateSharedDataFrame(shared_name + "_" + std::to_string(w), 200, 5);
            if (!arena->CreateWriter()) {
                std::cerr << "Writer " << w << " failed to create arena" << std::endl;
                return;
            }

            auto schema = arrow::schema({
                arrow::field("writer_id", arrow::int32()),
                arrow::field("message_id", arrow::int32()),
                arrow::field("timestamp", arrow::int64())
            });

            for (int m = 0; m < messages_per_writer; ++m) {
                arrow::Int32Builder writer_builder, message_builder;
                arrow::Int64Builder timestamp_builder;

                writer_builder.Append(w);
                message_builder.Append(m);
                timestamp_builder.Append(std::chrono::duration_cast<std::chrono::microseconds>(
                    std::chrono::high_resolution_clock::now().time_since_epoch()).count());

                std::shared_ptr<arrow::Array> writer_array, message_array, timestamp_array;
                writer_builder.Finish(&writer_array);
                message_builder.Finish(&message_array);
                timestamp_builder.Finish(&timestamp_array);

                auto record_batch = arrow::RecordBatch::Make(
                    schema, 1, {writer_array, message_array, timestamp_array});

                if (arena->WriteRecordBatch(record_batch).ok()) {
                    total_writes.fetch_add(1);
                }

                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }

            arena->Close();
        });
    }

    // Start readers
    for (int r = 0; r < num_readers; ++r) {
        threads.emplace_back([r, num_writers, messages_per_writer, &total_reads, &shared_name]() {
            std::this_thread::sleep_for(std::chrono::milliseconds(100)); // Let writers start

            for (int w = 0; w < num_writers; ++w) {
                auto arena = CreateSharedDataFrame(shared_name + "_" + std::to_string(w));
                if (!arena->AttachReader()) {
                    continue;
                }

                for (int m = 0; m < messages_per_writer; ++m) {
                    auto result = arena->ReadRecordBatch(1000); // 1 second timeout
                    if (result.ok()) {
                        total_reads.fetch_add(1);
                    } else {
                        break; // Timeout or error
                    }
                }

                arena->Close();
            }
        });
    }

    // Wait for all threads
    for (auto& thread : threads) {
        thread.join();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto total_duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);

    std::cout << "Concurrent benchmark results:" << std::endl;
    std::cout << "  Writers: " << num_writers << std::endl;
    std::cout << "  Readers: " << num_readers << std::endl;
    std::cout << "  Total writes: " << total_writes.load() << std::endl;
    std::cout << "  Total reads: " << total_reads.load() << std::endl;
    std::cout << "  Duration: " << total_duration.count() << " ms" << std::endl;
    std::cout << "  Write rate: " << (total_writes.load() * 1000.0 / total_duration.count()) << " writes/sec" << std::endl;
    std::cout << "  Read rate: " << (total_reads.load() * 1000.0 / total_duration.count()) << " reads/sec" << std::endl;
}

int main() {
    std::cout << "QADataSwap C++ Performance Tests" << std::endl;
    std::cout << "=================================" << std::endl;

    benchmark_throughput();
    benchmark_latency();
    benchmark_concurrent();

    std::cout << "\nAll performance tests completed!" << std::endl;
    return 0;
}