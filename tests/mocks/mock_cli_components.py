"""Mock components for CLI command testing."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from scraper.storage.models import Page


@dataclass
class MockScrapeResult:
    """Mock result for full scrape operations."""

    pages_count: int = 0
    revisions_count: int = 0
    namespaces_scraped: List[int] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    failed_pages: List[int] = field(default_factory=list)
    namespace_stats: dict = field(
        default_factory=dict
    )  # {ns_id: {"pages": count, "revisions": count}}
    _duration: Optional[float] = None  # Allow overriding duration directly

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        # Allow direct override of duration for testing
        if self._duration is not None:
            return self._duration
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success(self) -> bool:
        """Check if scrape was successful (no errors)."""
        return len(self.errors) == 0


@dataclass
class MockIncrementalStats:
    """Mock stats for incremental scrape operations."""

    pages_new: int = 0
    pages_modified: int = 0
    pages_deleted: int = 0
    pages_moved: int = 0
    revisions_added: int = 0
    files_downloaded: int = 0
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))

    @property
    def total_pages_affected(self) -> int:
        """Get total pages affected."""
        return (
            self.pages_new + self.pages_modified + self.pages_deleted + self.pages_moved
        )


class MockConfig:
    """Mock configuration object."""

    def __init__(self):
        """Initialize mock config with default values."""
        self.wiki = MockWikiConfig()
        self.scraper = MockScraperConfig()
        self.storage = MockStorageConfig()
        self.logging = MockLoggingConfig()

    def validate(self):
        """Mock validate method."""

    @staticmethod
    def from_yaml(path: str):
        """Create mock config from YAML file."""
        config = MockConfig()
        # Simulate loading from file
        return config


class MockWikiConfig:
    """Mock wiki configuration."""

    def __init__(self):
        """Initialize wiki config."""
        self.base_url = "https://irowiki.org"


class MockScraperConfig:
    """Mock scraper configuration."""

    def __init__(self):
        """Initialize scraper config."""
        self.rate_limit = 2.0
        self.user_agent = "Test Scraper/1.0"
        self.timeout = 30
        self.max_retries = 3


class MockStorageConfig:
    """Mock storage configuration."""

    def __init__(self):
        """Initialize storage config."""
        self.database_file = Path("data/test.db")
        self.data_dir = Path("data")
        self.checkpoint_file = Path("data/.checkpoint.json")


class MockLoggingConfig:
    """Mock logging configuration."""

    def __init__(self):
        """Initialize logging config."""
        self.level = "INFO"


class MockDatabase:
    """Mock database for testing."""

    def __init__(self, db_path: str):
        """Initialize mock database.

        Args:
            db_path: Path to database file
        """
        self.db_path = db_path
        self.pages_count = 0
        self.initialized = False
        self.closed = False

    def initialize_schema(self):
        """Mock schema initialization."""
        self.initialized = True

    def get_connection(self):
        """Mock connection getter."""
        return MockConnection(self.pages_count)

    def close(self):
        """Mock close method."""
        self.closed = True


class MockConnection:
    """Mock database connection."""

    def __init__(self, pages_count: int):
        """Initialize mock connection.

        Args:
            pages_count: Number of pages to return in queries
        """
        self.pages_count = pages_count

    def execute(self, query: str):
        """Mock execute method.

        Args:
            query: SQL query string

        Returns:
            MockCursor instance
        """
        return MockCursor(self.pages_count)


class MockCursor:
    """Mock database cursor."""

    def __init__(self, pages_count: int):
        """Initialize mock cursor.

        Args:
            pages_count: Number of pages to return
        """
        self.pages_count = pages_count

    def fetchone(self):
        """Mock fetchone method.

        Returns:
            Tuple with pages count
        """
        return (self.pages_count,)


class MockFullScraper:
    """Mock FullScraper for command testing."""

    def __init__(self, config, api_client, database, checkpoint_manager=None):
        """Initialize mock scraper.

        Args:
            config: Configuration object
            api_client: API client instance
            database: Database instance
            checkpoint_manager: Optional checkpoint manager
        """
        self.config = config
        self.api_client = api_client
        self.database = database
        self.checkpoint_manager = checkpoint_manager
        self.scrape_called = False
        self.scrape_args = {}
        self.result_to_return = None
        self.should_raise = None

    def set_result(self, result: MockScrapeResult):
        """Set result to return from scrape.

        Args:
            result: ScrapeResult to return
        """
        self.result_to_return = result

    def set_exception(self, exception: Exception):
        """Set exception to raise from scrape.

        Args:
            exception: Exception to raise
        """
        self.should_raise = exception

    def scrape(self, namespaces=None, progress_callback=None, resume=False):
        """Mock scrape method.

        Args:
            namespaces: Namespaces to scrape
            progress_callback: Progress callback function
            resume: Whether to resume from checkpoint

        Returns:
            MockScrapeResult instance

        Raises:
            Exception if set_exception was called
        """
        self.scrape_called = True
        self.scrape_args = {
            "namespaces": namespaces,
            "progress_callback": progress_callback,
            "resume": resume,
        }

        if self.should_raise:
            raise self.should_raise

        if self.result_to_return:
            # Call progress callback if provided (simulate some progress)
            if progress_callback:
                progress_callback("discover", 1, 2)
                progress_callback("discover", 2, 2)
                progress_callback("scrape", 50, 100)
                progress_callback("scrape", 100, 100)
            return self.result_to_return

        # Default result
        return MockScrapeResult(
            pages_count=100,
            revisions_count=500,
            namespaces_scraped=namespaces or [0, 4, 6, 10, 14],
            start_time=datetime.now(),
            end_time=datetime.now(),
        )


class MockIncrementalPageScraper:
    """Mock IncrementalPageScraper for command testing."""

    def __init__(self, api_client, database, download_dir):
        """Initialize mock incremental scraper.

        Args:
            api_client: API client instance
            database: Database instance
            download_dir: Download directory path
        """
        self.api_client = api_client
        self.database = database
        self.download_dir = download_dir
        self.scrape_called = False
        self.stats_to_return = None
        self.should_raise = None

    def set_stats(self, stats: MockIncrementalStats):
        """Set stats to return from scrape_incremental.

        Args:
            stats: Stats to return
        """
        self.stats_to_return = stats

    def set_exception(self, exception: Exception):
        """Set exception to raise from scrape_incremental.

        Args:
            exception: Exception to raise
        """
        self.should_raise = exception

    def scrape_incremental(self):
        """Mock scrape_incremental method.

        Returns:
            MockIncrementalStats instance

        Raises:
            Exception if set_exception was called
        """
        self.scrape_called = True

        if self.should_raise:
            raise self.should_raise

        if self.stats_to_return:
            return self.stats_to_return

        # Default stats
        return MockIncrementalStats(
            pages_new=5,
            pages_modified=10,
            pages_deleted=2,
            revisions_added=25,
            files_downloaded=3,
            duration=timedelta(seconds=45.5),
        )


class MockPageDiscovery:
    """Mock PageDiscovery for dry-run testing."""

    def __init__(self, api_client):
        """Initialize mock page discovery.

        Args:
            api_client: API client instance
        """
        self.api_client = api_client
        self.pages_to_return = []

    def set_pages(self, pages: List[Page]):
        """Set pages to return from discover_all_pages.

        Args:
            pages: List of pages to return
        """
        self.pages_to_return = pages

    def discover_all_pages(self, namespaces=None):
        """Mock discover_all_pages method.

        Args:
            namespaces: Namespaces to discover

        Returns:
            List of Page objects
        """
        return self.pages_to_return


class MockCheckpointManager:
    """Mock CheckpointManager for command testing."""

    def __init__(self, checkpoint_file: Path):
        """Initialize mock checkpoint manager.

        Args:
            checkpoint_file: Path to checkpoint file
        """
        self.checkpoint_file = checkpoint_file
        self.checkpoint_exists = False
        self.checkpoint = None
        self.cleared = False

    def exists(self) -> bool:
        """Check if checkpoint exists.

        Returns:
            True if checkpoint exists, False otherwise
        """
        return self.checkpoint_exists

    def get_checkpoint(self):
        """Get checkpoint data.

        Returns:
            Checkpoint data or None
        """
        return self.checkpoint

    def clear(self):
        """Clear checkpoint."""
        self.checkpoint_exists = False
        self.checkpoint = None
        self.cleared = True

    def set_checkpoint(self, checkpoint):
        """Set checkpoint for testing.

        Args:
            checkpoint: Checkpoint data
        """
        self.checkpoint = checkpoint
        self.checkpoint_exists = True
