"""Command-line interface for photoutils."""

import logging
from pathlib import Path
from typing import Annotated

from typer import Argument as Arg
from typer import Option as Opt
from typer import Typer

from photoutils.daemon import watch_dir

logging.basicConfig(level=logging.WARNING)
lg = logging.getLogger(__name__)


# Main app stub
app = Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Help with photo imports for post processing.",
)

# Directory watcher daemon
daemon_app = Typer()
app.add_typer(daemon_app)

_TA = Annotated[Path, Arg(help="Directory to watch for changes.", show_default=False)]
_TV = Annotated[bool, Opt("--verbose", "-v", help="Show additional messages.")]


@daemon_app.command()
def daemon(target: _TA, verbose: _TV = False) -> None:
    """Run a watcher daemon to organize new photos."""
    logging.getLogger("photoutils").setLevel("DEBUG" if verbose else "INFO")
    watch_dir(target)
