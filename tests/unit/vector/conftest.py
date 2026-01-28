"""
Test fixtures for vector database tests
"""

import sqlite3

import pytest


@pytest.fixture
def sample_wiki_content():
    """Sample wiki content with various MediaWiki markup"""
    return {
        "simple": "This is a simple page with plain text.",
        "with_links": """
This page has [[internal links]] and [[Link|link with text]].
It also has external links [https://example.com Example Site].
        """,
        "with_templates": """
This page has {{templates}} and {{template|param=value}}.
These should be removed during cleaning.
        """,
        "with_formatting": """
This has '''bold text''' and ''italic text''.
It also has <b>HTML tags</b> that should be cleaned.
        """,
        "with_sections": """
This is the introduction paragraph.

== First Section ==

This is the content of the first section.
It has multiple sentences. And some details.

=== Subsection ===

This is a subsection with more content.

== Second Section ==

This is the second section.
        """,
        "with_images": """
This page has [[File:Example.jpg|thumb|Caption]] images.
And [[Image:Another.png]] references.
        """,
        "complex": """
{{Infobox|name=Test}}

This is a '''complex page''' with [[links]], ''formatting'', and {{templates}}.

== History ==

The history section has multiple paragraphs.

This is the second paragraph with more information.
It continues here.

=== Early Period ===

Subsection content here.

== Characteristics ==

Another major section with [[cross-references]].

[[Category:Test]]
        """,
        "empty": "",
        "very_short": "Short.",
        "long_paragraph": " ".join(["This is a very long paragraph."] * 100),
    }


@pytest.fixture
def test_database(tmp_path):
    """Create a test SQLite database with sample data"""
    db_path = tmp_path / "test_wiki.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE pages (
            page_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            namespace INTEGER NOT NULL,
            latest_revision_id INTEGER,
            is_redirect INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE revisions (
            revision_id INTEGER PRIMARY KEY,
            page_id INTEGER NOT NULL,
            parent_id INTEGER,
            timestamp TEXT NOT NULL,
            contributor_name TEXT,
            content TEXT NOT NULL,
            FOREIGN KEY (page_id) REFERENCES pages(page_id)
        )
    """)

    # Insert sample data
    sample_pages = [
        (1, "Main_Page", 0, 101, 0),
        (2, "Poring", 0, 102, 0),
        (3, "Izlude", 0, 103, 0),
        (4, "Template:Infobox", 10, 104, 0),  # Template namespace
        (5, "Redirect_Page", 0, 105, 1),  # Redirect
        (6, "Empty_Page", 0, 106, 0),
    ]

    sample_revisions = [
        (
            101,
            1,
            None,
            "2024-01-01T00:00:00Z",
            "Editor1",
            "Welcome to the '''iRO Wiki'''. This is the [[main page]].",
        ),
        (
            102,
            2,
            None,
            "2024-01-02T00:00:00Z",
            "Editor2",
            """
The '''Poring''' is a monster in Ragnarok Online.

== Characteristics ==

Porings are pink, blob-like creatures.

== Location ==

Found in various fields around Midgard.

=== Prontera Field ===

Common in Prontera fields.
         """,
        ),
        (
            103,
            3,
            None,
            "2024-01-03T00:00:00Z",
            "Editor3",
            """
{{Infobox|type=City}}

'''Izlude''' is a city in Ragnarok Online.

== History ==

Izlude was established as a port city.

== NPCs ==

Various NPCs can be found here.
         """,
        ),
        (104, 4, None, "2024-01-04T00:00:00Z", "Editor4", "{{Template content}}"),
        (105, 5, None, "2024-01-05T00:00:00Z", "Editor5", "#REDIRECT [[Poring]]"),
        (106, 6, None, "2024-01-06T00:00:00Z", "Editor6", ""),
    ]

    cursor.executemany("INSERT INTO pages VALUES (?, ?, ?, ?, ?)", sample_pages)
    cursor.executemany(
        "INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?)", sample_revisions
    )

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for testing"""

    class MockModel:
        def __init__(self, embedding_dim=384):
            self.embedding_dim = embedding_dim

        def get_sentence_embedding_dimension(self):
            return self.embedding_dim

        def encode(
            self, texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
        ):
            """Return fake embeddings"""
            import numpy as np

            if isinstance(texts, str):
                texts = [texts]
            return np.random.rand(len(texts), self.embedding_dim).astype(np.float32)

    return MockModel()


@pytest.fixture
def temp_vector_storage(tmp_path):
    """Temporary directory for vector database storage"""
    storage_path = tmp_path / "vector_storage"
    storage_path.mkdir()
    return storage_path


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing"""
    from scripts.vectorize_wiki import Chunk

    return [
        Chunk(
            page_id=1,
            revision_id=101,
            page_title="Test_Page",
            namespace=0,
            content="This is test content for chunk 1.",
            chunk_type="section",
            section_title="Introduction",
            section_level=2,
            chunk_index=0,
            metadata={"timestamp": "2024-01-01T00:00:00Z"},
        ),
        Chunk(
            page_id=1,
            revision_id=101,
            page_title="Test_Page",
            namespace=0,
            content="This is test content for chunk 2.",
            chunk_type="section",
            section_title="Details",
            section_level=2,
            chunk_index=1,
            metadata={"timestamp": "2024-01-01T00:00:00Z"},
        ),
        Chunk(
            page_id=2,
            revision_id=102,
            page_title="Another_Page",
            namespace=0,
            content="Different page content.",
            chunk_type="page",
            chunk_index=0,
            metadata={"timestamp": "2024-01-02T00:00:00Z"},
        ),
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embeddings for testing"""
    import numpy as np

    return np.random.rand(3, 384).astype(np.float32)
