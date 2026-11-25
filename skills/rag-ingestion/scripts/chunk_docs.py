#!/usr/bin/env python3
"""Chunk Markdown, HTML and text files for retrieval, with overlap and metadata.

Splits on headings first (keeping the heading path as metadata), then packs
paragraphs into chunks of at most --max-tokens (estimated as characters / 4),
with --overlap tokens carried from the end of the previous chunk. Code blocks
and tables are not split mid-way unless they exceed the limit on their own.
HTML is converted to text (script, style, nav, header, footer and aside are
dropped; h1-h6 become headings).

Writes one JSON object per chunk (--out FILE.jsonl or stdout with --jsonl)
and prints stats: chunk count, size distribution, tiny and oversized chunks,
exact and near-duplicate chunks (dropped with --dedup).

Exit codes: 0 = ok, 1 = --fail-on-issues and problems found, 2 = error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

EXTS = {".md", ".markdown", ".mdx", ".txt", ".html", ".htm", ".rst"}
DROP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg", "form"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "tr", "br", "pre", "blockquote", "table", "ul", "ol"}


def est_tokens(text: str) -> int:
    return (len(text) + 3) // 4


class _HTMLToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TAGS:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif re.fullmatch(r"h[1-6]", tag) and not self.skip:
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li" and not self.skip:
            self.out.append("\n- ")
        elif tag in BLOCK_TAGS and not self.skip:
            self.out.append("\n\n" if tag in {"p", "div", "section", "article", "pre", "table"} else "\n")
        elif tag in ("td", "th") and not self.skip:
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in DROP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self._in_title = False
        elif re.fullmatch(r"h[1-6]", tag) and not self.skip:
            self.out.append("\n\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(re.sub(r"[ \t\r\f\v]+", " ", data) if "\n" not in data.strip() else data)


def html_to_markdown(html: str) -> tuple[str, str]:
    parser = _HTMLToMarkdown()
    parser.feed(html)
    text = "".join(parser.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), parser.title.strip()


def split_sections(text: str) -> list[tuple[list[str], str]]:
    """Return (heading_path, body) pairs, ignoring '#' lines inside code fences."""
    sections: list[tuple[list[str], list[str]]] = []
    path: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m:
            if any(x.strip() for x in current):
                sections.append((list(path), current))
            level = len(m.group(1))
            path = ([*path, *[""] * level])[: level - 1] + [m.group(2).strip()]
            current = [line]
        else:
            current.append(line)
    if any(x.strip() for x in current):
        sections.append((list(path), current))
    return [([h for h in p if h], "\n".join(lines).strip()) for p, lines in sections]


def blocks(body: str) -> list[str]:
    """Paragraph-level blocks; fenced code stays in one block."""
    out: list[str] = []
    buf: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            buf.append(line)
            if not in_fence:
                out.append("\n".join(buf))
                buf = []
            continue
        if not in_fence and not line.strip():
            if buf:
                out.append("\n".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        out.append("\n".join(buf))
    return [b for b in out if b.strip()]


def hard_split(text: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    buf = ""
    for s in sentences:
        while len(s) > max_chars:
            if buf:
                parts.append(buf)
                buf = ""
            parts.append(s[:max_chars])
            s = s[max_chars:]
        if len(buf) + len(s) + 1 > max_chars and buf:
            parts.append(buf)
            buf = s
        else:
            buf = f"{buf} {s}".strip() if buf else s
    if buf:
        parts.append(buf)
    return parts


def tail_overlap(text: str, overlap_chars: int) -> str:
    """Whole trailing sentences worth about overlap_chars (word-cut if one sentence is huge)."""
    if overlap_chars <= 0 or not text:
        return ""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text)]
    out: list[str] = []
    total = 0
    for s in reversed(sents):
        if not s or s.startswith("#") or s.startswith("```"):
            continue
        if out and total + len(s) > overlap_chars * 1.5:
            break
        out.insert(0, s)
        total += len(s) + 1
        if total >= overlap_chars:
            break
    tail = " ".join(out)
    if len(tail) > overlap_chars * 1.5:
        tail = tail[-overlap_chars:]
        sp = tail.find(" ")
        tail = tail[sp + 1 :] if 0 <= sp < len(tail) - 1 else tail
    return tail.strip()


def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50, min_tokens: int = 40) -> list[dict]:
    max_chars = max_tokens * 4
    overlap_chars = min(overlap * 4, max_chars // 2)
    chunks: list[dict] = []
    for path, body in split_sections(text):
        heading_line = " > ".join(path)
        pieces: list[str] = []
        for b in blocks(body):
            pieces += [b] if len(b) <= max_chars else hard_split(b, max_chars - int(overlap_chars * 1.5) - 2)
        buf = ""
        for piece in pieces:
            candidate = f"{buf}\n\n{piece}" if buf else piece
            if len(candidate) <= max_chars or not buf:
                buf = candidate
                continue
            chunks.append({"heading_path": path, "heading": heading_line, "text": buf})
            prefix = tail_overlap(buf, overlap_chars)
            buf = f"{prefix}\n\n{piece}" if prefix and len(prefix) + len(piece) + 2 <= max_chars else piece
        if buf:
            chunks.append({"heading_path": path, "heading": heading_line, "text": buf})
    # Merge tiny chunks into the previous chunk of the same section when it fits.
    merged: list[dict] = []
    for c in chunks:
        if (
            merged
            and est_tokens(c["text"]) < min_tokens
            and merged[-1]["heading_path"] == c["heading_path"]
            and len(merged[-1]["text"]) + len(c["text"]) + 2 <= max_chars
        ):
            merged[-1]["text"] += "\n\n" + c["text"]
        else:
            merged.append(c)
    return merged


def norm_for_dedup(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def shingles(text: str, k: int = 5) -> set[str]:
    w = norm_for_dedup(text).split()
    return {" ".join(w[i : i + k]) for i in range(max(1, len(w) - k + 1))}


def process(
    paths: list,
    max_tokens: int = 400,
    overlap: int = 50,
    min_tokens: int = 40,
    dedup: bool = False,
    near: float = 0.9,
) -> tuple[list[dict], dict]:
    all_chunks: list[dict] = []
    files = 0
    for item in paths:
        path, name = item if isinstance(item, tuple) else (item, Path(item).as_posix())
        raw = path.read_text(encoding="utf-8", errors="replace")
        title = ""
        if path.suffix.lower() in (".html", ".htm"):
            raw, title = html_to_markdown(raw)
        files += 1
        for i, c in enumerate(chunk_text(raw, max_tokens, overlap, min_tokens)):
            text = c["text"]
            all_chunks.append(
                {
                    "id": f"{name}#{i}",
                    "source": name,
                    "title": title or (c["heading_path"][0] if c["heading_path"] else path.stem),
                    "heading_path": c["heading_path"],
                    "chunk_index": i,
                    "text": text,
                    "chars": len(text),
                    "est_tokens": est_tokens(text),
                    "sha256": hashlib.sha256(norm_for_dedup(text).encode()).hexdigest()[:16],
                }
            )
    seen: dict[str, str] = {}
    sigs: list[tuple[str, set[str]]] = []
    exact, near_dups = [], []
    for c in all_chunks:
        if c["sha256"] in seen:
            c["duplicate_of"] = seen[c["sha256"]]
            exact.append(c["id"])
            continue
        seen[c["sha256"]] = c["id"]
        sh = shingles(c["text"])
        for other_id, other in sigs:
            if len(sh) >= 5 and len(sh & other) / len(sh | other) >= near:
                c["near_duplicate_of"] = other_id
                near_dups.append(c["id"])
                break
        sigs.append((c["id"], sh))
    kept = [c for c in all_chunks if not (dedup and ("duplicate_of" in c or "near_duplicate_of" in c))]
    sizes = sorted(c["est_tokens"] for c in all_chunks) or [0]
    stats = {
        "files": files,
        "chunks": len(all_chunks),
        "chunks_written": len(kept),
        "tokens_total": sum(sizes),
        "tokens_min": sizes[0],
        "tokens_median": sizes[len(sizes) // 2],
        "tokens_max": sizes[-1],
        "tiny_chunks": sum(1 for s in sizes if s < min_tokens and all_chunks),
        "oversized_chunks": sum(1 for s in sizes if s > max_tokens),
        "no_heading_chunks": sum(1 for c in all_chunks if not c["heading_path"]),
        "exact_duplicates": exact,
        "near_duplicates": near_dups,
    }
    return kept, stats


def collect(inputs: list[str]) -> list[tuple[Path, str]]:
    """Return (path, display name); names are relative to a given directory's parent."""
    out: list[tuple[Path, str]] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files = sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in EXTS)
            out += [
                (f, f.relative_to(p.resolve().parent if p.name in ("", ".") else p.parent).as_posix())
                for f in files
            ]
        elif p.is_file():
            out.append((p, p.as_posix()))
        else:
            raise FileNotFoundError(item)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Chunk Markdown/HTML/text for RAG with overlap and report stats.")
    p.add_argument("inputs", nargs="+", help="files or directories (.md .html .txt .rst)")
    p.add_argument("--max-tokens", type=int, default=400, help="max estimated tokens per chunk (default 400)")
    p.add_argument("--overlap", type=int, default=50, help="overlap in estimated tokens (default 50)")
    p.add_argument("--min-tokens", type=int, default=40, help="chunks below this are 'tiny' (default 40)")
    p.add_argument("--dedup", action="store_true", help="drop exact and near-duplicate chunks from output")
    p.add_argument("--near", type=float, default=0.9, help="near-duplicate Jaccard threshold (default 0.9)")
    p.add_argument("--out", type=Path, help="write chunks as JSONL to this file")
    p.add_argument("--jsonl", action="store_true", help="write chunks as JSONL to stdout (stats to stderr)")
    p.add_argument("--json", action="store_true", help="print stats as JSON")
    p.add_argument("--fail-on-issues", action="store_true", help="exit 1 on duplicates/oversized/tiny chunks")
    args = p.parse_args(argv)
    if args.overlap >= args.max_tokens:
        print("error: --overlap must be smaller than --max-tokens", file=sys.stderr)
        return 2
    try:
        paths = collect(args.inputs)
    except FileNotFoundError as exc:
        print(f"error: not found: {exc}", file=sys.stderr)
        return 2
    if not paths:
        print("error: no supported files found", file=sys.stderr)
        return 2
    chunks, stats = process(paths, args.max_tokens, args.overlap, args.min_tokens, args.dedup, args.near)
    lines = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks)
    if args.out:
        args.out.write_text(lines, encoding="utf-8")
    report_stream = sys.stderr if args.jsonl else sys.stdout
    if args.jsonl:
        sys.stdout.write(lines)
    if args.json:
        print(json.dumps(stats, indent=2), file=report_stream)
    else:
        print(
            f"{stats['files']} file(s) -> {stats['chunks']} chunk(s), {stats['chunks_written']} written\n"
            f"tokens: total {stats['tokens_total']}, min {stats['tokens_min']}, "
            f"median {stats['tokens_median']}, max {stats['tokens_max']}\n"
            f"tiny (<{args.min_tokens}): {stats['tiny_chunks']}, oversized (>{args.max_tokens}): "
            f"{stats['oversized_chunks']}, without heading: {stats['no_heading_chunks']}\n"
            f"exact duplicates: {len(stats['exact_duplicates'])}, "
            f"near duplicates: {len(stats['near_duplicates'])}",
            file=report_stream,
        )
    issues = (
        stats["exact_duplicates"]
        or stats["near_duplicates"]
        or stats["oversized_chunks"]
        or stats["tiny_chunks"]
    )
    return 1 if args.fail_on_issues and issues else 0


if __name__ == "__main__":
    sys.exit(main())
