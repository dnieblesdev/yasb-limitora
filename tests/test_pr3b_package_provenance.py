import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/verify_limitora_package.py"
WORKFLOW = ROOT / ".github/workflows/windows-proof.yml"
GOOD_MODULE = '''from datetime import timedelta
class OpenCodeGoConfig:
    def __init__(self, api_key, provider="opencode-go", timeout=timedelta(seconds=10)):
        self.api_key, self.provider, self.timeout = api_key, provider, timeout
    def __repr__(self): return "OpenCodeGoConfig(api_key=<redacted>)"
def activate_provider(config, *, enabled=True, clock=None):
    raise AssertionError("provider activation must not be called")
'''


def _verifier():
    spec = importlib.util.spec_from_file_location("package_verifier", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _distribution(root, *, requires=None, duplicate=False, extra="opencode-go"):
    files = ["limitora/__init__.py", "limitora-0.3.1.dist-info/WHEEL"]
    if duplicate:
        files.append("limitora/__init__.py")
    dist_info = root / "limitora-0.3.1.dist-info"
    dist_info.mkdir(exist_ok=True)
    (dist_info / "WHEEL").write_text("Wheel-Version: 1.0\n", encoding="utf-8")
    return SimpleNamespace(
        version="0.3.1",
        metadata=SimpleNamespace(get_all=lambda name: [extra] if name == "Provides-Extra" else []),
        requires=requires or ['httpx<1,>=0.27; extra == "opencode-go"'], files=files,
        locate_file=lambda name: root / str(name),
    )


def _package(root, source=GOOD_MODULE):
    package = root / "limitora"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(source, encoding="utf-8")


def _run(monkeypatch, module, distribution, import_root, *, cwd=None, extra_root=None):
    saved_path = list(sys.path)
    saved_modules = {n: v for n, v in sys.modules.items() if n == "limitora" or n.startswith("limitora.")}
    monkeypatch.setattr(module.metadata, "distribution", lambda name: distribution)
    monkeypatch.chdir(cwd or import_root.parent)
    sys.path[:] = [str(extra_root), str(import_root)] if extra_root else [str(import_root)]
    for name in tuple(sys.modules):
        if name == "limitora" or name.startswith("limitora."):
            del sys.modules[name]
    try:
        return module._run_verification()
    finally:
        sys.path[:] = saved_path
        for name in tuple(sys.modules):
            if name == "limitora" or name.startswith("limitora."):
                del sys.modules[name]
        sys.modules.update(saved_modules)


def test_wheel_provenance_passes(monkeypatch, tmp_path, capsys):
    root = tmp_path / "wheel-site"
    _package(root)
    result = _run(monkeypatch, _verifier(), _distribution(root), root)
    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"extra": "opencode-go", "package": "limitora", "signatures": True, "version": "0.3.1"}


def test_origin_must_match_prevalidated_distribution_file(monkeypatch, tmp_path, capsys):
    expected, loaded = tmp_path / "expected", tmp_path / "loaded"
    _package(expected)
    _package(loaded)
    assert _run(monkeypatch, _verifier(), _distribution(expected), loaded) == 1
    assert capsys.readouterr().err == "package verification failed: module_provenance_invalid: package contract rejected\n"


@pytest.mark.parametrize("requires", [
    ["opencode-go-api; extra == 'opencode-go'"],
    ['HTTPX>=0.27,<1; extra == "opencode-go"'],
    ['httpx>=0.27; extra == "opencode-go"'],
    ['httpx>=0.27,<1; extra == "other"'],
    ['httpx>=0.27,<1; extra == "opencode_go"'],
    ['httpx>=0.27,<1; extra == "opencode-go" and python_version >= "3.10"'],
    ['httpx>=0.27,<1; extra == "opencode-go"'] * 2,
    ['httpx>=0.27,>=0.27,<1; extra == "opencode-go"'],
    ['httpx>=0.27,<1,<1; extra == "opencode-go"'],
    ['httpx[]>=0.27,<1; extra == "opencode-go"'],
    ['httpx[security]>=0.27,<1; extra == "opencode-go"'],
], ids=["wrong-name", "wrong-httpx-name", "wrong-spec", "wrong-marker", "alias-marker", "compound-marker", "duplicate", "duplicate-lower", "duplicate-upper", "empty-extras", "named-extras"])
def test_extra_dependency_must_be_exact(monkeypatch, tmp_path, capsys, requires):
    root = tmp_path / "site"
    _package(root)
    assert _run(monkeypatch, _verifier(), _distribution(root, requires=requires), root) == 1
    assert capsys.readouterr().err.startswith("package verification failed: dependency_invalid:")


@pytest.mark.parametrize("extra", ["opencode_go", "OPENCODE.GO"])
def test_extra_alias_metadata_is_rejected(monkeypatch, tmp_path, capsys, extra):
    root = tmp_path / "site"
    _package(root)
    assert _run(monkeypatch, _verifier(), _distribution(root, extra=extra), root) == 1
    assert capsys.readouterr().err.startswith("package verification failed: dependency_invalid:")


def test_source_provenance_requires_wheel_metadata(monkeypatch, tmp_path, capsys):
    root = tmp_path / "source-site"
    _package(root)
    distribution = _distribution(root)
    distribution.files = ["limitora/__init__.py"]
    assert _run(monkeypatch, _verifier(), distribution, root) == 1
    assert capsys.readouterr().err.startswith("package verification failed: module_provenance_invalid:")


def test_editable_provenance_is_rejected(monkeypatch, tmp_path, capsys):
    root = tmp_path / "editable-site"
    _package(root)
    distribution = _distribution(root)
    dist_info = root / "limitora-0.3.1.dist-info"
    (dist_info / "direct_url.json").write_text('{"dir_info":{"editable":true}}', encoding="utf-8")
    distribution.files = [*distribution.files, "limitora-0.3.1.dist-info/direct_url.json"]
    assert _run(monkeypatch, _verifier(), distribution, root) == 1
    assert capsys.readouterr().err.startswith("package verification failed: module_provenance_invalid:")


def test_forged_distribution_file_cannot_bind_other_import(monkeypatch, tmp_path, capsys):
    expected, loaded = tmp_path / "forged-dist", tmp_path / "forged-import"
    _package(expected)
    _package(loaded)
    assert _run(monkeypatch, _verifier(), _distribution(expected), loaded) == 1
    assert capsys.readouterr().err.startswith("package verification failed: module_provenance_invalid:")


@pytest.mark.parametrize("source", [
    GOOD_MODULE.replace("api_key, provider", "api_key, *, provider", 1),
    GOOD_MODULE.replace("enabled=True", "enabled=False"),
], ids=["config-kind", "activation-default"])
def test_public_signatures_are_exact(monkeypatch, tmp_path, capsys, source):
    root = tmp_path / "site"
    _package(root, source)
    assert _run(monkeypatch, _verifier(), _distribution(root), root) == 1
    assert capsys.readouterr().err.startswith("package verification failed: contract_mismatch:")


@pytest.mark.parametrize("replacement", [
    ("enabled=True", "enabled=1"),
    ("timeout=timedelta(seconds=10)", "timeout=10"),
    ("timeout=timedelta(seconds=10)", "timeout=timedelta(seconds=11)"),
    ("clock=None", "clock=0"),
], ids=["bool-is-not-int", "timedelta-is-not-int", "timedelta-value", "none-is-not-value"])
def test_signature_defaults_require_exact_type_and_value(monkeypatch, tmp_path, capsys, replacement):
    root = tmp_path / "site"
    _package(root, GOOD_MODULE.replace(*replacement))
    assert _run(monkeypatch, _verifier(), _distribution(root), root) == 1
    assert capsys.readouterr().err.startswith("package verification failed: contract_mismatch:")


def test_diagnostics_are_bounded_and_path_free(monkeypatch, capsys):
    module = _verifier()
    monkeypatch.setattr(module.metadata, "distribution", lambda name: (_ for _ in ()).throw(OSError(r"C:\private\published-package\path")))
    assert module._run_verification() == 1
    error = capsys.readouterr().err
    assert error == "package verification failed: package_source_unreadable: published package source is unreadable\n"
    assert "private" not in error and "C:\\" not in error


def test_workflow_installs_published_extra_before_editable_proofs():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'python -m pip install --only-binary=:all: "limitora[opencode-go]==0.3.1"' in text
    assert 'python -m pip install -e ".[test]"' in text
    assert "python -I scripts/verify_limitora_package.py" in text
    assert text.index("verify_limitora_package.py") < text.index('python -m pip install -e ".[test]"')
    assert text.index("verify_limitora_package.py") < text.index("Invoke-NativePytestWmi")
    assert "limitora==0.1.0" not in text and ".[opencode-go,test]" not in text


def test_verifier_uses_only_the_standard_library():
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert all(value not in source for value in ("packaging", "import yasb", "pip install"))
    assert "wheel" in source and "direct_url.json" in source
    assert "sys.flags.isolated" in source and "safe_path" in source


def test_cli_rejects_non_isolated_invocation(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "package verification failed: interpreter_mode_invalid: isolated safe-path Python is required\n"


def test_isolated_cli_ignores_forged_dist_info_from_cwd(tmp_path):
    _package(tmp_path, GOOD_MODULE.replace("enabled=True", "enabled=False"))
    dist_info = tmp_path / "limitora-0.3.1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: limitora\nVersion: 0.3.1\n"
        "Provides-Extra: opencode-go\nRequires-Dist: httpx<1,>=0.27; extra == \"opencode-go\"\n",
        encoding="utf-8",
    )
    (dist_info / "RECORD").write_text("limitora/__init__.py,,\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert "interpreter_mode_invalid" not in result.stderr
    assert "contract_mismatch" not in result.stderr
