"""Repository-wide checks: vendor neutrality and script conventions."""

import re

import pytest

from conftest import ROOT, SKILLS, run_script

VENDOR_RE = re.compile(
    r"\b(openai|anthropic|claude|gpt-?\d|chatgpt|gemini|llama|mistral|cohere|bedrock|azure|vertex|"
    r"langchain|llamaindex|pinecone|weaviate|qdrant|chroma)\b",
    re.I,
)
SCRIPTS = sorted(SKILLS.glob("*/scripts/*.py"))


def test_skill_content_is_vendor_neutral():
    offenders = []
    for path in sorted(SKILLS.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".py", ".json", ".jsonl"}:
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if VENDOR_RE.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:80]}")
    assert offenders == []


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_scripts_help_and_stdlib(script):
    skill = script.parent.parent.name
    res = run_script(skill, script.name, "--help")
    assert res.returncode == 0
    assert "usage:" in res.stdout
    src = script.read_text()
    imports = set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_]+)", src, re.M))
    assert imports <= {
        "argparse",
        "collections",
        "copy",
        "difflib",
        "hashlib",
        "html",
        "json",
        "re",
        "sys",
        "pathlib",
        "__future__",
    }, imports


def test_no_network_imports():
    for script in SCRIPTS:
        assert not re.search(
            r"^\s*(import|from)\s+(urllib|http|socket|requests)", script.read_text(), re.M
        ), script
