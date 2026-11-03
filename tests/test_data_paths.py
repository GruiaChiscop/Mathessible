from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mathessible.data_paths import data_directory


class DataPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.legacy = self.home / ".mathessible"

    def test_platform_paths(self) -> None:
        self.assertEqual(data_directory(self.home, "darwin", {}), self.home / "Library/Application Support/Mathessible")
        self.assertEqual(
            data_directory(self.home, "win32", {"APPDATA": str(self.home / "roaming")}),
            self.home / "roaming/mathessible",
        )
        self.assertEqual(data_directory(self.home, "win32", {}), self.home / "AppData/Roaming/mathessible")
        self.assertEqual(data_directory(self.home, "linux", {}), self.legacy)
