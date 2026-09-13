"""S04a focused tests: read-only YASB discovery and spike-harness static contract."""
from __future__ import annotations

import re
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

from yasb_limitora import discovery
from yasb_limitora.deadline import DeadlineContext

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "spacepath_spike.ps1"
MODULE = ROOT / "src" / "yasb_limitora" / "discovery.py"


class FakeFs:
    def __init__(self, dirs=(), reparse=(), kinds=None):
        self.dirs, self.reparse, self.kinds = set(dirs), set(reparse), dict(kinds or {})

    def is_dir(self, path):
        return path in self.dirs

    def is_reparse(self, path):
        return path in self.reparse

    def file_kind(self, path):
        return self.kinds.get(path, "missing")


def _report(env, tmp_path, **kwargs):
    probes = {"registry": lambda: ((), False), "snapshot": lambda: ()}
    probes.update(kwargs)
    merged = {**({"USERPROFILE": str(tmp_path)} if tmp_path else {}), **env}
    return discovery.discover(merged, registry=probes["registry"], snapshot=probes["snapshot"])


def test_present_safe_env_var_is_authoritative(tmp_path):
    home, profile = tmp_path / "chosen", tmp_path / "profile"
    home.mkdir()
    resolved = discovery.resolve_config_home({"YASB_CONFIG_HOME": str(home), "USERPROFILE": str(profile)})
    assert (resolved.state, resolved.path, resolved.source) == ("resolved", str(home), "YASB_CONFIG_HOME")


@pytest.mark.parametrize("value", ["", "   ", "relative\\yasb", "\\\\server\\share", "\\\\.\\C:\\dev",
                                   "\\\\?\\C:\\ext", "C:\\", "C:\\a\\..\\b", "/posix/root"])
def test_present_empty_or_unsafe_env_var_is_unsafe_without_fallback(tmp_path, value):
    env = {"YASB_CONFIG_HOME": value, "USERPROFILE": str(tmp_path)}
    resolved = discovery.resolve_config_home(env)
    assert (resolved.state, resolved.path) == ("unsafe", None)
    report = _report(env, None, snapshot=lambda: ((1, "yasb.exe"),))
    assert report.outcome == discovery.OUTCOME_INCONCLUSIVE and report.config_home is None


def test_absent_env_var_resolves_userprofile_default(tmp_path):
    resolved = discovery.resolve_config_home({"USERPROFILE": str(tmp_path)})
    assert (resolved.state, resolved.source) == ("resolved", "USERPROFILE")
    assert resolved.path == str(tmp_path) + "\\.config\\yasb"
    assert discovery.resolve_config_home({}).state == "unresolved"
    assert discovery.resolve_config_home({"USERPROFILE": "\\\\host\\share"}).state == "unresolved"


def test_reparse_or_nondirectory_components_are_unsafe():
    assert discovery.resolve_config_home({"YASB_CONFIG_HOME": r"C:\a\b"},
                                         fs=FakeFs(dirs={r"C:\a", r"C:\a\b"}, reparse={r"C:\a"})).state == "unsafe"
    assert discovery.resolve_config_home({"YASB_CONFIG_HOME": r"C:\a\b"},
                                         fs=FakeFs(kinds={r"C:\a": "file"})).state == "unsafe"


def test_env_file_is_never_parsed_and_content_never_surfaces(tmp_path):
    home = tmp_path / ".config" / "yasb"
    home.mkdir(parents=True)
    (home / ".env").write_text("SECRET_TOKEN=hunter2 ][[ not yaml", encoding="utf-8")
    report = _report({}, tmp_path, registry=lambda: (("registry:HKCU:YASB",), False))
    assert report.outcome == discovery.OUTCOME_DETECTED and report.env_file_state == "present"
    assert "hunter2" not in repr(report)


def test_absent_env_is_absent_creatable_and_nothing_is_created(tmp_path):
    report = _report({}, tmp_path, registry=lambda: (("registry:HKCU:YASB",), False))
    assert report.outcome == discovery.OUTCOME_DETECTED
    assert report.env_file_state == discovery.ENV_ABSENT_CREATABLE
    assert not (tmp_path / ".config").exists() and list(tmp_path.iterdir()) == []


def test_unsafe_env_metadata_is_inconclusive_without_reading(tmp_path):
    (tmp_path / ".config" / "yasb" / ".env").mkdir(parents=True)
    report = _report({}, tmp_path, registry=lambda: (("registry:HKCU:YASB",), False))
    assert report.env_file_state == discovery.ENV_UNSAFE and report.outcome == discovery.OUTCOME_INCONCLUSIVE
    assert discovery.classify_env_file(r"C:\h", fs=FakeFs(dirs={r"C:\h"}, kinds={r"C:\h\.env": "unreadable"})) == discovery.ENV_UNSAFE


def test_no_install_evidence_is_absent_even_with_safe_home(tmp_path):
    report = _report({}, tmp_path)
    assert report.outcome == discovery.OUTCOME_ABSENT and report.install_evidence == ()
    assert report.config_home_state == "resolved" and report.env_file_state == discovery.ENV_ABSENT_CREATABLE


def test_partial_evidence_process_probe_and_probe_error_paths(tmp_path):
    (tmp_path / "prog" / "Programs" / "yasb").mkdir(parents=True)
    partial = _report({"LOCALAPPDATA": str(tmp_path / "prog")}, tmp_path)
    assert partial.outcome == discovery.OUTCOME_DETECTED
    assert partial.install_evidence == ("directory:" + str(tmp_path / "prog" / "Programs" / "yasb"),)
    running = _report({}, tmp_path, snapshot=lambda: ((42, "yasb.exe"),))
    assert running.outcome == discovery.OUTCOME_DETECTED and running.process_status == "running"
    assert running.install_evidence == ("process:yasb.exe:42",)
    errored = _report({}, tmp_path, registry=lambda: ((), True))
    assert errored.outcome == discovery.OUTCOME_INCONCLUSIVE and "registry-probe-failed" in errored.reasons
    failed = _report({}, tmp_path, snapshot=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert failed.outcome == discovery.OUTCOME_INCONCLUSIVE and "process-snapshot-failed" in failed.reasons


def test_exhausted_deadline_is_inconclusive(tmp_path):
    spent = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0)
    report = discovery.discover({"USERPROFILE": str(tmp_path)}, context=spent)
    assert report.outcome == discovery.OUTCOME_INCONCLUSIVE and report.reasons == ("deadline-exhausted",)


def test_discovery_module_is_read_only():
    source = MODULE.read_text(encoding="utf-8")
    assert not [t for t in ("makedirs", "mkdir", "write_text", "write_bytes", "unlink", "rmtree",
                            "rename", "open(", "chdir") if t in source]


def _code_only(text):
    text = re.sub(r"<#.*?#>", "", text, flags=re.S)
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def test_spike_harness_static_contract():
    code = _code_only(SCRIPT.read_text(encoding="utf-8"))
    assert all(f"'{m}'" in code for m in ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"))
    assert all(field in code for field in
               ("yasb_version", "yasb_install_path", "run_cmd", "use_shell", "yaml_quote", "screenshot",
                "child_cmdline", "process_ancestry", "exit_code", "stdout_excerpt", "path_before",
                "path_after", "harness_revision", "candidate_sha256", "secret_scan"))
    assert code.count("use_shell = $true") == 1  # M7 diagnostic only; every other mechanism is no-shell
    normalized = code.replace('"', "'")
    assert "GetEnvironmentVariable('Path','Machine')" in normalized
    assert "GetEnvironmentVariable('Path','User')" in normalized
    forbidden = ("SetEnvironmentVariable", "Set-Content", "Add-Content", "Out-File", "Stop-Process",
                 "taskkill", "CloseMainWindow", ".Kill(", "Suspend", "Rename-Item", "Remove-Item",
                 "SelectedMechanism", "verdict", "adopt")
    assert not [token for token in forbidden if token.lower() in code.lower()]
