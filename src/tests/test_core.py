"""Tests for the photoutils core module."""

import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest import LogCaptureFixture

from photoutils.core import (
    FILE_ACTIONS,
    MultipleTargetsError,
    NotADirectoryError,
    _get_unique_filename,  # type: ignore
    move_image,
    move_image_simple,
    read_exif_date,
    resolve_target_dir,
)


class TestConstants:
    """Test module constants."""

    def test_file_actions_mapping(self):
        """Test that FILE_ACTIONS contains expected mappings."""
        expected = {
            "RAF": "Raw Files",
            "DNG": "Raw Files",
            "JPG": "JPEGs",
            "MOV": "Videos",
        }

        assert FILE_ACTIONS == expected


class TestNotADirectoryError:
    """Test the NotADirectoryError exception."""

    def test_error_message(self, temp_dir: Path):
        """Test error message format."""
        non_dir = temp_dir / "not_a_dir.txt"
        non_dir.touch()

        error = NotADirectoryError(non_dir)
        assert str(error) == f"the path {non_dir} is not a directory"


class TestMultipleTargetsError:
    """Test the MultipleTargetsError exception."""

    def test_error_message(self, temp_dir: Path):
        """Test error message format."""
        candidates = [temp_dir / "dir1", temp_dir / "dir2"]
        for candidate in candidates:
            candidate.mkdir()

        error = MultipleTargetsError(temp_dir, candidates)
        assert str(error) == f"{temp_dir} has multiple potential children: {candidates}"


class TestGetUniqueFilename:
    """Test the _get_unique_filename function."""

    def test_unique_filename_no_conflict(self, temp_dir: Path):
        """Test that original filename is returned when no conflict exists."""
        result = _get_unique_filename(temp_dir, "test.jpg")
        assert result == temp_dir / "test.jpg"

    def test_unique_filename_single_conflict(self, temp_dir: Path):
        """Test that numbered suffix is added for first conflict."""
        existing_file = temp_dir / "test.jpg"
        existing_file.touch()

        result = _get_unique_filename(temp_dir, "test.jpg")
        assert result == temp_dir / "test (1).jpg"

    def test_unique_filename_multiple_conflicts(self, temp_dir: Path):
        """Test that counter increments for multiple conflicts."""
        # Create existing files
        (temp_dir / "test.jpg").touch()
        (temp_dir / "test (1).jpg").touch()
        (temp_dir / "test (2).jpg").touch()

        result = _get_unique_filename(temp_dir, "test.jpg")
        assert result == temp_dir / "test (3).jpg"

    def test_unique_filename_existing_numbered_suffix(self, temp_dir: Path):
        """Test handling of filenames that already have numbered suffixes."""
        existing_file = temp_dir / "test (5).jpg"
        existing_file.touch()

        result = _get_unique_filename(temp_dir, "test (5).jpg")
        assert result == temp_dir / "test (6).jpg"


class TestReadExifDate:
    """Test the read_exif_date function."""

    def test_read_exif_date_success(
        self,
        sample_image_file: Path,
        mock_exiftool: MagicMock,
    ):
        """Test successful EXIF date reading."""
        mock_exiftool.get_tags.return_value = [
            {"EXIF:DateTimeOriginal": "2023:12:25 14:30:00"}
        ]

        with patch("photoutils.core.ExifToolHelper", return_value=mock_exiftool):
            result = read_exif_date(sample_image_file)

        assert result == date(2023, 12, 25)
        mock_exiftool.get_tags.assert_called_once_with(
            [sample_image_file], "EXIF:DateTimeOriginal"
        )

    def test_read_exif_date_with_whitespace(
        self,
        sample_image_file: Path,
        mock_exiftool: MagicMock,
    ):
        """Test EXIF date reading with whitespace."""
        mock_exiftool.get_tags.return_value = [
            {"EXIF:DateTimeOriginal": "  2023:12:25 14:30:00  "}
        ]

        with patch("photoutils.core.ExifToolHelper", return_value=mock_exiftool):
            result = read_exif_date(sample_image_file)

        assert result == date(2023, 12, 25)


class TestResolveTargetDir:
    """Test the resolve_target_dir function."""

    def test_resolve_target_dir_not_directory(self, temp_dir: Path):
        """Test error when path is not a directory."""
        not_dir = temp_dir / "not_a_dir.txt"
        not_dir.touch()

        with pytest.raises(NotADirectoryError):
            resolve_target_dir(not_dir, date(2023, 12, 25))

    def test_resolve_target_dir_no_candidates(self, temp_dir: Path):
        """Test creating new dir when no candidates exist."""
        test_date = date(2023, 12, 25)
        result = resolve_target_dir(temp_dir, test_date)

        assert result == temp_dir / "2023-12-25"

    def test_resolve_target_dir_single_candidate(self, temp_dir: Path):
        """Test returning single matching directory."""
        test_date = date(2023, 12, 25)
        existing_dir = temp_dir / "2023-12-25"
        existing_dir.mkdir()

        result = resolve_target_dir(temp_dir, test_date)

        assert result == existing_dir

    def test_resolve_target_dir_multiple_candidates(self, temp_dir: Path):
        """Test error when multiple candidates exist."""
        test_date = date(2023, 12, 25)
        dir1 = temp_dir / "2023-12-25_event1"
        dir2 = temp_dir / "2023-12-25_event2"
        dir1.mkdir()
        dir2.mkdir()

        with pytest.raises(MultipleTargetsError):
            resolve_target_dir(temp_dir, test_date)


class TestMoveImage:
    """Test the move_image function."""

    def test_move_image_creates_directory_structure(
        self,
        temp_dir: Path,
        sample_image_file: Path,
    ):
        """Test move_image creates proper date-based structure."""
        test_date = date(2023, 12, 25)

        # Move the file to temp_dir first
        source_file = temp_dir / sample_image_file.name
        sample_image_file.rename(source_file)

        move_image(source_file, test_date)

        expected_path = temp_dir / "2023-12-25" / "JPEGs" / sample_image_file.name
        assert expected_path.exists()
        assert not source_file.exists()

    def test_move_image_handles_duplicates(
        self,
        temp_dir: Path,
        caplog: LogCaptureFixture,
    ):
        """Test that move_image handles duplicate files correctly."""
        test_date = date(2023, 12, 25)

        # Create source files
        source_file1 = temp_dir / "test.JPG"
        source_file2 = temp_dir / "test_copy.JPG"
        source_file1.write_bytes(b"test data 1")
        source_file2.write_bytes(b"test data 2")

        # Move first file
        move_image(source_file1, test_date)

        # Rename second file to match first file's name
        source_file2.rename(temp_dir / "test.JPG")

        # Move second file (should get numbered suffix)
        with caplog.at_level(logging.WARNING):
            move_image(temp_dir / "test.JPG", test_date)

        # Check that both files exist with correct names
        original_path = temp_dir / "2023-12-25" / "JPEGs" / "test.JPG"
        duplicate_path = temp_dir / "2023-12-25" / "JPEGs" / "test (1).JPG"

        assert original_path.exists()
        assert duplicate_path.exists()

        # Check that warning was logged
        assert "Duplicate file detected" in caplog.text


class TestMoveImageSimple:
    """Test the move_image_simple function."""

    def test_move_image_simple_creates_structure(self, temp_dir: Path):
        """Test move_image_simple creates type-based structure."""
        # Create test files
        files = [
            ("test.JPG", "JPEGs"),
            ("raw.RAF", "Raw Files"),
            ("backup.DNG", "Raw Files"),
            ("video.MOV", "Videos"),
        ]

        for filename, expected_subdir in files:
            source_file = temp_dir / filename
            source_file.write_bytes(b"test data")

            move_image_simple(source_file, temp_dir)

            expected_path = temp_dir / expected_subdir / filename
            assert expected_path.exists()
            assert not source_file.exists()

    def test_move_image_simple_handles_duplicates(
        self,
        temp_dir: Path,
        caplog: LogCaptureFixture,
    ):
        """Test that move_image_simple handles duplicate files correctly."""
        # Create source files
        source_file1 = temp_dir / "test.JPG"
        source_file2 = temp_dir / "test_copy.JPG"
        source_file1.write_bytes(b"test data 1")
        source_file2.write_bytes(b"test data 2")

        # Move first file
        move_image_simple(source_file1, temp_dir)

        # Rename second file to match first file's name
        source_file2.rename(temp_dir / "test.JPG")

        # Move second file (should get numbered suffix)
        with caplog.at_level(logging.WARNING):
            move_image_simple(temp_dir / "test.JPG", temp_dir)

        # Check that both files exist with correct names
        original_path = temp_dir / "JPEGs" / "test.JPG"
        duplicate_path = temp_dir / "JPEGs" / "test (1).JPG"

        assert original_path.exists()
        assert duplicate_path.exists()

        # Check that warning was logged
        assert "Duplicate file detected" in caplog.text

    def test_move_image_simple_sets_permissions(self, temp_dir: Path):
        """Test that moved files have correct permissions."""
        source_file = temp_dir / "test.JPG"
        source_file.write_bytes(b"test data")

        move_image_simple(source_file, temp_dir)

        moved_file = temp_dir / "JPEGs" / "test.JPG"
        assert oct(moved_file.stat().st_mode)[-3:] == "644"
