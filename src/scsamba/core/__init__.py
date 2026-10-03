"""Core (GUI-independent) smb.conf model, migrated to Python 3.

Public entry points:
    - SambaParser / SambaSection / SambaToken (parser, token)
    - SambaConfig (model) binding a backend
    - SambaBackend (backend) owning files and privileged commands
"""

from __future__ import annotations

from .sambaBackend import SambaBackend
from .sambaConfig import SambaConfig
from .sambaParser import SambaParser, SambaSection
from .sambaToken import (
    SambaToken, UnknownKeyError, sambaTokenCanonicalNameValue,
)

__all__ = [
    "SambaBackend", "SambaConfig", "SambaParser", "SambaSection",
    "SambaToken", "UnknownKeyError", "sambaTokenCanonicalNameValue",
]
