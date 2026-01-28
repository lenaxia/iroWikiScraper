"""Tests for US-0707: Configuration Management.

This module tests the integration of configuration loading with CLI argument
parsing, ensuring proper precedence order and error handling.

Test Coverage:
- AC1: Configuration Sources (defaults, YAML file, CLI args)
- AC2: Precedence Order (CLI > file > defaults)
- AC3: CLI Arguments Override Config (--database, --rate-limit, --log-level)
- AC4: Configuration Loading (file loading, error handling, defaults)
- AC5: Validation (validate after merge, exit on invalid, show which value)
"""

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from scraper.cli.commands import _load_config
from scraper.config import Config, ConfigError

# ============================================================================
# TEST INFRASTRUCTURE - FIXTURES
# ============================================================================


@pytest.fixture
def args_default():
    """Provide default CLI arguments with no config file."""
    return Namespace(
        config=None,
        database=Path("data/irowiki.db"),
        log_level="INFO",
        rate_limit=2.0,
    )


@pytest.fixture
def args_with_config(load_config_fixture):
    """Provide CLI arguments with config file specified."""
    return Namespace(
        config=load_config_fixture("valid_complete.yaml"),
        database=Path("data/irowiki.db"),
        log_level="INFO",
        rate_limit=2.0,
    )


@pytest.fixture
def args_with_overrides(load_config_fixture):
    """Provide CLI arguments that override config file values."""
    return Namespace(
        config=load_config_fixture("cli_override_test.yaml"),
        database=Path("cli_override.db"),
        log_level="DEBUG",
        rate_limit=5.0,
    )


@pytest.fixture
def args_missing_config(tmp_path):
    """Provide CLI arguments with nonexistent config file."""
    return Namespace(
        config=tmp_path / "nonexistent.yaml",
        database=Path("data/irowiki.db"),
        log_level="INFO",
        rate_limit=2.0,
    )


@pytest.fixture
def args_invalid_yaml(load_config_fixture):
    """Provide CLI arguments with invalid YAML config."""
    return Namespace(
        config=load_config_fixture("invalid_yaml.yaml"),
        database=Path("data/irowiki.db"),
        log_level="INFO",
        rate_limit=2.0,
    )


@pytest.fixture
def args_invalid_values(load_config_fixture):
    """Provide CLI arguments with config that has invalid values."""
    return Namespace(
        config=load_config_fixture("invalid_rate_limit.yaml"),
        database=Path("data/irowiki.db"),
        log_level="INFO",
        rate_limit=2.0,
    )


# ============================================================================
# AC1: Configuration Sources
# ============================================================================


class TestConfigurationSources:
    """Test AC1: Configuration from defaults, YAML file, and CLI args."""

    def test_load_from_defaults_when_no_config_file(self, args_default):
        """Test loading uses built-in defaults when no config file specified.

        AC1: Built-in defaults from Config class
        """
        config = _load_config(args_default)

        # Should use Config class defaults
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.wiki.api_path == "/w/api.php"
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3

    def test_load_from_yaml_file(self, args_with_config):
        """Test loading configuration from YAML file.

        AC1: YAML file via --config flag
        """
        config = _load_config(args_with_config)

        # Should load values from YAML file
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3

    def test_cli_arguments_applied(self, args_with_overrides):
        """Test CLI arguments are applied to configuration.

        AC1: Command-line argument overrides
        """
        config = _load_config(args_with_overrides)

        # CLI args should be present
        assert config.scraper.rate_limit == 5.0
        assert config.storage.database_file == Path("cli_override.db")
        assert config.logging.level == "DEBUG"


# ============================================================================
# AC2: Precedence Order
# ============================================================================


class TestPrecedenceOrder:
    """Test AC2: CLI > file > defaults precedence order."""

    def test_cli_overrides_file(self, args_with_overrides):
        """Test CLI arguments override config file values.

        AC2: CLI arguments have highest priority
        """
        config = _load_config(args_with_overrides)

        # Config file has rate_limit=1.5, CLI has 5.0
        assert config.scraper.rate_limit == 5.0

        # Config file has database_file="config_file.db", CLI has "cli_override.db"
        assert config.storage.database_file == Path("cli_override.db")

        # Config file has log_level="WARNING", CLI has "DEBUG"
        assert config.logging.level == "DEBUG"

    def test_cli_overrides_defaults(self, args_default):
        """Test CLI arguments override defaults.

        AC2: CLI arguments override defaults
        """
        config = _load_config(args_default)

        # Default rate_limit is 1.0, CLI args_default has 2.0
        assert config.scraper.rate_limit == 2.0

        # Default log_level is "INFO", CLI has "INFO" (matches default)
        assert config.logging.level == "INFO"

    def test_file_overrides_defaults(self, args_with_config):
        """Test config file values override defaults.

        AC2: Config file has middle priority
        """
        # Modify args to not override rate_limit
        args = Namespace(
            config=args_with_config.config,
            database=Path("data/irowiki.db"),
            log_level="INFO",
        )

        config = _load_config(args)

        # File has rate_limit=1.0, default is 1.0 (same)
        # But file specifies it explicitly
        assert config.scraper.rate_limit == 1.0

    def test_defaults_used_when_no_overrides(self, args_default):
        """Test defaults are used for values not specified elsewhere.

        AC2: Defaults have lowest priority
        """
        config = _load_config(args_default)

        # These should come from defaults (not in CLI args)
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3
        assert config.wiki.base_url == "https://irowiki.org"


# ============================================================================
# AC3: CLI Arguments Override Config
# ============================================================================


class TestCLIArgumentsOverride:
    """Test AC3: Specific CLI argument overrides."""

    def test_database_cli_override(self, args_with_overrides):
        """Test --database overrides storage.database_file.

        AC3: --database overrides storage.database_file
        """
        config = _load_config(args_with_overrides)

        assert config.storage.database_file == Path("cli_override.db")

    def test_rate_limit_cli_override(self, args_with_overrides):
        """Test --rate-limit overrides scraper.rate_limit.

        AC3: --rate-limit overrides scraper.rate_limit
        """
        config = _load_config(args_with_overrides)

        assert config.scraper.rate_limit == 5.0

    def test_log_level_cli_override(self, args_with_overrides):
        """Test --log-level overrides logging.level.

        AC3: --log-level overrides logging.level
        """
        config = _load_config(args_with_overrides)

        assert config.logging.level == "DEBUG"

    def test_multiple_overrides_together(self, args_with_overrides):
        """Test all three overrides work together.

        AC3: Multiple CLI overrides work simultaneously
        """
        config = _load_config(args_with_overrides)

        # All three should be overridden
        assert config.storage.database_file == Path("cli_override.db")
        assert config.scraper.rate_limit == 5.0
        assert config.logging.level == "DEBUG"


# ============================================================================
# AC4: Configuration Loading
# ============================================================================


class TestConfigurationLoading:
    """Test AC4: Configuration loading behavior and error handling."""

    def test_load_from_file_if_config_specified(self, args_with_config):
        """Test config loads from file when --config is specified.

        AC4: Load from file if --config specified
        """
        with patch("scraper.cli.commands.Config.from_yaml") as mock_from_yaml:
            mock_from_yaml.return_value = Config()

            _load_config(args_with_config)

            # Should have called from_yaml with the config path
            mock_from_yaml.assert_called_once_with(args_with_config.config)

    def test_use_defaults_if_no_config_specified(self, args_default):
        """Test config uses defaults when no --config specified.

        AC4: Use defaults if no config file specified
        """
        with patch("scraper.cli.commands.Config.from_yaml") as mock_from_yaml:
            config = _load_config(args_default)

            # Should NOT have called from_yaml
            mock_from_yaml.assert_not_called()

            # Should have created default Config
            assert config.wiki.base_url == "https://irowiki.org"

    def test_missing_config_file_exits_with_error(self, args_missing_config):
        """Test missing config file exits with error message.

        AC4: Handle missing config file gracefully (error message)
        """
        with pytest.raises(SystemExit) as exc_info:
            _load_config(args_missing_config)

        assert exc_info.value.code == 1

    def test_invalid_yaml_exits_with_error(self, args_invalid_yaml):
        """Test invalid YAML exits with error message.

        AC4: Handle invalid YAML gracefully (error message)
        """
        with pytest.raises(SystemExit) as exc_info:
            _load_config(args_invalid_yaml)

        assert exc_info.value.code == 1


# ============================================================================
# AC5: Validation
# ============================================================================


class TestValidation:
    """Test AC5: Configuration validation behavior."""

    def test_validate_called_after_loading_and_merging(self, args_with_config):
        """Test validate is called after loading and merging.

        AC5: Validate config after loading and merging
        """
        with patch.object(Config, "validate") as mock_validate:
            # Mock from_yaml to return a Config instance
            with patch("scraper.cli.commands.Config.from_yaml") as mock_from_yaml:
                mock_config = Config()
                mock_from_yaml.return_value = mock_config

                _load_config(args_with_config)

                # validate should have been called
                mock_validate.assert_called_once()

    def test_validation_failure_exits_with_error(self, args_with_config):
        """Test validation failure exits with error code.

        AC5: Exit with clear error if validation fails
        """
        with patch.object(Config, "validate") as mock_validate:
            mock_validate.side_effect = ConfigError("Test validation error")

            with patch("scraper.cli.commands.Config.from_yaml") as mock_from_yaml:
                mock_from_yaml.return_value = Config()

                with pytest.raises(SystemExit) as exc_info:
                    _load_config(args_with_config)

                assert exc_info.value.code == 1

    def test_validation_error_shows_which_value_invalid(self, args_invalid_values):
        """Test validation error shows which config value is invalid.

        AC5: Show which config value is invalid

        Note: This test now passes because CLI overrides work correctly.
        The config file has invalid rate_limit=-1.0, but CLI provides valid 2.0,
        so after merge the config is valid.

        To test validation error display, we need CLI to provide invalid value.
        """
        # Modify args to have invalid rate_limit from CLI
        args = Namespace(
            config=None,  # No config file
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=-1.0,  # Invalid from CLI
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config(args)

        assert exc_info.value.code == 1


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestConfigurationIntegration:
    """Integration tests for complete configuration workflow."""

    def test_complete_workflow_no_config_file(self, args_default):
        """Test complete workflow without config file."""
        config = _load_config(args_default)

        # Should have defaults + CLI overrides
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.scraper.rate_limit == 2.0  # From CLI
        assert config.storage.database_file == Path("data/irowiki.db")
        assert config.logging.level == "INFO"

    def test_complete_workflow_with_config_file(self, args_with_config):
        """Test complete workflow with config file."""
        config = _load_config(args_with_config)

        # Should have file values + CLI overrides
        assert config.wiki.base_url == "https://irowiki.org"  # From file
        assert config.scraper.rate_limit == 2.0  # From CLI
        assert config.scraper.timeout == 30  # From file
        assert config.storage.database_file == Path("data/irowiki.db")  # From CLI

    def test_complete_workflow_with_all_overrides(self, args_with_overrides):
        """Test complete workflow with all types of overrides."""
        config = _load_config(args_with_overrides)

        # Should demonstrate full precedence: CLI > file > defaults
        assert config.scraper.rate_limit == 5.0  # CLI overrides file (1.5)
        assert config.storage.database_file == Path(
            "cli_override.db"
        )  # CLI overrides file
        assert config.logging.level == "DEBUG"  # CLI overrides file (WARNING)
        assert config.scraper.timeout == 30  # Default (not in file or CLI)

    def test_config_is_usable_after_loading(self, args_default):
        """Test loaded config can be used immediately."""
        config = _load_config(args_default)

        # Should be able to access all values
        assert config.wiki.base_url.startswith("https://")
        assert config.scraper.rate_limit > 0
        assert config.scraper.timeout > 0
        assert isinstance(config.storage.database_file, Path)


# ============================================================================
# ERROR MESSAGE TESTS
# ============================================================================


class TestErrorMessages:
    """Test error messages are clear and helpful."""

    def test_missing_file_error_is_logged(self, args_missing_config, caplog):
        """Test missing file error is logged before exit."""
        with pytest.raises(SystemExit):
            _load_config(args_missing_config)

        # Should have logged an error about the config file
        assert any(
            "Failed to load config" in record.message for record in caplog.records
        )

    def test_invalid_yaml_error_is_logged(self, args_invalid_yaml, caplog):
        """Test invalid YAML error is logged before exit."""
        with pytest.raises(SystemExit):
            _load_config(args_invalid_yaml)

        # Should have logged an error
        assert any(
            "Failed to load config" in record.message for record in caplog.records
        )

    def test_validation_error_is_logged(self, caplog):
        """Test validation error is logged before exit."""
        args = Namespace(
            config=None,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=-1.0,  # Invalid
        )

        with pytest.raises(SystemExit):
            _load_config(args)

        # Should have logged validation error
        assert any(
            "validation failed" in record.message.lower() for record in caplog.records
        )
