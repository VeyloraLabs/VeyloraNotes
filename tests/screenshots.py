import conftest_env
import os, sys, tempfile, shutil
home = tempfile.mkdtemp()
os.environ.update(XDG_CONFIG_HOME=home+"/config", XDG_DATA_HOME=home+"/data", XDG_CACHE_HOME=home+"/cache", HOME=home)
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPixmap, QTextCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
QCoreApplication.setOrganizationName("VeyloraLabs"); QCoreApplication.setApplicationName("VeyloraNotes")
from app import i18n, theme
from app.paths import asset
from app.settings import Settings
from app.gui.main_window import MainWindow
import app.gui.main_window as mw

language = sys.argv[1] if len(sys.argv) > 1 else "es"
output = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/claude/exp/shots")
output.mkdir(parents=True, exist_ok=True)
app = QApplication([]); theme.apply(app)

def make_banner(path):
    width, height = 1280, 300
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0, QColor("#0a0d0c")); gradient.setColorAt(0.6, QColor("#0e1a15")); gradient.setColorAt(1, QColor("#0f3a2a"))
    painter.fillRect(0, 0, width, height, gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 244, 159, 22)); painter.drawEllipse(QRectF(width - 380, -120, 560, 560))
    painter.setBrush(QColor(0, 244, 159, 14)); painter.drawEllipse(QRectF(width - 240, 90, 380, 380))
    renderer = QSvgRenderer(str(asset("icon.svg")))
    renderer.render(painter, QRectF(110, 78, 144, 144))
    title = QFont("Inter"); title.setPixelSize(86); title.setWeight(QFont.Weight.ExtraBold)
    painter.setFont(title); painter.setPen(QColor("#e9eeeb"))
    painter.drawText(QRectF(290, 62, 900, 110), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Veylora")
    metrics = painter.fontMetrics(); offset = metrics.horizontalAdvance("Veylora")
    painter.setPen(QColor("#00f49f")); painter.drawText(QRectF(290 + offset, 62, 700, 110), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Notes")
    tagline = QFont("Inter"); tagline.setPixelSize(30)
    painter.setFont(tagline); painter.setPen(QColor("#9fb0a8"))
    painter.drawText(QRectF(294, 170, 900, 50), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "A notepad with superpowers")
    painter.end()
    image.save(str(path))

notes = Path(home) / "Notes"; (notes / "Journal").mkdir(parents=True); (notes / "images").mkdir()
make_banner(notes / "images" / "banner.png")
shot = QImage(520, 300, QImage.Format.Format_RGB32); shot.fill(QColor("#10241c")); shot.save(str(notes / "images" / "screen.png"))
(notes / "Journal" / "2026-11-03.md").write_text("# Tuesday, November 3, 2026\n\n- [x] Review the roadmap\n- [ ] Call the plumber\n")
(notes / "shopping.txt").write_text("bread\nmilk\neggs\ncoffee\n")
(notes / "config.json").write_text('{\n  "name": "veylora-notes",\n  "version": "2.0.0",\n  "features": ["tabs", "find", "preview"],\n  "debug": false,\n  "port": 8080\n}\n')
(notes / "backup.py").write_text('import shutil\nfrom pathlib import Path\n\n\ndef backup(source: str, target: str) -> int:\n    """Copy every note and return how many were copied."""\n    count = 0\n    for path in Path(source).glob("*.md"):\n        shutil.copy(path, target)  # keep the original\n        count += 1\n    return count\n\n\nif __name__ == "__main__":\n    print(backup("notes", "/tmp/backup"))\n')
readme = """# Roadmap 2026 🚀

![banner](images/banner.png)

> [!NOTE]
> This note is rendered **like GitHub** while you type, including images, tables and task lists.

## Goals

- [x] Ship the first release
- [x] Write the documentation
- [ ] Add a plugin system
- [ ] Translate everything to *three* languages

## Status

| Area | Owner | Progress |
|:-----|:------|---------:|
| **Editor** | Ana | 100% |
| **Preview** | Luis | 80% |
| `Search` | Marta | 45% |

## Snippet

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"  # friendly
```

> [!WARNING]
> Remember to back up the notes folder.
"""
(notes / "roadmap.md").write_text(readme)

settings = Settings()
settings.set("language", language); settings.set("notes_dir", str(notes)); settings.set("welcome_shown", True)
settings.set("restore_session", False)
w = MainWindow(settings, [notes / "shopping.txt", notes / "backup.py", notes / "config.json", notes / "roadmap.md", notes / "Journal" / "2026-11-03.md"])
w.resize(1320, 840); w.show()
import time
def pump(n=8):
    for _ in range(n):
        app.processEvents(); time.sleep(0.03)
pump()
def compose(extra):
    base = w.grab().toImage()
    painter = QPainter(base)
    for widget, position in extra:
        painter.drawPixmap(position, widget.grab())
    painter.end()
    return base

def go(name):
    view = w.view_for_path(notes / name); w.tab_bar.setCurrentIndex(w.views.index(view)); pump(); return view

view = go("backup.py")
view.editor.go_to_line(9, 5); pump()
w.sidebar.files.tree.expandAll(); pump()
w.grab().save(str(output / "01-editor.png"))

view = go("roadmap.md"); w.set_view_mode("split"); pump(20); view.preview.render_now(); pump(10)
w.grab().save(str(output / "02-preview.png"))

w.set_view_mode("editor"); view.editor.go_to_line(5, 1); pump()
w.open_find(True); w.find_bar.find_input.setText("the"); w.find_bar.replace_input.setText("THE"); pump(20); w.find_bar.refresh(); pump()
w.grab().save(str(output / "03-find.png"))
w.find_bar.close_bar(); pump()

w.open_palette(); w.palette.input.setText("sort" if language == "en" else "ordenar"); pump(10)
pal = w.palette
compose([(pal, pal.pos() - w.mapToGlobal(QPoint(0, 0)))]).save(str(output / "04-palette.png"))
pal.close(); pump()

menu = w.menus["menu.text"]
menu.popup(w.mapToGlobal(QPoint(300, 50))); pump(10)
actions = menu.actions()
menu.setActiveAction(actions[2]); pump(10)
sub = actions[2].menu()
parts = [(menu, menu.pos() - w.mapToGlobal(QPoint(0, 0)))]
if sub is not None and sub.isVisible():
    parts.append((sub, sub.pos() - w.mapToGlobal(QPoint(0, 0))))
compose(parts).save(str(output / "05-tools.png"))
menu.hide(); pump()

from app.gui.settings_dialog import SettingsDialog
dialog = SettingsDialog(settings, w); dialog.show(); pump(10)
dialog.grab().save(str(output / "06-settings.png")); dialog.close()

settings.set("preview_theme", "light"); view = go("roadmap.md"); w.set_view_mode("preview"); pump(20)
w.grab().save(str(output / "07-preview-light.png"))
make_banner(output / "banner.png")
print("done", language)
w.closing = True
