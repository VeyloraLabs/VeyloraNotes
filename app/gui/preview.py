import base64
import hashlib
import time
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QPainter, QPen, QTextDocument
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QTextBrowser

from .. import i18n
from ..core.markdown_html import MarkdownRenderer
from ..theme import PREVIEW_PALETTES

MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
CACHE_LIFETIME_SECONDS = 7 * 24 * 3600
CONTENT_MAX_WIDTH = 980
DOCUMENT_MARGIN = 26
SCALE_LIMIT_BYTES = 40 * 1024 * 1024


def placeholder_image(text, width=150, height=28):
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(145, 152, 161, 150), 1, Qt.PenStyle.DashLine))
    painter.setBrush(QColor(145, 152, 161, 30))
    painter.drawRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), 6, 6)
    painter.setPen(QColor(145, 152, 161))
    font = QFont()
    font.setPointSize(8)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    painter.drawText(
        QRectF(6, 0, width - 12, height),
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        metrics.elidedText(text, Qt.TextElideMode.ElideRight, width - 12),
    )
    painter.end()
    return image


def decode_image(data):
    head = bytes(data[:600]).lstrip().lower()
    if b"<svg" in head or head.startswith(b"<?xml"):
        renderer = QSvgRenderer(QByteArray(bytes(data)))
        if not renderer.isValid():
            return QImage()
        size = renderer.defaultSize()
        if size.isEmpty():
            size.setWidth(300)
            size.setHeight(150)
        scale = 2 if size.width() < 400 else 1
        image = QImage(size.width() * scale, size.height() * scale, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return image
    return QImage.fromData(QByteArray(bytes(data)))


class ImageStore(QObject):
    updated = Signal()

    def __init__(self, cache_directory, parent=None):
        super().__init__(parent)
        self.cache_directory = Path(cache_directory) / "images"
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        self.manager = QNetworkAccessManager(self)
        self.memory = {}
        self.pending = set()
        self.failed = set()
        self.allow_remote = True

    def resolve(self, request, base_dir):
        source = request.source.strip()
        label = request.alt or Path(urllib.parse.unquote(source.split("?")[0])).name or "image"
        if not source:
            return placeholder_image("🖼 " + label)
        image = self.fetch(source, base_dir, label)
        return self.fit(image, request.max_width)

    def fetch(self, source, base_dir, label):
        lowered = source.lower()
        if lowered.startswith("data:"):
            return self.decode_data_uri(source, label)
        if lowered.startswith(("http://", "https://")):
            return self.fetch_remote(source, label)
        return self.fetch_local(source, base_dir, label)

    def decode_data_uri(self, source, label):
        try:
            header, payload = source.split(",", 1)
            raw = base64.b64decode(payload) if ";base64" in header else urllib.parse.unquote_to_bytes(payload)
        except (ValueError, base64.binascii.Error):
            return placeholder_image("🖼 " + label)
        image = decode_image(raw)
        return image if not image.isNull() else placeholder_image("🖼 " + label)

    def fetch_local(self, source, base_dir, label):
        cleaned = urllib.parse.unquote(source.split("#")[0].split("?")[0])
        if cleaned.startswith("file://"):
            cleaned = cleaned[7:]
        path = Path(cleaned)
        if not path.is_absolute():
            path = (Path(base_dir) if base_dir else Path.cwd()) / path
        if not path.is_file():
            return placeholder_image("🖼 " + label)
        try:
            if path.stat().st_size > SCALE_LIMIT_BYTES:
                return placeholder_image("🖼 " + label)
            data = path.read_bytes()
        except OSError:
            return placeholder_image("🖼 " + label)
        image = decode_image(data)
        return image if not image.isNull() else placeholder_image("🖼 " + label)

    def fetch_remote(self, url, label):
        if not self.allow_remote:
            return placeholder_image("🖼 " + label)
        cached = self.memory.get(url)
        if cached is not None:
            return cached
        disk_file = self.cache_directory / hashlib.sha1(url.encode("utf-8")).hexdigest()
        if disk_file.is_file() and time.time() - disk_file.stat().st_mtime < CACHE_LIFETIME_SECONDS:
            image = decode_image(disk_file.read_bytes())
            if not image.isNull():
                self.memory[url] = image
                return image
        if url in self.failed:
            return placeholder_image("🖼 " + label)
        if url not in self.pending:
            self.start_download(url, disk_file)
        return placeholder_image("… " + label)

    def start_download(self, url, disk_file):
        self.pending.add(url)
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute, QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy
        )
        request.setTransferTimeout(15000)
        request.setRawHeader(b"User-Agent", b"VeyloraNotes")
        reply = self.manager.get(request)
        reply.finished.connect(lambda: self.finish_download(url, disk_file, reply))

    def finish_download(self, url, disk_file, reply):
        self.pending.discard(url)
        data = reply.readAll()
        error = reply.error()
        reply.deleteLater()
        if error != QNetworkReply.NetworkError.NoError or len(data) > MAX_DOWNLOAD_BYTES:
            self.failed.add(url)
            self.updated.emit()
            return
        raw = bytes(data)
        image = decode_image(raw)
        if image.isNull():
            self.failed.add(url)
        else:
            self.memory[url] = image
            try:
                disk_file.write_bytes(raw)
            except OSError:
                pass
        self.updated.emit()

    @staticmethod
    def fit(image, max_width):
        if max_width > 0 and image.width() > max_width:
            return image.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
        return image


class MarkdownPreview(QTextBrowser):
    document_requested = Signal(object, str)

    def __init__(self, settings, image_store, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.image_store = image_store
        self.base_dir = None
        self.source_text = ""
        self.images = {}
        self.renderer = None
        self.theme_name = ""
        self.last_width = 0
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.document().setDocumentMargin(DOCUMENT_MARGIN)
        self.anchorClicked.connect(self.handle_anchor)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(220)
        self.render_timer.timeout.connect(self.render_now)
        self.image_timer = QTimer(self)
        self.image_timer.setSingleShot(True)
        self.image_timer.setInterval(250)
        self.image_timer.timeout.connect(self.render_now)
        self.image_store.updated.connect(self.image_timer.start)
        self.refresh_theme()

    def refresh_theme(self):
        name = self.settings.get("preview_theme")
        if name not in PREVIEW_PALETTES:
            name = "dark"
        palette = PREVIEW_PALETTES[name]
        self.theme_name = name
        self.renderer = MarkdownRenderer(palette, self.labels())
        self.setStyleSheet(
            f"QTextBrowser {{ background: {palette['background']}; border: 1px solid {palette['border']}; border-radius: 10px; }}"
        )
        self.image_store.allow_remote = self.settings.get("remote_images")
        self.render_now()

    @staticmethod
    def labels():
        return {
            "mermaid_note": i18n.t("preview.mermaid"),
            "alerts": {
                "NOTE": i18n.t("preview.alert.note"),
                "TIP": i18n.t("preview.alert.tip"),
                "IMPORTANT": i18n.t("preview.alert.important"),
                "WARNING": i18n.t("preview.alert.warning"),
                "CAUTION": i18n.t("preview.alert.caution"),
            },
        }

    def set_content(self, text, base_dir, immediate=False):
        self.source_text = text
        self.base_dir = base_dir
        if immediate:
            self.render_timer.stop()
            self.render_now()
        else:
            self.render_timer.start()

    def content_width(self):
        return max(240, min(self.viewport().width(), CONTENT_MAX_WIDTH) - DOCUMENT_MARGIN * 2 - 4)

    def update_margins(self):
        total = self.width()
        side = max(0, (total - CONTENT_MAX_WIDTH) // 2)
        self.setViewportMargins(side, 0, side, 0)

    def render_now(self):
        if self.renderer is None:
            return
        self.update_margins()
        bar = self.verticalScrollBar()
        previous = bar.value()
        result = self.renderer.render(self.source_text, self.base_dir, self.content_width())
        self.images = result.images
        document = self.document()
        for key, request in result.images.items():
            document.addResource(
                QTextDocument.ResourceType.ImageResource, QUrl(key), self.image_store.resolve(request, self.base_dir)
            )
        self.setHtml(result.html)
        bar.setValue(min(previous, bar.maximum()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if abs(self.width() - self.last_width) > 24:
            self.last_width = self.width()
            self.render_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self.render_timer.start()

    def handle_anchor(self, url):
        text = url.toString()
        if text.startswith("#"):
            self.scrollToAnchor(urllib.parse.unquote(text[1:]))
            return
        scheme = url.scheme().lower()
        if scheme in ("http", "https", "mailto", "ftp"):
            QDesktopServices.openUrl(url)
            return
        raw_path = urllib.parse.unquote(text.split("#")[0].split("?")[0])
        fragment = text.split("#", 1)[1] if "#" in text else ""
        if raw_path.startswith("file://"):
            raw_path = raw_path[7:]
        target = Path(raw_path)
        if not target.is_absolute() and self.base_dir:
            target = Path(self.base_dir) / target
        if target.is_file():
            if target.suffix.lower() in (".md", ".markdown", ".txt"):
                self.document_requested.emit(target, fragment)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        elif not raw_path and fragment:
            self.scrollToAnchor(urllib.parse.unquote(fragment))
