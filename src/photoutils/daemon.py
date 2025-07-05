"""Run a watchdog daemon to make changes when files change."""

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from queue import Empty, Queue
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

    file_queue: Queue[Path | None] = Queue()
    max_workers = min(8, (os.cpu_count() or 1) * 2)

    lg.info(f"Starting daemon with [bold blue]{max_workers}[/bold blue] worker threads")
    lg.info(f"Watching directory: [bold magenta]{watched}[/bold magenta]")

    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="file-processor",
    ) as executor:
        # Start worker threads
        for _ in range(max_workers):
            executor.submit(process_files_worker, file_queue)

        # Start the observer
        observer = Observer()
        observer.schedule(FileAddedHandler(file_queue), path=str(watched))
        observer.start()

        # Wait for action
        try:
            while True:
                time.sleep(1)

        except (Exception, KeyboardInterrupt):
            lg.info("Shutdown requested, stopping observer...")
            observer.stop()

        finally:
            observer.join()

            # Signal workers to shut down
            for _ in range(max_workers):
                file_queue.put(None)

            lg.info("Shutdown complete")


class NotADirectoryError(OSError):
    def __init__(self, p: Path) -> None:
        super().__init__(f"the path {p} is not a directory")


class MultipleTargetsError(FileExistsError):
    def __init__(self, parent: Path, candidates: list[Path]) -> None:
        super().__init__(f"{parent} has multiple potential children: {candidates}")


def process_files_worker(file_queue: Queue[Path | None]) -> None:
    """Worker thread to process files from the queue."""
    while True:
        try:
            file_path = file_queue.get(timeout=1)

            # None is sentinel value for shutdown
            if file_path is None:
                lg.debug("Worker thread shutting down")
                file_queue.task_done()
                break

            lg.info(f"Processing file: [bold cyan]{file_path.name}[/bold cyan]")

            # Wait for file to be fully written
            wait_for_file(file_path)

            # Read EXIF and move file
            img_date = read_exif_date(file_path)
            move_image(file_path, img_date)

            lg.info(f"Successfully processed [bold green]{file_path.name}[/bold green]")

            file_queue.task_done()

        # Timeout from queue.get() - continue loop to check for shutdown
        except Empty:
            continue

        # Other uncaught exception
        except Exception as e:
            lg.error(f"Error processing file: [bold red]{e}[/bold red]")

            # Mark task as done even on error to prevent queue from hanging
            try:
                file_queue.task_done()
            except ValueError:
                # task_done() called more times than items in queue
                pass


class FileAddedHandler(FileSystemEventHandler):
    """Put file-creation events onto a queue."""

    def __init__(self, file_queue: Queue[Path | None]) -> None:
        self.file_queue = file_queue

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        if isinstance(event, DirCreatedEvent):
            return

        file = src_path_to_path(event.src_path)

        # Pre-filter files by extension before queuing
        if file.suffix.upper()[1:] in FILE_ACTIONS:
            self.file_queue.put(file)
            lg.debug(f"Queued file: [yellow]{file.name}[/yellow]")


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


def _get_unique_filename(dest_dir: Path, filename: str) -> Path:
    """Generate unique filename by adding numbered suffix if file exists."""
    dest_file = dest_dir / filename
    
    # If file doesn't exist, return original path
    if not dest_file.exists():
        return dest_file
    
    # Parse filename to extract base name and extension
    stem = dest_file.stem
    suffix = dest_file.suffix
    
    # Check if filename already has a numbered suffix like "photo (1)"
    match = re.search(r'^(.+)\s+\((\d+)\)$', stem)
    if match:
        base_name = match.group(1)
        start_num = int(match.group(2)) + 1
    else:
        base_name = stem
        start_num = 1
    
    # Find next available number
    counter = start_num
    while True:
        new_filename = f"{base_name} ({counter}){suffix}"
        new_dest_file = dest_dir / new_filename
        if not new_dest_file.exists():
            return new_dest_file
        counter += 1


def move_image(file: Path, img_date: date) -> None:
    """Move image-like files into a directory tree."""
    target_dir = resolve_target_dir(file.parent, img_date)
    dest = target_dir / FILE_ACTIONS[file.suffix.upper()[1:]]
    dest.mkdir(parents=True, exist_ok=True)

    dest_file = _get_unique_filename(dest, file.name)
    
    # Log warning if duplicate was found
    if dest_file.name != file.name:
        lg.warning(
            f"Duplicate file detected: [yellow]{file.name}[/yellow] → "
            f"[yellow]{dest_file.name}[/yellow]"
        )
    
    lg.debug(
        f"Moving [cyan]{file.name}[/cyan] to "
        f"[magenta]{dest_file.relative_to(file.parent)}[/magenta]"
    )
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
