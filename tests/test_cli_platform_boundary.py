import io
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from yasb_limitora import cli
from yasb_limitora.cli import main

UNSUPPORTED_PLATFORM = "yasb-limitora: unsupported_platform\n"
ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("argv", ((), ("--anything",), ("--config",)))
def test_non_windows_rejects_exactly_without_stdout(argv):
    stdout, stderr = io.BytesIO(), io.StringIO()

    assert main(argv, platform_is_windows=lambda: False, stdout=stdout, stderr=stderr) == 2
    assert stdout.getvalue() == b""
    assert stderr.getvalue() == UNSUPPORTED_PLATFORM


class _ExplodingSequence:
    def __iter__(self):
        raise AssertionError("argv was inspected before platform rejection")


class _ExplodingEnvironment:
    def get(self, *args, **kwargs):
        raise AssertionError("environment was inspected before platform rejection")

    def __contains__(self, item):
        raise AssertionError("environment was inspected before platform rejection")


def test_non_windows_rejects_before_product_side_effects(monkeypatch):
    events = []

    def unexpected(*args, **kwargs):
        events.append((args, kwargs))
        raise AssertionError("product execution started before platform rejection")

    monkeypatch.setattr(cli, "_output_version", unexpected)
    monkeypatch.setattr(cli, "_config_path", unexpected)
    monkeypatch.setattr(cli, "_resolve_config_path", unexpected)
    monkeypatch.setattr(cli, "_load", unexpected)
    monkeypatch.setattr(cli, "_load_v2_path", unexpected)
    monkeypatch.setattr(cli.time, "monotonic_ns", unexpected)
    monkeypatch.setattr(cli, "RuntimeCoordinator", unexpected)
    monkeypatch.setattr(cli, "V2ExecutionOrchestrator", unexpected)
    monkeypatch.setattr(cli, "_write", unexpected)
    stdout, stderr = io.BytesIO(), io.StringIO()

    assert main(
        cast(Sequence[str], _ExplodingSequence()),
        environment=cast(Mapping[str, str], _ExplodingEnvironment()),
        stdout=stdout,
        stderr=stderr,
        platform_is_windows=lambda: False,
    ) == 2
    assert events == []
    assert stdout.getvalue() == b""
    assert stderr.getvalue() == UNSUPPORTED_PLATFORM


@pytest.mark.skipif(os.name == "nt", reason="non-Windows boundary subprocess proof runs on non-Windows")
@pytest.mark.parametrize("argv", ((), ("--bad",), ("--config",)))
def test_public_routes_have_identical_non_windows_rejection(argv):
    console_script = shutil.which("yasb-limitora")
    if console_script is None:
        pytest.fail("installed yasb-limitora console script not found")

    environment = os.environ.copy()
    environment["YASB_LIMITORA_CONFIG"] = str(ROOT / "must-not-be-read.json")
    routes = (
        [console_script, *argv],
        [sys.executable, "-m", "yasb_limitora", *argv],
    )
    results = [
        subprocess.run(
            route,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            check=False,
        )
        for route in routes
    ]

    assert [(result.returncode, result.stdout, result.stderr) for result in results] == [
        (2, b"", UNSUPPORTED_PLATFORM.encode())
    ] * 2
