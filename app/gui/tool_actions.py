import os
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF, QUrl
from PySide6.QtGui import QGuiApplication, QPageLayout, QPageSize, QPdfWriter, QTextCursor, QTextDocument
from PySide6.QtWidgets import QColorDialog, QFileDialog

from .. import i18n
from ..core import calculator, diff_html, markdown_tools, text_tools
from ..core.markdown_html import MarkdownRenderer, export_html_document
from ..theme import PREVIEW_PALETTES
from .dialogs import DiffDialog, HashDialog, StatsDialog, TableDialog

TRANSFORMS = {
    "upper": (text_tools.to_upper, False),
    "lower": (text_tools.to_lower, False),
    "title": (text_tools.to_title, False),
    "sentence": (text_tools.to_sentence, False),
    "invert": (text_tools.invert_case, False),
    "camel": (text_tools.to_camel, False),
    "pascal": (text_tools.to_pascal, False),
    "snake": (text_tools.to_snake, False),
    "kebab": (text_tools.to_kebab, False),
    "constant": (text_tools.to_constant, False),
    "slug": (text_tools.to_slug, False),
    "strip_accents": (text_tools.strip_accents, False),
    "sort_asc": (lambda text: text_tools.sort_lines(text), True),
    "sort_desc": (lambda text: text_tools.sort_lines(text, descending=True), True),
    "sort_natural": (lambda text: text_tools.sort_lines(text, numeric=True), True),
    "reverse": (text_tools.reverse_lines, True),
    "unique": (text_tools.unique_lines, True),
    "remove_empty": (text_tools.remove_empty_lines, True),
    "collapse_empty": (text_tools.collapse_empty_lines, True),
    "trim_trailing": (text_tools.trim_trailing_spaces, True),
    "trim_all": (text_tools.trim_lines, True),
    "number_lines": (text_tools.number_lines, True),
    "shuffle": (text_tools.shuffle_lines, True),
    "base64_encode": (text_tools.base64_encode, False),
    "base64_decode": (text_tools.base64_decode, False),
    "url_encode": (text_tools.url_encode, False),
    "url_decode": (text_tools.url_decode, False),
    "html_escape": (text_tools.html_escape, False),
    "html_unescape": (text_tools.html_unescape, False),
    "hex_encode": (text_tools.hex_encode, False),
    "hex_decode": (text_tools.hex_decode, False),
    "rot13": (text_tools.rot13, False),
    "json_format": (text_tools.json_format, False),
    "json_minify": (text_tools.json_minify, False),
    "timestamp": (text_tools.convert_timestamp, False),
}


class ToolActions:
    def run_transform(self, name):
        editor = self.current_editor()
        if editor is None:
            return
        function, lines = TRANSFORMS[name]
        had_selection = editor.textCursor().hasSelection()
        try:
            changed = editor.transform_text(function, lines=lines)
        except (ValueError, OverflowError, OSError) as error:
            self.notify("error", i18n.t("tools.failed", str(error)[:120]))
            return
        if changed:
            self.show_message(i18n.t("tools.applied_selection" if had_selection else "tools.applied_document"))
        else:
            self.show_message(i18n.t("tools.no_change"))
        editor.setFocus()

    def run_tabs_to_spaces(self):
        editor = self.current_editor()
        width = self.settings.get("tab_width")
        if editor and editor.transform_text(lambda text: text_tools.tabs_to_spaces(text, width), lines=True):
            self.show_message(i18n.t("tools.applied_selection"))

    def run_spaces_to_tabs(self):
        editor = self.current_editor()
        width = self.settings.get("tab_width")
        if editor and editor.transform_text(lambda text: text_tools.spaces_to_tabs(text, width), lines=True):
            self.show_message(i18n.t("tools.applied_selection"))

    def run_join_with_comma(self):
        editor = self.current_editor()
        if editor and editor.transform_text(lambda text: text_tools.join_lines(text, ", "), lines=True):
            self.show_message(i18n.t("tools.applied_selection"))

    def selection_or_document(self):
        editor = self.current_editor()
        if editor is None:
            return "", ""
        selected = editor.selected_text()
        if selected:
            return selected, i18n.t("tools.scope_selection")
        return editor.text(), i18n.t("tools.scope_document")

    def calculate_selection(self):
        editor = self.current_editor()
        if editor is None:
            return
        if not editor.textCursor().hasSelection():
            cursor = editor.textCursor()
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            editor.setTextCursor(cursor)
        counter = {"done": 0}

        def apply(text):
            result, count = calculator.calculate_text(text)
            counter["done"] = count
            return result

        editor.transform_text(apply, lines=True)
        if counter["done"]:
            self.show_message(i18n.t("tools.calculated", counter["done"]))
        else:
            self.notify("warning", i18n.t("tools.nothing_to_calculate"))

    def show_statistics(self):
        text, scope = self.selection_or_document()
        if self.current_editor() is not None:
            StatsDialog(self, text_tools.compute_stats(text), scope).exec()

    def show_hashes(self):
        text, scope = self.selection_or_document()
        if self.current_editor() is not None:
            HashDialog(self, text_tools.compute_hashes(text), scope).exec()

    def validate_json(self):
        text, _ = self.selection_or_document()
        problem = text_tools.json_check(text)
        if problem is None:
            self.notify("success", i18n.t("tools.json_valid"))
            return
        line, column, message = problem
        self.notify("error", i18n.t("tools.json_invalid", line, column, message))
        editor = self.current_editor()
        if editor is not None and not editor.textCursor().hasSelection():
            editor.go_to_line(line, column)

    def extract_items(self, kind):
        text, _ = self.selection_or_document()
        extractor = {"urls": text_tools.extract_urls, "emails": text_tools.extract_emails, "numbers": text_tools.extract_numbers}[kind]
        items = extractor(text)
        if not items:
            self.notify("warning", i18n.t("tools.nothing_found"))
            return
        self.new_document("\n".join(items) + "\n", title_key=(f"tools.extract_title.{kind}",))
        self.show_message(i18n.t("tools.found", len(items)))

    def compare_with_disk(self):
        view = self.current_view()
        if view is None:
            return
        if view.path is None or not view.path.exists():
            self.notify("warning", i18n.t("tools.compare_no_file"))
            return
        from ..core.document_io import read_text_file

        disk = read_text_file(view.path, allow_binary=True).text
        self.show_diff(disk, view.text(), i18n.t("tools.disk_version"), i18n.t("tools.current_version"))

    def compare_with_clipboard(self):
        view = self.current_view()
        if view is None:
            return
        clipboard = QGuiApplication.clipboard().text().replace("\r\n", "\n")
        if not clipboard:
            self.notify("warning", i18n.t("tools.clipboard_empty"))
            return
        selected = view.editor.selected_text()
        current = selected if selected else view.text()
        self.show_diff(clipboard, current, i18n.t("tools.clipboard"), i18n.t("tools.selection" if selected else "tools.current_version"))

    def show_diff(self, old_text, new_text, old_label, new_label):
        lines = diff_html.diff_lines(old_text, new_text, old_label, new_label)
        if not lines:
            self.notify("success", i18n.t("tools.no_differences"))
            return
        added, removed = diff_html.diff_summary(lines)
        DiffDialog(self, i18n.t("tools.compare_title"), diff_html.render_diff(lines), i18n.t("tools.diff_summary", added, removed)).exec()

    def insert_now(self, pattern):
        editor = self.current_editor()
        if editor:
            editor.insert_text(datetime.now().strftime(pattern))

    def insert_unix_time(self):
        editor = self.current_editor()
        if editor:
            editor.insert_text(str(int(time.time())))

    def insert_generated(self, kind):
        editor = self.current_editor()
        if editor is None:
            return
        text = {
            "uuid": text_tools.new_uuid,
            "password": lambda: text_tools.generate_password(20),
            "lorem": lambda: text_tools.lorem_ipsum(3),
        }[kind]()
        editor.insert_text(text)

    def insert_color(self):
        editor = self.current_editor()
        if editor is None:
            return
        color = QColorDialog.getColor(parent=self, title=i18n.t("cmd.insert.color"))
        if color.isValid():
            editor.insert_text(color.name())

    def go_to_line_dialog(self):
        editor = self.current_editor()
        if editor is None:
            return
        from PySide6.QtWidgets import QInputDialog

        current = editor.cursor_line_column()[0]
        total = editor.document().blockCount()
        value, accepted = QInputDialog.getInt(
            self, i18n.t("cmd.edit.go_to_line"), i18n.t("tools.line_prompt", total), current, 1, total
        )
        if accepted:
            editor.go_to_line(value)

    def markdown_wrap(self, before, after=None, placeholder=None):
        editor = self.current_editor()
        if editor:
            editor.wrap_selection(before, after, placeholder or i18n.t("markdown.placeholder_text"))

    def markdown_heading(self, level):
        editor = self.current_editor()
        if editor:
            editor.prefix_lines("#" * level + " ", strip_pattern=r"^\s{0,3}#{1,6}\s*")

    def markdown_prefix(self, prefix, strip=None):
        editor = self.current_editor()
        if editor:
            editor.prefix_lines(prefix, strip_pattern=strip)

    def markdown_numbered(self):
        editor = self.current_editor()
        if editor is None:
            return
        editor.transform_text(
            lambda text: "\n".join(f"{index}. {line}" for index, line in enumerate(text.split("\n"), 1)), lines=True, whole_when_empty=False
        ) or editor.prefix_lines("1. ")

    def markdown_code_block(self):
        editor = self.current_editor()
        if editor is None:
            return
        selected = editor.selected_text()
        editor.replace_selection(f"```\n{selected or i18n.t('markdown.placeholder_code')}\n```")
        editor.setFocus()

    def markdown_link(self):
        editor = self.current_editor()
        if editor is None:
            return
        selected = editor.selected_text()
        cursor = editor.textCursor()
        clipboard = QGuiApplication.clipboard().text().strip()
        url = clipboard if clipboard.startswith(("http://", "https://")) else "https://"
        label = selected or i18n.t("markdown.placeholder_link")
        start = cursor.selectionStart()
        cursor.insertText(f"[{label}]({url})")
        url_start = start + len(label) + 3
        cursor.setPosition(url_start)
        cursor.setPosition(url_start + len(url), QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.setFocus()

    def markdown_rule(self):
        editor = self.current_editor()
        if editor:
            editor.insert_text("\n---\n")

    def markdown_table(self):
        editor = self.current_editor()
        if editor is None:
            return
        dialog = TableDialog(self)
        if dialog.exec():
            table = markdown_tools.build_table(dialog.columns(), dialog.rows(), i18n.t("table.header"))
            editor.insert_text("\n" + table + "\n")

    def markdown_format_table(self):
        editor = self.current_editor()
        if editor is None:
            return
        document = editor.document()
        lines = [document.findBlockByNumber(number).text() for number in range(document.blockCount())]
        index = editor.textCursor().blockNumber()
        found = markdown_tools.find_table_range(lines, index)
        if found is None:
            self.notify("warning", i18n.t("markdown.no_table"))
            return
        start, end = found
        formatted = markdown_tools.format_table(lines[start:end + 1])
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(document.findBlockByNumber(start).position())
        last = document.findBlockByNumber(end)
        cursor.setPosition(last.position() + last.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(formatted)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self.show_message(i18n.t("markdown.table_formatted"))

    def markdown_toc(self):
        editor = self.current_editor()
        if editor is None:
            return
        toc = markdown_tools.generate_toc(editor.text())
        if not toc:
            self.notify("warning", i18n.t("markdown.no_headings"))
            return
        editor.insert_text(toc + "\n")

    def markdown_insert_image(self):
        view = self.current_view()
        if view is None:
            return
        start = str(view.path.parent) if view.path else str(self.settings.notes_dir())
        selected, _ = QFileDialog.getOpenFileName(
            self, i18n.t("cmd.markdown.image"), start, i18n.t("filter.images")
        )
        if not selected:
            return
        target = Path(selected)
        if view.path:
            try:
                reference = os.path.relpath(target, view.path.parent).replace(os.sep, "/")
            except ValueError:
                reference = target.as_posix()
        else:
            reference = target.as_posix()
        view.editor.insert_text(f"![{target.stem}]({urllib.parse.quote(reference)})")

    def markdown_paste_image(self, image=None):
        view = self.current_view()
        if view is None:
            return
        image = image if image is not None and not isinstance(image, bool) else QGuiApplication.clipboard().image()
        if image is None or image.isNull():
            self.notify("warning", i18n.t("markdown.no_image"))
            return
        if view.path is None:
            if not self.save_view_as(view):
                return
        folder = view.path.parent / "images"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"image-{datetime.now():%Y%m%d-%H%M%S}.png"
        if not image.save(str(folder / name), "PNG"):
            self.notify("error", i18n.t("markdown.image_save_failed"))
            return
        view.editor.insert_text(f"![]({'images/' + name})")
        self.show_message(i18n.t("markdown.image_saved", name))

    def export_html(self):
        view = self.current_view()
        if view is None:
            return
        default = (view.path.with_suffix(".html") if view.path else self.settings.notes_dir() / f"{view.display_name()}.html")
        target, _ = QFileDialog.getSaveFileName(self, i18n.t("cmd.file.export_html"), str(default), "HTML (*.html)")
        if not target:
            return
        palette = PREVIEW_PALETTES[self.settings.get("preview_theme")]
        title = view.path.stem if view.path else view.display_name()
        try:
            Path(target).write_text(export_html_document(view.text(), title, palette), encoding="utf-8")
        except OSError as error:
            self.notify("error", str(error))
            return
        self.notify("success", i18n.t("export.done", Path(target).name))

    def export_pdf(self):
        view = self.current_view()
        if view is None:
            return
        default = (view.path.with_suffix(".pdf") if view.path else self.settings.notes_dir() / f"{view.display_name()}.pdf")
        target, _ = QFileDialog.getSaveFileName(self, i18n.t("cmd.file.export_pdf"), str(default), "PDF (*.pdf)")
        if not target:
            return
        palette = PREVIEW_PALETTES["light"]
        renderer = MarkdownRenderer(palette, view.preview.labels())
        result = renderer.render(view.text(), view.base_dir(), 640)
        document = QTextDocument()
        document.setDocumentMargin(0)
        for key, request in result.images.items():
            document.addResource(QTextDocument.ResourceType.ImageResource, QUrl(key), self.image_store.resolve(request, view.base_dir()))
        document.setHtml(result.html)
        writer = QPdfWriter(target)
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(16, 16, 16, 16), QPageLayout.Unit.Millimeter)
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        document.print_(writer)
        self.notify("success", i18n.t("export.done", Path(target).name))
