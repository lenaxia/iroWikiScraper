"""Response validation utilities for MediaWiki API.

This module provides utilities for validating and safely accessing fields
in MediaWiki API responses, providing resilience against API changes.
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from .exceptions import APIResponseError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResponseValidator:
    """Validates MediaWiki API response structure and provides safe field access.

    This class provides static methods for:
    - Validating required fields exist
    - Safely accessing fields with type checking
    - Validating continuation tokens
    - Validating query responses

    Example:
        >>> data = {"pageid": 1, "ns": 0, "title": "Test"}
        >>> ResponseValidator.validate_required_fields(
        ...     data, ["pageid", "ns", "title"], "page data"
        ... )
        >>> page_id = ResponseValidator.safe_get(data, "pageid", int, "page")
    """

    @staticmethod
    def validate_required_fields(
        data: Dict[str, Any], required_fields: List[str], context: str = "response"
    ) -> None:
        """Validate that all required fields are present in data.

        Args:
            data: Dictionary to validate
            required_fields: List of field names that must be present
            context: Description of what's being validated (for error messages)

        Raises:
            APIResponseError: If any required fields are missing
        """
        missing = [f for f in required_fields if f not in data]

        if missing:
            logger.error(
                f"Missing required fields in {context}: {missing}",
                extra={
                    "missing_fields": missing,
                    "available_fields": list(data.keys()),
                    "full_data": data,
                    "context": context,
                },
            )
            raise APIResponseError(
                f"API response missing required fields: {missing}",
                request_params={"context": context, "missing": missing},
            )

    @staticmethod
    def safe_get(
        data: Dict[str, Any],
        field: str,
        expected_type: Type[T],
        context: str = "response",
    ) -> T:
        """Safely get field with type validation.

        Args:
            data: Dictionary to get field from
            field: Field name to retrieve
            expected_type: Expected Python type (int, str, dict, list, bool, etc.)
            context: Description for error messages

        Returns:
            Field value with correct type

        Raises:
            APIResponseError: If field is missing or has wrong type
        """
        if field not in data:
            logger.error(
                f"Missing field '{field}' in {context}",
                extra={
                    "field": field,
                    "available_fields": list(data.keys()),
                    "data": data,
                    "context": context,
                },
            )
            raise APIResponseError(
                f"Missing required field: {field}",
                request_params={"context": context, "field": field},
            )

        value = data[field]

        if not isinstance(value, expected_type):
            logger.error(
                f"Field '{field}' has wrong type in {context}. "
                f"Expected {expected_type.__name__}, got {type(value).__name__}",
                extra={
                    "field": field,
                    "expected_type": expected_type.__name__,
                    "actual_type": type(value).__name__,
                    "value": value,
                    "data": data,
                    "context": context,
                },
            )
            raise APIResponseError(
                f"Field '{field}' has wrong type: "
                f"expected {expected_type.__name__}, got {type(value).__name__}",
                request_params={"context": context, "field": field},
            )

        return value  # type: ignore

    @staticmethod
    def optional_get(
        data: Dict[str, Any],
        field: str,
        expected_type: Type[T],
        default: Optional[T] = None,
    ) -> Optional[T]:
        """Get optional field with type validation.

        Args:
            data: Dictionary to get field from
            field: Field name to retrieve
            expected_type: Expected Python type
            default: Default value if field is missing

        Returns:
            Field value if present, otherwise default

        Raises:
            APIResponseError: If field is present but has wrong type
        """
        if field not in data:
            return default

        value = data[field]

        if not isinstance(value, expected_type):
            logger.error(
                f"Optional field '{field}' has wrong type. "
                f"Expected {expected_type.__name__}, got {type(value).__name__}",
                extra={
                    "field": field,
                    "expected_type": expected_type.__name__,
                    "actual_type": type(value).__name__,
                    "value": value,
                },
            )
            raise APIResponseError(
                f"Field '{field}' has wrong type: "
                f"expected {expected_type.__name__}, got {type(value).__name__}",
                request_params={"field": field},
            )

        return value  # type: ignore

    @staticmethod
    def validate_continuation(continuation: Any, context: str = "response") -> None:
        """Validate continuation token format.

        MediaWiki continuation tokens should be dictionaries. This validates
        that the continuation parameter has the expected structure.

        Args:
            continuation: Continuation token from API response
            context: Description for error messages

        Raises:
            APIResponseError: If continuation token format is invalid
        """
        if not isinstance(continuation, dict):
            logger.error(
                f"Invalid continuation token format in {context}. "
                f"Expected dict, got {type(continuation).__name__}",
                extra={
                    "continuation": continuation,
                    "type": type(continuation).__name__,
                    "context": context,
                },
            )
            raise APIResponseError(
                f"Invalid continuation token format: expected dict, "
                f"got {type(continuation).__name__}",
                request_params={
                    "context": context,
                    "continuation": str(continuation)[:100],
                },
            )

    @staticmethod
    def validate_query(
        response: Dict[str, Any], context: str = "response"
    ) -> Dict[str, Any]:
        """Validate and extract query field from response.

        Args:
            response: Full API response
            context: Description for error messages

        Returns:
            Query dictionary from response

        Raises:
            APIResponseError: If query field is missing or invalid
        """
        if "query" not in response:
            logger.error(
                f"Response missing 'query' field in {context}",
                extra={"response": response, "context": context},
            )
            raise APIResponseError(
                "API response missing 'query' field",
                request_params={"context": context},
            )

        query = response["query"]

        if not isinstance(query, dict):
            logger.error(
                f"Query field has wrong type in {context}. "
                f"Expected dict, got {type(query).__name__}",
                extra={
                    "query": query,
                    "type": type(query).__name__,
                    "context": context,
                },
            )
            raise APIResponseError(
                f"Query field has wrong type: expected dict, got {type(query).__name__}",
                request_params={"context": context},
            )

        return query
