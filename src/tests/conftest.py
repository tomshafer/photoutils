"""Test configuration and fixtures for photoutils tests."""

import tempfile
from collections.abc import Generator
from datetime import date
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def watch_dir(temp_dir: Path) -> Path:
    """Create a directory to watch for file changes."""
    watch_path = temp_dir / "watch"
    watch_path.mkdir()
    return watch_path


@pytest.fixture
def sample_image_file(temp_dir: Path) -> Path:
    """Create a sample image file for testing."""
    image_file = temp_dir / "test_image.JPG"
    image_file.write_bytes(b"fake image data")
    return image_file


@pytest.fixture
def sample_raw_file(temp_dir: Path) -> Path:
    """Create a sample RAW file for testing."""
    raw_file = temp_dir / "test_raw.RAF"
    raw_file.write_bytes(b"fake raw data")
    return raw_file


@pytest.fixture
def sample_video_file(temp_dir: Path) -> Path:
    """Create a sample video file for testing."""
    video_file = temp_dir / "test_video.MOV"
    video_file.write_bytes(b"fake video data")
    return video_file


@pytest.fixture
def file_queue() -> Queue[Path | None]:
    """Create a file queue for testing."""
    return Queue()


@pytest.fixture
def mock_exiftool() -> MagicMock:
    """Mock ExifToolHelper for EXIF data testing."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=None)
    return mock


@pytest.fixture
def mock_observer() -> MagicMock:
    """Mock watchdog Observer for testing."""
    mock = MagicMock()
    mock.start = MagicMock()
    mock.stop = MagicMock()
    mock.join = MagicMock()
    return mock


@pytest.fixture
def sample_date() -> date:
    """Sample date for testing."""
    return date(2023, 12, 25)


@pytest.fixture
def existing_date_dir(temp_dir: Path, sample_date: date) -> Path:
    """Create an existing date directory."""
    date_dir = temp_dir / sample_date.isoformat()
    date_dir.mkdir()
    return date_dir


@pytest.fixture
def existing_target_dirs(existing_date_dir: Path) -> dict[str, Path]:
    """Create existing target directories for different file types."""
    dirs: dict[str, Path] = {}
    for file_type in ["Raw Files", "JPEGs", "Videos"]:
        target_dir = existing_date_dir / file_type
        target_dir.mkdir()
        dirs[file_type] = target_dir
    return dirs
