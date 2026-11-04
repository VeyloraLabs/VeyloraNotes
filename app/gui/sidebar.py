import re
from pathlib import Path

from PySide6.QtCore import QDir, QFile, QFileInfo, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFileIconProvider,
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import SegmentedWidget

from .. import i18n
from ..core.document_io import read_text_file
from ..core.languages import is_text_candidate
from ..icons import icon
from ..theme import ACCENT, MUTED, PANEL, TEXT
from .ui import tool_button

MAX_SEARCH_FILE_BYTES = 2 * 1024 * 1024
MAX_SEARCH_RESULTS = 2000
SKIPPED_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", ".trash"}


class FileIconProvider(QFileIconProvider):
    def icon(self, argument):
        if isinstance(argument, QFileInfo):
            if argument.isDir():
                return icon("fa5s.folder", "#d9b45f", "#f0cf7a")
            suffix = argument.suffix().lower()
            if suffix in ("md", "markdown"):
                return icon("fa5s.file-alt", ACCENT, ACCENT)
            if suffix in ("py", "js", "ts", "json", "html", "css", "sh", "yml", "yaml", "toml", "xml"):
                return icon("fa5s.file-code", "#7fd8ff", "#7fd8ff")
            return icon("fa5s.file", MUTED, TEXT)
        return icon("fa5s.file", MUTED, TEXT)


class SearchWorker(QThread):
    found = Signal(str, list)
    finished_search = Signal(int)

    def __init__(self, root, pattern, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.pattern = pattern
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        total = 0
        stack = [self.root]
        while stack and not self.cancelled and total < MAX_SEARCH_RESULTS:
            directory = stack.pop()
            try:
                entries = sorted(directory.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                continue
            for entry in entries:
                if self.cancelled or total >= MAX_SEARCH_RESULTS:
                    break
                if entry.name.startswith(".") or entry.name in SKIPPED_DIRECTORIES:
                    continue
                if entry.is_dir():
                    stack.append(entry)
                    continue
                if not is_text_candidate(entry):
                    continue
                try:
                    if entry.stat().st_size > MAX_SEARCH_FILE_BYTES:
                        continue
                    text = read_text_file(entry).text
                except Exception:
                    continue
                hits = []
                for number, line in enumerate(text.split("\n"), 1):
                    for match in self.pattern.finditer(line):
                        if match.end() == match.start():
                            continue
                        column = len(line[: match.start()].encode("utf-16-le")) // 2
                        width = len(match.group(0).encode("utf-16-le")) // 2
                        hits.append((number, line.strip()[:200], column, width))
                        total += 1
                        break
                if hits:
                    self.found.emit(str(entry), hits)
        self.finished_search.emit(total)


class FilesPanel(QWidget):
    file_activated = Signal(object)
    file_renamed = Signal(object, object)
    file_deleted = Signal(object)
    folder_changed = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.model = QFileSystemModel(self)
        self.model.setIconProvider(FileIconProvider())
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.model.setReadOnly(False)
        self.model.setNameFilterDisables(False)
        self.model.fileRenamed.connect(self.on_renamed)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(2)
        self.folder_label = QLabel()
        self.folder_label.setStyleSheet(f"color: {TEXT}; font-weight: 700;")
        self.new_file_button = tool_button("fa5s.file-medical", "", size=28, icon_size=13)
        self.new_folder_button = tool_button("fa5s.folder-plus", "", size=28, icon_size=13)
        self.choose_button = tool_button("fa5s.folder-open", "", size=28, icon_size=13)
        header.addWidget(self.folder_label, 1)
        header.addWidget(self.new_file_button)
        header.addWidget(self.new_folder_button)
        header.addWidget(self.choose_button)
        root.addLayout(header)
        self.filter_input = QLineEdit()
        self.filter_input.setClearButtonEnabled(True)
        root.addWidget(self.filter_input)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setEditTriggers(QTreeView.EditTrigger.EditKeyPressed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.setDragEnabled(True)
        for column in (1, 2, 3):
            self.tree.setColumnHidden(column, True)
        root.addWidget(self.tree, 1)
        self.empty_label = QLabel()
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        root.addWidget(self.empty_label)

        self.filter_input.textChanged.connect(self.apply_filter)
        self.tree.doubleClicked.connect(self.on_double_click)
        self.tree.activated.connect(self.on_double_click)
        self.tree.customContextMenuRequested.connect(self.show_menu)
        self.new_file_button.clicked.connect(lambda: self.create_file())
        self.new_folder_button.clicked.connect(lambda: self.create_folder())
        self.choose_button.clicked.connect(self.folder_changed.emit)
        self.set_root(settings.notes_dir())
        self.retranslate()

    def root_path(self):
        return Path(self.model.rootPath())

    def set_root(self, path):
        path = Path(path)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self.model.setRootPath(str(path))
        self.tree.setRootIndex(self.model.index(str(path)))
        self.folder_label.setText(path.name or str(path))
        self.folder_label.setToolTip(str(path))

    def retranslate(self):
        t = i18n.t
        self.filter_input.setPlaceholderText(t("sidebar.filter"))
        self.new_file_button.setToolTip(t("sidebar.new_file"))
        self.new_folder_button.setToolTip(t("sidebar.new_folder"))
        self.choose_button.setToolTip(t("sidebar.choose_folder"))
        self.empty_label.setText(t("sidebar.hint"))

    def apply_filter(self, text):
        text = text.strip()
        self.model.setNameFilters([f"*{text}*"] if text else [])
        if text:
            self.tree.expandAll()

    def on_double_click(self, index):
        if index.isValid() and not self.model.isDir(index):
            self.file_activated.emit(Path(self.model.filePath(index)))

    def selected_directory(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            return self.root_path()
        path = Path(self.model.filePath(index))
        return path if self.model.isDir(index) else path.parent

    def ask_name(self, title, label, default=""):
        name, accepted = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Normal, default)
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip()
        return name if accepted and name else None

    def create_file(self, directory=None):
        directory = directory or self.selected_directory()
        name = self.ask_name(i18n.t("sidebar.new_file"), i18n.t("sidebar.name_prompt"), "")
        if not name:
            return
        target = directory / (name if Path(name).suffix else f"{name}.md")
        if target.exists():
            QMessageBox.warning(self, i18n.t("app.name"), i18n.t("sidebar.exists", target.name))
            return
        try:
            target.touch()
        except OSError as error:
            QMessageBox.critical(self, i18n.t("app.name"), str(error))
            return
        self.file_activated.emit(target)

    def create_folder(self, directory=None):
        directory = directory or self.selected_directory()
        name = self.ask_name(i18n.t("sidebar.new_folder"), i18n.t("sidebar.name_prompt"), "")
        if not name:
            return
        try:
            (directory / name).mkdir(parents=True, exist_ok=False)
        except OSError as error:
            QMessageBox.critical(self, i18n.t("app.name"), str(error))

    def show_menu(self, position):
        index = self.tree.indexAt(position)
        menu = QMenu(self)
        target = Path(self.model.filePath(index)) if index.isValid() else self.root_path()
        is_dir = not index.isValid() or self.model.isDir(index)
        directory = target if is_dir else target.parent
        if index.isValid() and not is_dir:
            menu.addAction(icon("fa5s.file-alt"), i18n.t("sidebar.open"), lambda: self.file_activated.emit(target))
            menu.addSeparator()
        menu.addAction(icon("fa5s.file-medical"), i18n.t("sidebar.new_file"), lambda: self.create_file(directory))
        menu.addAction(icon("fa5s.folder-plus"), i18n.t("sidebar.new_folder"), lambda: self.create_folder(directory))
        if index.isValid():
            menu.addSeparator()
            menu.addAction(icon("fa5s.edit"), i18n.t("sidebar.rename"), lambda: self.tree.edit(index))
            menu.addAction(icon("fa5s.trash-alt", "#ff6b6b", "#ff6b6b"), i18n.t("sidebar.delete"), lambda: self.delete_path(target))
        menu.addSeparator()
        menu.addAction(icon("fa5s.copy"), i18n.t("sidebar.copy_path"), lambda: QGuiApplication.clipboard().setText(str(target)))
        menu.addAction(icon("fa5s.external-link-alt"), i18n.t("sidebar.reveal"), lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))))
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def delete_path(self, path):
        answer = QMessageBox.warning(
            self, i18n.t("app.name"), i18n.t("sidebar.confirm_delete", path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not QFile.moveToTrash(str(path)):
            try:
                path.unlink() if path.is_file() else path.rmdir()
            except OSError as error:
                QMessageBox.critical(self, i18n.t("app.name"), str(error))
                return
        self.file_deleted.emit(path)

    def on_renamed(self, directory, old_name, new_name):
        self.file_renamed.emit(Path(directory) / old_name, Path(directory) / new_name)

    def list_files(self, limit=5000):
        root = self.root_path()
        result = []
        stack = [root]
        while stack and len(result) < limit:
            directory = stack.pop()
            try:
                entries = sorted(directory.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                continue
            for entry in entries:
                if entry.name.startswith(".") or entry.name in SKIPPED_DIRECTORIES:
                    continue
                if entry.is_dir():
                    stack.append(entry)
                elif is_text_candidate(entry):
                    result.append(entry)
        return result


class OutlinePanel(QWidget):
    jump_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.list = QTreeWidget()
        self.list.setHeaderHidden(True)
        self.list.setIndentation(14)
        self.list.setRootIsDecorated(False)
        self.empty_label = QLabel()
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self.list, 1)
        root.addWidget(self.empty_label)
        self.list.itemClicked.connect(self.on_click)
        self.retranslate()

    def retranslate(self):
        self.empty_label.setText(i18n.t("outline.empty"))

    def set_headings(self, headings):
        self.list.clear()
        for level, title, line in headings:
            item = QTreeWidgetItem([("   " * (level - 1)) + title])
            item.setData(0, Qt.ItemDataRole.UserRole, line)
            if level == 1:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            self.list.addTopLevelItem(item)
        self.empty_label.setVisible(not headings)
        self.list.setVisible(bool(headings))

    def on_click(self, item):
        self.jump_requested.emit(item.data(0, Qt.ItemDataRole.UserRole))


class SearchPanel(QWidget):
    result_activated = Signal(object, int, int, int)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.worker = None
        self.root_getter = settings.notes_dir
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.input = QLineEdit()
        self.case_button = tool_button(None, "", True, "Aa", 28)
        self.regex_button = tool_button(None, "", True, ".*", 28)
        row.addWidget(self.input, 1)
        row.addWidget(self.case_button)
        row.addWidget(self.regex_button)
        root.addLayout(row)
        self.status = QLabel()
        self.status.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        root.addWidget(self.status)
        self.results = QTreeWidget()
        self.results.setHeaderHidden(True)
        self.results.setIndentation(12)
        root.addWidget(self.results, 1)
        self.input.returnPressed.connect(self.start)
        self.results.itemActivated.connect(self.on_activated)
        self.results.itemClicked.connect(self.on_activated)
        self.retranslate()

    def retranslate(self):
        t = i18n.t
        self.input.setPlaceholderText(t("search.placeholder"))
        self.case_button.setToolTip(t("find.match_case"))
        self.regex_button.setToolTip(t("find.regex"))
        if not self.results.topLevelItemCount():
            self.status.setText(t("search.hint"))

    def focus_input(self, text=""):
        if text:
            self.input.setText(text)
        self.input.setFocus()
        self.input.selectAll()

    def start(self):
        query = self.input.text()
        if not query:
            return
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        source = query if self.regex_button.isChecked() else re.escape(query)
        flags = 0 if self.case_button.isChecked() else re.IGNORECASE
        try:
            pattern = re.compile(source, flags)
        except re.error:
            self.status.setText(i18n.t("find.invalid"))
            return
        self.results.clear()
        self.total_files = 0
        self.status.setText(i18n.t("search.running"))
        self.worker = SearchWorker(self.root_getter(), pattern, self)
        self.worker.found.connect(self.add_file_results)
        self.worker.finished_search.connect(self.finish)
        self.worker.start()

    def add_file_results(self, path, hits):
        path = Path(path)
        try:
            relative = path.relative_to(self.root_getter())
        except ValueError:
            relative = path
        parent = QTreeWidgetItem([f"{relative}  ({len(hits)})"])
        parent.setIcon(0, icon("fa5s.file-alt", ACCENT, ACCENT))
        parent.setData(0, Qt.ItemDataRole.UserRole, (str(path), 0, 0, 0))
        for line, text, column, length in hits:
            child = QTreeWidgetItem([f"{line}:  {text}"])
            child.setData(0, Qt.ItemDataRole.UserRole, (str(path), line, column, length))
            parent.addChild(child)
        self.results.addTopLevelItem(parent)
        parent.setExpanded(True)
        self.total_files += 1

    def finish(self, total):
        if total:
            self.status.setText(i18n.t("search.done", total, self.total_files))
        else:
            self.status.setText(i18n.t("search.none"))

    def on_activated(self, item, *_):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            path, line, column, length = data
            self.result_activated.emit(Path(path), line, column, length)

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)


class Sidebar(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setMinimumWidth(220)
        self.setMaximumWidth(460)
        self.setStyleSheet(f"Sidebar {{ background: {PANEL}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 10)
        root.setSpacing(10)
        self.tabs = SegmentedWidget(self)
        self.stack = QStackedWidget()
        self.files = FilesPanel(settings)
        self.outline = OutlinePanel()
        self.search = SearchPanel(settings)
        for key, widget in (("files", self.files), ("outline", self.outline), ("search", self.search)):
            self.stack.addWidget(widget)
            self.tabs.addItem(key, key, lambda _=False, w=widget: self.stack.setCurrentWidget(w))
        root.addWidget(self.tabs)
        root.addWidget(self.stack, 1)
        self.tabs.setCurrentItem("files")
        self.retranslate()

    def retranslate(self):
        for key in ("files", "outline", "search"):
            self.tabs.widget(key).setText(i18n.t(f"sidebar.tab.{key}"))
        self.files.retranslate()
        self.outline.retranslate()
        self.search.retranslate()

    def show_panel(self, key):
        self.tabs.setCurrentItem(key)
        self.stack.setCurrentWidget({"files": self.files, "outline": self.outline, "search": self.search}[key])
