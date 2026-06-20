from audiomind.chunking import PageAwareChunker
from audiomind.models import ExtractedPage


def test_page_metadata_and_overlap_are_preserved():
    pages = [
        ExtractedPage(1, "## Deadlocks\n\n" + "A process waits for a resource. " * 20),
        ExtractedPage(2, "## Prevention\n\nBreak one necessary condition. " * 15),
    ]
    chunks = PageAwareChunker(chunk_size=260, overlap=40).chunk(
        pages, "doc-1", "collection-1", "os-notes.pdf"
    )
    assert len(chunks) > 2
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert chunks[0].filename == "os-notes.pdf"
    assert any(chunk.chapter == "Deadlocks" for chunk in chunks)
    assert any(chunk.chapter == "Prevention" for chunk in chunks)


def test_invalid_overlap_is_rejected():
    try:
        PageAwareChunker(chunk_size=300, overlap=300)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected invalid overlap to fail")
