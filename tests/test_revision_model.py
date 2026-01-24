"""Tests for the Revision model."""

from datetime import datetime

import pytest

from scraper.storage.models import Revision


class TestRevisionModel:
    """Tests for Revision dataclass validation and creation."""

    def test_revision_creation_valid(self):
        """Test creating a valid revision with all required fields."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        revision = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=timestamp,
            user="TestUser",
            user_id=10,
            comment="Test comment",
            content="Test content",
            size=100,
            sha1="abc123",
            minor=False,
            tags=[],
        )

        assert revision.revision_id == 1001
        assert revision.page_id == 1
        assert revision.parent_id is None
        assert revision.timestamp == timestamp
        assert revision.user == "TestUser"
        assert revision.user_id == 10
        assert revision.comment == "Test comment"
        assert revision.content == "Test content"
        assert revision.size == 100
        assert revision.sha1 == "abc123"
        assert revision.minor is False
        assert revision.tags == []

    def test_revision_with_parent(self):
        """Test revision with a parent ID (not first revision)."""
        revision = Revision(
            revision_id=2002,
            page_id=2,
            parent_id=2001,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="Editor",
            user_id=20,
            comment="Second revision",
            content="Updated content",
            size=150,
            sha1="def456",
        )

        assert revision.parent_id == 2001

    def test_revision_with_tags(self):
        """Test revision with edit tags."""
        revision = Revision(
            revision_id=3001,
            page_id=3,
            parent_id=3000,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TagEditor",
            user_id=30,
            comment="Tagged edit",
            content="Content",
            size=50,
            sha1="ghi789",
            tags=["visual edit", "mobile edit"],
        )

        assert revision.tags == ["visual edit", "mobile edit"]

    def test_revision_minor_edit(self):
        """Test revision marked as minor."""
        revision = Revision(
            revision_id=4001,
            page_id=4,
            parent_id=4000,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="MinorEditor",
            user_id=40,
            comment="Typo fix",
            content="Fixed typo",
            size=75,
            sha1="jkl012",
            minor=True,
        )

        assert revision.minor is True

    def test_revision_deleted_user(self):
        """Test revision by deleted/hidden user."""
        revision = Revision(
            revision_id=5001,
            page_id=5,
            parent_id=5000,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="",  # Empty for deleted user
            user_id=None,  # None for deleted user
            comment="Old edit",
            content="Old content",
            size=100,
            sha1="mno345",
        )

        assert revision.user == ""
        assert revision.user_id is None

    def test_revision_empty_content(self):
        """Test revision with empty content (blank page)."""
        revision = Revision(
            revision_id=6001,
            page_id=6,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="Blanker",
            user_id=60,
            comment="Blanked page",
            content="",
            size=0,
            sha1="empty",
        )

        assert revision.content == ""
        assert revision.size == 0

    def test_revision_empty_comment(self):
        """Test revision with empty comment."""
        revision = Revision(
            revision_id=7001,
            page_id=7,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="SilentEditor",
            user_id=70,
            comment="",
            content="Content",
            size=50,
            sha1="pqr678",
        )

        assert revision.comment == ""

    def test_revision_tags_none_converts_to_empty_list(self):
        """Test that tags=None is converted to empty list."""
        revision = Revision(
            revision_id=8001,
            page_id=8,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="NoTags",
            user_id=80,
            comment="No tags",
            content="Content",
            size=50,
            sha1="stu901",
            tags=None,
        )

        assert revision.tags == []

    # Validation tests - invalid inputs

    def test_revision_invalid_revision_id_negative(self):
        """Test that negative revision_id raises ValueError."""
        with pytest.raises(ValueError, match="revision_id must be a positive integer"):
            Revision(
                revision_id=-1,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_revision_id_zero(self):
        """Test that zero revision_id raises ValueError."""
        with pytest.raises(ValueError, match="revision_id must be a positive integer"):
            Revision(
                revision_id=0,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_page_id(self):
        """Test that invalid page_id raises ValueError."""
        with pytest.raises(ValueError, match="page_id must be a positive integer"):
            Revision(
                revision_id=1001,
                page_id=0,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_parent_id_negative(self):
        """Test that negative parent_id raises ValueError."""
        with pytest.raises(
            ValueError, match="parent_id must be a positive integer or None"
        ):
            Revision(
                revision_id=2002,
                page_id=2,
                parent_id=-1,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_parent_id_greater_than_revision_id(self):
        """Test that parent_id >= revision_id raises ValueError."""
        with pytest.raises(
            ValueError, match="parent_id .* must be less than revision_id"
        ):
            Revision(
                revision_id=2002,
                page_id=2,
                parent_id=2002,  # Equal to revision_id
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_timestamp_not_datetime(self):
        """Test that non-datetime timestamp raises ValueError."""
        with pytest.raises(ValueError, match="timestamp must be a datetime object"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp="2024-01-15",  # String instead of datetime
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_user_not_string(self):
        """Test that non-string user raises ValueError."""
        with pytest.raises(ValueError, match="user must be a string"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user=123,  # Int instead of string
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_user_id_negative(self):
        """Test that negative user_id raises ValueError."""
        with pytest.raises(
            ValueError, match="user_id must be a positive integer or None"
        ):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=-1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_comment_not_string(self):
        """Test that non-string comment raises ValueError."""
        with pytest.raises(ValueError, match="comment must be a string"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment=None,  # None instead of string
                content="Content",
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_content_not_string(self):
        """Test that non-string content raises ValueError."""
        with pytest.raises(ValueError, match="content must be a string"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content=["Content"],  # List instead of string
                size=50,
                sha1="abc",
            )

    def test_revision_invalid_size_negative(self):
        """Test that negative size raises ValueError."""
        with pytest.raises(ValueError, match="size must be a non-negative integer"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=-10,
                sha1="abc",
            )

    def test_revision_invalid_sha1_empty(self):
        """Test that empty sha1 raises ValueError."""
        with pytest.raises(ValueError, match="sha1 must be a non-empty string"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="",
            )

    def test_revision_invalid_minor_not_bool(self):
        """Test that non-bool minor raises ValueError."""
        with pytest.raises(ValueError, match="minor must be a boolean"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
                minor="yes",  # String instead of bool
            )

    def test_revision_invalid_tags_not_list(self):
        """Test that non-list tags raises ValueError."""
        with pytest.raises(ValueError, match="tags must be a list or None"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
                tags="visual edit",  # String instead of list
            )

    def test_revision_invalid_tags_non_string_items(self):
        """Test that tags with non-string items raises ValueError."""
        with pytest.raises(ValueError, match="All tags must be strings"):
            Revision(
                revision_id=1001,
                page_id=1,
                parent_id=None,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                user="User",
                user_id=1,
                comment="Comment",
                content="Content",
                size=50,
                sha1="abc",
                tags=["visual edit", 123],  # Mixed types
            )

    def test_revision_repr(self):
        """Test __repr__ method."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        revision = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=timestamp,
            user="TestUser",
            user_id=10,
            comment="Test",
            content="Content",
            size=50,
            sha1="abc",
        )

        repr_str = repr(revision)
        assert "Revision(id=1001" in repr_str
        assert "page=1" in repr_str
        assert "user='TestUser'" in repr_str
        assert "2024-01-15T10:30:00" in repr_str

    def test_revision_frozen(self):
        """Test that Revision is immutable (frozen dataclass)."""
        revision = Revision(
            revision_id=1001,
            page_id=1,
            parent_id=None,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user="TestUser",
            user_id=10,
            comment="Test",
            content="Content",
            size=50,
            sha1="abc",
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            revision.revision_id = 9999
