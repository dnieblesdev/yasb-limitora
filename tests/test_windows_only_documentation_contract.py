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
SOURCE_OF_TRUTH_DOCUMENTS = (
    ROOT / "docs/architecture/README.md",
    ROOT / "docs/research/README.md",
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
    assert set(STATUS_DOCUMENTS) == {
        ROOT / "README.md",
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
    assert "bare `yasb-limitora` command" in combined
    assert "user `PATH`" in combined and "restart YASB" in combined
    assert re.search(r"fully qualified executable.{0,160}(?:diagnostic|workaround)", combined, re.IGNORECASE | re.DOTALL)
    assert re.search(r"machine-specific\s+paths?", combined, re.IGNORECASE)

    for path in STATUS_DOCUMENTS:
        context = _r10_context(texts[path]).lower()
        assert "automated" in context
        assert re.search(r"\b(?:cli|executable)\b", context, re.IGNORECASE)
        assert re.search(r"\bjson\s+v2\b", context, re.IGNORECASE)
        assert re.search(
            r"\bmaintainer(?:'s)?\s+manual\s+acceptance\b|\baccepted\s+manually\s+by\s+the\s+maintainer\b",
            context,
            re.IGNORECASE,
        )
        assert re.search(r"\breal\s+yasb\b", texts[path], re.IGNORECASE)
        assert re.search(
            r"\bno\s+automated\s+yasb\s+(?:rendering|e2e)\b|\bdoes\s+not\s+claim\s+automated\s+yasb\s+(?:rendering|e2e)\b",
            context,
            re.IGNORECASE | re.DOTALL,
        )

    assert re.search(r"R1-R10.{0,100}complete", texts[ROOT / "README.md"], re.IGNORECASE | re.DOTALL)
    assert re.search(r"R1-R10.{0,100}(?:evidenced|complete)", texts[ROOT / "docs/architecture/README.md"], re.IGNORECASE | re.DOTALL)
    assert re.search(r"R1-R10.{0,100}complete", texts[ROOT / "docs/roadmap.md"], re.IGNORECASE | re.DOTALL)

    roadmap_r10 = next(line for line in texts[ROOT / "docs/roadmap.md"].splitlines() if "| R10 |" in line)
    assert re.search(r"complete", roadmap_r10, re.IGNORECASE)
    assert "automated" in roadmap_r10.lower() and "manual" in roadmap_r10.lower()


def test_source_of_truth_docs_use_the_consumed_limitora_bearer_contract():
    texts = {
        path: path.read_text(encoding="utf-8") for path in SOURCE_OF_TRUTH_DOCUMENTS
    }
    architecture = texts[ROOT / "docs/architecture/README.md"]
    research = texts[ROOT / "docs/research/README.md"]
    roadmap = texts[ROOT / "docs/roadmap.md"]
    specification = texts[ROOT / "docs/specifications/json-v2.md"]

    architecture_contract = architecture.split("## Execution boundary", 1)[0]
    research_contract = research.split("## Sanitized evidence rules", 1)[0]
    for text in (architecture_contract, research_contract):
        assert "0.2.0" in text and "Bearer" in text
        assert "0.1.0" not in text
        assert not re.search(r"\b(?:workspace|cookie)\b", text, re.IGNORECASE)

    assert "Limitora 0.2.0" in roadmap
    assert "Limitora 0.1.0" not in roadmap
    assert "five_hour" in roadmap and "monthly" in roadmap and "weekly" in roadmap
    assert "#55" in roadmap and "#133" in roadmap

    assert "Limitora v0.3.0" in specification
    assert "yasb-limitora does not consume it until #133" in specification
    assert all(period in specification for period in ("five_hour", "monthly", "weekly"))
    assert "technical-only" in specification
    assert "- fixed assumptions about provider window count or names;" not in specification
