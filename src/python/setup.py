import os
import sys
from pathlib import Path

import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup, find_packages
import pyarrow as pa

# Get version
def get_version():
    version_file = Path(__file__).parent / "qadataswap" / "__init__.py"
    for line in version_file.read_text().splitlines():
        if line.startswith("__version__"):
            return line.split("=")[1].strip().strip('"\'')
    raise RuntimeError("Unable to find version string.")

# Get Arrow include directories and libraries
try:
    arrow_include_dirs = pa.get_include()
    arrow_library_dirs = pa.get_library_dirs()
    arrow_libraries = pa.get_libraries()
    ARROW_AVAILABLE = True
except Exception as e:
    print(f"Warning: Arrow not available ({e}), falling back to simple version")
    ARROW_AVAILABLE = False

def get_ext_modules():
    """Build extension modules based on available dependencies."""
    if ARROW_AVAILABLE:
        # Full version with Arrow support
        return [
            Pybind11Extension(
                "qadataswap.qadataswap",
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
                runtime_library_dirs=arrow_library_dirs,
                cxx_std=17,
                define_macros=[
                    ("VERSION_INFO", f'"{get_version()}"'),
                    ("QADATASWAP_ARROW_SUPPORT", "1"),
                ],
                language="c++",
            ),
        ]
    else:
        # Simple version without Arrow
        return [
            Pybind11Extension(
                "qadataswap.qadataswap",
                [
                    "qadataswap_simple.cpp",
                    "../cpp/src/simple_arena.cpp",
                ],
                include_dirs=[
                    pybind11.get_cmake_dir() + "/../../../include",
                    "../cpp/include",
                ],
                libraries=["rt", "pthread"],
                cxx_std=17,
                define_macros=[
                    ("VERSION_INFO", f'"{get_version()}"'),
                    ("QADATASWAP_SIMPLE_MODE", "1"),
                ],
                language="c++",
            ),
        ]

# Read README
readme_path = Path(__file__).parent / "README.md"
if not readme_path.exists():
    readme_path = Path(__file__).parent / "../../README.md"

long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

setup(
    name="qadataswap",
    version=get_version(),
    author="QADataSwap Team",
    author_email="support@qadataswap.org",
    description="High-performance cross-language zero-copy data transfer framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/quantaxis/qadataswap",
    project_urls={
        "Bug Tracker": "https://github.com/quantaxis/qadataswap/issues",
        "Documentation": "https://qadataswap.readthedocs.io/",
        "Source Code": "https://github.com/quantaxis/qadataswap",
    },
    packages=find_packages(),
    ext_modules=get_ext_modules(),
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.20.0",
    ],
    extras_require={
        "arrow": ["pyarrow>=10.0.0", "polars>=0.18.0"],
        "dev": ["pytest>=6.0", "pytest-benchmark", "black", "ruff"],
        "test": ["pytest>=6.0", "pytest-benchmark"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: C++",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)