"""Tests for IncrementalCheckpoint."""

import pytest
from datetime import datetime
from pathlib import Path
import json

from scraper.incremental.checkpoint import (
    IncrementalCheckpoint,
    IncrementalCheckpointState,
)


@pytest.fixture
def checkpoint_dir(tmp_path):
    """Create temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    return checkpoint_dir


@pytest.fixture
def checkpoint(checkpoint_dir):
    """Create IncrementalCheckpoint instance."""
    return IncrementalCheckpoint(checkpoint_dir)


class TestIncrementalCheckpointState:
    """Tests for IncrementalCheckpointState dataclass."""

    def test_init_default(self):
        """Test default initialization."""
        state = IncrementalCheckpointState()

        assert state.completed_new_pages == set()
        assert state.completed_modified_pages == set()
        assert state.completed_deleted_pages == set()
        assert state.completed_moved_pages == set()
        assert state.current_phase == "init"
        assert state.run_id == 0
        assert isinstance(state.last_updated, datetime)

    def test_total_completed(self):
        """Test total_completed property."""
        state = IncrementalCheckpointState(
            completed_new_pages={1, 2, 3},
            completed_modified_pages={10, 20},
            completed_deleted_pages={100},
            completed_moved_pages={50, 60},
        )

        assert state.total_completed == 8  # 3+2+1+2


class TestIncrementalCheckpoint:
    """Tests for IncrementalCheckpoint."""

    def test_init(self, checkpoint_dir):
        """Test initialization creates directory."""
        checkpoint = IncrementalCheckpoint(checkpoint_dir)

        assert checkpoint.checkpoint_dir == checkpoint_dir
        assert checkpoint.checkpoint_dir.exists()
        assert (
            checkpoint.checkpoint_file == checkpoint_dir / "incremental_checkpoint.json"
        )

    def test_exists_no_checkpoint(self, checkpoint):
        """Test exists returns False when no checkpoint."""
        assert not checkpoint.exists()

    def test_exists_with_checkpoint(self, checkpoint):
        """Test exists returns True when checkpoint exists."""
        # Save a checkpoint
        state = IncrementalCheckpointState(run_id=123)
        checkpoint.save(state)

        assert checkpoint.exists()

    def test_load_no_checkpoint(self, checkpoint):
        """Test loading when no checkpoint exists."""
        state = checkpoint.load()

        assert isinstance(state, IncrementalCheckpointState)
        assert state.run_id == 0
        assert state.total_completed == 0

    def test_save_and_load(self, checkpoint):
        """Test saving and loading checkpoint."""
        # Create state
        original_state = IncrementalCheckpointState(
            completed_new_pages={1, 2, 3},
            completed_modified_pages={10, 20},
            current_phase="modified_pages",
            run_id=123,
        )

        # Save
        checkpoint.save(original_state)

        # Load
        loaded_state = checkpoint.load()

        assert loaded_state.completed_new_pages == {1, 2, 3}
        assert loaded_state.completed_modified_pages == {10, 20}
        assert loaded_state.current_phase == "modified_pages"
        assert loaded_state.run_id == 123

    def test_save_updates_last_updated(self, checkpoint):
        """Test that save updates last_updated timestamp."""
        state = IncrementalCheckpointState(run_id=123)
        original_time = state.last_updated

        import time

        time.sleep(0.1)

        checkpoint.save(state)

        # last_updated should be updated
        assert state.last_updated > original_time

    def test_load_preserves_sets(self, checkpoint):
        """Test that sets are properly preserved."""
        original_state = IncrementalCheckpointState(completed_new_pages={1, 2, 3, 4, 5})

        checkpoint.save(original_state)
        loaded_state = checkpoint.load()

        assert loaded_state.completed_new_pages == {1, 2, 3, 4, 5}
        assert isinstance(loaded_state.completed_new_pages, set)

    def test_clear_removes_checkpoint(self, checkpoint):
        """Test that clear removes checkpoint file."""
        # Save a checkpoint
        state = IncrementalCheckpointState(run_id=123)
        checkpoint.save(state)

        assert checkpoint.exists()

        # Clear
        checkpoint.clear()

        assert not checkpoint.exists()

    def test_clear_when_no_checkpoint(self, checkpoint):
        """Test that clear doesn't fail when no checkpoint."""
        # Should not raise exception
        checkpoint.clear()

        assert not checkpoint.exists()

    def test_multiple_saves(self, checkpoint):
        """Test multiple saves overwrite previous."""
        # First save
        state1 = IncrementalCheckpointState(run_id=123, current_phase="new_pages")
        checkpoint.save(state1)

        # Second save with different data
        state2 = IncrementalCheckpointState(run_id=456, current_phase="modified_pages")
        checkpoint.save(state2)

        # Load should get second state
        loaded = checkpoint.load()
        assert loaded.run_id == 456
        assert loaded.current_phase == "modified_pages"

    def test_checkpoint_file_format(self, checkpoint):
        """Test that checkpoint file is valid JSON."""
        state = IncrementalCheckpointState(
            completed_new_pages={1, 2, 3},
            run_id=123,
        )

        checkpoint.save(state)

        # Read file directly
        data = json.loads(checkpoint.checkpoint_file.read_text())

        assert "completed_new_pages" in data
        assert "run_id" in data
        assert "current_phase" in data
        assert "last_updated" in data
        assert data["run_id"] == 123

    def test_load_handles_corrupted_checkpoint(self, checkpoint):
        """Test loading handles corrupted checkpoint file."""
        # Write invalid JSON
        checkpoint.checkpoint_file.write_text("{ invalid json }")

        # Should return empty state instead of crashing
        state = checkpoint.load()

        assert isinstance(state, IncrementalCheckpointState)
        assert state.run_id == 0


class TestCheckpointIntegration:
    """Integration tests for checkpoint functionality."""

    def test_resume_workflow(self, checkpoint):
        """Test realistic resume workflow."""
        # Simulate first run
        state = IncrementalCheckpointState(run_id=1, current_phase="new_pages")
        state.completed_new_pages = {1, 2, 3}
        checkpoint.save(state)

        # Simulate interruption and resume
        resumed_state = checkpoint.load()

        # Continue processing
        resumed_state.completed_new_pages.add(4)
        resumed_state.completed_new_pages.add(5)
        resumed_state.current_phase = "modified_pages"
        checkpoint.save(resumed_state)

        # Verify final state
        final_state = checkpoint.load()
        assert final_state.completed_new_pages == {1, 2, 3, 4, 5}
        assert final_state.current_phase == "modified_pages"

    def test_complete_workflow_with_cleanup(self, checkpoint):
        """Test complete workflow with checkpoint cleanup."""
        # Start scrape
        state = IncrementalCheckpointState(run_id=1)
        checkpoint.save(state)

        # Process some pages
        state.completed_new_pages = {1, 2, 3}
        state.current_phase = "new_pages"
        checkpoint.save(state)

        # Complete successfully
        state.current_phase = "complete"
        checkpoint.save(state)

        # Clean up
        checkpoint.clear()

        # Verify cleaned up
        assert not checkpoint.exists()

        # Loading should return fresh state
        new_state = checkpoint.load()
        assert new_state.run_id == 0
        assert new_state.total_completed == 0
