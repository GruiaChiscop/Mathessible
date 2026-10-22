import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from matex.patch_check import missing_patches


def _git(directory: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(directory), *arguments], check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git is needed to check patches")
class PatchCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        submodule = self.root / "MathCAT"
        submodule.mkdir()
        _git(submodule, "init", "-q")
        (submodule / "rules.txt").write_text("limit-inf\n", encoding="utf-8")
        _git(submodule, "add", "rules.txt")
        _git(submodule, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "upstream")
        (submodule / "rules.txt").write_text("lim-inf\n", encoding="utf-8")
        patches = self.root / "patches" / "mathcat"
        patches.mkdir(parents=True)
        diff = subprocess.run(["git", "-C", str(submodule), "diff"], check=True, capture_output=True, text=True)
        (patches / "0001-names.patch").write_text(diff.stdout, encoding="utf-8")
        self.submodule = submodule

    def test_an_applied_patch_is_not_missing(self) -> None:
        self.assertEqual(missing_patches(self.root), [])

    def test_an_unapplied_patch_is_reported(self) -> None:
        _git(self.submodule, "checkout", "-q", "rules.txt")  # Upstream again, as after `uv sync` alone.
        self.assertEqual(missing_patches(self.root), ["MathCAT/0001-names.patch"])

    def test_without_submodules_nothing_can_be_told(self) -> None:
        self.assertIsNone(missing_patches(Path(tempfile.mkdtemp())))

    def test_this_checkout_has_every_patch(self) -> None:
        # Fails after a fresh clone until scripts/bootstrap.sh has run.
        self.assertEqual(missing_patches(), [])
