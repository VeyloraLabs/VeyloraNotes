from PySide6.QtCore import QObject, Signal

from .strings import STRINGS

LANGUAGE_NAMES = {"es": "Español", "en": "English"}


class LanguageNotifier(QObject):
    changed = Signal(str)


notifier = LanguageNotifier()
current = "es"


def set_language(code):
    global current
    if code not in LANGUAGE_NAMES or code == current:
        return
    current = code
    notifier.changed.emit(code)


def language():
    return current


def t(key, *args, **kwargs):
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry[0] if current == "es" else entry[1]
    return text.format(*args, **kwargs) if args or kwargs else text
