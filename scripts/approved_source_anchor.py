"""Freeze an approved source anchor from a pinned Git revision.

Usage:
    python -B -I -E approved_source_anchor.py --repo REPO --revision REV \
        --version 0.2.0 --output ANCHOR.json

Exit 0: sanitized PASS plus the anchor digest to publish out of band.
Exit 1: sanitized FAIL.

The anchor is only a carrier. It becomes authority only when its digest is
published out of band and later supplied to the preflight by the operator.
A candidate that carries its own anchor proves nothing.
"""
import argparse
import hashlib
import json
import subprocess


SCHEMA = 1
PACKAGE = "src/yasb_limitora"
REQUIRED = ("__init__", "_native_proof_observability")


class Rejected(Exception):
    """Carries only a fixed public reason code."""


def require(condition, reason):
    if not condition:
        raise Rejected(reason)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Rejected("CLI_INVALID")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, check=True, timeout=30).stdout


def canonical_anchor_bytes(anchor):
    return (json.dumps(anchor, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def anchor_digest(anchor):
    return hashlib.sha256(canonical_anchor_bytes(anchor)).hexdigest()


def collect(repo, revision, version):
    listing = git(repo, "ls-tree", "-r", revision, "--", PACKAGE).decode("utf-8")
    files = {}
    for line in listing.splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        _, kind, blob = meta.split()
        require(kind == "blob", "ANCHOR_UNKNOWN")
        # Only Python modules are anchored; non-source siblings are not identity.
        if not path.endswith(".py"):
            continue
        content = git(repo, "cat-file", "blob", blob)
        files[path] = hashlib.sha256(content).hexdigest()
    require(bool(files), "ANCHOR_UNKNOWN")
    for name in REQUIRED:
        require(f"{PACKAGE}/{name}.py" in files, "ANCHOR_UNKNOWN")
    tree = git(repo, "rev-parse", f"{revision}:{PACKAGE}").decode("utf-8").strip()
    head = git(repo, "rev-parse", revision).decode("utf-8").strip()
    require(len(tree) == 40 and len(head) == 40, "ANCHOR_UNKNOWN")
    return {
        "schema": SCHEMA,
        "approved_revision": head,
        "approved_tree": tree,
        "version": version,
        "files": dict(sorted(files.items())),
    }


def main():
    parser = Parser(description="Freeze an approved source anchor from a pinned Git revision.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    try:
        args = parser.parse_args()
        anchor = collect(args.repo, args.revision, args.version)
    except Rejected as exc:
        result = {"status": "FAIL", "reason": str(exc)}
    except Exception:
        # No paths, repository values or exception text escape.
        result = {"status": "FAIL", "reason": "ANCHOR_UNKNOWN"}
    else:
        with open(args.output, "wb") as stream:
            stream.write(canonical_anchor_bytes(anchor))
        result = {
            "status": "PASS",
            "reason": "ANCHOR_FROZEN",
            "approved_revision": anchor["approved_revision"],
            "approved_tree": anchor["approved_tree"],
            "version": anchor["version"],
            "file_count": len(anchor["files"]),
            # Publish this out of band; the anchor cannot certify itself.
            "anchor_sha256": anchor_digest(anchor),
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
