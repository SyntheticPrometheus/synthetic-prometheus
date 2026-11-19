#!/usr/bin/env python3
"""upgrade-brief — instance 2 of the authored-brief class (see _brief.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _brief

_brief.main(["x", "5107", "5.1", "upgrade brief", "api,auth,console,search,docs", "30"])
