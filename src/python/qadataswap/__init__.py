"""
QADataSwap: High-performance cross-language zero-copy data transfer framework

A powerful library for sharing data between C++, Python, and Rust processes
using shared memory with zero-copy semantics.
"""

__version__ = "0.1.0"
__author__ = "QADataSwap Team"
__email__ = "support@qadataswap.org"

# Import the compiled extension
try:
    from .qadataswap import SharedDataFrame
    HAS_ARROW_SUPPORT = True
except ImportError:
    try:
        from .qadataswap import SimpleSharedMemory as SharedDataFrame
        HAS_ARROW_SUPPORT = False
        import warnings
        warnings.warn(
            "Arrow support not available, using simplified interface. "
            "Install PyArrow for full functionality.",
            ImportWarning
        )
    except ImportError:
        raise ImportError(
            "QADataSwap extension module not found. "
            "Please ensure the package was installed correctly."
        )

# Convenience imports
__all__ = ["SharedDataFrame", "HAS_ARROW_SUPPORT", "__version__"]

def get_version():
    """Get the current version of QADataSwap."""
    return __version__

def has_arrow_support():
    """Check if Arrow/Polars support is available."""
    return HAS_ARROW_SUPPORT

def create_writer(name, size_mb=100, buffer_count=3):
    """
    Create a shared memory writer.

    Args:
        name (str): Unique name for the shared memory region
        size_mb (int): Size in megabytes (default: 100)
        buffer_count (int): Number of buffers (default: 3)

    Returns:
        SharedDataFrame: Writer instance
    """
    return SharedDataFrame.create_writer(name, size_mb, buffer_count)

def create_reader(name):
    """
    Create a shared memory reader.

    Args:
        name (str): Name of the shared memory region to attach to

    Returns:
        SharedDataFrame: Reader instance
    """
    return SharedDataFrame.create_reader(name)