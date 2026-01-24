"""
Full-text search functionality using FTS5.

This module provides functions for searching wiki content using SQLite's
FTS5 (Full-Text Search) extension. It supports simple keyword searches,
boolean operators (AND, OR, NOT), phrase queries, and returns results
with BM25 ranking and snippet extraction.

Functions:
    search: Search page content using FTS5
    search_titles: Search only page titles (faster)
    rebuild_index: Rebuild entire FTS index
    index_page: Reindex a single page
    optimize_index: Optimize FTS index for performance
"""

import logging
import sqlite3
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """
    Search result with ranking and snippet.

    Attributes:
        page_id: ID of the page
        title: Page title
        snippet: Text excerpt with match highlighting
        rank: BM25 relevance score (lower is better)
    """

    page_id: int
    title: str
    snippet: str
    rank: float


def search(
    connection: sqlite3.Connection, query: str, limit: int = 10, offset: int = 0
) -> List[SearchResult]:
    """
    Search page content using FTS5.

    Args:
        connection: Database connection
        query: Search query (supports FTS5 syntax)
        limit: Maximum results to return (default 10)
        offset: Number of results to skip (default 0)

    Returns:
        List of SearchResult instances, ordered by relevance

    Examples:
        >>> search(db, "prontera")  # Simple search
        >>> search(db, "prontera AND geffen")  # Boolean AND
        >>> search(db, '"prontera castle"')  # Phrase search
        >>> search(db, "pron*")  # Prefix search

    Raises:
        sqlite3.OperationalError: If query syntax is invalid
    """
    # FTS5 query with BM25 ranking and snippet extraction
    # snippet() parameters: column, start_tag, end_tag, ellipsis, max_tokens
    sql = """
        SELECT
            pf.page_id,
            pf.title,
            snippet(pages_fts, 2, '<mark>', '</mark>', '...', 32) as snippet,
            rank as rank
        FROM pages_fts pf
        WHERE pages_fts MATCH ?
        ORDER BY rank
        LIMIT ? OFFSET ?
    """

    try:
        cursor = connection.execute(sql, (query, limit, offset))
    except sqlite3.OperationalError as e:
        logger.error(f"FTS5 query error: {e}, query: {query}")
        raise

    results = []
    for row in cursor.fetchall():
        results.append(
            SearchResult(page_id=row[0], title=row[1], snippet=row[2], rank=row[3])
        )

    logger.debug(f"Search '{query}' returned {len(results)} results")
    return results


def search_titles(
    connection: sqlite3.Connection, query: str, limit: int = 10
) -> List[SearchResult]:
    """
    Search only page titles (faster than full content search).

    Args:
        connection: Database connection
        query: Search query
        limit: Maximum results (default 10)

    Returns:
        List of SearchResult instances (snippet will be empty)

    Example:
        >>> search_titles(db, "prontera")
    """
    sql = """
        SELECT
            pf.page_id,
            pf.title,
            '' as snippet,
            rank as rank
        FROM pages_fts pf
        WHERE title MATCH ?
        ORDER BY rank
        LIMIT ?
    """

    try:
        cursor = connection.execute(sql, (query, limit))
    except sqlite3.OperationalError as e:
        logger.error(f"FTS5 title query error: {e}, query: {query}")
        raise

    results = []
    for row in cursor.fetchall():
        results.append(
            SearchResult(page_id=row[0], title=row[1], snippet="", rank=row[3])
        )

    logger.debug(f"Title search '{query}' returned {len(results)} results")
    return results


def index_page(connection: sqlite3.Connection, page_id: int) -> None:
    """
    Reindex a single page in FTS.

    Useful for updating the index after manual changes or corrections.

    Args:
        connection: Database connection
        page_id: Page ID to reindex

    Example:
        >>> index_page(db, 123)
    """
    # Delete existing entry
    connection.execute("DELETE FROM pages_fts WHERE page_id = ?", (page_id,))

    # Insert new entry with latest content
    connection.execute(
        """
        INSERT INTO pages_fts (page_id, title, content)
        SELECT
            p.page_id,
            p.title,
            (
                SELECT r.content
                FROM revisions r
                WHERE r.page_id = p.page_id
                ORDER BY r.timestamp DESC
                LIMIT 1
            )
        FROM pages p
        WHERE p.page_id = ?
          AND EXISTS (SELECT 1 FROM revisions WHERE page_id = ?)
    """,
        (page_id, page_id),
    )

    connection.commit()
    logger.info(f"Reindexed page {page_id}")


def rebuild_index(connection: sqlite3.Connection) -> None:
    """
    Rebuild entire FTS index from scratch.

    Useful if FTS table gets corrupted or out of sync with source data.
    This is a potentially expensive operation for large databases.

    Args:
        connection: Database connection

    Example:
        >>> rebuild_index(db)
    """
    logger.info("Rebuilding FTS index...")

    # Clear existing index
    connection.execute("DELETE FROM pages_fts")

    # Repopulate with latest revisions
    connection.execute("""
        INSERT INTO pages_fts (page_id, title, content)
        SELECT
            p.page_id,
            p.title,
            (
                SELECT r.content
                FROM revisions r
                WHERE r.page_id = p.page_id
                ORDER BY r.timestamp DESC
                LIMIT 1
            ) as content
        FROM pages p
        WHERE EXISTS (
            SELECT 1 FROM revisions r WHERE r.page_id = p.page_id
        )
    """)

    connection.commit()

    # Get index size
    cursor = connection.execute("SELECT COUNT(*) FROM pages_fts")
    count = cursor.fetchone()[0]

    logger.info(f"FTS index rebuilt: {count} pages indexed")


def optimize_index(connection: sqlite3.Connection) -> None:
    """
    Optimize FTS index (merge segments, reduce size).

    Run periodically for best query performance. This merges internal
    FTS5 b-tree segments which can improve search speed.

    Args:
        connection: Database connection

    Example:
        >>> optimize_index(db)
    """
    connection.execute("INSERT INTO pages_fts(pages_fts) VALUES('optimize')")
    connection.commit()
    logger.info("FTS index optimized")
