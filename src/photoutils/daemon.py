"""Run a watchdog daemon to make changes when files change."""

import logging
import os
from datetime import datetime
from pathlib import Path

from exiftool import ExifToolHelper

# from PIL import ExifTags, Image, UnidentifiedImageError
from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

lg = logging.getLogger(__name__)

type Exif = dict[str, str]


FILE_TYPES = {".RAF": "Raw Files", ".JPG": "JPEGs", ".MOV": "Videos"}


# TODO: Use a queue in parallel
class FileAdded(FileSystemEventHandler):
    def __init__(self, root: Path) -> None:
        self.root = root

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        # Ignore directories
        if event.is_directory:
            return

        # Handle bytes-like inputs
        if isinstance(event.src_path, (bytes, bytearray, memoryview)):
            event.src_path = bytes(event.src_path).decode("utf-8")
        path = Path(event.src_path)

        # Read the file, create the structure, and move the file.
        # TODO: Make this better, considering multiple exif tags
        with ExifToolHelper() as et:
            tags: list[Exif] = et.get_tags([event.src_path], "EXIF:DateTimeOriginal")  # type: ignore
            date_str = tags[0]["EXIF:DateTimeOriginal"].strip().split()[0]
            img_date = datetime.strptime(date_str, "%Y:%m:%d").date()

        dest = self.root / str(img_date) / FILE_TYPES[path.suffix.upper()]
        dest.mkdir(parents=True, exist_ok=True)
        os.rename(path, dest / path.name)
        os.chmod(dest / path.name, mode=0o644)

        # Todo... parallelize/multithread
        # Report/catch errors

        # try:
        #     with Image.open(path) as img:
        #         exif = img.getexif()
        #         print([ExifTags.TAGS[k] for k in exif])
        # except UnidentifiedImageError:
        #     lg.error(f"PIL could not read image: {path}")
        #     return
        # except FileNotFoundError:
        #     lg.error(f"File not found: {path}")
        #     return


def watch_dir(target: Path) -> None:
    observer = Observer()
    observer.schedule(FileAdded(target), str(target.absolute()), recursive=False)
    observer.start()

    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()
