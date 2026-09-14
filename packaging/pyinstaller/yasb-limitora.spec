# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for the internal yasb-limitora frozen candidate.

Contract (tests/test_packaging_spec.py): onedir only; console executable;
entry semantics yasb_limitora.cli:main identical to [project.scripts] with no
wrapper reordering; PyInstaller >=6,<7 enforced; UPX disabled; limitora
submodules collected; datas stay empty (no repository documentation, sample
widget, or test data material is ever bundled). Driven by
scripts/build_frozen_bundle.py via YASB_LIMITORA_VERSION_INFO.
"""
import os
from PyInstaller import __version__ as _pyinstaller_version
from PyInstaller.utils.hooks import collect_submodules

if int(_pyinstaller_version.split(".", 1)[0]) != 6:
    raise SystemExit(f"yasb-limitora.spec requires PyInstaller >=6,<7; found {_pyinstaller_version}")

_SRC = os.path.normpath(os.path.join(SPECPATH, "..", "..", "src"))
# Generated entry mirrors the console-script target yasb_limitora.cli:main.
_ENTRY_SOURCE = "import sys\nfrom yasb_limitora.cli import main\nsys.exit(main())\n"
_entry_path = os.path.join(workpath, "entry_yasb_limitora.py")
os.makedirs(workpath, exist_ok=True)
with open(_entry_path, "w", encoding="utf-8") as _entry_file:
    _entry_file.write(_ENTRY_SOURCE)

a = Analysis(
    [_entry_path],
    pathex=[_SRC],
    datas=[],
    hiddenimports=collect_submodules("limitora"),
    excludes=["tkinter", "pytest", "unittest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="yasb-limitora",
    strip=False,
    upx=False,
    console=True,
    version=os.environ.get("YASB_LIMITORA_VERSION_INFO") or None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="yasb-limitora")
