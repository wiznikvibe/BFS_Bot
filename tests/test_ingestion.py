from bfs_bot.ingestion import chunk_text, slugify


def test_chunk_text_uses_overlap_for_long_documents():
    words = [f"word{i}" for i in range(20)]

    chunks = chunk_text(" ".join(words), max_words=8, overlap=2)

    assert chunks[0].split() == words[:8]
    assert chunks[1].split()[:2] == words[6:8]


def test_slugify_creates_stable_chunk_prefixes():
    assert slugify("Terms and Conditions") == "terms-and-conditions"
