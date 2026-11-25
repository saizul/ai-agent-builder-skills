# Chunking guide

## Starting points

| Content | Max tokens | Overlap | Notes |
| --- | --- | --- | --- |
| FAQ / help-center articles | 200-400 | 0-40 | One question + answer per chunk is ideal |
| Policies, contracts, manuals | 300-600 | 50-80 | Keep clause numbers and headings in metadata |
| Product catalogue text | 150-300 | 0 | Often better served by structured search or a tool |
| Technical docs with code | 400-800 | 50 | Do not split code blocks |
| Chat transcripts / tickets | 200-400 | 50 | Redact PII first; consider summarising instead |

Measure, do not guess: run the retrieval smoke test at two or three settings and keep the
best. Larger chunks give more context per hit but dilute similarity; smaller chunks retrieve
precisely but lose context.

## Heading paths

`chunk_docs.py` stores the heading path (e.g. `["Returns", "Damaged items"]`). Prepend it to the
text you embed ("Returns > Damaged items: ...") or store it as a field; it helps both
retrieval and citations.

## Duplicates

- Exact duplicates: identical normalised text (case, punctuation and whitespace ignored).
- Near duplicates: 5-word shingle Jaccard similarity >= `--near` (default 0.9).
- Duplicates crowd the top-k with copies of one answer and hide the second-best source. Remove
  them, or keep one canonical copy and store the other sources in metadata.

## Metadata to keep

`id`, `source`, `source_url`, `title`, `heading_path`, `chunk_index`, `sha256`, `language`,
`audience` / access level, `product`, `region`, `effective_date`, `last_reviewed`, `ingested_at`.

## Retrieval smoke test

1. Write 20-50 questions real users ask, each with the expected source (and section).
2. For each question, retrieve top 5 with your production query settings.
3. Record hit@1, hit@5 and the rank of the expected chunk.
4. Investigate every miss: wrong chunking (answer split across chunks), missing metadata filter,
   outdated duplicate outranking the current page, vocabulary mismatch (add synonyms or hybrid
   search).
5. Keep the question set in the repository and re-run it after ingestion changes.

You can store the questions in `eval-harness` format and record the retrieved source IDs as
the output, then check them with `contains` checks.

## Common problems

- Tables flattened into unreadable text: convert to "Column: value" lines per row.
- PDFs with headers/footers on every page: remove before chunking or they become duplicates.
- Outdated documents indexed next to current ones: filter by `effective_date` or delete.
- Mixed languages in one chunk: split by language and store `language`.
