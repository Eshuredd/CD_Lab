"""Pytest configuration: puts src/ on sys.path so tests can import
compiler modules the same way main.py does (relative to src/)."""

import sys
from pathlib import Path

# Ensure src/ is the first entry so all compiler-internal imports resolve correctly.
SRC = str(Path(__file__).parent.parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
