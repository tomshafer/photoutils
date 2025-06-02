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


class FileAddedHandler(FileSystemEventHandler):
    """Put file-creation events onto a queue."""

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if isinstance(event, DirCreatedEvent):
            return

        file = src_path_to_path(event.src_path)
        if file.suffix.upper()[1:] in FILE_ACTIONS:
            move_image(file, read_exif_date(file))


def move_image(file: Path, img_date: date) -> None:
    """Move image-like files into a directory tree."""
    dest = file.parent / str(img_date) / FILE_ACTIONS[file.suffix.upper()[1:]]
    dest.mkdir(parents=True, exist_ok=True)

    dest_file = dest / file.name
    lg.debug(f"Moving {file.name} to {dest_file.relative_to(file.parent)}")
    os.rename(file, dest_file)
    os.chmod(dest_file, mode=0o644)


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
