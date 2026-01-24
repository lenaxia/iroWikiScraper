"""Configuration management for iRO-Wiki-Scraper.

This module provides configuration loading from YAML files with validation,
nested structure using dataclasses, and sensible defaults.

Example:
    >>> from pathlib import Path
    >>> from scraper.config import Config
    >>>
    >>> # Load from file
    >>> config = Config.from_yaml("config.yaml")
    >>> config.validate()
    >>>
    >>> # Use configuration
    >>> print(config.wiki.base_url)
    >>> print(config.scraper.rate_limit)
    >>>
    >>> # Use defaults
    >>> config = Config()
    >>> config.validate()
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""


@dataclass
class WikiConfig:
    """
    Configuration for Wiki API settings.

    Attributes:
        base_url: Base URL of the wiki (e.g., "https://irowiki.org")
        api_path: Path to API endpoint (e.g., "/w/api.php")

    Example:
        >>> wiki = WikiConfig(
        ...     base_url="https://irowiki.org",
        ...     api_path="/w/api.php"
        ... )
    """

    base_url: str = "https://irowiki.org"
    api_path: str = "/w/api.php"


@dataclass
class ScraperConfig:
    """
    Configuration for scraper behavior.

    Attributes:
        rate_limit: Maximum requests per second (must be positive)
        timeout: HTTP request timeout in seconds (must be positive)
        max_retries: Maximum number of retry attempts (must be non-negative)
        user_agent: User-Agent string for HTTP requests

    Example:
        >>> scraper = ScraperConfig(
        ...     rate_limit=1.0,
        ...     timeout=30,
        ...     max_retries=3,
        ...     user_agent="MyBot/1.0"
        ... )
    """

    rate_limit: float = 1.0
    timeout: int = 30
    max_retries: int = 3
    user_agent: str = (
        "iROWikiArchiver/1.0 (github.com/irowiki/scraper; archiver@irowiki.org)"
    )


@dataclass
class StorageConfig:
    """
    Configuration for data storage paths.

    Attributes:
        data_dir: Directory for storing scraped data
        checkpoint_file: Path to checkpoint file for resume capability
        database_file: Path to SQLite database file

    Example:
        >>> storage = StorageConfig(
        ...     data_dir=Path("data"),
        ...     checkpoint_file=Path("data/.checkpoint.json"),
        ...     database_file=Path("data/irowiki.db")
        ... )
    """

    data_dir: Path = field(default_factory=lambda: Path("data"))
    checkpoint_file: Path = field(default_factory=lambda: Path("data/.checkpoint.json"))
    database_file: Path = field(default_factory=lambda: Path("data/irowiki.db"))


@dataclass
class LoggingConfig:
    """
    Configuration for logging behavior.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        log_format: Format string for log messages

    Example:
        >>> logging_config = LoggingConfig(
        ...     level="INFO",
        ...     log_file=Path("logs/scraper.log"),
        ...     log_format="%(asctime)s - %(levelname)s - %(message)s"
        ... )
    """

    level: str = "INFO"
    log_file: Path = field(default_factory=lambda: Path("logs/scraper.log"))
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class Config:
    """
    Main configuration class with nested sections.

    Provides configuration management with validation, defaults, and
    YAML loading capabilities. Uses nested dataclasses for organization.

    Attributes:
        wiki: Wiki API configuration
        scraper: Scraper behavior configuration
        storage: Storage paths configuration
        logging: Logging configuration

    Example:
        >>> # Use defaults
        >>> config = Config()
        >>> config.validate()
        >>>
        >>> # Load from YAML
        >>> config = Config.from_yaml("config.yaml")
        >>> config.validate()
        >>>
        >>> # Access nested values
        >>> print(config.wiki.base_url)
        >>> print(config.scraper.rate_limit)
        >>> print(config.storage.data_dir)
        >>> print(config.logging.level)
    """

    wiki: WikiConfig = field(default_factory=WikiConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Config":
        """
        Load configuration from YAML file.

        Loads configuration from YAML file, applies defaults for missing
        fields, converts string paths to Path objects, and validates.

        Args:
            path: Path to YAML configuration file (string or Path object)

        Returns:
            Config instance with loaded values

        Raises:
            ConfigError: If file not found, YAML parsing fails, or validation fails

        Example:
            >>> config = Config.from_yaml("config.yaml")
            >>> config.validate()
            >>>
            >>> # Or with Path object
            >>> from pathlib import Path
            >>> config = Config.from_yaml(Path("config.yaml"))
        """
        # Convert to Path object
        config_path = Path(path)

        # Check file exists
        if not config_path.exists():
            error_msg = f"Configuration file not found: {config_path}"
            logger.error(error_msg)
            raise ConfigError(error_msg)

        # Load YAML
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Failed to parse YAML file {config_path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to read configuration file {config_path}: {e}"
            logger.error(error_msg)
            raise ConfigError(error_msg) from e

        # Handle empty file
        if data is None:
            data = {}

        # Extract nested sections with defaults
        wiki_data = data.get("wiki", {})
        scraper_data = data.get("scraper", {})
        storage_data = data.get("storage", {})
        logging_data = data.get("logging", {})

        # Convert string paths to Path objects in storage section
        if "data_dir" in storage_data and isinstance(storage_data["data_dir"], str):
            storage_data["data_dir"] = Path(storage_data["data_dir"])
        if "checkpoint_file" in storage_data and isinstance(
            storage_data["checkpoint_file"], str
        ):
            storage_data["checkpoint_file"] = Path(storage_data["checkpoint_file"])
        if "database_file" in storage_data and isinstance(
            storage_data["database_file"], str
        ):
            storage_data["database_file"] = Path(storage_data["database_file"])

        # Convert log_file to Path object in logging section
        if "log_file" in logging_data and isinstance(logging_data["log_file"], str):
            logging_data["log_file"] = Path(logging_data["log_file"])

        # Create nested config objects
        wiki = WikiConfig(**wiki_data)
        scraper = ScraperConfig(**scraper_data)
        storage = StorageConfig(**storage_data)
        logging_config = LoggingConfig(**logging_data)

        # Create main config
        config = cls(
            wiki=wiki, scraper=scraper, storage=storage, logging=logging_config
        )

        # Validate and return
        logger.info(f"Loaded configuration from {config_path}")
        config.validate()
        return config

    def validate(self) -> None:
        """
        Validate configuration values.

        Checks all configuration values for validity and raises ConfigError
        if any values are invalid.

        Raises:
            ConfigError: If any configuration value is invalid

        Example:
            >>> config = Config()
            >>> config.validate()  # Should not raise
            >>>
            >>> config.scraper.rate_limit = -1.0
            >>> config.validate()  # Raises ConfigError
        """
        errors = []

        # Validate wiki settings
        if not self.wiki.base_url:
            errors.append("wiki.base_url cannot be empty")

        # Validate scraper settings
        if self.scraper.rate_limit <= 0:
            errors.append(
                f"scraper.rate_limit must be positive, got {self.scraper.rate_limit}"
            )

        if self.scraper.timeout <= 0:
            errors.append(
                f"scraper.timeout must be positive, got {self.scraper.timeout}"
            )

        if self.scraper.max_retries < 0:
            errors.append(
                f"scraper.max_retries must be non-negative, got {self.scraper.max_retries}"
            )

        if not self.scraper.user_agent:
            errors.append("scraper.user_agent cannot be empty")

        # Validate logging settings
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level not in valid_log_levels:
            errors.append(f"Invalid log level: {
                    self.logging.level}. Must be one of: {
                    ', '.join(valid_log_levels)}")

        # Raise if any errors
        if errors:
            error_msg = "Configuration validation failed:\n  - " + "\n  - ".join(errors)
            logger.error(error_msg)
            raise ConfigError(error_msg)

        logger.debug("Configuration validation passed")
