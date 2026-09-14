"""S04a focused tests: read-only YASB discovery and spike-harness static contract."""
from __future__ import annotations

import inspect
import ntpath
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


# --- S04c: bounded adoption of the G2a-selected M6 mechanism (8.3 short-path alias, no PATH, no shell) ---
EXE = r"C:\apps\yasb-limitora\yasb-limitora.exe"
SPACED = r"C:\my apps\yasb-limitora\yasb-limitora.exe"
ALIAS = r"C:\MYAPPS~1\yasb-limitora\YASB-L~1.EXE"


def _ancestor_dirs(path):
    """Return the set of every parent below the drive root of a backslash path."""
    out = set()
    while re.fullmatch(r"[A-Za-z]:\\.+\\.*", path):
        path = ntpath.dirname(path)
        out.add(path)
    return out


class FakeIdentity:
    def __init__(self, ids=None):
        self.ids = dict(ids or {})

    def __call__(self, path):
        return self.ids.get(path)


def _resolve(exe=EXE, *, dirs=None, reparse=(), kinds=None, ids=None,
             short=lambda p: None, expected="yasb-limitora.exe"):
    if dirs is None:
        dirs = _ancestor_dirs(exe)
    k = {exe: "file"}
    k.update(kinds or {})
    fs = FakeFs(dirs=set(dirs), reparse=set(reparse), kinds=k)
    return discovery.resolve_installed_invocation(
        exe, expected_basename=expected, fs=fs,
        identity=FakeIdentity(ids), short_path=short)


def _poison(_):
    raise AssertionError("short-path API must not be consulted for this input")


def test_spacefree_path_resolves_literal_m6_sf_command():
    assert _resolve() == ("resolved", EXE, "SF", "M6", False, None)
    assert _resolve().use_shell is False and _resolve().command == EXE


def test_spaced_path_accepts_only_bound_spacefree_alias_sp83():
    result = _resolve(SPACED, dirs=_ancestor_dirs(SPACED) | _ancestor_dirs(ALIAS),
                      kinds={SPACED: "file", ALIAS: "file"},
                      ids={SPACED: "id-1", ALIAS: "id-1"}, short=lambda p: ALIAS)
    assert result == ("resolved", ALIAS, "SP-83", "M6", False, None)


INVALID = [
    (r"relative\yasb-limitora.exe", "file", "path-unsafe"),
    (r"\\server\share\yasb-limitora.exe", "file", "path-unsafe"),
    (r"\\.\C:\dev\yasb-limitora.exe", "file", "path-unsafe"),
    (r"C:\a\..\yasb-limitora.exe", "file", "path-unsafe"),
    (r"C:\yasb-limitora.exe", "file", "path-unsafe"),
    (r"C:\apps\gone\yasb-limitora.exe", "missing", "exe-missing"),
    (EXE, "dir", "exe-unsafe"),
    (EXE, "unreadable", "exe-unsafe"),
    (r"C:\apps\yasb-limitora\yasb.exe", "file", "basename-mismatch"),
]


@pytest.mark.parametrize("exe,exe_kind,reason", INVALID)
def test_invalid_input_yields_no_command_and_no_fallback(exe, exe_kind, reason):
    assert _resolve(exe, kinds={exe: exe_kind}, short=_poison) == ("invalid-input", None, None, None, False, reason)


def test_missing_source_ancestor_is_rejected_before_short_api():
    assert _resolve(EXE, dirs=(), kinds={EXE: "file"}, short=_poison) == ("invalid-input", None, None, None, False, "path-unsafe")


@pytest.mark.parametrize("exe", [r"C:\apps/yasb-limitora\yasb-limitora.exe", r"C:\apps\yasb-limitora\\yasb-limitora.exe"])
def test_noncanonical_source_spelling_is_rejected_before_short_api(exe):
    assert _resolve(exe, short=_poison) == ("invalid-input", None, None, None, False, "path-unsafe")


def test_lowercase_drive_spelling_is_canonical_and_case_preserved():
    lower = EXE.replace("C:", "c:", 1)
    assert _resolve(lower, short=_poison) == ("resolved", lower, "SF", "M6", False, None)


def test_spaced_alias_failures_report_sp_no83_without_command():
    bound = {SPACED: "id-1", ALIAS: "id-1"}
    cases = [
        (lambda p: None, bound, "short-name-unavailable"),
        (lambda p: (_ for _ in ()).throw(RuntimeError("boom")), bound, "short-name-unavailable"),
        (lambda p: "", bound, "short-name-unavailable"),
        (lambda p: r"C:\my alias\YASB-L~1.EXE", bound, "alias-contains-space"),
        (lambda p: r"relative\YASB-L~1.EXE", bound, "alias-unsafe"),
        (lambda p: ALIAS, {SPACED: "id-1", ALIAS: "id-2"}, "alias-identity-mismatch"),
        (lambda p: ALIAS, {SPACED: "id-1"}, "alias-identity-mismatch"),
        (lambda p: ALIAS, {}, "alias-identity-mismatch"),
    ]
    for short, ids, reason in cases:
        result = _resolve(SPACED, dirs=_ancestor_dirs(SPACED) | _ancestor_dirs(ALIAS),
                          kinds={SPACED: "file", ALIAS: "file"}, ids=ids, short=short)
        assert result == ("sp-no83", None, "SP-no83", "M6", False, reason), reason


def test_missing_alias_ancestor_reports_sp_no83_alias_unsafe():
    result = _resolve(SPACED, kinds={SPACED: "file", ALIAS: "file"},
                      ids={SPACED: "id-1", ALIAS: "id-1"}, short=lambda p: ALIAS)
    assert result == ("sp-no83", None, "SP-no83", "M6", False, "alias-unsafe")


@pytest.mark.parametrize("alias", [r"C:\MYAPPS~1/yasb-limitora\YASB-L~1.EXE", r"C:\MYAPPS~1\yasb-limitora\\YASB-L~1.EXE"])
def test_noncanonical_alias_spelling_reports_sp_no83(alias):
    result = _resolve(SPACED, dirs=_ancestor_dirs(SPACED) | _ancestor_dirs(alias),
                      kinds={SPACED: "file", alias: "file"},
                      ids={SPACED: "id-1", alias: "id-1"}, short=lambda p: alias)
    assert result == ("sp-no83", None, "SP-no83", "M6", False, "alias-unsafe")


def test_reparse_point_ancestor_is_rejected_without_short_path_lookup():
    assert _resolve(reparse={r"C:\apps"}, short=_poison) == ("invalid-input", None, None, None, False, "path-unsafe")


def test_nested_reparse_ancestor_and_dot_segment_are_rejected():
    assert _resolve(reparse={r"C:\apps\yasb-limitora"}, short=_poison) == ("invalid-input", None, None, None, False, "path-unsafe")
    dotted = r"C:\apps\.\yasb-limitora.exe"
    assert _resolve(dotted, short=_poison) == ("invalid-input", None, None, None, False, "path-unsafe")


@pytest.mark.parametrize("alias_kind", ["unreadable", "dir", "missing"])
def test_alias_leaf_non_file_reports_sp_no83_even_with_matching_identity(alias_kind):
    result = _resolve(SPACED, dirs=_ancestor_dirs(SPACED) | _ancestor_dirs(ALIAS),
                      kinds={SPACED: "file", ALIAS: alias_kind},
                      ids={SPACED: "id-1", ALIAS: "id-1"}, short=lambda p: ALIAS)
    assert result == ("sp-no83", None, "SP-no83", "M6", False, "alias-unsafe")


def test_alias_with_reparse_ancestor_reports_sp_no83():
    result = _resolve(SPACED, dirs=_ancestor_dirs(SPACED) | _ancestor_dirs(ALIAS),
                      reparse={r"C:\MYAPPS~1"},
                      kinds={SPACED: "file", ALIAS: "file"},
                      ids={SPACED: "id-1", ALIAS: "id-1"}, short=lambda p: ALIAS)
    assert result == ("sp-no83", None, "SP-no83", "M6", False, "alias-unsafe")


def test_invocation_api_surface_has_no_env_or_path_input():
    params = inspect.signature(discovery.resolve_installed_invocation).parameters
    assert set(params) == {"exe_path", "expected_basename", "fs", "short_path", "identity"}
    assert all(p.kind is p.KEYWORD_ONLY for name, p in params.items() if name != "exe_path")


def test_default_short_path_wrapper_is_read_only_and_bounded(tmp_path):
    exe = tmp_path / "yasb-limitora.exe"
    exe.write_bytes(b"MZ")
    assert discovery.get_short_path_name(str(exe)) is None or isinstance(discovery.get_short_path_name(str(exe)), str)
    assert discovery.get_short_path_name(str(tmp_path / "missing.exe")) is None


def test_defaults_resolve_real_spacefree_file(tmp_path):
    if " " in str(tmp_path):
        pytest.skip("temp path contains a space; SF default case needs a space-free path")
    exe = tmp_path / "yasb-limitora.exe"
    exe.write_bytes(b"MZ")
    assert discovery.resolve_installed_invocation(str(exe)) == ("resolved", str(exe), "SF", "M6", False, None)


def test_defaults_on_real_spaced_path_are_machine_honest(tmp_path):
    exe = tmp_path / "my apps" / "yasb-limitora.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    result = discovery.resolve_installed_invocation(str(exe))
    if result.state == "resolved":
        assert (result.machine_class, result.mechanism, result.use_shell) == ("SP-83", "M6", False)
        assert result.command is not None and " " not in result.command
    else:
        assert result.state == "sp-no83" and result.command is None and result.machine_class == "SP-no83"
