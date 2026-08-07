import os

import pytest

from yasb_limitora.v2_deadline import DeadlineContext
from yasb_limitora.v2_path import V2FileError, read_v2_config


def _context():
    return DeadlineContext(t0_ns=0, deadline_ns=10_000, reserve_ns=2_000, clock_ns=lambda: 0)


def test_v2_config_read_accepts_16384_bytes_and_rejects_the_extra_byte(tmp_path):
    valid = tmp_path / "valid.json"
    valid.write_bytes(b"{" + b" " * 16_382 + b"}")
    assert len(read_v2_config(valid, _context())) == 16_384

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 16_385)
    with pytest.raises(V2FileError):
        read_v2_config(oversized, _context())


def test_v2_config_read_rejects_non_regular_files_without_fallback(tmp_path):
    with pytest.raises(V2FileError):
        read_v2_config(tmp_path, _context())


def test_v2_config_read_does_not_open_after_deadline_expiry(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    opened = []
    expired = DeadlineContext(t0_ns=0, deadline_ns=0, reserve_ns=0, clock_ns=lambda: 1)

    def open_file(*args):
        opened.append(args)
        return os.open(*args)

    with pytest.raises(V2FileError):
        read_v2_config(path, expired, open_fn=open_file)
    assert opened == []


def test_v2_config_read_close_failure_is_sanitized(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")

    def close_file(_fd):
        raise OSError("private close detail")

    with pytest.raises(V2FileError) as error:
        read_v2_config(path, _context(), close_fn=close_file)
    assert str(error.value) == "configuration read failed"
