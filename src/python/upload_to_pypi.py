#!/usr/bin/env python3
"""
Upload script for QADataSwap to PyPI.

This script handles uploading to both Test PyPI and production PyPI.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if check and result.returncode != 0:
        sys.exit(result.returncode)

    return result

def check_dependencies():
    """Check if required tools are installed."""
    print("Checking dependencies...")

    try:
        import twine
        print(f"✓ twine version: {twine.__version__}")
    except ImportError:
        print("✗ twine not found. Installing...")
        run_command("python -m pip install twine")

def check_files():
    """Check if distribution files exist."""
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("✗ dist/ directory not found. Run build first.")
        sys.exit(1)

    whl_files = list(dist_dir.glob("*.whl"))
    tar_files = list(dist_dir.glob("*.tar.gz"))

    if not whl_files:
        print("✗ No wheel files found in dist/")
        sys.exit(1)

    if not tar_files:
        print("✗ No source distribution found in dist/")
        sys.exit(1)

    print(f"✓ Found {len(whl_files)} wheel file(s)")
    print(f"✓ Found {len(tar_files)} source distribution(s)")

    for f in sorted(dist_dir.iterdir()):
        print(f"  {f.name}")

def check_credentials(test_pypi=False):
    """Check PyPI credentials."""
    if test_pypi:
        print("Checking TestPyPI credentials...")
        # You can set up credentials in ~/.pypirc or use tokens
        print("Make sure you have TestPyPI credentials configured")
        print("Visit: https://test.pypi.org/manage/account/token/")
    else:
        print("Checking PyPI credentials...")
        print("Make sure you have PyPI credentials configured")
        print("Visit: https://pypi.org/manage/account/token/")

def upload_to_test_pypi():
    """Upload to Test PyPI."""
    print("Uploading to Test PyPI...")

    cmd = "python -m twine upload --repository testpypi dist/*"
    run_command(cmd)

    print("\n" + "="*50)
    print("✓ Upload to Test PyPI completed!")
    print("\nTo install from Test PyPI:")
    print("  pip install --index-url https://test.pypi.org/simple/ qadataswap")
    print("\nTest PyPI URL:")
    print("  https://test.pypi.org/project/qadataswap/")

def upload_to_pypi():
    """Upload to production PyPI."""
    print("Uploading to production PyPI...")

    # Extra confirmation for production
    response = input("Are you sure you want to upload to PRODUCTION PyPI? (yes/no): ")
    if response.lower() != "yes":
        print("Upload cancelled.")
        return

    cmd = "python -m twine upload dist/*"
    run_command(cmd)

    print("\n" + "="*50)
    print("✓ Upload to PyPI completed!")
    print("\nTo install:")
    print("  pip install qadataswap")
    print("\nPyPI URL:")
    print("  https://pypi.org/project/qadataswap/")

def check_package():
    """Check package with twine."""
    print("Checking package with twine...")
    run_command("python -m twine check dist/*")

def main():
    """Main upload process."""
    parser = argparse.ArgumentParser(description="Upload QADataSwap to PyPI")
    parser.add_argument("--test", action="store_true", help="Upload to Test PyPI")
    parser.add_argument("--prod", action="store_true", help="Upload to production PyPI")
    parser.add_argument("--check-only", action="store_true", help="Only check files, don't upload")

    args = parser.parse_args()

    if not any([args.test, args.prod, args.check_only]):
        print("Please specify --test, --prod, or --check-only")
        parser.print_help()
        sys.exit(1)

    print("QADataSwap PyPI Upload Tool")
    print("=" * 50)

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Run checks
    check_dependencies()
    check_files()
    check_package()

    if args.check_only:
        print("✓ All checks passed!")
        return

    if args.test:
        check_credentials(test_pypi=True)
        upload_to_test_pypi()

    if args.prod:
        check_credentials(test_pypi=False)
        upload_to_pypi()

if __name__ == "__main__":
    main()