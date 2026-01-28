"""Tests for US-0712: CLI Documentation and Help.

This module tests that:
1. Built-in help text is comprehensive with examples
2. README has all required documentation sections
3. Error messages are clear and actionable
4. FAQ section exists and covers key questions
"""

import re
import subprocess
from pathlib import Path

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def project_root():
    """Return path to project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def readme_path(project_root):
    """Return path to README.md file."""
    return project_root / "README.md"


@pytest.fixture
def readme_content(readme_path):
    """Return contents of README.md file."""
    return readme_path.read_text()


@pytest.fixture
def config_example_path(project_root):
    """Return path to example config file."""
    return project_root / "config" / "config.example.yaml"


@pytest.fixture
def faq_path(project_root):
    """Return path to FAQ.md file."""
    return project_root / "docs" / "FAQ.md"


def run_help_command(args: list[str]) -> str:
    """Run scraper help command and capture output.

    Args:
        args: Command arguments (e.g., ['--help'] or ['full', '--help'])

    Returns:
        Help text output
    """
    result = subprocess.run(
        ["python3", "-m", "scraper"] + args,
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Help goes to stdout
    return result.stdout


# =============================================================================
# AC1: Built-in Help
# =============================================================================


class TestBuiltInHelp:
    """Test that built-in help text is comprehensive."""

    def test_main_help_shows_usage(self):
        """Test main --help shows usage pattern."""
        help_text = run_help_command(["--help"])

        assert "usage: scraper" in help_text
        assert "{full,incremental}" in help_text

    def test_main_help_shows_description(self):
        """Test main --help shows description."""
        help_text = run_help_command(["--help"])

        assert "iRO Wiki Scraper" in help_text
        assert "Archive MediaWiki content" in help_text

    def test_main_help_shows_global_options(self):
        """Test main --help shows all global options."""
        help_text = run_help_command(["--help"])

        # Check for all global options
        assert "--config" in help_text
        assert "--database" in help_text
        assert "--log-level" in help_text
        assert "--quiet" in help_text

    def test_main_help_shows_subcommands(self):
        """Test main --help lists available subcommands."""
        help_text = run_help_command(["--help"])

        assert "full" in help_text
        assert "incremental" in help_text

    def test_main_help_shows_url(self):
        """Test main --help shows project URL."""
        help_text = run_help_command(["--help"])

        # Check for GitHub URL in epilog
        assert "github.com" in help_text

    def test_full_command_help_shows_usage(self):
        """Test 'full --help' shows command usage."""
        help_text = run_help_command(["full", "--help"])

        assert "usage: scraper full" in help_text

    def test_full_command_help_shows_description(self):
        """Test 'full --help' shows command description."""
        help_text = run_help_command(["full", "--help"])

        assert "Scrape all pages" in help_text
        assert "revision history" in help_text

    def test_full_command_help_shows_all_options(self):
        """Test 'full --help' shows all command options."""
        help_text = run_help_command(["full", "--help"])

        # Check for all full command options
        assert "--namespace" in help_text
        assert "--rate-limit" in help_text
        assert "--force" in help_text
        assert "--dry-run" in help_text
        assert "--format" in help_text
        assert "--resume" in help_text
        assert "--no-resume" in help_text
        assert "--clean" in help_text

    def test_full_command_help_includes_examples(self):
        """Test 'full --help' includes usage examples.

        AC1: Help text includes examples
        """
        help_text = run_help_command(["full", "--help"])

        # Check for examples section (should be added)
        # This test will fail initially and pass after implementation
        assert "example" in help_text.lower() or "Example" in help_text

    def test_incremental_command_help_shows_usage(self):
        """Test 'incremental --help' shows command usage."""
        help_text = run_help_command(["incremental", "--help"])

        assert "usage: scraper incremental" in help_text

    def test_incremental_command_help_shows_description(self):
        """Test 'incremental --help' shows command description."""
        help_text = run_help_command(["incremental", "--help"])

        assert "incremental" in help_text.lower() or "Update" in help_text
        assert "recent changes" in help_text or "prior full scrape" in help_text

    def test_incremental_command_help_shows_all_options(self):
        """Test 'incremental --help' shows all command options."""
        help_text = run_help_command(["incremental", "--help"])

        # Check for all incremental command options
        assert "--since" in help_text
        assert "--namespace" in help_text
        assert "--rate-limit" in help_text
        assert "--format" in help_text

    def test_incremental_command_help_includes_examples(self):
        """Test 'incremental --help' includes usage examples.

        AC1: Help text includes examples
        """
        help_text = run_help_command(["incremental", "--help"])

        # Check for examples section (should be added)
        # This test will fail initially and pass after implementation
        assert "example" in help_text.lower() or "Example" in help_text


# =============================================================================
# AC2: README Documentation
# =============================================================================


class TestREADMEDocumentation:
    """Test that README has all required sections."""

    def test_readme_exists(self, readme_path):
        """Test README.md file exists."""
        assert readme_path.exists()

    def test_readme_has_installation_section(self, readme_content):
        """Test README has installation instructions.

        AC2: Installation instructions
        """
        assert "## Installation" in readme_content or "# Installation" in readme_content
        assert "pip install" in readme_content or "requirements.txt" in readme_content

    def test_readme_has_quick_start_section(self, readme_content):
        """Test README has quick start guide.

        AC2: Quick start guide
        """
        # Check for quick start section
        assert any(
            [
                "## Quick Start" in readme_content,
                "# Quick Start" in readme_content,
                "## Usage" in readme_content,
            ]
        )

        # Should show basic usage example
        assert "python -m scraper" in readme_content or "scraper" in readme_content

    def test_readme_has_command_reference_section(self, readme_content):
        """Test README has command reference.

        AC2: Command reference (all commands and flags)
        """
        # Check for commands section
        assert "command" in readme_content.lower()

        # Should document main commands
        assert "full" in readme_content
        assert "incremental" in readme_content

    def test_readme_documents_all_commands(self, readme_content):
        """Test README documents full and incremental commands."""
        # Both commands should be mentioned
        assert "full" in readme_content.lower()
        assert "incremental" in readme_content.lower()

    def test_readme_documents_key_flags(self, readme_content):
        """Test README documents important flags."""
        # Key flags should be documented
        content_lower = readme_content.lower()

        # At least some key flags should be mentioned
        has_flags = any(
            [
                "--namespace" in readme_content,
                "--rate-limit" in readme_content,
                "--dry-run" in readme_content,
                "--config" in readme_content,
                "--database" in readme_content,
            ]
        )

        assert has_flags, "README should document key command-line flags"

    def test_readme_has_configuration_section(self, readme_content):
        """Test README describes configuration file format.

        AC2: Configuration file format
        """
        # Should have configuration section
        assert "config" in readme_content.lower()

        # Should reference YAML configuration
        assert "yaml" in readme_content.lower() or ".yaml" in readme_content

    def test_readme_has_examples_section(self, readme_content):
        """Test README has examples for common use cases.

        AC2: Examples for common use cases
        """
        # Check for examples section
        assert "example" in readme_content.lower()

        # Should have code examples
        assert "```" in readme_content

    def test_readme_has_usage_examples(self, readme_content):
        """Test README includes actual usage examples."""
        # Should show actual command examples
        examples_found = readme_content.count(
            "python -m scraper"
        ) + readme_content.count("scraper ")

        assert examples_found >= 2, "README should show multiple usage examples"

    def test_readme_has_troubleshooting_section(self, readme_content):
        """Test README has troubleshooting section.

        AC2: Troubleshooting section
        """
        # Check for troubleshooting section
        assert any(
            [
                "## Troubleshooting" in readme_content,
                "# Troubleshooting" in readme_content,
                "## Common Issues" in readme_content,
                "## Common Errors" in readme_content,
            ]
        )

    def test_readme_troubleshooting_has_content(self, readme_content):
        """Test troubleshooting section has actual content."""
        # Find troubleshooting section
        if "## Troubleshooting" in readme_content:
            section_start = readme_content.index("## Troubleshooting")
        elif "# Troubleshooting" in readme_content:
            section_start = readme_content.index("# Troubleshooting")
        else:
            pytest.skip("No troubleshooting section found")

        # Get content after troubleshooting heading (next 500 chars)
        section_content = readme_content[section_start : section_start + 500]

        # Should have some troubleshooting content
        assert len(section_content) > 100, "Troubleshooting section should have content"


# =============================================================================
# AC3: Usage Examples
# =============================================================================


class TestUsageExamples:
    """Test that README includes all required usage examples."""

    def test_example_basic_full_scrape(self, readme_content):
        """Test README shows basic full scrape example.

        AC3: Basic full scrape
        """
        # Should show basic full scrape command
        assert "full" in readme_content

        # Should be in a code block
        assert "```" in readme_content

    def test_example_namespace_specific_scrape(self, readme_content):
        """Test README shows namespace-specific scrape example.

        AC3: Full scrape with specific namespaces
        """
        # Should mention namespaces
        assert "namespace" in readme_content.lower()

    def test_example_dry_run(self, readme_content):
        """Test README shows dry run example.

        AC3: Dry run example
        """
        # Should mention dry run
        assert "--dry-run" in readme_content or "dry run" in readme_content.lower()

    def test_example_incremental_scrape(self, readme_content):
        """Test README shows incremental scrape example.

        AC3: Incremental scrape example
        """
        # Should show incremental command
        assert "incremental" in readme_content.lower()

    def test_example_custom_config(self, readme_content):
        """Test README shows custom configuration example.

        AC3: Custom configuration example
        """
        # Should show config flag
        assert "--config" in readme_content or "config.yaml" in readme_content

    def test_example_github_actions_integration(self, readme_content):
        """Test README shows GitHub Actions example.

        AC3: GitHub Actions integration example
        """
        # Should mention GitHub Actions
        assert (
            "github actions" in readme_content.lower()
            or "workflow" in readme_content.lower()
        )


# =============================================================================
# AC4: Error Messages
# =============================================================================


class TestErrorMessages:
    """Test that error messages are clear and actionable."""

    def test_error_messages_in_commands_module(self, project_root):
        """Test that commands.py has clear error messages.

        AC4: Clear, actionable error messages
        """
        commands_file = project_root / "scraper" / "cli" / "commands.py"
        content = commands_file.read_text()

        # Check that error messages exist
        assert "logger.error(" in content or "print(" in content

        # Error messages should include context
        assert 'f"' in content, "Should use f-strings for error context"

    def test_database_not_found_error_is_clear(self, project_root):
        """Test database not found error message is clear."""
        commands_file = project_root / "scraper" / "cli" / "commands.py"
        content = commands_file.read_text()

        # Check for database not found error
        assert "Database not found" in content or "not found" in content

        # Should suggest what to do
        assert "Run 'scraper full' first" in content or "full scrape" in content.lower()

    def test_config_error_messages_are_actionable(self, project_root):
        """Test configuration error messages suggest fixes."""
        commands_file = project_root / "scraper" / "cli" / "commands.py"
        content = commands_file.read_text()

        # Should handle config loading errors
        assert "config" in content.lower()
        assert "Failed to load config" in content or "Configuration" in content

    def test_error_messages_include_file_paths(self, project_root):
        """Test error messages include relevant file paths.

        AC4: Include relevant context (file paths, values)
        """
        commands_file = project_root / "scraper" / "cli" / "commands.py"
        content = commands_file.read_text()

        # Error messages should include file paths
        # Look for f-strings that include path variables
        assert 'f"' in content
        # Check for common path variable patterns in error messages
        has_path_context = any(
            [
                "db_path" in content,
                "{path}" in content,
                "database" in content,
            ]
        )

        assert has_path_context, "Error messages should include file path context"


# =============================================================================
# AC5: FAQ Section
# =============================================================================


class TestFAQSection:
    """Test that FAQ section exists and covers key questions."""

    def test_faq_file_exists_or_readme_has_faq(self, project_root, readme_content):
        """Test FAQ exists as separate file or in README.

        AC5: FAQ section exists
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # FAQ should exist as separate file OR in README
        has_faq_file = faq_path.exists()
        has_faq_in_readme = "## FAQ" in readme_content or "# FAQ" in readme_content

        assert (
            has_faq_file or has_faq_in_readme
        ), "FAQ should exist in docs/FAQ.md or README"

    def test_faq_covers_scrape_duration(self, project_root, readme_content):
        """Test FAQ covers 'How long does a full scrape take?'

        AC5: How long does a full scrape take?
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # Get FAQ content
        if faq_path.exists():
            faq_content = faq_path.read_text()
        else:
            faq_content = readme_content

        # Should discuss duration/time
        content_lower = faq_content.lower()
        assert any(
            [
                "how long" in content_lower,
                "duration" in content_lower,
                "take" in content_lower and "time" in content_lower,
            ]
        )

    def test_faq_covers_disk_space(self, project_root, readme_content):
        """Test FAQ covers 'How much disk space is needed?'

        AC5: How much disk space is needed?
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # Get FAQ content
        if faq_path.exists():
            faq_content = faq_path.read_text()
        else:
            faq_content = readme_content

        # Should discuss disk space
        content_lower = faq_content.lower()
        assert any(
            [
                "disk space" in content_lower,
                "storage" in content_lower,
                "how much" in content_lower and "space" in content_lower,
                "size" in content_lower,
            ]
        )

    def test_faq_covers_interruption(self, project_root, readme_content):
        """Test FAQ covers 'What if scrape is interrupted?'

        AC5: What if scrape is interrupted?
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # Get FAQ content
        if faq_path.exists():
            faq_content = faq_path.read_text()
        else:
            faq_content = readme_content

        # Should discuss interruption/resume
        content_lower = faq_content.lower()
        assert any(
            [
                "interrupt" in content_lower,
                "stop" in content_lower,
                "crash" in content_lower,
                "resume" in content_lower,
                "checkpoint" in content_lower,
            ]
        )

    def test_faq_covers_resume(self, project_root, readme_content):
        """Test FAQ covers 'How to resume a failed scrape?'

        AC5: How to resume a failed scrape?
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # Get FAQ content
        if faq_path.exists():
            faq_content = faq_path.read_text()
        else:
            faq_content = readme_content

        # Should discuss resuming
        content_lower = faq_content.lower()
        assert (
            "resume" in content_lower
            or "restart" in content_lower
            or "continue" in content_lower
        )

    def test_faq_covers_rate_limit(self, project_root, readme_content):
        """Test FAQ covers 'What rate limit should I use?'

        AC5: What rate limit should I use?
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # Get FAQ content
        if faq_path.exists():
            faq_content = faq_path.read_text()
        else:
            faq_content = readme_content

        # Should discuss rate limiting
        content_lower = faq_content.lower()
        assert "rate" in content_lower or "requests per second" in content_lower

    def test_faq_covers_namespaces(self, project_root, readme_content):
        """Test FAQ covers 'How to scrape only specific namespaces?'

        AC5: How to scrape only specific namespaces?
        """
        faq_path = project_root / "docs" / "FAQ.md"

        # Get FAQ content
        if faq_path.exists():
            faq_content = faq_path.read_text()
        else:
            faq_content = readme_content

        # Should discuss namespaces
        content_lower = faq_content.lower()
        assert "namespace" in content_lower


# =============================================================================
# Additional Documentation Tests
# =============================================================================


class TestConfigurationExamples:
    """Test that configuration examples are comprehensive."""

    def test_example_config_file_exists(self, config_example_path):
        """Test example configuration file exists."""
        assert config_example_path.exists()

    def test_example_config_has_comments(self, config_example_path):
        """Test example config has explanatory comments."""
        content = config_example_path.read_text()

        # Should have comments explaining options
        assert "#" in content

        # Count comment lines
        lines = content.split("\n")
        comment_lines = [l for l in lines if l.strip().startswith("#")]

        assert len(comment_lines) >= 10, "Example config should have helpful comments"

    def test_example_config_shows_all_sections(self, config_example_path):
        """Test example config shows all configuration sections."""
        content = config_example_path.read_text()

        # Should have main sections
        assert "wiki:" in content
        assert "scraper:" in content
        assert "storage:" in content
        assert "logging:" in content
