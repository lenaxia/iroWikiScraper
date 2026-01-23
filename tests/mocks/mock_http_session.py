"""Mock HTTP session for testing API client."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class MockResponse:
    """Mock HTTP response object."""

    def __init__(
        self,
        status_code: int,
        json_data: Optional[Dict[str, Any]] = None,
        text: str = "",
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize mock response.

        Args:
            status_code: HTTP status code
            json_data: JSON response data
            text: Response text content
            headers: Response headers
        """
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}

    def json(self) -> Dict[str, Any]:
        """
        Return JSON data or raise ValueError.

        Returns:
            JSON response data

        Raises:
            ValueError: If response is not valid JSON
        """
        if self._json_data is None:
            raise ValueError("Invalid JSON")
        return self._json_data

    def raise_for_status(self) -> None:
        """
        Raise HTTPError for bad status codes.

        Raises:
            requests.HTTPError: If status code indicates error
        """
        if self.status_code >= 400:
            error = requests.HTTPError()
            error.response = self
            raise error


class MockSession:
    """Mock HTTP session for testing."""

    def __init__(self, fixtures_dir: Path):
        """
        Initialize mock session.

        Args:
            fixtures_dir: Path to fixtures directory
        """
        self.fixtures_dir = fixtures_dir
        self.headers = {}
        self.get_call_count = 0
        self.last_request_params: Optional[Dict[str, Any]] = None
        self.last_request_url: Optional[str] = None
        self.response_sequence = []  # For testing retries
        self.current_response_index = 0

    def update(self, headers: Dict[str, str]) -> None:
        """
        Update session headers.

        Args:
            headers: Headers to add/update
        """
        self.headers.update(headers)

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> MockResponse:
        """
        Mock GET request.

        Args:
            url: Request URL
            params: Query parameters
            timeout: Request timeout

        Returns:
            MockResponse object
        """
        self.get_call_count += 1
        self.last_request_url = url
        self.last_request_params = params

        # If response sequence is set (for testing retries), use it
        if self.response_sequence:
            if self.current_response_index < len(self.response_sequence):
                response = self.response_sequence[self.current_response_index]
                self.current_response_index += 1
                return response
            # If we've exhausted the sequence, return the last response
            return self.response_sequence[-1]

        # Default behavior based on request parameters
        if params:
            # Simulate timeout
            if params.get("titles") == "TimeoutPage":
                raise requests.Timeout("Request timed out")

            # Simulate 404
            if params.get("titles") == "NonexistentPage":
                return MockResponse(404)

            # Simulate rate limit
            if params.get("titles") == "RateLimitPage":
                return MockResponse(429)

            # Simulate server error
            if params.get("titles") == "ServerErrorPage":
                return MockResponse(500)

            # Simulate malformed JSON
            if params.get("titles") == "MalformedPage":
                return MockResponse(200, text="Not JSON")

            # Simulate API error response
            if params.get("titles") == "APIErrorPage":
                fixture_file = self.fixtures_dir / "api" / "error_response.json"
                with open(fixture_file, encoding="utf-8") as f:
                    data = json.load(f)
                return MockResponse(200, json_data=data)

        # Default successful response
        fixture_file = self.fixtures_dir / "api" / "successful_page_response.json"
        with open(fixture_file, encoding="utf-8") as f:
            data = json.load(f)

        return MockResponse(200, json_data=data)

    def set_response_sequence(self, responses) -> None:
        """
        Set a sequence of responses for testing retries.

        Args:
            responses: List of MockResponse objects to return in sequence
        """
        self.response_sequence = responses
        self.current_response_index = 0
