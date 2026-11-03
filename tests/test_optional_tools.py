from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from mathessible.documents import optional_tools
from mathessible.documents.optional_tools import (
    ToolError,
    asset_name,
    find_pandoc,
    install,
    installed_program,
    tlmgr_program,
    unpack,
)
from mathessible.documents.tex_compile import find_installation, tinytex_directory
from mathessible.settings import AppSettings, load_settings, save_settings


class OptionalToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_settings_round_trip(self) -> None:
        path = self.root / "settings.json"
        settings = AppSettings(pandoc_path="/custom/pandoc", latex_bin_directory="/custom/tex/bin")
        save_settings(settings, path)
        loaded = load_settings(path)
        self.assertEqual(
            (loaded.pandoc_path, loaded.latex_bin_directory), (settings.pandoc_path, settings.latex_bin_directory)
        )

    def test_custom_path_never_falls_back(self) -> None:
        with patch("mathessible.documents.optional_tools.shutil.which", return_value=None) as which:
            self.assertIsNone(find_pandoc("/missing/pandoc"))
            which.assert_called_once_with(str(Path("/missing/pandoc")))
        self.assertIsNone(find_installation(configured=str(self.root / "missing")))

    def test_system_pandoc_wins_over_private_copy(self) -> None:
        with patch("mathessible.documents.optional_tools.shutil.which", return_value="/system/pandoc"):
            self.assertEqual(find_pandoc(), "/system/pandoc")

    def test_private_pandoc_fallback(self) -> None:
        binary = self.root / "bin" / "pandoc"
        binary.parent.mkdir()
        binary.write_text("binary")
        binary.chmod(0o755)
        with (
            patch("mathessible.documents.optional_tools.shutil.which", return_value=None),
            patch("mathessible.documents.optional_tools.managed_directory", return_value=self.root),
        ):
            self.assertEqual(find_pandoc(), str(binary))

    def test_private_tex_path_is_in_the_data_directory(self) -> None:
        self.assertEqual(
            tinytex_directory(home=self.root, platform="darwin"),
            self.root / "Library/Application Support/Mathessible/tools/TinyTeX",
        )
        self.assertEqual(tinytex_directory(home=self.root, platform="linux"), self.root / ".mathessible/tools/TinyTeX")

    def test_lock_left_by_a_stopped_process_is_taken_over(self) -> None:
        target = self.root / "tools" / "pandoc"
        target.parent.mkdir()
        lock = target.parent / ".pandoc.installing"
        with patch("mathessible.documents.optional_tools.managed_directory", return_value=target):
            for owner, running in (("4242", True), (str(os.getpid()), False)):
                lock.write_text(owner)
                with (
                    patch("mathessible.documents.optional_tools.running", return_value=running),
                    self.assertRaisesRegex(ToolError, "Another installation"),
                ):
                    install("pandoc", lambda percent: None)
            lock.write_text("4242")
            with (
                patch("mathessible.documents.optional_tools.running", return_value=False),
                patch("mathessible.documents.optional_tools.release", side_effect=ToolError("offline")),
                self.assertRaisesRegex(ToolError, "offline"),
            ):
                install("pandoc", lambda percent: None)
            self.assertFalse(lock.exists())

    def test_tlmgr_and_installed_programs(self) -> None:
        folder = self.root / "TinyTeX" / "bin" / "windows"
        folder.mkdir(parents=True)
        for name in ("tlmgr", "tlmgr.bat", "pdflatex.exe"):
            (folder / name).write_text("")
        self.assertEqual(tlmgr_program(folder, "win32"), folder / "tlmgr.bat")
        self.assertEqual(tlmgr_program(folder, "darwin"), folder / "tlmgr")
        self.assertIsNone(tlmgr_program(self.root, "linux"))
        self.assertEqual(installed_program("TinyTeX", self.root / "TinyTeX"), folder)
        pandoc = self.root / "pandoc" / "pandoc-3.5" / "bin" / "pandoc"
        pandoc.parent.mkdir(parents=True)
        pandoc.write_text("")
        self.assertEqual(installed_program("pandoc", self.root / "pandoc"), pandoc)
        with self.assertRaises(ToolError):
            installed_program("pandoc", self.root / "TinyTeX")

    def test_system_tex_precedes_private_copy_and_custom_path_wins(self) -> None:
        system = self.root / "system"
        private = tinytex_directory(home=self.root) / "bin" / "platform"
        for folder in (system, private):
            folder.mkdir(parents=True)
            binary = folder / "pdflatex"
            binary.write_text("binary")
            binary.chmod(0o755)
        with patch("mathessible.documents.tex_compile._candidates", return_value=[system]):
            self.assertEqual(find_installation(home=self.root).bin_directory, system)
            self.assertEqual(find_installation(home=self.root, configured=str(private)).bin_directory, private)
        with patch("mathessible.documents.tex_compile._candidates", return_value=[]):
            self.assertEqual(find_installation(home=self.root).bin_directory, private)

    def test_a_rename_windows_refuses_a_moment_is_tried_again(self) -> None:
        # Just after `pandoc --version`, Windows still locks pandoc.exe and refuses to rename its folder.
        refusals = [PermissionError(5, "Access is denied"), PermissionError(5, "Access is denied"), None]
        with (
            patch("mathessible.documents.optional_tools.os.rename", side_effect=refusals) as rename,
            patch("mathessible.documents.optional_tools.sys.platform", "win32"),
            patch("mathessible.documents.optional_tools.time.sleep"),
        ):
            optional_tools._rename(self.root / "staged", self.root / "pandoc")
        self.assertEqual(rename.call_count, 3)
        with (
            patch("mathessible.documents.optional_tools.os.rename", side_effect=PermissionError(13, "denied")),
            patch("mathessible.documents.optional_tools.sys.platform", "darwin"),
            self.assertRaises(PermissionError),
        ):
            optional_tools._rename(self.root / "staged", self.root / "pandoc")  # Elsewhere a refusal is final.

    def test_platform_assets(self) -> None:
        self.assertEqual(asset_name("pandoc", "3.13", "darwin", "arm64"), "pandoc-3.13-arm64-macOS.zip")
        self.assertEqual(asset_name("TinyTeX", "v2026.11", "darwin", "arm64"), "TinyTeX-1-darwin-v2026.11.tar.xz")
        # Windows 11 on ARM runs the x64 builds; there are no others.
        self.assertEqual(asset_name("pandoc", "3.13", "win32", "arm64"), "pandoc-3.13-windows-x86_64.zip")
        self.assertEqual(asset_name("TinyTeX", "v2026.11", "win32", "ARM64"), "TinyTeX-v2026.11.zip")
        with self.assertRaises(ToolError):
            asset_name("pandoc", "3.13", "win32", "ppc64")

    def test_zip_traversal_is_rejected(self) -> None:
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../outside", "bad")
        with self.assertRaises(ToolError):
            unpack(archive, self.root / "staging", lambda: False)
        self.assertFalse((self.root / "outside").exists())

    def test_tar_external_symlink_is_rejected(self) -> None:
        archive = self.root / "bad.tar"
        with tarfile.open(archive, "w") as bundle:
            entry = tarfile.TarInfo("link")
            entry.type, entry.linkname = tarfile.SYMTYPE, "/etc/passwd"
            bundle.addfile(entry)
        with self.assertRaises(tarfile.FilterError):
            unpack(archive, self.root / "staging", lambda: False)

    def _download(self, corrupt: bool = False, cancel: bool = False):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as bundle:
            bundle.writestr("pandoc-3.13/bin/pandoc", "binary")
        archive = data.getvalue()
        release = {
            "tag_name": "3.13",
            "assets": [
                {
                    "name": "pandoc-3.13-arm64-macOS.zip",
                    "size": len(archive),
                    "digest": "sha256:" + ("0" * 64 if corrupt else hashlib.sha256(archive).hexdigest()),
                    "browser_download_url": "https://github.com/jgm/pandoc/releases/download/3.13/archive.zip",
                }
            ],
        }
        target = self.root / "tools/pandoc"
        with (
            patch("mathessible.documents.optional_tools.managed_directory", return_value=target),
            patch("mathessible.documents.optional_tools.sys.platform", "darwin"),
            patch("mathessible.documents.optional_tools.platform.machine", return_value="arm64"),
            patch(
                "mathessible.documents.optional_tools.urlopen",
                side_effect=[io.BytesIO(json.dumps(release).encode()), io.BytesIO(archive)],
            ),
            patch("mathessible.documents.optional_tools.version", return_value="pandoc 3.13"),
        ):
            return install("pandoc", lambda percent: None, lambda: cancel)

    def test_verified_install_is_published(self) -> None:
        path = self._download()
        self.assertTrue((path / "pandoc-3.13/bin/pandoc").exists())
        self.assertTrue((path / "mathessible-install.json").exists())
        self.assertEqual(os.listdir(path.parent), ["pandoc"])

    def test_cancel_and_checksum_failure_leave_no_installation(self) -> None:
        for corrupt, cancel in ((True, False), (False, True)):
            with self.assertRaises(ToolError):
                self._download(corrupt, cancel)
            self.assertEqual(list((self.root / "tools").iterdir()), [])

    def test_existing_installation_is_never_replaced(self) -> None:
        target = self.root / "tools/pandoc"
        target.mkdir(parents=True)
        marker = target / "keep"
        marker.write_text("existing")
        with (
            patch("mathessible.documents.optional_tools.managed_directory", return_value=target),
            self.assertRaises(ToolError),
        ):
            install("pandoc", lambda percent: None)
        self.assertEqual(marker.read_text(), "existing")
