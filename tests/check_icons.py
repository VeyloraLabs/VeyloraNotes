import conftest_env
import re
from pathlib import Path
import qtawesome as qta
from PySide6.QtWidgets import QApplication
app = QApplication([])
names = set()
for path in (conftest_env.ROOT / "app").rglob("*.py"):
    names.update(re.findall(r"""["']((?:fa5s|fa5b|mdi6)\.[\w-]+)["']""", path.read_text()))
bad = []
for name in sorted(names):
    try:
        qta.icon(name)
    except Exception as error:
        bad.append((name, str(error)[:60]))
print(len(names), "icon names; invalid:", bad)
