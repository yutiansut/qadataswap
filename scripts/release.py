#!/usr/bin/env python3
"""
Release automation script for QADataSwap.

This script automates the release process including:
- Version bumping
- Git tagging
- Building wheels
- Publishing to PyPI
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import re

def run_command(cmd, check=True, cwd=None):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if check and result.returncode != 0:
        sys.exit(result.returncode)

    return result

def get_current_version():
    """Get current version from __init__.py."""
    init_file = Path("src/python/qadataswap/__init__.py")
    content = init_file.read_text()

    match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    else:
        raise RuntimeError("Could not find version in __init__.py")

def bump_version(current_version, bump_type):
    """Bump version according to semantic versioning."""
    major, minor, patch = map(int, current_version.split('.'))

    if bump_type == 'major':
        return f"{major + 1}.0.0"
    elif bump_type == 'minor':
        return f"{major}.{minor + 1}.0"
    elif bump_type == 'patch':
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

def update_version_file(new_version):
    """Update version in __init__.py."""
    init_file = Path("src/python/qadataswap/__init__.py")
    content = init_file.read_text()

    new_content = re.sub(
        r'__version__ = ["\'][^"\']+["\']',
        f'__version__ = "{new_version}"',
        content
    )

    init_file.write_text(new_content)
    print(f"Updated version to {new_version} in {init_file}")

def create_changelog_entry(version):
    """Create a changelog entry."""
    changelog = Path("CHANGELOG.md")

    if not changelog.exists():
        changelog.write_text("# Changelog\n\n")

    content = changelog.read_text()

    # Add new entry at the top
    new_entry = f"""## [{version}] - {subprocess.check_output(['date', '+%Y-%m-%d']).decode().strip()}

### Added
- New features

### Changed
- Improvements

### Fixed
- Bug fixes

"""

    # Insert after the first line (# Changelog)
    lines = content.split('\n')
    lines.insert(2, new_entry)
    changelog.write_text('\n'.join(lines))

    print(f"Added changelog entry for version {version}")
    print("Please edit CHANGELOG.md to add actual changes before continuing.")
    input("Press Enter when you've updated the changelog...")

def git_operations(version):
    """Perform git operations."""
    # Check if working directory is clean
    result = run_command("git status --porcelain", check=False)
    if result.stdout.strip():
        print("Working directory is not clean. Please commit or stash changes.")
        sys.exit(1)

    # Add and commit version changes
    run_command("git add src/python/qadataswap/__init__.py CHANGELOG.md")
    run_command(f'git commit -m "Bump version to {version}"')

    # Create tag
    run_command(f'git tag -a v{version} -m "Release version {version}"')

    print(f"Created git tag v{version}")

def build_and_upload(test_only=False):
    """Build wheels and upload to PyPI."""
    print("Building wheels...")

    # Clean previous builds
    run_command("rm -rf src/python/dist src/python/build", check=False)

    # Build
    run_command("python -m build", cwd="src/python")

    # Check
    run_command("python -m twine check dist/*", cwd="src/python")

    if test_only:
        print("Uploading to Test PyPI...")
        run_command("python -m twine upload --repository testpypi dist/*", cwd="src/python")
        print("\nTest the package with:")
        print("pip install --index-url https://test.pypi.org/simple/ qadataswap")
    else:
        response = input("Upload to production PyPI? (yes/no): ")
        if response.lower() == 'yes':
            run_command("python -m twine upload dist/*", cwd="src/python")
            print("✓ Package uploaded to PyPI!")

def push_changes():
    """Push changes to remote repository."""
    response = input("Push changes and tags to remote? (yes/no): ")
    if response.lower() == 'yes':
        run_command("git push origin main")
        run_command("git push --tags")
        print("✓ Changes pushed to remote repository")

def main():
    """Main release process."""
    parser = argparse.ArgumentParser(description="Release QADataSwap")
    parser.add_argument("bump_type", choices=["major", "minor", "patch"],
                       help="Type of version bump")
    parser.add_argument("--test-only", action="store_true",
                       help="Upload to Test PyPI only")
    parser.add_argument("--no-upload", action="store_true",
                       help="Skip PyPI upload")
    parser.add_argument("--no-git", action="store_true",
                       help="Skip git operations")

    args = parser.parse_args()

    print("QADataSwap Release Tool")
    print("=" * 50)

    # Change to repository root
    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)

    # Get current version and calculate new version
    current_version = get_current_version()
    new_version = bump_version(current_version, args.bump_type)

    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")

    response = input("Proceed with release? (yes/no): ")
    if response.lower() != 'yes':
        print("Release cancelled.")
        return

    # Update version
    update_version_file(new_version)

    # Update changelog
    create_changelog_entry(new_version)

    # Git operations
    if not args.no_git:
        git_operations(new_version)

    # Build and upload
    if not args.no_upload:
        build_and_upload(test_only=args.test_only)

    # Push changes
    if not args.no_git:
        push_changes()

    print("\n" + "=" * 50)
    print(f"✓ Release {new_version} completed!")

    if not args.no_upload:
        if args.test_only:
            print("Package uploaded to Test PyPI")
            print("Test with: pip install --index-url https://test.pypi.org/simple/ qadataswap")
        else:
            print("Package uploaded to PyPI")
            print("Install with: pip install qadataswap")

if __name__ == "__main__":
    main()