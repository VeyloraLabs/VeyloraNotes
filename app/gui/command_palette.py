import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from .. import i18n
from ..icons import icon
from ..theme import ACCENT, BORDER, CARD, MUTED, PANEL, TEXT

MAX_RESULTS = 60
ROW_HEIGHT = 36


@dataclass
class PaletteEntry:
    title: str
    category: str
    callback: Callable
    shortcut: str = ""
    icon_name: str = "fa5s.bolt"
    keywords: str = ""


def normalize(text):
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def score_entry(entry, tokens, fuzzy=False):
    haystack = normalize(f"{entry.title} {entry.category} {entry.keywords}")
    title = normalize(entry.title)
    total = 0
    for token in tokens:
        position = title.find(token)
        if position >= 0:
            total += 120 - min(position, 60)
            if position == 0 or title[position - 1] == " ":
                total += 40
            continue
        position = haystack.find(token)
        if position >= 0:
            total += 30
            continue
        if fuzzy:
            iterator = iter(haystack)
            if all(char in iterator for char in token):
                total += 5
                continue
        return None
    return total


class PaletteRow(QWidget):
    def __init__(self, entry):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)
        glyph = QLabel()
        glyph.setPixmap(icon(entry.icon_name, ACCENT, ACCENT).pixmap(16, 16))
        glyph.setFixedWidth(20)
        title = QLabel(entry.title)
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        category = QLabel(entry.category)
        category.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        layout.addWidget(glyph)
        layout.addWidget(title)
        layout.addWidget(category)
        layout.addStretch(1)
        if entry.shortcut:
            shortcut = QLabel(entry.shortcut)
            shortcut.setStyleSheet(
                f"color: {MUTED}; font-size: 11px; background: {CARD}; border: 1px solid {BORDER}; border-radius: 5px; padding: 1px 6px;"
            )
            layout.addWidget(shortcut)
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class CommandPalette(QDialog):
    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.entries = []
        self.line_callback = None
        self.setObjectName("palette")
        self.setStyleSheet(
            f"QDialog#palette {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}"
            f"QLineEdit {{ background: {CARD}; border-radius: 9px; padding: 10px 12px; font-size: 14px; }}"
            f"QListWidget {{ background: transparent; border: none; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.input = QLineEdit()
        self.list = QListWidget()
        self.list.setSpacing(1)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet(f"color: {MUTED}; padding: 18px;")
        root.addWidget(self.input)
        root.addWidget(self.list, 1)
        root.addWidget(self.empty)
        self.input.textChanged.connect(self.refresh)
        self.input.installEventFilter(self)
        self.list.itemActivated.connect(self.run_item)
        self.list.itemClicked.connect(self.run_item)

    def open_palette(self, entries, prefill="", line_callback=None):
        self.entries = entries
        self.line_callback = line_callback
        self.input.setPlaceholderText(i18n.t("palette.placeholder"))
        self.empty.setText(i18n.t("palette.empty"))
        parent = self.parentWidget()
        width = min(660, max(420, parent.width() - 80))
        self.resize(width, min(460, max(260, parent.height() - 140)))
        anchor = parent.mapToGlobal(parent.rect().topLeft())
        self.move(anchor.x() + (parent.width() - width) // 2, anchor.y() + 70)
        self.input.setText(prefill)
        self.refresh(prefill)
        self.show()
        self.input.setFocus()

    def refresh(self, text=""):
        self.list.clear()
        query = text.strip()
        matches = []
        line_match = re.fullmatch(r":\s*(\d+)", query)
        if line_match and self.line_callback:
            number = int(line_match.group(1))
            matches.append(PaletteEntry(i18n.t("palette.go_line", number), i18n.t("cat.edit"), lambda: self.line_callback(number), "", "fa5s.level-down-alt"))
        else:
            tokens = [normalize(token) for token in query.split() if token]
            if not tokens:
                matches = list(self.entries[:MAX_RESULTS])
            else:
                scored = []
                for fuzzy in (False, True):
                    for entry in self.entries:
                        score = score_entry(entry, tokens, fuzzy)
                        if score is not None:
                            scored.append((-score, entry.title.casefold(), entry))
                    if scored:
                        break
                scored.sort(key=lambda item: (item[0], item[1]))
                matches = [entry for _, _, entry in scored[:MAX_RESULTS]]
        for entry in matches:
            item = QListWidgetItem()
            row = PaletteRow(entry)
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        self.empty.setVisible(not matches)
        self.list.setVisible(bool(matches))
        if matches:
            self.list.setCurrentRow(0)

    def run_item(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        self.close()
        if entry is not None:
            entry.callback()

    def eventFilter(self, source, event):
        if source is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            count = self.list.count()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and count:
                step = 1 if key == Qt.Key.Key_Down else -1
                self.list.setCurrentRow((self.list.currentRow() + step) % count)
                return True
            if key in (Qt.Key.Key_PageDown, Qt.Key.Key_PageUp) and count:
                step = 8 if key == Qt.Key.Key_PageDown else -8
                self.list.setCurrentRow(max(0, min(count - 1, self.list.currentRow() + step)))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.list.currentItem() is not None:
                self.run_item(self.list.currentItem())
                return True
        return super().eventFilter(source, event)
