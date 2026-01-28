"""
E2E and Integration Test Quick Reference
=========================================

This file provides quick commands for running the comprehensive E2E and integration tests.
"""

# Run all E2E tests
pytest tests/e2e/ -v

# Run all integration tests
pytest tests/integration/ -v

# Run both E2E and integration tests
pytest tests/e2e/ tests/integration/ -v

# Run specific E2E test
pytest tests/e2e/test_cli_full_workflow.py::TestE2EFullScrapeWorkflow::test_full_scrape_complete_workflow -v

# Run with coverage
pytest tests/e2e/ tests/integration/ --cov=scraper --cov-report=html

# Run with detailed output
pytest tests/e2e/ tests/integration/ -vv -s

# Run only passing tests (skip known failures)
pytest tests/e2e/ tests/integration/ -v --tb=no -x

# Run and show test collection
pytest tests/e2e/ tests/integration/ --collect-only

# Quick Summary of Test Files
# ============================

# tests/e2e/test_cli_full_workflow.py
# - 14 tests covering complete CLI workflows
# - Tests: full scrape, dry run, resume, error recovery, config precedence, etc.
# - Uses real Database, real CheckpointManager, mock network only

# tests/integration/test_orchestration_integration.py  
# - 15 tests covering component integration
# - Tests: database integration, checkpoint integration, retry logic, progress tracking
# - Uses real components with minimal mocking

# Test Status Quick Check
# =======================
# E2E Tests:           7 passing, 2 failing, 5 skipped (50% pass rate)
# Integration Tests:   3 passing, 12 failing (20% pass rate)
# Total:               10 passing, 14 failing, 5 skipped

# Known Issues (See E2E_TEST_SUMMARY.md for details)
# ===================================================
# 1. Mock config objects need fixing (8 tests)
# 2. Checkpoint persistence issues (2 tests)
# 3. Retry logic not catching errors (3 tests)
# 4. Checkpoint corruption handling (2 tests)
