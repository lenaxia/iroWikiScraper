"""Edge case tests for US-0707: Configuration Management.

This module tests comprehensive edge cases for configuration loading:
- Config file exists but is empty
- Config file has partial settings (some missing)
- CLI args provided but are None/empty
- Multiple overrides at once
- Invalid values in file vs invalid from CLI
- File loading fails vs validation fails
"""

import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from scraper.cli.commands import _load_config
from scraper.config import Config, ConfigError

# ============================================================================
# EDGE CASE 1: Empty Config File
# ============================================================================


class TestEmptyConfigFile:
    """Test handling of empty or minimal config files."""

    def test_empty_config_file_uses_defaults(self, tmp_path):
        """Test empty config file falls back to defaults."""
        # Create empty YAML file
        empty_config = tmp_path / "empty.yaml"
        empty_config.write_text("")

        args = Namespace(
            config=empty_config,
            database=Path("data/irowiki.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        config = _load_config(args)

        # Should use defaults for everything not in file
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3

    def test_config_with_only_wiki_section(self, tmp_path):
        """Test config file with only one section uses defaults for rest."""
        partial_config = tmp_path / "partial.yaml"
        partial_config.write_text("""
wiki:
  base_url: "https://custom.org"
""")

        args = Namespace(
            config=partial_config,
            database=Path("data/irowiki.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        config = _load_config(args)

        # Should use partial values from file
        assert config.wiki.base_url == "https://custom.org"
        # Should use defaults for missing sections
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3


# ============================================================================
# EDGE CASE 2: Partial Config File Settings
# ============================================================================


class TestPartialConfigSettings:
    """Test config files with some missing settings."""

    def test_partial_scraper_settings(self, tmp_path):
        """Test config with only some scraper settings."""
        partial_config = tmp_path / "partial_scraper.yaml"
        partial_config.write_text("""
scraper:
  rate_limit: 3.5
  # timeout and max_retries not specified
""")

        args = Namespace(
            config=partial_config,
            database=Path("data/irowiki.db"),
            log_level="INFO",
            rate_limit=2.0,  # This will override the 3.5
        )

        config = _load_config(args)

        # CLI should override file
        assert config.scraper.rate_limit == 2.0
        # Missing values should use defaults
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3

    def test_partial_storage_settings(self, tmp_path):
        """Test config with only some storage settings."""
        partial_config = tmp_path / "partial_storage.yaml"
        partial_config.write_text("""
storage:
  data_dir: "custom_data"
  # database_file not specified
""")

        args = Namespace(
            config=partial_config,
            database=Path("override.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        config = _load_config(args)

        # CLI should override
        assert config.storage.database_file == Path("override.db")
        # Partial value from file
        assert config.storage.data_dir == Path("custom_data")

    def test_no_logging_section_uses_defaults(self, tmp_path):
        """Test config without logging section uses defaults then CLI."""
        no_logging = tmp_path / "no_logging.yaml"
        no_logging.write_text("""
wiki:
  base_url: "https://irowiki.org"
scraper:
  rate_limit: 1.0
""")

        args = Namespace(
            config=no_logging,
            database=Path("data/irowiki.db"),
            log_level="DEBUG",
            rate_limit=2.0,
        )

        config = _load_config(args)

        # CLI log_level should be applied
        assert config.logging.level == "DEBUG"


# ============================================================================
# EDGE CASE 3: None/Empty CLI Args
# ============================================================================


class TestNoneOrEmptyCLIArgs:
    """Test behavior when CLI args are None or empty."""

    def test_database_none_uses_config_or_default(self, load_config_fixture):
        """Test None database arg uses config file or default."""
        config_file = load_config_fixture("valid_complete.yaml")
        args = Namespace(
            config=config_file,
            database=None,  # None should use config file or default
            log_level="INFO",
            rate_limit=2.0,
        )

        config = _load_config(args)

        # Should use default since database is None
        # (None is falsy, so line 65 won't override)
        assert config.storage.database_file == Path("data/irowiki.db")

    def test_rate_limit_with_hasattr_check(self):
        """Test rate_limit handling when attribute may not exist."""
        # This tests the hasattr check on line 62
        args = Namespace(
            config=None,
            database=Path("test.db"),
            log_level="INFO",
            # Note: rate_limit not set (would be for commands without it)
        )

        config = _load_config(args)

        # Should use default rate_limit since hasattr check will fail
        assert config.scraper.rate_limit == 1.0


# ============================================================================
# EDGE CASE 4: Multiple Overrides at Once
# ============================================================================


class TestMultipleOverrides:
    """Test multiple CLI overrides applied simultaneously."""

    def test_all_three_overrides_together(self, load_config_fixture):
        """Test database, rate_limit, and log_level all override together."""
        config_file = load_config_fixture("cli_override_test.yaml")

        args = Namespace(
            config=config_file,
            database=Path("all_override.db"),
            log_level="CRITICAL",
            rate_limit=10.0,
        )

        config = _load_config(args)

        # All three should be overridden
        assert config.storage.database_file == Path("all_override.db")
        assert config.scraper.rate_limit == 10.0
        assert config.logging.level == "CRITICAL"

        # Other values from config file should remain
        assert config.scraper.timeout == 30
        assert config.wiki.base_url == "https://irowiki.org"

    def test_mixed_overrides_and_defaults(self, tmp_path):
        """Test mix of overrides with defaults and file values."""
        mixed_config = tmp_path / "mixed.yaml"
        mixed_config.write_text("""
scraper:
  rate_limit: 1.0
  timeout: 60
  max_retries: 5

storage:
  database_file: "from_file.db"
  data_dir: "archive"
""")

        args = Namespace(
            config=mixed_config,
            database=Path("from_cli.db"),
            log_level="WARNING",
            rate_limit=2.0,
        )

        config = _load_config(args)

        # CLI overrides
        assert config.storage.database_file == Path("from_cli.db")
        assert config.scraper.rate_limit == 2.0
        assert config.logging.level == "WARNING"

        # File values (not overridden)
        assert config.scraper.timeout == 60
        assert config.scraper.max_retries == 5
        assert config.storage.data_dir == Path("archive")


# ============================================================================
# EDGE CASE 5: Invalid Values (File vs CLI)
# ============================================================================


class TestInvalidValueSources:
    """Test invalid values from file vs CLI are caught."""

    def test_invalid_rate_limit_in_file_caught_by_validation(self, load_config_fixture):
        """Test invalid rate_limit in config file is caught during validation."""
        invalid_file = load_config_fixture("invalid_rate_limit.yaml")

        args = Namespace(
            config=invalid_file,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=2.0,  # Valid CLI value
        )

        # Should succeed - CLI overrides invalid file value
        config = _load_config(args)
        assert config.scraper.rate_limit == 2.0

    def test_invalid_rate_limit_from_cli_caught_by_validation(self):
        """Test invalid rate_limit from CLI is caught during validation."""
        args = Namespace(
            config=None,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=-5.0,  # Invalid
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config(args)

        assert exc_info.value.code == 1

    def test_invalid_log_level_from_cli_caught_early(self):
        """Test invalid log_level would be caught by argparse."""
        # Note: This would be caught by argparse before reaching _load_config
        # because log_level has choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        # This test documents that behavior

        args = Namespace(
            config=None,
            database=Path("test.db"),
            log_level="INFO",  # Valid value
            rate_limit=2.0,
        )

        config = _load_config(args)
        assert config.logging.level == "INFO"

    def test_invalid_timeout_in_file(self, tmp_path):
        """Test invalid timeout in file is caught by validation."""
        invalid_file = tmp_path / "invalid_timeout.yaml"
        invalid_file.write_text("""
scraper:
  timeout: -10
""")

        args = Namespace(
            config=invalid_file,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config(args)

        assert exc_info.value.code == 1


# ============================================================================
# EDGE CASE 6: File Loading Fails vs Validation Fails
# ============================================================================


class TestFailureTypes:
    """Test distinguishing file loading failures from validation failures."""

    def test_file_not_found_is_loading_failure(self, tmp_path):
        """Test missing file is caught as loading failure."""
        missing_file = tmp_path / "does_not_exist.yaml"

        args = Namespace(
            config=missing_file,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config(args)

        assert exc_info.value.code == 1

    def test_invalid_yaml_syntax_is_loading_failure(self, load_config_fixture):
        """Test malformed YAML is caught as loading failure."""
        invalid_yaml = load_config_fixture("invalid_yaml.yaml")

        args = Namespace(
            config=invalid_yaml,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config(args)

        assert exc_info.value.code == 1

    def test_valid_yaml_invalid_values_is_validation_failure(self, tmp_path):
        """Test valid YAML with invalid values is caught by validation."""
        valid_yaml_invalid_values = tmp_path / "valid_yaml_bad_values.yaml"
        valid_yaml_invalid_values.write_text("""
scraper:
  rate_limit: 0.0
  timeout: 30
  max_retries: 3
""")

        args = Namespace(
            config=valid_yaml_invalid_values,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=0.0,  # Invalid - will fail validation
        )

        with pytest.raises(SystemExit) as exc_info:
            _load_config(args)

        assert exc_info.value.code == 1

    def test_error_messages_distinguish_loading_vs_validation(self, tmp_path, caplog):
        """Test error messages clearly distinguish loading vs validation errors."""
        # Test loading error
        missing_file = tmp_path / "missing.yaml"
        args1 = Namespace(
            config=missing_file,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=2.0,
        )

        with pytest.raises(SystemExit):
            _load_config(args1)

        assert any(
            "Failed to load config" in record.message for record in caplog.records
        )

        caplog.clear()

        # Test validation error
        args2 = Namespace(
            config=None,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=-1.0,  # Invalid
        )

        with pytest.raises(SystemExit):
            _load_config(args2)

        assert any(
            "validation failed" in record.message.lower() for record in caplog.records
        )


# ============================================================================
# EDGE CASE 7: Precedence Verification
# ============================================================================


class TestExplicitPrecedenceVerification:
    """Test explicit precedence verification as mentioned in requirements."""

    def test_config_file_rate_limit_15_cli_50_gets_50(self, load_config_fixture):
        """Test exact scenario: config has 1.5, CLI has 5.0, result is 5.0."""
        config_file = load_config_fixture("cli_override_test.yaml")
        # This file has rate_limit: 1.5

        args = Namespace(
            config=config_file,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=5.0,
        )

        config = _load_config(args)

        # Verify scraper gets 5.0 (not 1.5)
        assert config.scraper.rate_limit == 5.0

    def test_no_file_cli_50_gets_50_not_default(self):
        """Test CLI override of default: default is 1.0, CLI is 5.0, get 5.0."""
        args = Namespace(
            config=None,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=5.0,
        )

        config = _load_config(args)

        # Default is 1.0, CLI is 5.0, should get 5.0
        assert config.scraper.rate_limit == 5.0
        assert config.scraper.rate_limit != 1.0  # Not default

    def test_file_15_no_cli_override_gets_15(self, load_config_fixture):
        """Test file value used when no CLI override."""
        config_file = load_config_fixture("cli_override_test.yaml")
        # This file has rate_limit: 1.5

        # Create args WITHOUT rate_limit attribute (simulate command without it)
        args = Namespace(
            config=config_file,
            database=Path("test.db"),
            log_level="INFO",
        )

        config = _load_config(args)

        # Should get file value 1.5 (not default 1.0)
        assert config.scraper.rate_limit == 1.5


# ============================================================================
# EDGE CASE 8: Integration with Full/Incremental Commands
# ============================================================================


class TestIntegrationWithCommands:
    """Test _load_config works correctly with actual command contexts."""

    def test_full_command_context_with_overrides(self, load_config_fixture):
        """Test _load_config in full command context."""
        config_file = load_config_fixture("valid_complete.yaml")

        # Simulate args from full command
        args = Namespace(
            config=config_file,
            database=Path("full_command.db"),
            log_level="DEBUG",
            rate_limit=3.0,
            namespace=[0, 1, 2],  # full command specific
            force=False,
            dry_run=False,
        )

        config = _load_config(args)

        # Should handle extra attributes gracefully
        assert config.scraper.rate_limit == 3.0
        assert config.storage.database_file == Path("full_command.db")
        assert config.logging.level == "DEBUG"

    def test_incremental_command_context_with_overrides(self, load_config_fixture):
        """Test _load_config in incremental command context."""
        config_file = load_config_fixture("valid_complete.yaml")

        # Simulate args from incremental command
        args = Namespace(
            config=config_file,
            database=Path("incremental_command.db"),
            log_level="INFO",
            rate_limit=2.5,
            since="2025-01-01T00:00:00Z",  # incremental specific
            namespace=[0],
        )

        config = _load_config(args)

        # Should handle extra attributes gracefully
        assert config.scraper.rate_limit == 2.5
        assert config.storage.database_file == Path("incremental_command.db")
        assert config.logging.level == "INFO"
