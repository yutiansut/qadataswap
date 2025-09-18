#include "qadataswap_core.h"
#include <iostream>
#include <chrono>
#include <thread>
#include <arrow/api.h>
#include <arrow/compute/api.h>

using namespace qadataswap;

int main(int argc, char* argv[]) {
    std::string shared_name = "cross_language_demo";
    if (argc > 1) {
        shared_name = argv[1];
    }

    std::cout << "C++ Cross-Language Reader" << std::endl;
    std::cout << "Shared memory name: " << shared_name << std::endl;
    std::cout << "=========================" << std::endl;

    // Wait for writer to initialize
    std::cout << "Waiting for writer to initialize..." << std::endl;
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));

    // Create shared memory arena
    auto arena = CreateSharedDataFrame(shared_name);
    if (!arena->AttachReader()) {
        std::cerr << "Failed to attach reader for: " << shared_name << std::endl;
        std::cerr << "Make sure a writer is running first!" << std::endl;
        return 1;
    }

    std::cout << "Reader attached successfully" << std::endl;

    int batch_count = 0;
    int max_batches = 20; // Read up to 20 batches

    while (batch_count < max_batches) {
        std::cout << "\nWaiting for batch " << (batch_count + 1) << "..." << std::endl;

        // Read from shared memory with timeout
        auto start_time = std::chrono::high_resolution_clock::now();

        auto read_result = arena->ReadRecordBatch(15000); // 15 second timeout
        if (!read_result.ok()) {
            if (read_result.status().message().find("Timeout") != std::string::npos) {
                std::cout << "Timeout waiting for data. Writer might have finished." << std::endl;
                break;
            } else {
                std::cerr << "Failed to read batch " << (batch_count + 1) << ": "
                          << read_result.status().ToString() << std::endl;
                break;
            }
        }

        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);

        auto record_batch = read_result.ValueOrDie();

        std::cout << "Batch " << (batch_count + 1) << " received in " << duration.count()
                  << " microseconds" << std::endl;
        std::cout << "Shape: " << record_batch->num_rows() << " rows, "
                  << record_batch->num_columns() << " columns" << std::endl;

        // Display schema (first batch only)
        if (batch_count == 0) {
            std::cout << "\nSchema:" << std::endl;
            std::cout << record_batch->schema()->ToString() << std::endl;
        }

        // Display sample data (first few rows)
        std::cout << "\nSample data (first 3 rows):" << std::endl;
        for (int64_t row = 0; row < std::min(3L, record_batch->num_rows()); ++row) {
            std::cout << "Row " << row << ": ";
            for (int col = 0; col < record_batch->num_columns(); ++col) {
                auto array = record_batch->column(col);
                auto scalar_result = array->GetScalar(row);
                if (scalar_result.ok()) {
                    std::cout << scalar_result.ValueOrDie()->ToString();
                    if (col < record_batch->num_columns() - 1) std::cout << ", ";
                }
            }
            std::cout << std::endl;
        }

        // Perform some analysis on the data
        if (record_batch->num_columns() >= 3) {
            auto price_column = record_batch->column(2); // Assuming price is 3rd column

            // Calculate statistics
            auto sum_result = arrow::compute::Sum(price_column);
            auto mean_result = arrow::compute::Mean(price_column);
            auto min_result = arrow::compute::MinMax(price_column);

            if (sum_result.ok() && mean_result.ok() && min_result.ok()) {
                auto sum_scalar = sum_result.ValueOrDie().scalar();
                auto mean_scalar = mean_result.ValueOrDie().scalar();
                auto minmax_scalar = min_result.ValueOrDie().scalar_as<arrow::StructScalar>();

                std::cout << "\nPrice Analysis:" << std::endl;
                std::cout << "  Sum: " << sum_scalar->ToString() << std::endl;
                std::cout << "  Mean: " << mean_scalar->ToString() << std::endl;

                if (minmax_scalar.value.size() >= 2) {
                    std::cout << "  Min: " << minmax_scalar.value[0]->ToString() << std::endl;
                    std::cout << "  Max: " << minmax_scalar.value[1]->ToString() << std::endl;
                }
            }
        }

        // Calculate and display throughput
        size_t estimated_size = record_batch->num_rows() * 8 * record_batch->num_columns(); // rough estimate
        double throughput_mb_s = (estimated_size / 1024.0 / 1024.0) / (duration.count() / 1000000.0);
        std::cout << "Read throughput: " << throughput_mb_s << " MB/s" << std::endl;

        batch_count++;
    }

    // Get final statistics
    auto stats = arena->GetStats();
    std::cout << "\nFinal Statistics:" << std::endl;
    std::cout << "  Total bytes read: " << stats.bytes_read << std::endl;
    std::cout << "  Total reads: " << stats.reads_count << std::endl;
    std::cout << "  Wait timeouts: " << stats.wait_timeouts << std::endl;
    if (stats.reads_count > 0) {
        std::cout << "  Average bytes per read: " << (stats.bytes_read / stats.reads_count) << std::endl;
    }

    arena->Close();
    std::cout << "\nC++ Reader finished. Read " << batch_count << " batches total." << std::endl;

    return 0;
}