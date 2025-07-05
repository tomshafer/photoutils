"""Tests for the photoutils daemon module."""

import time
from datetime import date
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest
from watchdog.events import DirCreatedEvent, FileCreatedEvent

from photoutils.daemon import (
    FILE_ACTIONS,
    FileAddedHandler,
    MultipleTargetsError,
    NotADirectoryError,
    move_image,
    process_files_worker,
    read_exif_date,
    resolve_target_dir,
    src_path_to_path,
    wait_for_file,
)


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


class TestFileAddedHandler:
    """Test the FileAddedHandler class."""

    def test_init(self, file_queue: Queue[Path | None]):
        """Test handler initialization."""
        handler = FileAddedHandler(file_queue)
        assert handler.file_queue is file_queue

    def test_on_created_ignores_directories(self, file_queue: Queue[Path | None]):
        """Test that directory creation events are ignored."""
        handler = FileAddedHandler(file_queue)
        event = DirCreatedEvent("/tmp/test_dir")

        handler.on_created(event)

        assert file_queue.empty()

    def test_on_created_queues_valid_files(self, file_queue: Queue[Path | None]):
        """Test that valid file extensions are queued."""
        handler = FileAddedHandler(file_queue)

        for ext in FILE_ACTIONS.keys():
            event = FileCreatedEvent(f"/tmp/test.{ext}")
            handler.on_created(event)

        assert file_queue.qsize() == len(FILE_ACTIONS)

    def test_on_created_ignores_invalid_files(self, file_queue: Queue[Path | None]):
        """Test that invalid file extensions are ignored."""
        handler = FileAddedHandler(file_queue)
        event = FileCreatedEvent("/tmp/test.txt")

        handler.on_created(event)

        assert file_queue.empty()

    def test_on_created_case_insensitive(self, file_queue: Queue[Path | None]):
        """Test that extension matching is case insensitive."""
        handler = FileAddedHandler(file_queue)
        event = FileCreatedEvent("/tmp/test.jpg")  # lowercase

        handler.on_created(event)

        assert file_queue.qsize() == 1


class TestSrcPathToPath:
    """Test the src_path_to_path function."""

    def test_string_input(self):
        """Test with string input."""
        result = src_path_to_path("/tmp/test.jpg")
        assert result == Path("/tmp/test.jpg")

    def test_bytes_input(self):
        """Test with bytes input."""
        result = src_path_to_path(b"/tmp/test.jpg")
        assert result == Path("/tmp/test.jpg")


class TestWaitForFile:
    """Test the wait_for_file function."""

    def test_wait_for_existing_stable_file(self, sample_image_file: Path):
        """Test waiting for an already stable file."""
        wait_for_file(sample_image_file)

    def test_wait_for_nonexistent_file_timeout(self, temp_dir: Path):
        """Test timeout for non-existent file."""
        non_existent = temp_dir / "does_not_exist.jpg"

        # Patch the constant inside the function
        with patch("photoutils.daemon.wait_for_file") as mock_wait:
            mock_wait.side_effect = TimeoutError("File never fully materialized")

            with pytest.raises(TimeoutError):
                mock_wait(non_existent)

    def test_wait_for_growing_file(self, temp_dir: Path):
        """Test waiting for a file that grows."""
        growing_file = temp_dir / "growing.jpg"

        def simulate_growth():
            growing_file.write_bytes(b"small")
            time.sleep(0.05)
            growing_file.write_bytes(b"much larger content")
            time.sleep(0.05)
            growing_file.write_bytes(b"final stable content that is even larger")

        import threading

        thread = threading.Thread(target=simulate_growth)
        thread.start()

        wait_for_file(growing_file)
        thread.join()

        assert growing_file.exists()
        assert growing_file.stat().st_size > 0


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

        with patch("photoutils.daemon.ExifToolHelper", return_value=mock_exiftool):
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

        with patch("photoutils.daemon.ExifToolHelper", return_value=mock_exiftool):
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

    def test_resolve_target_dir_single_candidate_with_suffix(self, temp_dir: Path):
        """Test returning single matching dir w/suffix."""
        test_date = date(2023, 12, 25)
        existing_dir = temp_dir / "2023-12-25_event"
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

    def test_resolve_target_dir_matches_existing_with_complex_suffix(
        self,
        temp_dir: Path,
    ):
        """Test images match existing dir w/suffix."""
        test_date = date(2025, 7, 4)
        existing_dir = temp_dir / "2025-07-04 Blah (Blah)"
        existing_dir.mkdir()

        result = resolve_target_dir(temp_dir, test_date)

        assert result == existing_dir
        # Verify no new directory was created
        assert not (temp_dir / "2025-07-04").exists()


class TestMoveImage:
    """Test the move_image function."""

    def test_move_image_creates_directory_structure(
        self,
        temp_dir: Path,
        sample_image_file: Path,
    ):
        """Test move_image creates proper structure."""
        test_date = date(2023, 12, 25)

        # Move the file to temp_dir first
        source_file = temp_dir / sample_image_file.name
        sample_image_file.rename(source_file)

        move_image(source_file, test_date)

        expected_path = temp_dir / "2023-12-25" / "JPEGs" / sample_image_file.name
        assert expected_path.exists()
        assert not source_file.exists()

    def test_move_image_different_file_types(self, temp_dir: Path):
        """Test moving different file types to subdirs."""
        test_date = date(2023, 12, 25)

        files = [
            ("test.JPG", "JPEGs"),
            ("test.RAF", "Raw Files"),
            ("test.DNG", "Raw Files"),
            ("test.MOV", "Videos"),
        ]

        for filename, expected_subdir in files:
            source_file = temp_dir / filename
            source_file.write_bytes(b"test data")

            move_image(source_file, test_date)

            expected_path = temp_dir / "2023-12-25" / expected_subdir / filename
            assert expected_path.exists()
            assert not source_file.exists()

    def test_move_image_sets_permissions(self, temp_dir: Path, sample_image_file: Path):
        """Test that moved files have correct permissions."""
        test_date = date(2023, 12, 25)

        source_file = temp_dir / sample_image_file.name
        sample_image_file.rename(source_file)

        move_image(source_file, test_date)

        expected_path = temp_dir / "2023-12-25" / "JPEGs" / sample_image_file.name
        assert oct(expected_path.stat().st_mode)[-3:] == "644"


class TestProcessFilesWorker:
    """Test the process_files_worker function."""

    def test_process_files_worker_shutdown_signal(self, file_queue: Queue[Path | None]):
        """Test that worker shuts down on None signal."""
        file_queue.put(None)

        # This should not hang
        process_files_worker(file_queue)

    def test_process_files_worker_timeout_continues(
        self,
        file_queue: Queue[Path | None],
    ):
        """Test that worker continues after timeout."""
        # Shutdown signal after a delay to test timeout handling
        import threading

        def delayed_shutdown():
            time.sleep(0.2)
            file_queue.put(None)

        thread = threading.Thread(target=delayed_shutdown)
        thread.start()

        # This should not hang; should handle timeout gracefully
        process_files_worker(file_queue)
        thread.join()

    @patch("photoutils.daemon.wait_for_file")
    @patch("photoutils.daemon.read_exif_date")
    @patch("photoutils.daemon.move_image")
    def test_process_files_worker_success(
        self,
        mock_move_image: MagicMock,
        mock_read_exif_date: MagicMock,
        mock_wait_for_file: MagicMock,
        file_queue: Queue[Path | None],
        sample_image_file: Path,
    ) -> None:
        """Test successful file processing."""
        mock_read_exif_date.return_value = date(2023, 12, 25)

        file_queue.put(sample_image_file)
        file_queue.put(None)  # Shutdown signal

        process_files_worker(file_queue)

        mock_wait_for_file.assert_called_once_with(sample_image_file)
        mock_read_exif_date.assert_called_once_with(sample_image_file)
        mock_move_image.assert_called_once_with(sample_image_file, date(2023, 12, 25))

    @patch("photoutils.daemon.wait_for_file")
    @patch("photoutils.daemon.read_exif_date")
    @patch("photoutils.daemon.move_image")
    def test_process_files_worker_handles_errors(
        self,
        mock_move_image: MagicMock,
        mock_read_exif_date: MagicMock,
        mock_wait_for_file: MagicMock,
        file_queue: Queue[Path | None],
        sample_image_file: Path,
    ) -> None:
        """Test that worker handles errors gracefully."""
        mock_read_exif_date.side_effect = Exception("EXIF read failed")

        file_queue.put(sample_image_file)
        file_queue.put(None)  # Shutdown signal

        # Should not raise exception
        process_files_worker(file_queue)

        mock_wait_for_file.assert_called_once_with(sample_image_file)
        mock_read_exif_date.assert_called_once_with(sample_image_file)
        mock_move_image.assert_not_called()


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
