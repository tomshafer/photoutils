"""Core file processing logic shared between daemon and cleanup operations."""

import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Final

from exiftool import ExifToolHelper

__all__ = [
    "FILE_ACTIONS",
    "MultipleTargetsError",
    "NotADirectoryError",
    "move_image",
    "move_image_simple",
    "read_exif_date",
    "resolve_target_dir",
]

lg = logging.getLogger(__name__)


# File extensions we allow operations against.
# EXT => Destination subdirectory
FILE_ACTIONS: Final[dict[str, str]] = {
    "RAF": "Raw Files",
    "DNG": "Raw Files",
    "JPG": "JPEGs",
    "MOV": "Videos",
}


class NotADirectoryError(OSError):
    """Raised when a path is not a directory."""

    def __init__(self, p: Path) -> None:
        """Initialize with the problematic path."""
        super().__init__(f"the path {p} is not a directory")


class MultipleTargetsError(FileExistsError):
    """Multiple target directories match a date prefix."""

    def __init__(self, parent: Path, candidates: list[Path]) -> None:
        """Initialize with the parent path and candidate directories."""
        super().__init__(f"{parent} has multiple potential children: {candidates}")


def _get_unique_filename(dest_dir: Path, filename: str) -> Path:
    """Generate unique filename by adding numbered suffix."""
    dest_file = dest_dir / filename

    # If file doesn't exist, return original path
    if not dest_file.exists():
        return dest_file

    # Parse filename to extract base name and extension
    stem = dest_file.stem
    suffix = dest_file.suffix

    # Check if filename already has a numbered suffix like "photo (1)"
    match = re.search(r"^(.+)\s+\((\d+)\)$", stem)
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


def _move_file_to_dest(file: Path, dest_dir: Path, relative_to: Path) -> None:
    """Move a file to a destination while handling duplicates.

    Args:
        file: File to move.
        dest_dir: Destination (including file-type subdir).
        relative_to: Base directory for relative path logging.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = _get_unique_filename(dest_dir, file.name)

    # Log warning if duplicate was found
    if dest_file.name != file.name:
        lg.warning(
            f"Duplicate file detected: [yellow]{file.name}[/yellow] → "
            f"[yellow]{dest_file.name}[/yellow]"
        )

    lg.debug(
        f"Moving [cyan]{file.name}[/cyan] to "
        f"[magenta]{dest_file.relative_to(relative_to)}[/magenta]"
    )
    os.rename(file, dest_file)
    os.chmod(dest_file, mode=0o644)


def move_image(file: Path, img_date: date) -> None:
    """Move image-like files into a date-based directory tree."""
    target_dir = resolve_target_dir(file.parent, img_date)
    dest_dir = target_dir / FILE_ACTIONS[file.suffix.upper()[1:]]
    _move_file_to_dest(file, dest_dir, file.parent)


def move_image_simple(file: Path, base_dir: Path) -> None:
    """Move image-like files into type-based subdirectories."""
    dest_dir = base_dir / FILE_ACTIONS[file.suffix.upper()[1:]]
    _move_file_to_dest(file, dest_dir, base_dir)


def resolve_target_dir(path: Path, image_date: date) -> Path:
    """Resolve the destination for an image based on its date."""
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
    """Read the EXIF date from a file."""
    # TODO: Make this better, considering multiple exif tags
    lg.debug(f"Reading EXIF date for {file.name}")
    with ExifToolHelper() as et:
        tags: list[dict[str, str]] = et.get_tags([file], "EXIF:DateTimeOriginal")  # type: ignore
        date_str = tags[0]["EXIF:DateTimeOriginal"].strip().split()[0]
        img_date = datetime.strptime(date_str, "%Y:%m:%d").date()
        lg.debug(f"EXIF date is {img_date}")
        return img_date
