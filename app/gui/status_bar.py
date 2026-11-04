from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .. import i18n
from ..theme import ACCENT, BORDER, MUTED, PANEL, WARNING
from .ui import link_button


class StatusBar(QWidget):
    language_clicked = Signal()
    encoding_clicked = Signal()
    eol_clicked = Signal()
    indent_clicked = Signal()
    zoom_clicked = Signal()
    position_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setStyleSheet(f"QWidget#statusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 2, 10, 2)
        layout.setSpacing(2)
        self.save_label = QLabel()
        self.message_label = QLabel()
        self.message_label.setStyleSheet(f"color: {MUTED}; font-size: 11px; padding-left: 12px;")
        self.selection_label = QLabel()
        self.selection_label.setStyleSheet(f"color: {MUTED}; font-size: 11px; padding-right: 6px;")
        self.position_button = link_button("")
        self.language_button = link_button("")
        self.encoding_button = link_button("")
        self.eol_button = link_button("")
        self.indent_button = link_button("")
        self.zoom_button = link_button("")
        layout.addWidget(self.save_label)
        layout.addWidget(self.message_label)
        layout.addStretch(1)
        layout.addWidget(self.selection_label)
        for button in (self.position_button, self.indent_button, self.encoding_button, self.eol_button, self.language_button, self.zoom_button):
            layout.addWidget(button)
        self.position_button.clicked.connect(self.position_clicked)
        self.language_button.clicked.connect(self.language_clicked)
        self.encoding_button.clicked.connect(self.encoding_clicked)
        self.eol_button.clicked.connect(self.eol_clicked)
        self.indent_button.clicked.connect(self.indent_clicked)
        self.zoom_button.clicked.connect(self.zoom_clicked)
        self.message_timer = QTimer(self)
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(lambda: self.message_label.setText(""))
        self.retranslate()

    def retranslate(self):
        t = i18n.t
        self.position_button.setToolTip(t("status.go_to_line"))
        self.language_button.setToolTip(t("status.language_tip"))
        self.encoding_button.setToolTip(t("status.encoding_tip"))
        self.eol_button.setToolTip(t("status.eol_tip"))
        self.indent_button.setToolTip(t("status.indent_tip"))
        self.zoom_button.setToolTip(t("status.zoom_tip"))

    def set_saved(self, saved):
        if saved:
            self.save_label.setText(f"✓  {i18n.t('status.saved')}")
            self.save_label.setStyleSheet(f"color: {ACCENT}; font-size: 11px;")
        else:
            self.save_label.setText(f"●  {i18n.t('status.unsaved')}")
            self.save_label.setStyleSheet(f"color: {WARNING}; font-size: 11px;")

    def set_position(self, line, column, lines):
        self.position_button.setText(i18n.t("status.position", line, column))
        self.position_button.setToolTip(i18n.t("status.go_to_line") + f"  ·  {lines}")

    def set_selection(self, characters, lines):
        if characters:
            text = i18n.t("status.selection", characters) if lines <= 1 else i18n.t("status.selection_lines", characters, lines)
        else:
            text = ""
        self.selection_label.setText(text)

    def set_document_info(self, language, encoding, eol, indent, zoom):
        self.language_button.setText(language)
        self.encoding_button.setText(encoding)
        self.eol_button.setText(eol)
        self.indent_button.setText(indent)
        self.zoom_button.setText(f"{zoom}%")

    def show_message(self, text, milliseconds=3500):
        self.message_label.setText(text)
        self.message_timer.start(milliseconds)
