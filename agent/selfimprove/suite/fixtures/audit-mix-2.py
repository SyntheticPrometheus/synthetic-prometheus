#!/usr/bin/env python3
"""audit-mix-2 — instance 2 of the spec-adherence-under-bulk class (see _audit_mix.py)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _audit_mix

json.dump(_audit_mix.build(2081), sys.stdout)
