import re

from PySide6.QtCore import QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from .. import i18n
from ..icons import icon
from ..theme import BORDER, DANGER, MUTED, PANEL, TEXT
from .ui import tool_button

MAX_MATCHES = 10000
TEMPLATE_PATTERN = re.compile(r"\\([0-9ntr\\])|\$(\d)")


def expand_template(template, match):
    def replace(found):
        escaped, group = found.group(1), found.group(2)
        if group is not None:
            return match.captured(int(group)) if int(group) <= match.lastCapturedIndex() else ""
        if escaped.isdigit():
            return match.captured(int(escaped)) if int(escaped) <= match.lastCapturedIndex() else ""
        return {"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}[escaped]

    return TEMPLATE_PATTERN.sub(replace, template)


class FindBar(QFrame):
    closed = Signal()
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = None
        self.setStyleSheet(
            f"FindBar {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}"
            f"QLineEdit {{ padding: 5px 9px; border-radius: 7px; }}"
        )
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(120)
        self.update_timer.timeout.connect(self.refresh)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(5)
        self.expand_button = tool_button("fa5s.chevron-right", "", True, size=28, icon_size=11)
        self.find_input = QLineEdit()
        self.find_input.setMinimumWidth(220)
        self.case_button = tool_button(None, "", True, "Aa", 28)
        self.word_button = tool_button(None, "", True, "ab", 28)
        self.regex_button = tool_button(None, "", True, ".*", 28)
        self.count_label = QLabel("")
        self.count_label.setMinimumWidth(78)
        self.count_label.setStyleSheet(f"color: {MUTED};")
        self.previous_button = tool_button("fa5s.arrow-up", "", size=28, icon_size=12)
        self.next_button = tool_button("fa5s.arrow-down", "", size=28, icon_size=12)
        self.close_button = tool_button("fa5s.times", "", size=28, icon_size=12)
        for widget in (self.expand_button, self.find_input, self.case_button, self.word_button, self.regex_button,
                       self.count_label, self.previous_button, self.next_button):
            top.addWidget(widget)
        top.addStretch(1)
        top.addWidget(self.close_button)
        root.addLayout(top)

        self.replace_row = QFrame()
        bottom = QHBoxLayout(self.replace_row)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(5)
        spacer = QLabel()
        spacer.setFixedWidth(28)
        self.replace_input = QLineEdit()
        self.replace_input.setMinimumWidth(220)
        self.replace_button = QPushButton()
        self.replace_all_button = QPushButton()
        for button in (self.replace_button, self.replace_all_button):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet("padding: 5px 12px;")
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bottom.addWidget(spacer)
        bottom.addWidget(self.replace_input)
        bottom.addWidget(self.replace_button)
        bottom.addWidget(self.replace_all_button)
        bottom.addStretch(1)
        root.addWidget(self.replace_row)
        self.replace_row.setVisible(False)

        self.expand_button.toggled.connect(self.set_replace_visible)
        self.find_input.textChanged.connect(self.schedule_refresh)
        for button in (self.case_button, self.word_button, self.regex_button):
            button.toggled.connect(self.schedule_refresh)
        self.find_input.returnPressed.connect(lambda: self.find_next(True))
        self.replace_input.returnPressed.connect(self.replace_current)
        self.next_button.clicked.connect(lambda: self.find_next(True))
        self.previous_button.clicked.connect(lambda: self.find_next(False))
        self.close_button.clicked.connect(self.close_bar)
        self.replace_button.clicked.connect(self.replace_current)
        self.replace_all_button.clicked.connect(self.replace_all)
        self.retranslate()
        self.setVisible(False)

    def retranslate(self):
        t = i18n.t
        self.find_input.setPlaceholderText(t("find.placeholder"))
        self.replace_input.setPlaceholderText(t("find.replace_placeholder"))
        self.case_button.setToolTip(t("find.match_case"))
        self.word_button.setToolTip(t("find.whole_word"))
        self.regex_button.setToolTip(t("find.regex"))
        self.previous_button.setToolTip(t("find.previous"))
        self.next_button.setToolTip(t("find.next"))
        self.close_button.setToolTip(t("find.close"))
        self.expand_button.setToolTip(t("find.toggle_replace"))
        self.replace_button.setText(t("find.replace"))
        self.replace_all_button.setText(t("find.replace_all"))

    def attach(self, editor):
        if self.editor is editor:
            return
        if self.editor is not None:
            try:
                self.editor.textChanged.disconnect(self.schedule_refresh)
            except (RuntimeError, TypeError):
                pass
            self.editor.set_search_matches([])
        self.editor = editor
        if editor is not None:
            editor.textChanged.connect(self.schedule_refresh)
            if self.isVisible():
                self.refresh()

    def open_bar(self, replace=False):
        self.setVisible(True)
        if replace:
            self.expand_button.setChecked(True)
        editor = self.editor
        if editor is not None:
            selected = editor.selected_text()
            if selected and "\n" not in selected and len(selected) < 200:
                self.find_input.setText(selected)
        self.find_input.setFocus()
        self.find_input.selectAll()
        self.refresh()

    def close_bar(self):
        self.setVisible(False)
        if self.editor is not None:
            self.editor.set_search_matches([])
            self.editor.setFocus()
        self.closed.emit()

    def set_replace_visible(self, visible):
        self.replace_row.setVisible(visible)
        self.expand_button.setIcon(icon("fa5s.chevron-down" if visible else "fa5s.chevron-right", MUTED, TEXT))

    def schedule_refresh(self, *_):
        if self.isVisible():
            self.update_timer.start()

    def build_pattern(self):
        text = self.find_input.text()
        if not text:
            return None, True
        if not self.regex_button.isChecked():
            return text, True
        source = text
        if self.word_button.isChecked():
            source = rf"\b(?:{text})\b"
        options = QRegularExpression.PatternOption.NoPatternOption
        if not self.case_button.isChecked():
            options = QRegularExpression.PatternOption.CaseInsensitiveOption
        pattern = QRegularExpression(source, options | QRegularExpression.PatternOption.UseUnicodePropertiesOption)
        return pattern, pattern.isValid()

    def search_flags(self, backward=False):
        flags = QTextDocument.FindFlag(0)
        if self.case_button.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.word_button.isChecked() and not self.regex_button.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def run_find(self, pattern, start_cursor, backward=False):
        document = self.editor.document()
        return document.find(pattern, start_cursor, self.search_flags(backward))

    def collect_matches(self):
        pattern, valid = self.build_pattern()
        if pattern is None or not valid or self.editor is None:
            return [], valid, False
        matches = []
        cursor = QTextCursor(self.editor.document())
        truncated = False
        while True:
            cursor = self.run_find(pattern, cursor)
            if cursor.isNull():
                break
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            if end == start:
                cursor.setPosition(end + 1)
                if end + 1 >= self.editor.document().characterCount():
                    break
                continue
            matches.append((start, end - start))
            if len(matches) >= MAX_MATCHES:
                truncated = True
                break
        return matches, valid, truncated

    def refresh(self):
        if self.editor is None:
            return
        matches, valid, truncated = self.collect_matches()
        self.editor.set_search_matches(matches)
        self.find_input.setStyleSheet(f"border-color: {DANGER};" if not valid else "")
        if not self.find_input.text():
            self.count_label.setText("")
        elif not valid:
            self.count_label.setText(i18n.t("find.invalid"))
        elif not matches:
            self.count_label.setText(i18n.t("find.no_results"))
        else:
            cursor = self.editor.textCursor()
            index = next((position for position, (start, length) in enumerate(matches, 1)
                          if start == cursor.selectionStart() and length == cursor.selectionEnd() - cursor.selectionStart()), 0)
            total = f"{len(matches)}+" if truncated else str(len(matches))
            self.count_label.setText(i18n.t("find.count", index, total) if index else i18n.t("find.total", total))

    def find_next(self, forward=True):
        if self.editor is None:
            return False
        pattern, valid = self.build_pattern()
        if pattern is None or not valid:
            return False
        editor = self.editor
        cursor = editor.textCursor()
        if not forward:
            cursor.setPosition(cursor.selectionStart())
        found = self.run_find(pattern, cursor, backward=not forward)
        if found.isNull():
            wrap = QTextCursor(editor.document())
            if not forward:
                wrap.movePosition(QTextCursor.MoveOperation.End)
            found = self.run_find(pattern, wrap, backward=not forward)
            if not found.isNull():
                self.message.emit(i18n.t("find.wrapped"))
        if found.isNull():
            self.count_label.setText(i18n.t("find.no_results"))
            return False
        editor.setTextCursor(found)
        editor.centerCursor()
        self.refresh()
        return True

    def selection_matches(self):
        pattern, valid = self.build_pattern()
        if pattern is None or not valid or self.editor is None:
            return False
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return False
        probe = QTextCursor(self.editor.document())
        probe.setPosition(cursor.selectionStart())
        probe.setPosition(cursor.selectionStart())
        found = self.run_find(pattern, probe)
        return not found.isNull() and found.selectionStart() == cursor.selectionStart() and found.selectionEnd() == cursor.selectionEnd()

    def replacement_for(self, cursor):
        template = self.replace_input.text()
        if not self.regex_button.isChecked():
            return template
        pattern, _ = self.build_pattern()
        block = cursor.block()
        offset = cursor.selectionStart() - block.position()
        match = pattern.match(block.text(), offset)
        if match.hasMatch() and match.capturedStart() == offset:
            return expand_template(template, match)
        return template

    def replace_current(self):
        if self.editor is None:
            return
        if self.selection_matches():
            cursor = self.editor.textCursor()
            replacement = self.replacement_for(cursor)
            cursor.insertText(replacement)
            self.editor.setTextCursor(cursor)
        self.find_next(True)

    def replace_all(self):
        if self.editor is None:
            return
        matches, valid, _ = self.collect_matches()
        if not matches:
            return
        editor = self.editor
        document = editor.document()
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        for start, length in reversed(matches):
            target = QTextCursor(document)
            target.setPosition(start)
            target.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            target.insertText(self.replacement_for(target) if self.regex_button.isChecked() else self.replace_input.text())
        cursor.endEditBlock()
        self.message.emit(i18n.t("find.replaced", len(matches)))
        self.refresh()
