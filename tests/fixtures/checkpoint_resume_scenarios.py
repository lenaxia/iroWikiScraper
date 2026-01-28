"""Test fixtures for checkpoint resume scenarios (US-0711)."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from scraper.storage.models import Page


def create_checkpoint_data(
    scrape_type: str = "full",
    namespaces: List[int] = None,
    namespaces_completed: List[int] = None,
    current_namespace: int = 0,
    pages_completed: List[int] = None,
    last_page_id: int = 0,
    rate_limit: float = 2.0,
) -> Dict[str, Any]:
    """Create checkpoint data for testing.

    Args:
        scrape_type: Type of scrape (full, incremental)
        namespaces: List of all namespaces to scrape
        namespaces_completed: List of completed namespaces
        current_namespace: Current namespace being scraped
        pages_completed: List of completed page IDs
        last_page_id: Last page ID processed
        rate_limit: Rate limit setting

    Returns:
        Dictionary with checkpoint data
    """
    if namespaces is None:
        namespaces = [0, 4, 6]
    if namespaces_completed is None:
        namespaces_completed = []
    if pages_completed is None:
        pages_completed = []

    return {
        "version": "1.0",
        "scrape_type": scrape_type,
        "started_at": "2025-01-24T10:00:00Z",
        "last_update": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "namespaces": namespaces,
            "rate_limit": rate_limit,
        },
        "progress": {
            "namespaces_completed": namespaces_completed,
            "current_namespace": current_namespace,
            "pages_completed": pages_completed,
            "last_page_id": last_page_id,
        },
        "statistics": {
            "pages_scraped": len(pages_completed),
            "revisions_scraped": len(pages_completed) * 5,  # Estimate
            "errors": 0,
        },
    }


def create_pages_for_namespace(namespace: int, count: int) -> List[Page]:
    """Create test pages for a namespace.

    Args:
        namespace: Namespace ID
        count: Number of pages to create

    Returns:
        List of Page objects
    """
    pages = []
    for i in range(count):
        page_id = namespace * 1000 + i + 1
        pages.append(
            Page(
                page_id=page_id,
                namespace=namespace,
                title=f"Test_Page_{namespace}_{i + 1}",
                is_redirect=False,
            )
        )
    return pages


def create_checkpoint_scenario_partial() -> Dict[str, Any]:
    """Create checkpoint for partially completed scrape.

    Scenario: Started scraping 3 namespaces (0, 4, 6),
    completed namespace 0, halfway through namespace 4.

    Returns:
        Dictionary with checkpoint data and test pages
    """
    # Namespace 0: 50 pages (all complete)
    # Namespace 4: 30 pages (15 complete)
    # Namespace 6: 40 pages (none complete)

    ns0_pages = create_pages_for_namespace(0, 50)
    ns4_pages = create_pages_for_namespace(4, 30)
    ns6_pages = create_pages_for_namespace(6, 40)

    completed_page_ids = [p.page_id for p in ns0_pages]  # All of ns 0
    completed_page_ids.extend([p.page_id for p in ns4_pages[:15]])  # Half of ns 4

    checkpoint = create_checkpoint_data(
        namespaces=[0, 4, 6],
        namespaces_completed=[0],
        current_namespace=4,
        pages_completed=completed_page_ids,
        last_page_id=ns4_pages[14].page_id,
    )

    return {
        "checkpoint": checkpoint,
        "all_pages": {
            0: ns0_pages,
            4: ns4_pages,
            6: ns6_pages,
        },
        "expected_skip": {
            0: ns0_pages,  # Skip all
            4: ns4_pages[:15],  # Skip first 15
            6: [],  # Skip none
        },
        "expected_scrape": {
            0: [],  # Already done
            4: ns4_pages[15:],  # Remaining 15
            6: ns6_pages,  # All 40
        },
    }


def create_checkpoint_scenario_single_namespace() -> Dict[str, Any]:
    """Create checkpoint for single namespace partially complete.

    Scenario: Scraping only namespace 0, completed 75 out of 100 pages.

    Returns:
        Dictionary with checkpoint data and test pages
    """
    ns0_pages = create_pages_for_namespace(0, 100)
    completed_page_ids = [p.page_id for p in ns0_pages[:75]]

    checkpoint = create_checkpoint_data(
        namespaces=[0],
        namespaces_completed=[],
        current_namespace=0,
        pages_completed=completed_page_ids,
        last_page_id=ns0_pages[74].page_id,
    )

    return {
        "checkpoint": checkpoint,
        "all_pages": {0: ns0_pages},
        "expected_skip": {0: ns0_pages[:75]},
        "expected_scrape": {0: ns0_pages[75:]},
    }


def create_checkpoint_scenario_fresh() -> Dict[str, Any]:
    """Create scenario with no checkpoint (fresh start).

    Returns:
        Dictionary with test pages and no checkpoint
    """
    ns0_pages = create_pages_for_namespace(0, 20)
    ns4_pages = create_pages_for_namespace(4, 15)

    return {
        "checkpoint": None,
        "all_pages": {
            0: ns0_pages,
            4: ns4_pages,
        },
        "expected_skip": {0: [], 4: []},
        "expected_scrape": {0: ns0_pages, 4: ns4_pages},
    }


def create_checkpoint_scenario_incompatible() -> Dict[str, Any]:
    """Create incompatible checkpoint (different namespaces).

    Scenario: Checkpoint was for namespaces [0, 4], but now
    running with [0, 6]. Should be ignored.

    Returns:
        Dictionary with checkpoint data
    """
    checkpoint = create_checkpoint_data(
        namespaces=[0, 4],  # Different from what will be requested
        namespaces_completed=[0],
        current_namespace=4,
        pages_completed=list(range(1, 51)),
    )

    return {
        "checkpoint": checkpoint,
        "requested_namespaces": [0, 6],  # Different!
        "is_compatible": False,
    }
