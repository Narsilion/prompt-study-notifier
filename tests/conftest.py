from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_LIB = PROJECT_ROOT / "build" / "lib"


def _normalize(path: str) -> str:
    return str(Path(path).resolve())


project_root_str = str(PROJECT_ROOT)
sys.path[:] = [path for path in sys.path if _normalize(path) != str(BUILD_LIB.resolve())]
if not sys.path or _normalize(sys.path[0]) != str(PROJECT_ROOT.resolve()):
    sys.path.insert(0, project_root_str)
