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


def test_pytest_privacy_summary_rejects_raw_diagnostics(tmp_path):
    raw = tmp_path / "pytest.raw"
    report = tmp_path / "pytest.xml"
    status = tmp_path / "status.json"
    raw.write_text("Traceback (most recent call last): C:\\Users\\runner\\secret.py\n", encoding="utf-8")
    report.write_text('<testsuites><testsuite tests="1" skipped="0" failures="1" errors="0" /></testsuites>', encoding="utf-8")
    with pytest.raises(ValueError):
        write_safe_pytest_status(raw, report, 1, status)
    assert not status.exists()


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
