mod lib;
use lib::{SharedDataFrame, SharedMemoryConfig, Result};
use polars::prelude::*;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use std::thread;
use rand::Rng;

fn create_market_data(rows: usize, symbols: &[&str]) -> Result<DataFrame> {
    let mut rng = rand::thread_rng();
    let now_micros = SystemTime::now()
        .duration_since(UNIX_EPOCH)?
        .as_micros() as i64;

    let mut timestamps = Vec::with_capacity(rows);
    let mut symbol_list = Vec::with_capacity(rows);
    let mut prices = Vec::with_capacity(rows);
    let mut volumes = Vec::with_capacity(rows);
    let mut bids = Vec::with_capacity(rows);
    let mut asks = Vec::with_capacity(rows);
    let mut spreads = Vec::with_capacity(rows);

    for i in 0..rows {
        let symbol = symbols[i % symbols.len()];
        let base_price = 100.0 + (i % 1000) as f64 * 0.1;
        let price = base_price + (rng.gen::<f64>() - 0.5) * 10.0;
        let volume = 100 + rng.gen::<u64>() % 10000;
        let spread = 0.01 + rng.gen::<f64>() * 0.01;
        let bid = price - spread / 2.0;
        let ask = price + spread / 2.0;

        timestamps.push(now_micros + (i as i64 * 1000)); // 1ms intervals
        symbol_list.push(symbol.to_string());
        prices.push(price);
        volumes.push(volume as i64);
        bids.push(bid);
        asks.push(ask);
        spreads.push(spread);
    }

    let df = df! {
        "timestamp" => timestamps,
        "symbol" => symbol_list,
        "price" => prices,
        "volume" => volumes,
        "bid" => bids,
        "ask" => asks,
        "spread" => spreads,
    }?;

    Ok(df)
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let shared_name = if args.len() > 1 {
        args[1].clone()
    } else {
        "cross_language_demo".to_string()
    };

    println!("Rust Cross-Language Writer");
    println!("Shared memory name: {}", shared_name);
    println!("=========================");

    // Create shared memory arena
    let config = SharedMemoryConfig::new(&shared_name)
        .with_size_mb(200)
        .with_buffer_count(5);
    let arena = SharedDataFrame::create_writer(config)?;

    println!("Writer created successfully");

    // Market symbols
    let symbols = vec!["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META"];

    // Send 10 batches of market data
    for iteration in 0..10 {
        println!("\nSending market data batch {}/10", iteration + 1);

        let rows_per_batch = 10000;
        let df = create_market_data(rows_per_batch, &symbols)?;

        let start = Instant::now();
        arena.write(&df)?;
        let duration = start.elapsed();

        println!(
            "Batch {} written in {:?} ({} rows)",
            iteration + 1,
            duration,
            rows_per_batch
        );

        // Calculate and display throughput
        let estimated_size = rows_per_batch * 7 * 8; // 7 columns * 8 bytes (rough estimate)
        let throughput_mb_s = (estimated_size as f64 / 1024.0 / 1024.0) / duration.as_secs_f64();
        println!("Estimated throughput: {:.2} MB/s", throughput_mb_s);

        // Display sample of the data sent
        println!("\nSample data (first 3 rows):");
        let sample = df.head(Some(3));
        println!("{}", sample);

        // Wait before next batch (simulate real-time updates)
        thread::sleep(Duration::from_millis(1000));
    }

    println!("\nRust Writer finished. Data is available for C++/Python readers.");
    println!("You can now run:");
    println!("  ./cpp_reader {}", shared_name);
    println!("  python examples/python/cross_language_reader.py {}", shared_name);

    Ok(())
}