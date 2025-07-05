"""Cleanup existing directories by organizing files into type-based subdirectories."""

import logging
from pathlib import Path

from photoutils.core import FILE_ACTIONS, NotADirectoryError, move_image_simple

__all__ = ["cleanup_directory"]

lg = logging.getLogger(__name__)


def cleanup_directory(target_dir: Path, dry_run: bool = False) -> None:
    """Clean up a directory by organizing files.

    Args:
        target_dir: Directory to clean up.
        dry_run: Only show what would be moved.

    """
    if not target_dir.is_dir():
        raise NotADirectoryError(target_dir)

    # Find all files with supported extensions
    files_to_move: list[Path] = []
    for ext in FILE_ACTIONS.keys():
        # Case-insensitive matching
        files_to_move.extend(target_dir.glob(f"*.{ext}"))
        files_to_move.extend(target_dir.glob(f"*.{ext.lower()}"))

    if not files_to_move:
        lg.info(f"No files to organize in [bold magenta]{target_dir}[/bold magenta]")
        return

    # Sort files for consistent processing order
    files_to_move.sort()

    lg.info(f"Found [bold blue]{len(files_to_move)}[/bold blue] files to organize")

    # Process each file
    for file in files_to_move:
        try:
            if dry_run:
                dest_subdir = FILE_ACTIONS[file.suffix.upper()[1:]]
                lg.info(
                    f"Would move [cyan]{file.name}[/cyan] to "
                    f"[magenta]{dest_subdir}/[/magenta]"
                )
            else:
                lg.info(f"Moving [cyan]{file.name}[/cyan]")
                move_image_simple(file, target_dir)
                lg.info(f"Successfully moved [bold green]{file.name}[/bold green]")

        except Exception as e:
            lg.error(f"Error processing [bold red]{file.name}[/bold red]: {e}")
            continue

    if dry_run:
        lg.info("[bold yellow]Dry run completed - no files were actually moved[/]")
    else:
        lg.info("[bold green]Cleanup completed[/bold green]")
