from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import pytest

from tests.r10_yasb_support import load_lock, validate_lock, verify_yasb_module, write_safe_pytest_status


def test_lock_accepts_only_the_pinned_sources_and_hashes():
    validate_lock(load_lock())


@pytest.mark.parametrize(
    ("path", "value"),
    (("commit", "main"), ("repository", "https://example.invalid/yasb"), ("archive_url", "https://github.com/amnweb/yasb/archive/main.tar.gz")),
)
def test_lock_rejects_floating_or_unexpected_identity(path, value):
    lock = copy.deepcopy(load_lock())
    lock["sources"][0][path] = value
    with pytest.raises(ValueError):
        validate_lock(lock)


@pytest.mark.parametrize("field", ("sha256", "filename"))
def test_lock_rejects_missing_artifact_identity(field):
    lock = copy.deepcopy(load_lock())
    lock["sources"][1].pop(field)
    with pytest.raises(ValueError):
        validate_lock(lock)


@pytest.mark.parametrize(("raw_text", "report_text", "exit_code", "expected"), [
    ("5 passed\n", '<testsuites><testsuite tests="1" skipped="0" failures="1" errors="0"><testcase name="test_real_yasb_205_custom_widget_is_imported_constructed_and_observed"><failure /></testcase></testsuite></testsuites>', 1, "admission_case_failed"),
    ("5 passed\n", '<testsuites><testsuite tests="1" skipped="1" failures="0" errors="0"><testcase name="lock" /></testsuite></testsuites>', 0, "admission_case_not_executed"),
    ("5 passed\n", None, 1, "junit_unavailable"),
    ("Traceback: C:\\Users\\runner\\secret.py\n", '<testsuites />', 1, "diagnostics_rejected"),
    ("5 passed\n", '<testsuites><testsuite tests="1" skipped="0" failures="0" errors="0"><testcase name="test_real_yasb_205_custom_widget_is_imported_constructed_and_observed" /></testsuite></testsuites>', 0, "admission_case_passed"),
])
def test_pytest_summary_classifies_failures_without_raw_diagnostics(tmp_path, raw_text, report_text, exit_code, expected):
    raw = tmp_path / "pytest.raw"
    report = tmp_path / "pytest.xml"
    status = tmp_path / "status.json"
    raw.write_text(raw_text, encoding="utf-8")
    if report_text is None: report.unlink(missing_ok=True)
    else: report.write_text(report_text, encoding="utf-8")
    write_safe_pytest_status(raw, report, exit_code, status, "test_real_yasb_205_custom_widget_is_imported_constructed_and_observed")
    value = __import__("json").loads(status.read_text(encoding="utf-8"))
    assert value["classification"] == expected and value["privacy"] in {"passed", "rejected"}


@pytest.mark.windows_yasb_admission
@pytest.mark.skipif(os.name != "nt", reason="real YASB admission requires Windows")
def test_real_yasb_205_custom_widget_is_imported_constructed_and_observed():
    if sys.version_info[:2] != (3, 14):
        pytest.fail("R10 admission requires isolated Python 3.14")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from core.validation.widgets.yasb.custom import CustomConfig
    from core.widgets.yasb.custom import CustomWidget

    source = verify_yasb_module(__import__("inspect").getfile(CustomWidget))
    assert source.name == "custom.py" and Path(__file__).parents[1] not in source.parents
    app = QApplication.instance() or QApplication([])
    config = CustomConfig.model_validate(
        {
            "class_name": "r10-admission",
            "label": "Admission {data[status]}",
            "tooltip": False,
            "exec_options": {"run_cmd": None, "run_once": False, "run_interval": 120000, "use_shell": False},
        }
    )
    widget = CustomWidget(config)
    widget._handle_exec_data({"status": "observed"})
    widget.show()
    app.processEvents()
    assert type(widget).__module__ == "core.widgets.yasb.custom"
    assert widget._widgets[0].text() == "Admission observed"
    assert widget.isVisible()
    widget.timer.stop()
    widget.deleteLater()
