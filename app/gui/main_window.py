import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, InfoBarPosition, PushButton

from .. import __version__, i18n
from ..core import markdown_tools
from ..core.document_io import ENCODINGS, EOL_NAMES, BinaryFileError, encoding_label
from ..core.languages import LANGUAGES, language_by_id
from ..core.session import SessionStore
from ..icons import app_icon, icon
from ..paths import cache_dir, data_dir
from ..theme import ACCENT, BG, BORDER, CARD, EDITOR_BG, HOVER, MUTED, TEXT, WARNING
from ..update import UpdateChecker
from .command_palette import CommandPalette, PaletteEntry
from .commands import MENU_LAYOUT, register_commands
from .dialogs import ShortcutsDialog
from .document_view import DocumentView
from .find_bar import FindBar
from .preview import ImageStore
from .settings_dialog import SettingsDialog
from .sidebar import Sidebar
from .status_bar import StatusBar
from .tool_actions import ToolActions
from .ui import separator

SESSION_INTERVAL_MS = 5000
TAB_ROW_HEIGHT = 42
DEFAULT_EXTENSIONS = {"markdown": ".md"}
SIDEBAR_KEYS = ("files", "outline", "search")
TOOLBAR_GROUPS = (
    ("file.new", "file.open", "file.save"),
    ("edit.undo", "edit.redo"),
    ("edit.find", "view.word_wrap"),
)
MARKDOWN_TOOLBAR = (
    "markdown.bold", "markdown.italic", "markdown.h2", "markdown.bullets", "markdown.task",
    "markdown.code", "markdown.link", "markdown.image", "markdown.table",
)


class TabCloseButton(QToolButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setIconSize(QSize(10, 10))
        self.modified = False
        self.hovered = False
        self.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 0; }}"
            f"QToolButton:hover {{ background: {HOVER}; }}"
        )
        self.refresh()

    def set_modified(self, modified):
        self.modified = modified
        self.refresh()

    def refresh(self):
        if self.modified and not self.hovered:
            self.setIcon(icon("fa5s.circle", WARNING, WARNING))
        else:
            self.setIcon(icon("fa5s.times", MUTED, TEXT))

    def enterEvent(self, event):
        self.hovered = True
        self.refresh()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.refresh()
        super().leaveEvent(event)


class MainWindow(ToolActions, QMainWindow):
    def __init__(self, settings, initial_paths=()):
        super().__init__()
        self.settings = settings
        i18n.set_language(settings.get("language"))
        self.image_store = ImageStore(cache_dir())
        self.session = SessionStore(data_dir() / "session")
        self.updater = UpdateChecker(self)
        self.views = []
        self.session_dirty = False
        self.closing = False
        self.focus_mode = False
        self.manual_update_check = False
        self.setWindowTitle("VeyloraNotes")
        self.setWindowIcon(app_icon())
        self.setAcceptDrops(True)
        self.resize(1320, 840)
        self.setMinimumSize(900, 560)

        self.registry = register_commands(self)
        self.build_ui()
        self.build_menus()
        self.connect_signals()
        self.retranslate()
        self.restore_geometry()
        self.sync_setting_actions()

        opened = False
        for path in initial_paths:
            opened = bool(self.open_path(path)) or opened
        if not opened and self.settings.get("restore_session"):
            self.restore_session()
        if not self.views:
            if not self.settings.get("welcome_shown"):
                self.show_welcome()
                self.settings.set("welcome_shown", True)
            else:
                self.new_document()
        self.on_tab_changed(self.tab_bar.currentIndex())
        QTimer.singleShot(4000, self.startup_update_check)

    def startup_update_check(self):
        if self.settings.get("check_updates"):
            self.check_updates(False)

    def build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(f"QWidget#central {{ background: {BG}; }}")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 8, 12, 2)
        header_layout.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(26, 26))
        header_layout.addWidget(logo)
        self.menu_bar = QMenuBar()
        self.menu_bar.setNativeMenuBar(False)
        header_layout.addWidget(self.menu_bar)
        header_layout.addStretch(1)
        self.palette_button = QPushButton()
        self.palette_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.palette_button.setIcon(icon("fa5s.bolt", ACCENT, ACCENT))
        self.palette_button.setMinimumWidth(300)
        self.palette_button.setStyleSheet(
            f"QPushButton {{ text-align: left; color: {MUTED}; background: {CARD}; border: 1px solid {BORDER}; "
            f"border-radius: 9px; padding: 6px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; color: {TEXT}; }}"
        )
        header_layout.addWidget(self.palette_button)
        self.settings_button = QToolButton()
        self.settings_button.setIcon(icon("fa5s.cog"))
        self.settings_button.setFixedSize(34, 34)
        self.settings_button.setIconSize(QSize(16, 16))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.settings_button)
        root.addWidget(self.header)

        self.toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(14, 4, 14, 4)
        toolbar_layout.setSpacing(2)
        for index, group in enumerate(TOOLBAR_GROUPS):
            if index:
                toolbar_layout.addSpacing(4)
                toolbar_layout.addWidget(separator())
                toolbar_layout.addSpacing(4)
            for command_id in group:
                toolbar_layout.addWidget(self.toolbar_button(command_id))
        self.markdown_toolbar = QWidget()
        markdown_layout = QHBoxLayout(self.markdown_toolbar)
        markdown_layout.setContentsMargins(0, 0, 0, 0)
        markdown_layout.setSpacing(2)
        markdown_layout.addSpacing(4)
        markdown_layout.addWidget(separator())
        markdown_layout.addSpacing(4)
        for command_id in MARKDOWN_TOOLBAR:
            markdown_layout.addWidget(self.toolbar_button(command_id))
        toolbar_layout.addWidget(self.markdown_toolbar)
        toolbar_layout.addStretch(1)
        self.tools_button = QToolButton()
        self.tools_button.setIcon(icon("fa5s.magic", ACCENT, ACCENT))
        self.tools_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tools_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.tools_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tools_button.setFixedHeight(32)
        self.tools_button.setStyleSheet("QToolButton { padding: 4px 12px; }")
        toolbar_layout.addWidget(self.tools_button)
        toolbar_layout.addSpacing(6)
        toolbar_layout.addWidget(separator())
        toolbar_layout.addSpacing(6)
        for command_id in ("view.mode_editor", "view.mode_split", "view.mode_preview"):
            toolbar_layout.addWidget(self.toolbar_button(command_id))
        toolbar_layout.addSpacing(4)
        toolbar_layout.addWidget(self.toolbar_button("view.sidebar"))
        root.addWidget(self.toolbar)

        self.tab_row = QWidget()
        tab_layout = QHBoxLayout(self.tab_row)
        tab_layout.setContentsMargins(0, 0, 14, 0)
        tab_layout.setSpacing(4)
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("documentTabs")
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.setFixedHeight(TAB_ROW_HEIGHT)
        self.tab_row.setFixedHeight(TAB_ROW_HEIGHT)
        tab_layout.addWidget(self.tab_bar, 0)
        self.new_tab_button = QToolButton()
        self.new_tab_button.setDefaultAction(self.registry.action("file.new"))
        self.new_tab_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.new_tab_button.setFixedSize(30, 30)
        self.new_tab_button.setIconSize(QSize(13, 13))
        self.new_tab_button.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_layout.addWidget(self.new_tab_button, 0, Qt.AlignmentFlag.AlignBottom)
        tab_layout.addStretch(1)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.sidebar = Sidebar(self.settings)
        self.splitter.addWidget(self.sidebar)
        editor_area = QWidget()
        area_layout = QVBoxLayout(editor_area)
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)
        area_layout.addWidget(self.tab_row)
        self.find_bar = FindBar()
        self.find_holder = QWidget()
        find_layout = QHBoxLayout(self.find_holder)
        find_layout.setContentsMargins(14, 0, 14, 8)
        find_layout.addWidget(self.find_bar)
        find_layout.addStretch(1)
        self.find_holder.setVisible(False)
        area_layout.addWidget(self.find_holder)
        frame = QFrame()
        frame.setObjectName("editorFrame")
        frame.setStyleSheet(f"QFrame#editorFrame {{ background: {EDITOR_BG}; border: 1px solid {BORDER}; border-radius: 0; }}")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        frame_layout.addWidget(self.stack)
        frame_holder = QWidget()
        holder_layout = QVBoxLayout(frame_holder)
        holder_layout.setContentsMargins(14, 0, 14, 10)
        holder_layout.addWidget(frame)
        area_layout.addWidget(frame_holder, 1)
        self.splitter.addWidget(editor_area)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([self.settings.get("sidebar_width"), 1000])
        root.addWidget(self.splitter, 1)

        self.status = StatusBar()
        root.addWidget(self.status)
        self.palette = CommandPalette(self)
        self.sidebar.setVisible(self.settings.get("sidebar_visible"))
        self.sidebar.show_panel(SIDEBAR_KEYS[max(0, min(2, self.settings.get("sidebar_tab")))])

        self.session_timer = QTimer(self)
        self.session_timer.setInterval(SESSION_INTERVAL_MS)
        self.session_timer.timeout.connect(self.flush_session)
        self.session_timer.start()
        self.outline_timer = QTimer(self)
        self.outline_timer.setSingleShot(True)
        self.outline_timer.setInterval(450)
        self.outline_timer.timeout.connect(self.refresh_outline)

    def toolbar_button(self, command_id):
        button = QToolButton()
        button.setDefaultAction(self.registry.action(command_id))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFixedSize(32, 32)
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def build_menus(self):
        self.menus = {}
        self.recent_menu = None
        for key, items in MENU_LAYOUT:
            menu = self.registry.menu(key, self.menu_bar)
            self.menus[key] = menu
            self.fill_menu(menu, items)
            self.menu_bar.addMenu(menu)
        self.tools_button.setMenu(self.menus["menu.text"])
        if self.recent_menu is not None:
            self.recent_menu.aboutToShow.connect(self.populate_recent_menu)

    def fill_menu(self, menu, items):
        for item in items:
            if item is None:
                menu.addSeparator()
            elif isinstance(item, str):
                menu.addAction(self.registry.action(item))
            else:
                key, children = item
                submenu = self.registry.menu(key, menu)
                menu.addMenu(submenu)
                if children == ["__recent__"]:
                    self.recent_menu = submenu
                else:
                    self.fill_menu(submenu, children)

    def populate_recent_menu(self):
        self.recent_menu.clear()
        files = [path for path in self.settings.recent_files() if path.exists()]
        for path in files:
            action = self.recent_menu.addAction(path.name)
            action.setToolTip(str(path))
            action.triggered.connect(lambda _=False, target=path: self.open_path(target))
        if files:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction(self.registry.action("file.clear_recent"))
        else:
            empty = self.recent_menu.addAction(i18n.t("menu.recent_empty"))
            empty.setEnabled(False)

    def connect_signals(self):
        self.tab_bar.currentChanged.connect(self.on_tab_changed)
        self.tab_bar.tabMoved.connect(self.on_tab_moved)
        self.tab_bar.customContextMenuRequested.connect(self.show_tab_menu)
        self.palette_button.clicked.connect(self.open_palette)
        self.settings_button.clicked.connect(lambda: self.show_settings())
        self.find_bar.closed.connect(lambda: self.find_holder.setVisible(False))
        self.find_bar.message.connect(self.show_message)
        self.status.language_clicked.connect(self.show_language_menu)
        self.status.encoding_clicked.connect(self.show_encoding_menu)
        self.status.eol_clicked.connect(self.show_eol_menu)
        self.status.indent_clicked.connect(self.show_indent_menu)
        self.status.zoom_clicked.connect(lambda: self.zoom(0))
        self.status.position_clicked.connect(self.go_to_line_dialog)
        self.sidebar.files.file_activated.connect(self.open_path)
        self.sidebar.files.file_renamed.connect(self.on_file_renamed)
        self.sidebar.files.file_deleted.connect(self.on_file_deleted)
        self.sidebar.files.folder_changed.connect(self.choose_notes_folder)
        self.sidebar.outline.jump_requested.connect(self.jump_to_line)
        self.sidebar.search.result_activated.connect(self.open_search_result)
        self.sidebar.tabs.currentItemChanged.connect(self.remember_sidebar_tab)
        self.settings.changed.connect(self.on_setting_changed)
        i18n.notifier.changed.connect(lambda _: self.retranslate())
        self.updater.update_available.connect(self.on_update_available)
        self.updater.up_to_date.connect(self.on_up_to_date)
        self.updater.failed.connect(self.on_update_failed)
        QApplication.instance().applicationStateChanged.connect(self.on_application_state)

    def retranslate(self):
        t = i18n.t
        self.registry.retranslate()
        self.tools_button.setText(t("toolbar.tools"))
        self.palette_button.setText("  " + t("header.palette", self.registry.commands["help.palette"].shortcut_text()))
        self.settings_button.setToolTip(t("cmd.help.settings"))
        self.status.retranslate()
        self.sidebar.retranslate()
        self.find_bar.retranslate()
        for view in self.views:
            self.update_tab(view)
            view.preview.refresh_theme()
        self.refresh_status()
        self.update_window_title()

    def sync_setting_actions(self):
        for key, command in (("word_wrap", "view.word_wrap"), ("line_numbers", "view.line_numbers"), ("show_whitespace", "view.whitespace")):
            self.registry.set_checked(command, self.settings.get(key))
        self.registry.set_checked("view.sidebar", self.sidebar.isVisible())

    def restore_geometry(self):
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def current_view(self):
        index = self.tab_bar.currentIndex()
        return self.views[index] if 0 <= index < len(self.views) else None

    def current_editor(self):
        view = self.current_view()
        return view.editor if view else None

    def editor_call(self, name, *arguments):
        editor = self.current_editor()
        if editor is None or not editor.isVisible():
            return None
        return getattr(editor, name)(*arguments)

    def next_untitled_number(self):
        used = {view.title_key[1] for view in self.views if view.title_key[:1] == ("doc.untitled",)}
        number = 1
        while number in used:
            number += 1
        return number

    def new_document(self, text="", title_key=None, language=None, view_mode="editor"):
        view = DocumentView(self.settings, self.image_store)
        view.title_key = title_key or ("doc.untitled", self.next_untitled_number())
        if language is not None:
            view.apply_language(language_by_id(language), manual=True)
        if text:
            view.set_text(text, modified=title_key != ("doc.welcome",))
        self.add_view(view)
        if view_mode != "editor":
            view.set_view_mode(view_mode)
            self.update_mode_actions()
        view.editor.setFocus()
        return view

    def add_view(self, view):
        self.views.append(view)
        self.stack.addWidget(view)
        index = self.tab_bar.addTab(view.display_name())
        button = TabCloseButton()
        button.clicked.connect(lambda _=False, target=view: self.close_view(target))
        self.tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)
        view.close_button = button
        view.modification_changed.connect(self.on_modification_changed)
        view.title_changed.connect(self.update_tab)
        view.cursor_changed.connect(self.on_cursor_changed)
        view.language_changed.connect(self.on_language_changed)
        view.text_edited.connect(self.on_text_edited)
        view.document_requested.connect(self.open_document_from_preview)
        editor = view.editor
        editor.reserved_shortcuts = self.registry.reserved_shortcuts()
        editor.files_dropped.connect(self.open_paths)
        editor.image_pasted.connect(self.markdown_paste_image)
        editor.context_menu_requested.connect(self.extend_context_menu)
        editor.zoom_changed.connect(lambda _: self.refresh_status())
        editor.escape_pressed.connect(self.on_escape)
        self.update_tab(view)
        self.tab_bar.setCurrentIndex(index)
        self.session_dirty = True
        QTimer.singleShot(0, self.fit_tab_bar)

    def view_for_path(self, path):
        try:
            target = Path(path).resolve()
        except OSError:
            target = Path(path)
        for view in self.views:
            if view.path is not None:
                try:
                    if view.path.resolve() == target:
                        return view
                except OSError:
                    continue
        return None

    def is_pristine(self, view):
        return view.path is None and not view.is_modified() and view.editor.document().isEmpty()

    def open_paths(self, paths):
        for path in paths:
            self.open_path(path)

    def open_path(self, path, line=None, column=None, length=None):
        target = Path(path).expanduser()
        existing = self.view_for_path(target)
        if existing is not None:
            self.tab_bar.setCurrentIndex(self.views.index(existing))
            self.reveal_position(existing, line, column, length)
            return existing
        if target.is_dir():
            self.settings.set("notes_dir", str(target))
            return None
        if not target.exists():
            self.notify("error", i18n.t("file.not_found", target.name))
            return None
        view = DocumentView(self.settings, self.image_store)
        try:
            view.load_file(target)
        except BinaryFileError:
            answer = QMessageBox.question(
                self, i18n.t("app.name"), i18n.t("file.binary", target.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                view.deleteLater()
                return None
            try:
                view.load_file(target, allow_binary=True)
            except OSError as error:
                self.notify("error", str(error))
                view.deleteLater()
                return None
        except OSError as error:
            self.notify("error", i18n.t("file.open_failed", target.name, str(error)))
            view.deleteLater()
            return None
        pristine = [candidate for candidate in self.views if self.is_pristine(candidate)]
        self.add_view(view)
        for candidate in pristine:
            self.close_view(candidate, force=True)
        self.settings.add_recent_file(target)
        self.reveal_position(view, line, column, length)
        return view

    def reveal_position(self, view, line, column, length):
        if line:
            view.editor.go_to_line(line, (column or 0) + 1)
            if length:
                cursor = view.editor.textCursor()
                cursor.setPosition(cursor.position() + length, QTextCursor.MoveMode.KeepAnchor)
                view.editor.setTextCursor(cursor)
        view.editor.setFocus()

    def open_search_result(self, path, line, column, length):
        self.open_path(path, line or None, column, length)

    def open_document_from_preview(self, path, fragment):
        view = self.open_path(path)
        if view is not None and fragment:
            QTimer.singleShot(150, lambda: view.preview.scrollToAnchor(fragment))

    def open_file_dialog(self):
        view = self.current_view()
        start = str(view.path.parent) if view and view.path else str(self.settings.notes_dir())
        paths, _ = QFileDialog.getOpenFileNames(self, i18n.t("cmd.file.open"), start, i18n.t("filter.open"))
        self.open_paths(paths)

    def choose_notes_folder(self):
        selected = QFileDialog.getExistingDirectory(self, i18n.t("settings.notes_folder"), str(self.settings.notes_dir()))
        if selected:
            self.settings.set("notes_dir", selected)

    def clear_recent(self):
        self.settings.clear_recent_files()

    def open_today_note(self):
        today = datetime.now()
        folder = self.settings.notes_dir() / i18n.t("diary.folder")
        target = folder / f"{today:%Y-%m-%d}.md"
        if not target.exists():
            weekdays = i18n.t("date.weekdays").split(",")
            months = i18n.t("date.months").split(",")
            heading = i18n.t(
                "date.format", weekday=weekdays[today.weekday()], day=today.day, month=months[today.month - 1], year=today.year
            )
            try:
                folder.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# {heading}\n\n", encoding="utf-8")
            except OSError as error:
                self.notify("error", str(error))
                return
        view = self.open_path(target)
        if view is not None:
            view.editor.moveCursor(QTextCursor.MoveOperation.End)
            view.editor.setFocus()

    def show_welcome(self):
        self.new_document(i18n.t("welcome.text"), title_key=("doc.welcome",), language="markdown", view_mode="split")

    def default_extension(self, view):
        return DEFAULT_EXTENSIONS.get(view.language.id, ".txt")

    def save_current(self):
        view = self.current_view()
        return self.save_view(view) if view else False

    def save_current_as(self):
        view = self.current_view()
        return self.save_view_as(view) if view else False

    def save_view(self, view):
        if view.path is None:
            return self.save_view_as(view)
        return self.write_view(view, view.path)

    def save_view_as(self, view):
        if view.path is not None:
            start = view.path
        else:
            stem = re.sub(r'[<>:"/\\|?*]', "", view.display_name()).strip() or "note"
            start = self.settings.notes_dir() / f"{stem}{self.default_extension(view)}"
        selected, _ = QFileDialog.getSaveFileName(self, i18n.t("cmd.file.save_as"), str(start), i18n.t("filter.save"))
        if not selected:
            return False
        target = Path(selected)
        if not target.suffix:
            target = target.with_suffix(self.default_extension(view))
        return self.write_view(view, target)

    def write_view(self, view, target):
        try:
            view.save(target)
        except OSError as error:
            QMessageBox.critical(self, i18n.t("app.name"), i18n.t("file.save_failed", Path(target).name, str(error)))
            return False
        self.settings.add_recent_file(target)
        self.show_message(i18n.t("status.saved_file", Path(target).name))
        self.session_dirty = True
        return True

    def save_all(self):
        for view in list(self.views):
            if view.is_modified() and not self.save_view(view):
                break

    def ask_discard_changes(self, view):
        answer = QMessageBox.question(
            self, i18n.t("app.name"), i18n.t("file.reload_confirm", view.display_name()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def reload_current(self):
        view = self.current_view()
        if view is None or view.path is None:
            return
        if view.is_modified() and not self.ask_discard_changes(view):
            return
        try:
            view.reload_from_disk()
        except (OSError, BinaryFileError) as error:
            self.notify("error", str(error))

    def reveal_current(self):
        view = self.current_view()
        if view is not None and view.path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(view.path.parent)))

    def copy_current_path(self):
        view = self.current_view()
        if view is not None and view.path is not None:
            QGuiApplication.clipboard().setText(str(view.path))
            self.show_message(i18n.t("status.path_copied"))

    def confirm_close(self, view):
        if not view.is_modified():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(i18n.t("app.name"))
        box.setText(i18n.t("close.prompt", view.display_name()))
        save = box.addButton(i18n.t("close.save"), QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(i18n.t("close.discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(i18n.t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self.save_view(view)
        return clicked is discard

    def close_view(self, view, force=False):
        if view not in self.views:
            return False
        if not force and not self.confirm_close(view):
            return False
        index = self.views.index(view)
        self.views.pop(index)
        self.tab_bar.removeTab(index)
        self.stack.removeWidget(view)
        view.deleteLater()
        self.session_dirty = True
        QTimer.singleShot(0, self.fit_tab_bar)
        if not self.views:
            self.new_document()
        return True

    def close_current(self):
        view = self.current_view()
        if view:
            self.close_view(view)

    def close_others(self):
        keep = self.current_view()
        for view in list(self.views):
            if view is not keep and not self.close_view(view):
                break

    def close_all_tabs(self):
        for view in list(self.views):
            if not self.close_view(view):
                break

    def close_to_right(self, index):
        for view in list(self.views[index + 1:]):
            if not self.close_view(view):
                break

    def step_tab(self, delta):
        count = len(self.views)
        if count > 1:
            self.tab_bar.setCurrentIndex((self.tab_bar.currentIndex() + delta) % count)

    def show_tab_menu(self, position):
        index = self.tab_bar.tabAt(position)
        if index < 0:
            return
        view = self.views[index]
        menu = QMenu(self)
        menu.addAction(icon("fa5s.save"), i18n.t("cmd.file.save"), lambda: self.save_view(view))
        menu.addSeparator()
        menu.addAction(icon("fa5s.times"), i18n.t("cmd.file.close"), lambda: self.close_view(view))
        menu.addAction(i18n.t("cmd.file.close_others"), lambda: (self.tab_bar.setCurrentIndex(index), self.close_others()))
        menu.addAction(i18n.t("tabs.close_right"), lambda: self.close_to_right(index))
        if view.path is not None:
            menu.addSeparator()
            menu.addAction(icon("fa5s.copy"), i18n.t("cmd.file.copy_path"), lambda: QGuiApplication.clipboard().setText(str(view.path)))
            menu.addAction(
                icon("fa5s.external-link-alt"), i18n.t("cmd.file.reveal"),
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(view.path.parent))),
            )
        menu.exec(self.tab_bar.mapToGlobal(position))

    def fit_tab_bar(self):
        available = self.tab_row.width() - self.new_tab_button.width() - 24
        width = min(self.tab_bar.sizeHint().width() + 2, max(140, available))
        if self.tab_bar.width() != width:
            self.tab_bar.setFixedWidth(width)

    def on_tab_moved(self, source, target):
        self.views.insert(target, self.views.pop(source))
        self.session_dirty = True

    def on_tab_changed(self, index):
        view = self.views[index] if 0 <= index < len(self.views) else None
        if view is None:
            self.find_bar.attach(None)
            return
        self.stack.setCurrentWidget(view)
        self.find_bar.attach(view.editor)
        self.refresh_outline()
        self.update_mode_actions()
        self.markdown_toolbar.setVisible(view.language.id == "markdown")
        self.refresh_status()
        self.update_window_title()
        self.session_dirty = True
        if self.isActiveWindow():
            (view.preview if view.view_mode == "preview" else view.editor).setFocus()
        self.check_external_change(view)

    def update_tab(self, view):
        if view not in self.views:
            return
        index = self.views.index(view)
        name = view.display_name()
        self.tab_bar.setTabText(index, name)
        self.tab_bar.setTabToolTip(index, str(view.path) if view.path else name)
        view.close_button.set_modified(view.is_modified())
        QTimer.singleShot(0, self.fit_tab_bar)
        if view is self.current_view():
            self.update_window_title()

    def update_window_title(self):
        view = self.current_view()
        if view is None:
            self.setWindowTitle("VeyloraNotes")
            return
        marker = "● " if view.is_modified() else ""
        self.setWindowTitle(f"{marker}{view.display_name()} — VeyloraNotes")

    def on_modification_changed(self, view):
        self.update_tab(view)
        if view is self.current_view():
            self.refresh_status()
        self.session_dirty = True

    def on_text_edited(self, view):
        self.session_dirty = True
        if view is self.current_view() and view.language.id == "markdown":
            self.outline_timer.start()

    def on_cursor_changed(self, view):
        if view is self.current_view():
            self.refresh_status()

    def on_language_changed(self, view):
        if view is self.current_view():
            self.markdown_toolbar.setVisible(view.language.id == "markdown")
            self.refresh_outline()
            self.refresh_status()

    def language_label(self, language):
        return i18n.t("language.plain") if language.id == "plain" else language.name

    def refresh_status(self):
        view = self.current_view()
        if view is None:
            return
        editor = view.editor
        line, column = editor.cursor_line_column()
        self.status.set_position(line, column, editor.document().blockCount())
        cursor = editor.textCursor()
        selected = cursor.selectionEnd() - cursor.selectionStart()
        selected_lines = editor.selected_text().count("\n") + 1 if selected else 0
        self.status.set_selection(selected, selected_lines)
        indent = i18n.t("status.spaces", editor.tab_width) if editor.use_spaces else i18n.t("status.tabs", editor.tab_width)
        self.status.set_document_info(
            self.language_label(view.language), encoding_label(view.encoding), EOL_NAMES[view.eol], indent, editor.zoom_percent()
        )
        self.status.set_saved(not view.is_modified())

    def refresh_outline(self):
        view = self.current_view()
        if view is None or view.language.id != "markdown":
            self.sidebar.outline.set_headings([])
            return
        self.sidebar.outline.set_headings(markdown_tools.extract_headings(view.text()))

    def jump_to_line(self, line):
        editor = self.current_editor()
        if editor is not None:
            editor.go_to_line(line)

    def update_mode_actions(self):
        view = self.current_view()
        if view is not None:
            self.registry.set_checked(f"view.mode_{view.view_mode}", True)

    def set_view_mode(self, mode, _checked=None):
        view = self.current_view()
        if view is None:
            return
        view.set_view_mode(mode)
        self.update_mode_actions()
        self.session_dirty = True

    def cycle_preview(self):
        view = self.current_view()
        if view is None:
            return
        order = ("editor", "split", "preview")
        self.set_view_mode(order[(order.index(view.view_mode) + 1) % 3])

    def toggle_setting(self, key, checked=None):
        self.settings.set(key, bool(checked) if checked is not None else not self.settings.get(key))

    def toggle_sidebar(self, checked=None):
        visible = (not self.sidebar.isVisible()) if checked is None else bool(checked)
        self.sidebar.setVisible(visible)
        self.settings.set("sidebar_visible", visible)
        self.registry.set_checked("view.sidebar", visible)

    def show_sidebar_panel(self, key):
        if not self.sidebar.isVisible():
            self.toggle_sidebar(True)
        self.sidebar.show_panel(key)

    def remember_sidebar_tab(self, key):
        if key in SIDEBAR_KEYS:
            self.settings.set("sidebar_tab", SIDEBAR_KEYS.index(key))

    def search_in_folder(self):
        editor = self.current_editor()
        selected = editor.selected_text() if editor else ""
        self.show_sidebar_panel("search")
        self.sidebar.search.focus_input(selected if selected and "\n" not in selected else "")

    def zoom(self, delta):
        editor = self.current_editor()
        if editor is None:
            return
        if delta == 0:
            editor.reset_zoom()
        elif delta > 0:
            editor.zoom_in()
        else:
            editor.zoom_out()

    def toggle_fullscreen(self, checked=None):
        full = (not self.isFullScreen()) if checked is None else bool(checked)
        if full:
            self.showFullScreen()
        else:
            self.showNormal()
        self.registry.set_checked("view.fullscreen", full)

    def toggle_focus_mode(self, checked=None):
        self.focus_mode = (not self.focus_mode) if checked is None else bool(checked)
        visible = not self.focus_mode
        for widget in (self.header, self.toolbar, self.tab_row, self.status):
            widget.setVisible(visible)
        self.sidebar.setVisible(visible and self.settings.get("sidebar_visible"))
        self.registry.set_checked("view.focus_mode", self.focus_mode)

    def open_find(self, replace=False):
        editor = self.current_editor()
        if editor is None:
            return
        self.find_bar.attach(editor)
        self.find_holder.setVisible(True)
        self.find_bar.open_bar(bool(replace))

    def find_step(self, forward):
        if not self.find_bar.find_input.text():
            self.open_find()
            return
        self.find_bar.attach(self.current_editor())
        self.find_bar.find_next(forward)

    def on_escape(self):
        if self.find_bar.isVisible():
            self.find_bar.close_bar()

    def extend_context_menu(self, menu):
        menu.addSeparator()
        menu.addAction(self.menus["menu.text"].menuAction())
        view = self.current_view()
        if view is not None and view.language.id == "markdown":
            menu.addAction(self.menus["menu.markdown"].menuAction())

    def palette_entries(self):
        entries = []
        for command in self.registry.commands.values():
            if command.id == "file.clear_recent":
                continue
            entries.append(
                PaletteEntry(
                    command.label(), i18n.t(command.category), command.action.trigger, command.shortcut_text(),
                    command.icon_name or "fa5s.bolt", command.keywords,
                )
            )
        entries.extend(self.file_entries(include_folder=False))
        return entries

    def file_entries(self, include_folder):
        entries = []
        seen = set()
        for view in self.views:
            entries.append(
                PaletteEntry(
                    view.display_name(), i18n.t("cat.tab"),
                    lambda target=view: self.tab_bar.setCurrentIndex(self.views.index(target)),
                    "", "fa5s.file-alt", str(view.path or ""),
                )
            )
            if view.path:
                seen.add(str(view.path))
        for path in self.settings.recent_files():
            if str(path) not in seen and path.exists():
                seen.add(str(path))
                entries.append(PaletteEntry(path.name, i18n.t("cat.recent"), lambda target=path: self.open_path(target), "", "fa5s.history", str(path)))
        if include_folder:
            root = self.settings.notes_dir()
            for path in self.sidebar.files.list_files():
                if str(path) in seen:
                    continue
                try:
                    relative = str(path.relative_to(root))
                except ValueError:
                    relative = str(path)
                entries.append(PaletteEntry(path.name, relative, lambda target=path: self.open_path(target), "", "fa5s.file", relative))
        return entries

    def open_palette(self):
        self.palette.open_palette(self.palette_entries(), line_callback=self.jump_to_line)

    def open_quick_open(self):
        self.palette.open_palette(self.file_entries(include_folder=True), line_callback=self.jump_to_line)

    def show_shortcuts(self):
        rows = sorted(self.registry.palette_rows(), key=lambda row: (row[0], row[1]))
        ShortcutsDialog(self, rows).exec()

    def show_settings(self, scroll_to_about=False):
        dialog = SettingsDialog(self.settings, self)
        dialog.check_updates_requested.connect(lambda: self.check_updates(True))
        if scroll_to_about:
            bar = dialog.scroll.verticalScrollBar()
            QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))
        dialog.exec()

    def show_about(self):
        self.show_settings(True)

    def on_setting_changed(self, key):
        if key == "language":
            i18n.set_language(self.settings.get("language"))
            return
        if key == "notes_dir":
            self.sidebar.files.set_root(self.settings.notes_dir())
            return
        if key in ("word_wrap", "line_numbers", "show_whitespace"):
            self.sync_setting_actions()
        if key in ("recent_files", "sidebar_visible", "sidebar_tab", "sidebar_width", "welcome_shown"):
            return
        for view in self.views:
            view.apply_settings()
        self.refresh_status()

    def show_language_menu(self):
        view = self.current_view()
        if view is None:
            return
        menu = QMenu(self)
        for language in LANGUAGES:
            action = menu.addAction(self.language_label(language))
            action.setCheckable(True)
            action.setChecked(language.id == view.language.id)
            action.triggered.connect(lambda _=False, chosen=language: view.apply_language(chosen, manual=True))
        self.popup_above(menu, self.status.language_button)

    def show_encoding_menu(self):
        view = self.current_view()
        if view is None:
            return
        menu = QMenu(self)
        save_menu = menu.addMenu(i18n.t("encoding.save_with"))
        for codec, label in ENCODINGS:
            action = save_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(codec == view.encoding)
            action.triggered.connect(lambda _=False, chosen=codec: self.set_encoding(view, chosen))
        reopen_menu = menu.addMenu(i18n.t("encoding.reopen_with"))
        reopen_menu.setEnabled(view.path is not None)
        for codec, label in ENCODINGS:
            action = reopen_menu.addAction(label)
            action.triggered.connect(lambda _=False, chosen=codec: self.reopen_with_encoding(view, chosen))
        self.popup_above(menu, self.status.encoding_button)

    def set_encoding(self, view, codec):
        if codec != view.encoding:
            view.encoding = codec
            view.editor.document().setModified(True)
            self.refresh_status()

    def reopen_with_encoding(self, view, codec):
        if view.is_modified() and not self.ask_discard_changes(view):
            return
        try:
            view.reload_from_disk(codec)
        except (OSError, BinaryFileError) as error:
            self.notify("error", str(error))

    def show_eol_menu(self):
        view = self.current_view()
        if view is None:
            return
        menu = QMenu(self)
        for eol, name in EOL_NAMES.items():
            action = menu.addAction(i18n.t(f"eol.{name}"))
            action.setCheckable(True)
            action.setChecked(eol == view.eol)
            action.triggered.connect(lambda _=False, chosen=eol: self.set_eol(view, chosen))
        self.popup_above(menu, self.status.eol_button)

    def set_eol(self, view, eol):
        if eol != view.eol:
            view.eol = eol
            view.editor.document().setModified(True)
            self.refresh_status()

    def show_indent_menu(self):
        menu = QMenu(self)
        spaces = menu.addAction(i18n.t("indent.spaces"))
        spaces.setCheckable(True)
        spaces.setChecked(self.settings.get("use_spaces"))
        spaces.triggered.connect(lambda: self.settings.set("use_spaces", True))
        tabs = menu.addAction(i18n.t("indent.tabs"))
        tabs.setCheckable(True)
        tabs.setChecked(not self.settings.get("use_spaces"))
        tabs.triggered.connect(lambda: self.settings.set("use_spaces", False))
        menu.addSeparator()
        for width in (2, 4, 8):
            action = menu.addAction(i18n.t("indent.width", width))
            action.setCheckable(True)
            action.setChecked(self.settings.get("tab_width") == width)
            action.triggered.connect(lambda _=False, value=width: self.settings.set("tab_width", value))
        self.popup_above(menu, self.status.indent_button)

    def popup_above(self, menu, button):
        height = menu.sizeHint().height()
        menu.exec(button.mapToGlobal(QPoint(0, -height - 4)))

    def check_updates(self, manual=False):
        self.manual_update_check = manual
        self.updater.check()

    def on_update_available(self, version, url):
        bar = InfoBar.info(
            i18n.t("update.title"), i18n.t("update.available", version), duration=12000,
            position=InfoBarPosition.TOP_RIGHT, parent=self,
        )
        button = PushButton(i18n.t("update.download"))
        button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        bar.addWidget(button)

    def on_up_to_date(self):
        if self.manual_update_check:
            self.notify("success", i18n.t("update.latest", __version__))

    def on_update_failed(self):
        if self.manual_update_check:
            self.notify("warning", i18n.t("update.failed"))

    def notify(self, kind, text):
        factory = {"success": InfoBar.success, "error": InfoBar.error, "warning": InfoBar.warning, "info": InfoBar.info}[kind]
        factory(
            i18n.t(f"notify.{kind}"), text, duration=7000 if kind == "error" else 4200,
            position=InfoBarPosition.TOP_RIGHT, parent=self,
        )

    def show_message(self, text):
        self.status.show_message(text)

    def on_application_state(self, state):
        if state == Qt.ApplicationState.ApplicationActive:
            QTimer.singleShot(200, self.check_external_changes)

    def check_external_changes(self):
        for view in list(self.views):
            self.check_external_change(view)

    def check_external_change(self, view):
        if view not in self.views or self.closing:
            return
        state = view.external_state()
        if state == "none":
            return
        if state == "deleted":
            view.signature = None
            view.editor.document().setModified(True)
            self.notify("warning", i18n.t("file.deleted_outside", view.display_name()))
            return
        if not view.is_modified():
            try:
                view.reload_from_disk()
                self.show_message(i18n.t("file.reloaded", view.display_name()))
            except (OSError, BinaryFileError):
                view.acknowledge_external_change()
            return
        answer = QMessageBox.question(
            self, i18n.t("app.name"), i18n.t("file.changed_outside", view.display_name()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                view.reload_from_disk()
            except (OSError, BinaryFileError) as error:
                self.notify("error", str(error))
        else:
            view.acknowledge_external_change()

    def on_file_renamed(self, old, new):
        view = self.view_for_path(old)
        if view is not None:
            view.path = Path(new)
            view.acknowledge_external_change()
            self.update_tab(view)

    def on_file_deleted(self, path):
        view = self.view_for_path(path)
        if view is not None:
            self.close_view(view, force=True)

    def flush_session(self):
        if self.session_dirty and not self.closing:
            self.save_session()

    def save_session(self):
        self.session_dirty = False
        if not self.settings.get("restore_session"):
            self.session.clear()
            return
        try:
            self.session.save([view.snapshot() for view in self.views], self.tab_bar.currentIndex())
        except OSError:
            pass

    def restore_session(self):
        records, active = self.session.load()
        for record in records:
            view = self.view_from_record(record)
            if view is not None:
                self.add_view(view)
                self.apply_view_state(view, record)
        if self.views:
            self.tab_bar.setCurrentIndex(max(0, min(active, len(self.views) - 1)))

    def view_from_record(self, record):
        view = DocumentView(self.settings, self.image_store)
        if record.get("language_manual"):
            view.apply_language(language_by_id(record.get("language", "plain")), manual=True)
        path = Path(record["path"]) if record.get("path") else None
        text = record.get("text")
        if path is not None and path.exists():
            try:
                view.load_file(path, allow_binary=True)
            except OSError:
                view.deleteLater()
                return None
            if record.get("signature"):
                view.signature = tuple(record["signature"])
            if text is not None and record.get("modified"):
                view.set_text(text, modified=True)
        elif text is not None:
            view.path = path
            view.set_text(text, modified=bool(record.get("modified")) or path is None)
        else:
            view.deleteLater()
            return None
        if path is None:
            view.title_key = tuple(record.get("title_key") or ("doc.untitled", self.next_untitled_number()))
        view.encoding = record.get("encoding", view.encoding)
        view.eol = record.get("eol", view.eol)
        return view

    def apply_view_state(self, view, record):
        view.editor.set_zoom_steps(int(record.get("zoom", 0)))
        mode = record.get("view_mode", "editor")
        if mode != "editor":
            view.set_view_mode(mode)

        def restore_cursor():
            cursor = view.editor.textCursor()
            cursor.setPosition(min(int(record.get("cursor", 0)), max(0, view.editor.document().characterCount() - 1)))
            view.editor.setTextCursor(cursor)
            view.editor.verticalScrollBar().setValue(int(record.get("scroll", 0)))

        QTimer.singleShot(0, restore_cursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.fit_tab_bar)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(80, self.fit_tab_bar)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.open_paths(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.settings.get("restore_session"):
            self.save_session()
        else:
            for view in list(self.views):
                if view.is_modified():
                    self.tab_bar.setCurrentIndex(self.views.index(view))
                    if not self.confirm_close(view):
                        event.ignore()
                        return
            self.session.clear()
        self.closing = True
        self.settings.set_value("window_geometry", self.saveGeometry())
        if self.sidebar.isVisible():
            self.settings.set("sidebar_width", self.sidebar.width())
        self.sidebar.search.shutdown()
        super().closeEvent(event)
