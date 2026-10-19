"""sixgame — the three-game LLM behavioural transfer experiment package.

Submodules: games (game definitions), transport (model calls), runner
(collection with resume), probes (recognition probes), analysis +
benchmarks + stats (regenerating every table from raw JSONL), configs
(frozen sample plans).
"""

# Make the plain module names (games, transport, ...) importable no
# matter how the package is entered (tests, `python -m sixgame.x`), by
# putting both the package directory and its parent on the path.
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _path in (str(_HERE), str(_HERE.parent)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
