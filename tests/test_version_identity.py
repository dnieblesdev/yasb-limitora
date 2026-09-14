"""First-public 0.2.0 version identity (R11 S01).

Proves the single dynamic version source, the absence of any active
placeholder or public ``-rc`` identity, the closed public argv/version
selection contract, and that product release material stays out of the
Limitora-version guarded document regions.
"""

import importlib
import io
import json
import re
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

ROOT = Path(__file__).parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_INIT = ROOT / "src/yasb_limitora/__init__.py"
RELEASE_NOTES = ROOT / "docs/release/0.2.0/RELEASE_NOTES.md"
MIGRATION = ROOT / "docs/release/0.2.0/MIGRATION.md"
RELEASE_METADATA = (PYPROJECT, PACKAGE_INIT, RELEASE_NOTES, MIGRATION)


def test_package_version_is_the_single_source_of_truth():
    package = importlib.import_module("yasb_limitora")
    assert package.__version__ == "0.2.0"
    assert re.fullmatch(r"\d+\.\d+\.\d+", package.__version__)


def test_pyproject_maps_dynamic_version_to_the_package_attribute():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert re.search(r'^dynamic = \["version"\]$', text, re.MULTILINE)
    assert not re.search(r"^version = [\"']", text, re.MULTILINE), "static version literal must be removed"
    attr = re.search(
        r'\[tool\.setuptools\.dynamic\]\s*\nversion = \{attr = "([^"]+)"\}',
        text,
    )
    assert attr, "pyproject must map the dynamic version to a package attribute"
    assert attr.group(1) == "yasb_limitora.__version__"
    module_name, _, attribute = attr.group(1).rpartition(".")
    module = importlib.import_module(module_name)
    assert getattr(module, attribute) == "0.2.0"


def test_public_scripts_surface_is_unchanged():
    text = PYPROJECT.read_text(encoding="utf-8")
    scripts = text.split("[project.scripts]", 1)[1].split("[", 1)[0]
    assert scripts.strip().splitlines() == ['yasb-limitora = "yasb_limitora.cli:main"']
    assert "setup-assist" not in text and "setup_assist" not in text


def test_no_active_surface_reports_the_placeholder_version():
    for path in (PYPROJECT, PACKAGE_INIT, ROOT / "README.md", ROOT / "docs/roadmap.md"):
        assert "0.1.0" not in path.read_text(encoding="utf-8"), path


def test_stale_build_lib_placeholder_copy_is_removed():
    assert not (ROOT / "build/lib/yasb_limitora/__init__.py").exists()


def test_release_metadata_never_creates_a_public_rc_identity():
    for path in RELEASE_METADATA:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"0\.2\.0\s*[-._]?rc", text, re.IGNORECASE), path
        assert not re.search(r"^-rc|\s-rc\d", text, re.MULTILINE), path


@pytest.mark.parametrize(
    "argv",
    (
        ("--version",),
        ("--version", "0.2.0"),
        ("--version=0.2.0",),
        ("-V",),
        ("version",),
        ("--output-version", "2"),
        ("--output-version=1",),
    ),
)
def test_public_version_selection_surface_stays_closed(argv):
    from yasb_limitora.cli import main

    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(
        argv,
        environment={},
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: True,
    )
    assert code == 2
    assert stderr.getvalue() == "yasb-limitora: invocation_invalid\n"
    raw = stdout.getvalue()
    document = json.loads(raw)
    assert "version" not in document
    assert document["execution_error"] == {"code": "invocation_invalid", "phase": "configuration"}
    assert b"0.2.0" not in raw and b"0.1.0" not in raw


def test_release_notes_cover_first_public_identity_137_break_and_unsigned_disclosure():
    notes = " ".join(RELEASE_NOTES.read_text(encoding="utf-8").split())
    for phrase in (
        "first public release",
        "#137",
        "root `version` field",
        "selector-free",
        "sole supported output",
        "setup.exe",
        "unsigned",
        "SmartScreen",
        "SHA-256",
    ):
        assert phrase in notes, phrase


def test_migration_covers_setup_exe_path_state_retention_and_yasb_boundary():
    text = " ".join(MIGRATION.read_text(encoding="utf-8").split())
    for phrase in (
        "first public release",
        "#137",
        "root `version` field",
        "setup.exe",
        "development-only",
        "%LOCALAPPDATA%\\Programs\\yasb-limitora",
        "%LOCALAPPDATA%\\yasb-limitora",
        "preserved by default",
        "unchecked by default",
        "never manages the YASB lifecycle",
        "unsigned",
        "SmartScreen",
    ):
        assert phrase in text, phrase


def test_product_version_material_stays_outside_limitora_guarded_regions():
    architecture = (ROOT / "docs/architecture/README.md").read_text(encoding="utf-8")
    research = (ROOT / "docs/research/README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
    architecture_contract = architecture.split("## Execution boundary", 1)[0]
    research_contract = research.split("## Sanitized evidence rules", 1)[0]
    for region in (architecture_contract, research_contract):
        assert "0.1.0" not in region and "0.2.0" not in region
    assert "Limitora 0.1.0" not in roadmap and "Limitora 0.2.0" not in roadmap
    assert "Release and smoke-test 0.2.0" in roadmap


def test_status_documents_point_to_release_material_without_publication_claims():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
    assert "docs/release/0.2.0/" in readme
    assert "development-only" in readme
    assert "docs/release/0.2.0/" in roadmap
    for text in (readme, roadmap):
        assert not re.search(r"(?:published|released)\s+(?:the\s+)?setup\.exe", text, re.IGNORECASE)
