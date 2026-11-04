from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget

from .. import i18n
from ..core.document_io import disk_signature, read_text_file, write_text_file
from ..core.languages import language_by_id, language_for_path
from .editor import CodeEditor
from .preview import MarkdownPreview

VIEW_MODES = ("editor", "split", "preview")


class DocumentView(QWidget):
    modification_changed = Signal(object)
    title_changed = Signal(object)
    cursor_changed = Signal(object)
    language_changed = Signal(object)
    text_edited = Signal(object)
    document_requested = Signal(object, str)

    def __init__(self, settings, image_store, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.path = None
        self.title_key = ()
        self.encoding = "utf-8"
        self.eol = "\n"
        self.language = language_by_id("plain")
        self.language_manual = False
        self.view_mode = "editor"
        self.signature = None
        self.buffer_name = None
        self.syncing = False

        self.editor = CodeEditor(settings)
        self.preview = MarkdownPreview(settings, image_store)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        self.preview.setVisible(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)

        self.editor.document().modificationChanged.connect(lambda _: self.modification_changed.emit(self))
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.cursor_info_changed.connect(lambda: self.cursor_changed.emit(self))
        self.editor.verticalScrollBar().valueChanged.connect(self.sync_from_editor)
        self.preview.verticalScrollBar().valueChanged.connect(self.sync_from_preview)
        self.preview.document_requested.connect(self.document_requested)
        self.editor.apply_settings()
        self.apply_language(language_by_id(settings.get("default_language")))

    def display_name(self):
        if self.path:
            return self.path.name
        return i18n.t(*self.title_key) if self.title_key else ""

    def is_modified(self):
        return self.editor.document().isModified()

    def base_dir(self):
        return self.path.parent if self.path else None

    def text(self):
        return self.editor.text()

    def apply_settings(self):
        self.editor.apply_settings()
        self.preview.refresh_theme()

    def apply_language(self, language, manual=False):
        self.language = language
        if manual:
            self.language_manual = True
        self.editor.set_language(language)
        self.language_changed.emit(self)

    def set_text(self, text, modified=False):
        self.editor.setPlainText(text)
        self.editor.document().setModified(modified)
        self.editor.set_language(self.language)
        self.refresh_preview(immediate=True)

    def load_file(self, path, forced_encoding=None, allow_binary=False):
        loaded = read_text_file(path, forced_encoding, allow_binary)
        self.path = Path(path)
        self.encoding = loaded.encoding
        self.eol = loaded.eol
        self.signature = disk_signature(self.path)
        if not self.language_manual:
            self.language = language_for_path(self.path)
        self.set_text(loaded.text)
        self.title_changed.emit(self)
        self.language_changed.emit(self)

    def reload_from_disk(self, forced_encoding=None):
        if self.path is None:
            return
        line = self.editor.cursor_line_column()[0]
        self.load_file(self.path, forced_encoding)
        self.editor.go_to_line(line)

    def save(self, path=None):
        target = Path(path) if path else self.path
        write_text_file(target, self.editor.text(), self.encoding, self.eol)
        self.path = target
        self.signature = disk_signature(target)
        if not self.language_manual:
            self.language = language_for_path(target)
            self.editor.set_language(self.language)
        self.editor.document().setModified(False)
        self.title_changed.emit(self)
        self.language_changed.emit(self)
        self.refresh_preview(immediate=True)

    def external_state(self):
        if self.path is None:
            return "none"
        current = disk_signature(self.path)
        if current is None:
            return "deleted"
        if self.signature is not None and current != self.signature:
            return "changed"
        return "none"

    def acknowledge_external_change(self):
        self.signature = disk_signature(self.path) if self.path else None

    def on_text_changed(self):
        self.text_edited.emit(self)
        if self.view_mode != "editor":
            self.refresh_preview()

    def refresh_preview(self, immediate=False):
        if self.view_mode == "editor":
            return
        self.preview.set_content(self.editor.text(), self.base_dir(), immediate)

    def set_view_mode(self, mode):
        if mode not in VIEW_MODES:
            return
        self.view_mode = mode
        self.editor.setVisible(mode != "preview")
        self.preview.setVisible(mode != "editor")
        if mode != "editor":
            self.preview.set_content(self.editor.text(), self.base_dir(), True)
        if mode == "split":
            total = max(400, self.splitter.width())
            self.splitter.setSizes([total // 2, total // 2])
        if mode == "editor":
            self.editor.setFocus()
        elif mode == "preview":
            self.preview.setFocus()

    def sync_from_editor(self, value):
        if self.syncing or self.view_mode != "split" or not self.settings.get("sync_scroll"):
            return
        source = self.editor.verticalScrollBar()
        self.scroll_proportionally(source, self.preview.verticalScrollBar())

    def sync_from_preview(self, value):
        if self.syncing or self.view_mode != "split" or not self.settings.get("sync_scroll"):
            return
        source = self.preview.verticalScrollBar()
        self.scroll_proportionally(source, self.editor.verticalScrollBar())

    def scroll_proportionally(self, source, target):
        if source.maximum() <= 0:
            return
        self.syncing = True
        target.setValue(round(source.value() / source.maximum() * target.maximum()))
        self.syncing = False

    def snapshot(self):
        modified = self.is_modified()
        record = {
            "path": str(self.path) if self.path else None,
            "title_key": list(self.title_key),
            "encoding": self.encoding,
            "eol": self.eol,
            "language": self.language.id,
            "language_manual": self.language_manual,
            "view_mode": self.view_mode,
            "cursor": self.editor.textCursor().position(),
            "scroll": self.editor.verticalScrollBar().value(),
            "zoom": self.editor.zoom_steps,
            "modified": modified,
            "buffer": self.buffer_name,
            "signature": list(self.signature) if self.signature else None,
        }
        if modified or self.path is None:
            record["text"] = self.editor.text()
        return record
