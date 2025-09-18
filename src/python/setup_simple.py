import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ext_modules = [
    Pybind11Extension(
        "qadataswap",
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
        define_macros=[("VERSION_INFO", '"dev"')],
        language="c++",
    ),
]

setup(
    name="qadataswap-simple",
    version="0.1.0",
    author="QADataSwap Team",
    author_email="",
    description="High-performance cross-language zero-copy data transfer (simple version)",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)