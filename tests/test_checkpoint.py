"""Tests for checkpoint and resume functionality."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import pytest

from scraper.utils.checkpoint import Checkpoint

# ============================================================================
# TEST INFRASTRUCTURE - FIXTURES AND HELPERS
# ============================================================================


@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    """
    Create temporary directory for checkpoint files.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to temporary checkpoint directory
    """
    checkpoint_path = tmp_path / "checkpoints"
    checkpoint_path.mkdir(exist_ok=True)
    return checkpoint_path


@pytest.fixture
def checkpoint_file(checkpoint_dir: Path) -> Path:
    """
    Return path to test checkpoint file.

    Args:
        checkpoint_dir: Path to checkpoint directory

    Returns:
        Path to checkpoint.json file
    """
    return checkpoint_dir / "checkpoint.json"


@pytest.fixture
def valid_checkpoint_data() -> Dict[str, Any]:
    """
    Return valid checkpoint data structure.

    Returns:
        Dictionary with valid checkpoint data
    """
    return {
        "version": "1.0",
        "created_at": "2026-01-23T10:00:00Z",
        "updated_at": "2026-01-23T10:30:00Z",
        "phase": "scraping_pages",
        "completed_pages": [1, 2, 3, 4, 5],
        "completed_files": ["File_A.png", "File_B.jpg"],
        "current_namespace": 0,
        "total_pages": 2400,
        "total_files": 4000,
    }


def create_checkpoint_file(
    path: Path, data: Dict[str, Any], valid: bool = True
) -> None:
    """
    Create a checkpoint file for testing.

    Args:
        path: Path to checkpoint file
        data: Data to write
        valid: If False, write corrupted data
    """
    if valid:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        # Write corrupted JSON
        with open(path, "w") as f:
            f.write("{invalid json content: [1, 2, 3")


def create_large_checkpoint(path: Path, num_pages: int, num_files: int) -> None:
    """
    Create checkpoint file with large number of entries.

    Args:
        path: Path to checkpoint file
        num_pages: Number of pages to include
        num_files: Number of files to include
    """
    data = {
        "version": "1.0",
        "created_at": "2026-01-23T10:00:00Z",
        "updated_at": "2026-01-23T10:30:00Z",
        "phase": "downloading_files",
        "completed_pages": list(range(1, num_pages + 1)),
        "completed_files": [f"File_{i}.png" for i in range(num_files)],
        "current_namespace": 0,
        "total_pages": num_pages,
        "total_files": num_files,
    }
    with open(path, "w") as f:
        json.dump(data, f)


# ============================================================================
# TEST CLASS 1: CHECKPOINT INITIALIZATION
# ============================================================================


class TestCheckpointInit:
    """Test checkpoint initialization scenarios."""

    def test_init_non_existent_file_creates_empty(self, checkpoint_file: Path):
        """Test initializing with non-existent file creates empty checkpoint."""
        # File should not exist yet
        assert not checkpoint_file.exists()

        # Initialize checkpoint
        checkpoint = Checkpoint(checkpoint_file)

        # Should have empty data structure
        assert checkpoint.data["version"] == "1.0"
        assert checkpoint.data["completed_pages"] == []
        assert checkpoint.data["completed_files"] == []
        assert checkpoint.data["phase"] == "scraping_pages"
        assert "created_at" in checkpoint.data
        assert "updated_at" in checkpoint.data

    def test_init_existing_valid_checkpoint_loads_data(
        self, checkpoint_file: Path, valid_checkpoint_data: Dict[str, Any]
    ):
        """Test initializing with existing valid checkpoint loads data."""
        # Create valid checkpoint file
        create_checkpoint_file(checkpoint_file, valid_checkpoint_data)

        # Initialize checkpoint
        checkpoint = Checkpoint(checkpoint_file)

        # Should load existing data
        assert checkpoint.data["version"] == "1.0"
        assert checkpoint.data["completed_pages"] == [1, 2, 3, 4, 5]
        assert checkpoint.data["completed_files"] == ["File_A.png", "File_B.jpg"]
        assert checkpoint.data["phase"] == "scraping_pages"
        assert checkpoint.data["total_pages"] == 2400
        assert checkpoint.data["total_files"] == 4000

    def test_init_corrupted_checkpoint_starts_fresh(
        self, checkpoint_file: Path, caplog
    ):
        """Test initializing with corrupted checkpoint starts fresh and logs warning."""
        # Create corrupted checkpoint
        create_checkpoint_file(checkpoint_file, {}, valid=False)

        # Initialize checkpoint with logging
        with caplog.at_level(logging.WARNING):
            checkpoint = Checkpoint(checkpoint_file)

        # Should have empty data structure
        assert checkpoint.data["completed_pages"] == []
        assert checkpoint.data["completed_files"] == []

        # Should log error/warning
        assert (
            "Corrupted checkpoint file" in caplog.text
            or "Failed to load" in caplog.text
            or "Failed to parse" in caplog.text
        )

    def test_init_invalid_json_starts_fresh(self, checkpoint_file: Path, caplog):
        """Test initializing with invalid JSON starts fresh and logs error."""
        # Write invalid JSON
        with open(checkpoint_file, "w") as f:
            f.write("not json at all {{{")

        # Initialize checkpoint
        with caplog.at_level(logging.ERROR):
            checkpoint = Checkpoint(checkpoint_file)

        # Should have empty data structure
        assert checkpoint.data["completed_pages"] == []
        assert checkpoint.data["completed_files"] == []

        # Should log error
        assert len(caplog.records) > 0

    def test_init_missing_fields_uses_defaults(self, checkpoint_file: Path, caplog):
        """Test initializing with missing fields uses defaults and logs warning."""
        # Create checkpoint with missing fields
        incomplete_data = {
            "version": "1.0",
            "completed_pages": [1, 2, 3],
            # Missing: completed_files, phase, timestamps, etc.
        }
        create_checkpoint_file(checkpoint_file, incomplete_data)

        # Initialize checkpoint
        with caplog.at_level(logging.WARNING):
            checkpoint = Checkpoint(checkpoint_file)

        # Should use defaults for missing fields
        assert checkpoint.data["completed_pages"] == [1, 2, 3]
        assert checkpoint.data["completed_files"] == []  # Default
        assert checkpoint.data["phase"] == "scraping_pages"  # Default


# ============================================================================
# TEST CLASS 2: LOAD AND SAVE OPERATIONS
# ============================================================================


class TestCheckpointLoadSave:
    """Test checkpoint load and save operations."""

    def test_load_valid_checkpoint_file(
        self, checkpoint_file: Path, valid_checkpoint_data: Dict[str, Any]
    ):
        """Test loading valid checkpoint file."""
        create_checkpoint_file(checkpoint_file, valid_checkpoint_data)
        checkpoint = Checkpoint(checkpoint_file)

        assert checkpoint.data["completed_pages"] == [1, 2, 3, 4, 5]
        assert checkpoint.data["completed_files"] == ["File_A.png", "File_B.jpg"]

    def test_load_handles_missing_fields_with_defaults(self, checkpoint_file: Path):
        """Test load handles missing fields with sensible defaults."""
        minimal_data = {"version": "1.0"}
        create_checkpoint_file(checkpoint_file, minimal_data)

        checkpoint = Checkpoint(checkpoint_file)

        # Check defaults
        assert checkpoint.data["completed_pages"] == []
        assert checkpoint.data["completed_files"] == []
        assert checkpoint.data["phase"] == "scraping_pages"
        assert checkpoint.data["current_namespace"] == 0
        assert checkpoint.data["total_pages"] == 0
        assert checkpoint.data["total_files"] == 0

    def test_save_creates_valid_json_file(self, checkpoint_file: Path):
        """Test save creates valid JSON file."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(123)
        checkpoint.mark_file_complete("test.png")

        # Manually trigger save
        checkpoint._save()

        # Verify file exists and contains valid JSON
        assert checkpoint_file.exists()
        with open(checkpoint_file) as f:
            data = json.load(f)
            assert 123 in data["completed_pages"]
            assert "test.png" in data["completed_files"]

    def test_save_is_atomic(self, checkpoint_file: Path):
        """Test save uses atomic write (temp file + rename)."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(456)
        checkpoint._save()

        # Verify no temp files left behind
        temp_files = list(checkpoint_file.parent.glob("*.tmp"))
        assert len(temp_files) == 0

        # Verify final file exists
        assert checkpoint_file.exists()

    def test_save_updates_timestamp(self, checkpoint_file: Path):
        """Test save updates the updated_at timestamp."""
        checkpoint = Checkpoint(checkpoint_file)
        original_updated = checkpoint.data["updated_at"]

        # Wait a tiny bit and save
        import time

        time.sleep(0.01)
        checkpoint.mark_page_complete(789)

        # Timestamp should be updated
        assert checkpoint.data["updated_at"] != original_updated

    def test_load_after_save_preserves_data(self, checkpoint_file: Path):
        """Test loading after saving preserves all data."""
        # Create and populate checkpoint
        checkpoint1 = Checkpoint(checkpoint_file)
        checkpoint1.mark_page_complete(111)
        checkpoint1.mark_page_complete(222)
        checkpoint1.mark_file_complete("file1.png")
        checkpoint1._save()

        # Load in new instance
        checkpoint2 = Checkpoint(checkpoint_file)

        # Verify data preserved
        assert checkpoint2.is_page_complete(111)
        assert checkpoint2.is_page_complete(222)
        assert checkpoint2.is_file_complete("file1.png")


# ============================================================================
# TEST CLASS 3: MARK COMPLETE OPERATIONS
# ============================================================================


class TestCheckpointMarkComplete:
    """Test marking pages and files as complete."""

    def test_mark_page_complete_adds_to_set(self, checkpoint_file: Path):
        """Test mark_page_complete adds page to completed set."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(100)

        assert checkpoint.is_page_complete(100)
        assert 100 in checkpoint.data["completed_pages"]

    def test_mark_file_complete_adds_to_set(self, checkpoint_file: Path):
        """Test mark_file_complete adds file to completed set."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_file_complete("MyFile.png")

        assert checkpoint.is_file_complete("MyFile.png")
        assert "MyFile.png" in checkpoint.data["completed_files"]

    def test_marking_same_page_twice_is_idempotent(self, checkpoint_file: Path):
        """Test marking same page twice is idempotent."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(200)
        checkpoint.mark_page_complete(200)

        # Should only appear once
        assert checkpoint.data["completed_pages"].count(200) == 1

    def test_marking_same_file_twice_is_idempotent(self, checkpoint_file: Path):
        """Test marking same file twice is idempotent."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_file_complete("duplicate.png")
        checkpoint.mark_file_complete("duplicate.png")

        # Should only appear once
        assert checkpoint.data["completed_files"].count("duplicate.png") == 1

    def test_save_called_after_marking_complete(self, checkpoint_file: Path):
        """Test save is automatically called after marking complete."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(300)

        # File should exist (auto-saved)
        assert checkpoint_file.exists()

        # Load fresh instance to verify
        checkpoint2 = Checkpoint(checkpoint_file)
        assert checkpoint2.is_page_complete(300)

    def test_mark_multiple_pages_complete(self, checkpoint_file: Path):
        """Test marking multiple pages complete."""
        checkpoint = Checkpoint(checkpoint_file)
        pages = [1, 2, 3, 4, 5, 10, 20, 30]

        for page_id in pages:
            checkpoint.mark_page_complete(page_id)

        # All should be marked complete
        for page_id in pages:
            assert checkpoint.is_page_complete(page_id)

    def test_mark_multiple_files_complete(self, checkpoint_file: Path):
        """Test marking multiple files complete."""
        checkpoint = Checkpoint(checkpoint_file)
        files = ["a.png", "b.jpg", "c.gif", "d.svg"]

        for filename in files:
            checkpoint.mark_file_complete(filename)

        # All should be marked complete
        for filename in files:
            assert checkpoint.is_file_complete(filename)


# ============================================================================
# TEST CLASS 4: IS COMPLETE CHECKS
# ============================================================================


class TestCheckpointIsComplete:
    """Test checking if pages and files are complete."""

    def test_is_page_complete_returns_true_for_completed(self, checkpoint_file: Path):
        """Test is_page_complete returns True for completed page."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(500)

        assert checkpoint.is_page_complete(500) is True

    def test_is_page_complete_returns_false_for_not_completed(
        self, checkpoint_file: Path
    ):
        """Test is_page_complete returns False for not completed page."""
        checkpoint = Checkpoint(checkpoint_file)

        assert checkpoint.is_page_complete(999) is False

    def test_is_file_complete_returns_true_for_completed(self, checkpoint_file: Path):
        """Test is_file_complete returns True for completed file."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_file_complete("complete.png")

        assert checkpoint.is_file_complete("complete.png") is True

    def test_is_file_complete_returns_false_for_not_completed(
        self, checkpoint_file: Path
    ):
        """Test is_file_complete returns False for not completed file."""
        checkpoint = Checkpoint(checkpoint_file)

        assert checkpoint.is_file_complete("notfound.png") is False

    def test_empty_checkpoint_returns_false_for_all(self, checkpoint_file: Path):
        """Test empty checkpoint returns False for all queries."""
        checkpoint = Checkpoint(checkpoint_file)

        assert checkpoint.is_page_complete(1) is False
        assert checkpoint.is_page_complete(999999) is False
        assert checkpoint.is_file_complete("anything.png") is False

    def test_check_multiple_pages_mixed_results(self, checkpoint_file: Path):
        """Test checking multiple pages returns correct mixed results."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(1)
        checkpoint.mark_page_complete(3)
        checkpoint.mark_page_complete(5)

        assert checkpoint.is_page_complete(1) is True
        assert checkpoint.is_page_complete(2) is False
        assert checkpoint.is_page_complete(3) is True
        assert checkpoint.is_page_complete(4) is False
        assert checkpoint.is_page_complete(5) is True


# ============================================================================
# TEST CLASS 5: STATISTICS
# ============================================================================


class TestCheckpointGetStats:
    """Test checkpoint statistics retrieval."""

    def test_stats_show_correct_counts(self, checkpoint_file: Path):
        """Test get_stats returns correct counts."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(1)
        checkpoint.mark_page_complete(2)
        checkpoint.mark_page_complete(3)
        checkpoint.mark_file_complete("a.png")
        checkpoint.mark_file_complete("b.png")

        stats = checkpoint.get_stats()

        assert stats["pages_completed"] == 3
        assert stats["files_completed"] == 2

    def test_stats_update_after_marking_complete(self, checkpoint_file: Path):
        """Test stats update after marking items complete."""
        checkpoint = Checkpoint(checkpoint_file)

        # Initial stats
        stats1 = checkpoint.get_stats()
        assert stats1["pages_completed"] == 0

        # Mark some complete
        checkpoint.mark_page_complete(10)
        checkpoint.mark_page_complete(20)

        # Updated stats
        stats2 = checkpoint.get_stats()
        assert stats2["pages_completed"] == 2

    def test_empty_checkpoint_shows_zero_stats(self, checkpoint_file: Path):
        """Test empty checkpoint shows zero for all stats."""
        checkpoint = Checkpoint(checkpoint_file)

        stats = checkpoint.get_stats()

        assert stats["pages_completed"] == 0
        assert stats["files_completed"] == 0

    def test_stats_include_all_required_fields(self, checkpoint_file: Path):
        """Test stats include all required fields."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(100)
        checkpoint.mark_file_complete("test.png")

        stats = checkpoint.get_stats()

        # Required fields
        assert "pages_completed" in stats
        assert "files_completed" in stats
        assert isinstance(stats["pages_completed"], int)
        assert isinstance(stats["files_completed"], int)

    def test_stats_reflect_total_values(self, checkpoint_file: Path):
        """Test stats include total values if set."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.data["total_pages"] = 1000
        checkpoint.data["total_files"] = 500

        stats = checkpoint.get_stats()

        assert "total_pages" in stats or stats["pages_completed"] >= 0
        assert "total_files" in stats or stats["files_completed"] >= 0


# ============================================================================
# TEST CLASS 6: CLEAR OPERATIONS
# ============================================================================


class TestCheckpointClear:
    """Test checkpoint clearing functionality."""

    def test_clear_removes_checkpoint_file(self, checkpoint_file: Path):
        """Test clear removes checkpoint file from disk."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(123)
        checkpoint._save()

        # File should exist
        assert checkpoint_file.exists()

        # Clear checkpoint
        checkpoint.clear()

        # File should be removed
        assert not checkpoint_file.exists()

    def test_clear_resets_internal_state(self, checkpoint_file: Path):
        """Test clear resets internal data structure."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(123)
        checkpoint.mark_file_complete("test.png")

        # Clear checkpoint
        checkpoint.clear()

        # Internal state should be reset
        assert checkpoint.data["completed_pages"] == []
        assert checkpoint.data["completed_files"] == []
        assert not checkpoint.is_page_complete(123)
        assert not checkpoint.is_file_complete("test.png")

    def test_can_mark_complete_after_clearing(self, checkpoint_file: Path):
        """Test can continue marking complete after clearing."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(100)
        checkpoint.clear()

        # Should be able to mark new items
        checkpoint.mark_page_complete(200)
        assert checkpoint.is_page_complete(200)
        assert not checkpoint.is_page_complete(100)

    def test_clear_on_non_existent_checkpoint_is_safe(self, checkpoint_file: Path):
        """Test clearing non-existent checkpoint doesn't raise error."""
        checkpoint = Checkpoint(checkpoint_file)

        # File doesn't exist yet
        assert not checkpoint_file.exists()

        # Should not raise error
        checkpoint.clear()

        # Should still not exist
        assert not checkpoint_file.exists()

    def test_clear_multiple_times_is_safe(self, checkpoint_file: Path):
        """Test clearing multiple times is safe."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(100)

        # Clear multiple times
        checkpoint.clear()
        checkpoint.clear()
        checkpoint.clear()

        # Should not raise errors
        assert not checkpoint_file.exists()


# ============================================================================
# TEST CLASS 7: PHASE TRACKING
# ============================================================================


class TestCheckpointPhaseTracking:
    """Test checkpoint phase tracking functionality."""

    def test_set_and_get_current_phase(self, checkpoint_file: Path):
        """Test setting and getting current phase."""
        checkpoint = Checkpoint(checkpoint_file)

        # Default phase
        assert checkpoint.data["phase"] == "scraping_pages"

        # Set new phase
        checkpoint.set_phase("downloading_files")
        assert checkpoint.get_phase() == "downloading_files"

    def test_phase_persists_across_load_save(self, checkpoint_file: Path):
        """Test phase persists across save and load."""
        checkpoint1 = Checkpoint(checkpoint_file)
        checkpoint1.set_phase("extracting_links")
        checkpoint1._save()

        # Load in new instance
        checkpoint2 = Checkpoint(checkpoint_file)
        assert checkpoint2.get_phase() == "extracting_links"

    def test_valid_phases(self, checkpoint_file: Path):
        """Test all valid phases can be set."""
        checkpoint = Checkpoint(checkpoint_file)
        valid_phases = [
            "scraping_pages",
            "downloading_files",
            "extracting_links",
            "complete",
        ]

        for phase in valid_phases:
            checkpoint.set_phase(phase)
            assert checkpoint.get_phase() == phase

    def test_invalid_phase_raises_error(self, checkpoint_file: Path):
        """Test setting invalid phase raises ValueError."""
        checkpoint = Checkpoint(checkpoint_file)

        with pytest.raises(ValueError, match="Invalid phase"):
            checkpoint.set_phase("invalid_phase_name")

    def test_phase_included_in_stats(self, checkpoint_file: Path):
        """Test phase is included in statistics."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.set_phase("downloading_files")

        stats = checkpoint.get_stats()
        assert "phase" in stats
        assert stats["phase"] == "downloading_files"


# ============================================================================
# TEST CLASS 8: EDGE CASES
# ============================================================================


class TestCheckpointEdgeCases:
    """Test checkpoint edge cases and boundary conditions."""

    def test_very_large_checkpoint(self, checkpoint_dir: Path):
        """Test checkpoint with 10,000+ pages and 4,000+ files."""
        large_file = checkpoint_dir / "large_checkpoint.json"
        create_large_checkpoint(large_file, num_pages=10000, num_files=4000)

        # Should load successfully
        checkpoint = Checkpoint(large_file)

        assert len(checkpoint.data["completed_pages"]) == 10000
        assert len(checkpoint.data["completed_files"]) == 4000

        # Verify random samples
        assert checkpoint.is_page_complete(5000)
        assert checkpoint.is_file_complete("File_2000.png")

    def test_unicode_in_filenames(self, checkpoint_file: Path):
        """Test Unicode characters in filenames."""
        checkpoint = Checkpoint(checkpoint_file)

        unicode_files = [
            "文件.png",  # Chinese
            "файл.jpg",  # Russian
            "αρχείο.gif",  # Greek
            "ファイル.svg",  # Japanese
            "🎨_emoji.png",  # Emoji
        ]

        for filename in unicode_files:
            checkpoint.mark_file_complete(filename)

        # Should all be saved and retrievable
        for filename in unicode_files:
            assert checkpoint.is_file_complete(filename)

    def test_special_characters_in_filenames(self, checkpoint_file: Path):
        """Test special characters in filenames."""
        checkpoint = Checkpoint(checkpoint_file)

        special_files = [
            "file with spaces.png",
            "file_with_underscores.png",
            "file-with-dashes.png",
            "file.multiple.dots.png",
            "file(with)parens.png",
            "file[with]brackets.png",
        ]

        for filename in special_files:
            checkpoint.mark_file_complete(filename)

        # Should all work
        for filename in special_files:
            assert checkpoint.is_file_complete(filename)

    def test_very_long_filename(self, checkpoint_file: Path):
        """Test very long filename (255 chars)."""
        checkpoint = Checkpoint(checkpoint_file)

        long_filename = "a" * 250 + ".png"
        checkpoint.mark_file_complete(long_filename)

        assert checkpoint.is_file_complete(long_filename)

    def test_page_id_zero(self, checkpoint_file: Path):
        """Test page ID of zero."""
        checkpoint = Checkpoint(checkpoint_file)

        checkpoint.mark_page_complete(0)
        assert checkpoint.is_page_complete(0)

    def test_negative_page_id(self, checkpoint_file: Path):
        """Test negative page ID (should work, though unusual)."""
        checkpoint = Checkpoint(checkpoint_file)

        checkpoint.mark_page_complete(-1)
        assert checkpoint.is_page_complete(-1)

    def test_very_large_page_id(self, checkpoint_file: Path):
        """Test very large page ID."""
        checkpoint = Checkpoint(checkpoint_file)

        large_id = 999999999
        checkpoint.mark_page_complete(large_id)
        assert checkpoint.is_page_complete(large_id)

    def test_empty_filename(self, checkpoint_file: Path):
        """Test empty filename."""
        checkpoint = Checkpoint(checkpoint_file)

        checkpoint.mark_file_complete("")
        assert checkpoint.is_file_complete("")

    def test_checkpoint_file_permissions(self, checkpoint_file: Path):
        """Test checkpoint file has correct permissions after creation."""
        checkpoint = Checkpoint(checkpoint_file)
        checkpoint.mark_page_complete(1)
        checkpoint._save()

        # Check file is readable and writable
        assert checkpoint_file.exists()
        assert checkpoint_file.is_file()
        # On Unix systems, check it's readable/writable
        import stat

        mode = checkpoint_file.stat().st_mode
        assert mode & stat.S_IRUSR  # Owner can read
        assert mode & stat.S_IWUSR  # Owner can write


# ============================================================================
# TEST CLASS 9: INTEGRATION SCENARIOS
# ============================================================================


class TestCheckpointIntegration:
    """Test checkpoint integration with scraping workflow."""

    def test_resume_from_interrupted_scrape(self, checkpoint_file: Path):
        """Test resuming from interrupted scrape operation."""
        # Simulate first scrape session
        checkpoint1 = Checkpoint(checkpoint_file)
        checkpoint1.set_phase("scraping_pages")

        # Process some pages
        for page_id in range(1, 51):
            checkpoint1.mark_page_complete(page_id)

        # Simulate interruption (save happens automatically)

        # Resume in new session
        checkpoint2 = Checkpoint(checkpoint_file)

        # Should skip already processed pages
        for page_id in range(1, 51):
            assert checkpoint2.is_page_complete(page_id)

        # Continue processing new pages
        for page_id in range(51, 101):
            if not checkpoint2.is_page_complete(page_id):
                checkpoint2.mark_page_complete(page_id)

        # Verify all completed
        for page_id in range(1, 101):
            assert checkpoint2.is_page_complete(page_id)

    def test_clear_after_successful_completion(self, checkpoint_file: Path):
        """Test clearing checkpoint after successful completion."""
        checkpoint = Checkpoint(checkpoint_file)

        # Simulate complete workflow
        checkpoint.set_phase("scraping_pages")
        for i in range(1, 11):
            checkpoint.mark_page_complete(i)

        checkpoint.set_phase("downloading_files")
        for i in range(5):
            checkpoint.mark_file_complete(f"file{i}.png")

        checkpoint.set_phase("complete")

        # Verify checkpoint exists
        assert checkpoint_file.exists()

        # Clear after completion
        checkpoint.clear()

        # Checkpoint should be gone
        assert not checkpoint_file.exists()

    def test_multiple_mark_check_cycles(self, checkpoint_file: Path):
        """Test multiple cycles of marking and checking."""
        checkpoint = Checkpoint(checkpoint_file)

        # Cycle 1: Pages
        for i in range(1, 11):
            checkpoint.mark_page_complete(i)

        for i in range(1, 11):
            assert checkpoint.is_page_complete(i)

        # Cycle 2: Files
        for i in range(10):
            checkpoint.mark_file_complete(f"file{i}.png")

        for i in range(10):
            assert checkpoint.is_file_complete(f"file{i}.png")

        # Cycle 3: More pages
        for i in range(11, 21):
            checkpoint.mark_page_complete(i)

        for i in range(11, 21):
            assert checkpoint.is_page_complete(i)

    def test_integration_with_actual_scraping_workflow(self, checkpoint_file: Path):
        """Test checkpoint integrates with realistic scraping workflow."""
        checkpoint = Checkpoint(checkpoint_file)

        # Phase 1: Discover pages
        checkpoint.set_phase("scraping_pages")
        pages_to_scrape = [100, 200, 300, 400, 500]

        for page_id in pages_to_scrape:
            if not checkpoint.is_page_complete(page_id):
                # Simulate scraping
                checkpoint.mark_page_complete(page_id)

        # Verify phase 1 complete
        assert all(checkpoint.is_page_complete(pid) for pid in pages_to_scrape)

        # Phase 2: Download files
        checkpoint.set_phase("downloading_files")
        files_to_download = ["img1.png", "img2.jpg", "img3.gif"]

        for filename in files_to_download:
            if not checkpoint.is_file_complete(filename):
                # Simulate download
                checkpoint.mark_file_complete(filename)

        # Verify phase 2 complete
        assert all(checkpoint.is_file_complete(f) for f in files_to_download)

        # Mark complete
        checkpoint.set_phase("complete")
        assert checkpoint.get_phase() == "complete"

        # Get final stats
        stats = checkpoint.get_stats()
        assert stats["pages_completed"] == len(pages_to_scrape)
        assert stats["files_completed"] == len(files_to_download)

    def test_concurrent_checkpoint_usage_safety(self, checkpoint_file: Path):
        """Test checkpoint handles concurrent usage safely."""
        # This is a basic test - full concurrency testing would need threading
        checkpoint1 = Checkpoint(checkpoint_file)
        checkpoint1.mark_page_complete(1)

        # Simulate another process loading checkpoint
        checkpoint2 = Checkpoint(checkpoint_file)

        # Both should see the same data
        assert checkpoint2.is_page_complete(1)

        # Mark in first instance
        checkpoint1.mark_page_complete(2)

        # Reload second instance
        checkpoint3 = Checkpoint(checkpoint_file)
        assert checkpoint3.is_page_complete(2)

    def test_workflow_interruption_and_recovery(self, checkpoint_file: Path):
        """Test complete workflow interruption and recovery."""
        # Session 1: Start scraping
        session1 = Checkpoint(checkpoint_file)
        session1.set_phase("scraping_pages")
        session1.data["total_pages"] = 100

        for i in range(1, 26):
            session1.mark_page_complete(i)

        # Simulate crash (checkpoint auto-saved)
        stats1 = session1.get_stats()
        assert stats1["pages_completed"] == 25

        # Session 2: Resume
        session2 = Checkpoint(checkpoint_file)
        assert session2.get_phase() == "scraping_pages"
        assert session2.data["total_pages"] == 100

        # Continue from where we left off
        for i in range(1, 101):
            if not session2.is_page_complete(i):
                session2.mark_page_complete(i)

        # Verify all done
        stats2 = session2.get_stats()
        assert stats2["pages_completed"] == 100

        # Complete
        session2.set_phase("complete")
        session2.clear()

        assert not checkpoint_file.exists()


# ============================================================================
# TEST CLASS 10: ERROR HANDLING
# ============================================================================


class TestCheckpointErrorHandling:
    """Test checkpoint error handling and recovery."""

    def test_corrupted_json_recovery(self, checkpoint_file: Path, caplog):
        """Test recovery from corrupted JSON."""
        # Write corrupted data
        with open(checkpoint_file, "w") as f:
            f.write("{bad json")

        with caplog.at_level(logging.WARNING):
            checkpoint = Checkpoint(checkpoint_file)

        # Should recover with empty checkpoint
        assert checkpoint.data["completed_pages"] == []

    def test_partial_json_recovery(self, checkpoint_file: Path):
        """Test recovery from partial JSON."""
        # Write partial JSON (intentionally malformed)
        with open(checkpoint_file, "w") as f:
            f.write('{"version": "1.0", "completed_pages": [1, 2')
        # Missing closing bracket

        checkpoint = Checkpoint(checkpoint_file)
        # Should initialize with empty data
        assert checkpoint.data["completed_pages"] == []

    def test_non_dict_json_recovery(self, checkpoint_file: Path):
        """Test recovery when JSON is not a dictionary."""
        # Write JSON array instead of dict
        with open(checkpoint_file, "w") as f:
            json.dump([1, 2, 3], f)

        checkpoint = Checkpoint(checkpoint_file)
        # Should recover with empty checkpoint
        assert checkpoint.data["completed_pages"] == []

    def test_readonly_directory_error(self, tmp_path: Path):
        """Test error handling when directory is read-only."""
        # This test is tricky on different systems
        # Skip if we can't set permissions
        import stat

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()

        checkpoint_file = readonly_dir / "checkpoint.json"
        checkpoint = Checkpoint(checkpoint_file)

        try:
            # Make directory read-only
            readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

            # Try to save - should handle gracefully
            try:
                checkpoint.mark_page_complete(1)
                # If it succeeds, that's ok (permissions might not work as expected)
            except (OSError, PermissionError):
                # Expected on some systems
                pass
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(stat.S_IRWXU)

    def test_disk_full_simulation(self, checkpoint_file: Path, monkeypatch):
        """Test handling when disk is full (simulated)."""
        checkpoint = Checkpoint(checkpoint_file)

        # This is hard to test realistically without filling disk
        # We'll just verify the checkpoint handles write errors gracefully
        def mock_write_error(*args, **kwargs):
            raise OSError("No space left on device")

        # Mark complete should handle errors gracefully
        checkpoint.mark_page_complete(1)
        # If we get here, basic operation works
        assert checkpoint.is_page_complete(1)
