from PySide6.QtGui import QColor, QPalette
from qfluentwidgets import Theme, setTheme, setThemeColor

ACCENT = "#00f49f"
ACCENT_HOVER = "#30ffb0"
ACCENT_TEXT = "#07120d"
BG = "#111315"
PANEL = "#171a1d"
CARD = "#1d2125"
BORDER = "#2a3035"
MUTED = "#858e95"
TEXT = "#e9eeeb"
EDITOR_BG = "#14171a"
GUTTER = "#566066"
CURRENT_LINE = "#1a1f22"
HOVER = "#232a28"
SELECTED = "#202b26"
SELECTED_BORDER = "#244737"
WARNING = "#f0b857"
DANGER = "#ff6b6b"
SELECTION = "#1f5c46"
MATCH = "#4c3f12"
MATCH_CURRENT = "#8a6d00"
OCCURRENCE = "#25302c"
BRACKET = "#2d5f4b"

SYNTAX = {
    "keyword": "#c4a7ff",
    "string": "#f0c987",
    "number": "#ff9e64",
    "comment": "#66756e",
    "function": "#7fd8ff",
    "type": "#5eead4",
    "literal": "#ff9e64",
    "operator": "#9fb0a8",
    "decorator": "#e9a6ff",
    "tag": "#ff7b9c",
    "attribute": "#f0c987",
    "key": "#00f49f",
    "heading": "#00f49f",
    "link": "#7fd8ff",
    "code": "#f0c987",
    "bold": "#ffffff",
    "italic": "#d6e4dd",
    "quote": "#8aa39a",
    "marker": "#ff7b9c",
    "added": "#7ee2a8",
    "removed": "#ff9a9a",
    "hunk": "#7fd8ff",
}

PREVIEW_PALETTES = {
    "dark": {
        "background": "#0d1117",
        "text": "#e6edf3",
        "muted": "#9198a1",
        "border": "#3d444d",
        "soft_border": "#30363d",
        "code_background": "#151b23",
        "inline_code_background": "#262c36",
        "link": "#4493f8",
        "table_stripe": "#151b23",
        "quote_bar": "#3d444d",
        "check_done": "#3fb950",
        "alert_note": "#4493f8",
        "alert_tip": "#3fb950",
        "alert_important": "#ab7df8",
        "alert_warning": "#d29922",
        "alert_caution": "#f85149",
        "syntax": {
            "keyword": "#ff7b72", "string": "#a5d6ff", "comment": "#8b949e", "number": "#79c0ff",
            "function": "#d2a8ff", "class": "#ffa657", "builtin": "#79c0ff", "operator": "#ff7b72",
            "tag": "#7ee787", "attribute": "#79c0ff", "decorator": "#d2a8ff", "constant": "#79c0ff",
            "deleted": "#ffdcd7", "inserted": "#aff5b4", "heading": "#79c0ff",
        },
    },
    "light": {
        "background": "#ffffff",
        "text": "#1f2328",
        "muted": "#59636e",
        "border": "#d1d9e0",
        "soft_border": "#d8dee4",
        "code_background": "#f6f8fa",
        "inline_code_background": "#eaeef2",
        "link": "#0969da",
        "table_stripe": "#f6f8fa",
        "quote_bar": "#d1d9e0",
        "check_done": "#1a7f37",
        "alert_note": "#0969da",
        "alert_tip": "#1a7f37",
        "alert_important": "#8250df",
        "alert_warning": "#9a6700",
        "alert_caution": "#d1242f",
        "syntax": {
            "keyword": "#cf222e", "string": "#0a3069", "comment": "#59636e", "number": "#0550ae",
            "function": "#8250df", "class": "#953800", "builtin": "#0550ae", "operator": "#cf222e",
            "tag": "#116329", "attribute": "#0550ae", "decorator": "#8250df", "constant": "#0550ae",
            "deleted": "#82071e", "inserted": "#116329", "heading": "#0550ae",
        },
    },
}


def build_palette():
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: PANEL,
        QPalette.ColorRole.AlternateBase: CARD,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: CARD,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: SELECTION,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: CARD,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: ACCENT,
        QPalette.ColorRole.BrightText: "#ffffff",
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#5b6469"))
    return palette


def stylesheet():
    return f"""
        QMainWindow, QDialog {{ background: {BG}; }}
        QWidget {{ color: {TEXT}; }}
        QLabel {{ background: transparent; }}
        QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px 8px; }}

        QLineEdit, QPlainTextEdit, QTextBrowser, QListWidget, QTreeView, QListView, QTextEdit {{
            background: {PANEL}; border: 1px solid {BORDER}; border-radius: 9px;
            selection-background-color: {SELECTION}; selection-color: #ffffff;
        }}
        QLineEdit {{ padding: 7px 11px; }}
        QLineEdit:focus {{ border-color: {ACCENT}; }}
        QListWidget, QTreeView, QListView {{ padding: 4px; outline: none; }}
        QListWidget::item, QTreeView::item {{ border: none; border-radius: 7px; padding: 4px 6px; }}
        QListWidget::item:selected, QTreeView::item:selected {{ background: {SELECTED}; color: {TEXT}; }}
        QListWidget::item:hover:!selected, QTreeView::item:hover:!selected {{ background: {CARD}; }}
        QTreeView::branch {{ background: transparent; }}

        QPushButton, PushButton {{
            background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 14px; color: {TEXT};
        }}
        QPushButton:hover, PushButton:hover {{ border-color: {ACCENT}; background: {HOVER}; }}
        QPushButton:pressed, PushButton:pressed {{ background: #18251f; }}
        QPushButton:disabled, PushButton:disabled {{ color: #5b6469; border-color: {BORDER}; }}
        PrimaryPushButton {{
            background: {ACCENT}; border: 1px solid {ACCENT}; border-radius: 8px; padding: 7px 14px;
            color: {ACCENT_TEXT}; font-weight: 700;
        }}
        PrimaryPushButton:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
        PrimaryPushButton:disabled {{ background: #1f3a2f; border-color: #1f3a2f; color: #5b7a6b; }}
        SearchLineEdit {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 11px; }}

        QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 5px; color: {TEXT}; }}
        QToolButton:hover {{ background: {HOVER}; }}
        QToolButton:pressed {{ background: #18251f; }}
        QToolButton:checked {{ background: {SELECTED}; border-color: {SELECTED_BORDER}; }}
        QToolButton:disabled {{ color: #5b6469; }}
        QToolButton::menu-indicator {{ image: none; width: 0; }}
        QToolButton#flatLink {{ padding: 2px 8px; color: {MUTED}; font-size: 11px; border-radius: 6px; }}
        QToolButton#flatLink:hover {{ color: {TEXT}; background: {HOVER}; }}

        QMenuBar {{ background: transparent; color: {TEXT}; spacing: 2px; }}
        QMenuBar::item {{ background: transparent; padding: 6px 11px; border-radius: 7px; }}
        QMenuBar::item:selected {{ background: {HOVER}; }}
        QMenuBar::item:pressed {{ background: {SELECTED}; }}
        QMenu {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 9px; padding: 6px; }}
        QMenu::item {{ padding: 7px 30px 7px 12px; border-radius: 6px; margin: 1px 0; }}
        QMenu::item:selected {{ background: {SELECTED}; color: {TEXT}; }}
        QMenu::item:disabled {{ color: #5b6469; }}
        QMenu::icon {{ padding-left: 6px; }}
        QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
        QMenu::right-arrow {{ margin-right: 8px; }}

        QTabBar#documentTabs {{ background: transparent; qproperty-drawBase: 0; }}
        QTabBar#documentTabs::tab {{
            background: transparent; color: {MUTED}; padding: 8px 6px 8px 14px; margin: 6px 2px 0 0;
            border-top-left-radius: 9px; border-top-right-radius: 9px; border: 1px solid transparent; border-bottom: none;
            min-width: 96px; max-width: 230px;
        }}
        QTabBar#documentTabs::tab:hover:!selected {{ background: {CARD}; color: {TEXT}; }}
        QTabBar#documentTabs::tab:selected {{
            background: {EDITOR_BG}; color: {TEXT}; border-color: {BORDER}; border-top: 2px solid {ACCENT};
        }}
        QTabBar::scroller {{ width: 26px; }}
        QTabBar QToolButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 2px; }}

        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: #39423e; border-radius: 4px; min-height: 30px; }}
        QScrollBar::handle:vertical:hover {{ background: #4a5650; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: #39423e; border-radius: 4px; min-width: 30px; }}
        QScrollBar::handle:horizontal:hover {{ background: #4a5650; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

        QSplitter::handle {{ background: {BG}; }}
        QSplitter::handle:hover {{ background: {BORDER}; }}

        QMessageBox {{ background: {BG}; }}
        QMessageBox QLabel {{ color: {TEXT}; }}
        QHeaderView::section {{ background: {PANEL}; color: {MUTED}; border: none; padding: 6px; }}
        QGroupBox {{ border: 1px solid {BORDER}; border-radius: 10px; margin-top: 12px; padding: 14px 10px 10px 10px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {MUTED}; }}
    """


def apply(app):
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    setTheme(Theme.DARK)
    setThemeColor(QColor(ACCENT), save=False)
    app.setStyleSheet(stylesheet())
