#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "simple_arena.h"

namespace py = pybind11;

namespace qadataswap {

class SimpleSharedMemory {
public:
    SimpleSharedMemory(const std::string& name, size_t size_mb = 100, size_t buffer_count = 3)
        : arena_(std::make_unique<SimpleArena>(name, size_mb * 1024 * 1024, buffer_count)) {}

    bool create_writer() {
        return arena_->CreateWriter();
    }

    bool attach_reader() {
        return arena_->AttachReader();
    }

    bool write_bytes(const py::bytes& data) {
        std::string str_data = data;
        return arena_->WriteBytes(reinterpret_cast<const uint8_t*>(str_data.data()), str_data.size());
    }

    py::bytes read_bytes(int timeout_ms = -1) {
        std::vector<uint8_t> buffer(1024 * 1024); // 1MB buffer
        size_t out_size;
        if (arena_->ReadBytes(buffer.data(), buffer.size(), &out_size, timeout_ms)) {
            return py::bytes(reinterpret_cast<const char*>(buffer.data()), out_size);
        }
        return py::bytes();
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

    static std::shared_ptr<SimpleSharedMemory> create_writer(const std::string& name,
                                                           size_t size_mb = 100,
                                                           size_t buffer_count = 3) {
        auto sdf = std::make_shared<SimpleSharedMemory>(name, size_mb, buffer_count);
        if (!sdf->create_writer()) {
            throw std::runtime_error("Failed to create writer");
        }
        return sdf;
    }

    static std::shared_ptr<SimpleSharedMemory> create_reader(const std::string& name) {
        auto sdf = std::make_shared<SimpleSharedMemory>(name);
        if (!sdf->attach_reader()) {
            throw std::runtime_error("Failed to attach reader");
        }
        return sdf;
    }

private:
    std::unique_ptr<SimpleArena> arena_;
};

} // namespace qadataswap

PYBIND11_MODULE(qadataswap, m) {
    m.doc() = "QADataSwap: High-performance cross-language zero-copy data transfer (simple version)";

    py::class_<qadataswap::SimpleSharedMemory, std::shared_ptr<qadataswap::SimpleSharedMemory>>(m, "SimpleSharedMemory")
        .def(py::init<const std::string&, size_t, size_t>(),
             py::arg("name"), py::arg("size_mb") = 100, py::arg("buffer_count") = 3)
        .def_static("create_writer",
                   static_cast<std::shared_ptr<qadataswap::SimpleSharedMemory>(*)(const std::string&, size_t, size_t)>(&qadataswap::SimpleSharedMemory::create_writer),
                   py::arg("name"), py::arg("size_mb") = 100, py::arg("buffer_count") = 3)
        .def_static("create_reader",
                   static_cast<std::shared_ptr<qadataswap::SimpleSharedMemory>(*)(const std::string&)>(&qadataswap::SimpleSharedMemory::create_reader),
                   py::arg("name"))
        .def("write_bytes", &qadataswap::SimpleSharedMemory::write_bytes,
             "Write raw bytes to shared memory")
        .def("read_bytes", &qadataswap::SimpleSharedMemory::read_bytes,
             py::arg("timeout_ms") = -1, "Read raw bytes from shared memory")
        .def("get_stats", &qadataswap::SimpleSharedMemory::get_stats)
        .def("close", &qadataswap::SimpleSharedMemory::close);
}