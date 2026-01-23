"""Pytest configuration and fixtures for API client tests."""

import json
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
