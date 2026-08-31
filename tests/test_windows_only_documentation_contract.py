import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs/windows-json.md",
    ROOT / "docs/architecture/README.md",
    ROOT / "docs/research/README.md",
)
STATUS_DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "docs/architecture/README.md",
    ROOT / "docs/research/README.md",
    ROOT / "docs/roadmap.md",
    ROOT / "docs/specifications/json-v2.md",
)
ACTIVE_STATUS_DOCUMENTS = STATUS_DOCUMENTS[:3]
SOURCE_OF_TRUTH_DOCUMENTS = (
    ROOT / "docs/architecture/README.md",
    ROOT / "docs/research/README.md",
    ROOT / "docs/roadmap.md",
    ROOT / "docs/specifications/json-v2.md",
)


def _r10_context(text: str) -> str:
    markers = ("R10", "automated native", "maintainer accepted")
    return " ".join(
        paragraph
        for paragraph in text.split("\n\n")
        if any(marker.lower() in paragraph.lower() for marker in markers)
    )


def test_scoped_docs_declare_one_bounded_windows_only_contract():
    assert set(DOCUMENTS) == {
        ROOT / "README.md",
        ROOT / "docs/windows-json.md",
        ROOT / "docs/architecture/README.md",
        ROOT / "docs/research/README.md",
    }
    assert set(ACTIVE_STATUS_DOCUMENTS) == set(DOCUMENTS) - {ROOT / "docs/windows-json.md"}
    assert set(STATUS_DOCUMENTS) == set(ACTIVE_STATUS_DOCUMENTS) | {
        ROOT / "docs/roadmap.md",
        ROOT / "docs/specifications/json-v2.md",
    }
    assert set(SOURCE_OF_TRUTH_DOCUMENTS) == {
        ROOT / "docs/architecture/README.md",
        ROOT / "docs/research/README.md",
        ROOT / "docs/roadmap.md",
        ROOT / "docs/specifications/json-v2.md",
    }

    texts = {path: path.read_text(encoding="utf-8") for path in DOCUMENTS}
    combined = "\n".join(texts.values())
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

    forbidden = (
        r"JSON\s+v[12]", r"frozen\s+v1", r"--output-version",
        r"\bversion\s*:\s*[12]",
        r"(?:has|with|contains|integer)\s+`version`",
        r"\bv[12]\s+(?:document|contract|envelope|commands?)",
    )
    for path, text in texts.items():
        assert not any(re.search(pattern, text, re.IGNORECASE) for pattern in forbidden), path

    for phrase in (
        "sole current JSON contract", "deliberate pre-stable", "selector-free",
        "schema-3", "cold refresh", "execution_state", "provider outcome",
        "exactly one UTF-8 JSON document", "exit code `0`", "exit code `1`",
        "exit code `2`", "shared deadline", "cleanup",
        "Global\\\\yasb-limitora-v2-guard-", "quota-v2-cache.json",
        "codex-app-server-v2", "opencode-go-api",
    ):
        assert phrase in combined, phrase

    for path in ACTIVE_STATUS_DOCUMENTS:
        context = _r10_context(texts[path]).lower()
        assert "automated" in context
        assert re.search(r"\b(?:cli|executable)\b", context, re.IGNORECASE)
        assert re.search(r"current\s+json", context, re.IGNORECASE)
        assert re.search(
            r"\bmaintainer(?:'s)?\s+manual\s+acceptance\b|\baccepted\s+(?:the\s+real\s+)?(?:YASB\s+CustomWidget\s+)?manually\s+by\s+the\s+maintainer\b|\bmaintainer\s+accepted\b|\bexternal\s+pending\s+gate\b",
            context,
            re.IGNORECASE,
        )
        assert re.search(r"\breal\s+yasb\b", texts[path], re.IGNORECASE)
        assert re.search(
            r"\bno\s+automated\s+yasb\s+(?:rendering|e2e)\b|\bdoes\s+not\s+claim\s+automated\s+yasb\s+(?:rendering|e2e)\b|\bnot\b[^.]{0,40}\bautomated-yasb-rendering\s+claim\b",
            context,
            re.IGNORECASE | re.DOTALL,
        )

    readme = texts[ROOT / "README.md"]
    architecture = texts[ROOT / "docs/architecture/README.md"]
    assert re.search(r"R1-R10.{0,100}complete", readme, re.IGNORECASE | re.DOTALL)
    assert re.search(r"R1-R10.{0,100}(?:evidenced|complete)", architecture, re.IGNORECASE | re.DOTALL)

    roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
    assert re.search(r"R1-R10.{0,100}complete", roadmap, re.IGNORECASE | re.DOTALL)
    roadmap_r10 = next(line for line in roadmap.splitlines() if "| R10 |" in line)
    assert re.search(r"complete", roadmap_r10, re.IGNORECASE)
    assert "automated" in roadmap_r10.lower() and "manual" in roadmap_r10.lower()


def test_issue_137_roadmap_supersession_note_precedes_retained_history():
    roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
    note_start = roadmap.index("## Issue #137 supersession — 2026-08-31")
    note_end = roadmap.index("## Delivery order", note_start)
    note = roadmap[note_start:note_end]

    assert "supersedes" in note
    assert "current JSON contract is the single supported contract" in note
    assert "sole supported output" in note
    assert "no output selector" in note
    assert "no root `version` field" in note
    assert "v1/v2, selector, and root-version material below" in note
    assert "retained as historical roadmap text only" in note

    for marker in (
        "JSON v2",
        "v1 golden fixtures",
        "--output-version 2",
        "## R5 closeout",
        "## R10 closeout",
    ):
        assert note_end < roadmap.index(marker, note_end)


def test_opencode_operator_contract_documents_the_copy_ready_flow():
    readme, windows = [(ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "docs/windows-json.md")]
    example_readme = (ROOT / "examples/customwidget/README.md").read_text(encoding="utf-8")
    example_readme_normalized = " ".join(example_readme.split())
    yaml = (ROOT / "examples/customwidget/customwidget.yaml").read_text(encoding="utf-8")
    combined = " ".join((readme + windows).split())
    normalized = " ".join(windows.split())
    quick = " ".join(windows.split("## Quick path", 1)[1].split("## Runtime support boundary", 1)[0].split())
    assert all(needle in combined for needle in ("LIMITORA_OPENCODE_API_KEY=<key>", "%USERPROFILE%\\.config\\yasb\\.env", "%YASB_CONFIG_HOME%\\.env", "OS environment value wins", "yasbc reload", "starts a fresh", "reloads `.env`", "manual restart/start fallback", "not published to PyPI", "py -m pip install -e .", "%LOCALAPPDATA%\\yasb-limitora\\config.json", "YASB_LIMITORA_CONFIG", '"opencode_go": {"enabled": true}', "YASB_CONFIG_HOME", "only YASB", "sole current JSON contract", "manual acceptance", "external pending gate"))
    assert all(needle in quick for needle in (
        "Create or select the separate Limitora JSON configuration",
        '"opencode_go": {', '"enabled": true', "selector-free",
        "register it in a YASB bar",
        "providers[1]"))
    assert "default `limitora_r9` entry is Codex-only" in example_readme
    assert "sole current JSON contract" in example_readme_normalized
    assert "--output-version" not in example_readme and "--output-version" not in yaml
    assert yaml.count('run_cmd: "yasb-limitora"') == 2 and "providers][1]" in yaml
    assert all(needle in normalized for needle in ("### Current commands", "selector-free", "no root `version` field", "fixed order `codex`, then `opencode_go`", "Codex and OpenCode outcomes are independent", "manual acceptance procedure", "Temporarily add `limitora_r9_opencode_manual` to YASB's `widgets:` config and bar list", "remove/revert the temporary widget from both the YASB bar list and `widgets:` config", "not automated E2E", "install/embed YASB", "extra commercial periods are discarded", "Unavailable is reserved for those fixed-slot cases", "Limitora #55 was implemented and released in v0.3.0", "#133 remains the downstream follow-up", "outside the #130/0.2 migration", "generic YASB CustomWidget acceptance", "OpenCode provider acceptance", "remaining R11 gate"))
    for code in ("guard_acquisition_failed", "guard_wait_timeout", "deadline_exhausted", "credential_invalid", "provider_timeout", "provider_rate_limited", "provider_failed", "provider_unavailable", "invalid_provider_data", "unknown_provider_state"):
        assert code in windows
    for state in ("available", "partial", "unavailable", "unauthorized", "rate_limited", "transient_error", "invalid_data"):
        assert f"`{state}`" in windows
    for distinction in ("`unavailable` is a state inside a returned snapshot", "`provider_unavailable` is an attempted-provider execution error", "`invalid_data` is a public state", "`invalid_provider_data` is a sanitized"):
        assert distinction in windows
    current = windows.split("### Current commands", 1)[1].split("## Availability and fail-safe behavior", 1)[0]
    assert all(term in current for term in ("execution_state", "execution_error", "snapshot", "undetected", "not_run"))
    assert "exit code `1`" in current and all(code in current for code in ("guard_acquisition_failed", "guard_wait_timeout", "deadline_exhausted"))
    exit_rows = [line for line in current.splitlines() if re.match(r"\|\s*`[012]`\s*\|", line.strip())]
    exit_1_rows = [line for line in exit_rows if re.match(r"\|\s*`1`\s*\|", line.strip())]
    exit_2_rows = [line for line in exit_rows if re.match(r"\|\s*`2`\s*\|", line.strip())]
    assert exit_1_rows and not any(code in " ".join(exit_1_rows) for code in ("guard_acquisition_failed", "guard_wait_timeout", "deadline_exhausted"))
    assert any(all(code in line for code in ("guard_acquisition_failed", "guard_wait_timeout", "deadline_exhausted")) for line in exit_2_rows)
    assert any(re.search(r"mixed\s+usable", line, re.IGNORECASE) for line in exit_rows if re.match(r"\|\s*`0`\s*\|", line.strip()))
    assert any("no usable provider" in line.lower() or "no provider result remains usable" in line.lower() for line in exit_1_rows)
    frozen = " ".join(current.split("### Frozen PyInstaller runtime", 1)[1].split())
    assert "internal child relaunch" in frozen and "child relaunch is not a public CLI invocation" in frozen
    assert "JSON/stream/exit contracts" in frozen
    assert "selector-free" in frozen
    assert "exit code `2`" in frozen
    manual = " ".join(windows.split("## Manual native YASB acceptance", 1)[1].split("## Verified limitations and troubleshooting", 1)[0].split())
    assert all(needle in manual for needle in ("remove the `LIMITORA_OPENCODE_API_KEY` line from `.env`", "clear/unset any `LIMITORA_OPENCODE_API_KEY` value in the current/inherited OS environment", "Do not print it", "yasbc reload", "restore it securely")) and "## Published-package verification" not in windows


def test_windows_json_exit_matrix_matches_the_normative_specification():
    windows = " ".join((ROOT / "docs/windows-json.md").read_text(encoding="utf-8").split())
    distinction = " ".join(
        windows.split("## Configuration", 1)[1].split("### Configuration resolution", 1)[0].split()
    )
    assert "provider-scoped" in distinction
    assert "document/global configuration failures" in distinction
    assert re.search(r"provider-scoped[^.]{0,180}provider_failed", distinction, re.IGNORECASE)
    assert re.search(r"document/global[^.]{0,180}exit.{0,8}2", distinction, re.IGNORECASE)
    assert re.search(r"mixed\s+usable.{0,120}\bexit\s+code\s+`0`", windows, re.IGNORECASE | re.DOTALL)
    assert re.search(r"provider-owned\s+failure.{0,140}no\s+usable\s+provider.{0,80}\bexit\s+code\s+`1`", windows, re.IGNORECASE | re.DOTALL)
    assert re.search(r"document/global.{0,160}\bexit\s+code\s+`2`", windows, re.IGNORECASE | re.DOTALL)
    assert re.search(r"unsupported.{0,200}invocation.{0,200}exit\s+code\s+`2`", windows, re.IGNORECASE | re.DOTALL)


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
        assert "0.3.1" in text and "Bearer" in text
        assert "0.1.0" not in text and "0.2.0" not in text
        assert not re.search(r"\b(?:workspace|cookie)\b", text, re.IGNORECASE)

    assert "Limitora 0.3.1" in roadmap
    assert "Limitora 0.1.0" not in roadmap and "Limitora 0.2.0" not in roadmap
    assert "Release and smoke-test 0.2.0" in roadmap
    assert "five_hour" in roadmap and "monthly" in roadmap and "weekly" in roadmap
    assert "#55" in roadmap and "#133" in roadmap

    r10_record = roadmap.split("### R10 final stabilization evidence", 1)[1]
    r10_record = r10_record.split("## Current gate", 1)[0]
    assert "`1e6c86e`" in r10_record
    assert "Python 3.13.5" in r10_record
    assert "Limitora 0.3.1" in r10_record
    assert "597 passed" in r10_record and "4 skipped" in r10_record
    assert "106 passed" in r10_record
    assert re.search(r"frozen[^.]{0,160}exit\s+`?0`?", r10_record, re.IGNORECASE | re.DOTALL)
    assert re.search(r"empty\s+stderr", r10_record, re.IGNORECASE)
    assert re.search(r"no\s+remaining\s+process", r10_record, re.IGNORECASE)

    assert "Limitora v0.3.0" in specification
    assert "yasb-limitora does not consume it until #133" in specification
    assert all(period in specification for period in ("five_hour", "monthly", "weekly"))
    assert "technical-only" in specification
    assert "- fixed assumptions about provider window count or names;" not in specification


def test_completed_migration_130_is_not_documented_as_a_pending_gate():
    texts = {path: path.read_text(encoding="utf-8") for path in STATUS_DOCUMENTS}
    windows = (ROOT / "docs/windows-json.md").read_text(encoding="utf-8")
    readme = texts[ROOT / "README.md"]
    roadmap = texts[ROOT / "docs/roadmap.md"]
    research = texts[ROOT / "docs/research/README.md"]
    specification = texts[ROOT / "docs/specifications/json-v2.md"]
    example_readme = (ROOT / "examples/customwidget/README.md").read_text(encoding="utf-8")
    combined = "\n".join(texts[path] for path in STATUS_DOCUMENTS) + "\n" + windows + "\n" + example_readme

    # Migration #130 is complete and integrated; no document may describe
    # it as a pending implementation gate or an unmet R11 dependency again.
    for pattern in (
        r"R11/#130",
        r"gated by[^.]{0,120}#130",
        r"\bpending[^.\n]{0,80}#130",
        r"deferred to[^.\n]{0,60}#130",
        r"#130[^.\n]{0,80}(?:is|was|remains)[^.\n]{0,40}\b(?:pending|next)\b",
        r"#130[^.\n]{0,80}must be completed|must be completed[^.\n]{0,60}#130",
        r"next R11 dependency",
    ):
        assert not re.search(pattern, combined, re.IGNORECASE), pattern

    # Completion/integration must stay visible on the migration-gate status surfaces.
    assert re.search(
        r"#130[^.\n]{0,120}(?:complete|implemented)[^.\n]{0,120}#159", readme, re.IGNORECASE
    )
    assert re.search(r"#130[^.\n]{0,120}\bcomplete", research, re.IGNORECASE)
    assert re.search(
        r"(?:complete|completed)[^.\n]{0,80}#130[^.\n]{0,80}implementation base",
        specification,
        re.IGNORECASE,
    )
    roadmap_r11 = next(line for line in roadmap.splitlines() if "| R11 |" in line)
    assert re.search(r"#130[^|\n]{0,120}\bcomplete", roadmap_r11, re.IGNORECASE)

    # The concise #159/main integration evidence remains recorded.
    for evidence in (
        "#159",
        "`bdcd29f6`",
        "`33345080629`",
        "Limitora 0.3.1",
        "598 passed",
        "4 skipped",
        "checkpoint 9",
    ):
        assert evidence in roadmap

    # The separate external manual OpenCode gate wording must survive.
    assert "external pending gate" in readme
    assert re.search(r"manual\s+OpenCode\s+acceptance", roadmap, re.IGNORECASE)
    manual = " ".join(
        windows.split("## Manual native YASB acceptance", 1)[1]
        .split("## Verified limitations and troubleshooting", 1)[0]
        .split()
    )
    for needle in (
        "migration #130 is complete",
        "remaining R11 gate",
        "manual acceptance procedure, not automated E2E",
        "externally pending",
    ):
        assert needle in manual

    example_status = " ".join(example_readme.split())
    assert re.search(
        r"generic YASB CustomWidget acceptance is complete[^.]{0,160}#130 is complete/integrated via #159[^.]{0,160}manual acceptance remains pending for R11",
        example_status,
        re.IGNORECASE,
    )
