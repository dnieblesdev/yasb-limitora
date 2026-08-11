import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs/windows-json.md",
    ROOT / "docs/architecture/README.md",
    ROOT / "docs/roadmap.md",
    ROOT / "docs/specifications/json-v2.md",
)
STATUS_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs/architecture/README.md",
    ROOT / "docs/roadmap.md",
    ROOT / "docs/specifications/json-v2.md",
)


def _r10_context(text: str) -> str:
    return " ".join(paragraph for paragraph in text.split("\n\n") if "R10" in paragraph)


def test_scoped_docs_declare_one_bounded_windows_only_contract():
    texts = {path: path.read_text(encoding="utf-8") for path in DOCUMENTS}
    combined = "\n".join(texts.values())

    assert set(texts) == {
        ROOT / "README.md",
        ROOT / "docs/windows-json.md",
        ROOT / "docs/architecture/README.md",
        ROOT / "docs/roadmap.md",
        ROOT / "docs/specifications/json-v2.md",
    }

    for text in texts.values():
        assert re.search(r"\bWindows-only\b", text, re.IGNORECASE)
        assert "yasb-limitora: unsupported_platform\\n" in text
        assert re.search(r"(?:exit(?: code)?|returns?)\D{0,24}\b2\b", text, re.IGNORECASE)
        assert re.search(r"\b(?:no|zero)\b[^.]{0,30}\bstdout(?: bytes)?\b", text, re.IGNORECASE)
        assert re.search(r"\bnot\b[^.]{0,40}\b(?:supported|compatibility|portability)\b", text, re.IGNORECASE)

    assert "yasb-limitora" in combined and "python -m yasb_limitora" in combined
    assert re.search(r"both public CLI routes|installed console route.*python -m yasb_limitora", combined, re.IGNORECASE | re.DOTALL)

    for path in STATUS_DOCUMENTS:
        context = _r10_context(texts[path]).lower()
        assert {"historical", "reverted", "non-authoritative"} <= set(re.findall(r"[a-z-]+", context))
        assert re.search(r"\b(?:not|no|does not|without)\b[^.]{0,120}\b(?:proof|completion)\b", context, re.IGNORECASE)

    assert re.search(r"R1-R9.{0,100}(?:evidenced|complete)", texts[ROOT / "README.md"], re.IGNORECASE | re.DOTALL)
    assert re.search(r"R1-R9.{0,100}(?:evidenced|complete)", texts[ROOT / "docs/architecture/README.md"], re.IGNORECASE | re.DOTALL)
    assert re.search(r"R1-R9.{0,100}(?:evidenced|complete)", texts[ROOT / "docs/roadmap.md"], re.IGNORECASE | re.DOTALL)

    roadmap_r10 = next(line for line in texts[ROOT / "docs/roadmap.md"].splitlines() if "| R10 |" in line)
    assert re.search(r"not complete", roadmap_r10, re.IGNORECASE)
    assert {"historical", "reverted", "non-authoritative"} <= set(re.findall(r"[a-z-]+", roadmap_r10.lower()))
