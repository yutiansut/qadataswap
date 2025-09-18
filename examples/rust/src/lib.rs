// Simplified mock implementation for examples
use polars::prelude::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTimeError};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum QADataSwapError {
    #[error("Polars error: {0}")]
    Polars(#[from] PolarsError),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("System time error: {0}")]
    SystemTime(#[from] SystemTimeError),
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

// Mock shared storage using static HashMap
lazy_static::lazy_static! {
    static ref SHARED_STORAGE: Arc<Mutex<HashMap<String, Vec<Vec<u8>>>>> =
        Arc::new(Mutex::new(HashMap::new()));
}

/// High-level interface for Polars DataFrames
pub struct SharedDataFrame {
    config: SharedMemoryConfig,
    is_writer: bool,
}

impl SharedDataFrame {
    pub fn create_writer(config: SharedMemoryConfig) -> Result<Self> {
        // Initialize storage for this name
        let mut storage = SHARED_STORAGE.lock().unwrap();
        storage.insert(config.name.clone(), Vec::new());

        Ok(Self {
            config,
            is_writer: true,
        })
    }

    pub fn create_reader(config: SharedMemoryConfig) -> Result<Self> {
        Ok(Self {
            config,
            is_writer: false,
        })
    }

    /// Write a Polars DataFrame using IPC format
    pub fn write(&self, df: &DataFrame) -> Result<()> {
        if !self.is_writer {
            return Err(QADataSwapError::SharedMemory("Not a writer".to_string()));
        }

        // Use Polars IPC serialization
        let mut buffer = Vec::new();
        let mut cursor = std::io::Cursor::new(&mut buffer);
        let mut df_clone = df.clone();

        IpcWriter::new(&mut cursor)
            .finish(&mut df_clone)
            .map_err(QADataSwapError::Polars)?;

        // Store in mock shared storage
        let mut storage = SHARED_STORAGE.lock().unwrap();
        if let Some(data_vec) = storage.get_mut(&self.config.name) {
            data_vec.push(buffer);
        }

        Ok(())
    }

    /// Read as Polars DataFrame using IPC format
    pub fn read(&self, timeout_ms: Option<i32>) -> Result<Option<DataFrame>> {
        if self.is_writer {
            return Err(QADataSwapError::SharedMemory("Writer cannot read".to_string()));
        }

        let start = Instant::now();
        let timeout_duration = timeout_ms.map(|ms| Duration::from_millis(ms as u64));

        loop {
            {
                let mut storage = SHARED_STORAGE.lock().unwrap();
                if let Some(data_vec) = storage.get_mut(&self.config.name) {
                    if let Some(bytes) = data_vec.pop() {
                        let cursor = std::io::Cursor::new(bytes);
                        let df = IpcReader::new(cursor)
                            .finish()
                            .map_err(QADataSwapError::Polars)?;
                        return Ok(Some(df));
                    }
                }
            }

            // Check timeout
            if let Some(timeout) = timeout_duration {
                if start.elapsed() > timeout {
                    return Err(QADataSwapError::Timeout);
                }
            }

            // Small sleep to avoid busy waiting
            std::thread::sleep(Duration::from_millis(10));
        }
    }

    pub fn close(&self) {
        // Cleanup mock storage
        let mut storage = SHARED_STORAGE.lock().unwrap();
        storage.remove(&self.config.name);
    }
}