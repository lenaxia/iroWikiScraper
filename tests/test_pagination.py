"""Tests for generic pagination handler."""

import pytest
from unittest.mock import Mock, call

from scraper.api.pagination import PaginatedQuery
from scraper.api.exceptions import APIError
from tests.mocks.mock_http_session import MockResponse


class TestPaginatedQueryInit:
    """Tests for PaginatedQuery initialization."""

    def test_valid_initialization(self, api_client):
        """Test valid initialization with correct parameters."""
        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages", "aplimit": 500},
            result_path=["query", "allpages"],
        )

        assert query.api == api_client
        assert query.params == {"list": "allpages", "aplimit": 500}
        assert query.result_path == ["query", "allpages"]
        assert query.progress_callback is None

    def test_initialization_with_progress_callback(self, api_client):
        """Test initialization with progress callback."""
        callback = Mock()
        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
            progress_callback=callback,
        )

        assert query.progress_callback == callback

    def test_invalid_api_client_none(self):
        """Test initialization fails with None api_client."""
        with pytest.raises(TypeError, match="api_client cannot be None"):
            PaginatedQuery(
                api_client=None,
                initial_params={"list": "allpages"},
                result_path=["query", "allpages"],
            )

    def test_invalid_api_client_wrong_type(self):
        """Test initialization fails with wrong type for api_client."""
        with pytest.raises(
            TypeError, match="api_client must be MediaWikiAPIClient instance"
        ):
            PaginatedQuery(
                api_client="not_a_client",
                initial_params={"list": "allpages"},
                result_path=["query", "allpages"],
            )

    def test_invalid_params_none(self, api_client):
        """Test initialization fails with None params."""
        with pytest.raises(ValueError, match="initial_params cannot be None or empty"):
            PaginatedQuery(
                api_client=api_client,
                initial_params=None,
                result_path=["query", "allpages"],
            )

    def test_invalid_params_empty(self, api_client):
        """Test initialization fails with empty params."""
        with pytest.raises(ValueError, match="initial_params cannot be None or empty"):
            PaginatedQuery(
                api_client=api_client,
                initial_params={},
                result_path=["query", "allpages"],
            )

    def test_invalid_params_wrong_type(self, api_client):
        """Test initialization fails with wrong type for params."""
        with pytest.raises(ValueError, match="initial_params must be a dictionary"):
            PaginatedQuery(
                api_client=api_client,
                initial_params="not_a_dict",
                result_path=["query", "allpages"],
            )

    def test_invalid_result_path_none(self, api_client):
        """Test initialization fails with None result_path."""
        with pytest.raises(ValueError, match="result_path cannot be None or empty"):
            PaginatedQuery(
                api_client=api_client,
                initial_params={"list": "allpages"},
                result_path=None,
            )

    def test_invalid_result_path_empty(self, api_client):
        """Test initialization fails with empty result_path."""
        with pytest.raises(ValueError, match="result_path cannot be None or empty"):
            PaginatedQuery(
                api_client=api_client,
                initial_params={"list": "allpages"},
                result_path=[],
            )

    def test_invalid_result_path_wrong_type(self, api_client):
        """Test initialization fails with wrong type for result_path."""
        with pytest.raises(ValueError, match="result_path must be a list"):
            PaginatedQuery(
                api_client=api_client,
                initial_params={"list": "allpages"},
                result_path="query.allpages",
            )

    def test_invalid_result_path_non_string_elements(self, api_client):
        """Test initialization fails with non-string elements in result_path."""
        with pytest.raises(
            ValueError,
            match="result_path elements must be strings, got: int at index 1",
        ):
            PaginatedQuery(
                api_client=api_client,
                initial_params={"list": "allpages"},
                result_path=["query", 123, "allpages"],
            )


class TestPaginatedQueryBasic:
    """Tests for basic pagination functionality."""

    def test_single_batch_no_pagination(self, api_client, mock_session, load_fixture):
        """Test query with single batch (no pagination needed)."""
        data = load_fixture("pagination_single_item.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages", "aplimit": 500},
            result_path=["query", "allpages"],
        )

        results = list(query)

        assert len(results) == 1
        assert results[0]["pageid"] == 999
        assert results[0]["title"] == "Only_Item"

    def test_multiple_batches_with_continuation(
        self, api_client, mock_session, load_fixture
    ):
        """Test query spanning multiple batches with continuation tokens."""
        batch1 = load_fixture("pagination_batch1.json")
        batch2 = load_fixture("pagination_batch2.json")
        batch3 = load_fixture("pagination_batch3_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=batch2),
                MockResponse(200, json_data=batch3),
            ]
        )

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages", "aplimit": 3},
            result_path=["query", "allpages"],
        )

        results = list(query)

        # Should have 3 + 2 + 2 = 7 items across all batches
        assert len(results) == 7
        assert results[0]["title"] == "Item_A"
        assert results[3]["title"] == "Item_D"
        assert results[6]["title"] == "Item_G"

    def test_empty_results(self, api_client, mock_session, load_fixture):
        """Test query returning empty results."""
        data = load_fixture("pagination_empty.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages", "aplimit": 500},
            result_path=["query", "allpages"],
        )

        results = list(query)

        assert len(results) == 0

    def test_single_item_result(self, api_client, mock_session, load_fixture):
        """Test query returning exactly one item."""
        data = load_fixture("pagination_single_item.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        results = list(query)

        assert len(results) == 1
        assert results[0]["pageid"] == 999


class TestPaginatedQueryResultPath:
    """Tests for result path navigation."""

    def test_simple_path(self, api_client, mock_session, load_fixture):
        """Test navigation with simple two-level path."""
        data = load_fixture("pagination_single_item.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        results = list(query)

        assert len(results) == 1

    def test_deep_nested_path(self, api_client, mock_session):
        """Test navigation with deeply nested path."""
        data = {
            "query": {
                "pages": {
                    "1": {
                        "revisions": [
                            {"revid": 100, "content": "text1"},
                            {"revid": 101, "content": "text2"},
                        ]
                    }
                }
            }
        }
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"prop": "revisions"},
            result_path=["query", "pages", "1", "revisions"],
        )

        results = list(query)

        assert len(results) == 2
        assert results[0]["revid"] == 100

    def test_invalid_path_key_error(self, api_client, mock_session):
        """Test that invalid path raises KeyError with context."""
        data = {"query": {"allpages": []}}
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "nonexistent", "path"],
        )

        with pytest.raises(
            KeyError,
            match="Failed to navigate result_path.*Key 'nonexistent' not found at path",
        ):
            list(query)

    def test_missing_intermediate_keys_handled(self, api_client, mock_session):
        """Test graceful handling when intermediate keys are missing."""
        data = {"query": {}}  # Missing 'allpages' key
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        with pytest.raises(
            KeyError, match="Key 'allpages' not found at path.*Available keys"
        ):
            list(query)

    def test_path_ends_at_non_iterable(self, api_client, mock_session):
        """Test error when result path points to non-iterable."""
        data = {"query": {"allpages": "not_a_list"}}
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        with pytest.raises(
            TypeError, match="Result at path.*is not iterable.*Got type: str"
        ):
            list(query)


class TestPaginatedQueryProgressCallback:
    """Tests for progress callback functionality."""

    def test_callback_invoked_for_each_batch(
        self, api_client, mock_session, load_fixture
    ):
        """Test that callback is invoked once per batch."""
        batch1 = load_fixture("pagination_batch1.json")
        batch2 = load_fixture("pagination_batch2.json")
        batch3 = load_fixture("pagination_batch3_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=batch2),
                MockResponse(200, json_data=batch3),
            ]
        )

        callback = Mock()
        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
            progress_callback=callback,
        )

        list(query)

        # Should be called 3 times (once per batch)
        assert callback.call_count == 3

    def test_callback_receives_correct_parameters(
        self, api_client, mock_session, load_fixture
    ):
        """Test that callback receives correct batch number and item count."""
        batch1 = load_fixture("pagination_batch1.json")
        batch2 = load_fixture("pagination_batch2.json")
        batch3 = load_fixture("pagination_batch3_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=batch2),
                MockResponse(200, json_data=batch3),
            ]
        )

        callback = Mock()
        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
            progress_callback=callback,
        )

        list(query)

        # Check callback was called with correct parameters
        callback.assert_has_calls(
            [
                call(batch_num=1, items_count=3),  # First batch has 3 items
                call(batch_num=2, items_count=2),  # Second batch has 2 items
                call(batch_num=3, items_count=2),  # Third batch has 2 items
            ]
        )

    def test_no_callback_works_fine(self, api_client, mock_session, load_fixture):
        """Test that query works without callback (None)."""
        data = load_fixture("pagination_single_item.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
            progress_callback=None,
        )

        results = list(query)

        assert len(results) == 1

    def test_callback_exception_doesnt_break_iteration(
        self, api_client, mock_session, load_fixture
    ):
        """Test that exception in callback doesn't break iteration."""
        batch1 = load_fixture("pagination_batch1.json")
        batch2 = load_fixture("pagination_batch2.json")
        batch3 = load_fixture("pagination_batch3_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=batch2),
                MockResponse(200, json_data=batch3),
            ]
        )

        def failing_callback(batch_num, items_count):
            if batch_num == 1:
                raise ValueError("Callback error")

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
            progress_callback=failing_callback,
        )

        # Should continue despite callback failure
        results = list(query)

        # Should still get all results
        assert len(results) == 7  # 3 from batch1 + 2 from batch2 + 2 from batch3


class TestPaginatedQueryErrorHandling:
    """Tests for error handling during pagination."""

    def test_api_error_during_pagination(self, api_client, mock_session, load_fixture):
        """Test handling of API error during pagination."""
        batch1 = load_fixture("pagination_batch1.json")
        error_response = load_fixture("error_response.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(400, json_data=error_response),
            ]
        )

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        with pytest.raises(APIError):
            list(query)

    def test_malformed_continue_token(self, api_client, mock_session):
        """Test handling of malformed continue token."""
        # First batch has malformed continue (not a dict)
        malformed_data = {
            "continue": "not_a_dict",
            "query": {"allpages": [{"pageid": 1, "title": "Test"}]},
        }
        mock_session.set_response_sequence(
            [MockResponse(200, json_data=malformed_data)]
        )

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        with pytest.raises(
            TypeError, match="continue token must be a dictionary, got: str"
        ):
            list(query)

    def test_missing_result_path_in_response(self, api_client, mock_session):
        """Test handling when result path is missing from response."""
        # Response missing the expected 'query' key
        data = {"somekey": "somevalue"}
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        with pytest.raises(KeyError, match="Key 'query' not found"):
            list(query)

    def test_empty_batches_in_middle_of_pagination(
        self, api_client, mock_session, load_fixture
    ):
        """Test handling of empty batch in middle of pagination."""
        batch1 = load_fixture("pagination_batch1.json")
        empty_batch = {
            "continue": {"apcontinue": "Next", "continue": "-||"},
            "query": {"allpages": []},
        }
        batch3 = load_fixture("pagination_batch3_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=empty_batch),
                MockResponse(200, json_data=batch3),
            ]
        )

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        results = list(query)

        # Should handle empty batch gracefully and continue
        # 3 from batch1 + 0 from empty + 2 from batch3
        assert len(results) == 5

    def test_continue_token_preserved_across_batches(
        self, api_client, mock_session, load_fixture
    ):
        """Test that continue tokens are properly merged into params."""
        batch1 = load_fixture("pagination_batch1.json")
        batch2 = load_fixture("pagination_batch2.json")
        batch3 = load_fixture("pagination_batch3_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=batch2),
                MockResponse(200, json_data=batch3),
            ]
        )

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages", "aplimit": 3},
            result_path=["query", "allpages"],
        )

        list(query)

        # Verify that all three requests were made
        # MockSession should have recorded the params
        assert mock_session.get_call_count == 3


class TestPaginatedQueryIntegration:
    """Integration tests with existing components."""

    def test_works_with_mediawiki_api_client(
        self, api_client, mock_session, load_fixture
    ):
        """Test that PaginatedQuery works with real MediaWikiAPIClient."""
        data = load_fixture("pagination_single_item.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages", "aplimit": 500},
            result_path=["query", "allpages"],
        )

        results = list(query)

        assert len(results) == 1
        assert isinstance(results[0], dict)

    def test_reusable_across_multiple_iterations(
        self, api_client, mock_session, load_fixture
    ):
        """Test that PaginatedQuery can be iterated multiple times."""
        data = load_fixture("pagination_single_item.json")

        # Need to set up response for each iteration
        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        # First iteration
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])
        results1 = list(query)

        # Second iteration
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])
        results2 = list(query)

        assert results1 == results2

    def test_generator_behavior(self, api_client, mock_session, load_fixture):
        """Test that results are yielded incrementally (generator pattern)."""
        batch1 = load_fixture("pagination_batch1.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=batch1)])

        query = PaginatedQuery(
            api_client=api_client,
            initial_params={"list": "allpages"},
            result_path=["query", "allpages"],
        )

        # Test generator protocol
        iterator = iter(query)
        first_item = next(iterator)

        assert first_item["pageid"] == 100
        assert first_item["title"] == "Item_A"
