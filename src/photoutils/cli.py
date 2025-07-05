"""Command-line interface for photoutils."""

import logging
from pathlib import Path
from typing import Annotated

from rich.logging import RichHandler
from typer import Argument as Arg
from typer import Option as Opt
from typer import Typer

from photoutils.cleanup import cleanup_directory
from photoutils.daemon import watch_dir

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
lg = logging.getLogger(__name__)


# Main app stub
app = Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Help with photo imports for post processing.",
    add_completion=False,
)

# Directory watcher daemon
daemon_app = Typer()
app.add_typer(daemon_app)

# Directory cleanup
cleanup_app = Typer()
app.add_typer(cleanup_app)

_TA = Annotated[Path, Arg(help="Directory to watch for changes.", show_default=False)]
_TV = Annotated[bool, Opt("--verbose", "-v", help="Show additional messages.")]
_TC = Annotated[Path, Arg(help="Directory to clean up.", show_default=False)]
_TD = Annotated[bool, Opt("--dry-run", "-d", help="Do not actually move files.")]


@daemon_app.command()
def daemon(target: _TA, verbose: _TV = False) -> None:
    """Run a watcher daemon to organize new photos."""
    logging.getLogger("photoutils").setLevel("DEBUG" if verbose else "INFO")
    watch_dir(target)


@cleanup_app.command()
def cleanup(target: _TC, dry_run: _TD = False, verbose: _TV = False) -> None:
    """Clean up a directory by organizing files into type-based subdirectories."""
    logging.getLogger("photoutils").setLevel("DEBUG" if verbose else "INFO")
    cleanup_directory(target, dry_run=dry_run)
