import conftest_env
import os, sys, tempfile, traceback
home = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = home + "/config"
os.environ["XDG_DATA_HOME"] = home + "/data"
os.environ["XDG_CACHE_HOME"] = home + "/cache"
os.environ["HOME"] = home
from pathlib import Path
from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import QClipboard, QColor, QGuiApplication, QImage, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMenu, QMessageBox
QCoreApplication.setOrganizationName("VeyloraLabs"); QCoreApplication.setApplicationName("VeyloraNotes")

errors = []
sys.excepthook = lambda *args: errors.append("".join(traceback.format_exception(*args)))

from PySide6.QtWidgets import QColorDialog
QColorDialog.getColor = staticmethod(lambda *a, **k: QColor('#123456'))
QDialog.exec = lambda self: 0
QMessageBox.exec = lambda self: 0
QMenu.exec = lambda self, *a, **k: None
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.critical = staticmethod(lambda *a, **k: None)
QInputDialog.getText = staticmethod(lambda *a, **k: ("nuevo", True))
QInputDialog.getInt = staticmethod(lambda *a, **k: (2, True))
notes = Path(home) / "Notas"; notes.mkdir()
out_dir = Path(home) / "out"; out_dir.mkdir()
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out_dir / "guardado.md"), ""))
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(notes))

from app import i18n, theme
from app.settings import Settings
from app.gui.main_window import MainWindow
from app.gui.tool_actions import TRANSFORMS
MainWindow.popup_above = lambda self, menu, button: None

app = QApplication([])
theme.apply(app)
settings = Settings()
settings.set("language", "es")
settings.set("notes_dir", str(notes))
(notes / "a.md").write_text("# Título\n\n- [ ] uno\n\n| a | b |\n|-|-|\n| 1 | 2 |\n", encoding="utf-8")
(notes / "b.txt").write_bytes("canción ñ\r\nsegunda\r\n".encode("cp1252"))

def pump(n=5):
    for _ in range(n):
        app.processEvents()

w = MainWindow(settings)
w.show(); pump()
check = lambda cond, msg: (print("OK  ", msg) if cond else (print("FAIL", msg), errors.append("FAIL " + msg)))

# 1. shortcuts unique
seen = {}
for command in w.registry.commands.values():
    for text in [command.shortcut, *command.alternatives]:
        if text:
            key = QKeySequence(text).toString()
            if key in seen:
                errors.append(f"duplicate shortcut {key}: {seen[key]} / {command.id}")
            seen[key] = command.id
check(True, f"{len(seen)} shortcuts checked for duplicates")

# 2. open files
w.open_path(notes / "a.md"); w.open_path(notes / "b.txt"); pump()
check(len(w.views) == 3, "welcome kept (not empty) + 2 files, views=%d" % len(w.views))
b = w.view_for_path(notes / "b.txt")
check(b.encoding == "cp1252" and b.eol == "\r\n" and "canción" in b.text(), "cp1252 + CRLF detected")
w.tab_bar.setCurrentIndex(w.views.index(b)); pump()
b.editor.insert_text("X"); pump()
check(b.is_modified(), "modified after typing")
w.save_current(); pump()
check((notes / "b.txt").read_bytes() == "Xcanción ñ\r\nsegunda\r\n".encode("cp1252"), "saved preserving cp1252 and CRLF")
check(not b.is_modified(), "not modified after save")

# 3. find / replace
a = w.view_for_path(notes / "a.md"); w.tab_bar.setCurrentIndex(w.views.index(a)); pump()
w.open_find(True); w.find_bar.find_input.setText("uno"); pump(); w.find_bar.refresh()
check(w.find_bar.count_label.text().startswith("–") or "1" in w.find_bar.count_label.text(), "find count: " + w.find_bar.count_label.text())
w.find_bar.replace_input.setText("UNO"); w.find_bar.replace_all(); pump()
check("UNO" in a.text(), "replace all")
w.find_bar.regex_button.setChecked(True); w.find_bar.find_input.setText(r"(\d) \| (\d)"); w.find_bar.replace_input.setText(r"$2-\1"); pump(200); w.find_bar.refresh()
w.find_bar.replace_all(); pump()
check("2-1" in a.text(), "regex replace with groups: " + a.text().splitlines()[-1])
w.find_bar.close_bar(); a.editor.document().setModified(False)

# 4. every command
skip = {"file.quit", "file.close_all", "file.close", "file.close_others", "file.reload"}
for cid, command in w.registry.commands.items():
    if cid in skip:
        continue
    try:
        if command.checkable:
            command.action.trigger()
        else:
            command.action.trigger()
    except Exception:
        errors.append(f"command {cid} raised\n" + traceback.format_exc())
    pump(2)
check(True, f"{len(w.registry.commands)} commands triggered")

# 5. text tools on a doc
w.new_document("hola mundo\nb\na\nb\n"); pump()
for name in TRANSFORMS:
    w.current_editor().selectAll()
    w.run_transform(name)
    pump(1)
check(True, "all transforms ran without crashing")

# 6. language switch retranslates
before = w.registry.action("file.save").text()
i18n.set_language("en"); pump()
after = w.registry.action("file.save").text()
check(before == "Guardar" and after == "Save", f"language switch {before} -> {after}")
check(w.menus["menu.file"].title() == "File", "menu title retranslated")
i18n.set_language("es"); pump()

# 7. hot exit: modify untitled, snapshot, new window
w.new_document("texto sin guardar 💚"); pump()
w.save_session()
w2_settings = Settings()
w2 = MainWindow(w2_settings); w2.show(); pump()
texts = [v.text() for v in w2.views]
check(any("texto sin guardar 💚" in t for t in texts), "unsaved untitled text restored (%d tabs)" % len(w2.views))
restored = [v for v in w2.views if "sin guardar" in v.text()][0]
check(restored.is_modified() and restored.path is None, "restored tab flagged modified, no path")
w2.session.clear(); w2.closing = True; w2.close()

# 8. markdown preview modes + paste image + export
(notes / "c.md").write_text("# Titulo C\n\ntexto uno\n\n## Sub\n", encoding="utf-8")
a = w.open_path(notes / "c.md"); pump()
for mode in ("split", "preview", "editor"):
    w.set_view_mode(mode); pump()
    check(a.view_mode == mode, "view mode " + mode)
img = QImage(40, 30, QImage.Format.Format_RGB32); img.fill(QColor("#00f49f"))
from PySide6.QtGui import QTextCursor
a.editor.moveCursor(QTextCursor.MoveOperation.End)
w.markdown_paste_image(img); pump()
check((notes / "images").is_dir() and len(list((notes / "images").glob("*.png"))) == 1, "pasted image saved to images/")
check("![](images/image-" in a.text(), "markdown link inserted")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out_dir / "x.html"), ""))
w.export_html(); check((out_dir / "x.html").exists() and "<h1" in (out_dir / "x.html").read_text(), "export html")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out_dir / "x.pdf"), ""))
w.export_pdf(); check((out_dir / "x.pdf").exists() and (out_dir / "x.pdf").stat().st_size > 1500, "export pdf %d bytes" % (out_dir / "x.pdf").stat().st_size)

# 9. today note, palette, sidebar search, outline
w.open_today_note(); pump()
check(any(v.path and v.path.parent.name == "Diario" for v in w.views), "today note created")
entries = w.palette_entries(); check(len(entries) > 130, "palette entries: %d" % len(entries))
w.sidebar.search.input.setText("uno"); w.sidebar.search.start(); w.sidebar.search.worker.wait(3000); pump(10)
check(w.sidebar.search.results.topLevelItemCount() >= 1, "folder search found results")
w.tab_bar.setCurrentIndex(w.views.index(a)); pump(); w.refresh_outline()
check(w.sidebar.outline.list.topLevelItemCount() == 2, "outline lists headings")

# 10. external change
(notes / "b.txt").write_bytes(b"changed outside\n"); 
bview = w.view_for_path(notes / "b.txt"); w.check_external_change(bview); pump()
check(bview.text().startswith("changed outside"), "external change reloaded")

# 11. light theme preview & settings dialog build
settings.set("preview_theme", "light"); pump()
from app.gui.settings_dialog import SettingsDialog
d = SettingsDialog(settings, w); d.change_language(1); d.change_language(0); pump()

w.closing = True
print("\nERRORS:", len(errors))
for e in errors: print(e)
sys.exit(1 if errors else 0)
