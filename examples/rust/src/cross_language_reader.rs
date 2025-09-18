use qadataswap::SharedDataFrame;
use polars::prelude::*;
use std::time::{Duration, Instant};
use std::thread;
use anyhow::Result;

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let shared_name = if args.len() > 1 {
        args[1].clone()
    } else {
        "cross_language_demo".to_string()
    };

    println!("Rust Cross-Language Reader");
    println!("Shared memory name: {}", shared_name);
    println!("=========================");

    // Wait for writer to initialize
    println!("Waiting for writer to initialize...");
    thread::sleep(Duration::from_millis(1000));

    // Create shared memory arena
    let arena = SharedDataFrame::new(&shared_name, 0, 0)?;
    arena.attach_reader()?;

    println!("Reader attached successfully");

    let mut batch_count = 0;
    let max_batches = 20; // Read up to 20 batches

    while batch_count < max_batches {
        println!("\nWaiting for batch {}...", batch_count + 1);

        // Read from shared memory with timeout
        let start = Instant::now();

        match arena.read(Duration::from_secs(15)) {
            Ok(df) => {
                let duration = start.elapsed();

                println!(
                    "Batch {} received in {:?}",
                    batch_count + 1,
                    duration
                );
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

                // Perform analysis on financial data
                if df.get_column_names().contains(&"price") {
                    let analysis = df.select([
                        col("price").sum().alias("total_volume_value"),
                        col("price").mean().alias("avg_price"),
                        col("price").min().alias("min_price"),
                        col("price").max().alias("max_price"),
                        col("volume").sum().alias("total_volume"),
                    ]);

                    if let Ok(stats) = analysis {
                        println!("\nPrice Analysis:");
                        println!("{}", stats);
                    }
                }

                // Group by symbol if available
                if df.get_column_names().contains(&"symbol") {
                    let symbol_stats = df
                        .lazy()
                        .group_by([col("symbol")])
                        .agg([
                            col("price").mean().alias("avg_price"),
                            col("volume").sum().alias("total_volume"),
                            col("price").count().alias("trade_count"),
                        ])
                        .collect();

                    if let Ok(stats) = symbol_stats {
                        println!("\nSymbol Statistics:");
                        println!("{}", stats);
                    }
                }

                // Calculate and display throughput
                let estimated_size = df.height() * df.width() * 8; // rough estimate
                let throughput_mb_s = (estimated_size as f64 / 1024.0 / 1024.0) / duration.as_secs_f64();
                println!("Read throughput: {:.2} MB/s", throughput_mb_s);

                batch_count += 1;
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

    println!("\nRust Reader finished. Read {} batches total.", batch_count);

    Ok(())
}