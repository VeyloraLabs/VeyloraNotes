from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtWidgets import QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import ComboBox, PrimaryPushButton, PushButton, SwitchButton

from .. import __version__, i18n
from ..icons import app_icon
from ..theme import ACCENT, BORDER, CARD, MUTED, TEXT

REPOSITORY_URL = "https://github.com/VeyloraLabs/VeyloraNotes"


class SettingsDialog(QDialog):
    check_updates_requested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.resize(680, 700)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 14)
        self.scroll = None
        self.build()

    def build(self):
        if self.scroll is not None:
            self.outer.removeWidget(self.scroll)
            self.scroll.deleteLater()
            footer = getattr(self, "footer", None)
            if footer is not None:
                self.outer.removeWidget(footer)
                footer.deleteLater()
        t = i18n.t
        self.setWindowTitle(t("settings.title"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(26, 22, 26, 10)
        self.body.setSpacing(6)
        self.scroll.setWidget(content)
        self.outer.insertWidget(0, self.scroll, 1)

        self.heading(t("settings.general"))
        language = ComboBox()
        language.addItems([i18n.LANGUAGE_NAMES[code] for code in ("es", "en")])
        language.setCurrentIndex(0 if i18n.language() == "es" else 1)
        language.currentIndexChanged.connect(self.change_language)
        self.row(t("settings.language"), language)
        self.folder_label = QLabel(str(self.settings.notes_dir()))
        self.folder_label.setStyleSheet(f"color: {MUTED};")
        choose = PushButton(t("settings.change"))
        choose.clicked.connect(self.choose_folder)
        self.row(t("settings.notes_folder"), choose, t("settings.notes_folder_hint"), extra=self.folder_label)
        self.switch("restore_session", t("settings.restore_session"), t("settings.restore_session_hint"))
        self.switch("check_updates", t("settings.check_updates"), t("settings.check_updates_hint"))
        default_language = ComboBox()
        default_language.addItems([t("language.plain"), "Markdown"])
        default_language.setCurrentIndex(1 if self.settings.get("default_language") == "markdown" else 0)
        default_language.currentIndexChanged.connect(
            lambda index: self.settings.set("default_language", "markdown" if index == 1 else "plain")
        )
        self.row(t("settings.default_language"), default_language, t("settings.default_language_hint"))

        self.heading(t("settings.editor"))
        fonts = sorted({family for family in QFontDatabase.families() if QFontDatabase.isFixedPitch(family)})
        current_font = self.settings.get("font_family")
        if current_font not in fonts:
            fonts.insert(0, current_font)
        font_box = ComboBox()
        font_box.addItems(fonts)
        font_box.setCurrentText(current_font)
        font_box.currentTextChanged.connect(lambda text: self.settings.set("font_family", text))
        self.row(t("settings.font"), font_box)
        self.number_choice("font_size", t("settings.font_size"), list(range(8, 29)) + [32, 36, 40])
        self.number_choice("tab_width", t("settings.tab_width"), [1, 2, 3, 4, 6, 8])
        self.switch("use_spaces", t("settings.use_spaces"))
        self.switch("word_wrap", t("settings.word_wrap"))
        self.switch("line_numbers", t("settings.line_numbers"))
        self.switch("highlight_line", t("settings.highlight_line"))
        self.switch("show_whitespace", t("settings.show_whitespace"))
        self.switch("auto_indent", t("settings.auto_indent"))
        self.switch("list_continuation", t("settings.list_continuation"), t("settings.list_continuation_hint"))

        self.heading(t("settings.preview"))
        theme = ComboBox()
        theme.addItems([t("settings.theme_dark"), t("settings.theme_light")])
        theme.setCurrentIndex(0 if self.settings.get("preview_theme") == "dark" else 1)
        theme.currentIndexChanged.connect(lambda index: self.settings.set("preview_theme", "dark" if index == 0 else "light"))
        self.row(t("settings.preview_theme"), theme)
        self.switch("remote_images", t("settings.remote_images"), t("settings.remote_images_hint"))
        self.switch("sync_scroll", t("settings.sync_scroll"))

        self.heading(t("settings.about"))
        self.about_block()
        self.body.addStretch(1)

        self.footer = QWidget()
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(26, 0, 26, 0)
        footer_layout.addStretch(1)
        done = PrimaryPushButton(t("common.close"))
        done.clicked.connect(self.accept)
        footer_layout.addWidget(done)
        self.outer.addWidget(self.footer)

    def heading(self, text):
        label = QLabel(text.upper())
        label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; padding-top: 18px; padding-bottom: 4px;")
        self.body.addWidget(label)

    def row(self, title, control, description=None, extra=None):
        frame = QFrame()
        frame.setStyleSheet(f"QFrame#settingRow {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}")
        frame.setObjectName("settingRow")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(title)
        name.setStyleSheet(f"color: {TEXT}; border: none;")
        text.addWidget(name)
        if description:
            hint = QLabel(description)
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {MUTED}; font-size: 11px; border: none;")
            text.addWidget(hint)
        if extra is not None:
            extra.setStyleSheet(f"color: {MUTED}; font-size: 11px; border: none;")
            extra.setWordWrap(True)
            text.addWidget(extra)
        layout.addLayout(text, 1)
        layout.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.body.addWidget(frame)

    def switch(self, key, title, description=None):
        button = SwitchButton()
        button.setOnText(i18n.t("common.on"))
        button.setOffText(i18n.t("common.off"))
        button.setChecked(self.settings.get(key))
        button.checkedChanged.connect(lambda checked: self.settings.set(key, checked))
        self.row(title, button, description)

    def number_choice(self, key, title, values):
        box = ComboBox()
        box.addItems([str(value) for value in values])
        current = self.settings.get(key)
        box.setCurrentText(str(current) if current in values else str(values[0]))
        box.currentTextChanged.connect(lambda text: self.settings.set(key, int(text)))
        self.row(title, box)

    def change_language(self, index):
        code = "es" if index == 0 else "en"
        self.settings.set("language", code)
        i18n.set_language(code)
        self.build()

    def choose_folder(self):
        selected = QFileDialog.getExistingDirectory(self, i18n.t("settings.notes_folder"), str(self.settings.notes_dir()))
        if selected:
            self.settings.set("notes_dir", selected)
            self.folder_label.setText(selected)

    def about_block(self):
        t = i18n.t
        frame = QFrame()
        frame.setObjectName("settingRow")
        frame.setStyleSheet(f"QFrame#settingRow {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(56, 56))
        logo.setStyleSheet("border: none;")
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("VeyloraNotes")
        title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 700; border: none;")
        version = QLabel(t("about.version", __version__))
        version.setStyleSheet(f"color: {MUTED}; border: none;")
        title_box.addWidget(title)
        title_box.addWidget(version)
        top.addWidget(logo)
        top.addSpacing(10)
        top.addLayout(title_box)
        top.addStretch(1)
        layout.addLayout(top)
        made = QLabel(t("about.made_with"))
        made.setStyleSheet(f"color: {ACCENT}; font-weight: 700; border: none;")
        layout.addWidget(made)
        description = QLabel(t("about.description"))
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {MUTED}; border: none;")
        layout.addWidget(description)
        buttons = QHBoxLayout()
        github = PushButton("GitHub")
        github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPOSITORY_URL)))
        updates = PushButton(t("about.check_updates"))
        updates.clicked.connect(self.check_updates_requested.emit)
        buttons.addWidget(github)
        buttons.addWidget(updates)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.body.addWidget(frame)
