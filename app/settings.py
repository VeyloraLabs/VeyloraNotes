import json
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, QSettings, Signal
from PySide6.QtGui import QFontDatabase

from .paths import default_notes_dir

PREFERRED_MONO_FONTS = (
    "JetBrains Mono",
    "Fira Code",
    "Cascadia Code",
    "Cascadia Mono",
    "Source Code Pro",
    "Ubuntu Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Noto Sans Mono",
)
MAX_RECENT_FILES = 15


def detect_language():
    name = QLocale.system().name().lower()
    return "es" if name.startswith("es") else "en"


def default_mono_family():
    families = set(QFontDatabase.families())
    for family in PREFERRED_MONO_FONTS:
        if family in families:
            return family
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


class Settings(QObject):
    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.store = QSettings("VeyloraLabs", "VeyloraNotes")
        self.defaults = {
            "language": detect_language(),
            "notes_dir": str(default_notes_dir()),
            "font_family": default_mono_family(),
            "font_size": 11,
            "tab_width": 4,
            "use_spaces": True,
            "word_wrap": True,
            "line_numbers": True,
            "highlight_line": True,
            "show_whitespace": False,
            "auto_indent": True,
            "list_continuation": True,
            "default_language": "plain",
            "restore_session": True,
            "check_updates": True,
            "remote_images": True,
            "preview_theme": "dark",
            "sync_scroll": True,
            "sidebar_visible": True,
            "sidebar_width": 280,
            "sidebar_tab": 0,
            "welcome_shown": False,
            "recent_files": "[]",
        }

    def get(self, key):
        default = self.defaults[key]
        return self.store.value(key, default, type=type(default))

    def set(self, key, value):
        if self.store.contains(key) and self.get(key) == value:
            return
        self.store.setValue(key, value)
        self.changed.emit(key)

    def notes_dir(self):
        return Path(self.get("notes_dir")).expanduser()

    def recent_files(self):
        try:
            items = json.loads(self.get("recent_files"))
        except (TypeError, ValueError):
            return []
        return [Path(item) for item in items if isinstance(item, str)]

    def add_recent_file(self, path):
        path = str(Path(path))
        items = [str(item) for item in self.recent_files() if str(item) != path]
        items.insert(0, path)
        self.set("recent_files", json.dumps(items[:MAX_RECENT_FILES]))

    def clear_recent_files(self):
        self.set("recent_files", "[]")

    def value(self, key, default=None):
        return self.store.value(key, default)

    def set_value(self, key, value):
        self.store.setValue(key, value)
