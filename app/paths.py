import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def asset(name):
    return resource_root() / "assets" / name


def data_dir():
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    path = Path(location or Path.home() / ".local" / "share" / "VeyloraLabs" / "VeyloraNotes")
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir():
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    path = Path(location or Path.home() / ".cache" / "veylora")
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_notes_dir():
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(documents or Path.home() / "Documents") / "VeyloraNotes"
