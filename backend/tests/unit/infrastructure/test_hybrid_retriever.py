from compileit_chat.infrastructure.retrieval.hybrid_retriever import HybridRetriever
from compileit_chat.infrastructure.retrieval.tokenizer import SwedishTokenizer
from tests.fakes import InMemoryVectorStore, KeywordEmbeddings, ParagraphChunker, make_document

PAGES = [
    make_document(
        "https://compileit.com/kontakt",
        "Våra kontor finns i Stockholm, Kalmar och Skövde.\n\nMejla hello@compileit.com.",
        "Kontakta oss",
    ),
    make_document(
        "https://compileit.com/privacy-policy",
        "Organisationsnummer 559058-9650.\n\nVi behandlar personuppgifter enligt GDPR.",
        "Integritetspolicy",
    ),
    make_document(
        "https://compileit.com/tjanster/ai",
        "Vi bygger AI-agenter för kundservice.",
        "AI-tjänster",
    ),
]
# The fake embedding only "understands" these concepts; anything else is lexical-only.
EMBEDDINGS = KeywordEmbeddings(["kontor", "ai", "personuppgifter"])


async def make_retriever(candidates: int = 20) -> tuple[HybridRetriever, InMemoryVectorStore]:
    store = InMemoryVectorStore()
    chunks = [chunk for page in PAGES for chunk in ParagraphChunker().split(page)]
    await store.replace_all(
        chunks, await EMBEDDINGS.embed_documents([c.search_text for c in chunks])
    )
    retriever = HybridRetriever(EMBEDDINGS, store, SwedishTokenizer(), candidates=candidates)
    return retriever, store


async def test_semantic_match_ranks_first() -> None:
    retriever, _ = await make_retriever()

    hits = await retriever.search("Var har ni era kontor?", k=2)

    assert hits[0].chunk.text.startswith("Våra kontor")


async def test_exact_term_unknown_to_embeddings_is_found_lexically() -> None:
    retriever, _ = await make_retriever()

    hits = await retriever.search("559058-9650", k=1)

    assert hits[0].chunk.text == "Organisationsnummer 559058-9650."


async def test_returns_at_most_k_with_descending_fused_scores() -> None:
    retriever, _ = await make_retriever()

    hits = await retriever.search("AI-agenter för kundservice", k=3)

    assert len(hits) == 3
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


async def test_empty_index_returns_nothing_and_is_not_cached() -> None:
    store = InMemoryVectorStore()
    retriever = HybridRetriever(EMBEDDINGS, store, SwedishTokenizer())

    assert await retriever.search("kontor", k=3) == []

    chunks = ParagraphChunker().split(PAGES[0])
    await store.replace_all(chunks, await EMBEDDINGS.embed_documents([c.text for c in chunks]))

    assert len(await retriever.search("kontor", k=3)) == 2
