"""
Host test configuration.

Puts src/ on sys.path so the FIA core imports the same flat way it does on
device (`import fia_peak`, not `from src import fia_peak`).

Appended, not prepended, on purpose: src/code.py would otherwise shadow the
stdlib `code` module that pytest's pdb integration imports, which fails the
whole run before collection. Nothing in the FIA core collides with a stdlib
name, so appending resolves everything it needs.

Nothing here stubs board or ulab, and no test may import constants,
colorimeter, calibrations, configuration or light_sensor -- all five reach
`import board` transitively. test_fia_purity.py enforces that boundary.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, 'src')
TESTS_DIR = os.path.join(REPO_ROOT, 'tests')

for path in (SRC_DIR, TESTS_DIR):
    if path not in sys.path:
        sys.path.append(path)
