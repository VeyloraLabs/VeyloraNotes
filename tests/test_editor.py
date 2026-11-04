import conftest_env
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.languages import language_by_id
from app.gui.editor import CodeEditor
from app.settings import Settings

app = QApplication([])
app.setOrganizationName("VNTest")
app.setApplicationName("VNTest")
settings = Settings()
settings.store.clear()


def make(text, language="plain"):
    editor = CodeEditor(settings)
    editor.apply_settings()
    editor.set_language(language_by_id(language))
    editor.setPlainText(text)
    editor.resize(600, 300)
    return editor


def place(editor, line, column=0, end_line=None, end_column=None):
    document = editor.document()
    cursor = QTextCursor(document)
    cursor.setPosition(document.findBlockByNumber(line).position() + column)
    if end_line is not None:
        cursor.setPosition(document.findBlockByNumber(end_line).position() + end_column, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


e = make("a\nb\nc")
place(e, 1, 1); e.duplicate_line(); assert e.text() == "a\nb\nb\nc", e.text()
place(e, 0, 0, 1, 1); e.duplicate_line(); assert e.text().startswith("a\nb"), e.text()
e = make("a\nb\nc"); place(e, 1); e.delete_line(); assert e.text() == "a\nc", e.text()
e = make("a\nb\nc"); place(e, 2); e.delete_line(); assert e.text() == "a\nb", e.text()
e = make("only"); place(e, 0); e.delete_line(); assert e.text() == "", repr(e.text())
e = make("a\nb\nc"); place(e, 1); e.move_lines(-1); assert e.text() == "b\na\nc", e.text()
e.move_lines(1); assert e.text() == "a\nb\nc", e.text()
e = make("a\nb\nc"); place(e, 0, 0, 1, 1); e.move_lines(1); assert e.text() == "c\na\nb", e.text()
e = make("a\nb\nc"); place(e, 0); e.move_lines(-1); assert e.text() == "a\nb\nc"
e = make("a\n  b\n  c"); place(e, 0, 0, 2, 3); e.join_lines(); assert e.text() == "a b c", e.text()
e = make("one\ntwo"); place(e, 0); e.join_lines(); assert e.text() == "one two", e.text()
e = make("a\nb"); place(e, 0, 0, 1, 1); e.indent_selection(); assert e.text() == "    a\n    b", e.text()
e.outdent_selection(); assert e.text() == "a\nb", e.text()
e = make("x = 1\n\ny = 2", "python"); place(e, 0, 0, 2, 3); e.toggle_comment(); assert e.text() == "# x = 1\n\n# y = 2", e.text()
e.toggle_comment(); assert e.text() == "x = 1\n\ny = 2", e.text()
e = make("text", "html"); place(e, 0); e.toggle_comment(); assert e.text() == "<!-- text -->", e.text()
e.toggle_comment(); assert e.text() == "text", e.text()
e = make("hello world"); e.transform_text(str.upper); assert e.text() == "HELLO WORLD"
place(e, 0, 0, 0, 5); e.transform_text(str.lower); assert e.text() == "hello WORLD", e.text()
e = make("b\na\nc\nd"); place(e, 0, 1, 2, 0); e.transform_text(lambda t: "\n".join(sorted(t.split("\n"))), lines=True); assert e.text() == "a\nb\nc\nd", repr(e.text())
e.undo(); assert e.text() == "b\na\nc\nd", e.text()
e = make("- [ ] task\n"); place(e, 0); e.toggle_task(); assert e.text() == "- [x] task\n", e.text()
e = make("plain"); place(e, 0, 0, 0, 5); e.wrap_selection("**"); assert e.text() == "**plain**"; e.wrap_selection("**"); 
e = make(""); e.wrap_selection("**", placeholder="bold"); assert e.text() == "**bold**" and e.selected_text() == "bold"
e = make("line", "markdown"); e.setPlainText("- item"); place(e, 0, 6); QTest.keyClick(e, Qt.Key.Key_Return); assert e.text() == "- item\n- ", repr(e.text())
QTest.keyClick(e, Qt.Key.Key_Return); assert e.text() == "- item\n", repr(e.text())
e = make("1. a"); e.set_language(language_by_id("markdown")); place(e, 0, 4); QTest.keyClick(e, Qt.Key.Key_Return); assert e.text() == "1. a\n2. ", repr(e.text())
e = make("    indented"); place(e, 0, 12); QTest.keyClick(e, Qt.Key.Key_Return); assert e.text() == "    indented\n    ", repr(e.text())
e = make("def f():", "python"); place(e, 0, 8); QTest.keyClick(e, Qt.Key.Key_Return); assert e.text() == "def f():\n    ", repr(e.text())
e = make("ab"); place(e, 0, 1); QTest.keyClick(e, Qt.Key.Key_Tab); assert e.text() == "a   b", repr(e.text())
e = make("  x"); place(e, 0, 3); QTest.keyClick(e, Qt.Key.Key_Home); assert e.textCursor().positionInBlock() == 2
QTest.keyClick(e, Qt.Key.Key_Home); assert e.textCursor().positionInBlock() == 0
e = make("a💚b\nsecond"); e.select_line(); assert e.selected_text().startswith("a💚b"), e.selected_text()
e = make("foo bar foo"); place(e, 0, 0, 0, 3); e.refresh_extra_selections(); print("selections:", len(e.extraSelections()))
e = make("(a [b] {c})"); place(e, 0, 0); print("bracket selections:", len(e.bracket_selections()))
e = make("x"); e.zoom_in(); e.zoom_in(); assert e.zoom_percent() > 100; e.reset_zoom(); assert e.zoom_percent() == 100
e = make("\n".join(str(i) for i in range(1000))); assert e.gutter_width() > 40
e.show(); app.processEvents(); e.line_number_area.grab()
print("all editor tests passed")
