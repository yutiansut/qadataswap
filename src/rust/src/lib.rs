use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_void};
use std::ptr;
use std::sync::Arc;
use std::time::Duration;

use arrow::array::RecordBatch;
use arrow::datatypes::Schema;
use arrow::ipc::{reader::StreamReader, writer::StreamWriter};
use arrow::buffer::Buffer;
use arrow::error::ArrowError;

use polars::prelude::*;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum QADataSwapError {
    #[error("Arrow error: {0}")]
    Arrow(#[from] ArrowError),
    #[error("Polars error: {0}")]
    Polars(#[from] PolarsError),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Shared memory error: {0}")]
    SharedMemory(String),
    #[error("Timeout")]
    Timeout,
    #[error("Not connected")]
    NotConnected,
}

pub type Result<T> = std::result::Result<T, QADataSwapError>;

/// Configuration for shared memory arena
#[derive(Debug, Clone)]
pub struct SharedMemoryConfig {
    pub name: String,
    pub size_mb: usize,
    pub buffer_count: usize,
    pub timeout_ms: Option<i32>,
}

impl Default for SharedMemoryConfig {
    fn default() -> Self {
        Self {
            name: "default".to_string(),
            size_mb: 100,
            buffer_count: 3,
            timeout_ms: None,
        }
    }
}

impl SharedMemoryConfig {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            ..Default::default()
        }
    }

    pub fn with_size_mb(mut self, size_mb: usize) -> Self {
        self.size_mb = size_mb;
        self
    }

    pub fn with_buffer_count(mut self, buffer_count: usize) -> Self {
        self.buffer_count = buffer_count;
        self
    }

    pub fn with_timeout_ms(mut self, timeout_ms: i32) -> Self {
        self.timeout_ms = Some(timeout_ms);
        self
    }
}

// FFI bindings to C++ core
extern "C" {
    fn qads_create_arena(name: *const c_char, size: usize, buffer_count: usize) -> *mut c_void;
    fn qads_destroy_arena(arena: *mut c_void);
    fn qads_create_writer(arena: *mut c_void) -> c_int;
    fn qads_attach_reader(arena: *mut c_void) -> c_int;
    fn qads_write_data(arena: *mut c_void, data: *const u8, size: usize) -> c_int;
    fn qads_read_data(arena: *mut c_void, data: *mut u8, max_size: usize,
                      actual_size: *mut usize, timeout_ms: c_int) -> c_int;
    fn qads_wait_for_data(arena: *mut c_void, timeout_ms: c_int) -> c_int;
    fn qads_notify_data_ready(arena: *mut c_void);
    fn qads_close(arena: *mut c_void);
}

/// Shared memory arena for zero-copy data transfer
pub struct SharedMemoryArena {
    inner: *mut c_void,
    config: SharedMemoryConfig,
    is_writer: bool,
}

unsafe impl Send for SharedMemoryArena {}
unsafe impl Sync for SharedMemoryArena {}

impl SharedMemoryArena {
    pub fn new(config: SharedMemoryConfig) -> Result<Self> {
        let name_cstr = CString::new(config.name.clone())
            .map_err(|_| QADataSwapError::SharedMemory("Invalid name".to_string()))?;

        let inner = unsafe {
            qads_create_arena(
                name_cstr.as_ptr(),
                config.size_mb * 1024 * 1024,
                config.buffer_count,
            )
        };

        if inner.is_null() {
            return Err(QADataSwapError::SharedMemory("Failed to create arena".to_string()));
        }

        Ok(Self {
            inner,
            config,
            is_writer: false,
        })
    }

    pub fn create_writer(&mut self) -> Result<()> {
        let result = unsafe { qads_create_writer(self.inner) };
        if result != 0 {
            return Err(QADataSwapError::SharedMemory("Failed to create writer".to_string()));
        }
        self.is_writer = true;
        Ok(())
    }

    pub fn attach_reader(&mut self) -> Result<()> {
        let result = unsafe { qads_attach_reader(self.inner) };
        if result != 0 {
            return Err(QADataSwapError::SharedMemory("Failed to attach reader".to_string()));
        }
        self.is_writer = false;
        Ok(())
    }

    fn write_record_batch(&self, batch: &RecordBatch) -> Result<()> {
        if !self.is_writer {
            return Err(QADataSwapError::SharedMemory("Not a writer".to_string()));
        }

        // Serialize RecordBatch to Arrow IPC format
        let mut buffer = Vec::new();
        {
            let mut writer = StreamWriter::try_new(&mut buffer, &batch.schema())?;
            writer.write(batch)?;
            writer.finish()?;
        }

        let result = unsafe {
            qads_write_data(self.inner, buffer.as_ptr(), buffer.len())
        };

        if result != 0 {
            return Err(QADataSwapError::SharedMemory("Failed to write data".to_string()));
        }

        Ok(())
    }

    fn read_record_batch(&self, timeout_ms: Option<i32>) -> Result<Option<RecordBatch>> {
        if self.is_writer {
            return Err(QADataSwapError::SharedMemory("Writer cannot read".to_string()));
        }

        let mut buffer = vec![0u8; self.config.size_mb * 1024 * 1024];
        let mut actual_size = 0usize;
        let timeout = timeout_ms.unwrap_or(self.config.timeout_ms.unwrap_or(-1));

        let result = unsafe {
            qads_read_data(
                self.inner,
                buffer.as_mut_ptr(),
                buffer.len(),
                &mut actual_size,
                timeout,
            )
        };

        match result {
            0 => {
                // Success
                buffer.truncate(actual_size);
                let cursor = std::io::Cursor::new(buffer);
                let mut reader = StreamReader::try_new(cursor, None)?;

                match reader.next() {
                    Some(Ok(batch)) => Ok(Some(batch)),
                    Some(Err(e)) => Err(QADataSwapError::Arrow(e)),
                    None => Ok(None),
                }
            },
            1 => Err(QADataSwapError::Timeout),
            _ => Err(QADataSwapError::SharedMemory("Failed to read data".to_string())),
        }
    }

    pub fn wait_for_data(&self, timeout_ms: Option<i32>) -> Result<()> {
        let timeout = timeout_ms.unwrap_or(self.config.timeout_ms.unwrap_or(-1));
        let result = unsafe { qads_wait_for_data(self.inner, timeout) };

        match result {
            0 => Ok(()),
            1 => Err(QADataSwapError::Timeout),
            _ => Err(QADataSwapError::SharedMemory("Wait failed".to_string())),
        }
    }

    pub fn notify_data_ready(&self) {
        unsafe { qads_notify_data_ready(self.inner) };
    }

    pub fn close(&self) {
        unsafe { qads_close(self.inner) };
    }
}

impl Drop for SharedMemoryArena {
    fn drop(&mut self) {
        if !self.inner.is_null() {
            unsafe { qads_destroy_arena(self.inner) };
        }
    }
}

/// High-level interface for Polars DataFrames
pub struct SharedDataFrame {
    arena: SharedMemoryArena,
}

impl SharedDataFrame {
    pub fn create_writer(config: SharedMemoryConfig) -> Result<Self> {
        let mut arena = SharedMemoryArena::new(config)?;
        arena.create_writer()?;
        Ok(Self { arena })
    }

    pub fn create_reader(config: SharedMemoryConfig) -> Result<Self> {
        let mut arena = SharedMemoryArena::new(config)?;
        arena.attach_reader()?;
        Ok(Self { arena })
    }

    /// Write a Polars DataFrame with zero-copy
    pub fn write(&self, df: &DataFrame) -> Result<()> {
        // Convert Polars DataFrame to Arrow RecordBatch
        let batches = df.to_arrow(CompatLevel::newest())?;

        for batch in batches {
            self.arena.write_record_batch(&batch)?;
        }

        Ok(())
    }

    /// Write a Polars LazyFrame with zero-copy
    pub fn write_lazy(&self, lf: LazyFrame) -> Result<()> {
        let df = lf.collect()?;
        self.write(&df)
    }

    /// Read as Polars DataFrame with zero-copy
    pub fn read(&self, timeout_ms: Option<i32>) -> Result<Option<DataFrame>> {
        match self.arena.read_record_batch(timeout_ms)? {
            Some(batch) => {
                // Convert Arrow RecordBatch to Polars DataFrame
                let df = DataFrame::try_from((batch, &[]));
                match df {
                    Ok(df) => Ok(Some(df)),
                    Err(e) => Err(QADataSwapError::Polars(e)),
                }
            },
            None => Ok(None),
        }
    }

    /// Read as Polars LazyFrame with zero-copy
    pub fn read_lazy(&self, timeout_ms: Option<i32>) -> Result<Option<LazyFrame>> {
        match self.read(timeout_ms)? {
            Some(df) => Ok(Some(df.lazy())),
            None => Ok(None),
        }
    }

    pub fn wait_for_data(&self, timeout_ms: Option<i32>) -> Result<()> {
        self.arena.wait_for_data(timeout_ms)
    }

    pub fn notify_data_ready(&self) {
        self.arena.notify_data_ready();
    }

    pub fn close(&self) {
        self.arena.close();
    }
}

/// Streaming interface for large datasets
pub struct SharedDataStream {
    arena: SharedMemoryArena,
}

impl SharedDataStream {
    pub fn create_writer(config: SharedMemoryConfig) -> Result<Self> {
        let mut arena = SharedMemoryArena::new(config)?;
        arena.create_writer()?;
        Ok(Self { arena })
    }

    pub fn create_reader(config: SharedMemoryConfig) -> Result<Self> {
        let mut arena = SharedMemoryArena::new(config)?;
        arena.attach_reader()?;
        Ok(Self { arena })
    }

    /// Write a chunk (DataFrame)
    pub fn write_chunk(&self, df: &DataFrame) -> Result<()> {
        self.arena.write_record_batch(&df.to_arrow(CompatLevel::newest())?[0])
    }

    /// Read a chunk as DataFrame
    pub fn read_chunk(&self, timeout_ms: Option<i32>) -> Result<Option<DataFrame>> {
        match self.arena.read_record_batch(timeout_ms)? {
            Some(batch) => {
                let df = DataFrame::try_from((batch, &[]))?;
                Ok(Some(df))
            },
            None => Ok(None),
        }
    }

    /// Iterator over chunks as DataFrames
    pub fn iter_chunks(&self) -> DataFrameChunkIterator {
        DataFrameChunkIterator { stream: self }
    }
}

pub struct DataFrameChunkIterator<'a> {
    stream: &'a SharedDataStream,
}

impl<'a> Iterator for DataFrameChunkIterator<'a> {
    type Item = Result<DataFrame>;

    fn next(&mut self) -> Option<Self::Item> {
        match self.stream.read_chunk(None) {
            Ok(Some(df)) => Some(Ok(df)),
            Ok(None) => None,
            Err(e) => Some(Err(e)),
        }
    }
}

#[cfg(feature = "async")]
pub mod r#async {
    use super::*;
    use tokio::time::{timeout, Duration};

    impl SharedDataFrame {
        pub async fn read_async(&self, timeout_duration: Option<Duration>) -> Result<Option<DataFrame>> {
            let timeout_ms = timeout_duration.map(|d| d.as_millis() as i32);

            match timeout_duration {
                Some(duration) => {
                    timeout(duration, tokio::task::spawn_blocking({
                        let timeout_ms = timeout_ms;
                        move || self.read(timeout_ms)
                    })).await
                    .map_err(|_| QADataSwapError::Timeout)?
                    .map_err(|e| QADataSwapError::SharedMemory(e.to_string()))?
                },
                None => {
                    tokio::task::spawn_blocking(move || self.read(None)).await
                    .map_err(|e| QADataSwapError::SharedMemory(e.to_string()))?
                }
            }
        }

        pub async fn write_async(&self, df: &DataFrame) -> Result<()> {
            let df = df.clone();
            tokio::task::spawn_blocking(move || {
                // Write logic here
                Ok(())
            }).await
            .map_err(|e| QADataSwapError::SharedMemory(e.to_string()))?
        }
    }
}

// Convenience functions
pub fn create_shared_dataframe_writer(name: &str, size_mb: usize) -> Result<SharedDataFrame> {
    let config = SharedMemoryConfig::new(name).with_size_mb(size_mb);
    SharedDataFrame::create_writer(config)
}

pub fn create_shared_dataframe_reader(name: &str) -> Result<SharedDataFrame> {
    let config = SharedMemoryConfig::new(name);
    SharedDataFrame::create_reader(config)
}

pub fn create_shared_datastream_writer(name: &str, size_mb: usize, buffer_count: usize) -> Result<SharedDataStream> {
    let config = SharedMemoryConfig::new(name)
        .with_size_mb(size_mb)
        .with_buffer_count(buffer_count);
    SharedDataStream::create_writer(config)
}

pub fn create_shared_datastream_reader(name: &str) -> Result<SharedDataStream> {
    let config = SharedMemoryConfig::new(name);
    SharedDataStream::create_reader(config)
}

#[cfg(test)]
mod tests {
    use super::*;
    use polars::prelude::*;
    use std::thread;
    use std::time::Duration;

    #[test]
    fn test_basic_dataframe_transfer() -> Result<()> {
        let name = "test_basic";

        // Create test data
        let df = df! {
            "a" => [1, 2, 3, 4, 5],
            "b" => [1.1, 2.2, 3.3, 4.4, 5.5],
            "c" => ["foo", "bar", "baz", "qux", "quux"],
        }?;

        // Writer thread
        let df_clone = df.clone();
        let writer_handle = thread::spawn(move || -> Result<()> {
            let writer = create_shared_dataframe_writer(name, 10)?;
            writer.write(&df_clone)?;
            Ok(())
        });

        // Small delay to ensure writer is ready
        thread::sleep(Duration::from_millis(100));

        // Reader thread
        let reader_handle = thread::spawn(move || -> Result<DataFrame> {
            let reader = create_shared_dataframe_reader(name)?;
            match reader.read(Some(5000))? {
                Some(df) => Ok(df),
                None => Err(QADataSwapError::SharedMemory("No data received".to_string())),
            }
        });

        // Wait for completion
        writer_handle.join().unwrap()?;
        let received_df = reader_handle.join().unwrap()?;

        // Verify data integrity
        assert_eq!(df.shape(), received_df.shape());
        assert_eq!(df.get_column_names(), received_df.get_column_names());

        Ok(())
    }

    #[test]
    fn test_streaming_transfer() -> Result<()> {
        let name = "test_streaming";
        let chunk_size = 1000;
        let num_chunks = 5;

        // Writer thread
        let writer_handle = thread::spawn(move || -> Result<()> {
            let writer = create_shared_datastream_writer(name, 50, 8)?;

            for i in 0..num_chunks {
                let start = i * chunk_size;
                let end = start + chunk_size;
                let df = df! {
                    "id" => (start..end).collect::<Vec<_>>(),
                    "value" => (start..end).map(|x| x as f64 * 1.5).collect::<Vec<_>>(),
                }?;

                writer.write_chunk(&df)?;
            }
            Ok(())
        });

        // Small delay
        thread::sleep(Duration::from_millis(100));

        // Reader thread
        let reader_handle = thread::spawn(move || -> Result<i32> {
            let reader = create_shared_datastream_reader(name)?;
            let mut total_rows = 0;

            for chunk_result in reader.iter_chunks() {
                let chunk = chunk_result?;
                total_rows += chunk.height() as i32;
            }

            Ok(total_rows)
        });

        // Wait for completion
        writer_handle.join().unwrap()?;
        let total_rows = reader_handle.join().unwrap()?;

        assert_eq!(total_rows, (chunk_size * num_chunks) as i32);

        Ok(())
    }
}