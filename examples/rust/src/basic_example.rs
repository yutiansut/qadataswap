mod lib;
use lib::{SharedDataFrame, SharedMemoryConfig, Result};
use polars::prelude::*;
use std::time::{Duration, Instant};
use std::thread;

fn create_sample_dataframe(rows: usize) -> Result<DataFrame> {
    let ids: Vec<i64> = (0..rows as i64).collect();
    let values1: Vec<f64> = (0..rows).map(|i| i as f64 * 3.14).collect();
    let values2: Vec<f64> = (0..rows).map(|i| i as f64 * 2.71).collect();
    let categories: Vec<String> = (0..rows).map(|i| format!("cat_{}", i % 10)).collect();

    let df = df! {
        "id" => ids,
        "value1" => values1,
        "value2" => values2,
        "category" => categories,
    }?;

    Ok(df)
}

fn writer_process() -> Result<()> {
    println!("=== Rust Basic Writer Example ===");

    let shared_name = "rust_basic_demo";
    let config = SharedMemoryConfig::new(shared_name)
        .with_size_mb(100)
        .with_buffer_count(5);
    let arena = SharedDataFrame::create_writer(config)?;

    println!("Writer created successfully");

    // Send 5 batches of data
    for i in 0..5 {
        println!("\nSending batch {}/5", i + 1);

        let df = create_sample_dataframe(1000)?;
        println!("Created DataFrame with {} rows, {} columns", df.height(), df.width());

        let start = Instant::now();
        arena.write(&df)?;
        let duration = start.elapsed();

        println!("Batch {} written in {:?}", i + 1, duration);

        // Calculate throughput
        let estimated_size = df.height() * df.width() * 8; // rough estimate
        let throughput_mb_s = (estimated_size as f64 / 1024.0 / 1024.0) / duration.as_secs_f64();
        println!("Estimated throughput: {:.2} MB/s", throughput_mb_s);

        thread::sleep(Duration::from_millis(500));
    }

    println!("\nWriter finished. Data available for readers.");
    Ok(())
}

fn reader_process() -> Result<()> {
    println!("=== Rust Basic Reader Example ===");

    // Wait for writer to initialize
    println!("Waiting for writer to initialize...");
    thread::sleep(Duration::from_millis(1000));

    let shared_name = "rust_basic_demo";
    let config = SharedMemoryConfig::new(shared_name);
    let arena = SharedDataFrame::create_reader(config)?;

    println!("Reader attached successfully");

    let mut batch_count = 0;
    let max_batches = 10;

    while batch_count < max_batches {
        println!("\nWaiting for batch {}...", batch_count + 1);

        let start = Instant::now();
        match arena.read(Some(10000)) { // 10 seconds in milliseconds
            Ok(Some(df)) => {
                let duration = start.elapsed();

                println!("Batch {} received in {:?}", batch_count + 1, duration);
                println!("Shape: {} rows, {} columns", df.height(), df.width());

                // Display schema (first batch only)
                if batch_count == 0 {
                    println!("\nSchema:");
                    for (name, dtype) in df.get_column_names().iter().zip(df.dtypes()) {
                        println!("  {}: {:?}", name, dtype);
                    }
                }

                // Display sample data (first 3 rows)
                println!("\nSample data (first 3 rows):");
                let sample_df = df.head(Some(3));
                println!("{}", sample_df);

                // Perform some analysis on numeric columns
                if let Ok(stats) = df.clone().lazy().select([
                    col("value1").mean().alias("value1_mean"),
                    col("value1").min().alias("value1_min"),
                    col("value1").max().alias("value1_max"),
                    col("value2").sum().alias("value2_sum"),
                ]).collect() {
                    println!("\nStatistics:");
                    println!("{}", stats);
                }

                // Calculate throughput
                let estimated_size = df.height() * df.width() * 8;
                let throughput_mb_s = (estimated_size as f64 / 1024.0 / 1024.0) / duration.as_secs_f64();
                println!("Read throughput: {:.2} MB/s", throughput_mb_s);

                batch_count += 1;
            }
            Ok(None) => {
                println!("No data available. Writer might have finished.");
                break;
            }
            Err(e) => {
                if e.to_string().contains("Timeout") {
                    println!("Timeout waiting for data. Writer might have finished.");
                    break;
                } else {
                    eprintln!("Failed to read batch {}: {}", batch_count + 1, e);
                    break;
                }
            }
        }
    }

    println!("\nReader finished. Read {} batches total.", batch_count);
    Ok(())
}

fn main() -> Result<()> {
    println!("QADataSwap Rust Basic Example");
    println!("=============================");

    let args: Vec<String> = std::env::args().collect();

    if args.len() < 2 {
        println!("Usage:");
        println!("  {} writer   - Run as writer", args[0]);
        println!("  {} reader   - Run as reader", args[0]);
        println!();
        println!("Example:");
        println!("  # Terminal 1 (writer):");
        println!("  cargo run --bin basic_example -- writer");
        println!();
        println!("  # Terminal 2 (reader):");
        println!("  cargo run --bin basic_example -- reader");
        return Ok(());
    }

    match args[1].as_str() {
        "writer" => writer_process()?,
        "reader" => reader_process()?,
        _ => {
            eprintln!("Invalid mode. Use 'writer' or 'reader'");
            std::process::exit(1);
        }
    }

    Ok(())
}