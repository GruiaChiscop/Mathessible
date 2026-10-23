"""MateX's tests. Run them with `uv run python -m unittest discover -s tests -v`.

The test modules import their shared helpers (`converter_harness`) as
top-level modules, as `discover -s tests` does; this makes that work too
when one module is run as `python -m unittest tests.test_unicodemath`.
"""

import sys
from pathlib import Path

_TESTS = str(Path(__file__).resolve().parent)
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)
