"""Shortcut to run `python -m rp ...` from the project root as well.

The package lives in app/rp. Inside app/ Python finds the package directly and this file is not used; at the root,
it puts app/ first on the import path and runs the real package (python -m rp interface, verificar, etc.).
It changes nothing in the program's behavior: config, database and snapshots are still resolved from app/.
"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
sys.modules.pop("rp", None)
runpy.run_module("rp", run_name="__main__", alter_sys=True)
