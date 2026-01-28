"""Pytest configuration and fixtures for API client tests."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from tests.mocks.mock_http_session import MockSession
from tests.mocks.mock_time import MockTime


@pytest.fixture
def fixtures_dir():
    """
    Return path to fixtures directory.

    Returns:
        Path object pointing to fixtures directory
    """
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def load_fixture(fixtures_dir):
    """
    Helper fixture to load JSON fixtures by name.

    Args:
        fixtures_dir: Path to fixtures directory

    Returns:
        Callable that loads a fixture file by name
    """

    def _load(filename: str) -> dict:
        """Load a JSON fixture file from fixtures/api directory."""
        fixture_path = fixtures_dir / "api" / filename
        with open(fixture_path, "r") as f:
            return json.load(f)

    return _load


@pytest.fixture
def mock_session(fixtures_dir):
    """
    Return mock HTTP session.

    Args:
        fixtures_dir: Path to fixtures directory

    Returns:
        MockSession instance
    """
    return MockSession(fixtures_dir)


@pytest.fixture
def api_client(mock_session, monkeypatch):
    """
    Return API client with mocked session and disabled rate limiter.

    Args:
        mock_session: Mock HTTP session fixture
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        MediaWikiAPIClient instance with mocked session
    """
    from scraper.api.client import MediaWikiAPIClient
    from scraper.api.rate_limiter import RateLimiter

    # Use disabled rate limiter for faster tests
    disabled_limiter = RateLimiter(enabled=False)
    client = MediaWikiAPIClient("https://irowiki.org", rate_limiter=disabled_limiter)
    monkeypatch.setattr(client, "session", mock_session)

    return client


@pytest.fixture
def mock_api_client(api_client):
    """
    Alias for api_client for backward compatibility.

    Returns:
        MediaWikiAPIClient instance with mocked session
    """
    return api_client


@pytest.fixture
def mock_time():
    """
    Return mock time module for testing rate limiter.

    Returns:
        MockTime instance with controllable time
    """
    return MockTime()


@pytest.fixture
def rate_limiter_with_mock_time(mock_time, monkeypatch):
    """
    Return rate limiter with mocked time module.

    Args:
        mock_time: MockTime fixture
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        RateLimiter instance configured to use mock time
    """
    from scraper.api.rate_limiter import RateLimiter

    # Replace time.time and time.sleep with mock versions
    monkeypatch.setattr("time.time", mock_time.time)
    monkeypatch.setattr("time.sleep", mock_time.sleep)

    return RateLimiter()


@pytest.fixture
def mock_tqdm():
    """
    Return mock tqdm for testing progress tracking.

    Returns:
        MockTqdm class
    """
    from tests.mocks.mock_tqdm import MockTqdm

    return MockTqdm


@pytest.fixture
def config_fixtures_dir(fixtures_dir):
    """
    Return path to config fixtures directory.

    Args:
        fixtures_dir: Path to main fixtures directory

    Returns:
        Path object pointing to config fixtures directory
    """
    return fixtures_dir / "config"


@pytest.fixture
def load_config_fixture(config_fixtures_dir):
    """
    Helper fixture to load config YAML fixtures by name.

    Args:
        config_fixtures_dir: Path to config fixtures directory

    Returns:
        Callable that returns path to a config fixture file by name
    """

    def _load(filename: str) -> Path:
        """Return path to a config fixture file."""
        return config_fixtures_dir / filename

    return _load


# =============================================================================
# Database Fixtures for Epic 02
# =============================================================================


@pytest.fixture
def temp_db_path():
    """
    Create temporary database file for testing.

    Yields:
        Path to temporary database file

    Cleanup:
        Deletes database file after test
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def db(temp_db_path):
    """
    Create initialized database for testing.

    Provides a Database instance with schema loaded and ready for testing.
    Automatically closes connection after test.

    Args:
        temp_db_path: Path to temporary database file

    Yields:
        Database instance with initialized schema
    """
    from scraper.storage.database import Database

    db = Database(temp_db_path)
    db.initialize_schema()

    yield db

    db.close()


@pytest.fixture
def sample_pages():
    """
    Provide sample Page instances for testing.

    Returns:
        List of Page instances with varied data
    """
    from scraper.storage.models import Page

    return [
        Page(page_id=1, namespace=0, title="Main Page", is_redirect=False),
        Page(page_id=2, namespace=0, title="Test Article", is_redirect=False),
        Page(page_id=3, namespace=1, title="Talk:Main Page", is_redirect=False),
        Page(page_id=4, namespace=0, title="Redirect Page", is_redirect=True),
        Page(page_id=5, namespace=6, title="File:Example.png", is_redirect=False),
    ]


@pytest.fixture
def sample_revisions():
    """
    Provide sample Revision instances for testing.

    Returns:
        List of Revision instances with varied data
    """
    from scraper.storage.models import Revision

    return [
        Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            user="Alice",
            user_id=101,
            comment="Initial creation",
            content="Hello world!",
            size=12,
            sha1="a" * 40,
            minor=False,
            tags=["visual-edit"],
        ),
        Revision(
            revision_id=1002,
            page_id=1,
            parent_id=1001,
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            user="Bob",
            user_id=102,
            comment="Minor fix",
            content="Hello world! Updated.",
            size=21,
            sha1="b" * 40,
            minor=True,
            tags=[],
        ),
        Revision(
            revision_id=1003,
            page_id=2,
            parent_id=None,
            timestamp=datetime(2024, 1, 3, 10, 0, 0),
            user="Charlie",
            user_id=103,
            comment="New article",
            content="Test content here.",
            size=18,
            sha1="c" * 40,
            minor=False,
            tags=None,
        ),
    ]


@pytest.fixture
def sample_files():
    """
    Provide sample FileMetadata instances for testing.

    Returns:
        List of FileMetadata instances with varied data
    """
    from scraper.storage.models import FileMetadata

    return [
        FileMetadata(
            filename="Example.png",
            url="https://example.com/files/Example.png",
            descriptionurl="https://example.com/wiki/File:Example.png",
            sha1="1234567890abcdef1234567890abcdef12345678",
            size=102400,
            width=800,
            height=600,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            uploader="Alice",
        ),
        FileMetadata(
            filename="Document.pdf",
            url="https://example.com/files/Document.pdf",
            descriptionurl="https://example.com/wiki/File:Document.pdf",
            sha1="abcdef1234567890abcdef1234567890abcdef12",
            size=524288,
            width=None,
            height=None,
            mime_type="application/pdf",
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            uploader="Bob",
        ),
    ]


@pytest.fixture
def sample_links():
    """
    Provide sample Link instances for testing.

    Returns:
        List of Link instances with varied types
    """
    from scraper.storage.models import Link

    return [
        Link(source_page_id=1, target_title="Test Article", link_type="page"),
        Link(source_page_id=1, target_title="Template:Infobox", link_type="template"),
        Link(source_page_id=1, target_title="File:Example.png", link_type="file"),
        Link(source_page_id=1, target_title="Category:Test", link_type="category"),
        Link(source_page_id=2, target_title="Main Page", link_type="page"),
    ]


# =============================================================================
# CLI Testing Fixtures
# =============================================================================


@pytest.fixture
def cli_args_full():
    """
    Provide CLI arguments for full scrape command testing.

    Returns:
        Namespace with all required CLI arguments for full scrape
    """
    from argparse import Namespace

    return Namespace(
        command="full",
        database=Path("data/test.db"),
        config=None,
        log_level="INFO",
        rate_limit=2.0,
        namespace=None,
        force=False,
        dry_run=False,
        quiet=False,
        resume=False,
        format="text",
    )


@pytest.fixture
def mock_config():
    """
    Provide mock configuration for CLI testing.

    Returns:
        MockConfig instance
    """
    from tests.mocks.mock_cli_components import MockConfig

    return MockConfig()


@pytest.fixture
def mock_full_scraper():
    """
    Provide mock FullScraper for CLI testing.

    Returns:
        MockFullScraper instance
    """
    from tests.mocks.mock_cli_components import MockConfig, MockFullScraper
    from unittest.mock import MagicMock

    config = MockConfig()
    api_client = MagicMock()
    database = MagicMock()

    return MockFullScraper(config, api_client, database)


@pytest.fixture
def mock_checkpoint_manager():
    """
    Provide mock CheckpointManager for CLI testing.

    Returns:
        MockCheckpointManager instance that doesn't load real checkpoints
    """
    from tests.mocks.mock_cli_components import MockCheckpointManager

    manager = MockCheckpointManager(Path("data/.checkpoint.json"))
    # By default, no checkpoint exists
    manager.checkpoint_exists = False
    manager.checkpoint = None
    return manager


@pytest.fixture
def patch_checkpoint_manager(mock_checkpoint_manager):
    """
    Patch CheckpointManager in CLI commands to prevent loading real files.

    Use this fixture in CLI tests to mock checkpoint functionality.
    """
    from unittest.mock import patch

    with patch(
        "scraper.cli.commands.CheckpointManager", return_value=mock_checkpoint_manager
    ):
        yield mock_checkpoint_manager
