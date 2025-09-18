use polars::prelude::*;
use qadataswap::{SharedDataFrame, SharedMemoryConfig, Result};
use std::thread;
use std::time::{Duration, Instant};

fn writer_task(name: &str, num_rows: i32) -> Result<()> {
    println!("Writer: Starting with {} rows", num_rows);

    // Create writer
    let config = SharedMemoryConfig::new(name).with_size_mb(100);
    let writer = SharedDataFrame::create_writer(config)?;

    // Generate test data
    let df = df! {
        "id" => (0..num_rows).collect::<Vec<_>>(),
        "price" => (0..num_rows).map(|x| x as f64 * 1.5 + 100.0).collect::<Vec<_>>(),
        "volume" => (0..num_rows).map(|x| x * 10).collect::<Vec<_>>(),
        "symbol" => (0..num_rows).map(|i| match i % 5 {
            0 => "AAPL",
            1 => "MSFT",
            2 => "GOOGL",
            3 => "TSLA",
            _ => "NVDA",
        }).collect::<Vec<_>>(),
    }?;

    println!("Writer: Generated DataFrame with shape {:?}", df.shape());
    println!("Writer: Sample data:");
    println!("{}", df.head(Some(5)));

    // Write data (zero-copy)
    let start = Instant::now();
    writer.write(&df)?;
    let write_time = start.elapsed();

    println!("Writer: Data written in {:.4} seconds", write_time.as_secs_f64());
    writer.close();
    println!("Writer: Finished");

    Ok(())
}

fn reader_task(name: &str, expected_rows: i32) -> Result<()> {
    println!("Reader: Starting");

    // Wait a bit for writer to initialize
    thread::sleep(Duration::from_millis(500));

    // Create reader
    let config = SharedMemoryConfig::new(name);
    let reader = SharedDataFrame::create_reader(config)?;

    // Read data (zero-copy)
    let start = Instant::now();
    let df = reader.read(Some(10000))?; // 10 second timeout
    let read_time = start.elapsed();

    match df {
        Some(df) => {
            println!("Reader: Data read in {:.4} seconds", read_time.as_secs_f64());
            println!("Reader: Received DataFrame with shape {:?}", df.shape());

            // Verify data integrity
            assert_eq!(df.height(), expected_rows as usize,
                      "Expected {} rows, got {}", expected_rows, df.height());
            assert_eq!(df.width(), 4,
                      "Expected 4 columns, got {}", df.width());

            println!("Reader: Sample data:");
            println!("{}", df.head(Some(5)));

            // Perform some operations
            let result = df
                .lazy()
                .filter(col("price").gt(lit(500.0)))
                .group_by([col("symbol")])
                .agg([
                    col("volume").sum().alias("total_volume"),
                    col("price").mean().alias("avg_price"),
                    col("id").count().alias("count"),
                ])
                .sort("total_volume", SortMultipleOptions::default().with_order_descending(true))
                .collect()?;

            println!("Reader: Aggregation result:");
            println!("{}", result);

            reader.close();
            println!("Reader: Finished");
        }
        None => {
            println!("Reader: No data received (timeout)");
        }
    }

    Ok(())
}

fn benchmark_comparison() -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("PERFORMANCE COMPARISON");
    println!("{}", "=".repeat(60));

    let num_rows = 1000000;
    let df = df! {
        "id" => (0..num_rows).collect::<Vec<_>>(),
        "value" => (0..num_rows).map(|x| x as f64 * 1.5).collect::<Vec<_>>(),
    }?;

    // QADataSwap method
    println!("Testing QADataSwap (zero-copy)...");

    let write_time = {
        let config = SharedMemoryConfig::new("benchmark").with_size_mb(50);
        let writer = SharedDataFrame::create_writer(config)?;
        let start = Instant::now();
        writer.write(&df)?;
        start.elapsed()
    };

    let (read_time, rows_read) = {
        thread::sleep(Duration::from_millis(100)); // Ensure writer is ready
        let config = SharedMemoryConfig::new("benchmark");
        let reader = SharedDataFrame::create_reader(config)?;
        let start = Instant::now();
        let result = reader.read(Some(5000))?;
        let elapsed = start.elapsed();
        let rows = result.map(|df| df.height()).unwrap_or(0);
        (elapsed, rows)
    };

    println!("QADataSwap write: {:.4}s", write_time.as_secs_f64());
    println!("QADataSwap read:  {:.4}s ({} rows)", read_time.as_secs_f64(), rows_read);

    // Traditional method (serialization)
    println!("\nTesting traditional serialization...");

    let serialize_time = {
        let start = Instant::now();
        let mut buf = Vec::new();
        IpcWriter::new(&mut buf).finish(&mut df.clone())?;
        start.elapsed()
    };

    let deserialize_time = {
        let mut buf = Vec::new();
        IpcWriter::new(&mut buf).finish(&mut df.clone())?;
        let start = Instant::now();
        let cursor = std::io::Cursor::new(buf);
        let _df_restored = LazyFrame::scan_ipc(cursor, ScanArgsIpc::default())?;
        start.elapsed()
    };

    println!("Serialize:   {:.4}s", serialize_time.as_secs_f64());
    println!("Deserialize: {:.4}s", deserialize_time.as_secs_f64());

    // Memory usage comparison
    let memory_original = df.estimated_size("mb");

    println!("\nMemory usage:");
    println!("Original DataFrame: {:.2} MB", memory_original);
    println!("QADataSwap overhead: ~0 MB (zero-copy)");

    // Performance summary
    let total_qads = write_time + read_time;
    let total_traditional = serialize_time + deserialize_time;
    let speedup = total_traditional.as_secs_f64() / total_qads.as_secs_f64();

    println!("\nPerformance Summary:");
    println!("QADataSwap total:   {:.4}s", total_qads.as_secs_f64());
    println!("Traditional total:  {:.4}s", total_traditional.as_secs_f64());
    println!("Speedup:           {:.1}x", speedup);

    Ok(())
}

fn main() -> Result<()> {
    println!("QADataSwap Rust Basic Example with Polars");
    println!("{}", "=".repeat(50));

    let shared_name = "basic_example_rust";
    let num_rows = 1000000;

    // Start writer and reader tasks
    let writer_handle = {
        let name = shared_name.to_string();
        thread::spawn(move || writer_task(&name, num_rows))
    };

    let reader_handle = {
        let name = shared_name.to_string();
        thread::spawn(move || reader_task(&name, num_rows))
    };

    // Wait for both tasks to complete
    writer_handle.join().unwrap()?;
    reader_handle.join().unwrap()?;

    println!("\nBasic example completed successfully!");

    // Run performance comparison
    benchmark_comparison()?;

    Ok(())
}