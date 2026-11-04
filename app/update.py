import json

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__

RELEASES_API = "https://api.github.com/repos/VeyloraLabs/VeyloraNotes/releases/latest"
RELEASES_PAGE = "https://github.com/VeyloraLabs/VeyloraNotes/releases/latest"


def parse_version(text):
    parts = []
    for piece in text.strip().lstrip("vV").split("."):
        digits = "".join(char for char in piece if char.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class UpdateChecker(QObject):
    update_available = Signal(str, str)
    up_to_date = Signal()
    failed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)

    def check(self):
        request = QNetworkRequest(QUrl(RELEASES_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"VeyloraNotes")
        request.setTransferTimeout(10000)
        reply = self.manager.get(request)
        reply.finished.connect(lambda: self.handle(reply))

    def handle(self, reply):
        data = bytes(reply.readAll())
        error = reply.error()
        reply.deleteLater()
        if error != QNetworkReply.NetworkError.NoError:
            self.failed.emit()
            return
        try:
            payload = json.loads(data.decode("utf-8"))
            tag = str(payload["tag_name"])
        except (ValueError, KeyError):
            self.failed.emit()
            return
        if parse_version(tag) > parse_version(__version__):
            self.update_available.emit(tag.lstrip("vV"), str(payload.get("html_url") or RELEASES_PAGE))
        else:
            self.up_to_date.emit()
