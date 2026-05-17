"""Re-export shim for backwards compatibility.

The canonical LLMConfig lives at fos.core.llm_config.
Import from there directly.
"""

from fos.core.llm_config import *  # noqa: F401, F403
from fos.core.llm_config import LLMConfig  # explicit for type checkers
