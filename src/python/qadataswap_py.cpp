#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <pybind11/chrono.h>

#include "qadataswap_core.h"

#include <arrow/python/pyarrow.h>
#include <arrow/api.h>

namespace py = pybind11;

namespace qadataswap {

class SharedDataFrame {
public:
    SharedDataFrame(const std::string& name, size_t size_mb = 100, size_t buffer_count = 3)
        : arena_(std::make_unique<SharedMemoryArena>(name, size_mb * 1024 * 1024, buffer_count)) {}

    bool create_writer() {
        return arena_->CreateWriter();
    }

    bool attach_reader() {
        return arena_->AttachReader();
    }

    py::object write_polars_dataframe(py::object polars_df) {
        // Convert Polars DataFrame to Arrow Table
        py::object arrow_table = polars_df.attr("to_arrow")();

        // Get the underlying Arrow Table
        auto cpp_table = unwrap_table(arrow_table.ptr());
        if (!cpp_table.ok()) {
            throw std::runtime_error("Failed to unwrap Arrow table");
        }

        // Convert to RecordBatch
        auto batches = cpp_table.ValueOrDie()->CombineChunksToBatch();
        if (!batches.ok()) {
            throw std::runtime_error("Failed to combine chunks to batch");
        }

        auto status = arena_->WriteRecordBatch(batches.ValueOrDie());
        if (!status.ok()) {
            throw std::runtime_error("Failed to write: " + status.ToString());
        }

        return py::none();
    }

    py::object write_pyarrow_table(py::object pyarrow_table) {
        auto cpp_table = unwrap_table(pyarrow_table.ptr());
        if (!cpp_table.ok()) {
            throw std::runtime_error("Failed to unwrap Arrow table");
        }

        auto status = arena_->WriteTable(cpp_table.ValueOrDie());
        if (!status.ok()) {
            throw std::runtime_error("Failed to write: " + status.ToString());
        }

        return py::none();
    }

    py::object read_as_polars_dataframe(int timeout_ms = -1) {
        auto result = arena_->ReadRecordBatch(timeout_ms);
        if (!result.ok()) {
            if (result.status().IsIOError() && result.status().message().find("Timeout") != std::string::npos) {
                return py::none(); // Return None for timeout
            }
            throw std::runtime_error("Failed to read: " + result.status().ToString());
        }

        auto batch = result.ValueOrDie();
        auto table = arrow::Table::FromRecordBatches({batch});
        if (!table.ok()) {
            throw std::runtime_error("Failed to create table from batch");
        }

        // Convert to PyArrow Table
        auto py_table = wrap_table(table.ValueOrDie());
        if (!py_table) {
            throw std::runtime_error("Failed to wrap table");
        }

        // Convert PyArrow Table to Polars DataFrame
        py::module polars = py::module::import("polars");
        py::object polars_df = polars.attr("from_arrow")(py::reinterpret_steal<py::object>(py_table));

        return polars_df;
    }

    py::object read_as_pyarrow_table(int timeout_ms = -1) {
        auto result = arena_->ReadTable(timeout_ms);
        if (!result.ok()) {
            if (result.status().IsIOError() && result.status().message().find("Timeout") != std::string::npos) {
                return py::none();
            }
            throw std::runtime_error("Failed to read: " + result.status().ToString());
        }

        auto py_table = wrap_table(result.ValueOrDie());
        if (!py_table) {
            throw std::runtime_error("Failed to wrap table");
        }

        return py::reinterpret_steal<py::object>(py_table);
    }

    bool wait_for_data(int timeout_ms = -1) {
        auto status = arena_->WaitForData(timeout_ms);
        return status.ok();
    }

    void notify_data_ready() {
        arena_->NotifyDataReady();
    }

    py::dict get_stats() {
        auto stats = arena_->GetStats();
        py::dict result;
        result["bytes_written"] = stats.bytes_written;
        result["bytes_read"] = stats.bytes_read;
        result["writes_count"] = stats.writes_count;
        result["reads_count"] = stats.reads_count;
        result["wait_timeouts"] = stats.wait_timeouts;
        return result;
    }

    void close() {
        arena_->Close();
    }

    static std::shared_ptr<SharedDataFrame> create_writer(const std::string& name,
                                                         size_t size_mb = 100,
                                                         size_t buffer_count = 3) {
        auto sdf = std::make_shared<SharedDataFrame>(name, size_mb, buffer_count);
        if (!sdf->create_writer()) {
            throw std::runtime_error("Failed to create writer");
        }
        return sdf;
    }

    static std::shared_ptr<SharedDataFrame> create_reader(const std::string& name) {
        auto sdf = std::make_shared<SharedDataFrame>(name);
        if (!sdf->attach_reader()) {
            throw std::runtime_error("Failed to attach reader");
        }
        return sdf;
    }

private:
    std::unique_ptr<SharedMemoryArena> arena_;

    arrow::Result<std::shared_ptr<arrow::Table>> unwrap_table(PyObject* obj) {
        if (!arrow::py::is_table(obj)) {
            return arrow::Status::TypeError("Object is not an Arrow Table");
        }
        return arrow::py::unwrap_table(obj);
    }

    PyObject* wrap_table(const std::shared_ptr<arrow::Table>& table) {
        return arrow::py::wrap_table(table);
    }
};

// Note: SharedDataStream removed for simplification - use SharedDataFrame for now

} // namespace qadataswap

PYBIND11_MODULE(qadataswap, m) {
    arrow::py::import_pyarrow();

    m.doc() = "QADataSwap: High-performance cross-language zero-copy data transfer with Polars support";

    py::class_<qadataswap::SharedDataFrame, std::shared_ptr<qadataswap::SharedDataFrame>>(m, "SharedDataFrame")
        .def(py::init<const std::string&, size_t, size_t>(),
             py::arg("name"), py::arg("size_mb") = 100, py::arg("buffer_count") = 3)
        .def_static("create_writer",
                   static_cast<std::shared_ptr<qadataswap::SharedDataFrame>(*)(const std::string&, size_t, size_t)>(&qadataswap::SharedDataFrame::create_writer),
                   py::arg("name"), py::arg("size_mb") = 100, py::arg("buffer_count") = 3)
        .def_static("create_reader",
                   static_cast<std::shared_ptr<qadataswap::SharedDataFrame>(*)(const std::string&)>(&qadataswap::SharedDataFrame::create_reader),
                   py::arg("name"))
        .def("write", &qadataswap::SharedDataFrame::write_polars_dataframe,
             "Write a Polars DataFrame with zero-copy")
        .def("write_arrow", &qadataswap::SharedDataFrame::write_pyarrow_table,
             "Write a PyArrow Table with zero-copy")
        .def("read", &qadataswap::SharedDataFrame::read_as_polars_dataframe,
             py::arg("timeout_ms") = -1, "Read as Polars DataFrame with zero-copy")
        .def("read_arrow", &qadataswap::SharedDataFrame::read_as_pyarrow_table,
             py::arg("timeout_ms") = -1, "Read as PyArrow Table with zero-copy")
        .def("wait_for_data", &qadataswap::SharedDataFrame::wait_for_data,
             py::arg("timeout_ms") = -1)
        .def("notify_data_ready", &qadataswap::SharedDataFrame::notify_data_ready)
        .def("get_stats", &qadataswap::SharedDataFrame::get_stats)
        .def("close", &qadataswap::SharedDataFrame::close);
}