# ADR-0003: Hybrid retrieval (vector + BM25) with Reciprocal Rank Fusion

- Status: accepted
- Date: 2026-11-17

## Context

The corpus is small (56 pages, ~110 chunks) and Swedish. Questions come in two shapes:

- **Paraphrases**: "var sitter ni?" should find the "Våra kontor" section. Embeddings handle this well.
- **Exact terms**: names, e-mail addresses, "Gasellpris", an org number. Embeddings blur
  these, keyword search does not.

A BM25-only check on the real snapshot confirmed that neither half is enough alone. Stemming
puts `/kontakt` first for "Hur kontaktar man er?", but for "Vad erbjuder ni för typer av
AI-tjänster?" the words "ai" and "tjänst" occur on so many pages that `/tjanster/ai` falls
out of the lexical top 5.

## Decision

`HybridRetriever` (behind `RetrieverPort`) runs both searches and merges them:

1. **Vector**: `text-embedding-3-small` over Chroma (cosine).
2. **BM25**: a small in-house Okapi BM25 over the same chunks, with a Swedish tokenizer:
   case folding, stop words, Snowball stemming, and letter/digit splitting.
3. **Reciprocal Rank Fusion** (k = 60) of the top 20 from each.

Both sides index `Chunk.search_text`, which is the chunk prefixed with
"page title > section path", so a chunk keeps the context of where it sits.

RRF uses ranks only, so incomparable scores (cosine vs. BM25) never need normalising or a
tuned weight. BM25 is about 30 lines of our own code instead of a library: it keeps
tokenization explicit, adds no dependency, and is trivially fast at this scale. It is built
lazily from the vector store, so there is a single source of truth for the indexed chunks.

## Consequences

- One embedding call per query; BM25 cost is negligible.
- The BM25 index is cached per process. After `make ingest` the API must restart, which is
  acceptable because ingestion is an offline step.
- Queries made only of stop words ("Om oss") get no lexical signal and rely on the vector
  side. The agent's `get_page`/`list_pages` tools cover page-level requests anyway.
- Next steps if quality requires it: a cross-encoder reranker on the fused top 20, or
  per-page diversity in the results. We will decide based on eval results, not up front.
