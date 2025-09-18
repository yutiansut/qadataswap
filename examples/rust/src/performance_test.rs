use qadataswap::SharedDataFrame;
use polars::prelude::*;
use std::time::{Duration, Instant};
use std::thread;
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicUsize, Ordering};
use anyhow::Result;

fn create_test_dataframe(rows: usize) -> Result<DataFrame> {
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

fn benchmark_throughput() -> Result<()> {
    println!("=== Throughput Benchmark ===");

    let test_sizes = vec![1000, 10000, 100000, 1000000];

    for num_rows in test_sizes {
        println!("\nTesting with {} rows:", num_rows);

        // Create arena
        let shared_name = format!("perf_test_{}", num_rows);
        let arena = SharedDataFrame::new(&shared_name, 500, 3)?;
        arena.create_writer()?;

        // Create test data
        let df = create_test_dataframe(num_rows)?;

        // Measure write performance
        let start_time = Instant::now();
        arena.write(&df)?;
        let write_duration = start_time.elapsed();

        // Estimate data size
        let estimated_size = num_rows * 4 * 8; // 4 columns * 8 bytes (rough estimate)
        let write_throughput = (estimated_size as f64 / 1024.0 / 1024.0) / write_duration.as_secs_f64();

        println!(
            "Write: {:?}, {:.2} MB/s",
            write_duration, write_throughput
        );

        // Test reader performance
        let reader_arena = SharedDataFrame::new(&shared_name, 0, 0)?;
        reader_arena.attach_reader()?;

        let start_time = Instant::now();
        let read_result = reader_arena.read(Duration::from_secs(5));
        let read_duration = start_time.elapsed();

        match read_result {
            Ok(_) => {
                let read_throughput = (estimated_size as f64 / 1024.0 / 1024.0) / read_duration.as_secs_f64();
                println!(
                    "Read:  {:?}, {:.2} MB/s",
                    read_duration, read_throughput
                );
            }
            Err(e) => {
                eprintln!("Read failed: {}", e);
            }
        }
    }

    Ok(())
}

fn benchmark_latency() -> Result<()> {
    println!("\n=== Latency Benchmark ===");

    let arena = SharedDataFrame::new("latency_test", 100, 10)?;
    arena.create_writer()?;

    // Small message for latency test
    let df = df! {
        "timestamp" => vec![chrono::Utc::now().timestamp_micros()],
    }?;

    let mut latencies = Vec::new();
    let num_tests = 1000;

    for i in 0..num_tests {
        let start_time = Instant::now();

        let test_df = df! {
            "timestamp" => vec![chrono::Utc::now().timestamp_micros() + i],
        }?;

        if arena.write(&test_df).is_ok() {
            let duration = start_time.elapsed();
            latencies.push(duration.as_micros() as f64);
        }

        // Small delay between tests
        thread::sleep(Duration::from_micros(100));
    }

    // Calculate statistics
    if !latencies.is_empty() {
        latencies.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let sum: f64 = latencies.iter().sum();
        let mean = sum / latencies.len() as f64;

        println!("Latency statistics ({} samples):", latencies.len());
        println!("  Mean: {:.2} μs", mean);
        println!("  Min:  {:.2} μs", latencies[0]);
        println!("  Max:  {:.2} μs", latencies[latencies.len() - 1]);
        println!("  P50:  {:.2} μs", latencies[latencies.len() / 2]);
        println!("  P95:  {:.2} μs", latencies[latencies.len() * 95 / 100]);
        println!("  P99:  {:.2} μs", latencies[latencies.len() * 99 / 100]);
    }

    Ok(())
}

fn benchmark_concurrent() -> Result<()> {
    println!("\n=== Concurrent Access Benchmark ===");

    let shared_name = "concurrent_test";
    let num_writers = 4;
    let num_readers = 2;
    let messages_per_writer = 100;

    let total_writes = Arc::new(AtomicUsize::new(0));
    let total_reads = Arc::new(AtomicUsize::new(0));

    let start_time = Instant::now();

    // Start writers
    let mut handles = vec![];

    for w in 0..num_writers {
        let total_writes_clone = Arc::clone(&total_writes);
        let writer_name = format!("{}_{}", shared_name, w);

        let handle = thread::spawn(move || -> Result<()> {
            let arena = SharedDataFrame::new(&writer_name, 200, 5)?;
            arena.create_writer()?;

            for m in 0..messages_per_writer {
                let df = df! {
                    "writer_id" => vec![w as i32],
                    "message_id" => vec![m as i32],
                    "timestamp" => vec![chrono::Utc::now().timestamp_micros()],
                }?;

                if arena.write(&df).is_ok() {
                    total_writes_clone.fetch_add(1, Ordering::Relaxed);
                }

                thread::sleep(Duration::from_millis(10));
            }

            Ok(())
        });

        handles.push(handle);
    }

    // Start readers
    for r in 0..num_readers {
        let total_reads_clone = Arc::clone(&total_reads);

        let handle = thread::spawn(move || -> Result<()> {
            thread::sleep(Duration::from_millis(100)); // Let writers start

            for w in 0..num_writers {
                let writer_name = format!("{}_{}", shared_name, w);
                let arena = SharedDataFrame::new(&writer_name, 0, 0)?;

                if arena.attach_reader().is_ok() {
                    for _m in 0..messages_per_writer {
                        if arena.read(Duration::from_secs(1)).is_ok() {
                            total_reads_clone.fetch_add(1, Ordering::Relaxed);
                        } else {
                            break; // Timeout or error
                        }
                    }
                }
            }

            Ok(())
        });

        handles.push(handle);
    }

    // Wait for all threads
    for handle in handles {
        if let Err(e) = handle.join() {
            eprintln!("Thread panicked: {:?}", e);
        }
    }

    let total_duration = start_time.elapsed();

    let writes_count = total_writes.load(Ordering::Relaxed);
    let reads_count = total_reads.load(Ordering::Relaxed);

    println!("Concurrent benchmark results:");
    println!("  Writers: {}", num_writers);
    println!("  Readers: {}", num_readers);
    println!("  Total writes: {}", writes_count);
    println!("  Total reads: {}", reads_count);
    println!("  Duration: {:?}", total_duration);
    println!(
        "  Write rate: {:.2} writes/sec",
        writes_count as f64 / total_duration.as_secs_f64()
    );
    println!(
        "  Read rate: {:.2} reads/sec",
        reads_count as f64 / total_duration.as_secs_f64()
    );

    Ok(())
}

fn main() -> Result<()> {
    println!("QADataSwap Rust Performance Tests");
    println!("==================================");

    benchmark_throughput()?;
    benchmark_latency()?;
    benchmark_concurrent()?;

    println!("\nAll performance tests completed!");
    Ok(())
}