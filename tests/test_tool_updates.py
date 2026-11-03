from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mathessible.documents.optional_tools import ToolError, publish, update_tinytex
from mathessible.documents.tex_compile import TexInstallation
from mathessible.documents.tool_updates import check, newer


class UpdateTests(unittest.TestCase):
    def test_numeric_versions(self) -> None:
        self.assertTrue(newer("3.13", "pandoc 3.9"))
        self.assertFalse(newer("3.13", "pandoc 3.13.0"))
        self.assertFalse(newer("3.13", "pandoc 4.0"))
        with self.assertRaises(ToolError):
            newer("3.13", "unknown")

    def test_pandoc_update_is_compared_to_detected_binary(self) -> None:
        with (
            patch("mathessible.documents.tool_updates.locate", return_value="/system/pandoc"),
            patch("mathessible.documents.tool_updates.is_managed", return_value=False),
            patch("mathessible.documents.tool_updates.version", return_value="pandoc 3.9"),
            patch("mathessible.documents.tool_updates.release", return_value={"tag_name": "3.13"}),
        ):
            result = check("pandoc")
            self.assertTrue(result.available)
            self.assertFalse(result.managed)
            self.assertEqual(result.path, "/system/pandoc")

    def test_latex_package_check_does_not_update_packages(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder)
            installation = TexInstallation("TinyTeX", binary, ("pdflatex",))
            installation.program("tlmgr").touch()
            for body, expected in (("pkg u 1 2 100\n", True), ("", False)):
                with (
                    patch("mathessible.documents.tool_updates.locate", return_value=folder),
                    patch("mathessible.documents.tool_updates.find_installation", return_value=installation),
                    patch("mathessible.documents.tool_updates.version", return_value="pdfTeX"),
                    patch("mathessible.documents.tool_updates.subprocess.run") as run,
                ):
                    run.return_value.stdout = "end-of-header\n" + body + "end-of-updates\n"
                    self.assertEqual(check("TinyTeX").available, expected)
                    self.assertEqual(run.call_args.args[0][-3:], ["--machine-readable", "update", "--list"])

    def test_publish_keeps_previous_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target, staged = Path(folder) / "current", Path(folder) / "new"
            target.mkdir()
            staged.mkdir()
            (target / "data").write_text("old")
            (staged / "data").write_text("new")
            publish(staged, target)
            self.assertEqual((target / "data").read_text(), "new")
            backup = next(Path(folder).glob("current.previous-*"))
            self.assertEqual((backup / "data").read_text(), "old")

    def test_publish_keeps_only_the_latest_previous_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "current"
            target.mkdir()
            for version in ("1", "2", "3"):
                staged = Path(folder) / "new"
                staged.mkdir()
                (staged / "data").write_text(version)
                publish(staged, target)
            backups = list(Path(folder).glob("current.previous-*"))
            self.assertEqual([(backup / "data").read_text() for backup in backups], ["2"])
            staged.mkdir()
            (staged / "data").write_text("4")
            publish(staged, target, keep_previous=False)
            self.assertEqual(list(Path(folder).glob("current.previous-*")), backups)
            self.assertEqual((target / "data").read_text(), "4")

    def test_failed_publish_restores_previous_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target, staged = Path(folder) / "current", Path(folder) / "missing"
            target.mkdir()
            (target / "data").write_text("old")
            with self.assertRaises(OSError):
                publish(staged, target)
            self.assertEqual((target / "data").read_text(), "old")

    def test_tinytex_failure_and_cancellation_keep_original(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "TinyTeX"
            binary = root / "bin" / "platform"
            binary.mkdir(parents=True)
            (root / "mathessible-install.json").write_text("{}")
            (binary / "tlmgr").write_text("fake")
            with patch("mathessible.documents.optional_tools.managed_directory", return_value=root):
                with (
                    patch(
                        "mathessible.documents.optional_tools.subprocess.run",
                        side_effect=subprocess.CalledProcessError(1, "tlmgr"),
                    ),
                    self.assertRaises(ToolError),
                ):
                    update_tinytex()
                with self.assertRaises(ToolError):
                    update_tinytex(lambda: True)
            self.assertTrue((binary / "tlmgr").exists())
            self.assertEqual(list(Path(folder).iterdir()), [root])
