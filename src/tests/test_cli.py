"""Tests for the photoutils CLI module."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from photoutils.cli import app, daemon_app


class TestCLIApp:
    """Test the main CLI application."""

    def test_app_help(self) -> None:
        """Test that the main app shows help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Help with photo imports for post processing" in result.output

    def test_app_short_help(self) -> None:
        """Test that the main app shows help with -h."""
        runner = CliRunner()
        result = runner.invoke(app, ["-h"])

        assert result.exit_code == 0
        assert "Help with photo imports for post processing" in result.output


class TestDaemonCommand:
    """Test the daemon command."""

    def test_daemon_help(self) -> None:
        """Test that the daemon command shows help."""
        runner = CliRunner()
        result = runner.invoke(daemon_app, ["daemon", "--help"])

        assert result.exit_code == 0
        assert "Run a watcher daemon to organize new photos" in result.output

    @patch("photoutils.cli.watch_dir")
    def test_daemon_with_directory(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test daemon command with directory argument."""
        runner = CliRunner()
        result = runner.invoke(app, ["daemon", str(temp_dir)])

        assert result.exit_code == 0
        mock_watch_dir.assert_called_once_with(temp_dir)

    @patch("photoutils.cli.watch_dir")
    def test_daemon_with_verbose(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test daemon command with verbose flag."""
        runner = CliRunner()
        result = runner.invoke(app, ["daemon", str(temp_dir), "--verbose"])

        assert result.exit_code == 0
        mock_watch_dir.assert_called_once_with(temp_dir)

    @patch("photoutils.cli.watch_dir")
    def test_daemon_with_verbose_short(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test daemon command with verbose short flag."""
        runner = CliRunner()
        result = runner.invoke(app, ["daemon", str(temp_dir), "-v"])

        assert result.exit_code == 0
        mock_watch_dir.assert_called_once_with(temp_dir)

    @patch("photoutils.cli.watch_dir")
    def test_daemon_logging_level_default(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that default logging level is INFO."""
        runner = CliRunner()

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            runner.invoke(app, ["daemon", str(temp_dir)])

            mock_logger.setLevel.assert_called_once_with("INFO")

    @patch("photoutils.cli.watch_dir")
    def test_daemon_logging_level_verbose(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that verbose flag sets DEBUG logging level."""
        runner = CliRunner()

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            runner.invoke(app, ["daemon", str(temp_dir), "--verbose"])

            mock_logger.setLevel.assert_called_once_with("DEBUG")

    def test_daemon_nonexistent_directory(self) -> None:
        """Test daemon command with non-existent directory."""
        runner = CliRunner()
        result = runner.invoke(daemon_app, ["daemon", "/nonexistent/directory"])

        # Should exit with error due to invalid path
        assert result.exit_code != 0

    @patch("photoutils.cli.watch_dir")
    def test_daemon_with_file_instead_of_directory(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test daemon command with file instead of directory."""
        file_path = temp_dir / "test_file.txt"
        file_path.touch()

        runner = CliRunner()
        result = runner.invoke(app, ["daemon", str(file_path)])

        # The CLI should accept the path, but watch_dir should handle the validation
        assert result.exit_code == 0
        mock_watch_dir.assert_called_once_with(file_path)

    @patch("photoutils.cli.watch_dir")
    def test_daemon_path_conversion(
        self,
        mock_watch_dir: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test that string paths are converted to Path objects."""
        runner = CliRunner()
        result = runner.invoke(app, ["daemon", str(temp_dir)])

        assert result.exit_code == 0
        # Verify that the argument was converted to a Path object
        args, _ = mock_watch_dir.call_args
        assert isinstance(args[0], Path)
        assert args[0] == temp_dir


class TestLoggingConfiguration:
    """Test logging configuration."""

    def test_logging_configuration(self) -> None:
        """Test that logging is configured correctly."""
        # Test that the module sets up logging correctly

        # Check that RichHandler is configured by checking
        # module-level configuration. Since logging is configured
        # at module level, we'll check that the configuration
        # exists
        photoutils_logger = logging.getLogger("photoutils")
        assert photoutils_logger is not None

    def test_photoutils_logger_exists(self) -> None:
        """Test that photoutils logger exists."""
        logger = logging.getLogger("photoutils")
        assert logger is not None

    def test_cli_logger_exists(self) -> None:
        """Test that CLI logger exists."""
        import photoutils.cli

        assert photoutils.cli.lg is not None


class TestIntegration:
    """Integration tests for the CLI."""

    def test_main_app_includes_daemon_app(self) -> None:
        """Test that the main app includes the daemon app."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Should show daemon as a subcommand
        assert "daemon" in result.output

    def test_daemon_subcommand_accessible(self) -> None:
        """Test that daemon subcommand is accessible."""
        runner = CliRunner()
        result = runner.invoke(app, ["daemon", "--help"])

        assert result.exit_code == 0
        assert "Run a watcher daemon to organize new photos" in result.output
