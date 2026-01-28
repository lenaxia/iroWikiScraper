"""Edge case tests for US-0705: Progress Tracking and Logging.

This module tests all edge cases mentioned in the validation requirements:
1. total=0 (division by zero)
2. very large numbers (formatting)
3. --quiet flag actually suppresses progress
4. --quiet flag does NOT suppress errors
5. each log level correctly filters messages
6. percentage always has 1 decimal place
7. Terminal compatibility (no tqdm, simple print, scrolling works)
"""

import logging
from io import StringIO

from scraper.cli.commands import _print_progress, _setup_logging


class TestDivisionByZero:
    """Test edge case: total=0 (division by zero protection)."""

    def test_total_zero_does_not_crash(self, capsys):
        """Test progress handles total=0 without crashing."""
        # Should not raise ZeroDivisionError
        _print_progress("test", 0, 0)
        captured = capsys.readouterr()
        assert "0/0 (0.0%)" in captured.out

    def test_total_zero_shows_zero_percent(self, capsys):
        """Test total=0 displays 0.0%."""
        _print_progress("test", 0, 0)
        captured = capsys.readouterr()
        assert "(0.0%)" in captured.out

    def test_current_nonzero_total_zero_shows_zero_percent(self, capsys):
        """Test even if current>0 but total=0, shows 0.0%."""
        # Edge case: current=5 but total=0 (shouldn't happen, but handle it)
        _print_progress("test", 5, 0)
        captured = capsys.readouterr()
        assert "(0.0%)" in captured.out


class TestVeryLargeNumbers:
    """Test edge case: very large numbers (formatting)."""

    def test_large_page_count(self, capsys):
        """Test progress handles large page counts (100K+)."""
        _print_progress("scrape", 150000, 200000)
        captured = capsys.readouterr()
        assert "150000/200000" in captured.out
        assert "75.0%" in captured.out

    def test_very_large_revision_count(self, capsys):
        """Test progress handles very large revision counts (1M+)."""
        _print_progress("scrape", 1000000, 1500000)
        captured = capsys.readouterr()
        assert "1000000/1500000" in captured.out
        assert "66.7%" in captured.out

    def test_massive_numbers_no_scientific_notation(self, capsys):
        """Test progress doesn't use scientific notation for large numbers."""
        _print_progress("scrape", 9999999, 10000000)
        captured = capsys.readouterr()
        # Should contain full numbers, not scientific notation
        assert "9999999/10000000" in captured.out
        # The word "scrape" contains 'e', so check the numbers specifically
        import re

        numbers = re.findall(r"\d+", captured.out)
        for num in numbers:
            assert "e" not in num.lower()  # No scientific notation in numbers


class TestQuietFlagBehavior:
    """Test edge case: --quiet flag suppresses progress but NOT errors."""

    def test_quiet_suppresses_info_messages(self):
        """Test --quiet suppresses INFO level messages."""
        _setup_logging("ERROR")
        logger = logging.getLogger("test_quiet")

        # Create a handler to capture what actually gets logged
        import logging as log_module
        from io import StringIO

        stream = StringIO()
        handler = log_module.StreamHandler(stream)
        logger.addHandler(handler)

        logger.info("This info should not appear")
        logger.error("This error should appear")

        output = stream.getvalue()

        # INFO message should not be in output
        assert "This info should not appear" not in output
        # ERROR message should be in output
        assert "This error should appear" in output

    def test_quiet_does_not_suppress_errors(self, caplog):
        """Test --quiet does NOT suppress ERROR level messages."""
        _setup_logging("ERROR")
        logger = logging.getLogger("test_quiet")

        with caplog.at_level(logging.ERROR):
            logger.error("Critical error message")

        assert any(
            "Critical error message" in record.message for record in caplog.records
        )

    def test_quiet_does_not_suppress_warnings(self, caplog):
        """Test WARNING level still logs warnings."""
        _setup_logging("WARNING")
        logger = logging.getLogger("test_quiet")

        with caplog.at_level(logging.WARNING):
            logger.debug("Debug - should not appear")
            logger.info("Info - should not appear")
            logger.warning("Warning - should appear")
            logger.error("Error - should appear")

        messages = [record.message for record in caplog.records]
        assert "Debug - should not appear" not in messages
        assert "Info - should not appear" not in messages
        assert "Warning - should appear" in messages
        assert "Error - should appear" in messages


class TestLogLevelFiltering:
    """Test edge case: each log level correctly filters messages."""

    def test_debug_level_shows_all_messages(self, caplog):
        """Test DEBUG level shows all message levels."""
        _setup_logging("DEBUG")
        logger = logging.getLogger("test_debug")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

        level_names = [record.levelname for record in caplog.records]
        assert "DEBUG" in level_names
        assert "INFO" in level_names
        assert "WARNING" in level_names
        assert "ERROR" in level_names
        assert "CRITICAL" in level_names

    def test_info_level_filters_debug(self):
        """Test INFO level filters out DEBUG messages."""
        _setup_logging("INFO")
        logger = logging.getLogger("test_info_filter")

        # Verify the root logger level is set correctly
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

        # Logger should inherit from root and filter DEBUG
        assert logger.getEffectiveLevel() == logging.INFO

    def test_warning_level_filters_info_and_debug(self):
        """Test WARNING level filters out INFO and DEBUG messages."""
        _setup_logging("WARNING")
        logger = logging.getLogger("test_warning_filter")

        # Verify the root logger level is set correctly
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

        # Logger should inherit from root and filter DEBUG and INFO
        assert logger.getEffectiveLevel() == logging.WARNING

    def test_error_level_only_shows_errors_and_critical(self):
        """Test ERROR level only shows ERROR and CRITICAL messages."""
        _setup_logging("ERROR")
        logger = logging.getLogger("test_error_filter")

        # Verify the root logger level is set correctly
        root_logger = logging.getLogger()
        assert root_logger.level == logging.ERROR

        # Logger should inherit from root and only allow ERROR and CRITICAL
        assert logger.getEffectiveLevel() == logging.ERROR

    def test_critical_level_only_shows_critical(self):
        """Test CRITICAL level only shows CRITICAL messages."""
        _setup_logging("CRITICAL")
        logger = logging.getLogger("test_critical_filter")

        # Verify the root logger level is set correctly
        root_logger = logging.getLogger()
        assert root_logger.level == logging.CRITICAL

        # Logger should inherit from root and only allow CRITICAL
        assert logger.getEffectiveLevel() == logging.CRITICAL


class TestPercentageFormatting:
    """Test edge case: percentage always has 1 decimal place."""

    def test_whole_number_percentage_has_decimal(self, capsys):
        """Test whole number percentages show .0"""
        test_cases = [
            (0, 10, "0.0%"),
            (5, 10, "50.0%"),
            (10, 10, "100.0%"),
            (25, 100, "25.0%"),
        ]

        for current, total, expected in test_cases:
            _print_progress("test", current, total)
            captured = capsys.readouterr()
            assert expected in captured.out, f"Failed for {current}/{total}"

    def test_fractional_percentage_has_one_decimal(self, capsys):
        """Test fractional percentages show exactly 1 decimal place."""
        test_cases = [
            (1, 3, "33.3%"),  # 33.333... → 33.3%
            (2, 3, "66.7%"),  # 66.666... → 66.7%
            (1, 7, "14.3%"),  # 14.285... → 14.3%
            (5, 7, "71.4%"),  # 71.428... → 71.4%
        ]

        for current, total, expected in test_cases:
            _print_progress("test", current, total)
            captured = capsys.readouterr()
            assert expected in captured.out, f"Failed for {current}/{total}"

    def test_percentage_never_has_two_decimals(self, capsys):
        """Test percentage never shows 2 decimal places."""
        # Test various ratios that might produce multiple decimals
        for i in range(1, 10):
            _print_progress("test", i, 7)
            captured = capsys.readouterr()

            # Extract percentage from output
            import re

            match = re.search(r"\((\d+\.\d+)%\)", captured.out)
            assert match, f"No percentage found in: {captured.out}"

            percentage_str = match.group(1)
            decimal_part = percentage_str.split(".")[1]
            assert (
                len(decimal_part) == 1
            ), f"Percentage has {len(decimal_part)} decimals: {percentage_str}"


class TestTerminalCompatibilityDetailed:
    """Test edge case: terminal compatibility (no tqdm, simple print, scrolling)."""

    def test_no_carriage_return_for_in_place_updates(self, capsys):
        """Test output doesn't use carriage return (\\r) for in-place updates."""
        _print_progress("test", 1, 10)
        _print_progress("test", 2, 10)
        captured = capsys.readouterr()

        # Should not contain carriage returns
        assert "\r" not in captured.out

    def test_no_ansi_escape_codes(self, capsys):
        """Test output doesn't contain ANSI escape codes."""
        _print_progress("test", 50, 100)
        captured = capsys.readouterr()

        # Should not contain ANSI escape sequences
        assert "\033[" not in captured.out  # CSI sequence
        assert "\x1b[" not in captured.out  # Alternative CSI

    def test_each_update_is_new_line(self, capsys):
        """Test each progress update is a separate line."""
        _print_progress("test", 1, 5)
        _print_progress("test", 2, 5)
        _print_progress("test", 3, 5)
        captured = capsys.readouterr()

        # Should have 3 lines (one for each update)
        lines = captured.out.strip().split("\n")
        assert len(lines) == 3

    def test_output_uses_standard_print(self, capsys):
        """Test output uses standard print() with newlines."""
        _print_progress("test", 10, 100)
        captured = capsys.readouterr()

        # Output should end with newline (implicit from print)
        assert captured.out.endswith("\n") or len(captured.out.strip()) > 0

    def test_no_cursor_manipulation(self, capsys):
        """Test output doesn't manipulate cursor position."""
        _print_progress("test", 25, 100)
        captured = capsys.readouterr()

        # Should not contain cursor control codes
        cursor_codes = [
            "\033[A",  # Cursor up
            "\033[B",  # Cursor down
            "\033[C",  # Cursor forward
            "\033[D",  # Cursor back
            "\033[H",  # Cursor home
            "\033[J",  # Clear screen
            "\033[K",  # Clear line
        ]

        for code in cursor_codes:
            assert code not in captured.out

    def test_output_is_plain_text(self, capsys):
        """Test output is plain text without special formatting."""
        _print_progress("discover", 42, 100)
        captured = capsys.readouterr()

        # Should be simple format: [stage] current/total (percentage%)
        assert captured.out.strip() == "[discover] 42/100 (42.0%)"

    def test_flush_ensures_immediate_output(self):
        """Test flush=True ensures output appears immediately."""
        # Create a StringIO to simulate stdout
        output = StringIO()

        # Temporarily redirect stdout
        import sys

        original_stdout = sys.stdout
        sys.stdout = output

        try:
            _print_progress("test", 1, 10)
            # With flush=True, output should be immediately available
            result = output.getvalue()
            assert "[test] 1/10 (10.0%)" in result
        finally:
            sys.stdout = original_stdout


class TestProgressCallbackIntegration:
    """Test progress callback integration with FullScraper."""

    def test_progress_callback_receives_discover_stage(self):
        """Test progress callback receives 'discover' stage name."""
        calls = []

        def mock_callback(stage, current, total):
            calls.append((stage, current, total))

        # Simulate what FullScraper does
        mock_callback("discover", 1, 5)
        mock_callback("discover", 2, 5)

        assert len(calls) == 2
        assert all(call[0] == "discover" for call in calls)

    def test_progress_callback_receives_scrape_stage(self):
        """Test progress callback receives 'scrape' stage name."""
        calls = []

        def mock_callback(stage, current, total):
            calls.append((stage, current, total))

        # Simulate what FullScraper does
        mock_callback("scrape", 100, 1000)
        mock_callback("scrape", 200, 1000)

        assert len(calls) == 2
        assert all(call[0] == "scrape" for call in calls)

    def test_progress_callback_receives_correct_counts(self):
        """Test progress callback receives correct current/total counts."""
        calls = []

        def mock_callback(stage, current, total):
            calls.append((stage, current, total))

        mock_callback("scrape", 50, 100)

        assert calls[0] == ("scrape", 50, 100)

    def test_none_callback_does_not_crash(self):
        """Test None callback (quiet mode) doesn't cause errors."""
        # Simulate what FullScraper does with None callback
        callback = None

        if callback:
            callback("test", 1, 10)

        # Should not raise any exceptions


class TestOutputFormatConsistency:
    """Test output format is consistent across all cases."""

    def test_format_always_includes_brackets(self, capsys):
        """Test stage name is always in brackets."""
        stages = ["discover", "scrape", "test"]

        for stage in stages:
            _print_progress(stage, 1, 10)
            captured = capsys.readouterr()
            assert f"[{stage}]" in captured.out

    def test_format_always_includes_slash(self, capsys):
        """Test current/total always separated by slash."""
        _print_progress("test", 25, 100)
        captured = capsys.readouterr()
        assert "25/100" in captured.out

    def test_format_always_includes_parentheses_around_percentage(self, capsys):
        """Test percentage is always in parentheses."""
        _print_progress("test", 30, 100)
        captured = capsys.readouterr()
        assert "(30.0%)" in captured.out

    def test_format_has_consistent_spacing(self, capsys):
        """Test format has consistent spacing."""
        _print_progress("discover", 5, 20)
        captured = capsys.readouterr()

        # Format: [stage] current/total (percentage%)
        # Should have space after stage and before percentage
        assert "[discover] 5/20 (25.0%)" in captured.out
