#!/usr/bin/env python3
"""release-brief — instance 1 of the authored-brief class (see _brief.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _brief

_brief.main(["x", "4201", "4.2", "release brief", "api,auth,billing,search,docs", "24"])
