import pytest

from compileit_chat.application.errors import IngestionError
from compileit_chat.application.use_cases import IngestReport, IngestWebsite
from tests.fakes import (
    FakeCrawler,
    FakeExtractor,
    InMemoryDocumentStore,
    make_document,
)

HOME = make_document("https://compileit.com", "Vi bygger digitala tjänster.")
ABOUT = make_document("https://compileit.com/om-oss", "Vår story.")
ABOUT_COPY = make_document("https://compileit.com/om-oss-kopia", "  vår   STORY. ")


async def test_stores_unique_documents_and_reports_what_was_skipped() -> None:
    crawler = FakeCrawler([HOME.url, ABOUT.url, "https://compileit.com/tom", ABOUT_COPY.url])
    extractor = FakeExtractor({d.url: d for d in (HOME, ABOUT, ABOUT_COPY)})
    store = InMemoryDocumentStore()

    report = await IngestWebsite(crawler, extractor, store).execute()

    assert store.documents == [HOME, ABOUT]  # first occurrence of duplicate content wins
    assert report == IngestReport(
        pages_fetched=4, documents=2, skipped_empty=1, skipped_duplicate=1
    )


async def test_empty_crawl_keeps_existing_documents() -> None:
    store = InMemoryDocumentStore([HOME])

    with pytest.raises(IngestionError):
        await IngestWebsite(FakeCrawler([]), FakeExtractor({}), store).execute()

    assert store.documents == [HOME]


async def test_is_idempotent() -> None:
    store = InMemoryDocumentStore()
    use_case = IngestWebsite(FakeCrawler([HOME.url]), FakeExtractor({HOME.url: HOME}), store)

    first, second = await use_case.execute(), await use_case.execute()

    assert first == second
    assert store.documents == [HOME]
