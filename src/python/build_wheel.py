#!/usr/bin/env python3
"""
Build script for QADataSwap wheels.

This script builds wheels for different Python versions and architectures.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and print output."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if check and result.returncode != 0:
        sys.exit(result.returncode)

    return result

def clean_build():
    """Clean previous build artifacts."""
    print("Cleaning build artifacts...")

    dirs_to_clean = ["build", "dist", "*.egg-info", "qadataswap/*.so"]
    for pattern in dirs_to_clean:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"Removed directory: {path}")
            else:
                path.unlink()
                print(f"Removed file: {path}")

def build_sdist():
    """Build source distribution."""
    print("Building source distribution...")
    run_command("python setup.py sdist")

def build_wheel():
    """Build wheel distribution."""
    print("Building wheel distribution...")
    run_command("python setup.py bdist_wheel")

def build_with_pip():
    """Build using pip (recommended)."""
    print("Building with pip...")
    run_command("python -m pip wheel . -w dist --no-deps")

def check_wheel():
    """Check wheel contents."""
    print("Checking wheel contents...")

    wheel_files = list(Path("dist").glob("*.whl"))
    if not wheel_files:
        print("No wheel files found!")
        return

    wheel_file = wheel_files[0]
    print(f"Checking wheel: {wheel_file}")

    try:
        import zipfile
        with zipfile.ZipFile(wheel_file, 'r') as zf:
            print("\nWheel contents:")
            for name in sorted(zf.namelist()):
                print(f"  {name}")
    except ImportError:
        print("zipfile not available, skipping wheel content check")

def main():
    """Main build process."""
    if len(sys.argv) > 1 and sys.argv[1] == "--clean-only":
        clean_build()
        return

    print("QADataSwap Wheel Builder")
    print("=" * 50)

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Clean previous builds
    clean_build()

    # Install build dependencies
    print("Installing build dependencies...")
    run_command("python -m pip install --upgrade pip setuptools wheel build")

    # Try to install optional dependencies
    try:
        run_command("python -m pip install pyarrow polars", check=False)
        print("Arrow dependencies installed successfully")
    except:
        print("Warning: Could not install Arrow dependencies, building simple version")

    # Build distributions
    try:
        build_sdist()

        # Try modern build first
        try:
            run_command("python -m build --wheel")
        except:
            print("Modern build failed, falling back to setuptools...")
            build_wheel()

        check_wheel()

        print("\n" + "=" * 50)
        print("Build completed successfully!")
        print("\nGenerated files:")
        for f in Path("dist").iterdir():
            print(f"  {f}")

        print("\nTo install locally:")
        wheel_files = list(Path("dist").glob("*.whl"))
        if wheel_files:
            print(f"  pip install {wheel_files[0]}")

        print("\nTo upload to PyPI:")
        print("  python -m twine upload dist/*")

    except Exception as e:
        print(f"Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()