# QADataSwap API 参考文档

## Python API

### 创建写入器 (Writer)

```python
import qadataswap

writer = qadataswap.create_writer(name: str, buffer_count: int) -> Writer
```

**参数:**
- `name`: 共享内存区域名称
- `buffer_count`: 环形缓冲区数量

**返回:** Writer 对象

### 创建读取器 (Reader)

```python
reader = qadataswap.create_reader(name: str) -> Reader
```

**参数:**
- `name`: 共享内存区域名称

**返回:** Reader 对象

### Writer 方法

```python
writer.write_arrow(table: pyarrow.Table) -> None
```

写入 Arrow 表到共享内存。

**参数:**
- `table`: PyArrow 表对象

### Reader 方法

```python
table = reader.read_arrow(timeout_ms: int) -> pyarrow.Table | None
```

从共享内存读取 Arrow 表。

**参数:**
- `timeout_ms`: 超时时间（毫秒）

**返回:** PyArrow 表对象，如果超时返回 None

## Rust API

### 创建写入器

```rust
use qadataswap::{create_writer, Writer};

let writer = create_writer(name: &str, buffer_count: usize) -> Result<Writer, QADataSwapError>
```

### 创建读取器

```rust
use qadataswap::{create_reader, Reader};

let reader = create_reader(name: &str) -> Result<Reader, QADataSwapError>
```

### Writer 方法

```rust
writer.write_arrow(table: &RecordBatch) -> Result<(), QADataSwapError>
```

### Reader 方法

```rust
let table = reader.read_arrow(timeout_ms: u64) -> Result<Option<RecordBatch>, QADataSwapError>
```

## C++ FFI API

### 创建共享内存区域

```cpp
void* qads_create_arena(const char* name, size_t size, size_t buffer_count);
```

### 销毁共享内存区域

```cpp
void qads_destroy_arena(void* arena);
```

### 创建写入器

```cpp
int qads_create_writer(void* arena);
```

### 连接读取器

```cpp
int qads_attach_reader(void* arena);
```

### 写入数据

```cpp
int qads_write_data(void* arena, const void* data, size_t size);
```

### 读取数据

```cpp
int qads_read_data(void* arena, void* buffer, size_t buffer_size, size_t* read_size, uint64_t timeout_ms);
```

## 错误处理

### Python

Python 绑定会抛出 `RuntimeError` 异常，包含详细错误信息。

### Rust

使用 `QADataSwapError` 枚举：

```rust
pub enum QADataSwapError {
    InvalidName,
    MemoryMapFailed,
    WriteError,
    ReadTimeout,
    ArrowError(arrow::error::ArrowError),
}
```

### C++

FFI 函数返回整数状态码：
- `0`: 成功
- `-1`: 一般错误
- `-2`: 超时
- `-3`: 内存错误

## 使用模式

### 生产者-消费者

```python
# 生产者进程
writer = qadataswap.create_writer("market_data", 10)
for data_batch in data_stream:
    arrow_table = polars_df.to_arrow()
    writer.write_arrow(arrow_table)

# 消费者进程
reader = qadataswap.create_reader("market_data")
while True:
    table = reader.read_arrow(5000)  # 5秒超时
    if table:
        df = pl.from_arrow(table)
        process_data(df)
```

### 多语言通信

```python
# Python 写入
writer = qadataswap.create_writer("cross_lang", 5)
df = pl.DataFrame({"price": [1.0, 2.0], "volume": [100, 200]})
writer.write_arrow(df.to_arrow())
```

```rust
// Rust 读取
let reader = create_reader("cross_lang")?;
if let Some(batch) = reader.read_arrow(3000)? {
    let df = LazyFrame::scan_arrow(batch)?.collect()?;
    println!("{}", df);
}
```

## 性能优化建议

1. **缓冲区数量**: 根据读写频率调整，通常 3-10 个
2. **超时设置**: 根据数据生产频率设置合理超时
3. **批处理**: 尽量批量写入而非逐行写入
4. **内存预分配**: 使用足够大的共享内存区域避免重新分配