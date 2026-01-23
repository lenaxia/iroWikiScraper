"""Pytest configuration and fixtures for API client tests."""

from pathlib import Path

import pytest

from tests.mocks.mock_http_session import MockSession


@pytest.fixture
def fixtures_dir():
    """
    Return path to fixtures directory.

    Returns:
        Path object pointing to fixtures directory
    """
    return Path(__file__).parent.parent / "fixtures"


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
    Return API client with mocked session.

    Args:
        mock_session: Mock HTTP session fixture
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        MediaWikiAPIClient instance with mocked session
    """
    from scraper.api.client import MediaWikiAPIClient

    client = MediaWikiAPIClient("https://irowiki.org")
    monkeypatch.setattr(client, "session", mock_session)

    return client
