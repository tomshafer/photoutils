"""Run a watchdog daemon to make changes when files change."""

import logging
import os
import time
from datetime import date, datetime
from pathlib import Path
from queue import Queue
from threading import Thread

from exiftool import ExifToolHelper
from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

__all__ = ["watch_dir"]

lg = logging.getLogger(__name__)


def watch_dir(watched: Path) -> None:
    """Watch a directory for images to file."""
    if not watched.is_dir():
        raise NotADirectoryError(watched)

    queue = Queue[Path | None]()

    threads: list[Thread] = []
    for i in range(os.process_cpu_count() or 1):
        thread = Thread(target=run_thread, name=f"t-{i}", kwargs={"queue": queue})
        thread.start()
        threads.append(thread)

    observer = Observer()
    observer.schedule(FileAddedHandler(queue), path=str(watched))
    observer.start()

    try:
        while True:
            time.sleep(1)
    except (Exception, KeyboardInterrupt):
        observer.stop()
        for _ in threads:
            queue.put(None)

    observer.join()
    queue.join()
    for thread in threads:
        thread.join()


class NotADirectoryError(OSError):
    def __init__(self, p: Path) -> None:
        super().__init__(f"the path {p} is not a directory")


def run_thread(queue: Queue[Path | None]) -> None:
    """Run a thread to pull and process events from a queue."""
    while True:
        path = queue.get()

        # None is a sentinel for 'shut down'
        if path is None:
            queue.task_done()
            return

        lg.debug(f"Consuming path {path.name}")
        if path.suffix.lower()[1:] in ("raf", "jpg", "dng"):
            move_image(path, read_exif_date(path))
            queue.task_done()


class FileAddedHandler(FileSystemEventHandler):
    """Put file-creation events onto a queue."""

    def __init__(self, queue: Queue[Path | None]) -> None:
        self.queue = queue

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if isinstance(event, DirCreatedEvent):
            return

        file = src_path_to_path(event.src_path)
        self.queue.put(file)
        lg.debug(f"Putting path '{file.name}'")


def move_image(file: Path, img_date: date) -> None:
    """Move image-like files into a directory tree."""
    DIRS = {"RAF": "Raw Files", "DNG": "Raw Files", "JPG": "JPEGs"}
    dest = file.parent / str(img_date) / DIRS[file.suffix.upper()[1:]]
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
