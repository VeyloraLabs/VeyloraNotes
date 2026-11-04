import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = os.environ.get("VN_SITE_PACKAGES")
if VENV:
    sys.path.insert(0, VENV)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
