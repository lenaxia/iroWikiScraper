"""Tests for CLI argument parsing.

Tests US-0702 acceptance criteria for argument parsing functionality.
"""

from pathlib import Path

import pytest

from scraper.cli.args import create_parser


class TestParserCreation:
    """Test parser creation and basic structure."""

    def test_create_parser_returns_parser(self):
        """Test that create_parser returns an ArgumentParser."""
        parser = create_parser()
        assert parser is not None
        assert hasattr(parser, "parse_args")

    def test_parser_has_correct_prog_name(self):
        """Test parser has correct program name."""
        parser = create_parser()
        assert parser.prog == "scraper"

    def test_parser_has_description(self):
        """Test parser has a description."""
        parser = create_parser()
        assert parser.description is not None
        assert "iRO Wiki Scraper" in parser.description

    def test_parser_has_epilog(self):
        """Test parser has help epilog."""
        parser = create_parser()
        assert parser.epilog is not None
        assert "github.com" in parser.epilog.lower()


class TestGlobalArguments:
    """Test global command-line arguments."""

    def test_config_argument(self):
        """Test --config argument."""
        parser = create_parser()
        args = parser.parse_args(["--config", "test.yaml", "full"])
        assert args.config == Path("test.yaml")

    def test_config_argument_is_optional(self):
        """Test --config is optional."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.config is None

    def test_database_argument(self):
        """Test --database argument."""
        parser = create_parser()
        args = parser.parse_args(["--database", "wiki.db", "full"])
        assert args.database == Path("wiki.db")

    def test_database_argument_is_optional(self):
        """Test --database is optional."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.database is None

    def test_log_level_argument(self):
        """Test --log-level argument."""
        parser = create_parser()
        args = parser.parse_args(["--log-level", "DEBUG", "full"])
        assert args.log_level == "DEBUG"

    def test_log_level_has_default(self):
        """Test --log-level has default value."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.log_level == "INFO"

    def test_log_level_choices(self):
        """Test --log-level validates choices."""
        parser = create_parser()

        # Valid choices should work
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            args = parser.parse_args(["--log-level", level, "full"])
            assert args.log_level == level

        # Invalid choice should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["--log-level", "INVALID", "full"])

    def test_quiet_argument(self):
        """Test --quiet flag."""
        parser = create_parser()
        args = parser.parse_args(["--quiet", "full"])
        assert args.quiet is True

    def test_quiet_default_is_false(self):
        """Test --quiet defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.quiet is False


class TestSubcommands:
    """Test subcommand structure."""

    def test_subcommand_is_required(self):
        """Test that a subcommand must be specified."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_full_subcommand_exists(self):
        """Test 'full' subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.command == "full"

    def test_incremental_subcommand_exists(self):
        """Test 'incremental' subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(["incremental"])
        assert args.command == "incremental"

    def test_invalid_subcommand_rejected(self):
        """Test invalid subcommand is rejected."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["invalid"])


class TestFullScrapeArguments:
    """Test arguments for 'full' subcommand."""

    def test_namespace_argument(self):
        """Test --namespace argument accepts multiple values."""
        parser = create_parser()
        args = parser.parse_args(["full", "--namespace", "0", "4", "6"])
        assert args.namespace == [0, 4, 6]

    def test_namespace_is_optional(self):
        """Test --namespace is optional."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.namespace is None

    def test_namespace_single_value(self):
        """Test --namespace with single value."""
        parser = create_parser()
        args = parser.parse_args(["full", "--namespace", "0"])
        assert args.namespace == [0]

    def test_rate_limit_argument(self):
        """Test --rate-limit argument."""
        parser = create_parser()
        args = parser.parse_args(["full", "--rate-limit", "1.5"])
        assert args.rate_limit == 1.5

    def test_rate_limit_has_default(self):
        """Test --rate-limit has default value."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.rate_limit == 2.0

    def test_force_flag(self):
        """Test --force flag."""
        parser = create_parser()
        args = parser.parse_args(["full", "--force"])
        assert args.force is True

    def test_force_default_is_false(self):
        """Test --force defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.force is False

    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        parser = create_parser()
        args = parser.parse_args(["full", "--dry-run"])
        assert args.dry_run is True

    def test_dry_run_default_is_false(self):
        """Test --dry-run defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["full"])
        assert args.dry_run is False

    def test_full_with_all_arguments(self):
        """Test full command with all arguments."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--config",
                "config.yaml",
                "--database",
                "wiki.db",
                "--log-level",
                "DEBUG",
                "--quiet",
                "full",
                "--namespace",
                "0",
                "4",
                "--rate-limit",
                "1.0",
                "--force",
                "--dry-run",
            ]
        )

        assert args.config == Path("config.yaml")
        assert args.database == Path("wiki.db")
        assert args.log_level == "DEBUG"
        assert args.quiet is True
        assert args.command == "full"
        assert args.namespace == [0, 4]
        assert args.rate_limit == 1.0
        assert args.force is True
        assert args.dry_run is True


class TestIncrementalScrapeArguments:
    """Test arguments for 'incremental' subcommand."""

    def test_since_argument(self):
        """Test --since argument."""
        parser = create_parser()
        args = parser.parse_args(["incremental", "--since", "2025-01-01T00:00:00Z"])
        assert args.since == "2025-01-01T00:00:00Z"

    def test_since_is_optional(self):
        """Test --since is optional."""
        parser = create_parser()
        args = parser.parse_args(["incremental"])
        assert args.since is None

    def test_namespace_argument(self):
        """Test --namespace argument for incremental."""
        parser = create_parser()
        args = parser.parse_args(["incremental", "--namespace", "0", "4"])
        assert args.namespace == [0, 4]

    def test_namespace_is_optional(self):
        """Test --namespace is optional for incremental."""
        parser = create_parser()
        args = parser.parse_args(["incremental"])
        assert args.namespace is None

    def test_rate_limit_argument(self):
        """Test --rate-limit argument for incremental."""
        parser = create_parser()
        args = parser.parse_args(["incremental", "--rate-limit", "3.0"])
        assert args.rate_limit == 3.0

    def test_rate_limit_has_default(self):
        """Test --rate-limit has default for incremental."""
        parser = create_parser()
        args = parser.parse_args(["incremental"])
        assert args.rate_limit == 2.0

    def test_incremental_with_all_arguments(self):
        """Test incremental command with all arguments."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--config",
                "config.yaml",
                "--database",
                "wiki.db",
                "--log-level",
                "WARNING",
                "--quiet",
                "incremental",
                "--since",
                "2025-01-01T00:00:00Z",
                "--namespace",
                "0",
                "4",
                "6",
                "--rate-limit",
                "1.5",
            ]
        )

        assert args.config == Path("config.yaml")
        assert args.database == Path("wiki.db")
        assert args.log_level == "WARNING"
        assert args.quiet is True
        assert args.command == "incremental"
        assert args.since == "2025-01-01T00:00:00Z"
        assert args.namespace == [0, 4, 6]
        assert args.rate_limit == 1.5


class TestHelpText:
    """Test help text generation."""

    def test_main_help_contains_description(self):
        """Test main help text contains description."""
        parser = create_parser()
        help_text = parser.format_help()
        assert "iRO Wiki Scraper" in help_text
        assert "Archive MediaWiki content" in help_text

    def test_main_help_lists_subcommands(self):
        """Test main help lists available subcommands."""
        parser = create_parser()
        help_text = parser.format_help()
        assert "full" in help_text
        assert "incremental" in help_text

    def test_full_help_has_description(self):
        """Test full subcommand has description."""
        parser = create_parser()
        # Get subparser for 'full'
        subparsers_actions = [
            action
            for action in parser._actions
            if isinstance(action, type(parser._subparsers))
        ]
        if subparsers_actions:
            subparser_container = subparsers_actions[0]
            full_parser = subparser_container.choices.get("full")
            if full_parser:
                help_text = full_parser.format_help()
                assert "scrape" in help_text.lower()

    def test_incremental_help_has_description(self):
        """Test incremental subcommand has description."""
        parser = create_parser()
        # Get subparser for 'incremental'
        subparsers_actions = [
            action
            for action in parser._actions
            if isinstance(action, type(parser._subparsers))
        ]
        if subparsers_actions:
            subparser_container = subparsers_actions[0]
            incr_parser = subparser_container.choices.get("incremental")
            if incr_parser:
                help_text = incr_parser.format_help()
                assert (
                    "incremental" in help_text.lower() or "update" in help_text.lower()
                )


class TestArgumentOrder:
    """Test that arguments can be specified in different orders."""

    def test_global_args_before_subcommand(self):
        """Test global arguments before subcommand."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--config",
                "config.yaml",
                "--log-level",
                "DEBUG",
                "full",
                "--namespace",
                "0",
            ]
        )
        assert args.config == Path("config.yaml")
        assert args.log_level == "DEBUG"
        assert args.command == "full"
        assert args.namespace == [0]

    def test_subcommand_args_after_subcommand(self):
        """Test subcommand arguments must come after subcommand."""
        parser = create_parser()
        # This should work
        args = parser.parse_args(
            [
                "full",
                "--namespace",
                "0",
            ]
        )
        assert args.namespace == [0]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_args_shows_error(self):
        """Test that no arguments shows error."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_only_global_args_shows_error(self):
        """Test that only global args without subcommand shows error."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--config", "config.yaml"])

    def test_negative_rate_limit_accepted(self):
        """Test that negative rate limit is accepted by parser (validation elsewhere)."""
        parser = create_parser()
        # Parser doesn't validate, just parses
        args = parser.parse_args(["full", "--rate-limit", "-1.0"])
        assert args.rate_limit == -1.0

    def test_namespace_with_negative_numbers(self):
        """Test namespace with negative numbers (parser accepts, validation elsewhere)."""
        parser = create_parser()
        args = parser.parse_args(["full", "--namespace", "-1"])
        assert args.namespace == [-1]

    def test_help_flag_exits(self):
        """Test that --help flag causes exit."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        # Help exits with code 0
        assert exc_info.value.code == 0

    def test_subcommand_help_exits(self):
        """Test that subcommand --help exits."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["full", "--help"])
        assert exc_info.value.code == 0
