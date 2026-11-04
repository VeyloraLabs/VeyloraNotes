import re

from PySide6.QtCore import QRect, QSize, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextOption,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from ..core.markdown_tools import list_continuation, toggle_task_line
from ..theme import (
    BORDER,
    BRACKET,
    CURRENT_LINE,
    EDITOR_BG,
    GUTTER,
    MATCH,
    OCCURRENCE,
    TEXT,
)
from .highlighter import MAX_HIGHLIGHT_CHARACTERS, create_highlighter

BRACKETS = {"(": ")", "[": "]", "{": "}"}
CLOSING = {value: key for key, value in BRACKETS.items()}
URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+")
MAX_SEARCH_HIGHLIGHTS = 3000
MAX_OCCURRENCES = 400
MAX_BRACKET_SCAN = 20000
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72


def normalize_selection(text):
    return text.replace("\u2029", "\n").replace("\u2028", "\n")


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    zoom_changed = Signal(int)
    files_dropped = Signal(list)
    image_pasted = Signal(object)
    context_menu_requested = Signal(object)
    escape_pressed = Signal()
    cursor_info_changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.language = None
        self.highlighter = None
        self.zoom_steps = 0
        self.search_matches = []
        self.show_numbers = True
        self.highlight_current_line = True
        self.use_spaces = True
        self.tab_width = 4
        self.auto_indent = True
        self.continue_lists = True
        self.base_font_size = 11
        self.reserved_shortcuts = set()
        self.line_number_area = LineNumberArea(self)
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {EDITOR_BG}; border: none; border-radius: 0; padding: 0; "
            f"selection-background-color: #1f5c46; selection-color: #ffffff; }}"
        )
        self.document().setDocumentMargin(12)
        self.setCursorWidth(2)
        self.setUndoRedoEnabled(True)
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.on_cursor_changed)
        self.selectionChanged.connect(self.on_cursor_changed)
        self.update_gutter_width()

    def apply_settings(self):
        settings = self.settings
        self.base_font_size = settings.get("font_size")
        self.show_numbers = settings.get("line_numbers")
        self.highlight_current_line = settings.get("highlight_line")
        self.use_spaces = settings.get("use_spaces")
        self.tab_width = settings.get("tab_width")
        self.auto_indent = settings.get("auto_indent")
        self.continue_lists = settings.get("list_continuation")
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if settings.get("word_wrap") else QPlainTextEdit.LineWrapMode.NoWrap
        )
        option = self.document().defaultTextOption()
        flags = option.flags()
        if settings.get("show_whitespace"):
            flags |= QTextOption.Flag.ShowTabsAndSpaces
        else:
            flags &= ~QTextOption.Flag.ShowTabsAndSpaces
        option.setFlags(flags)
        self.document().setDefaultTextOption(option)
        self.apply_font()
        self.update_gutter_width()
        self.refresh_extra_selections()

    def apply_font(self):
        font = QFont(self.settings.get("font_family"))
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSizeF(max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self.base_font_size + self.zoom_steps)))
        self.setFont(font)
        self.line_number_area.setFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * self.tab_width)
        self.update_gutter_width()

    def zoom_percent(self):
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self.base_font_size + self.zoom_steps))
        return round(size / self.base_font_size * 100)

    def set_zoom_steps(self, steps):
        self.zoom_steps = max(MIN_FONT_SIZE - self.base_font_size, min(MAX_FONT_SIZE - self.base_font_size, steps))
        self.apply_font()
        self.zoom_changed.emit(self.zoom_percent())

    def zoom_in(self):
        self.set_zoom_steps(self.zoom_steps + 1)

    def zoom_out(self):
        self.set_zoom_steps(self.zoom_steps - 1)

    def reset_zoom(self):
        self.set_zoom_steps(0)

    def set_language(self, language):
        self.language = language
        if self.highlighter is not None:
            self.highlighter.setDocument(None)
            self.highlighter.deleteLater()
            self.highlighter = None
        if self.document().characterCount() <= MAX_HIGHLIGHT_CHARACTERS:
            self.highlighter = create_highlighter(self.document(), language)

    def is_markdown(self):
        return self.language is not None and self.language.id == "markdown"

    def text(self):
        return self.toPlainText()

    def selected_text(self):
        return normalize_selection(self.textCursor().selectedText())

    def cursor_line_column(self):
        cursor = self.textCursor()
        return cursor.blockNumber() + 1, cursor.positionInBlock() + 1

    def go_to_line(self, line, column=1):
        block = self.document().findBlockByNumber(max(0, min(line - 1, self.document().blockCount() - 1)))
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + max(0, min(column - 1, block.length() - 1)))
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()

    def replace_selection(self, text):
        cursor = self.textCursor()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def insert_text(self, text):
        self.replace_selection(text)
        self.setFocus()

    def transform_text(self, function, lines=False, whole_when_empty=True):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            if not cursor.hasSelection():
                if not whole_when_empty:
                    return False
                cursor.select(QTextCursor.SelectionType.Document)
            elif lines:
                start, end = sorted((cursor.anchor(), cursor.position()))
                cursor.setPosition(start)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                if not (cursor.atBlockStart() and end > start):
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            original = normalize_selection(cursor.selectedText())
            keeps_newline = lines and original.endswith("\n")
            result = function(original[:-1] if keeps_newline else original)
            if keeps_newline:
                result += "\n"
            if result == original:
                return False
            start = min(cursor.anchor(), cursor.position())
            cursor.insertText(result)
            cursor.setPosition(start)
            cursor.setPosition(start + len(result), QTextCursor.MoveMode.KeepAnchor)
        finally:
            cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def selected_block_range(self):
        cursor = self.textCursor()
        start = self.document().findBlock(min(cursor.anchor(), cursor.position()))
        end_position = max(cursor.anchor(), cursor.position())
        end = self.document().findBlock(end_position)
        if cursor.hasSelection() and end.position() == end_position and end.blockNumber() > start.blockNumber():
            end = end.previous()
        return start.blockNumber(), end.blockNumber()

    def duplicate_line(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if cursor.hasSelection():
            text = cursor.selectedText()
            end = max(cursor.anchor(), cursor.position())
            cursor.setPosition(end)
            cursor.insertText(text)
            cursor.setPosition(end)
            cursor.setPosition(end + len(text), QTextCursor.MoveMode.KeepAnchor)
        else:
            document = self.document()
            block = cursor.block()
            column = cursor.positionInBlock()
            cursor.setPosition(block.position() + block.length() - 1)
            cursor.insertText("\n" + block.text())
            copy = document.findBlockByNumber(block.blockNumber() + 1)
            cursor.setPosition(copy.position() + min(column, copy.length() - 1))
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def delete_line(self):
        start, end = self.selected_block_range()
        document = self.document()
        first = document.findBlockByNumber(start)
        last = document.findBlockByNumber(end)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if last.next().isValid():
            cursor.setPosition(first.position())
            cursor.setPosition(last.next().position(), QTextCursor.MoveMode.KeepAnchor)
        elif first.previous().isValid():
            previous = first.previous()
            cursor.setPosition(previous.position() + previous.length() - 1)
            cursor.setPosition(last.position() + last.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(first.position())
            cursor.setPosition(last.position() + last.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def move_lines(self, direction):
        document = self.document()
        start, end = self.selected_block_range()
        if direction < 0 and start == 0:
            return
        if direction > 0 and end >= document.blockCount() - 1:
            return
        had_selection = self.textCursor().hasSelection()
        column = self.textCursor().positionInBlock()
        first = start - 1 if direction < 0 else start
        last = end if direction < 0 else end + 1
        lines = [document.findBlockByNumber(number).text() for number in range(first, last + 1)]
        lines = lines[1:] + lines[:1] if direction < 0 else lines[-1:] + lines[:-1]
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(document.findBlockByNumber(first).position())
        last_block = document.findBlockByNumber(last)
        cursor.setPosition(last_block.position() + last_block.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText("\n".join(lines))
        cursor.endEditBlock()
        new_start = start + direction
        new_end = end + direction
        result = QTextCursor(document.findBlockByNumber(new_start))
        if had_selection:
            result.setPosition(document.findBlockByNumber(new_start).position())
            tail = document.findBlockByNumber(new_end)
            result.setPosition(tail.position() + tail.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        else:
            block = document.findBlockByNumber(new_start)
            result.setPosition(block.position() + min(column, block.length() - 1))
        self.setTextCursor(result)

    def join_lines(self):
        cursor = self.textCursor()
        document = self.document()
        start, end = self.selected_block_range()
        if start == end:
            end = min(end + 1, document.blockCount() - 1)
        if start == end:
            return
        lines = [document.findBlockByNumber(number).text() for number in range(start, end + 1)]
        joined = lines[0].rstrip() + "".join(" " + line.strip() if line.strip() else "" for line in lines[1:])
        cursor.beginEditBlock()
        cursor.setPosition(document.findBlockByNumber(start).position())
        last = document.findBlockByNumber(end)
        cursor.setPosition(last.position() + last.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(joined)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def select_line(self):
        start, end = self.selected_block_range()
        document = self.document()
        cursor = self.textCursor()
        cursor.setPosition(document.findBlockByNumber(start).position())
        last = document.findBlockByNumber(end)
        cursor.setPosition(min(last.position() + last.length(), document.characterCount() - 1), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def indent_unit(self):
        return " " * self.tab_width if self.use_spaces else "\t"

    def indent_selection(self):
        start, end = self.selected_block_range()
        unit = self.indent_unit()
        document = self.document()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for number in range(start, end + 1):
            block = document.findBlockByNumber(number)
            if block.text().strip() or start == end:
                inserter = QTextCursor(block)
                inserter.insertText(unit)
        cursor.endEditBlock()

    def outdent_selection(self):
        start, end = self.selected_block_range()
        document = self.document()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for number in range(start, end + 1):
            block = document.findBlockByNumber(number)
            text = block.text()
            if text.startswith("\t"):
                remove = 1
            else:
                remove = min(self.tab_width, len(text) - len(text.lstrip(" ")))
            if remove:
                remover = QTextCursor(block)
                remover.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, remove)
                remover.removeSelectedText()
        cursor.endEditBlock()

    def toggle_comment(self):
        language = self.language
        if language is None:
            return
        if language.line_comment:
            self.toggle_line_comment(language.line_comment.rstrip() + " " if not language.line_comment.endswith(" ") else language.line_comment)
        elif language.block_comment:
            self.toggle_block_comment(*language.block_comment)

    def toggle_line_comment(self, prefix):
        start, end = self.selected_block_range()
        document = self.document()
        blocks = [document.findBlockByNumber(number) for number in range(start, end + 1)]
        bare = prefix.rstrip()
        non_empty = [block for block in blocks if block.text().strip()]
        if not non_empty:
            return
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if all(block.text().lstrip().startswith(bare) for block in non_empty):
            for block in non_empty:
                text = block.text()
                indent = len(text) - len(text.lstrip())
                width = len(prefix) if text[indent:].startswith(prefix) else len(bare)
                remover = QTextCursor(block)
                remover.setPosition(block.position() + indent)
                remover.setPosition(block.position() + indent + width, QTextCursor.MoveMode.KeepAnchor)
                remover.removeSelectedText()
        else:
            indent = min(len(block.text()) - len(block.text().lstrip()) for block in non_empty)
            for block in non_empty:
                inserter = QTextCursor(block)
                inserter.setPosition(block.position() + indent)
                inserter.insertText(prefix)
        cursor.endEditBlock()

    def toggle_block_comment(self, opening, closing):
        def convert(text):
            stripped = text.strip()
            if stripped.startswith(opening) and stripped.endswith(closing) and len(stripped) >= len(opening) + len(closing):
                inner = stripped[len(opening):len(stripped) - len(closing)]
                return inner.strip(" ") if inner.startswith(" ") or inner.endswith(" ") else inner
            return f"{opening} {text} {closing}"

        self.transform_text(convert, lines=True)

    def toggle_task(self):
        start, end = self.selected_block_range()
        document = self.document()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for number in range(start, end + 1):
            block = document.findBlockByNumber(number)
            replacement = toggle_task_line(block.text())
            line_cursor = QTextCursor(block)
            line_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            line_cursor.insertText(replacement)
        cursor.endEditBlock()

    def wrap_selection(self, before, after=None, placeholder="text"):
        after = before if after is None else after
        cursor = self.textCursor()
        selected = normalize_selection(cursor.selectedText())
        cursor.beginEditBlock()
        if selected.startswith(before) and selected.endswith(after) and len(selected) >= len(before) + len(after):
            cursor.insertText(selected[len(before):len(selected) - len(after)])
        elif selected:
            cursor.insertText(f"{before}{selected}{after}")
        else:
            position = cursor.position()
            cursor.insertText(f"{before}{placeholder}{after}")
            cursor.setPosition(position + len(before))
            cursor.setPosition(position + len(before) + len(placeholder), QTextCursor.MoveMode.KeepAnchor)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setFocus()

    def prefix_lines(self, prefix, strip_pattern=None):
        start, end = self.selected_block_range()
        document = self.document()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for number in range(start, end + 1):
            block = document.findBlockByNumber(number)
            text = block.text()
            if strip_pattern:
                text = re.sub(strip_pattern, "", text)
            line_cursor = QTextCursor(block)
            line_cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            line_cursor.insertText(prefix + text)
        cursor.endEditBlock()
        self.setFocus()

    def set_search_matches(self, matches):
        self.search_matches = matches[:MAX_SEARCH_HIGHLIGHTS]
        self.refresh_extra_selections()

    def on_cursor_changed(self):
        self.refresh_extra_selections()
        self.line_number_area.update()
        self.cursor_info_changed.emit()

    def refresh_extra_selections(self):
        selections = []
        if self.highlight_current_line and not self.textCursor().hasSelection():
            line = QTextEdit.ExtraSelection()
            line.format.setBackground(QColor(CURRENT_LINE))
            line.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            line.cursor = self.textCursor()
            line.cursor.clearSelection()
            selections.append(line)
        selections.extend(self.occurrence_selections())
        for start, length in self.search_matches:
            match = QTextEdit.ExtraSelection()
            match.format.setBackground(QColor(MATCH))
            match.cursor = QTextCursor(self.document())
            match.cursor.setPosition(start)
            match.cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            selections.append(match)
        selections.extend(self.bracket_selections())
        self.setExtraSelections(selections)

    def occurrence_selections(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return []
        word = cursor.selectedText()
        if not 2 <= len(word) <= 60 or not re.fullmatch(r"\w+", word, re.UNICODE):
            return []
        selections = []
        found = QTextCursor(self.document())
        flags = QTextDocument.FindFlag.FindCaseSensitively | QTextDocument.FindFlag.FindWholeWords
        while len(selections) < MAX_OCCURRENCES:
            found = self.document().find(word, found, flags)
            if found.isNull():
                break
            if found.selectionStart() == cursor.selectionStart():
                continue
            extra = QTextEdit.ExtraSelection()
            extra.format.setBackground(QColor(OCCURRENCE))
            extra.cursor = found
            selections.append(extra)
        return selections

    def bracket_selections(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            return []
        document = self.document()
        position = cursor.position()
        for candidate in (position, position - 1):
            if candidate < 0:
                continue
            character = document.characterAt(candidate)
            if character in BRACKETS or character in CLOSING:
                partner = self.find_partner(candidate, character)
                if partner is not None:
                    result = []
                    for index in (candidate, partner):
                        extra = QTextEdit.ExtraSelection()
                        extra.format.setBackground(QColor(BRACKET))
                        extra.cursor = QTextCursor(document)
                        extra.cursor.setPosition(index)
                        extra.cursor.setPosition(index + 1, QTextCursor.MoveMode.KeepAnchor)
                        result.append(extra)
                    return result
        return []

    def find_partner(self, index, character):
        document = self.document()
        forward = character in BRACKETS
        target = BRACKETS[character] if forward else CLOSING[character]
        depth = 0
        step = 1 if forward else -1
        position = index
        total = document.characterCount()
        for _ in range(MAX_BRACKET_SCAN):
            current = document.characterAt(position)
            if current == character:
                depth += 1
            elif current == target:
                depth -= 1
                if depth == 0:
                    return position
            position += step
            if position < 0 or position >= total:
                return None
        return None

    def gutter_width(self):
        if not self.show_numbers:
            return 0
        digits = max(3, len(str(self.blockCount())))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_gutter_width(self, *_):
        width = self.gutter_width()
        self.setViewportMargins(width, 0, 0, 0)
        self.line_number_area.setVisible(self.show_numbers)
        self.line_number_area.setGeometry(QRect(self.contentsRect().left(), self.contentsRect().top(), width, self.contentsRect().height()))

    def update_gutter(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(QRect(contents.left(), contents.top(), self.gutter_width(), contents.height()))

    def paint_gutter(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#121518"))
        painter.setPen(QColor(BORDER))
        painter.drawLine(self.line_number_area.width() - 1, event.rect().top(), self.line_number_area.width() - 1, event.rect().bottom())
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        height = self.fontMetrics().height()
        width = self.line_number_area.width() - 12
        bold_font = QFont(self.font())
        bold_font.setBold(True)
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setFont(bold_font if number == current else self.font())
                painter.setPen(QColor(TEXT if number == current else GUTTER))
                painter.drawText(0, top, width, height, Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    def event(self, event):
        if event.type() == event.Type.ShortcutOverride and self.reserved_shortcuts:
            sequence = QKeySequence(event.keyCombination()).toString()
            if sequence in self.reserved_shortcuts:
                event.ignore()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        plain = not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier))
        if key == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            super().keyPressEvent(event)
            return
        if key == Qt.Key.Key_Tab and plain and not self.isReadOnly():
            cursor = self.textCursor()
            if cursor.hasSelection() and self.selected_block_range()[0] != self.selected_block_range()[1]:
                self.indent_selection()
            elif self.use_spaces:
                column = cursor.positionInBlock()
                cursor.insertText(" " * (self.tab_width - column % self.tab_width))
            else:
                cursor.insertText("\t")
            return
        if key == Qt.Key.Key_Backtab and not self.isReadOnly():
            self.outdent_selection()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and plain and not self.isReadOnly():
            if self.handle_enter():
                return
        if key == Qt.Key.Key_Home and not (modifiers & Qt.KeyboardModifier.ControlModifier):
            if self.smart_home(bool(modifiers & Qt.KeyboardModifier.ShiftModifier)):
                return
        super().keyPressEvent(event)

    def smart_home(self, extend):
        cursor = self.textCursor()
        block = cursor.block()
        text = block.text()
        first = len(text) - len(text.lstrip())
        target = block.position() + (first if cursor.position() != block.position() + first else 0)
        if first == 0:
            return False
        mode = QTextCursor.MoveMode.KeepAnchor if extend else QTextCursor.MoveMode.MoveAnchor
        cursor.setPosition(target, mode)
        self.setTextCursor(cursor)
        return True

    def handle_enter(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        block = cursor.block()
        text = block.text()
        column = cursor.positionInBlock()
        if self.continue_lists and self.is_markdown() and column == block.length() - 1:
            continuation = list_continuation(text)
            if continuation:
                prefix, empty, _ = continuation
                cursor.beginEditBlock()
                if empty:
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                else:
                    cursor.insertText("\n" + prefix)
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                return True
        if not self.auto_indent:
            return False
        indent = text[: len(text) - len(text.lstrip())][:column]
        extra = ""
        before = text.encode("utf-16-le")[: column * 2].decode("utf-16-le", errors="ignore").rstrip()
        if self.language is not None and self.language.engine in ("code", "rules") and before.endswith(("{", "[", "(", ":")):
            if before.endswith(":") and self.language.id not in ("python", "yaml"):
                extra = ""
            else:
                extra = self.indent_unit()
        cursor.insertText("\n" + indent + extra)
        self.ensureCursorVisible()
        return True

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def url_at(self, position):
        cursor = self.cursorForPosition(position)
        text = cursor.block().text()
        column = cursor.positionInBlock()
        for match in URL_PATTERN.finditer(text):
            start = len(text[: match.start()].encode("utf-16-le")) // 2
            end = len(text[: match.end()].encode("utf-16-le")) // 2
            if start <= column <= end:
                return match.group(0).rstrip(".,;:!?")
        return None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            url = self.url_at(event.position().toPoint())
            if url:
                QDesktopServices.openUrl(QUrl(url))
        super().mouseReleaseEvent(event)

    def canInsertFromMimeData(self, source):
        return source.hasUrls() or source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasUrls() and all(url.isLocalFile() for url in source.urls()):
            self.files_dropped.emit([url.toLocalFile() for url in source.urls()])
            return
        if source.hasImage() and not source.hasText():
            self.image_pasted.emit(source.imageData())
            return
        if source.hasText():
            self.insertPlainText(source.text())
            return
        super().insertFromMimeData(source)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        self.context_menu_requested.emit(menu)
        menu.exec(event.globalPos())
        menu.deleteLater()
