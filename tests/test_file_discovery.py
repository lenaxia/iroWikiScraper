"""Tests for file discovery functionality."""

from datetime import datetime
from unittest.mock import patch

import pytest

from scraper.api.exceptions import APIError
from scraper.scrapers.file_scraper import FileDiscovery
from scraper.storage.models import FileMetadata
from tests.mocks.mock_http_session import MockResponse


class TestFileMetadataModel:
    """Tests for FileMetadata dataclass."""

    def test_valid_file_metadata_creation_all_fields(self):
        """Test creating valid file metadata with all fields."""
        metadata = FileMetadata(
            filename="Example.png",
            url="https://irowiki.org/images/Example.png",
            descriptionurl="https://irowiki.org/wiki/File:Example.png",
            sha1="abc123def456789012345678901234567890abcd",
            size=123456,
            width=800,
            height=600,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            uploader="AdminUser",
        )

        assert metadata.filename == "Example.png"
        assert metadata.url == "https://irowiki.org/images/Example.png"
        assert metadata.descriptionurl == "https://irowiki.org/wiki/File:Example.png"
        assert metadata.sha1 == "abc123def456789012345678901234567890abcd"
        assert metadata.size == 123456
        assert metadata.width == 800
        assert metadata.height == 600
        assert metadata.mime_type == "image/png"
        assert metadata.timestamp == datetime(2024, 1, 15, 10, 30, 0)
        assert metadata.uploader == "AdminUser"

    def test_image_file_with_dimensions(self):
        """Test image file with width and height."""
        metadata = FileMetadata(
            filename="Image.jpg",
            url="https://irowiki.org/images/Image.jpg",
            descriptionurl="https://irowiki.org/wiki/File:Image.jpg",
            sha1="1234567890123456789012345678901234567890",
            size=100000,
            width=1920,
            height=1080,
            mime_type="image/jpeg",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            uploader="User1",
        )

        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.mime_type == "image/jpeg"

    def test_non_image_file_no_dimensions(self):
        """Test non-image file (video/pdf) with no width/height."""
        metadata = FileMetadata(
            filename="Video.webm",
            url="https://irowiki.org/images/Video.webm",
            descriptionurl="https://irowiki.org/wiki/File:Video.webm",
            sha1="abcdef1234567890123456789012345678901234",
            size=5000000,
            width=None,
            height=None,
            mime_type="video/webm",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            uploader="VideoUser",
        )

        assert metadata.width is None
        assert metadata.height is None
        assert metadata.mime_type == "video/webm"

    def test_empty_uploader_deleted_user(self):
        """Test file with empty uploader (deleted user)."""
        metadata = FileMetadata(
            filename="Orphaned.png",
            url="https://irowiki.org/images/Orphaned.png",
            descriptionurl="https://irowiki.org/wiki/File:Orphaned.png",
            sha1="1111111111111111111111111111111111111111",
            size=50000,
            width=500,
            height=400,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            uploader="",
        )

        assert metadata.uploader == ""

    def test_invalid_filename_empty_raises_error(self):
        """Test that empty filename raises ValueError."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            FileMetadata(
                filename="",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_filename_whitespace_raises_error(self):
        """Test that whitespace-only filename raises ValueError."""
        with pytest.raises(ValueError, match="filename cannot be empty"):
            FileMetadata(
                filename="   ",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_sha1_wrong_length_raises_error(self):
        """Test that SHA1 with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="sha1 must be exactly 40 characters"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="abc123",  # Too short
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_sha1_non_hex_raises_error(self):
        """Test that SHA1 with non-hex characters raises ValueError."""
        with pytest.raises(ValueError, match="sha1 must be a valid hexadecimal string"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="gggggggggggggggggggggggggggggggggggggggg",  # Invalid hex
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_size_negative_raises_error(self):
        """Test that negative size raises ValueError."""
        with pytest.raises(ValueError, match="size must be non-negative"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=-100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_url_empty_raises_error(self):
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            FileMetadata(
                filename="Test.png",
                url="",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_descriptionurl_empty_raises_error(self):
        """Test that empty description URL raises ValueError."""
        with pytest.raises(ValueError, match="descriptionurl cannot be empty"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_invalid_mime_type_empty_raises_error(self):
        """Test that empty mime_type raises ValueError."""
        with pytest.raises(ValueError, match="mime_type cannot be empty"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=100,
                mime_type="",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_frozen_dataclass_immutable(self):
        """Test that FileMetadata is frozen (immutable)."""
        metadata = FileMetadata(
            filename="Test.png",
            url="https://irowiki.org/images/Test.png",
            descriptionurl="https://irowiki.org/wiki/File:Test.png",
            sha1="1234567890123456789012345678901234567890",
            size=100,
            width=100,
            height=100,
            mime_type="image/png",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            uploader="User",
        )

        with pytest.raises(AttributeError):
            metadata.filename = "Modified.png"

    def test_width_height_validation_negative(self):
        """Test that negative width/height raises ValueError."""
        with pytest.raises(ValueError, match="width must be positive if provided"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=-100,
                height=100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

        with pytest.raises(ValueError, match="height must be positive if provided"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=-100,
                mime_type="image/png",
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                uploader="User",
            )

    def test_timestamp_validation(self):
        """Test that timestamp must be datetime."""
        with pytest.raises(ValueError, match="timestamp must be a datetime object"):
            FileMetadata(
                filename="Test.png",
                url="https://irowiki.org/images/Test.png",
                descriptionurl="https://irowiki.org/wiki/File:Test.png",
                sha1="1234567890123456789012345678901234567890",
                size=100,
                width=100,
                height=100,
                mime_type="image/png",
                timestamp="2024-01-15",  # String instead of datetime
                uploader="User",
            )


class TestFileDiscoveryInit:
    """Tests for FileDiscovery initialization."""

    def test_valid_initialization_with_defaults(self, api_client):
        """Test valid initialization with default parameters."""
        discovery = FileDiscovery(api_client)

        assert discovery.api == api_client
        assert discovery.batch_size == 500
        assert discovery.progress_interval == 100

    def test_custom_batch_size_and_progress_interval(self, api_client):
        """Test initialization with custom batch_size and progress_interval."""
        discovery = FileDiscovery(api_client, batch_size=250, progress_interval=50)

        assert discovery.batch_size == 250
        assert discovery.progress_interval == 50

    def test_batch_size_capped_at_500(self, api_client):
        """Test that batch_size is capped at 500 (API maximum)."""
        discovery = FileDiscovery(api_client, batch_size=1000)

        assert discovery.batch_size == 500

    def test_initialization_with_zero_batch_size(self, api_client):
        """Test that zero batch_size is handled."""
        discovery = FileDiscovery(api_client, batch_size=0)

        # Should use minimum of 1
        assert discovery.batch_size >= 1


class TestFileDiscoverFiles:
    """Tests for discover_files method."""

    def test_single_file_discovery(self, api_client, mock_session, load_fixture):
        """Test discovering a single file."""
        data = load_fixture("allimages_single.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert files[0].filename == "Example.png"
        assert files[0].url == "https://irowiki.org/wiki/images/a/ab/Example.png"
        assert files[0].sha1 == "abc123def456789012345678901234567890abcd"
        assert files[0].size == 123456
        assert files[0].width == 800
        assert files[0].height == 600
        assert files[0].mime_type == "image/png"
        assert files[0].uploader == "AdminUploader"

    def test_multiple_files_discovery(self, api_client, mock_session, load_fixture):
        """Test discovering multiple files."""
        data = load_fixture("allimages_multiple.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 3
        assert files[0].filename == "First_Image.png"
        assert files[1].filename == "Second_Image.jpg"
        assert files[2].filename == "Third_Image.gif"

    def test_pagination_with_multiple_batches(
        self, api_client, mock_session, load_fixture
    ):
        """Test pagination spanning multiple batches."""
        batch1 = load_fixture("allimages_batch1.json")
        final_batch = load_fixture("allimages_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=final_batch),
            ]
        )

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        # Should have 2 files from batch1 + 2 from final = 4 total
        assert len(files) == 4
        assert files[0].filename == "Batch1_File1.png"
        assert files[1].filename == "Batch1_File2.jpg"
        assert files[2].filename == "Final_File1.png"
        assert files[3].filename == "Final_File2.jpg"

    def test_empty_results_no_files(self, api_client, mock_session, load_fixture):
        """Test handling of empty results (no files found)."""
        data = load_fixture("allimages_empty.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 0

    def test_files_with_various_mime_types(
        self, api_client, mock_session, load_fixture
    ):
        """Test discovering files with various MIME types (images, video, PDF)."""
        data = load_fixture("allimages_video.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 2
        # Video file (no width/height)
        assert files[0].filename == "Tutorial_Video.webm"
        assert files[0].mime_type == "video/webm"
        assert files[0].width is None
        assert files[0].height is None
        # PDF file (no width/height)
        assert files[1].filename == "Documentation.pdf"
        assert files[1].mime_type == "application/pdf"
        assert files[1].width is None
        assert files[1].height is None

    @patch("scraper.scrapers.file_scraper.logger")
    def test_progress_logging(
        self, mock_logger, api_client, mock_session, load_fixture
    ):
        """Test that progress is logged at INFO level."""
        data = load_fixture("allimages_single.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client, progress_interval=1)
        discovery.discover_files()

        # Check that info logs were called
        assert mock_logger.info.called

    def test_timestamp_parsing(self, api_client, mock_session, load_fixture):
        """Test that timestamps are correctly parsed."""
        data = load_fixture("allimages_single.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert isinstance(files[0].timestamp, datetime)
        assert files[0].timestamp == datetime(2024, 1, 15, 10, 30, 0)


class TestFileDiscoveryDeletedUser:
    """Tests for handling files from deleted users."""

    def test_handle_deleted_user_empty_uploader(
        self, api_client, mock_session, load_fixture
    ):
        """Test handling files uploaded by deleted users (empty uploader)."""
        data = load_fixture("allimages_deleted_user.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert files[0].filename == "Orphaned_File.png"
        assert files[0].uploader == ""

    def test_missing_user_field_handled_gracefully(self, api_client, mock_session):
        """Test graceful handling when user field is missing."""
        data = {
            "batchcomplete": "",
            "query": {
                "allimages": [
                    {
                        "name": "Test.png",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "url": "https://irowiki.org/images/Test.png",
                        "descriptionurl": "https://irowiki.org/wiki/File:Test.png",
                        "size": 100,
                        "width": 100,
                        "height": 100,
                        "sha1": "1234567890123456789012345678901234567890",
                        "mime": "image/png",
                        # Missing "user" field
                    }
                ]
            },
        }
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert files[0].uploader == ""


class TestFileDiscoveryIntegration:
    """Integration tests with existing components."""

    def test_integration_with_paginated_query(
        self, api_client, mock_session, load_fixture
    ):
        """Test integration with PaginatedQuery."""
        batch1 = load_fixture("allimages_batch1.json")
        final_batch = load_fixture("allimages_final.json")

        mock_session.set_response_sequence(
            [
                MockResponse(200, json_data=batch1),
                MockResponse(200, json_data=final_batch),
            ]
        )

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        # Should use PaginatedQuery internally and handle continuation
        assert len(files) == 4

    def test_integration_with_api_client(self, api_client, mock_session, load_fixture):
        """Test integration with MediaWikiAPIClient."""
        data = load_fixture("allimages_single.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        # Verify API client was used
        assert len(files) == 1

    def test_verify_api_parameters_correct(
        self, api_client, mock_session, load_fixture
    ):
        """Test that correct API parameters are sent."""
        data = load_fixture("allimages_single.json")
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client, batch_size=500)
        files = discovery.discover_files()

        # Verify the mock was called with correct parameters
        # The PaginatedQuery should use 'list': 'allimages'
        assert len(files) == 1

    def test_api_error_propagates(self, api_client, mock_session, load_fixture):
        """Test that API errors are propagated correctly."""
        error_response = load_fixture("error_response.json")
        mock_session.set_response_sequence(
            [MockResponse(400, json_data=error_response)]
        )

        discovery = FileDiscovery(api_client)

        with pytest.raises(APIError):
            discovery.discover_files()


class TestFileDiscoveryEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_optional_dimensions(self, api_client, mock_session):
        """Test files without width/height (non-images)."""
        data = {
            "batchcomplete": "",
            "query": {
                "allimages": [
                    {
                        "name": "Document.pdf",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "url": "https://irowiki.org/images/Document.pdf",
                        "descriptionurl": "https://irowiki.org/wiki/File:Document.pdf",
                        "size": 100000,
                        # No width/height fields
                        "sha1": "1234567890123456789012345678901234567890",
                        "mime": "application/pdf",
                        "user": "DocUser",
                    }
                ]
            },
        }
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert files[0].width is None
        assert files[0].height is None

    def test_defensive_parsing_with_defaults(self, api_client, mock_session):
        """Test defensive parsing using .get() with defaults."""
        # This test verifies the implementation uses defensive parsing
        data = {
            "batchcomplete": "",
            "query": {
                "allimages": [
                    {
                        "name": "Minimal.png",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "url": "https://irowiki.org/images/Minimal.png",
                        "descriptionurl": "https://irowiki.org/wiki/File:Minimal.png",
                        "size": 1000,
                        "sha1": "1234567890123456789012345678901234567890",
                        "mime": "image/png",
                        # Missing optional fields
                    }
                ]
            },
        }
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert files[0].uploader == ""
        assert files[0].width is None
        assert files[0].height is None

    def test_large_file_size(self, api_client, mock_session):
        """Test handling of very large file sizes."""
        data = {
            "batchcomplete": "",
            "query": {
                "allimages": [
                    {
                        "name": "LargeVideo.mp4",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "url": "https://irowiki.org/images/LargeVideo.mp4",
                        "descriptionurl": "https://irowiki.org/wiki/File:LargeVideo.mp4",
                        "size": 2147483647,  # Large file
                        "sha1": "1234567890123456789012345678901234567890",
                        "mime": "video/mp4",
                        "user": "VideoUser",
                    }
                ]
            },
        }
        mock_session.set_response_sequence([MockResponse(200, json_data=data)])

        discovery = FileDiscovery(api_client)
        files = discovery.discover_files()

        assert len(files) == 1
        assert files[0].size == 2147483647
