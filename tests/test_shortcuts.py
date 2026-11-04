import conftest_env
import os, tempfile
home = tempfile.mkdtemp()
os.environ.update(XDG_CONFIG_HOME=home+"/c", XDG_DATA_HOME=home+"/d", XDG_CACHE_HOME=home+"/k", HOME=home)
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
QCoreApplication.setOrganizationName("VeyloraLabs"); QCoreApplication.setApplicationName("VeyloraNotes")
from app import theme
from app.settings import Settings
from app.gui.main_window import MainWindow
app = QApplication([]); theme.apply(app)
s = Settings(); s.set("welcome_shown", True); s.set("restore_session", False)
w = MainWindow(s); w.show(); w.activateWindow()
for _ in range(10): app.processEvents()
assert w.isActiveWindow()
ed = w.current_editor(); ed.setFocus(); ed.setPlainText("linea uno\nlinea dos"); ed.moveCursor(ed.textCursor().MoveOperation.Start)
C = Qt.KeyboardModifier.ControlModifier; A = Qt.KeyboardModifier.AltModifier; S = Qt.KeyboardModifier.ShiftModifier
QTest.keyClick(ed, Qt.Key.Key_D, C); assert ed.toPlainText() == "linea uno\nlinea uno\nlinea dos", "ctrl+d"
QTest.keyClick(ed, Qt.Key.Key_K, C); assert "](https://" in ed.toPlainText() or "](" in ed.toPlainText(), "ctrl+k must insert a link, not delete to end of line"
QTest.keyClick(ed, Qt.Key.Key_F, C); assert w.find_bar.isVisible(), "ctrl+f"
w.find_bar.close_bar()
before = ed.toPlainText(); QTest.keyClick(ed, Qt.Key.Key_Down, A); assert ed.toPlainText() != before, "alt+down"
QTest.keyClick(ed, Qt.Key.Key_P, C | S); assert w.palette.isVisible(), "ctrl+shift+p"; w.palette.close()
before = ed.toPlainText(); QTest.keyClick(ed, Qt.Key.Key_B, C); assert "**" in ed.toPlainText(), "ctrl+b"
QTest.keyClick(ed, Qt.Key.Key_Z, C); assert "**" not in ed.toPlainText(), "ctrl+z"
print("all shortcut tests passed")
