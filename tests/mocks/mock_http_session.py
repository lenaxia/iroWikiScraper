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
        content: bytes = b"",
    ):
        """
        Initialize mock response.

        Args:
            status_code: HTTP status code
            json_data: JSON response data
            text: Response text content
            headers: Response headers
            content: Binary content for file downloads
        """
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = content
        self._chunk_size = 8192

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

    def iter_content(self, chunk_size: int = 8192):
        """
        Iterate over response content in chunks (for streaming downloads).

        Args:
            chunk_size: Size of chunks to yield

        Yields:
            Chunks of binary content
        """
        content = self.content
        for i in range(0, len(content), chunk_size):
            yield content[i : i + chunk_size]


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
        self.responses = []  # Queue of responses to return
        self.current_response_index = 0
        self._force_exception: Optional[Exception] = None
        self._force_status_code: Optional[int] = None
        self._force_text: Optional[str] = None
        self._force_content: Optional[bytes] = None

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
        stream: bool = False,
    ) -> MockResponse:
        """
        Mock GET request.

        Args:
            url: Request URL
            params: Query parameters
            timeout: Request timeout
            stream: Whether to stream the response

        Returns:
            MockResponse object

        Raises:
            Exception: If force_exception is set
        """
        self.get_call_count += 1
        self.last_request_url = url
        self.last_request_params = params

        # Check for forced exception (for testing error handling)
        if self._force_exception:
            exception = self._force_exception
            self._force_exception = None  # Reset after raising
            raise exception

        # Check for forced status code
        if self._force_status_code:
            if self._force_content:
                response = MockResponse(
                    self._force_status_code, content=self._force_content
                )
            elif self._force_text:
                response = MockResponse(self._force_status_code, text=self._force_text)
            else:
                response = MockResponse(self._force_status_code)
            return response

        # If responses queue is set (simpler API), use it
        if self.responses:
            if len(self.responses) > 0:
                response_data = self.responses.pop(0)
                return MockResponse(200, json_data=response_data)
            # If queue is empty, raise an error
            raise RuntimeError("No more responses in queue")

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

            # Simulate API warning response
            if params.get("titles") == "WarningPage":
                fixture_file = self.fixtures_dir / "api" / "warning_response.json"
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

    def add_response(self, method: str, json_data: Dict[str, Any]) -> None:
        """
        Add a response to the queue (simpler API for tests).

        Args:
            method: HTTP method (currently ignored, always uses GET)
            json_data: JSON data to return as response
        """
        self.responses.append(json_data)

    def set_exception(self, exception: Exception) -> None:
        """
        Force the session to raise an exception on next request.

        Args:
            exception: Exception to raise
        """
        self._force_exception = exception

    def set_status_code(self, status_code: int, text: Optional[str] = None) -> None:
        """
        Force the session to return a specific status code.

        Args:
            status_code: HTTP status code to return
            text: Optional response text
        """
        self._force_status_code = status_code
        self._force_text = text

    def set_content(self, content: bytes, status_code: int = 200) -> None:
        """
        Force the session to return binary content (for file downloads).

        Args:
            content: Binary content to return
            status_code: HTTP status code (default 200)
        """
        self._force_content = content
        self._force_status_code = status_code

    def reset(self) -> None:
        """Reset all forced behaviors."""
        self._force_exception = None
        self._force_status_code = None
        self._force_text = None
        self._force_content = None
        self.response_sequence = []
        self.responses = []
        self.current_response_index = 0
        self.get_call_count = 0
