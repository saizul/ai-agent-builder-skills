import json

from conftest import load_script, run_script

SKILL = "rag-ingestion"
SCRIPT = "chunk_docs.py"
m = load_script(SKILL, SCRIPT)


def test_heading_paths_and_code_fence():
    text = "# A\n\nintro\n\n## B\n\nbody b\n\n```\n# not heading\n```\n\n### C\n\nbody c\n\n# D\n\nbody d\n"
    secs = m.split_sections(text)
    assert [p for p, _ in secs] == [["A"], ["A", "B"], ["A", "B", "C"], ["D"]]
    assert "# not heading" in secs[1][1]


def test_chunks_respect_max_and_overlap():
    sentences = " ".join(f"Sentence number {i} explains one rule of the returns policy." for i in range(60))
    chunks = m.chunk_text("# Policy\n\n" + sentences, max_tokens=100, overlap=20, min_tokens=10)
    assert len(chunks) > 3
    assert all(len(c["text"]) <= 400 for c in chunks)
    # Each chunk after the first starts with the last sentence(s) of the previous one.
    for prev, cur in zip(chunks, chunks[1:]):
        first_sentence = cur["text"].split(". ")[0]
        assert first_sentence in prev["text"]


def test_no_overlap():
    sentences = " ".join(f"Line {i} of text here." for i in range(200))
    chunks = m.chunk_text(sentences, max_tokens=50, overlap=0)
    joined = " ".join(c["text"] for c in chunks)
    assert joined.count("Line 10 of") == 1


def test_html_conversion(fixtures):
    html = (fixtures / SKILL / "docs" / "faq.html").read_text()
    text, title = m.html_to_markdown(html)
    assert title == "Shipping FAQ"
    assert "# Shipping FAQ" in text and "## Tracking" in text
    assert "- Standard shipping is free" in text
    for dropped in ("tracking pixel", "Home | Shop", "Copyright", "color:red"):
        assert dropped not in text


def test_process_stats_and_dedup(fixtures):
    docs = fixtures / SKILL / "docs"
    files = m.collect([str(docs)])
    assert len(files) == 4
    chunks, stats = m.process(files, max_tokens=120, overlap=20, min_tokens=40)
    assert stats["files"] == 4
    assert stats["oversized_chunks"] == 0
    assert stats["tiny_chunks"] >= 1  # "### Photos / Short."
    assert len(stats["exact_duplicates"]) == 11  # returns-policy.md is a copy
    assert stats["no_heading_chunks"] == 1  # notes.txt
    deduped, stats2 = m.process(files, max_tokens=120, overlap=20, min_tokens=40, dedup=True)
    assert stats2["chunks_written"] == stats["chunks"] - 11
    assert all("duplicate_of" not in c for c in deduped)
    c = chunks[0]
    for key in (
        "id",
        "source",
        "title",
        "heading_path",
        "chunk_index",
        "text",
        "chars",
        "est_tokens",
        "sha256",
    ):
        assert key in c
    assert c["source"].startswith("docs/")


def test_near_duplicates(tmp_path):
    base = " ".join(f"word{i}" for i in range(80))
    (tmp_path / "a.md").write_text("# A\n\n" + base)
    (tmp_path / "b.md").write_text("# A\n\n" + base + " extra")
    _, stats = m.process([tmp_path / "a.md", tmp_path / "b.md"], near=0.9)
    assert len(stats["near_duplicates"]) == 1
    assert stats["exact_duplicates"] == []


def test_cli(fixtures, tmp_path):
    docs = fixtures / SKILL / "docs"
    out = tmp_path / "chunks.jsonl"
    r = run_script(
        SKILL, SCRIPT, str(docs), "--max-tokens", "120", "--overlap", "20", "--out", str(out), "--json"
    )
    assert r.returncode == 0, r.stderr
    stats = json.loads(r.stdout)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == stats["chunks_written"] == stats["chunks"]
    r = run_script(SKILL, SCRIPT, str(docs), "--max-tokens", "120", "--overlap", "20", "--fail-on-issues")
    assert r.returncode == 1
    r = run_script(SKILL, SCRIPT, str(docs / "faq.html"), "--jsonl")
    assert r.returncode == 0
    assert json.loads(r.stdout.splitlines()[0])["title"] == "Shipping FAQ"
    assert "chunk(s)" in r.stderr
    assert run_script(SKILL, SCRIPT, str(docs), "--overlap", "500").returncode == 2
    assert run_script(SKILL, SCRIPT, str(tmp_path / "missing")).returncode == 2
