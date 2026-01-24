"""Tests for ResponseValidator class."""

import pytest

from scraper.api.exceptions import APIResponseError


class TestResponseValidatorValidateRequiredFields:
    """Tests for ResponseValidator.validate_required_fields method."""

    def test_validate_all_fields_present(self):
        """Test validation passes when all required fields are present."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1, "ns": 0, "title": "Test Page"}

        # Should not raise
        ResponseValidator.validate_required_fields(
            data, required_fields=["pageid", "ns", "title"], context="test"
        )

    def test_validate_missing_single_field(self):
        """Test validation fails when a single field is missing."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1, "ns": 0}  # Missing 'title'

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_required_fields(
                data, required_fields=["pageid", "ns", "title"], context="test"
            )

        error = exc_info.value
        assert "title" in str(error)
        assert "missing" in str(error).lower()

    def test_validate_missing_multiple_fields(self):
        """Test validation fails when multiple fields are missing."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1}  # Missing 'ns' and 'title'

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_required_fields(
                data,
                required_fields=["pageid", "ns", "title"],
                context="page data",
            )

        error = exc_info.value
        assert "missing" in str(error).lower()
        # Should mention at least one missing field
        assert "ns" in str(error) or "title" in str(error)

    def test_validate_empty_required_fields_list(self):
        """Test validation passes when no fields are required."""
        from scraper.api.validation import ResponseValidator

        data = {}

        # Should not raise
        ResponseValidator.validate_required_fields(
            data, required_fields=[], context="test"
        )

    def test_validate_with_custom_context(self):
        """Test error message includes custom context."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_required_fields(
                data, required_fields=["title"], context="custom_context"
            )

        error = exc_info.value
        # Error should include info about missing field
        assert "title" in str(error)

    def test_validate_extra_fields_ok(self):
        """Test validation passes when extra fields are present."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1, "ns": 0, "title": "Test", "extra": "field"}

        # Should not raise - extra fields are allowed
        ResponseValidator.validate_required_fields(
            data, required_fields=["pageid", "ns", "title"], context="test"
        )


class TestResponseValidatorSafeGet:
    """Tests for ResponseValidator.safe_get method."""

    def test_safe_get_field_exists_correct_type(self):
        """Test safe_get returns value when field exists with correct type."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 123, "title": "Test Page"}

        value = ResponseValidator.safe_get(data, "pageid", int, "test")
        assert value == 123

        value = ResponseValidator.safe_get(data, "title", str, "test")
        assert value == "Test Page"

    def test_safe_get_field_missing(self):
        """Test safe_get raises error when field is missing."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 123}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, "title", str, "test")

        error = exc_info.value
        assert "title" in str(error)
        assert "missing" in str(error).lower()

    def test_safe_get_wrong_type_str_instead_of_int(self):
        """Test safe_get raises error when type is wrong (str instead of int)."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": "123"}  # String instead of int

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, "pageid", int, "test")

        error = exc_info.value
        assert "type" in str(error).lower()
        assert "pageid" in str(error)

    def test_safe_get_wrong_type_int_instead_of_str(self):
        """Test safe_get raises error when type is wrong (int instead of str)."""
        from scraper.api.validation import ResponseValidator

        data = {"title": 123}  # Int instead of str

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, "title", str, "test")

        error = exc_info.value
        assert "type" in str(error).lower()

    def test_safe_get_with_dict_type(self):
        """Test safe_get works with dict type."""
        from scraper.api.validation import ResponseValidator

        data = {"metadata": {"key": "value"}}

        value = ResponseValidator.safe_get(data, "metadata", dict, "test")
        assert value == {"key": "value"}

    def test_safe_get_with_list_type(self):
        """Test safe_get works with list type."""
        from scraper.api.validation import ResponseValidator

        data = {"tags": ["tag1", "tag2"]}

        value = ResponseValidator.safe_get(data, "tags", list, "test")
        assert value == ["tag1", "tag2"]

    def test_safe_get_with_bool_type(self):
        """Test safe_get works with bool type."""
        from scraper.api.validation import ResponseValidator

        data = {"redirect": True}

        value = ResponseValidator.safe_get(data, "redirect", bool, "test")
        assert value is True

    def test_safe_get_none_value(self):
        """Test safe_get handles None value (field exists but value is None)."""
        from scraper.api.validation import ResponseValidator

        data = {"title": None}

        # This should raise because None is not a str
        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, "title", str, "test")

        error = exc_info.value
        assert "type" in str(error).lower()

    def test_safe_get_with_custom_context(self):
        """Test error message includes custom context."""
        from scraper.api.validation import ResponseValidator

        data = {}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.safe_get(data, "field", str, "custom_context")

        error = exc_info.value
        # Error should mention the field
        assert "field" in str(error)

    def test_safe_get_nested_dict_structure(self):
        """Test safe_get works with nested dict values."""
        from scraper.api.validation import ResponseValidator

        data = {"query": {"pages": {"1": {"title": "Test"}}}}

        # Get nested dict
        value = ResponseValidator.safe_get(data, "query", dict, "test")
        assert "pages" in value

    def test_safe_get_empty_string_is_valid(self):
        """Test safe_get accepts empty string as valid str."""
        from scraper.api.validation import ResponseValidator

        data = {"comment": ""}

        value = ResponseValidator.safe_get(data, "comment", str, "test")
        assert value == ""

    def test_safe_get_zero_is_valid_int(self):
        """Test safe_get accepts 0 as valid int."""
        from scraper.api.validation import ResponseValidator

        data = {"ns": 0}

        value = ResponseValidator.safe_get(data, "ns", int, "test")
        assert value == 0

    def test_safe_get_empty_list_is_valid(self):
        """Test safe_get accepts empty list as valid list."""
        from scraper.api.validation import ResponseValidator

        data = {"tags": []}

        value = ResponseValidator.safe_get(data, "tags", list, "test")
        assert value == []


class TestResponseValidatorOptionalGet:
    """Tests for ResponseValidator.optional_get method."""

    def test_optional_get_field_exists(self):
        """Test optional_get returns value when field exists."""
        from scraper.api.validation import ResponseValidator

        data = {"redirect": ""}

        value = ResponseValidator.optional_get(data, "redirect", str, None)
        assert value == ""

    def test_optional_get_field_missing_returns_default(self):
        """Test optional_get returns default when field is missing."""
        from scraper.api.validation import ResponseValidator

        data = {"pageid": 1}

        value = ResponseValidator.optional_get(data, "redirect", str, None)
        assert value is None

        value = ResponseValidator.optional_get(data, "count", int, 0)
        assert value == 0

    def test_optional_get_wrong_type_raises_error(self):
        """Test optional_get raises error when type is wrong."""
        from scraper.api.validation import ResponseValidator

        data = {"redirect": 123}  # Int instead of str

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.optional_get(data, "redirect", str, None)

        error = exc_info.value
        assert "type" in str(error).lower()

    def test_optional_get_with_various_defaults(self):
        """Test optional_get with various default values."""
        from scraper.api.validation import ResponseValidator

        data = {}

        assert (
            ResponseValidator.optional_get(data, "field", str, "default") == "default"
        )
        assert ResponseValidator.optional_get(data, "field", int, 42) == 42
        assert ResponseValidator.optional_get(data, "field", bool, False) is False
        assert ResponseValidator.optional_get(data, "field", list, []) == []


class TestResponseValidatorValidateContinuation:
    """Tests for ResponseValidator.validate_continuation method."""

    def test_validate_continuation_dict_valid(self):
        """Test validation passes for valid dict continuation."""
        from scraper.api.validation import ResponseValidator

        continuation = {"continue": "-||", "apcontinue": "Test"}

        # Should not raise
        ResponseValidator.validate_continuation(continuation, "test")

    def test_validate_continuation_invalid_type(self):
        """Test validation fails for non-dict continuation."""
        from scraper.api.validation import ResponseValidator

        continuation = "invalid_string_format"

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_continuation(continuation, "test")

        error = exc_info.value
        assert "continuation" in str(error).lower()
        assert "dict" in str(error).lower() or "type" in str(error).lower()

    def test_validate_continuation_empty_dict(self):
        """Test validation passes for empty dict."""
        from scraper.api.validation import ResponseValidator

        continuation = {}

        # Should not raise - empty dict is valid
        ResponseValidator.validate_continuation(continuation, "test")

    def test_validate_continuation_none(self):
        """Test validation fails for None."""
        from scraper.api.validation import ResponseValidator

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_continuation(None, "test")

        error = exc_info.value
        assert "continuation" in str(error).lower()

    def test_validate_continuation_list(self):
        """Test validation fails for list."""
        from scraper.api.validation import ResponseValidator

        continuation = ["continue", "token"]

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_continuation(continuation, "test")

        error = exc_info.value
        assert "continuation" in str(error).lower()


class TestResponseValidatorValidateQuery:
    """Tests for ResponseValidator.validate_query method."""

    def test_validate_query_exists(self):
        """Test validation passes when query field exists."""
        from scraper.api.validation import ResponseValidator

        response = {"query": {"pages": {}}}

        # Should not raise
        query = ResponseValidator.validate_query(response, "test")
        assert query == {"pages": {}}

    def test_validate_query_missing(self):
        """Test validation fails when query field is missing."""
        from scraper.api.validation import ResponseValidator

        response = {"batchcomplete": ""}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_query(response, "test")

        error = exc_info.value
        assert "query" in str(error).lower()
        assert "missing" in str(error).lower()

    def test_validate_query_wrong_type(self):
        """Test validation fails when query is not a dict."""
        from scraper.api.validation import ResponseValidator

        response = {"query": "not_a_dict"}

        with pytest.raises(APIResponseError) as exc_info:
            ResponseValidator.validate_query(response, "test")

        error = exc_info.value
        assert "query" in str(error).lower()
        assert "type" in str(error).lower()

    def test_validate_query_empty_dict(self):
        """Test validation passes for empty query dict."""
        from scraper.api.validation import ResponseValidator

        response = {"query": {}}

        query = ResponseValidator.validate_query(response, "test")
        assert query == {}
