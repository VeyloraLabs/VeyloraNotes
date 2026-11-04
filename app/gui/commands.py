from dataclasses import dataclass, field
from functools import partial
from typing import Callable

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu

from .. import i18n
from ..icons import icon
from .tool_actions import TRANSFORMS


@dataclass
class Command:
    id: str
    callback: Callable
    category: str
    shortcut: str
    icon_name: str
    checkable: bool
    keywords: str
    action: QAction
    alternatives: list = field(default_factory=list)

    def label(self):
        return i18n.t(f"cmd.{self.id}")

    def shortcut_text(self):
        return QKeySequence(self.shortcut).toString(QKeySequence.SequenceFormat.NativeText) if self.shortcut else ""


class CommandRegistry:
    def __init__(self, window):
        self.window = window
        self.commands = {}
        self.menus = []

    def add(self, command_id, callback, category="cat.edit", shortcut="", icon_name="", checkable=False, keywords="", alternatives=()):
        action = QAction(self.window)
        if shortcut:
            sequences = [QKeySequence(shortcut)] + [QKeySequence(item) for item in alternatives]
            action.setShortcuts(sequences)
        if icon_name:
            action.setIcon(icon(icon_name))
        action.setCheckable(checkable)
        action.setIconVisibleInMenu(bool(icon_name))
        if checkable:
            action.triggered.connect(lambda checked, function=callback: function(checked))
        else:
            action.triggered.connect(lambda _checked=False, function=callback: function())
        self.window.addAction(action)
        command = Command(command_id, callback, category, shortcut, icon_name, checkable, keywords, action, list(alternatives))
        command.action.setText(command.label())
        self.commands[command_id] = command
        return action

    def action(self, command_id):
        return self.commands[command_id].action

    def set_checked(self, command_id, checked):
        action = self.commands[command_id].action
        action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(False)

    def retranslate(self):
        for command in self.commands.values():
            command.action.setText(command.label())
            shortcut = command.shortcut_text()
            command.action.setToolTip(f"{command.label()} ({shortcut})" if shortcut else command.label())
        for menu, key in self.menus:
            menu.setTitle(i18n.t(key))

    def reserved_shortcuts(self):
        blocked = {"Ctrl+Z", "Ctrl+Y", "Ctrl+X", "Ctrl+C", "Ctrl+V", "Ctrl+A", "Ctrl+Shift+Z"}
        sequences = set()
        for command in self.commands.values():
            for text in [command.shortcut, *command.alternatives]:
                normalized = QKeySequence(text).toString() if text else ""
                if normalized and normalized not in blocked:
                    sequences.add(normalized)
        return sequences

    def palette_rows(self):
        return [
            (i18n.t(command.category), command.label(), command.shortcut_text())
            for command in self.commands.values()
        ]

    def menu(self, title_key, parent=None):
        menu = QMenu(parent)
        menu.setTitle(i18n.t(title_key))
        self.menus.append((menu, title_key))
        return menu


def register_commands(window):
    registry = CommandRegistry(window)
    w = window
    ed = window.editor_call
    add = registry.add

    add("file.new", w.new_document, "cat.file", "Ctrl+N", "fa5s.plus")
    add("file.open", w.open_file_dialog, "cat.file", "Ctrl+O", "fa5s.folder-open")
    add("file.open_folder", w.choose_notes_folder, "cat.file", "Ctrl+Shift+O", "fa5s.folder")
    add("file.today", w.open_today_note, "cat.file", "Ctrl+Alt+D", "fa5s.calendar-day", keywords="diario journal")
    add("file.clear_recent", w.clear_recent, "cat.file")
    add("file.save", w.save_current, "cat.file", "Ctrl+S", "fa5s.save")
    add("file.save_as", w.save_current_as, "cat.file", "Ctrl+Shift+S", "fa5s.file-export")
    add("file.save_all", w.save_all, "cat.file", "Ctrl+Alt+S", "fa5s.layer-group")
    add("file.reload", w.reload_current, "cat.file", "Ctrl+Alt+R", "fa5s.sync-alt")
    add("file.reveal", w.reveal_current, "cat.file", icon_name="fa5s.external-link-alt")
    add("file.copy_path", w.copy_current_path, "cat.file", icon_name="fa5s.copy")
    add("file.export_html", w.export_html, "cat.file", icon_name="fa5s.file-code")
    add("file.export_pdf", w.export_pdf, "cat.file", icon_name="fa5s.file-pdf")
    add("file.close", w.close_current, "cat.file", "Ctrl+W", "fa5s.times")
    add("file.close_others", w.close_others, "cat.file")
    add("file.close_all", w.close_all_tabs, "cat.file", "Ctrl+Shift+W")
    add("file.quit", w.close, "cat.file", "Ctrl+Q", "fa5s.power-off")

    add("edit.undo", partial(ed, "undo"), "cat.edit", "Ctrl+Z", "fa5s.undo")
    add("edit.redo", partial(ed, "redo"), "cat.edit", "Ctrl+Y", "fa5s.redo", alternatives=("Ctrl+Shift+Z",))
    add("edit.cut", partial(ed, "cut"), "cat.edit", "Ctrl+X", "fa5s.cut")
    add("edit.copy", partial(ed, "copy"), "cat.edit", "Ctrl+C", "fa5s.copy")
    add("edit.paste", partial(ed, "paste"), "cat.edit", "Ctrl+V", "fa5s.paste")
    add("edit.select_all", partial(ed, "selectAll"), "cat.edit", "Ctrl+A")
    add("edit.duplicate", partial(ed, "duplicate_line"), "cat.edit", "Ctrl+D", "fa5s.clone")
    add("edit.delete_line", partial(ed, "delete_line"), "cat.edit", "Ctrl+Shift+K", "fa5s.trash-alt")
    add("edit.move_up", partial(ed, "move_lines", -1), "cat.edit", "Alt+Up", "fa5s.arrow-up")
    add("edit.move_down", partial(ed, "move_lines", 1), "cat.edit", "Alt+Down", "fa5s.arrow-down")
    add("edit.join", partial(ed, "join_lines"), "cat.edit", "Ctrl+J")
    add("edit.select_line", partial(ed, "select_line"), "cat.edit", "Ctrl+L")
    add("edit.indent", partial(ed, "indent_selection"), "cat.edit", "Ctrl+]", "fa5s.indent")
    add("edit.outdent", partial(ed, "outdent_selection"), "cat.edit", "Ctrl+[", "fa5s.outdent")
    add("edit.comment", partial(ed, "toggle_comment"), "cat.edit", "Ctrl+/", "fa5s.comment-slash", keywords="comentar comment")
    add("edit.find", w.open_find, "cat.edit", "Ctrl+F", "fa5s.search")
    add("edit.find_next", partial(w.find_step, True), "cat.edit", "F3")
    add("edit.find_previous", partial(w.find_step, False), "cat.edit", "Shift+F3")
    add("edit.replace", partial(w.open_find, True), "cat.edit", "Ctrl+H", "fa5s.exchange-alt")
    add("edit.find_in_folder", w.search_in_folder, "cat.edit", "Ctrl+Shift+F", "fa5s.folder-open")
    add("edit.go_to_line", w.go_to_line_dialog, "cat.edit", "Ctrl+G", "fa5s.level-down-alt")

    add("insert.date_time", partial(w.insert_now, "%Y-%m-%d %H:%M"), "cat.insert", "F5", "fa5s.clock")
    add("insert.date", partial(w.insert_now, "%Y-%m-%d"), "cat.insert", icon_name="fa5s.calendar-alt")
    add("insert.time", partial(w.insert_now, "%H:%M"), "cat.insert")
    add("insert.unix_time", w.insert_unix_time, "cat.insert")
    add("insert.uuid", partial(w.insert_generated, "uuid"), "cat.insert", icon_name="fa5s.fingerprint")
    add("insert.password", partial(w.insert_generated, "password"), "cat.insert", icon_name="fa5s.key", keywords="contraseña password")
    add("insert.lorem", partial(w.insert_generated, "lorem"), "cat.insert", icon_name="fa5s.paragraph")
    add("insert.color", w.insert_color, "cat.insert", icon_name="fa5s.palette")

    add("view.sidebar", w.toggle_sidebar, "cat.view", "Ctrl+\\", "fa5s.columns", checkable=True)
    add("view.files", partial(w.show_sidebar_panel, "files"), "cat.view", "Ctrl+Shift+E", "fa5s.folder")
    add("view.outline", partial(w.show_sidebar_panel, "outline"), "cat.view", icon_name="fa5s.list-ul")
    add("view.preview", w.cycle_preview, "cat.view", "Ctrl+Shift+V", "fa5s.eye")
    add("view.mode_editor", partial(w.set_view_mode, "editor"), "cat.view", icon_name="fa5s.pen", checkable=True)
    add("view.mode_split", partial(w.set_view_mode, "split"), "cat.view", icon_name="fa5s.columns", checkable=True)
    add("view.mode_preview", partial(w.set_view_mode, "preview"), "cat.view", icon_name="fa5s.eye", checkable=True)
    group = QActionGroup(window)
    group.setExclusive(True)
    for mode in ("editor", "split", "preview"):
        group.addAction(registry.action(f"view.mode_{mode}"))
    add("view.word_wrap", partial(w.toggle_setting, "word_wrap"), "cat.view", "Alt+Z", "fa5s.align-left", checkable=True)
    add("view.line_numbers", partial(w.toggle_setting, "line_numbers"), "cat.view", icon_name="fa5s.list-ol", checkable=True)
    add("view.whitespace", partial(w.toggle_setting, "show_whitespace"), "cat.view", icon_name="fa5s.paragraph", checkable=True)
    add("view.zoom_in", partial(w.zoom, 1), "cat.view", "Ctrl++", "fa5s.search-plus", alternatives=("Ctrl+=",))
    add("view.zoom_out", partial(w.zoom, -1), "cat.view", "Ctrl+-", "fa5s.search-minus")
    add("view.zoom_reset", partial(w.zoom, 0), "cat.view", "Ctrl+0")
    add("view.fullscreen", w.toggle_fullscreen, "cat.view", "F11", "fa5s.expand", checkable=True)
    add("view.focus_mode", w.toggle_focus_mode, "cat.view", "Ctrl+Alt+Z", "fa5s.bullseye", checkable=True, keywords="zen concentracion focus")
    add("view.next_tab", partial(w.step_tab, 1), "cat.view", "Ctrl+PgDown")
    add("view.previous_tab", partial(w.step_tab, -1), "cat.view", "Ctrl+PgUp")

    shortcuts = {"upper": "Ctrl+Shift+U", "lower": "Ctrl+U"}
    for name in TRANSFORMS:
        add(f"tool.{name}", partial(w.run_transform, name), "cat.text", shortcuts.get(name, ""))
    add("tool.join_comma", w.run_join_with_comma, "cat.text")
    add("tool.tabs_to_spaces", w.run_tabs_to_spaces, "cat.text")
    add("tool.spaces_to_tabs", w.run_spaces_to_tabs, "cat.text")
    add("tool.json_validate", w.validate_json, "cat.text")
    add("tool.calculate", w.calculate_selection, "cat.text", "Ctrl+Alt+Return", "fa5s.calculator", keywords="calcular math")
    add("tool.hashes", w.show_hashes, "cat.text", icon_name="fa5s.fingerprint", keywords="md5 sha")
    add("tool.stats", w.show_statistics, "cat.text", "Ctrl+Alt+I", "fa5s.chart-bar", keywords="palabras words count")
    for kind in ("urls", "emails", "numbers"):
        add(f"tool.extract_{kind}", partial(w.extract_items, kind), "cat.text")
    add("tool.compare_disk", w.compare_with_disk, "cat.text", icon_name="fa5s.balance-scale")
    add("tool.compare_clipboard", w.compare_with_clipboard, "cat.text", icon_name="fa5s.balance-scale")

    add("markdown.bold", partial(w.markdown_wrap, "**"), "cat.markdown", "Ctrl+B", "fa5s.bold")
    add("markdown.italic", partial(w.markdown_wrap, "*"), "cat.markdown", "Ctrl+I", "fa5s.italic")
    add("markdown.strike", partial(w.markdown_wrap, "~~"), "cat.markdown", "Ctrl+Shift+X", "fa5s.strikethrough")
    add("markdown.code", partial(w.markdown_wrap, "`"), "cat.markdown", "Ctrl+`", "fa5s.code")
    add("markdown.h1", partial(w.markdown_heading, 1), "cat.markdown", "Ctrl+1", "mdi6.format-header-1")
    add("markdown.h2", partial(w.markdown_heading, 2), "cat.markdown", "Ctrl+2", "mdi6.format-header-2")
    add("markdown.h3", partial(w.markdown_heading, 3), "cat.markdown", "Ctrl+3", "mdi6.format-header-3")
    add("markdown.bullets", partial(w.markdown_prefix, "- ", r"^\s*(?:[-*+]|\d+[.)])\s+"), "cat.markdown", "Ctrl+Shift+L", "fa5s.list-ul")
    add("markdown.numbered", w.markdown_numbered, "cat.markdown", icon_name="fa5s.list-ol")
    add("markdown.task", partial(ed, "toggle_task"), "cat.markdown", "Ctrl+Return", "fa5s.check-square", keywords="checklist tarea")
    add("markdown.quote", partial(w.markdown_prefix, "> ", r"^\s{0,3}>\s?"), "cat.markdown", "Ctrl+Shift+Q", "fa5s.quote-right")
    add("markdown.code_block", w.markdown_code_block, "cat.markdown", "Ctrl+Shift+C", "fa5s.terminal")
    add("markdown.rule", w.markdown_rule, "cat.markdown", icon_name="fa5s.minus")
    add("markdown.link", w.markdown_link, "cat.markdown", "Ctrl+K", "fa5s.link")
    add("markdown.image", w.markdown_insert_image, "cat.markdown", icon_name="fa5s.image")
    add("markdown.paste_image", w.markdown_paste_image, "cat.markdown", "Ctrl+Alt+V", "fa5s.paste", keywords="captura screenshot")
    add("markdown.table", w.markdown_table, "cat.markdown", icon_name="fa5s.table")
    add("markdown.format_table", w.markdown_format_table, "cat.markdown", icon_name="fa5s.table")
    add("markdown.toc", w.markdown_toc, "cat.markdown", icon_name="fa5s.list", keywords="indice contents")

    add("help.palette", w.open_palette, "cat.help", "Ctrl+Shift+P", "fa5s.bolt", keywords="comandos commands")
    add("help.quick_open", w.open_quick_open, "cat.help", "Ctrl+P", "fa5s.search", keywords="abrir archivo open file")
    add("help.shortcuts", w.show_shortcuts, "cat.help", "F1", "fa5s.keyboard")
    add("help.welcome", w.show_welcome, "cat.help", icon_name="fa5s.star")
    add("help.settings", w.show_settings, "cat.help", "Ctrl+,", "fa5s.cog", keywords="ajustes preferencias settings")
    add("help.updates", partial(w.check_updates, True), "cat.help", icon_name="fa5s.sync-alt")
    add("help.about", w.show_about, "cat.help", icon_name="fa5s.info-circle")
    add("status.language", w.show_language_menu, "cat.view", keywords="lenguaje language syntax")
    add("status.encoding", w.show_encoding_menu, "cat.view", keywords="codificacion encoding utf")
    add("status.eol", w.show_eol_menu, "cat.view", keywords="crlf lf saltos")
    return registry


MENU_LAYOUT = (
    ("menu.file", [
        "file.new", "file.open", "file.open_folder", "file.today", ("menu.recent", ["__recent__"]), None,
        "file.save", "file.save_as", "file.save_all", "file.reload", None,
        "file.reveal", "file.copy_path", ("menu.export", ["file.export_html", "file.export_pdf"]), None,
        "file.close", "file.close_others", "file.close_all", None, "file.quit",
    ]),
    ("menu.edit", [
        "edit.undo", "edit.redo", None, "edit.cut", "edit.copy", "edit.paste", "edit.select_all", None,
        "edit.duplicate", "edit.delete_line", "edit.move_up", "edit.move_down", "edit.join", "edit.select_line", None,
        "edit.indent", "edit.outdent", "edit.comment", None,
        "edit.find", "edit.find_next", "edit.find_previous", "edit.replace", "edit.find_in_folder", "edit.go_to_line", None,
        ("menu.insert", [
            "insert.date_time", "insert.date", "insert.time", "insert.unix_time", None,
            "insert.uuid", "insert.password", "insert.lorem", "insert.color",
        ]),
    ]),
    ("menu.view", [
        "view.sidebar", "view.files", "view.outline", None,
        "view.preview", "view.mode_editor", "view.mode_split", "view.mode_preview", None,
        "view.word_wrap", "view.line_numbers", "view.whitespace", None,
        "view.zoom_in", "view.zoom_out", "view.zoom_reset", None,
        "view.fullscreen", "view.focus_mode", None, "view.next_tab", "view.previous_tab", None,
        "status.language", "status.encoding", "status.eol",
    ]),
    ("menu.text", [
        ("menu.case", ["tool.upper", "tool.lower", "tool.title", "tool.sentence", "tool.invert"]),
        ("menu.style", ["tool.camel", "tool.pascal", "tool.snake", "tool.kebab", "tool.constant", "tool.slug", "tool.strip_accents"]),
        ("menu.lines", [
            "tool.sort_asc", "tool.sort_desc", "tool.sort_natural", "tool.reverse", "tool.unique", None,
            "tool.remove_empty", "tool.collapse_empty", "tool.trim_trailing", "tool.trim_all", None,
            "tool.number_lines", "tool.shuffle", "tool.join_comma",
        ]),
        ("menu.spaces", ["tool.tabs_to_spaces", "tool.spaces_to_tabs"]),
        ("menu.encode", [
            "tool.base64_encode", "tool.base64_decode", None, "tool.url_encode", "tool.url_decode", None,
            "tool.html_escape", "tool.html_unescape", None, "tool.hex_encode", "tool.hex_decode", None, "tool.rot13",
        ]),
        ("menu.json", ["tool.json_format", "tool.json_minify", "tool.json_validate"]),
        None,
        "tool.calculate", "tool.timestamp", "tool.hashes", "tool.stats", None,
        ("menu.extract", ["tool.extract_urls", "tool.extract_emails", "tool.extract_numbers"]),
        ("menu.compare", ["tool.compare_disk", "tool.compare_clipboard"]),
    ]),
    ("menu.markdown", [
        "markdown.bold", "markdown.italic", "markdown.strike", "markdown.code", None,
        "markdown.h1", "markdown.h2", "markdown.h3", None,
        "markdown.bullets", "markdown.numbered", "markdown.task", "markdown.quote", "markdown.code_block", "markdown.rule", None,
        "markdown.link", "markdown.image", "markdown.paste_image", None,
        "markdown.table", "markdown.format_table", "markdown.toc",
    ]),
    ("menu.help", [
        "help.palette", "help.quick_open", "help.shortcuts", "help.welcome", None, "help.settings", "help.updates", "help.about",
    ]),
)
