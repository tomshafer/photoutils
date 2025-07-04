"""Run a watchdog daemon to make changes when files change."""

import logging
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Final

from exiftool import ExifToolHelper
from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

__all__ = ["watch_dir"]

lg = logging.getLogger(__name__)


# File extensions we allow operations against.
# EXT => Destination subdirectory
FILE_ACTIONS: Final[dict[str, str]] = {
    "RAF": "Raw Files",
    "DNG": "Raw Files",
    "JPG": "JPEGs",
    "MOV": "Videos",
}


def watch_dir(watched: Path) -> None:
    """Watch a directory for images to file."""
    if not watched.is_dir():
        raise NotADirectoryError(watched)

    observer = Observer()
    observer.schedule(FileAddedHandler(), path=str(watched))
    observer.start()

    try:
        while True:
            time.sleep(1)
    except (Exception, KeyboardInterrupt):
        observer.stop()
    finally:
        observer.join()


class NotADirectoryError(OSError):
    def __init__(self, p: Path) -> None:
        super().__init__(f"the path {p} is not a directory")


class MultipleTargetsError(FileExistsError):
    def __init__(self, parent: Path, candidates: list[Path]) -> None:
        super().__init__(f"{parent} has multiple potential children: {candidates}")


class FileAddedHandler(FileSystemEventHandler):
    """Put file-creation events onto a queue."""

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if isinstance(event, DirCreatedEvent):
            return

        file = src_path_to_path(event.src_path)
        if file.suffix.upper()[1:] in FILE_ACTIONS:
            wait_for_file(file)
            move_image(file, read_exif_date(file))


def wait_for_file(file: Path) -> None:
    """Wait for a file to materialize using adaptive polling."""
    MAX_TIMEOUT = 60  # seconds
    RAPID_POLL_INTERVAL = 0.1  # 100ms for first 5 seconds
    RAPID_POLL_DURATION = 5.0  # seconds
    SLOW_POLL_INTERVAL = 0.5  # 500ms after rapid phase
    STABILITY_CHECKS = 3  # consecutive stable size checks needed

    start_time = time.time()
    last_size, stable_count = 0, 0
    last_growth_time = start_time

    lg.debug(f"Waiting for file {file.name} to materialize")

    while True:
        elapsed = time.time() - start_time

        # Check timeout
        if elapsed > MAX_TIMEOUT:
            _msg = f"File {file.name} never fully materialized after {{MAX_TIMEOUT}} s"
            raise TimeoutError(_msg)

        # Wait for file existence
        if not file.exists():
            sleep_interval = (
                RAPID_POLL_INTERVAL
                if elapsed < RAPID_POLL_DURATION
                else SLOW_POLL_INTERVAL
            )
            time.sleep(sleep_interval)
            continue

        # Check file size
        cur_size = file.stat().st_size

        # File size is growing - reset stability counter
        if cur_size > last_size:
            stable_count = 0
            last_size = cur_size
            last_growth_time = time.time()
            lg.debug(f"File {file.name} size: {cur_size} bytes")

        # File size is stable
        elif cur_size > 0 and cur_size == last_size:
            stable_count += 1
            if stable_count >= STABILITY_CHECKS:
                lg.debug(f"File {file.name} stable after {elapsed:.2f}s")
                break

        # Determine polling interval based on recent growth
        time_since_growth = time.time() - last_growth_time
        if elapsed < RAPID_POLL_DURATION or time_since_growth < 1.0:
            sleep_interval = RAPID_POLL_INTERVAL
        else:
            # Exponential backoff for edge cases, but cap at reasonable interval
            backoff_factor = min(4, int(time_since_growth))
            sleep_interval = min(2.0, SLOW_POLL_INTERVAL * (2**backoff_factor))

        time.sleep(sleep_interval)


def move_image(file: Path, img_date: date) -> None:
    """Move image-like files into a directory tree."""
    target_dir = resolve_target_dir(file.parent, img_date)
    dest = target_dir / FILE_ACTIONS[file.suffix.upper()[1:]]
    dest.mkdir(parents=True, exist_ok=True)

    dest_file = dest / file.name
    lg.debug(f"Moving {file.name} to {dest_file.relative_to(file.parent)}")
    os.rename(file, dest_file)
    os.chmod(dest_file, mode=0o644)


def resolve_target_dir(path: Path, image_date: date) -> Path:
    """Resolve the destination for an image."""
    if not path.is_dir():
        raise NotADirectoryError(path)

    date_ = image_date.isoformat()
    candidates = [d for d in path.iterdir() if d.name.startswith(date_) and d.is_dir()]

    if not candidates:
        return path / date_

    if len(candidates) == 1:
        return candidates.pop()

    raise MultipleTargetsError(path, candidates)


def read_exif_date(file: Path) -> date:
    """Read the file, create the structure, and move the file."""
    # TODO: Make this better, considering multiple exif tags
    lg.debug(f"Reading EXIF date for {file.name}")
    with ExifToolHelper() as et:
        tags: list[dict[str, str]] = et.get_tags([file], "EXIF:DateTimeOriginal")  # type: ignore
        date_str = tags[0]["EXIF:DateTimeOriginal"].strip().split()[0]
        img_date = datetime.strptime(date_str, "%Y:%m:%d").date()
        lg.debug(f"EXIF date is {img_date}")
        return img_date


def src_path_to_path(src_path: bytes | str) -> Path:
    """Cast an event src_path to pathlib.Path."""
    src = src_path if isinstance(src_path, str) else bytes(src_path).decode()
    return Path(src)
