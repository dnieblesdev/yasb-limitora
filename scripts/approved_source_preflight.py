"""Fail-closed import-identity preflight against an out-of-band approved-source anchor.

This gate never authorizes a native run. It compares a candidate checkout against an
anchor that was frozen elsewhere and pinned by digest, so the candidate cannot certify
itself.

Usage (dedicated venv, isolated):
    <dedicated-python> -B -I -E approved_source_preflight.py \
        --candidate-root ROOT --anchor ANCHOR.json \
        --anchor-sha256 DIGEST --expected-executable PYTHON

Exit 0: sanitized PASS with identity evidence. Exit 1: sanitized FAIL with a reason code.
No native test, provider call, installation, or network access is performed.

Trust model:
  * the anchor file must live outside the candidate checkout (self-declaration refused);
  * the anchor must match the separately supplied pinned digest, so a swapped anchor is
    rejected even when it is internally consistent;
  * every required module must exist in the candidate at the anchored digest, resolve to
    the candidate package root, and import as a source file from that root;
  * an unexpected editable distribution and an unexpected candidate identity both fail.
"""
import argparse
import hashlib
import importlib
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname


SCHEMA = 1
PACKAGE = "src/yasb_limitora"
REQUIRED = ("__init__", "_native_proof_observability")
DIGEST = re.compile(r"[0-9a-f]{64}")


class Rejected(Exception):
    """Carries only a fixed public reason code."""


def require(condition, reason):
    if not condition:
        raise Rejected(reason)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Rejected("CLI_INVALID")


def canonical(path):
    return Path(path).resolve(strict=True)


def canonical_anchor_bytes(anchor):
    return (json.dumps(anchor, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def validate_anchor_files(files):
    """Shared shape gate: every anchored path must be a plain package-relative .py file."""
    require(isinstance(files, dict) and bool(files), "ANCHOR_INVALID")
    for relative, digest in files.items():
        require(isinstance(relative, str) and isinstance(digest, str)
                and DIGEST.fullmatch(digest) is not None, "ANCHOR_INVALID")
        parsed = PurePosixPath(relative)
        require(relative == parsed.as_posix() and parsed.parts[:2] == ("src", "yasb_limitora")
                and ".." not in parsed.parts and parsed.suffix == ".py", "ANCHOR_INVALID")
    for name in REQUIRED:
        require(f"{PACKAGE}/{name}.py" in files, "ANCHOR_INVALID")


def load_anchor(anchor_path, expected_digest, candidate_root):
    """Read the anchor from outside the candidate and authenticate it by pinned digest."""
    path = canonical(anchor_path)
    require(not path.is_relative_to(candidate_root), "ANCHOR_INSIDE_CANDIDATE")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_digest, "ANCHOR_DIGEST_MISMATCH")
    try:
        anchor = json.loads(raw.decode("utf-8"))
    except Exception:
        raise Rejected("ANCHOR_INVALID")
    require(isinstance(anchor, dict), "ANCHOR_INVALID")
    require(set(anchor) == {"schema", "approved_revision", "approved_tree", "version", "files"},
            "ANCHOR_INVALID")
    require(type(anchor["schema"]) is int and anchor["schema"] == SCHEMA, "ANCHOR_INVALID")
    require(isinstance(anchor["version"], str) and anchor["version"], "ANCHOR_INVALID")
    for key in ("approved_revision", "approved_tree"):
        require(isinstance(anchor[key], str) and re.fullmatch(r"[0-9a-f]{40}", anchor[key]) is not None,
                "ANCHOR_INVALID")
    files = anchor["files"]
    validate_anchor_files(files)
    # Re-encoding must reproduce the matched bytes, so the digest covers the whole anchor.
    require(canonical_anchor_bytes(anchor) == raw, "ANCHOR_NONCANONICAL")
    return anchor


def check_spec(name, expected):
    spec = importlib.util.find_spec(name)
    require(spec is not None and isinstance(spec.loader, importlib.machinery.SourceFileLoader)
            and isinstance(spec.origin, str), "ORIGIN_UNKNOWN")
    require(canonical(spec.origin) == expected, "ORIGIN_MISMATCH")
    return spec


def editable_root(data):
    url = urlsplit(data["url"])
    require(url.scheme == "file" and not url.query and not url.fragment
            and url.netloc in ("", "localhost"), "METADATA_UNKNOWN")
    return canonical(url2pathname(unquote(url.path)))


def canonical_bytes(path):
    """Bytes as Git's canonical content: line endings normalised to LF.

    A working tree is not a byte store. With core.autocrlf enabled (or a text attribute)
    Git checks text files out with CRLF while the blob is stored LF, so hashing raw working
    -tree bytes would reject a legitimate checkout. Normalising to the canonical form keeps
    the check portable across platforms. The consequence is documented: a change that only
    alters line endings is not a content divergence.
    """
    return path.read_bytes().replace(b"\r\n", b"\n")


def module_name(relative):
    """Dotted module name for an anchored path, including subpackages.

    Using only the file stem would collide on every `__init__.py` in the package.
    """
    parts = PurePosixPath(relative).parts[2:]
    *package_parts, filename = parts
    stem = filename[:-3] if filename.endswith(".py") else filename
    dotted = ".".join(["yasb_limitora", *package_parts])
    return dotted if stem == "__init__" else f"{dotted}.{stem}"


def compare_candidate(root, anchor):
    """Pure candidate-versus-anchor comparison: no environment or import assumptions.

    Returns the verified relative-path to SHA-256 map. Raises Rejected on any divergence,
    so the trust decisions are testable without a dedicated interpreter.
    """
    validate_anchor_files(anchor["files"])
    package = canonical(root / PACKAGE)
    verified = {}
    for relative, digest in anchor["files"].items():
        source = root / relative
        require(source.is_file(), "MISSING_MODULE")
        resolved = source.resolve(strict=True)
        require(resolved.is_relative_to(package), "ORIGIN_MISMATCH")
        require(hashlib.sha256(canonical_bytes(resolved)).hexdigest() == digest, "HASH_MISMATCH")
        verified[relative] = digest
    # A module the anchor does not know is a divergence too: the candidate must be exactly
    # the anchored tree, not a superset of it.
    present = {p.relative_to(root).as_posix() for p in package.rglob("*.py")}
    require(present == set(anchor["files"]), "CANDIDATE_EXTRA_MODULE")
    return verified


def verify(args):
    # Trust checks come first: a self-declared or unauthenticated anchor is the most
    # important violation, and it must be reported even when the interpreter is not the
    # dedicated one. Both orders fail closed; this order surfaces the trust reason.
    root = canonical(args.candidate_root)
    require(DIGEST.fullmatch(args.anchor_sha256) is not None, "CLI_INVALID")
    anchor = load_anchor(args.anchor, args.anchor_sha256, root)
    verified = compare_candidate(root, anchor)
    package = canonical(root / PACKAGE)

    require(sys.flags.isolated == 1 and sys.flags.ignore_environment == 1
            and sys.flags.no_site == 0, "FLAGS_INVALID")
    # Do not resolve executable symlinks: the dedicated venv path is the identity.
    require(Path(sys.executable).absolute() == Path(args.expected_executable).absolute(),
            "EXECUTABLE_MISMATCH")
    require(sys.prefix != sys.base_prefix, "VENV_REQUIRED")
    settings = dict(line.lower().strip().split("=", 1)
                    for line in (Path(sys.prefix) / "pyvenv.cfg").read_text().splitlines()
                    if "=" in line)
    require(any(key.strip() == "include-system-site-packages" and value.strip() == "false"
                for key, value in settings.items()), "SYSTEM_SITE_FORBIDDEN")
    require(Path(sys.executable).absolute().is_relative_to(Path(sys.prefix).absolute()),
            "EXECUTABLE_MISMATCH")

    check_spec("yasb_limitora", canonical(package / "__init__.py"))
    imported = importlib.import_module("yasb_limitora")
    require(hasattr(imported, "__path__") and len(imported.__path__) == 1
            and canonical(imported.__path__[0]) == package, "ORIGIN_MISMATCH")
    for relative in anchor["files"]:
        check_spec(module_name(relative), canonical(root / relative))

    candidates = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        require(isinstance(name, str) and bool(name), "METADATA_UNKNOWN")
        is_candidate = re.sub(r"[-_.]+", "-", name).lower() == "yasb-limitora"
        direct = distribution.read_text("direct_url.json")
        data = json.loads(direct) if direct is not None else None
        if data is not None:
            require(isinstance(data, dict), "METADATA_UNKNOWN")
            info = data.get("dir_info", {})
            require(isinstance(info, dict), "METADATA_UNKNOWN")
            if info.get("editable") is True:
                require(is_candidate, "UNEXPECTED_EDITABLE")
        if is_candidate:
            require(distribution.version == anchor["version"], "VERSION_MISMATCH")
            require(data is not None and data.get("dir_info", {}).get("editable") is True,
                    "METADATA_UNKNOWN")
            require(editable_root(data) == root, "EDITABLE_MISMATCH")
            candidates.append(distribution)
    require(len(candidates) == 1, "DISTRIBUTION_MISMATCH")

    return {
        "anchor_sha256": args.anchor_sha256,
        "approved_revision": anchor["approved_revision"],
        "approved_tree": anchor["approved_tree"],
        "version": candidates[0].version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": {
            "role": "dedicated_venv",
            "relative_path": Path(sys.executable).absolute().relative_to(
                Path(sys.prefix).absolute()).as_posix(),
        },
        "flags": {"isolated": sys.flags.isolated,
                  "ignore_environment": sys.flags.ignore_environment,
                  "no_site": sys.flags.no_site},
        "modules": {
            module_name(relative):
            {"origin": relative,
             "sha256": verified[relative],
             "matches_expected": True}
            for relative in sorted(verified)
        },
    }


def main():
    parser = Parser(description="Verify a candidate checkout against an out-of-band approved anchor.")
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--anchor", required=True, help="Anchor frozen outside this candidate")
    parser.add_argument("--anchor-sha256", required=True, help="Pinned digest of that anchor")
    parser.add_argument("--expected-executable", required=True)
    try:
        args = parser.parse_args()
        details = verify(args)
    except Rejected as exc:
        result = {"status": "FAIL", "reason": str(exc)}
    except Exception:
        # No paths, environment values, provider data, or exception text escape.
        result = {"status": "FAIL", "reason": "IDENTITY_UNKNOWN"}
    else:
        result = {"status": "PASS", "reason": "IDENTITY_VERIFIED", "details": details}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
