from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox, PrimaryPushButton, PushButton

from .. import i18n
from ..theme import ACCENT, BORDER, CARD, MUTED, PANEL, TEXT

MONO = "'JetBrains Mono','DejaVu Sans Mono',monospace"


class BaseDialog(QDialog):
    def __init__(self, parent, title, width=520, height=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        if height:
            self.resize(width, height)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(22, 20, 22, 18)
        self.root.setSpacing(14)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(8)
        self.buttons.addStretch(1)

    def finish(self, primary_text=None):
        close = PrimaryPushButton(primary_text or i18n.t("common.close"))
        close.clicked.connect(self.accept)
        self.buttons.addWidget(close)
        self.root.addLayout(self.buttons)
        return close


class StatsDialog(BaseDialog):
    def __init__(self, parent, stats, scope):
        super().__init__(parent, i18n.t("stats.title"), 520)
        subtitle = QLabel(scope)
        subtitle.setStyleSheet(f"color: {MUTED};")
        self.root.addWidget(subtitle)
        grid = QGridLayout()
        grid.setSpacing(10)
        minutes = stats["reading_minutes"]
        reading = i18n.t("stats.less_than_minute") if minutes < 1 else i18n.t("stats.minutes", round(minutes))
        items = (
            ("words", f"{stats['words']:,}"),
            ("characters", f"{stats['characters']:,}"),
            ("characters_no_spaces", f"{stats['characters_no_spaces']:,}"),
            ("lines", f"{stats['lines']:,}"),
            ("paragraphs", f"{stats['paragraphs']:,}"),
            ("sentences", f"{stats['sentences']:,}"),
            ("bytes", f"{stats['bytes']:,}"),
            ("reading", reading),
        )
        for index, (key, value) in enumerate(items):
            card = QWidget()
            card.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;")
            inner = QVBoxLayout(card)
            inner.setContentsMargins(12, 9, 12, 9)
            inner.setSpacing(0)
            number = QLabel(value)
            number.setStyleSheet(f"color: {ACCENT}; font-size: 20px; font-weight: 700; border: none;")
            caption = QLabel(i18n.t(f"stats.{key}"))
            caption.setStyleSheet(f"color: {MUTED}; font-size: 11px; border: none;")
            inner.addWidget(number)
            inner.addWidget(caption)
            grid.addWidget(card, index // 4, index % 4)
        self.root.addLayout(grid)
        if stats["top_words"]:
            heading = QLabel(i18n.t("stats.top_words"))
            heading.setStyleSheet(f"color: {TEXT}; font-weight: 700;")
            self.root.addWidget(heading)
            words = QLabel("  ·  ".join(f"{word} ({count})" for word, count in stats["top_words"]))
            words.setWordWrap(True)
            words.setStyleSheet(f"color: {MUTED};")
            self.root.addWidget(words)
        self.finish()


class HashDialog(BaseDialog):
    def __init__(self, parent, hashes, scope):
        super().__init__(parent, i18n.t("hash.title"), 640)
        subtitle = QLabel(scope)
        subtitle.setStyleSheet(f"color: {MUTED};")
        self.root.addWidget(subtitle)
        for name, value in hashes.items():
            row = QHBoxLayout()
            label = QLabel(name)
            label.setFixedWidth(70)
            label.setStyleSheet(f"color: {ACCENT}; font-weight: 700;")
            field = QLineEdit(value)
            field.setReadOnly(True)
            field.setStyleSheet(f"font-family: {MONO}; font-size: 12px;")
            copy = PushButton(i18n.t("common.copy"))
            copy.clicked.connect(lambda _=False, text=value: QGuiApplication.clipboard().setText(text))
            row.addWidget(label)
            row.addWidget(field, 1)
            row.addWidget(copy)
            self.root.addLayout(row)
        self.finish()


class DiffDialog(BaseDialog):
    def __init__(self, parent, title, html, summary):
        super().__init__(parent, title, 760, 520)
        label = QLabel(summary)
        label.setStyleSheet(f"color: {MUTED};")
        self.root.addWidget(label)
        view = QTextBrowser()
        view.setStyleSheet(f"QTextBrowser {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px; }}")
        view.setHtml(html)
        self.root.addWidget(view, 1)
        self.finish()


class TableDialog(BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, i18n.t("table.title"), 340)
        grid = QGridLayout()
        grid.setSpacing(10)
        self.column_box = ComboBox()
        self.column_box.addItems([str(value) for value in range(1, 13)])
        self.column_box.setCurrentText("3")
        self.row_box = ComboBox()
        self.row_box.addItems([str(value) for value in range(1, 31)])
        self.row_box.setCurrentText("3")
        grid.addWidget(QLabel(i18n.t("table.columns")), 0, 0)
        grid.addWidget(self.column_box, 0, 1)
        grid.addWidget(QLabel(i18n.t("table.rows")), 1, 0)
        grid.addWidget(self.row_box, 1, 1)
        self.root.addLayout(grid)
        self.add_actions()

    def columns(self):
        return int(self.column_box.currentText())

    def rows(self):
        return int(self.row_box.currentText())

    def add_actions(self):
        cancel = PushButton(i18n.t("common.cancel"))
        cancel.clicked.connect(self.reject)
        self.buttons.addWidget(cancel)
        ok = PrimaryPushButton(i18n.t("table.insert"))
        ok.clicked.connect(self.accept)
        self.buttons.addWidget(ok)
        self.root.addLayout(self.buttons)


class ShortcutsDialog(BaseDialog):
    def __init__(self, parent, rows):
        super().__init__(parent, i18n.t("shortcuts.title"), 640, 560)
        self.rows = rows
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(i18n.t("shortcuts.filter"))
        self.root.addWidget(self.filter)
        self.view = QTextBrowser()
        self.view.setStyleSheet(f"QTextBrowser {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px; }}")
        self.root.addWidget(self.view, 1)
        self.filter.textChanged.connect(self.render)
        self.render("")
        self.finish()

    def render(self, text):
        query = text.strip().casefold()
        pieces = [f'<table width="100%" cellspacing="0" cellpadding="5">']
        current = None
        for category, title, shortcut in self.rows:
            if query and query not in f"{category} {title} {shortcut}".casefold():
                continue
            if category != current:
                current = category
                pieces.append(f'<tr><td colspan="2" style="color:{ACCENT}; font-weight:700; padding-top:12px;">{category}</td></tr>')
            keys = shortcut or "—"
            pieces.append(
                f'<tr><td style="color:{TEXT};">{title}</td><td align="right" style="color:{MUTED}; font-family:{MONO};">{keys}</td></tr>'
            )
        pieces.append("</table>")
        self.view.setHtml("".join(pieces))
