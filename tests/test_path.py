import pytest  # pyright: ignore[reportMissingImports] - optional test dependency is present at runtime

from yasb_limitora.path import (
    PathError,
    canonicalize_path,
    path_identity,
)


@pytest.mark.parametrize(
    ("first", "second"),
    ((r"C:\Config\..\config.json", r"c:/config.json"), ("C:\\config.json\\", r"c:/config.json")),
)
def test_lexical_path_identity_ignores_alias_spelling(first, second):
    assert path_identity(first) == path_identity(second)


def test_missing_path_is_accepted_without_lookup(monkeypatch):
    def unexpected_lookup(*args, **kwargs):
        raise AssertionError("canonicalization performed a filesystem lookup")

    monkeypatch.setattr("pathlib.Path.exists", unexpected_lookup)
    assert canonicalize_path(r"C:\missing\config.json") == r"C:\missing\config.json"


@pytest.mark.parametrize("path", (r"\\?\C:\config.json", r"\\.\pipe\config", r"\\server\share\config.json"))
def test_device_and_unc_paths_are_rejected(path):
    with pytest.raises(PathError):
        canonicalize_path(path)


@pytest.mark.parametrize("path", ("//server/share/config.json", "//?/C:/config.json"))
def test_forward_slash_unc_and_device_paths_are_rejected_before_open(path):
    with pytest.raises(PathError):
        canonicalize_path(path)


def test_utf16_path_limit_is_checked_before_open():
    accepted = "C:\\" + "a" * (32_767 - 3)
    rejected = "C:\\" + "a" * (32_768 - 3)
    assert len(canonicalize_path(accepted).encode("utf-16-le")) // 2 == 32_767
    with pytest.raises(PathError):
        canonicalize_path(rejected)
