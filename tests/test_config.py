"""Tests for configuration management."""

import logging
from pathlib import Path

import pytest

from scraper.config import Config, ConfigError

# ============================================================================
# TEST INFRASTRUCTURE - FIXTURES AND HELPERS
# ============================================================================


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """
    Create temporary directory for config files.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to temporary config directory
    """
    config_path = tmp_path / "config"
    config_path.mkdir(exist_ok=True)
    return config_path


@pytest.fixture
def valid_complete_config(load_config_fixture) -> Path:
    """Return path to valid complete config fixture."""
    return load_config_fixture("valid_complete.yaml")


@pytest.fixture
def valid_minimal_config(load_config_fixture) -> Path:
    """Return path to valid minimal config fixture."""
    return load_config_fixture("valid_minimal.yaml")


@pytest.fixture
def invalid_yaml_config(load_config_fixture) -> Path:
    """Return path to invalid YAML config fixture."""
    return load_config_fixture("invalid_yaml.yaml")


@pytest.fixture
def invalid_rate_limit_config(load_config_fixture) -> Path:
    """Return path to invalid rate_limit config fixture."""
    return load_config_fixture("invalid_rate_limit.yaml")


@pytest.fixture
def invalid_timeout_config(load_config_fixture) -> Path:
    """Return path to invalid timeout config fixture."""
    return load_config_fixture("invalid_timeout.yaml")


@pytest.fixture
def invalid_max_retries_config(load_config_fixture) -> Path:
    """Return path to invalid max_retries config fixture."""
    return load_config_fixture("invalid_max_retries.yaml")


@pytest.fixture
def invalid_log_level_config(load_config_fixture) -> Path:
    """Return path to invalid log_level config fixture."""
    return load_config_fixture("invalid_log_level.yaml")


@pytest.fixture
def empty_config(load_config_fixture) -> Path:
    """Return path to empty config fixture."""
    return load_config_fixture("empty.yaml")


# ============================================================================
# TEST CLASS 1: CONFIG INITIALIZATION AND DEFAULTS
# ============================================================================


class TestConfigInit:
    """Test config initialization and default values."""

    def test_default_config_has_correct_values(self):
        """Test default config has correct default values."""
        config = Config()

        # Wiki defaults
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.wiki.api_path == "/w/api.php"

        # Scraper defaults
        assert config.scraper.rate_limit == 1.0
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3
        assert "iROWikiArchiver" in config.scraper.user_agent

        # Storage defaults
        assert config.storage.data_dir == Path("data")
        assert config.storage.checkpoint_file == Path("data/.checkpoint.json")
        assert config.storage.database_file == Path("data/irowiki.db")

        # Logging defaults
        assert config.logging.level == "INFO"
        assert config.logging.log_file == Path("logs/scraper.log")
        assert "asctime" in config.logging.log_format

    def test_default_config_validates_successfully(self):
        """Test default config passes validation."""
        config = Config()
        config.validate()  # Should not raise


# ============================================================================
# TEST CLASS 2: LOADING FROM YAML
# ============================================================================


class TestConfigFromYAML:
    """Test loading config from YAML files."""

    def test_load_valid_complete_config(self, valid_complete_config: Path):
        """Test loading valid complete config file."""
        config = Config.from_yaml(valid_complete_config)

        # Wiki settings
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.wiki.api_path == "/w/api.php"

        # Scraper settings
        assert config.scraper.rate_limit == 1.0
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3
        assert (
            config.scraper.user_agent
            == "iROWikiArchiver/1.0 (github.com/user/repo; contact@example.com)"
        )

        # Storage settings
        assert config.storage.data_dir == Path("data")
        assert config.storage.checkpoint_file == Path("data/.checkpoint.json")
        assert config.storage.database_file == Path("data/irowiki.db")

        # Logging settings
        assert config.logging.level == "INFO"
        assert config.logging.log_file == Path("logs/scraper.log")
        assert "asctime" in config.logging.log_format

    def test_load_valid_minimal_config_uses_defaults(self, valid_minimal_config: Path):
        """Test loading minimal config uses defaults for missing fields."""
        config = Config.from_yaml(valid_minimal_config)

        # Specified values
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.scraper.rate_limit == 2.0

        # Default values for unspecified fields
        assert config.scraper.timeout == 30
        assert config.scraper.max_retries == 3
        assert config.storage.data_dir == Path("data")
        assert config.logging.level == "INFO"

    def test_load_nonexistent_file_raises_error(self, temp_config_dir: Path):
        """Test loading nonexistent file raises ConfigError."""
        nonexistent = temp_config_dir / "nonexistent.yaml"

        with pytest.raises(ConfigError, match="not found"):
            Config.from_yaml(nonexistent)

    def test_load_invalid_yaml_raises_error(self, invalid_yaml_config: Path):
        """Test loading invalid YAML raises ConfigError."""
        with pytest.raises(ConfigError, match="Failed to parse YAML"):
            Config.from_yaml(invalid_yaml_config)

    def test_load_empty_config_uses_all_defaults(self, empty_config: Path):
        """Test loading empty config file uses all default values."""
        config = Config.from_yaml(empty_config)

        # Should have all default values
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.scraper.rate_limit == 1.0
        assert config.storage.data_dir == Path("data")
        assert config.logging.level == "INFO"

    def test_paths_converted_to_path_objects(self, valid_complete_config: Path):
        """Test string paths are converted to Path objects."""
        config = Config.from_yaml(valid_complete_config)

        # All paths should be Path objects
        assert isinstance(config.storage.data_dir, Path)
        assert isinstance(config.storage.checkpoint_file, Path)
        assert isinstance(config.storage.database_file, Path)
        assert isinstance(config.logging.log_file, Path)

    def test_load_from_string_path(self, valid_complete_config: Path):
        """Test from_yaml accepts string path."""
        config = Config.from_yaml(str(valid_complete_config))

        assert config.wiki.base_url == "https://irowiki.org"

    def test_load_from_path_object(self, valid_complete_config: Path):
        """Test from_yaml accepts Path object."""
        config = Config.from_yaml(valid_complete_config)

        assert config.wiki.base_url == "https://irowiki.org"


# ============================================================================
# TEST CLASS 3: VALIDATION - POSITIVE CASES
# ============================================================================


class TestConfigValidationPositive:
    """Test config validation with valid configurations."""

    def test_validate_default_config(self):
        """Test validate succeeds with default config."""
        config = Config()
        config.validate()  # Should not raise

    def test_validate_custom_valid_values(self):
        """Test validate succeeds with custom valid values."""
        config = Config()
        config.scraper.rate_limit = 2.5
        config.scraper.timeout = 60
        config.scraper.max_retries = 5
        config.logging.level = "DEBUG"

        config.validate()  # Should not raise

    def test_validate_all_log_levels(self):
        """Test validate accepts all valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = Config()
            config.logging.level = level
            config.validate()  # Should not raise

    def test_validate_boundary_values(self):
        """Test validate accepts boundary values."""
        config = Config()
        config.scraper.rate_limit = 0.01  # Very slow
        config.scraper.timeout = 1  # Minimum timeout
        config.scraper.max_retries = 0  # No retries

        config.validate()  # Should not raise


# ============================================================================
# TEST CLASS 4: VALIDATION - NEGATIVE CASES
# ============================================================================


class TestConfigValidationNegative:
    """Test config validation with invalid configurations."""

    def test_validate_negative_rate_limit(self, invalid_rate_limit_config: Path):
        """Test validate rejects negative rate_limit."""
        with pytest.raises(ConfigError, match="rate_limit must be positive"):
            Config.from_yaml(invalid_rate_limit_config)

    def test_validate_zero_rate_limit(self):
        """Test validate rejects zero rate_limit."""
        config = Config()
        config.scraper.rate_limit = 0.0

        with pytest.raises(ConfigError, match="rate_limit must be positive"):
            config.validate()

    def test_validate_negative_timeout(self):
        """Test validate rejects negative timeout."""
        config = Config()
        config.scraper.timeout = -10

        with pytest.raises(ConfigError, match="timeout must be positive"):
            config.validate()

    def test_validate_zero_timeout(self, invalid_timeout_config: Path):
        """Test validate rejects zero timeout."""
        with pytest.raises(ConfigError, match="timeout must be positive"):
            Config.from_yaml(invalid_timeout_config)

    def test_validate_negative_max_retries(self, invalid_max_retries_config: Path):
        """Test validate rejects negative max_retries."""
        with pytest.raises(ConfigError, match="max_retries must be non-negative"):
            Config.from_yaml(invalid_max_retries_config)

    def test_validate_invalid_log_level(self, invalid_log_level_config: Path):
        """Test validate rejects invalid log level."""
        with pytest.raises(ConfigError, match="Invalid log level"):
            Config.from_yaml(invalid_log_level_config)

    def test_validate_empty_base_url(self):
        """Test validate rejects empty base_url."""
        config = Config()
        config.wiki.base_url = ""

        with pytest.raises(ConfigError, match="base_url cannot be empty"):
            config.validate()

    def test_validate_empty_user_agent(self):
        """Test validate rejects empty user_agent."""
        config = Config()
        config.scraper.user_agent = ""

        with pytest.raises(ConfigError, match="user_agent cannot be empty"):
            config.validate()


# ============================================================================
# TEST CLASS 5: NESTED STRUCTURE
# ============================================================================


class TestConfigNestedStructure:
    """Test config nested structure with dataclasses."""

    def test_wiki_section_accessible(self):
        """Test wiki section is accessible as nested object."""
        config = Config()

        assert hasattr(config, "wiki")
        assert hasattr(config.wiki, "base_url")
        assert hasattr(config.wiki, "api_path")

    def test_scraper_section_accessible(self):
        """Test scraper section is accessible as nested object."""
        config = Config()

        assert hasattr(config, "scraper")
        assert hasattr(config.scraper, "rate_limit")
        assert hasattr(config.scraper, "timeout")
        assert hasattr(config.scraper, "max_retries")
        assert hasattr(config.scraper, "user_agent")

    def test_storage_section_accessible(self):
        """Test storage section is accessible as nested object."""
        config = Config()

        assert hasattr(config, "storage")
        assert hasattr(config.storage, "data_dir")
        assert hasattr(config.storage, "checkpoint_file")
        assert hasattr(config.storage, "database_file")

    def test_logging_section_accessible(self):
        """Test logging section is accessible as nested object."""
        config = Config()

        assert hasattr(config, "logging")
        assert hasattr(config.logging, "level")
        assert hasattr(config.logging, "log_file")
        assert hasattr(config.logging, "log_format")

    def test_nested_modification(self):
        """Test nested config values can be modified."""
        config = Config()

        # Modify nested values
        config.wiki.base_url = "https://example.com"
        config.scraper.rate_limit = 5.0
        config.storage.data_dir = Path("/tmp/data")
        config.logging.level = "DEBUG"

        # Verify modifications
        assert config.wiki.base_url == "https://example.com"
        assert config.scraper.rate_limit == 5.0
        assert config.storage.data_dir == Path("/tmp/data")
        assert config.logging.level == "DEBUG"


# ============================================================================
# TEST CLASS 6: TYPE SAFETY
# ============================================================================


class TestConfigTypeSafety:
    """Test config type safety and type conversion."""

    def test_rate_limit_is_float(self):
        """Test rate_limit is float type."""
        config = Config()
        assert isinstance(config.scraper.rate_limit, float)

    def test_timeout_is_int(self):
        """Test timeout is int type."""
        config = Config()
        assert isinstance(config.scraper.timeout, int)

    def test_max_retries_is_int(self):
        """Test max_retries is int type."""
        config = Config()
        assert isinstance(config.scraper.max_retries, int)

    def test_paths_are_path_objects(self):
        """Test all path fields are Path objects."""
        config = Config()

        assert isinstance(config.storage.data_dir, Path)
        assert isinstance(config.storage.checkpoint_file, Path)
        assert isinstance(config.storage.database_file, Path)
        assert isinstance(config.logging.log_file, Path)

    def test_string_fields_are_strings(self):
        """Test string fields are string type."""
        config = Config()

        assert isinstance(config.wiki.base_url, str)
        assert isinstance(config.wiki.api_path, str)
        assert isinstance(config.scraper.user_agent, str)
        assert isinstance(config.logging.level, str)
        assert isinstance(config.logging.log_format, str)


# ============================================================================
# TEST CLASS 7: EDGE CASES
# ============================================================================


class TestConfigEdgeCases:
    """Test config edge cases and boundary conditions."""

    def test_very_high_rate_limit(self):
        """Test very high rate_limit value."""
        config = Config()
        config.scraper.rate_limit = 1000.0
        config.validate()  # Should not raise

    def test_very_long_timeout(self):
        """Test very long timeout value."""
        config = Config()
        config.scraper.timeout = 3600  # 1 hour
        config.validate()  # Should not raise

    def test_many_retries(self):
        """Test many retries value."""
        config = Config()
        config.scraper.max_retries = 100
        config.validate()  # Should not raise

    def test_complex_path_with_subdirectories(self):
        """Test complex paths with multiple subdirectories."""
        config = Config()
        config.storage.data_dir = Path("path/to/deep/nested/directory")
        config.validate()  # Should not raise

    def test_unicode_in_paths(self):
        """Test Unicode characters in paths."""
        config = Config()
        config.storage.data_dir = Path("data/文件夹")
        config.validate()  # Should not raise

    def test_special_characters_in_user_agent(self):
        """Test special characters in user_agent."""
        config = Config()
        config.scraper.user_agent = "MyBot/1.0 (example.com; user+tag@example.com)"
        config.validate()  # Should not raise

    def test_case_insensitive_log_level(self):
        """Test log level is case-sensitive (standard Python logging)."""
        config = Config()

        # Valid uppercase
        config.logging.level = "INFO"
        config.validate()

        # Invalid lowercase should fail
        config.logging.level = "info"
        with pytest.raises(ConfigError, match="Invalid log level"):
            config.validate()


# ============================================================================
# TEST CLASS 8: ERROR MESSAGES
# ============================================================================


class TestConfigErrorMessages:
    """Test config error messages are clear and helpful."""

    def test_missing_file_error_includes_path(self, temp_config_dir: Path):
        """Test missing file error includes the file path."""
        missing_path = temp_config_dir / "missing.yaml"

        with pytest.raises(ConfigError) as exc_info:
            Config.from_yaml(missing_path)

        assert str(missing_path) in str(exc_info.value)

    def test_yaml_parse_error_is_descriptive(self, invalid_yaml_config: Path):
        """Test YAML parse error is descriptive."""
        with pytest.raises(ConfigError) as exc_info:
            Config.from_yaml(invalid_yaml_config)

        assert "Failed to parse YAML" in str(exc_info.value)

    def test_validation_error_specifies_field(self):
        """Test validation error specifies which field is invalid."""
        config = Config()
        config.scraper.rate_limit = -1.0

        with pytest.raises(ConfigError) as exc_info:
            config.validate()

        assert "rate_limit" in str(exc_info.value)

    def test_validation_error_includes_invalid_value(self):
        """Test validation error includes the invalid value."""
        config = Config()
        config.logging.level = "INVALID"

        with pytest.raises(ConfigError) as exc_info:
            config.validate()

        assert "INVALID" in str(exc_info.value)


# ============================================================================
# TEST CLASS 9: INTEGRATION
# ============================================================================


class TestConfigIntegration:
    """Test config integration scenarios."""

    def test_load_validate_and_use(self, valid_complete_config: Path):
        """Test complete workflow: load, validate, and use config."""
        # Load
        config = Config.from_yaml(valid_complete_config)

        # Validate
        config.validate()

        # Use values
        assert config.wiki.base_url.startswith("https://")
        assert config.scraper.rate_limit > 0
        assert config.storage.data_dir.is_absolute() is False  # Relative path

    def test_modify_loaded_config_and_revalidate(self, valid_minimal_config: Path):
        """Test modifying loaded config and revalidating."""
        # Load
        config = Config.from_yaml(valid_minimal_config)

        # Modify
        config.scraper.timeout = 60
        config.logging.level = "DEBUG"

        # Revalidate
        config.validate()  # Should not raise

        # Verify modifications
        assert config.scraper.timeout == 60
        assert config.logging.level == "DEBUG"

    def test_create_default_modify_and_validate(self):
        """Test creating default config, modifying, and validating."""
        # Create default
        config = Config()

        # Modify for production use
        config.scraper.rate_limit = 0.5  # Slower for politeness
        config.scraper.max_retries = 5  # More retries for reliability
        config.logging.level = "WARNING"  # Less verbose

        # Validate
        config.validate()

        # Use
        assert config.scraper.rate_limit == 0.5
        assert config.scraper.max_retries == 5

    def test_partial_override_preserves_other_defaults(
        self, valid_minimal_config: Path
    ):
        """Test partial override preserves other default values."""
        config = Config.from_yaml(valid_minimal_config)

        # Minimal config only sets base_url and rate_limit
        assert config.wiki.base_url == "https://irowiki.org"
        assert config.scraper.rate_limit == 2.0

        # All other values should be defaults
        assert config.scraper.timeout == 30  # Default
        assert config.scraper.max_retries == 3  # Default
        assert config.logging.level == "INFO"  # Default


# ============================================================================
# TEST CLASS 10: LOGGING INTEGRATION
# ============================================================================


class TestConfigLogging:
    """Test config loading logs appropriately."""

    def test_loading_logs_info_message(self, valid_complete_config: Path, caplog):
        """Test loading config logs info message."""
        with caplog.at_level(logging.INFO):
            Config.from_yaml(valid_complete_config)

        # Should log something about loading config
        assert len(caplog.records) > 0

    def test_validation_failure_logs_error(self, caplog):
        """Test validation failure logs error before raising."""
        config = Config()
        config.scraper.rate_limit = -1.0

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ConfigError):
                config.validate()

        # Should log validation error
        assert any("rate_limit" in record.message for record in caplog.records)

    def test_missing_file_logs_error(self, temp_config_dir: Path, caplog):
        """Test missing file logs error."""
        missing = temp_config_dir / "missing.yaml"

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ConfigError):
                Config.from_yaml(missing)

        assert len(caplog.records) > 0
