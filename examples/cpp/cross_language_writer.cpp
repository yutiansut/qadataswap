#include "qadataswap_core.h"
#include <iostream>
#include <vector>
#include <chrono>
#include <thread>
#include <arrow/api.h>

using namespace qadataswap;

int main(int argc, char* argv[]) {
    std::string shared_name = "cross_language_demo";
    if (argc > 1) {
        shared_name = argv[1];
    }

    std::cout << "C++ Cross-Language Writer" << std::endl;
    std::cout << "Shared memory name: " << shared_name << std::endl;
    std::cout << "=========================" << std::endl;

    // Create shared memory arena
    auto arena = CreateSharedDataFrame(shared_name, 200, 5);
    if (!arena->CreateWriter()) {
        std::cerr << "Failed to create writer for: " << shared_name << std::endl;
        return 1;
    }

    std::cout << "Writer created successfully" << std::endl;

    // Create schema for financial data
    auto schema = arrow::schema({
        arrow::field("timestamp", arrow::timestamp(arrow::TimeUnit::MICRO)),
        arrow::field("symbol", arrow::utf8()),
        arrow::field("price", arrow::float64()),
        arrow::field("volume", arrow::int64()),
        arrow::field("bid", arrow::float64()),
        arrow::field("ask", arrow::float64()),
        arrow::field("spread", arrow::float64())
    });

    // Simulate real-time market data
    std::vector<std::string> symbols = {"AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META"};

    for (int iteration = 0; iteration < 10; ++iteration) {
        std::cout << "\nSending market data batch " << (iteration + 1) << "/10" << std::endl;

        // Build arrays
        arrow::TimestampBuilder timestamp_builder(arrow::timestamp(arrow::TimeUnit::MICRO), arrow::default_memory_pool());
        arrow::StringBuilder symbol_builder;
        arrow::DoubleBuilder price_builder;
        arrow::Int64Builder volume_builder;
        arrow::DoubleBuilder bid_builder;
        arrow::DoubleBuilder ask_builder;
        arrow::DoubleBuilder spread_builder;

        auto now = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        size_t rows_per_batch = 10000;

        for (size_t i = 0; i < rows_per_batch; ++i) {
            auto& symbol = symbols[i % symbols.size()];
            double base_price = 100.0 + (i % 1000) * 0.1;
            double price = base_price + (rand() % 1000 - 500) * 0.01;
            int64_t volume = 100 + (rand() % 10000);
            double spread_val = 0.01 + (rand() % 100) * 0.0001;
            double bid = price - spread_val / 2;
            double ask = price + spread_val / 2;

            timestamp_builder.Append(now + i * 1000); // 1ms intervals
            symbol_builder.Append(symbol);
            price_builder.Append(price);
            volume_builder.Append(volume);
            bid_builder.Append(bid);
            ask_builder.Append(ask);
            spread_builder.Append(spread_val);
        }

        // Finish arrays
        std::shared_ptr<arrow::Array> timestamp_array, symbol_array, price_array,
                                     volume_array, bid_array, ask_array, spread_array;

        timestamp_builder.Finish(&timestamp_array);
        symbol_builder.Finish(&symbol_array);
        price_builder.Finish(&price_array);
        volume_builder.Finish(&volume_array);
        bid_builder.Finish(&bid_array);
        ask_builder.Finish(&ask_array);
        spread_builder.Finish(&spread_array);

        // Create record batch
        auto record_batch = arrow::RecordBatch::Make(
            schema, rows_per_batch,
            {timestamp_array, symbol_array, price_array, volume_array, bid_array, ask_array, spread_array});

        // Write to shared memory
        auto start_time = std::chrono::high_resolution_clock::now();

        auto write_status = arena->WriteRecordBatch(record_batch);
        if (!write_status.ok()) {
            std::cerr << "Failed to write batch " << iteration + 1 << ": "
                      << write_status.ToString() << std::endl;
            continue;
        }

        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);

        std::cout << "Batch " << (iteration + 1) << " written in " << duration.count()
                  << " microseconds (" << rows_per_batch << " rows)" << std::endl;

        // Calculate and display throughput
        size_t estimated_size = rows_per_batch * (8 + 10 + 8 + 8 + 8 + 8 + 8); // rough estimate
        double throughput_mb_s = (estimated_size / 1024.0 / 1024.0) / (duration.count() / 1000000.0);
        std::cout << "Estimated throughput: " << throughput_mb_s << " MB/s" << std::endl;

        // Wait before next batch (simulate real-time updates)
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }

    // Get final statistics
    auto stats = arena->GetStats();
    std::cout << "\nFinal Statistics:" << std::endl;
    std::cout << "  Total bytes written: " << stats.bytes_written << std::endl;
    std::cout << "  Total writes: " << stats.writes_count << std::endl;
    std::cout << "  Average bytes per write: " << (stats.bytes_written / stats.writes_count) << std::endl;

    arena->Close();
    std::cout << "\nC++ Writer finished. Data is available for Python/Rust readers." << std::endl;
    std::cout << "You can now run:" << std::endl;
    std::cout << "  python examples/python/cross_language_reader.py " << shared_name << std::endl;
    std::cout << "  cargo run --bin cross_language_reader -- " << shared_name << std::endl;

    return 0;
}