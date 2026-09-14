"""S02 packaging contract: onedir spec, version template, build driver, smoke driver."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = _ROOT / "packaging" / "pyinstaller" / "yasb-limitora.spec"
_TEMPLATE = _ROOT / "packaging" / "pyinstaller" / "version_info.txt.in"


def _load(name: str, path: Path):
    found = importlib.util.spec_from_file_location(name, path)
    assert found is not None and found.loader is not None
    module = importlib.util.module_from_spec(found)
    found.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_mod():
    return _load("s02_build_frozen_bundle", _ROOT / "scripts" / "build_frozen_bundle.py")


@pytest.fixture(scope="module")
def spec_text() -> str:
    return _SPEC.read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    """Strip the module docstring and # comments so assertions inspect real construction."""
    stripped = re.sub(r'\A\s*"""(?s:.)*?"""', "", text, count=1)
    return "\n".join(line for line in stripped.splitlines() if not line.lstrip().startswith("#"))


class TestSpec:
    def test_onedir_console_entry(self, spec_text):
        code = _code_only(spec_text)
        assert re.search(r"EXE\((?s:.*?)exclude_binaries=True", code) and "COLLECT(" in code
        assert re.search(r"EXE\((?s:.*?)console=True", code)
        assert "yasb_limitora.cli import main" in code and "sys.exit(main())" in code

    def test_pyinstaller_range_upx_collection(self, spec_text):
        code = _code_only(spec_text)
        assert re.search(r"int\(_pyinstaller_version\.split\(\"\.\", 1\)\[0\]\) != 6", code)
        assert ">=6,<7" in code
        assert code.count("upx=False") >= 2
        assert 'collect_submodules("limitora")' in code

    def test_construction_checks_ignore_docstring_mutant(self):
        mutant = '"""console=True upx=False COLLECT( >=6,<7 datas=[] """\n# collect_submodules("limitora")\n'
        code = _code_only(mutant)
        assert "console=True" not in code and "upx=False" not in code and "COLLECT(" not in code
        assert 'collect_submodules("limitora")' not in code and "datas=[]" not in code

    def test_no_repo_datas(self, spec_text):
        code = _code_only(spec_text)
        assert re.search(r"datas\s*=\s*\[\s*\]", code)
        for banned in ("examples/", "docs/", "fixtures", "Tree("):
            assert banned not in code

    def test_template_is_placeholder_driven(self):
        text = _TEMPLATE.read_text(encoding="utf-8")
        assert "@@VERSION@@" in text and "@@VERSION_TUPLE@@" in text and "VSVersionInfo" in text
        assert "0.2.0" not in text and "0.1.0" not in text and "yasb-limitora.exe" in text


class TestBuildDriver:
    def test_version_single_source(self, build_mod):
        assert build_mod.read_product_version(_ROOT) == "0.2.0"

    def test_render_version_info(self, build_mod):
        rendered = build_mod.render_version_info("0.2.0", _TEMPLATE.read_text(encoding="utf-8"))
        assert "(0, 2, 0, 0)" in rendered and "'0.2.0'" in rendered and "@@" not in rendered

    @pytest.mark.parametrize(("raw", "ok"),
                             [("6.11.1", True), ("5.13.2", False), ("7.0", False), (None, False)])
    def test_pyinstaller_enforcement(self, build_mod, raw, ok):
        if ok:
            assert build_mod.check_pyinstaller_version(raw) == raw
        else:
            with pytest.raises(build_mod.BuildError, match=re.escape(">=6,<7")):
                build_mod.check_pyinstaller_version(raw)

    def test_source_date_epoch_env_wins(self, build_mod):
        identity = build_mod.capture_source_identity(_ROOT, env={"SOURCE_DATE_EPOCH": "1700000000"})
        assert identity["source_date_epoch"] == "1700000000" and identity["source_commit"]

    def test_source_date_epoch_propagated_to_subprocess(self, build_mod, tmp_path):
        captured: list[dict[str, str]] = []

        def runner(cmd, **kwargs):
            captured.append(dict(kwargs["env"]))
            exe = Path(kwargs["env"]["_TEST_DIST"]) / "yasb-limitora" / "yasb-limitora.exe"
            exe.parent.mkdir(parents=True, exist_ok=True)
            exe.write_bytes(b"MZ")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        dist = tmp_path / "dist"
        build_mod.run_build(repo_root=_ROOT, output_root=tmp_path,
                            version_info_path=tmp_path / "v.txt", runner=runner,
                            env={"_TEST_DIST": str(dist)}, source_date_epoch="1234567890")
        assert captured[0]["SOURCE_DATE_EPOCH"] == "1234567890"

    def test_build_info_record_bounded(self, build_mod):
        record = build_mod.build_info_record(
            version="0.2.0", source_commit="a" * 40, source_date_epoch="1700000000",
            python_version="3.13.1", pyinstaller_version="6.11.1", limitora_version="0.3.1")
        assert set(record) == {"version", "source_commit", "python", "pyinstaller",
                               "limitora", "source_date_epoch"}
        blob = json.dumps(record)
        assert ":\\" not in blob and "\\\\" not in blob

    def test_missing_hidden_import_diagnostic(self, build_mod):
        diag = build_mod.diagnose_failure(
            1, "ModuleNotFoundError: No module named 'limitora.providers.foo'")
        assert "hidden-import" in diag and "limitora.providers.foo" in diag

    def test_build_failure_removes_output(self, build_mod, tmp_path):
        calls = []

        def runner(cmd, **kwargs):
            calls.append(cmd)
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()

        dist = tmp_path / "dist" / "yasb-limitora"
        dist.mkdir(parents=True)
        with pytest.raises(build_mod.BuildError) as exc:
            build_mod.run_build(repo_root=_ROOT, output_root=tmp_path,
                                version_info_path=tmp_path / "v.txt", runner=runner, env={})
        assert exc.value.reason_code == "build_failed" and "boom" in exc.value.detail
        assert not dist.exists() and calls
