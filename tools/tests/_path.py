import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = TOOLS_DIR.parent


def ensure_path() -> None:
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
