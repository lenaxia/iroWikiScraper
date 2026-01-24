"""Tests for ScrapeRunTracker."""

from datetime import datetime

from scraper.incremental.scrape_run_tracker import ScrapeRunTracker


class TestScrapeRunTracker:
    """Tests for ScrapeRunTracker initialization and basic operations."""

    def test_init(self, db):
        """Test initialization."""
        tracker = ScrapeRunTracker(db)

        assert tracker.db is db
        assert tracker.conn is not None

    def test_get_last_scrape_timestamp_no_runs(self, db):
        """Test getting timestamp when no scrape runs exist."""
        tracker = ScrapeRunTracker(db)

        timestamp = tracker.get_last_scrape_timestamp()

        assert timestamp is None

    def test_get_last_scrape_timestamp_with_completed_runs(self, db):
        """Test getting timestamp with completed runs."""
        tracker = ScrapeRunTracker(db)

        # Create and complete a run
        run_id = tracker.create_scrape_run("full")
        stats = {
            "pages_new": 100,
            "pages_modified": 0,
            "pages_deleted": 0,
            "revisions_added": 500,
            "files_downloaded": 50,
        }
        tracker.complete_scrape_run(run_id, stats)

        # Get timestamp
        timestamp = tracker.get_last_scrape_timestamp()

        assert timestamp is not None
        assert isinstance(timestamp, datetime)
        # Should be recent (within last minute)
        assert (datetime.utcnow() - timestamp).total_seconds() < 60

    def test_get_last_scrape_timestamp_ignores_failed_runs(self, db):
        """Test that failed runs don't count as last scrape."""
        tracker = ScrapeRunTracker(db)

        # Create and fail a run
        run_id = tracker.create_scrape_run("incremental")
        tracker.fail_scrape_run(run_id, "Test error")

        # Should still be None (no successful runs)
        timestamp = tracker.get_last_scrape_timestamp()

        assert timestamp is None

    def test_get_last_scrape_timestamp_returns_most_recent(self, db):
        """Test that most recent completed run is returned."""
        tracker = ScrapeRunTracker(db)

        # Create first run
        run_id1 = tracker.create_scrape_run("full")
        tracker.complete_scrape_run(run_id1, {"pages_new": 100})

        # Wait a bit
        import time

        time.sleep(0.1)

        # Create second run (more recent)
        run_id2 = tracker.create_scrape_run("incremental")
        tracker.complete_scrape_run(run_id2, {"pages_new": 10})

        # Should get timestamp from second run
        timestamp = tracker.get_last_scrape_timestamp()

        # Verify it's the more recent one
        run2_info = tracker.get_scrape_run_status(run_id2)
        assert timestamp == run2_info["end_time"]

    def test_create_scrape_run(self, db):
        """Test creating a new scrape run."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        assert isinstance(run_id, int)
        assert run_id > 0

        # Verify in database
        info = tracker.get_scrape_run_status(run_id)
        assert info is not None
        assert info["status"] == "running"
        assert info["start_time"] is not None
        assert info["end_time"] is None
        assert info["pages_scraped"] == 0
        assert info["revisions_scraped"] == 0
        assert info["files_downloaded"] == 0

    def test_create_multiple_scrape_runs(self, db):
        """Test creating multiple scrape runs."""
        tracker = ScrapeRunTracker(db)

        run_id1 = tracker.create_scrape_run("full")
        run_id2 = tracker.create_scrape_run("incremental")
        run_id3 = tracker.create_scrape_run("incremental")

        # IDs should be sequential
        assert run_id2 == run_id1 + 1
        assert run_id3 == run_id2 + 1

    def test_complete_scrape_run(self, db):
        """Test completing a scrape run with statistics."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        stats = {
            "pages_new": 10,
            "pages_modified": 20,
            "pages_deleted": 2,
            "pages_moved": 1,
            "revisions_added": 45,
            "files_downloaded": 5,
        }

        tracker.complete_scrape_run(run_id, stats)

        # Verify in database
        info = tracker.get_scrape_run_status(run_id)
        assert info["status"] == "completed"
        assert info["end_time"] is not None
        assert info["pages_scraped"] == 33  # 10+20+2+1
        assert info["revisions_scraped"] == 45
        assert info["files_downloaded"] == 5

    def test_complete_scrape_run_with_minimal_stats(self, db):
        """Test completing run with minimal statistics."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        # Minimal stats - missing fields should default to 0
        stats = {"pages_new": 5}

        tracker.complete_scrape_run(run_id, stats)

        info = tracker.get_scrape_run_status(run_id)
        assert info["status"] == "completed"
        assert info["pages_scraped"] == 5
        assert info["revisions_scraped"] == 0
        assert info["files_downloaded"] == 0

    def test_fail_scrape_run(self, db):
        """Test marking a scrape run as failed."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        error_msg = "API connection timeout"
        tracker.fail_scrape_run(run_id, error_msg)

        # Verify in database
        info = tracker.get_scrape_run_status(run_id)
        assert info["status"] == "failed"
        assert info["end_time"] is not None
        assert info["error_message"] == error_msg

    def test_get_scrape_run_status_not_found(self, db):
        """Test getting status for nonexistent run."""
        tracker = ScrapeRunTracker(db)

        info = tracker.get_scrape_run_status(999999)

        assert info is None

    def test_get_scrape_run_status_running(self, db):
        """Test getting status for running scrape."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        info = tracker.get_scrape_run_status(run_id)

        assert info["run_id"] == run_id
        assert info["status"] == "running"
        assert info["start_time"] is not None
        assert info["end_time"] is None
        assert info["error_message"] is None


class TestTimestampOrdering:
    """Tests for timestamp ordering and query performance."""

    def test_last_scrape_uses_end_time_not_start_time(self, db):
        """Test that last scrape uses end_time, not start_time."""
        tracker = ScrapeRunTracker(db)

        # Create run 1, complete it
        run_id1 = tracker.create_scrape_run("full")
        import time

        time.sleep(0.1)
        tracker.complete_scrape_run(run_id1, {"pages_new": 100})

        # Create run 2, complete it later
        run_id2 = tracker.create_scrape_run("incremental")
        time.sleep(0.1)
        tracker.complete_scrape_run(run_id2, {"pages_new": 10})

        # Last scrape should be run 2 (based on end_time)
        timestamp = tracker.get_last_scrape_timestamp()
        run2_info = tracker.get_scrape_run_status(run_id2)

        assert timestamp == run2_info["end_time"]

    def test_multiple_completed_runs_returns_latest(self, db):
        """Test with multiple completed runs."""
        tracker = ScrapeRunTracker(db)

        timestamps = []

        # Create 5 completed runs
        for i in range(5):
            run_id = tracker.create_scrape_run("incremental")
            import time

            time.sleep(0.05)  # Small delay to ensure different timestamps
            tracker.complete_scrape_run(run_id, {"pages_new": i})

            info = tracker.get_scrape_run_status(run_id)
            timestamps.append(info["end_time"])

        # Get last scrape timestamp
        last_timestamp = tracker.get_last_scrape_timestamp()

        # Should be the most recent (last in list)
        assert last_timestamp == timestamps[-1]


class TestStatisticsAccumulation:
    """Tests for statistics calculation and storage."""

    def test_pages_scraped_sums_all_page_types(self, db):
        """Test that pages_scraped correctly sums all page types."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        stats = {
            "pages_new": 10,
            "pages_modified": 20,
            "pages_deleted": 5,
            "pages_moved": 3,
            "revisions_added": 100,
        }

        tracker.complete_scrape_run(run_id, stats)

        info = tracker.get_scrape_run_status(run_id)

        # Should sum all page types: 10+20+5+3=38
        assert info["pages_scraped"] == 38

    def test_statistics_with_zero_values(self, db):
        """Test statistics when all values are zero."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")

        stats = {
            "pages_new": 0,
            "pages_modified": 0,
            "pages_deleted": 0,
            "revisions_added": 0,
            "files_downloaded": 0,
        }

        tracker.complete_scrape_run(run_id, stats)

        info = tracker.get_scrape_run_status(run_id)

        assert info["pages_scraped"] == 0
        assert info["revisions_scraped"] == 0
        assert info["files_downloaded"] == 0
        assert info["status"] == "completed"


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_complete_nonexistent_run(self, db):
        """Test completing a run that doesn't exist."""
        tracker = ScrapeRunTracker(db)

        # Should not raise exception (UPDATE with no matching rows)
        tracker.complete_scrape_run(999999, {"pages_new": 10})

        # Verify run doesn't exist
        info = tracker.get_scrape_run_status(999999)
        assert info is None

    def test_fail_nonexistent_run(self, db):
        """Test failing a run that doesn't exist."""
        tracker = ScrapeRunTracker(db)

        # Should not raise exception
        tracker.fail_scrape_run(999999, "Test error")

        # Verify run doesn't exist
        info = tracker.get_scrape_run_status(999999)
        assert info is None

    def test_complete_already_completed_run(self, db):
        """Test completing a run that's already completed."""
        tracker = ScrapeRunTracker(db)

        run_id = tracker.create_scrape_run("incremental")
        tracker.complete_scrape_run(run_id, {"pages_new": 10})

        # Get original end time
        info1 = tracker.get_scrape_run_status(run_id)
        original_end = info1["end_time"]

        import time

        time.sleep(0.1)

        # Complete again
        tracker.complete_scrape_run(run_id, {"pages_new": 20})

        # Should update (no error)
        info2 = tracker.get_scrape_run_status(run_id)
        assert info2["status"] == "completed"
        assert info2["pages_scraped"] == 20
        # End time should be updated
        assert info2["end_time"] != original_end


class TestEnhancedMetadataQueries:
    """Tests for Story 11 - Enhanced metadata queries."""

    def test_list_recent_runs_empty(self, db):
        """Test listing recent runs when none exist."""
        tracker = ScrapeRunTracker(db)

        runs = tracker.list_recent_runs()

        assert runs == []

    def test_list_recent_runs(self, db):
        """Test listing recent runs."""
        tracker = ScrapeRunTracker(db)

        # Create multiple runs
        run_ids = []
        for i in range(5):
            run_id = tracker.create_scrape_run("incremental")
            tracker.complete_scrape_run(run_id, {"pages_new": i * 10})
            run_ids.append(run_id)
            import time

            time.sleep(0.01)  # Ensure different timestamps

        # Get recent runs
        runs = tracker.list_recent_runs(limit=3)

        assert len(runs) == 3
        # Should be in reverse chronological order (most recent first)
        assert runs[0]["run_id"] == run_ids[4]
        assert runs[1]["run_id"] == run_ids[3]
        assert runs[2]["run_id"] == run_ids[2]

    def test_list_recent_runs_limit(self, db):
        """Test limit parameter for recent runs."""
        tracker = ScrapeRunTracker(db)

        # Create 10 runs
        for i in range(10):
            run_id = tracker.create_scrape_run("incremental")
            tracker.complete_scrape_run(run_id, {"pages_new": i})

        # Get with different limits
        runs_3 = tracker.list_recent_runs(limit=3)
        runs_7 = tracker.list_recent_runs(limit=7)
        runs_all = tracker.list_recent_runs(limit=100)

        assert len(runs_3) == 3
        assert len(runs_7) == 7
        assert len(runs_all) == 10

    def test_list_recent_runs_includes_failed(self, db):
        """Test that recent runs includes failed runs."""
        tracker = ScrapeRunTracker(db)

        # Create mix of successful and failed runs
        run1 = tracker.create_scrape_run("incremental")
        tracker.complete_scrape_run(run1, {"pages_new": 10})

        run2 = tracker.create_scrape_run("incremental")
        tracker.fail_scrape_run(run2, "Test error")

        run3 = tracker.create_scrape_run("incremental")
        tracker.complete_scrape_run(run3, {"pages_new": 5})

        runs = tracker.list_recent_runs()

        assert len(runs) == 3
        statuses = [r["status"] for r in runs]
        assert "completed" in statuses
        assert "failed" in statuses

    def test_get_run_statistics_empty(self, db):
        """Test statistics when no runs exist."""
        tracker = ScrapeRunTracker(db)

        stats = tracker.get_run_statistics()

        assert stats["total_runs"] == 0
        assert stats["completed_runs"] == 0
        assert stats["failed_runs"] == 0
        assert stats["total_pages"] == 0
        assert stats["total_revisions"] == 0
        assert stats["total_files"] == 0

    def test_get_run_statistics(self, db):
        """Test aggregate statistics calculation."""
        tracker = ScrapeRunTracker(db)

        # Create multiple runs with different statistics
        run1 = tracker.create_scrape_run("full")
        tracker.complete_scrape_run(
            run1,
            {
                "pages_new": 100,
                "pages_modified": 0,
                "revisions_added": 500,
                "files_downloaded": 50,
            },
        )

        run2 = tracker.create_scrape_run("incremental")
        tracker.complete_scrape_run(
            run2,
            {
                "pages_new": 10,
                "pages_modified": 20,
                "revisions_added": 45,
                "files_downloaded": 5,
            },
        )

        run3 = tracker.create_scrape_run("incremental")
        tracker.fail_scrape_run(run3, "Test error")

        stats = tracker.get_run_statistics()

        assert stats["total_runs"] == 3
        assert stats["completed_runs"] == 2
        assert stats["failed_runs"] == 1
        assert stats["total_pages"] == 130  # 100 + 30
        assert stats["total_revisions"] == 545  # 500 + 45
        assert stats["total_files"] == 55  # 50 + 5

    def test_get_run_statistics_with_only_failed(self, db):
        """Test statistics when only failed runs exist."""
        tracker = ScrapeRunTracker(db)

        run1 = tracker.create_scrape_run("incremental")
        tracker.fail_scrape_run(run1, "Error 1")

        run2 = tracker.create_scrape_run("incremental")
        tracker.fail_scrape_run(run2, "Error 2")

        stats = tracker.get_run_statistics()

        assert stats["total_runs"] == 2
        assert stats["completed_runs"] == 0
        assert stats["failed_runs"] == 2
        # Failed runs should have 0 for all counts
        assert stats["total_pages"] == 0
        assert stats["total_revisions"] == 0
        assert stats["total_files"] == 0
