# Native artifact inventory without directory reads

The private final proof scanner now returns an in-memory inventory while keeping its existing sentinel assertion and callers unchanged. It reads regular files only and recursively inspects owned artifact directories, including empty directories. It does not write inventory files or change cleanup.

## Inventory contract

| Entry | Fields |
|-------|--------|
| Regular file | `name`, `type: file`, byte `size`, `sha256` |
| Directory | `name`, `type: directory` |

Names start with the supplied artifact's basename; descendants use relative forward-slash names. Absolute roots and file contents are not included. Every regular file, including nested files, is checked for the ASCII sentinel before its inventory entry is returned. A violation retains the exact message `native proof artifact scan failed`, without including the sentinel or path.

## Fail-closed boundaries

The scanner uses `lstat` and rejects symlinks, Windows reparse points (including directory junctions), and unsupported file types before reading or traversing them. This follows the repository's metadata checks in `src/yasb_limitora/cache.py`. Actual metadata, directory-listing, and file-read exceptions propagate unchanged; an inaccessible artifact is not success. No partial inventory is returned on failure.

This is a post-execution scan of owned artifact trees, not a concurrency-safe filesystem sandbox. Metadata checks do not pin entries against a concurrent replacement between checking and opening. Keep artifact trees controlled and quiescent; no native race-resistance or native proof PASS is claimed.

## Hermetic evidence

`tests/test_native_artifact_scanner.py` compiles only the existing scanner definition from its source AST, without importing or executing the native proof module or helper. Tests cover the prior single-file behavior, mixed nested trees, empty directories, poisoned directory reads, regular and nested sentinel rejection, unchanged exception identity, and simulated symlink, Windows reparse, and unsupported metadata. Simulations require no symlink privileges and do not establish native Windows proof.

This unit extracts only the artifact-scanner behavior from the retained IPC infrastructure investigation. Its historical task record and RED/GREEN logs remain provenance, not inputs required by a clean checkout. Historical IPC cause, observer hooks and helper import diagnosis are outside this scanner unit.
