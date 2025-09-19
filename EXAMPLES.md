# QADataSwap 使用示例集合

## 基础示例

### 1. 简单数据传输

**写入进程 (Python):**
```python
import polars as pl
import sys
sys.path.append('src/python')
import qadataswap

# 创建测试数据
df = pl.DataFrame({
    'timestamp': [1640995200, 1640995201, 1640995202],
    'symbol': ['AAPL', 'MSFT', 'GOOGL'],
    'price': [150.0, 280.0, 2800.0],
    'volume': [1000, 2000, 500]
})

# 写入共享内存
writer = qadataswap.create_writer("basic_example", 3)
writer.write_arrow(df.to_arrow())
print("数据已写入共享内存")
```

**读取进程 (Python):**
```python
import polars as pl
import sys
sys.path.append('src/python')
import qadataswap

# 读取共享内存
reader = qadataswap.create_reader("basic_example")
arrow_table = reader.read_arrow(5000)  # 5秒超时

if arrow_table:
    df = pl.from_arrow(arrow_table)
    print("读取到的数据:")
    print(df)
else:
    print("读取超时")
```

### 2. 跨语言数据传输

**Python 写入 → Rust 读取:**

```python
# python_writer.py
import polars as pl
import sys
sys.path.append('src/python')
import qadataswap

df = pl.DataFrame({
    'id': list(range(1000)),
    'value': [i * 1.5 for i in range(1000)],
    'category': [f'type_{i % 5}' for i in range(1000)]
})

writer = qadataswap.create_writer("py_to_rust", 5)
writer.write_arrow(df.to_arrow())
print(f"Python写入了 {len(df)} 行数据")
```

```rust
// rust_reader.rs
use qadataswap::{create_reader, QADataSwapError};
use polars::prelude::*;

fn main() -> Result<(), QADataSwapError> {
    let reader = create_reader("py_to_rust")?;

    match reader.read_arrow(10000)? {  // 10秒超时
        Some(batch) => {
            println!("Rust读取到 {} 行数据", batch.num_rows());
            // 转换为Polars DataFrame
            let df = LazyFrame::scan_arrow(batch)?.collect()?;
            println!("{}", df.head(Some(5)));
        },
        None => println!("读取超时"),
    }

    Ok(())
}
```

## 实时数据流示例

### 3. 实时股票数据流

**数据生产者 (模拟实时数据):**
```python
import polars as pl
import time
import random
import sys
sys.path.append('src/python')
import qadataswap

def generate_market_data():
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']
    current_time = int(time.time())

    return pl.DataFrame({
        'timestamp': [current_time] * len(symbols),
        'symbol': symbols,
        'price': [100 + random.uniform(-5, 5) for _ in symbols],
        'volume': [random.randint(1000, 10000) for _ in symbols],
        'bid': [100 + random.uniform(-5, 5) for _ in symbols],
        'ask': [100 + random.uniform(-5, 5) for _ in symbols]
    })

# 启动数据流
writer = qadataswap.create_writer("market_stream", 10)

print("开始实时数据流...")
try:
    for i in range(100):  # 发送100批数据
        df = generate_market_data()
        writer.write_arrow(df.to_arrow())
        print(f"发送第 {i+1} 批数据，{len(df)} 行")
        time.sleep(1)  # 每秒发送一次
except KeyboardInterrupt:
    print("数据流已停止")
```

**数据消费者 (实时处理):**
```python
import polars as pl
import time
import sys
sys.path.append('src/python')
import qadataswap

reader = qadataswap.create_reader("market_stream")
processed_count = 0

print("开始接收实时数据...")
try:
    while True:
        arrow_table = reader.read_arrow(2000)  # 2秒超时

        if arrow_table:
            df = pl.from_arrow(arrow_table)
            processed_count += len(df)

            # 简单的数据处理示例
            avg_price = df['price'].mean()
            total_volume = df['volume'].sum()

            print(f"处理了 {len(df)} 行数据 | 平均价格: {avg_price:.2f} | 总成交量: {total_volume}")
            print(f"累计处理: {processed_count} 行")
        else:
            print("等待新数据...")

        time.sleep(0.1)  # 短暂休息

except KeyboardInterrupt:
    print(f"处理完成，总计: {processed_count} 行")
```

## 高性能批处理示例

### 4. 大数据量传输

```python
import polars as pl
import time
import sys
sys.path.append('src/python')
import qadataswap

def create_large_dataset(rows=1000000):
    """创建大型数据集"""
    return pl.DataFrame({
        'id': list(range(rows)),
        'timestamp': [1640995200 + i for i in range(rows)],
        'price': [100.0 + (i % 1000) * 0.01 for i in range(rows)],
        'volume': [1000 + (i % 10000) for i in range(rows)],
        'category': [f'cat_{i % 100}' for i in range(rows)]
    })

# 大数据写入测试
print("创建100万行测试数据...")
start_time = time.time()
large_df = create_large_dataset(1000000)
create_time = time.time() - start_time
print(f"数据创建耗时: {create_time:.2f} 秒")

# 写入性能测试
writer = qadataswap.create_writer("big_data", 20)
start_time = time.time()
writer.write_arrow(large_df.to_arrow())
write_time = time.time() - start_time

print(f"数据写入耗时: {write_time:.2f} 秒")
print(f"写入速度: {len(large_df) / write_time:.0f} 行/秒")

# 读取性能测试
reader = qadataswap.create_reader("big_data")
start_time = time.time()
result = reader.read_arrow(30000)  # 30秒超时
read_time = time.time() - start_time

if result:
    result_df = pl.from_arrow(result)
    print(f"数据读取耗时: {read_time:.2f} 秒")
    print(f"读取速度: {len(result_df) / read_time:.0f} 行/秒")
    print(f"数据完整性: {len(result_df) == len(large_df)}")
else:
    print("读取失败或超时")
```

## 错误处理和重连示例

### 5. 健壮的数据处理

```python
import polars as pl
import time
import sys
sys.path.append('src/python')
import qadataswap

class RobustDataProcessor:
    def __init__(self, name, max_retries=3):
        self.name = name
        self.max_retries = max_retries
        self.reader = None
        self.connect()

    def connect(self):
        """连接到共享内存"""
        for attempt in range(self.max_retries):
            try:
                self.reader = qadataswap.create_reader(self.name)
                print(f"成功连接到 {self.name}")
                return True
            except Exception as e:
                print(f"连接失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                time.sleep(1)
        return False

    def process_data(self, timeout_ms=5000):
        """处理数据，包含错误重试"""
        retry_count = 0

        while retry_count < self.max_retries:
            try:
                arrow_table = self.reader.read_arrow(timeout_ms)

                if arrow_table:
                    df = pl.from_arrow(arrow_table)
                    self.handle_data(df)
                    return True
                else:
                    print("读取超时，等待新数据...")
                    return False

            except RuntimeError as e:
                retry_count += 1
                print(f"读取错误 (尝试 {retry_count}/{self.max_retries}): {e}")

                if retry_count < self.max_retries:
                    print("尝试重新连接...")
                    if not self.connect():
                        break
                else:
                    print("达到最大重试次数，放弃处理")
                    return False

        return False

    def handle_data(self, df):
        """实际数据处理逻辑"""
        print(f"处理数据: {df.shape[0]} 行 × {df.shape[1]} 列")

        # 数据验证
        if df.is_empty():
            print("警告: 接收到空数据")
            return

        # 简单统计
        numeric_cols = df.select(pl.col(pl.Float64, pl.Int64)).columns
        if numeric_cols:
            stats = df.select([pl.col(col).mean().alias(f"{col}_avg") for col in numeric_cols])
            print(f"数据统计: {stats}")

# 使用示例
if __name__ == "__main__":
    processor = RobustDataProcessor("robust_test")

    # 持续处理数据
    processed = 0
    while processed < 10:  # 处理10批数据后退出
        if processor.process_data():
            processed += 1
            print(f"已处理 {processed} 批数据")
        time.sleep(1)

    print("数据处理完成")
```

## 运行示例

1. **基础示例**:
   ```bash
   # 终端1: 运行写入器
   python3 examples/python/basic_writer.py

   # 终端2: 运行读取器
   python3 examples/python/basic_reader.py
   ```

2. **跨语言示例**:
   ```bash
   # 终端1: Python写入
   python3 python_writer.py

   # 终端2: Rust读取
   cd examples/rust
   cargo run --bin rust_reader py_to_rust
   ```

3. **性能测试**:
   ```bash
   # 运行完整性能基准
   python3 tests/performance/benchmark_all.py
   ```

记住在运行示例前确保已完成构建：
```bash
./scripts/build_all.sh
```