# Changelog

All notable changes to this project will be documented in this
file.

The format is based on [Keep a Changelog][], and this project
adheres to [Semantic Versioning][].

[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.htmlØ

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

[0.0.2]: https://github.com/tomshafer/photoutils/releases/tag/0.0.2
[0.0.1]: https://github.com/tomshafer/photoutils/releases/tag/0.0.1
