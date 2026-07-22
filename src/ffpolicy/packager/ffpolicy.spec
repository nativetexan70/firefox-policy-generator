# PyInstaller spec for ffpolicy. Build with:
#   pyinstaller src/ffpolicy/packager/ffpolicy.spec
import os

from PyInstaller.utils.hooks import collect_data_files

SRC_DIR = os.path.join(SPECPATH, "..", "..")  # repo's src/ directory

datas = collect_data_files("ffpolicy.resources")

a = Analysis(
    [os.path.join(SRC_DIR, "ffpolicy", "__main__.py")],
    pathex=[SRC_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ffpolicy",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ffpolicy",
)
