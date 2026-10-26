import unittest
from pathlib import Path

from mathessible.help_links import HELP_PAGES, page_url, version

ROOT = Path(__file__).resolve().parent.parent


class HelpLinksTests(unittest.TestCase):
    def test_every_help_page_is_in_the_repository(self) -> None:
        for _label, path in HELP_PAGES:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
                self.assertEqual(page_url(path), f"https://github.com/GruiaChiscop/Mathessible/blob/main/{path}")

    def test_the_version_is_the_packages(self) -> None:
        self.assertRegex(version(), r"^\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
