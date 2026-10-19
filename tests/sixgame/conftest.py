"""Make the sixgame package importable in tests (offline, no network).

Adds both the scripts directory and the package directory itself to the
path, so tests can import modules either way the code lays them out.
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
for _path in (str(_SCRIPTS), str(_SCRIPTS / "sixgame")):
    if _path not in sys.path:
        sys.path.insert(0, _path)
