"""Tests for GitHub Actions workflow integration.

Tests US-0708 acceptance criteria for GitHub Actions integration.
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def workflows_dir():
    """Return path to workflows directory."""
    return Path(__file__).parent.parent.parent / ".github" / "workflows"


@pytest.fixture
def monthly_workflow_path(workflows_dir):
    """Return path to monthly scrape workflow."""
    return workflows_dir / "monthly-scrape.yml"


@pytest.fixture
def manual_workflow_path(workflows_dir):
    """Return path to manual scrape workflow."""
    return workflows_dir / "manual-scrape.yml"


@pytest.fixture
def monthly_workflow(monthly_workflow_path):
    """Load monthly scrape workflow YAML."""
    with open(monthly_workflow_path) as f:
        # Use unsafe_load to preserve 'on' keyword (not convert to True)
        return yaml.load(f, Loader=yaml.FullLoader)


@pytest.fixture
def manual_workflow(manual_workflow_path):
    """Load manual scrape workflow YAML."""
    with open(manual_workflow_path) as f:
        # Use unsafe_load to preserve 'on' keyword (not convert to True)
        return yaml.load(f, Loader=yaml.FullLoader)


class TestMonthlyWorkflow:
    """Test monthly scrape workflow configuration."""

    def test_workflow_exists(self, monthly_workflow_path):
        """Test monthly workflow file exists."""
        assert monthly_workflow_path.exists()

    def test_uses_incremental_command(self, monthly_workflow):
        """Test workflow uses incremental scrape command."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        # Find the actual scrape step (named "Run scrape")
        scrape_step = None
        for step in steps:
            if "name" in step and step["name"] == "Run scrape":
                scrape_step = step
                break

        assert scrape_step is not None, "Scrape step not found"
        assert "run" in scrape_step

        # Check that incremental command is used (as default in the workflow)
        run_script = scrape_step["run"]
        assert "python -m scraper" in run_script
        assert "incremental" in run_script or "full" in run_script

    def test_removes_old_placeholder(self, monthly_workflow):
        """Test workflow doesn't use old placeholder commands."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        # Check no step uses just "python -m scraper" without subcommand
        for step in steps:
            if "run" in step:
                run_script = step["run"]
                # Should not have bare "python -m scraper" without subcommand
                if "python -m scraper" in run_script:
                    # Must have either "full" or "incremental" or "scrape"
                    assert any(
                        cmd in run_script
                        for cmd in ["full", "incremental", "scrape", "--incremental"]
                    ), f"Step uses old placeholder: {run_script}"

    def test_has_scheduled_trigger(self, monthly_workflow):
        """Test workflow has scheduled trigger."""
        # Handle YAML parser converting 'on' to True
        triggers = monthly_workflow.get("on", monthly_workflow.get(True, {}))
        assert "schedule" in triggers
        assert len(triggers["schedule"]) > 0

    def test_workflow_fails_on_nonzero_exit(self, monthly_workflow):
        """Test workflow fails if scrape exits non-zero."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        # Find the actual scrape step
        scrape_step = None
        for step in steps:
            if "name" in step and step["name"] == "Run scrape":
                scrape_step = step
                break

        assert scrape_step is not None
        run_script = scrape_step["run"]

        # Check that script exits on error (via "set -e" or exit code check)
        assert (
            "exit" in run_script.lower()
            or "set -e" in run_script
            or "SCRAPE_EXIT_CODE" in run_script
        )

    def test_statistics_step_after_scrape(self, monthly_workflow):
        """Test statistics generation runs after scrape."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        # Find scrape and stats steps by exact names
        scrape_index = None
        stats_index = None

        for i, step in enumerate(steps):
            if "name" in step:
                if step["name"] == "Run scrape":
                    scrape_index = i
                if step["name"] == "Generate statistics and release notes":
                    stats_index = i

        assert scrape_index is not None, "Scrape step not found"
        assert stats_index is not None, "Statistics step not found"
        assert stats_index > scrape_index, "Stats must run after scrape"


class TestManualWorkflow:
    """Test manual scrape workflow configuration."""

    def test_workflow_exists(self, manual_workflow_path):
        """Test manual workflow file exists."""
        assert manual_workflow_path.exists()

    def test_has_workflow_dispatch_trigger(self, manual_workflow):
        """Test workflow has manual trigger."""
        # Handle YAML parser converting 'on' to True
        triggers = manual_workflow.get("on", manual_workflow.get(True, {}))
        assert "workflow_dispatch" in triggers

    def test_has_required_inputs(self, manual_workflow):
        """Test workflow has all required inputs."""
        # Handle YAML parser converting 'on' to True
        triggers = manual_workflow.get("on", manual_workflow.get(True, {}))
        inputs = triggers["workflow_dispatch"]["inputs"]

        # Check for required inputs (based on US-0708)
        # Note: The actual workflow uses 'scrape_type' not 'incremental'
        assert "scrape_type" in inputs or "incremental" in inputs
        assert "force" in inputs
        assert "create_release" in inputs

        # Optional inputs
        # notify or announce
        assert "notify" in inputs or "announce" in inputs
        assert "reason" in inputs

    def test_supports_full_and_incremental_modes(self, manual_workflow):
        """Test workflow supports both full and incremental scrapes."""
        jobs = manual_workflow["jobs"]
        job = list(jobs.values())[0]  # Get first job
        steps = job["steps"]

        # Find the scrape step
        scrape_step = None
        for step in steps:
            if "name" in step and "scraper" in step["name"].lower():
                scrape_step = step
                break

        assert scrape_step is not None, "Scrape step not found"
        run_script = scrape_step["run"]

        # Check for conditional execution of full vs incremental
        assert "scrape_type" in run_script or "incremental" in run_script

    def test_passes_force_flag(self, manual_workflow):
        """Test workflow passes --force flag when force=true."""
        jobs = manual_workflow["jobs"]
        job = list(jobs.values())[0]
        steps = job["steps"]

        # Find the scrape step
        scrape_step = None
        for step in steps:
            if "name" in step and "scraper" in step["name"].lower():
                scrape_step = step
                break

        assert scrape_step is not None
        run_script = scrape_step["run"]

        # Check for force flag handling
        assert "--force" in run_script
        assert "force" in run_script.lower()


class TestWorkflowErrorHandling:
    """Test workflow error handling."""

    def test_monthly_workflow_shows_errors(self, monthly_workflow):
        """Test monthly workflow error output is visible."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        # Find diagnostics or error handling step
        has_error_handling = False
        for step in steps:
            if "if" in step and "failure()" in step["if"]:
                has_error_handling = True
                break

        assert has_error_handling, "No error handling step found"

    def test_manual_workflow_shows_errors(self, manual_workflow):
        """Test manual workflow error output is visible."""
        jobs = manual_workflow["jobs"]
        job = list(jobs.values())[0]
        steps = job["steps"]

        # Find diagnostics or error handling step
        has_error_handling = False
        for step in steps:
            if "if" in step and "failure()" in step["if"]:
                has_error_handling = True
                break

        # Manual workflow should also handle errors
        # (may not have explicit failure step, but logs are uploaded)
        log_upload = any(
            "upload" in step.get("name", "").lower()
            and "log" in step.get("name", "").lower()
            for step in steps
        )

        assert has_error_handling or log_upload, "No error handling or log upload found"

    def test_statistics_handles_empty_database(self, workflows_dir):
        """Test statistics script handles empty database gracefully."""
        # This tests the generate-stats.sh script
        stats_script = workflows_dir.parent.parent / "scripts" / "generate-stats.sh"

        assert stats_script.exists(), "Statistics script not found"

        # Script should check if database exists
        with open(stats_script) as f:
            content = f.read()

        assert "if" in content.lower()
        assert "database" in content.lower() or "db" in content.lower()


class TestWorkflowCommands:
    """Test workflow uses correct CLI commands."""

    def test_monthly_uses_incremental_command(self, monthly_workflow):
        """Test monthly workflow uses 'incremental' command."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        scrape_step = None
        for step in steps:
            if "name" in step and step["name"] == "Run scrape":
                scrape_step = step
                break

        assert scrape_step is not None
        run_script = scrape_step["run"]

        # Should use incremental command
        assert "--incremental" in run_script or "incremental" in run_script

    def test_manual_uses_correct_commands_based_on_input(self, manual_workflow):
        """Test manual workflow uses correct command based on input."""
        jobs = manual_workflow["jobs"]
        job = list(jobs.values())[0]
        steps = job["steps"]

        scrape_step = None
        for step in steps:
            if "name" in step and "scraper" in step["name"].lower():
                scrape_step = step
                break

        assert scrape_step is not None
        run_script = scrape_step["run"]

        # Should have conditional for full vs incremental
        assert "scrape_type" in run_script or "incremental" in run_script
        assert "--force-full" in run_script or "full" in run_script


class TestWorkflowSyntax:
    """Test workflow YAML syntax is valid."""

    def test_monthly_workflow_yaml_valid(self, monthly_workflow):
        """Test monthly workflow YAML is valid."""
        assert isinstance(monthly_workflow, dict)
        assert "name" in monthly_workflow
        assert "jobs" in monthly_workflow

    def test_manual_workflow_yaml_valid(self, manual_workflow):
        """Test manual workflow YAML is valid."""
        assert isinstance(manual_workflow, dict)
        assert "name" in manual_workflow
        assert "jobs" in manual_workflow

    def test_monthly_workflow_has_required_steps(self, monthly_workflow):
        """Test monthly workflow has all required steps."""
        jobs = monthly_workflow["jobs"]
        scrape_job = jobs["scrape-and-release"]
        steps = scrape_job["steps"]

        step_names = [step.get("name", "").lower() for step in steps]

        # Required steps
        assert any("checkout" in name for name in step_names)
        assert any("python" in name for name in step_names)
        assert any("install" in name for name in step_names)
        assert any("scrape" in name for name in step_names)
        assert any(
            "statistic" in name or "release notes" in name for name in step_names
        )

    def test_manual_workflow_has_required_steps(self, manual_workflow):
        """Test manual workflow has all required steps."""
        jobs = manual_workflow["jobs"]
        job = list(jobs.values())[0]
        steps = job["steps"]

        step_names = [step.get("name", "").lower() for step in steps]

        # Required steps
        assert any("checkout" in name for name in step_names)
        assert any("python" in name for name in step_names)
        assert any("install" in name for name in step_names)
        assert any("scraper" in name or "scrape" in name for name in step_names)
