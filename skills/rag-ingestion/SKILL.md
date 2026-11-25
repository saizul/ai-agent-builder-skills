---
name: rag-ingestion
description: Prepare business documents for retrieval-augmented generation (RAG) - source inventory, cleaning, heading-aware chunking with overlap, metadata (source, title, heading path, hashes, access level, dates), exact and near-duplicate removal, chunk-size QA and a retrieval smoke test - with a script that chunks Markdown, HTML and text into JSONL and reports size distribution, tiny/oversized chunks and duplicates. Use when building or fixing a knowledge base for a chatbot or agent, when answers miss facts that are in the docs, when choosing chunk size and overlap, or before loading documents into a vector or search index.
license: MIT
compatibility: Python 3.8+ standard library. Output JSONL works with any embedding model, vector database or search engine.
metadata:
  author: Saizul Amin
  version: "0.1.0"
---

# RAG ingestion

Retrieval quality is decided at ingestion: clean text, sensible chunks, rich metadata and no
duplicates. Fix those before tuning embeddings or prompts.

Paths below are relative to this skill's folder.

## When to use

- Building a knowledge base from help-center articles, policies, product docs, wikis, exports
- "The bot says it doesn't know, but it's in the docs", "answers quote outdated policy"
- Choosing chunk size and overlap, or auditing an existing index
- Re-ingesting after a documentation migration

## When not to use

- Structured data (orders, stock, prices): expose it through tools, not embeddings
- PDFs or scans: convert to Markdown/HTML/text first (layout-aware converter, OCR), then come back
- Ranking/embedding model selection: out of scope here; measure with `eval-harness`

## Workflow

1. **Inventory sources.** For each source: owner, format, count, update frequency, audience
   (public / internal / restricted), and whether it is the source of truth. Drop drafts,
   duplicates of other systems and archived content unless explicitly needed.
2. **Clean before chunking.** Remove navigation, cookie banners, footers, "related articles",
   tracking text; keep headings, lists, tables and code. Convert PDFs and Office files with
   a converter that keeps headings. Run `guardrails-and-safety` scans for PII and injected
   instructions on anything user-generated or scraped.
3. **Chunk and measure.**
   ```bash
   python3 scripts/chunk_docs.py docs/ --max-tokens 400 --overlap 50 --out chunks.jsonl
   python3 scripts/chunk_docs.py docs/ --dedup --out chunks.jsonl --json
   python3 scripts/chunk_docs.py help-center/*.html --max-tokens 300 --fail-on-issues
   ```
   Each JSONL row has `id`, `source`, `title`, `heading_path`, `chunk_index`, `text`, `chars`,
   `est_tokens`, `sha256` and duplicate markers. Token counts are estimates (characters / 4).
4. **Read the stats.** Many tiny chunks: headings with little text; raise `--min-tokens` or
   restructure docs. Oversized chunks: long tables or code; split the source. Many duplicates:
   boilerplate or copied pages; use `--dedup` and fix the source. Defaults and trade-offs are in
   [references/chunking-guide.md](references/chunking-guide.md).
5. **Add business metadata** your retriever will filter on: `audience`/access level, product,
   language, region, `effective_date`, `last_reviewed`, `source_url`. Never index restricted
   content into a shared index; filter by access at query time.
6. **Embed or index** with your stack (embedding model, vector database or keyword search).
   Prefer hybrid (keyword + vector) search for product names, codes and numbers.
7. **Smoke-test retrieval.** Write 20-50 real questions with the expected source; check that
   the right chunk appears in the top 3-5. Log misses and fix the chunking or the source.
   Re-run after every ingestion change. See the test recipe in
   [references/chunking-guide.md](references/chunking-guide.md).
8. **Plan updates.** Re-ingest changed documents by `source` + `sha256`; delete chunks of
   removed documents; record ingestion date per chunk.

## Output

```
212 files -> 1,873 chunks, 1,790 written (--dedup)
tokens: total 512,400, min 12, median 286, max 400
tiny (<40): 41, oversized (>400): 0, without heading: 18
exact duplicates: 61 (cookie notice + "contact us" footer), near duplicates: 22 (EN/UK pages)
Actions: strip footer boilerplate, merge 14 one-line FAQ pages, add audience metadata,
retrieval smoke test 44/50 top-5 hits; misses are all in pricing tables -> convert to text.
```
