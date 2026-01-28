"""Comprehensive precedence validation for US-0707.

This test file validates the EXACT scenario mentioned in the requirements:
- Create config file with rate_limit=1.5
- Pass --rate-limit 5.0
- Verify scraper gets 5.0 (not 1.5)
"""

from argparse import Namespace
from pathlib import Path

from scraper.cli.commands import _load_config


class TestExactPrecedenceScenario:
    """Test the exact precedence scenario from requirements."""

    def test_config_file_rate_limit_1_5_cli_5_0_gets_5_0(self, load_config_fixture):
        """Test EXACT scenario: config has 1.5, CLI has 5.0, result is 5.0.

        This is the specific scenario mentioned in requirements:
        - Create config file with rate_limit=1.5
        - Pass --rate-limit 5.0
        - Verify scraper gets 5.0 (not 1.5)
        """
        # Use cli_override_test.yaml which has rate_limit: 1.5
        config_file = load_config_fixture("cli_override_test.yaml")

        # Create args with --rate-limit 5.0
        args = Namespace(
            config=config_file,
            database=Path("test.db"),
            log_level="INFO",
            rate_limit=5.0,
        )

        # Load config with CLI override
        config = _load_config(args)

        # VERIFY: scraper gets 5.0 (not 1.5)
        assert config.scraper.rate_limit == 5.0
        assert config.scraper.rate_limit != 1.5

    def test_integration_full_workflow_with_exact_scenario(
        self, load_config_fixture, tmp_path
    ):
        """Test full integration workflow with exact precedence scenario."""
        # Create config file with rate_limit=1.5
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
scraper:
  rate_limit: 1.5
  timeout: 45
  max_retries: 4

storage:
  database_file: "from_file.db"

logging:
  level: "ERROR"
""")

        # Simulate CLI args with --rate-limit 5.0
        args = Namespace(
            config=config_file,
            database=Path("from_cli.db"),  # Override database too
            log_level="INFO",  # Override log level too
            rate_limit=5.0,  # Override rate limit
        )

        # Load config
        config = _load_config(args)

        # VERIFY CLI overrides
        assert (
            config.scraper.rate_limit == 5.0
        ), "Rate limit should be from CLI (5.0), not file (1.5)"
        assert config.storage.database_file == Path(
            "from_cli.db"
        ), "Database should be from CLI"
        assert (
            config.logging.level == "INFO"
        ), "Log level should be from CLI (INFO), not file (ERROR)"

        # VERIFY file values are preserved where not overridden
        assert (
            config.scraper.timeout == 45
        ), "Timeout should be from file (not overridden)"
        assert (
            config.scraper.max_retries == 4
        ), "Max retries should be from file (not overridden)"

        # VERIFY defaults are used where neither file nor CLI specify
        assert (
            config.wiki.base_url == "https://irowiki.org"
        ), "Base URL should be default"
