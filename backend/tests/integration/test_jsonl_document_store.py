from pathlib import Path

from compileit_chat.infrastructure.storage.jsonl_document_store import JsonlDocumentStore
from tests.fakes import make_document

ABOUT = make_document("https://compileit.com/om-oss", "# Om oss\n\nVår story", "Om oss")
CONTACT = make_document("https://compileit.com/kontakt", "Skövde", "Kontakt")


async def test_round_trips_documents_sorted_by_url(tmp_path: Path) -> None:
    path = tmp_path / "snapshot" / "pages.jsonl"
    await JsonlDocumentStore(path).replace_all([ABOUT, CONTACT])

    reloaded = JsonlDocumentStore(path)

    assert await reloaded.list_all() == [CONTACT, ABOUT]
    assert "Skövde" in path.read_text(encoding="utf-8")  # readable diffs, no \\u escapes


async def test_get_matches_url_variants(tmp_path: Path) -> None:
    store = JsonlDocumentStore(tmp_path / "pages.jsonl")
    await store.replace_all([ABOUT])

    assert await store.get("https://compileit.com/om-oss/#team") == ABOUT
    assert await store.get("https://compileit.com/saknas") is None


async def test_replace_all_drops_removed_pages(tmp_path: Path) -> None:
    store = JsonlDocumentStore(tmp_path / "pages.jsonl")
    await store.replace_all([ABOUT, CONTACT])

    await store.replace_all([CONTACT])

    assert await JsonlDocumentStore(tmp_path / "pages.jsonl").list_all() == [CONTACT]


async def test_missing_file_means_no_documents(tmp_path: Path) -> None:
    assert await JsonlDocumentStore(tmp_path / "missing.jsonl").list_all() == []
