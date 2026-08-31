"""Verify the installed published Limitora OpenCode package contract.

The check is package-only: it validates metadata, provenance, the released
root API, and construction of a redacted dummy configuration. It never reads
credentials, activates a provider, imports or installs YASB, or uses network.
"""

from __future__ import annotations

from datetime import timedelta
import importlib
import importlib.metadata as metadata
import importlib.util
import inspect
import json
from pathlib import Path, PurePosixPath
import re
import sys

PACKAGE = "limitora"
EXPECTED_VERSION = "0.3.1"
EXTRA = "opencode-go"
DUMMY = "package-verification-dummy"
EXTRA_EQUALITY = re.compile(r"\bextra\s*==\s*(['\"])([^'\"]*)\1")
EXTRA_MARKER = re.compile(r"\s*extra\s*==\s*(['\"])opencode-go\1\s*")
REQUIREMENT = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([^\]]*)\])?\s*(.*)\s*")


class _Failure(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def _require(condition: bool, code: str = "contract_mismatch") -> None:
    if not condition:
        raise _Failure(code)


def _file(value: object) -> Path:
    path = Path(value).resolve(strict=True)
    _require(path.is_file(), "module_provenance_invalid")
    return path


def _wheel_origin(distribution: object) -> Path | None:
    files = getattr(distribution, "files", None)
    if files is None:
        return None
    paths = [PurePosixPath(str(item)) for item in files]
    wheel_files = [item for item, path in zip(files, paths) if path.name == "WHEEL" and path.parent.name.endswith(".dist-info")]
    _require(len(wheel_files) == 1, "module_provenance_invalid")
    _require(
        not any(path.name == "direct_url.json" and path.parent.name.endswith(".dist-info") for path in paths),
        "module_provenance_invalid",
    )
    matches = [item for item in files if PurePosixPath(str(item)).as_posix() == f"{PACKAGE}/__init__.py"]
    _require(len(matches) == 1, "module_provenance_invalid")
    locate = getattr(distribution, "locate_file", None)
    _require(locate is not None, "module_provenance_invalid")
    _file(locate(wheel_files[0]))
    return _file(locate(matches[0]))


def _expected_origin(distribution: object) -> Path:
    wheel = _wheel_origin(distribution)
    _require(wheel is not None, "module_provenance_invalid")
    return wheel


def _normalize_extra(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _load(expected: Path):
    spec = importlib.util.find_spec(PACKAGE)
    _require(spec is not None and spec.origin is not None, "module_provenance_invalid")
    _require(_file(spec.origin) == expected, "module_provenance_invalid")
    module = importlib.import_module(PACKAGE)
    loaded_file = getattr(module, "__file__", None)
    loaded_spec = getattr(module, "__spec__", None)
    loaded_origin = getattr(loaded_spec, "origin", None)
    _require(loaded_file is not None and loaded_origin is not None, "module_provenance_invalid")
    _require(_file(loaded_file) == expected and _file(loaded_origin) == expected, "module_provenance_invalid")
    return module


def _validate_extra(distribution: object) -> None:
    extras = list(distribution.metadata.get_all("Provides-Extra") or ())
    _require(len(extras) == 1 and extras[0] == EXTRA and _normalize_extra(extras[0]) == EXTRA, "dependency_invalid")
    requires = list(distribution.requires or ())
    _require(len(requires) == 1, "dependency_invalid")
    requirement, separator, marker = str(requires[0]).partition(";")
    marker_names = tuple(_normalize_extra(match.group(2)) for match in EXTRA_EQUALITY.finditer(marker))
    _require(separator and marker_names == (EXTRA,) and EXTRA_MARKER.fullmatch(marker), "dependency_invalid")
    parsed = REQUIREMENT.fullmatch(requirement)
    _require(parsed is not None, "dependency_invalid")
    name, extras_text, specifier = parsed.groups()
    parts = tuple(part.strip() for part in specifier.split(","))
    _require(name == "httpx" and extras_text is None and len(parts) == 2 and len(set(parts)) == 2 and set(parts) == {">=0.27", "<1"}, "dependency_invalid")

def _validate_signatures(module: object) -> None:
    expected_config = (
        ("api_key", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("provider", inspect.Parameter.POSITIONAL_OR_KEYWORD, EXTRA),
        ("timeout", inspect.Parameter.POSITIONAL_OR_KEYWORD, timedelta(seconds=10)),
    )
    expected_activate = (
        ("config", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
        ("enabled", inspect.Parameter.KEYWORD_ONLY, True),
        ("clock", inspect.Parameter.KEYWORD_ONLY, None),
    )
    config = tuple(inspect.signature(getattr(module, "OpenCodeGoConfig")).parameters.values())
    activate = tuple(inspect.signature(getattr(module, "activate_provider")).parameters.values())
    def matches(actual, expected) -> bool:
        if expected is None:
            return actual is None
        return type(actual) is type(expected) and actual == expected

    _require(
        len(config) == len(expected_config)
        and all(
            actual.name == name and actual.kind is kind and matches(actual.default, default)
            for actual, (name, kind, default) in zip(config, expected_config)
        )
    )
    _require(
        len(activate) == len(expected_activate)
        and all(
            actual.name == name and actual.kind is kind and matches(actual.default, default)
            for actual, (name, kind, default) in zip(activate, expected_activate)
        )
    )


def _run_verification() -> int:
    try:
        distribution = metadata.distribution(PACKAGE)
        _require(distribution.version == EXPECTED_VERSION)
        _validate_extra(distribution)
        module = _load(_expected_origin(distribution))
        _validate_signatures(module)
        dummy = module.OpenCodeGoConfig(api_key=DUMMY, timeout=timedelta(seconds=7))
        _require(DUMMY not in repr(dummy))
        print(json.dumps({"extra": EXTRA, "package": PACKAGE, "signatures": True, "version": distribution.version}, sort_keys=True))
        return 0
    except _Failure as error:
        print(f"package verification failed: {error.code}: package contract rejected", file=sys.stderr)
    except ImportError:
        print("package verification failed: dependency_missing: required package dependency is unavailable", file=sys.stderr)
    except OSError:
        print("package verification failed: package_source_unreadable: published package source is unreadable", file=sys.stderr)
    except (TypeError, ValueError, AttributeError):
        print("package verification failed: published_api_invalid: published package API value is invalid", file=sys.stderr)
    except Exception:
        print("package verification failed: verification_failed: package verification could not complete", file=sys.stderr)
    return 1


def main() -> int:
    try:
        _require(bool(sys.flags.isolated and getattr(sys.flags, "safe_path", False)), "interpreter_mode_invalid")
    except _Failure as error:
        print(f"package verification failed: {error.code}: isolated safe-path Python is required", file=sys.stderr)
        return 1
    return _run_verification()


if __name__ == "__main__":
    raise SystemExit(main())
