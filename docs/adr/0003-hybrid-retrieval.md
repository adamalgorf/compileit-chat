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
3. **Reciprocal Rank Fusion** (k = 60) of the vector top 20 and the **BM25 top 3**.

Both sides index `Chunk.search_text`, which is the chunk prefixed with
"page title > section path", so a chunk keeps the context of where it sits.

RRF uses ranks only, so incomparable scores (cosine vs. BM25) never need normalising.
BM25 is about 30 lines of our own code instead of a library: it keeps tokenization
explicit, adds no dependency, and is trivially fast at this scale. It is built lazily from
the vector store, so there is a single source of truth for the indexed chunks.

### Why only BM25's top 3: measured, not assumed

The textbook setup (both sides' top 20, equal weight) made results **worse** than vector
search alone. The test used 14 queries: the five case questions, keyword-style rewrites
like the agent sends, and exact-term probes. Each query was scored on whether its expected
page appears in the top 5 pages:

| Fusion setup | Hit@5 |
|---|---|
| Vector only | 13/14 |
| BM25 only | 7/14 |
| RRF, BM25 top 20 (equal weight, or BM25 weighted 0.5 / 0.3) | 11/14 |
| RRF, BM25 top 10 | 12/14 |
| **RRF, BM25 top 5 or top 3** | **13/14** |

The cause is RRF's agreement bonus. Generic question words ("typer", "jobbar") make BM25's
top 20 overlap with the vector top 20, so mediocre chunks found by both outrank the best
vector hit. For example, "typer" matched a TypeScript article that then beat `/tjanster/ai`
for Q1. Down-weighting BM25 did not help; limiting its depth did. With BM25 top 3, BM25
still wins exact-term queries ("organisationsnummer": vector rank 5 → rank 1), and the
hit rate matches vector-only.

Honest caveat: within the top 5, vector-only still ranks some generic questions slightly
higher (e.g. `/uppdrag` at 1 instead of 3 for "branscher"). The agent receives the top 5
chunks, so this costs little. The phase 7 eval re-checks it on a larger golden set. 14
queries are too few to tune finer than this without overfitting.

## Consequences

- One embedding call per query; BM25 cost is negligible.
- The BM25 index is cached per process. After `make ingest` the API must restart, which is
  acceptable because ingestion is an offline step.
- Queries made only of stop words ("Om oss") get no lexical signal and rely on the vector
  side. The agent's `get_page`/`list_pages` tools cover page-level requests anyway.
- No query matched "vem är VD" (the site says "CEO"). Vocabulary mismatch like this is left
  to the agent, which rewrites queries before searching.
- Next steps if quality requires it: a cross-encoder reranker on the fused top 20, or
  per-page diversity in the results. We will decide based on eval results, not up front.
