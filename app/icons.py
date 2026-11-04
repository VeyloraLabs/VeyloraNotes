import qtawesome as qta
from PySide6.QtGui import QIcon

from .theme import MUTED, TEXT

_cache = {}


def icon(name, color=MUTED, active=None):
    key = (name, color, active)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        result = qta.icon(name, color=color, color_active=active or TEXT)
    except Exception:
        result = QIcon()
    _cache[key] = result
    return result



def app_icon():
    from .paths import asset

    return QIcon(str(asset("icon.svg")))
