"""Tests for the photoutils cleanup module."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest import LogCaptureFixture

from photoutils.cleanup import cleanup_directory
from photoutils.core import FILE_ACTIONS, NotADirectoryError


class TestCleanupDirectory:
    """Test the cleanup_directory function."""

    def test_cleanup_directory_not_directory(self, temp_dir: Path):
        """Test error when path is not a directory."""
        not_dir = temp_dir / "not_a_dir.txt"
        not_dir.touch()

        with pytest.raises(NotADirectoryError):
            cleanup_directory(not_dir)

    def test_cleanup_directory_no_files(
        self, temp_dir: Path, caplog: LogCaptureFixture
    ):
        """Test cleanup when no files are found."""
        with caplog.at_level(logging.INFO):
            cleanup_directory(temp_dir)

        assert "No files to organize" in caplog.text
        assert str(temp_dir) in caplog.text

    def test_cleanup_directory_organizes_files(self, temp_dir: Path):
        """Test that files are organized into correct subdirectories."""
        # Create test files
        files = [
            ("test.JPG", "JPEGs"),
            ("photo.jpg", "JPEGs"),
            ("raw.RAF", "Raw Files"),
            ("backup.DNG", "Raw Files"),
            ("video.MOV", "Videos"),
        ]

        for filename, _ in files:
            (temp_dir / filename).write_bytes(b"test data")

        cleanup_directory(temp_dir)

        # Check that files were moved to correct subdirectories
        for filename, expected_subdir in files:
            expected_path = temp_dir / expected_subdir / filename
            assert expected_path.exists()
            assert not (temp_dir / filename).exists()

    def test_cleanup_directory_dry_run(self, temp_dir: Path, caplog: LogCaptureFixture):
        """Test dry run mode doesn't actually move files."""
        # Create test files
        test_files = ["test.JPG", "photo.RAF", "video.MOV"]
        for filename in test_files:
            (temp_dir / filename).write_bytes(b"test data")

        with caplog.at_level(logging.INFO):
            cleanup_directory(temp_dir, dry_run=True)

        # Check that original files still exist
        for filename in test_files:
            assert (temp_dir / filename).exists()

        # Check that no subdirectories were created
        assert not (temp_dir / "JPEGs").exists()
        assert not (temp_dir / "Raw Files").exists()
        assert not (temp_dir / "Videos").exists()

        # Check log messages
        assert "Would move" in caplog.text
        assert "Dry run completed" in caplog.text

    def test_cleanup_directory_handles_duplicates(
        self,
        temp_dir: Path,
        caplog: LogCaptureFixture,
    ):
        """Test that duplicate files are handled correctly."""
        # Create source files
        (temp_dir / "test.JPG").write_bytes(b"original")

        # Create JPEGs directory with existing file
        jpegs_dir = temp_dir / "JPEGs"
        jpegs_dir.mkdir()
        (jpegs_dir / "test.JPG").write_bytes(b"existing")

        # Create another file with same name
        (temp_dir / "test_copy.JPG").write_bytes(b"duplicate")
        (temp_dir / "test_copy.JPG").rename(temp_dir / "test2.JPG")

        with caplog.at_level(logging.WARNING):
            cleanup_directory(temp_dir)

        # Check that duplicate was renamed
        assert (jpegs_dir / "test.JPG").exists()
        assert (jpegs_dir / "test (1).JPG").exists()
        assert (jpegs_dir / "test2.JPG").exists()

        # Check warning was logged
        assert "Duplicate file detected" in caplog.text

    def test_cleanup_directory_handles_errors(
        self,
        temp_dir: Path,
        caplog: LogCaptureFixture,
    ):
        """Test that errors are handled gracefully."""
        # Create a test file
        test_file = temp_dir / "test.JPG"
        test_file.write_bytes(b"test data")

        # Mock move_image_simple to raise an exception
        with patch("photoutils.cleanup.move_image_simple") as mock_move:
            mock_move.side_effect = Exception("Mock error")

            with caplog.at_level(logging.ERROR):
                cleanup_directory(temp_dir)

        # Check that error was logged
        assert "Error processing" in caplog.text
        assert "test.JPG" in caplog.text
        assert "Mock error" in caplog.text

    def test_cleanup_directory_case_insensitive(self, temp_dir: Path):
        """Test that file extension matching is case insensitive."""
        # Create files with different cases
        files = [
            ("test.jpg", "JPEGs"),
            ("photo.JPG", "JPEGs"),
            ("raw.raf", "Raw Files"),
            ("backup.RAF", "Raw Files"),
            ("video.mov", "Videos"),
            ("clip.MOV", "Videos"),
        ]

        for filename, _ in files:
            (temp_dir / filename).write_bytes(b"test data")

        cleanup_directory(temp_dir)

        # Check that all files were moved regardless of case
        for filename, expected_subdir in files:
            expected_path = temp_dir / expected_subdir / filename
            assert expected_path.exists()

    def test_cleanup_directory_ignores_unsupported_files(
        self,
        temp_dir: Path,
        caplog: LogCaptureFixture,
    ):
        """Test that unsupported file types are ignored."""
        # Create mix of supported and unsupported files
        (temp_dir / "test.JPG").write_bytes(b"supported")
        (temp_dir / "document.txt").write_bytes(b"unsupported")
        (temp_dir / "archive.zip").write_bytes(b"unsupported")

        with caplog.at_level(logging.INFO):
            cleanup_directory(temp_dir)

        # Check that only supported file was moved
        assert (temp_dir / "JPEGs" / "test.JPG").exists()
        assert (temp_dir / "document.txt").exists()  # Still in original location
        assert (temp_dir / "archive.zip").exists()  # Still in original location

        # Check log shows only 1 file found
        assert "Found [bold blue]1[/bold blue] files to organize" in caplog.text

    def test_cleanup_directory_creates_subdirectories(self, temp_dir: Path):
        """Test that subdirectories are created as needed."""
        # Create files for all supported types
        files = [
            ("test.JPG", "JPEGs"),
            ("raw.RAF", "Raw Files"),
            ("backup.DNG", "Raw Files"),
            ("video.MOV", "Videos"),
        ]

        for filename, _ in files:
            (temp_dir / filename).write_bytes(b"test data")

        cleanup_directory(temp_dir)

        # Check that all necessary subdirectories were created
        for _, expected_subdir in files:
            assert (temp_dir / expected_subdir).is_dir()

    def test_cleanup_directory_permissions(self, temp_dir: Path):
        """Test that moved files have correct permissions."""
        test_file = temp_dir / "test.JPG"
        test_file.write_bytes(b"test data")

        cleanup_directory(temp_dir)

        moved_file = temp_dir / "JPEGs" / "test.JPG"
        assert oct(moved_file.stat().st_mode)[-3:] == "644"


class TestConstants:
    """Test that cleanup uses the same constants as core."""

    def test_file_actions_available(self):
        """Test that FILE_ACTIONS is available from core."""
        expected = {
            "RAF": "Raw Files",
            "DNG": "Raw Files",
            "JPG": "JPEGs",
            "MOV": "Videos",
        }

        assert FILE_ACTIONS == expected
