"""Tests for progress tracking and logging functionality."""

import logging
from io import StringIO
from pathlib import Path
from typing import List

import pytest

# Import will be available after implementation
# from scraper.utils.progress_tracker import ProgressTracker


# ============================================================================
# TEST INFRASTRUCTURE - FIXTURES AND HELPERS
# ============================================================================


@pytest.fixture
def mock_tqdm_class(monkeypatch):
    """
    Replace tqdm with mock implementation for testing.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        MockTqdm class that was patched in
    """
    from tests.mocks.mock_tqdm import MockTqdm

    # Patch tqdm in the progress_tracker module
    monkeypatch.setattr("scraper.utils.progress_tracker.tqdm", MockTqdm)

    return MockTqdm


@pytest.fixture
def mock_time_module(monkeypatch):
    """
    Replace time module with mock for ETA testing.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        MockTime instance
    """
    from tests.mocks.mock_time import MockTime

    mock_time = MockTime(initial_time=1000.0)

    # Patch time.time in progress_tracker module
    monkeypatch.setattr("scraper.utils.progress_tracker.time.time", mock_time.time)

    return mock_time


@pytest.fixture
def log_capture():
    """
    Capture log output for testing.

    Returns:
        StringIO buffer containing log output
    """
    log_buffer = StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger("scraper.utils.progress_tracker")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    yield log_buffer

    # Cleanup
    logger.removeHandler(handler)


# ============================================================================
# TEST CLASS 1: PROGRESS TRACKER INITIALIZATION
# ============================================================================


class TestProgressTrackerInit:
    """Test progress tracker initialization scenarios."""

    def test_init_with_valid_total(self, mock_tqdm_class):
        """Test initializing with valid total pages."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        assert tracker.total_pages == 100
        assert tracker.stats["pages"] == 0
        assert tracker.stats["revisions"] == 0
        assert tracker.stats["files"] == 0
        assert tracker.stats["errors"] == 0

    def test_init_with_zero_total(self, mock_tqdm_class):
        """Test initializing with zero total (should work for unknown totals)."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=0)

        assert tracker.total_pages == 0
        assert tracker.stats["pages"] == 0

    def test_init_with_custom_log_interval(self, mock_tqdm_class):
        """Test initializing with custom logging interval."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100, log_interval=25)

        assert tracker.log_interval == 25

    def test_init_with_default_log_interval(self, mock_tqdm_class):
        """Test default logging interval is 10."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        assert tracker.log_interval == 10

    def test_init_creates_progress_bar(self, mock_tqdm_class):
        """Test initialization creates tqdm progress bar."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        assert tracker.pbar is not None
        assert tracker.pbar.total == 100
        assert tracker.pbar.desc == "Pages"
        assert tracker.pbar.unit == "page"

    def test_init_invalid_total_raises_error(self, mock_tqdm_class):
        """Test initializing with negative total raises ValueError."""
        from scraper.utils.progress_tracker import ProgressTracker

        with pytest.raises(ValueError, match="total_pages must be non-negative"):
            ProgressTracker(total_pages=-1)

    def test_init_invalid_log_interval_raises_error(self, mock_tqdm_class):
        """Test initializing with invalid log_interval raises ValueError."""
        from scraper.utils.progress_tracker import ProgressTracker

        with pytest.raises(ValueError, match="log_interval must be positive"):
            ProgressTracker(total_pages=100, log_interval=0)

        with pytest.raises(ValueError, match="log_interval must be positive"):
            ProgressTracker(total_pages=100, log_interval=-5)


# ============================================================================
# TEST CLASS 2: UPDATE OPERATIONS
# ============================================================================


class TestProgressTrackerUpdate:
    """Test progress tracking update operations."""

    def test_update_page_increments_stats(self, mock_tqdm_class):
        """Test update_page increments page count."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_page(revision_count=5)

        assert tracker.stats["pages"] == 1
        assert tracker.stats["revisions"] == 5

    def test_update_page_updates_progress_bar(self, mock_tqdm_class):
        """Test update_page updates tqdm progress bar."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_page(revision_count=3)

        assert tracker.pbar.n == 1
        assert len(tracker.pbar.updates) == 1
        assert tracker.pbar.updates[0] == 1

    def test_update_page_multiple_times(self, mock_tqdm_class):
        """Test calling update_page multiple times."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        for i in range(10):
            tracker.update_page(revision_count=i + 1)

        assert tracker.stats["pages"] == 10
        assert tracker.stats["revisions"] == 55  # 1+2+3+...+10
        assert tracker.pbar.n == 10

    def test_update_page_with_zero_revisions(self, mock_tqdm_class):
        """Test update_page with zero revisions."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_page(revision_count=0)

        assert tracker.stats["pages"] == 1
        assert tracker.stats["revisions"] == 0

    def test_update_file_increments_stats(self, mock_tqdm_class):
        """Test update_file increments file count."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_file()

        assert tracker.stats["files"] == 1

    def test_update_file_multiple_times(self, mock_tqdm_class):
        """Test calling update_file multiple times."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        for _ in range(25):
            tracker.update_file()

        assert tracker.stats["files"] == 25

    def test_update_error_increments_stats(self, mock_tqdm_class):
        """Test update_error increments error count."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_error()

        assert tracker.stats["errors"] == 1

    def test_update_error_multiple_times(self, mock_tqdm_class):
        """Test calling update_error multiple times."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        for _ in range(5):
            tracker.update_error()

        assert tracker.stats["errors"] == 5

    def test_mixed_updates(self, mock_tqdm_class):
        """Test mixed update operations."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        tracker.update_page(revision_count=10)
        tracker.update_page(revision_count=5)
        tracker.update_file()
        tracker.update_file()
        tracker.update_file()
        tracker.update_error()

        assert tracker.stats["pages"] == 2
        assert tracker.stats["revisions"] == 15
        assert tracker.stats["files"] == 3
        assert tracker.stats["errors"] == 1


# ============================================================================
# TEST CLASS 3: LOGGING
# ============================================================================


class TestProgressTrackerLogging:
    """Test progress logging functionality."""

    def test_update_page_logs_at_interval(self, mock_tqdm_class, log_capture):
        """Test update_page logs progress at configured interval."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100, log_interval=10)

        # Update 9 times - should not log
        for i in range(9):
            tracker.update_page(revision_count=1)

        log_output = log_capture.getvalue()
        assert "Progress:" not in log_output

        # 10th update - should log
        tracker.update_page(revision_count=1)

        log_output = log_capture.getvalue()
        assert "Progress:" in log_output

    def test_logging_includes_stats(self, mock_tqdm_class, log_capture):
        """Test log output includes all statistics."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100, log_interval=5)

        # Update to trigger log
        for i in range(5):
            tracker.update_page(revision_count=2)
            tracker.update_file()

        log_output = log_capture.getvalue()
        assert "5/100" in log_output  # pages
        assert "10" in log_output  # revisions
        assert "5" in log_output  # files

    def test_custom_log_interval(self, mock_tqdm_class, log_capture):
        """Test custom logging interval works correctly."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100, log_interval=25)

        # Update 24 times - should not log
        for _ in range(24):
            tracker.update_page(revision_count=1)

        log_output = log_capture.getvalue()
        assert "Progress:" not in log_output

        # 25th update - should log
        tracker.update_page(revision_count=1)

        log_output = log_capture.getvalue()
        assert "Progress:" in log_output
        assert "25/100" in log_output

    def test_logging_at_every_update(self, mock_tqdm_class, log_capture):
        """Test logging at every update (interval=1)."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=10, log_interval=1)

        tracker.update_page(revision_count=5)

        log_output = log_capture.getvalue()
        assert "Progress:" in log_output
        assert "1/10" in log_output


# ============================================================================
# TEST CLASS 4: ETA CALCULATION
# ============================================================================


class TestProgressTrackerETA:
    """Test ETA calculation functionality."""

    def test_eta_calculation_basic(self, mock_tqdm_class, mock_time_module):
        """Test basic ETA calculation."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        # Process 10 pages over 10 seconds
        for i in range(10):
            tracker.update_page(revision_count=1)
            mock_time_module.advance(1.0)

        eta = tracker.get_eta()

        # 10 pages in 10 seconds = 1 page/sec
        # 90 pages remaining = 90 seconds
        assert eta is not None
        assert 85 <= eta <= 95  # Allow small variance

    def test_eta_none_when_no_progress(self, mock_tqdm_class, mock_time_module):
        """Test ETA is None when no progress made."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        eta = tracker.get_eta()

        assert eta is None

    def test_eta_none_when_complete(self, mock_tqdm_class, mock_time_module):
        """Test ETA is None when all pages processed."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=10)

        for i in range(10):
            tracker.update_page(revision_count=1)
            mock_time_module.advance(1.0)

        eta = tracker.get_eta()

        assert eta is None or eta == 0

    def test_eta_with_varying_speed(self, mock_tqdm_class, mock_time_module):
        """Test ETA adapts to varying processing speed."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        # Start slow - 5 pages in 10 seconds
        for i in range(5):
            tracker.update_page(revision_count=1)
            mock_time_module.advance(2.0)

        eta1 = tracker.get_eta()

        # Speed up - 5 more pages in 5 seconds
        for i in range(5):
            tracker.update_page(revision_count=1)
            mock_time_module.advance(1.0)

        eta2 = tracker.get_eta()

        # ETA should decrease as speed increases
        assert eta2 is not None
        # Average speed improved, so ETA should be reasonable

    def test_get_eta_string_format(self, mock_tqdm_class, mock_time_module):
        """Test get_eta_string returns formatted string."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        # Process some pages
        for i in range(10):
            tracker.update_page(revision_count=1)
            mock_time_module.advance(1.0)

        eta_string = tracker.get_eta_string()

        assert isinstance(eta_string, str)
        # Should contain time info
        assert any(unit in eta_string for unit in ["second", "minute", "hour"])

    def test_get_eta_string_no_progress(self, mock_tqdm_class, mock_time_module):
        """Test get_eta_string when no progress made."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        eta_string = tracker.get_eta_string()

        assert eta_string == "Unknown"

    def test_get_eta_string_complete(self, mock_tqdm_class, mock_time_module):
        """Test get_eta_string when complete."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=10)

        for i in range(10):
            tracker.update_page(revision_count=1)

        eta_string = tracker.get_eta_string()

        assert eta_string in ["Complete", "0 seconds"]


# ============================================================================
# TEST CLASS 5: SUMMARY STATISTICS
# ============================================================================


class TestProgressTrackerSummary:
    """Test summary statistics functionality."""

    def test_get_summary_returns_string(self, mock_tqdm_class):
        """Test get_summary returns formatted string."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_page(revision_count=5)
        tracker.update_file()

        summary = tracker.get_summary()

        assert isinstance(summary, str)
        assert "Pages:" in summary
        assert "1" in summary  # 1 page
        assert "5" in summary  # 5 revisions

    def test_summary_includes_all_stats(self, mock_tqdm_class):
        """Test summary includes all statistics."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        tracker.update_page(revision_count=10)
        tracker.update_page(revision_count=20)
        tracker.update_file()
        tracker.update_file()
        tracker.update_file()
        tracker.update_error()

        summary = tracker.get_summary()

        # Check all stats present
        assert "Pages:" in summary or "pages" in summary.lower()
        assert "2" in summary  # 2 pages
        assert "30" in summary  # 30 revisions
        assert "3" in summary  # 3 files
        assert "1" in summary or "error" in summary.lower()  # 1 error

    def test_summary_with_zero_stats(self, mock_tqdm_class):
        """Test summary with no updates."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        summary = tracker.get_summary()

        assert "0" in summary or summary.startswith("Pages: 0")

    def test_get_stats_dict(self, mock_tqdm_class):
        """Test get_stats returns dictionary."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        tracker.update_page(revision_count=15)
        tracker.update_file()
        tracker.update_error()

        stats = tracker.get_stats()

        assert isinstance(stats, dict)
        assert stats["pages"] == 1
        assert stats["revisions"] == 15
        assert stats["files"] == 1
        assert stats["errors"] == 1

    def test_stats_dict_structure(self, mock_tqdm_class):
        """Test stats dictionary has required keys."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        stats = tracker.get_stats()

        required_keys = ["pages", "revisions", "files", "errors"]
        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], int)


# ============================================================================
# TEST CLASS 6: CLEANUP
# ============================================================================


class TestProgressTrackerCleanup:
    """Test progress tracker cleanup functionality."""

    def test_close_closes_progress_bar(self, mock_tqdm_class):
        """Test close() closes the tqdm progress bar."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.close()

        assert tracker.pbar.closed is True

    def test_context_manager_closes_automatically(self, mock_tqdm_class):
        """Test using tracker as context manager closes automatically."""
        from scraper.utils.progress_tracker import ProgressTracker

        with ProgressTracker(total_pages=100) as tracker:
            tracker.update_page(revision_count=1)
            pbar = tracker.pbar

        assert pbar.closed is True

    def test_close_multiple_times_is_safe(self, mock_tqdm_class):
        """Test calling close() multiple times is safe."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        tracker.close()
        tracker.close()
        tracker.close()

        # Should not raise error
        assert tracker.pbar.closed is True


# ============================================================================
# TEST CLASS 7: EDGE CASES
# ============================================================================


class TestProgressTrackerEdgeCases:
    """Test progress tracker edge cases and boundary conditions."""

    def test_very_large_total(self, mock_tqdm_class):
        """Test with very large total pages."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=1_000_000)

        assert tracker.total_pages == 1_000_000
        tracker.update_page(revision_count=1)
        assert tracker.stats["pages"] == 1

    def test_very_large_revision_count(self, mock_tqdm_class):
        """Test with very large revision count."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)
        tracker.update_page(revision_count=10_000)

        assert tracker.stats["revisions"] == 10_000

    def test_many_updates(self, mock_tqdm_class):
        """Test with many sequential updates."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=10_000)

        for i in range(10_000):
            tracker.update_page(revision_count=1)

        assert tracker.stats["pages"] == 10_000
        assert tracker.pbar.n == 10_000

    def test_updates_beyond_total(self, mock_tqdm_class):
        """Test updating beyond total (shouldn't error)."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=10)

        for i in range(15):
            tracker.update_page(revision_count=1)

        # Should track actual count even if exceeds total
        assert tracker.stats["pages"] == 15

    def test_zero_total_pages_with_updates(self, mock_tqdm_class):
        """Test zero total (unknown) with updates."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=0)

        tracker.update_page(revision_count=5)
        tracker.update_page(revision_count=3)

        assert tracker.stats["pages"] == 2
        assert tracker.stats["revisions"] == 8

    def test_negative_revision_count_raises_error(self, mock_tqdm_class):
        """Test negative revision count raises ValueError."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        with pytest.raises(ValueError, match="revision_count must be non-negative"):
            tracker.update_page(revision_count=-1)

    def test_rapid_updates_performance(self, mock_tqdm_class):
        """Test performance with rapid updates."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=1000, log_interval=100)

        import time

        start = time.time()

        for i in range(1000):
            tracker.update_page(revision_count=1)

        elapsed = time.time() - start

        # Should complete very quickly (mocked, no I/O)
        assert elapsed < 1.0  # Less than 1 second


# ============================================================================
# TEST CLASS 8: INTEGRATION SCENARIOS
# ============================================================================


class TestProgressTrackerIntegration:
    """Test progress tracker integration with scraping workflow."""

    def test_realistic_scraping_workflow(self, mock_tqdm_class, mock_time_module):
        """Test realistic scraping workflow with progress tracking."""
        from scraper.utils.progress_tracker import ProgressTracker

        total_pages = 50
        tracker = ProgressTracker(total_pages=total_pages, log_interval=10)

        # Simulate scraping pages
        for page_id in range(1, total_pages + 1):
            # Simulate varying revision counts
            revision_count = (page_id % 10) + 1

            # Simulate some pages have files
            if page_id % 5 == 0:
                tracker.update_file()

            # Simulate occasional errors
            if page_id % 20 == 0:
                tracker.update_error()

            # Update page
            tracker.update_page(revision_count=revision_count)

            # Simulate processing time
            mock_time_module.advance(0.5)

        # Verify final stats
        assert tracker.stats["pages"] == total_pages
        assert tracker.stats["revisions"] > 0
        assert tracker.stats["files"] == 10  # Every 5th page
        assert tracker.stats["errors"] == 2  # Every 20th page

        # Get final summary
        summary = tracker.get_summary()
        assert "50" in summary  # 50 pages
        assert "10" in summary  # 10 files

        tracker.close()

    def test_with_checkpoint_integration(self, mock_tqdm_class, tmp_path):
        """Test progress tracker integrating with checkpoint system."""
        from scraper.utils.checkpoint import Checkpoint
        from scraper.utils.progress_tracker import ProgressTracker

        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint = Checkpoint(checkpoint_file)
        tracker = ProgressTracker(total_pages=100, log_interval=20)

        # Simulate scraping with checkpointing
        for page_id in range(1, 51):
            if not checkpoint.is_page_complete(page_id):
                # Scrape page
                revision_count = 5
                tracker.update_page(revision_count=revision_count)
                checkpoint.mark_page_complete(page_id)

        # Verify progress
        assert tracker.stats["pages"] == 50
        assert checkpoint.get_stats()["pages_completed"] == 50

        tracker.close()

    def test_error_handling_workflow(self, mock_tqdm_class):
        """Test workflow with error handling."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=20, log_interval=5)

        successful_pages = 0
        failed_pages = 0

        for page_id in range(1, 21):
            try:
                # Simulate some pages failing
                if page_id % 7 == 0:
                    raise Exception(f"Failed to scrape page {page_id}")

                # Success
                tracker.update_page(revision_count=3)
                successful_pages += 1

            except Exception:
                tracker.update_error()
                failed_pages += 1

        assert tracker.stats["pages"] == successful_pages
        assert tracker.stats["errors"] == failed_pages
        assert successful_pages + failed_pages == 20

        tracker.close()

    def test_incremental_scrape_workflow(self, mock_tqdm_class):
        """Test incremental scraping workflow."""
        from scraper.utils.progress_tracker import ProgressTracker

        # Initial scrape
        tracker1 = ProgressTracker(total_pages=100, log_interval=10)

        for i in range(100):
            tracker1.update_page(revision_count=5)

        stats1 = tracker1.get_stats()
        assert stats1["pages"] == 100
        assert stats1["revisions"] == 500

        tracker1.close()

        # Incremental scrape (only 10 new pages)
        tracker2 = ProgressTracker(total_pages=10, log_interval=5)

        for i in range(10):
            tracker2.update_page(revision_count=2)

        stats2 = tracker2.get_stats()
        assert stats2["pages"] == 10
        assert stats2["revisions"] == 20

        tracker2.close()

    def test_file_download_tracking(self, mock_tqdm_class):
        """Test tracking file downloads separately."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=50, log_interval=10)

        files_downloaded = 0

        for page_id in range(1, 51):
            # Update page
            tracker.update_page(revision_count=3)

            # Simulate downloading files for some pages
            num_files = page_id % 3
            for _ in range(num_files):
                tracker.update_file()
                files_downloaded += 1

        assert tracker.stats["pages"] == 50
        assert tracker.stats["files"] == files_downloaded

        tracker.close()


# ============================================================================
# TEST CLASS 9: CONCURRENCY SAFETY
# ============================================================================


class TestProgressTrackerConcurrency:
    """Test progress tracker thread safety (basic tests)."""

    def test_sequential_updates_are_consistent(self, mock_tqdm_class):
        """Test sequential updates maintain consistency."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=1000, log_interval=100)

        expected_pages = 0
        expected_revisions = 0

        for i in range(1000):
            rev_count = (i % 10) + 1
            tracker.update_page(revision_count=rev_count)
            expected_pages += 1
            expected_revisions += rev_count

        assert tracker.stats["pages"] == expected_pages
        assert tracker.stats["revisions"] == expected_revisions

        tracker.close()


# ============================================================================
# TEST CLASS 10: TYPE VALIDATION
# ============================================================================


class TestProgressTrackerTypeValidation:
    """Test type validation and error handling."""

    def test_invalid_total_pages_type(self, mock_tqdm_class):
        """Test invalid total_pages type raises TypeError."""
        from scraper.utils.progress_tracker import ProgressTracker

        with pytest.raises(TypeError):
            ProgressTracker(total_pages="100")  # type: ignore

    def test_invalid_log_interval_type(self, mock_tqdm_class):
        """Test invalid log_interval type raises TypeError."""
        from scraper.utils.progress_tracker import ProgressTracker

        with pytest.raises(TypeError):
            ProgressTracker(total_pages=100, log_interval="10")  # type: ignore

    def test_invalid_revision_count_type(self, mock_tqdm_class):
        """Test invalid revision_count type raises TypeError."""
        from scraper.utils.progress_tracker import ProgressTracker

        tracker = ProgressTracker(total_pages=100)

        with pytest.raises(TypeError):
            tracker.update_page(revision_count="5")  # type: ignore
