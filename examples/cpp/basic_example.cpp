#include "qadataswap_core.h"
#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <arrow/api.h>
#include <arrow/compute/api.h>

using namespace qadataswap;

void writer_example() {
    std::cout << "C++ Writer: Starting..." << std::endl;

    // Create shared memory arena
    auto arena = CreateSharedDataFrame("cpp_example", 100, 3);
    if (!arena->CreateWriter()) {
        std::cerr << "Failed to create writer" << std::endl;
        return;
    }

    // Create test data
    auto schema = arrow::schema({
        arrow::field("id", arrow::int64()),
        arrow::field("value", arrow::float64()),
        arrow::field("name", arrow::utf8()),
        arrow::field("active", arrow::boolean())
    });

    // Build arrays
    arrow::Int64Builder id_builder;
    arrow::DoubleBuilder value_builder;
    arrow::StringBuilder name_builder;
    arrow::BooleanBuilder active_builder;

    size_t num_rows = 10000;

    for (size_t i = 0; i < num_rows; ++i) {
        auto status = id_builder.Append(static_cast<int64_t>(i));
        if (!status.ok()) {
            std::cerr << "Failed to append id: " << status.ToString() << std::endl;
            return;
        }

        status = value_builder.Append(i * 3.14);
        if (!status.ok()) {
            std::cerr << "Failed to append value: " << status.ToString() << std::endl;
            return;
        }

        status = name_builder.Append("item_" + std::to_string(i));
        if (!status.ok()) {
            std::cerr << "Failed to append name: " << status.ToString() << std::endl;
            return;
        }

        status = active_builder.Append(i % 2 == 0);
        if (!status.ok()) {
            std::cerr << "Failed to append active: " << status.ToString() << std::endl;
            return;
        }
    }

    // Finish arrays
    std::shared_ptr<arrow::Array> id_array, value_array, name_array, active_array;

    auto result = id_builder.Finish(&id_array);
    if (!result.ok()) {
        std::cerr << "Failed to finish id array: " << result.ToString() << std::endl;
        return;
    }

    result = value_builder.Finish(&value_array);
    if (!result.ok()) {
        std::cerr << "Failed to finish value array: " << result.ToString() << std::endl;
        return;
    }

    result = name_builder.Finish(&name_array);
    if (!result.ok()) {
        std::cerr << "Failed to finish name array: " << result.ToString() << std::endl;
        return;
    }

    result = active_builder.Finish(&active_array);
    if (!result.ok()) {
        std::cerr << "Failed to finish active array: " << result.ToString() << std::endl;
        return;
    }

    // Create record batch
    auto record_batch = arrow::RecordBatch::Make(
        schema, num_rows, {id_array, value_array, name_array, active_array});

    std::cout << "C++ Writer: Created RecordBatch with " << record_batch->num_rows()
              << " rows, " << record_batch->num_columns() << " columns" << std::endl;

    // Write to shared memory
    auto start_time = std::chrono::high_resolution_clock::now();

    auto write_status = arena->WriteRecordBatch(record_batch);
    if (!write_status.ok()) {
        std::cerr << "Failed to write: " << write_status.ToString() << std::endl;
        return;
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);

    std::cout << "C++ Writer: Data written in " << duration.count() << " microseconds" << std::endl;

    // Get statistics
    auto stats = arena->GetStats();
    std::cout << "C++ Writer Statistics:" << std::endl;
    std::cout << "  Bytes written: " << stats.bytes_written << std::endl;
    std::cout << "  Writes count: " << stats.writes_count << std::endl;

    arena->Close();
    std::cout << "C++ Writer: Finished" << std::endl;
}

void reader_example() {
    std::cout << "C++ Reader: Starting..." << std::endl;

    // Wait for writer to initialize
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Create shared memory arena
    auto arena = CreateSharedDataFrame("cpp_example");
    if (!arena->AttachReader()) {
        std::cerr << "Failed to attach reader" << std::endl;
        return;
    }

    // Read from shared memory
    auto start_time = std::chrono::high_resolution_clock::now();

    auto read_result = arena->ReadRecordBatch(10000); // 10 second timeout
    if (!read_result.ok()) {
        std::cerr << "Failed to read: " << read_result.status().ToString() << std::endl;
        return;
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);

    auto record_batch = read_result.ValueOrDie();

    std::cout << "C++ Reader: Data read in " << duration.count() << " microseconds" << std::endl;
    std::cout << "C++ Reader: Received RecordBatch with " << record_batch->num_rows()
              << " rows, " << record_batch->num_columns() << " columns" << std::endl;

    // Print sample data
    std::cout << "C++ Reader: Sample data (first 5 rows):" << std::endl;
    std::cout << record_batch->schema()->ToString() << std::endl;

    for (int64_t i = 0; i < std::min(5L, record_batch->num_rows()); ++i) {
        std::cout << "Row " << i << ": ";
        for (int col = 0; col < record_batch->num_columns(); ++col) {
            auto array = record_batch->column(col);
            auto scalar_result = array->GetScalar(i);
            if (scalar_result.ok()) {
                std::cout << scalar_result.ValueOrDie()->ToString() << " ";
            }
        }
        std::cout << std::endl;
    }

    // Perform computation
    auto id_column = record_batch->column(0);
    auto value_column = record_batch->column(1);

    // Calculate sum of values
    auto sum_result = arrow::compute::Sum(value_column);
    if (sum_result.ok()) {
        auto sum_scalar = sum_result.ValueOrDie().scalar();
        std::cout << "C++ Reader: Sum of values: " << sum_scalar->ToString() << std::endl;
    }

    // Calculate mean of values
    auto mean_result = arrow::compute::Mean(value_column);
    if (mean_result.ok()) {
        auto mean_scalar = mean_result.ValueOrDie().scalar();
        std::cout << "C++ Reader: Mean of values: " << mean_scalar->ToString() << std::endl;
    }

    // Get statistics
    auto stats = arena->GetStats();
    std::cout << "C++ Reader Statistics:" << std::endl;
    std::cout << "  Bytes read: " << stats.bytes_read << std::endl;
    std::cout << "  Reads count: " << stats.reads_count << std::endl;

    arena->Close();
    std::cout << "C++ Reader: Finished" << std::endl;
}

void streaming_example() {
    std::cout << "\n=== C++ Streaming Example ===" << std::endl;

    std::thread writer_thread([]() {
        auto arena = CreateSharedDataFrame("cpp_streaming", 200, 8);
        if (!arena->CreateWriter()) {
            std::cerr << "Failed to create streaming writer" << std::endl;
            return;
        }

        auto writer = arena->GetWriter();

        // Send multiple batches
        for (int batch_num = 0; batch_num < 5; ++batch_num) {
            auto schema = arrow::schema({
                arrow::field("batch_id", arrow::int32()),
                arrow::field("sequence", arrow::int64()),
                arrow::field("timestamp", arrow::timestamp(arrow::TimeUnit::MICRO)),
                arrow::field("data", arrow::float64())
            });

            arrow::Int32Builder batch_id_builder;
            arrow::Int64Builder sequence_builder;
            arrow::TimestampBuilder timestamp_builder(arrow::timestamp(arrow::TimeUnit::MICRO), arrow::default_memory_pool());
            arrow::DoubleBuilder data_builder;

            size_t batch_size = 1000;
            auto now = std::chrono::duration_cast<std::chrono::microseconds>(
                std::chrono::system_clock::now().time_since_epoch()).count();

            for (size_t i = 0; i < batch_size; ++i) {
                batch_id_builder.Append(batch_num);
                sequence_builder.Append(batch_num * batch_size + i);
                timestamp_builder.Append(now + i);
                data_builder.Append(batch_num * 100.0 + i * 0.1);
            }

            std::shared_ptr<arrow::Array> batch_id_array, sequence_array, timestamp_array, data_array;
            batch_id_builder.Finish(&batch_id_array);
            sequence_builder.Finish(&sequence_array);
            timestamp_builder.Finish(&timestamp_array);
            data_builder.Finish(&data_array);

            auto record_batch = arrow::RecordBatch::Make(
                schema, batch_size, {batch_id_array, sequence_array, timestamp_array, data_array});

            auto status = writer->WriteChunk(record_batch);
            if (status.ok()) {
                std::cout << "Streaming Writer: Sent batch " << batch_num << std::endl;
            } else {
                std::cerr << "Failed to write batch " << batch_num << ": " << status.ToString() << std::endl;
            }

            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }

        writer->Finish();
        arena->Close();
        std::cout << "Streaming Writer: Finished" << std::endl;
    });

    std::thread reader_thread([]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));

        auto arena = CreateSharedDataFrame("cpp_streaming");
        if (!arena->AttachReader()) {
            std::cerr << "Failed to attach streaming reader" << std::endl;
            return;
        }

        auto reader = arena->GetReader();

        for (int batch_num = 0; batch_num < 5; ++batch_num) {
            auto read_result = reader->ReadChunk(5000); // 5 second timeout
            if (read_result.ok()) {
                auto batch = read_result.ValueOrDie();
                if (batch) {
                    std::cout << "Streaming Reader: Received batch " << batch_num
                             << " with " << batch->num_rows() << " rows" << std::endl;

                    // Print first few values
                    if (batch->num_rows() > 0) {
                        auto batch_id = std::static_pointer_cast<arrow::Int32Array>(batch->column(0))->Value(0);
                        auto first_seq = std::static_pointer_cast<arrow::Int64Array>(batch->column(1))->Value(0);
                        auto last_seq = std::static_pointer_cast<arrow::Int64Array>(batch->column(1))->Value(batch->num_rows() - 1);

                        std::cout << "  Batch ID: " << batch_id
                                 << ", Sequence: " << first_seq << " - " << last_seq << std::endl;
                    }
                } else {
                    std::cout << "Streaming Reader: End of stream" << std::endl;
                    break;
                }
            } else {
                std::cerr << "Failed to read batch " << batch_num << ": " << read_result.status().ToString() << std::endl;
                break;
            }
        }

        arena->Close();
        std::cout << "Streaming Reader: Finished" << std::endl;
    });

    writer_thread.join();
    reader_thread.join();
}

int main() {
    std::cout << "QADataSwap C++ Examples" << std::endl;
    std::cout << "=======================" << std::endl;

    // Basic example with separate writer and reader
    std::cout << "\n--- Basic Example ---" << std::endl;

    std::thread writer_thread(writer_example);
    std::thread reader_thread(reader_example);

    writer_thread.join();
    reader_thread.join();

    // Streaming example
    streaming_example();

    std::cout << "\nAll C++ examples completed!" << std::endl;
    return 0;
}