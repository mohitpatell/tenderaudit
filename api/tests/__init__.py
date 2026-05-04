"""TenderAudit test suite.

Adds the project root (the parent of ``api``) to ``sys.path`` so tests can use
``from api.x import y`` regardless of where pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # tenderaudit/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
