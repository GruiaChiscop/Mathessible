# PyInstaller's recipe for the packaged application: `uv run --group packaging pyinstaller packaging/mathessible.spec`.
# dist/Mathessible.app on macOS, the folder dist/Mathessible elsewhere.
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

root = Path(SPECPATH).parent
version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

datas = collect_data_files("mathessible", includes=["locale/**/*", "symbols/*.dic"])
datas += [
    (str(root / "UnicodeMathML" / "dist"), "UnicodeMathML/dist"),
    (str(root / "UnicodeMathML" / "playground" / "assets" / "TeX.js"), "UnicodeMathML/playground/assets"),
    (str(root / "liblouis" / "tables"), "liblouis/tables"),
]
binaries, hiddenimports = [], []
# wx loads WebView2's loader by name at run time, so PyInstaller does not see it; without it wx falls
# back to Internet Explorer, which cannot run the converter. "." is on the bundle's DLL search path.
if sys.platform == "win32":
    import wx

    binaries += [(str(Path(wx.__file__).parent / "WebView2Loader.dll"), ".")]
for package in ("prism", "typst", "mathessible_mathcat"):
    found = collect_all(package)
    datas += found[0]
    binaries += found[1]
    hiddenimports += found[2]
# Prism imports its cffi module (`_prism_cffi.pyd`/`.abi3.so`) from prism/_native, a folder it adds to its
# own __path__, so PyInstaller does not find it: without it speech falls back to the console, silently.
import prism

native = Path(prism.__file__).parent / "_native"
binaries += [(str(path), "prism/_native") for path in native.iterdir() if path.name.startswith("_prism_cffi")]
hiddenimports += ["_cffi_backend"]

analysis = Analysis(
    [str(root / "packaging" / "launch.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(analysis.pure)
icon = root / "packaging" / ("Mathessible.icns" if sys.platform == "darwin" else "Mathessible.ico")
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Mathessible",
    console=False,
    icon=str(icon),
)
folder = COLLECT(executable, analysis.binaries, analysis.datas, name="Mathessible")

if sys.platform == "darwin":
    document = {"CFBundleTypeRole": "Editor", "LSHandlerRank": "Alternate"}
    app = BUNDLE(
        folder,
        name="Mathessible.app",
        icon=str(icon),
        bundle_identifier="org.mathessible.Mathessible",
        version=version,
        info_plist={
            "CFBundleShortVersionString": version,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": [
                {**document, "CFBundleTypeName": "Markdown document", "CFBundleTypeExtensions": ["md", "markdown"]},
                {**document, "CFBundleTypeName": "LaTeX document", "CFBundleTypeExtensions": ["tex"]},
                {**document, "CFBundleTypeName": "Mathessible notebook", "CFBundleTypeExtensions": ["msnb"]},
            ],
        },
    )
