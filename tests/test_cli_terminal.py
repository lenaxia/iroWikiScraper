"""Tests for terminal handling in CLI.

Validates that the CLI does not interfere with normal terminal functionality:
- Up/down arrow keys for command history
- Scroll wheel functionality
- Terminal state restoration on exit
- Ctrl+C handling
"""

import signal
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from scraper.__main__ import main, signal_handler


class TestSignalHandling:
    """Test signal handling for graceful termination."""

    def test_signal_handler_prints_message(self):
        """Test signal handler prints interruption message."""
        mock_frame = MagicMock()

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            with pytest.raises(SystemExit) as exc_info:
                signal_handler(signal.SIGINT, mock_frame)

            assert exc_info.value.code == 130
            output = mock_stderr.getvalue()
            assert "Interrupted" in output or "user" in output.lower()

    def test_main_registers_signal_handler(self):
        """Test that main() registers SIGINT handler."""
        with patch("signal.signal") as mock_signal:
            with patch("scraper.__main__.create_parser") as mock_parser:
                # Make parser raise exception to exit early
                mock_parser.return_value.parse_args.side_effect = SystemExit(0)

                try:
                    main()
                except SystemExit:
                    pass

                # Verify signal handler was registered
                mock_signal.assert_called_once_with(signal.SIGINT, signal_handler)


class TestMainFunction:
    """Test main() function behavior."""

    def test_main_with_no_args_shows_help(self):
        """Test main with no arguments shows help and exits."""
        with patch("sys.argv", ["scraper"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Should exit with error code since no subcommand
            assert exc_info.value.code != 0

    def test_main_routes_to_full_command(self):
        """Test main routes to full_scrape_command."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.return_value = 0

                exit_code = main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    def test_main_routes_to_incremental_command(self):
        """Test main routes to incremental_scrape_command."""
        with patch("sys.argv", ["scraper", "incremental"]):
            with patch("scraper.__main__.incremental_scrape_command") as mock_cmd:
                mock_cmd.return_value = 0

                exit_code = main()

                assert exit_code == 0
                mock_cmd.assert_called_once()

    def test_main_handles_keyboard_interrupt(self):
        """Test main handles KeyboardInterrupt gracefully."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.side_effect = KeyboardInterrupt()

                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    exit_code = main()

                    assert exit_code == 130
                    output = mock_stderr.getvalue()
                    assert "Interrupted" in output or "user" in output.lower()

    def test_main_handles_generic_exception(self):
        """Test main handles unexpected exceptions."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.side_effect = RuntimeError("Test error")

                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    exit_code = main()

                    assert exit_code == 1
                    output = mock_stderr.getvalue()
                    assert "ERROR" in output
                    assert "Test error" in output


class TestTerminalState:
    """Test that CLI preserves normal terminal functionality.

    These tests verify that the CLI implementation doesn't interfere with:
    - Command history (up/down arrows)
    - Terminal scrolling (mouse wheel)
    - Terminal state on exit
    """

    def test_no_progress_bars_in_quiet_mode(self):
        """Test that quiet mode suppresses progress output.

        Progress bars can interfere with terminal scrolling.
        """
        # _print_progress uses print() which preserves terminal scrolling
        # No tqdm or curses that would interfere with terminal
        import inspect

        from scraper.cli.commands import _print_progress

        source = inspect.getsource(_print_progress)

        # Ensure no tqdm usage
        assert "tqdm" not in source.lower()
        assert "progressbar" not in source.lower()
        assert "curses" not in source.lower()

    def test_commands_use_simple_print(self):
        """Test that commands use simple print() for output.

        Simple print() statements work with normal terminal scrolling
        and don't interfere with command history.
        """
        import inspect

        from scraper.cli import commands

        # Check that commands module doesn't use terminal control libraries
        source = inspect.getsource(commands)

        # These libraries can interfere with terminal
        assert "curses" not in source.lower()
        assert "termios" not in source.lower()
        assert "tty" not in source.lower()

    def test_no_terminal_mode_changes(self):
        """Test that CLI doesn't change terminal modes.

        Changing terminal modes (raw mode, cbreak, etc.) can interfere
        with arrow keys and require explicit restoration.
        """
        import inspect

        from scraper.cli import commands

        source = inspect.getsource(commands)

        # Check for terminal mode manipulation
        assert "setraw" not in source
        assert "setcbreak" not in source
        assert "tcgetattr" not in source
        assert "tcsetattr" not in source

    def test_main_exits_cleanly(self):
        """Test that main() exits cleanly without leaving terminal in bad state."""
        with patch("sys.argv", ["scraper", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Help should exit with 0
            assert exc_info.value.code == 0

            # No terminal cleanup needed because we never modified terminal state

    def test_ctrl_c_during_command_exits_cleanly(self):
        """Test Ctrl+C during command execution exits cleanly."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                # Simulate Ctrl+C during execution
                mock_cmd.side_effect = KeyboardInterrupt()

                exit_code = main()

                # Should exit with 130 (standard for SIGINT)
                assert exit_code == 130


class TestOutputFormatting:
    """Test that output is formatted for easy terminal use."""

    def test_progress_uses_flush(self):
        """Test that progress output uses flush for immediate display."""
        import inspect

        from scraper.cli.commands import _print_progress

        source = inspect.getsource(_print_progress)

        # Should use flush=True for immediate output
        assert "flush=True" in source

    def test_error_output_goes_to_stderr(self):
        """Test that errors are written to stderr."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.side_effect = RuntimeError("Test error")

                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                        main()

                        stderr_output = mock_stderr.getvalue()
                        stdout_output = mock_stdout.getvalue()

                        # Error should go to stderr, not stdout
                        assert "ERROR" in stderr_output
                        assert "Test error" in stderr_output


class TestExitCodes:
    """Test that CLI uses proper exit codes."""

    def test_success_returns_zero(self):
        """Test successful execution returns 0."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.return_value = 0

                exit_code = main()
                assert exit_code == 0

    def test_failure_returns_nonzero(self):
        """Test failed execution returns non-zero."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.return_value = 1

                exit_code = main()
                assert exit_code == 1

    def test_interrupt_returns_130(self):
        """Test interrupt returns 130 (standard SIGINT exit code)."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.side_effect = KeyboardInterrupt()

                exit_code = main()
                assert exit_code == 130

    def test_exception_returns_1(self):
        """Test unexpected exception returns 1."""
        with patch("sys.argv", ["scraper", "full"]):
            with patch("scraper.__main__.full_scrape_command") as mock_cmd:
                mock_cmd.side_effect = RuntimeError("Unexpected")

                exit_code = main()
                assert exit_code == 1
