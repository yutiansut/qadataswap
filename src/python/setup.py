import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup, Extension
import pyarrow as pa

# Get Arrow include directories and libraries
arrow_include_dirs = pa.get_include()
arrow_library_dirs = pa.get_library_dirs()
arrow_libraries = pa.get_libraries()

ext_modules = [
    Pybind11Extension(
        "qadataswap",
        [
            "qadataswap_py.cpp",
            "../cpp/src/shared_memory_arena.cpp",
        ],
        include_dirs=[
            pybind11.get_cmake_dir() + "/../../../include",
            "../cpp/include",
            arrow_include_dirs,
        ],
        library_dirs=arrow_library_dirs,
        libraries=arrow_libraries + ["rt", "pthread"],
        cxx_std=17,
        define_macros=[("VERSION_INFO", '"dev"')],
        language="c++",
    ),
]

setup(
    name="qadataswap",
    version="0.1.0",
    author="QADataSwap Team",
    author_email="",
    description="High-performance cross-language zero-copy data transfer with Polars support",
    long_description=open("../../README.md").read(),
    long_description_content_type="text/markdown",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.8",
    install_requires=[
        "pyarrow>=10.0.0",
        "polars>=0.18.0",
        "numpy",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: System :: Distributed Computing",
    ],
)