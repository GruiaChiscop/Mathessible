from __future__ import annotations

import os
import subprocess
import sys
import unittest

from mathessible.processes import running


class ProcessTests(unittest.TestCase):
    def test_running_and_stopped_processes(self) -> None:
        self.assertTrue(running(os.getpid()))
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertFalse(running(child.pid))
        self.assertFalse(running(0))
