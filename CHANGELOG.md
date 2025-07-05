# Changelog

All notable changes to this project will be documented in this
file.

The format is based on [Keep a Changelog][], and this project
adheres to [Semantic Versioning][].

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html

## [Unreleased]

### Added

- Added `photoutils cleanup` command for organizing existing directories.
- Added `core.py` module with shared file processing logic.
- Added `move_image_simple()` function for type-based file organization.
- Added comprehensive test suite for cleanup functionality.
- Added tests for core functionality with Claude Code.
- Added test for directory prefix matching.
- Added duplicate file handling with numbered suffixes (e.g., `photo.jpg` → `photo (1).jpg`).
- Added warning logs when duplicates are detected in processing.

### Changed

- Refactored common file processing logic from `daemon.py` into reusable `core.py` module.
- Updated `daemon.py` to import shared functions from `core.py`.
- Enhanced CLI with new cleanup subcommand alongside existing daemon functionality.

## [0.0.3] (2025-07-04)

### Added

- Added `wait_for_file()`, which blocks until a file has positive
  size for three time steps. After sixty seconds, a
  `TimeoutError` will be raised.
- Re-implemented multithreading for file processing with
  `ThreadPoolExecutor`.
- Added Rich logging with colored output and better formatting.

### Changed

- `resolve_image()` now uses any directory whose name begins with
  the image's ISO-formatted date.
- `photoutils daemon` now uses multithreading again for better performance
  on systems with multiple files being processed simultaneously.
- File extension filtering now happens before queuing to reduce overhead.
- Enhanced error handling ensures individual file processing failures don't
  stop the entire daemon.
- Improved logging output with Rich formatting for better visibility.

## [0.0.2] (2025-06-01)

### Added

- Added a CI workflow to run the linter and type checker.
- Added `py.typed`.

### Changed

- `photoutils daemon` is now single-threaded.
- Fixed the package version number.
- Marked the package as compatible with Pythons ≥ 3.10.

## [0.0.1] (2025-05-24)

### Added

- Initial version of the package.
- `photoutils daemon` will run a filesystem watcher that
  automatically organizes photos and videos by date and file
  type.

[Unreleased]: https://github.com/tomshafer/photoutils/compare/0.0.3...HEAD
[0.0.3]: https://github.com/tomshafer/photoutils/compare/0.0.2...0.0.3
[0.0.2]: https://github.com/tomshafer/photoutils/compare/0.0.1...0.0.2
[0.0.1]: https://github.com/tomshafer/photoutils/releases/tag/0.0.1
