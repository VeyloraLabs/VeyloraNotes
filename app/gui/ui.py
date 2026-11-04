from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QToolButton

from ..icons import icon
from ..theme import BORDER, MUTED, TEXT


def tool_button(icon_name=None, tooltip="", checkable=False, text="", size=32, icon_size=16, parent=None):
    button = QToolButton(parent)
    button.setToolTip(tooltip)
    button.setCheckable(checkable)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        button.setIcon(icon(icon_name, MUTED, TEXT))
        button.setIconSize(QSize(icon_size, icon_size))
    if text:
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly if not icon_name else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setFixedHeight(size)
    if not text:
        button.setFixedWidth(size)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button


def separator(height=18):
    line = QFrame()
    line.setFixedSize(1, height)
    line.setStyleSheet(f"background: {BORDER};")
    return line


def link_button(text, tooltip=""):
    button = QToolButton()
    button.setObjectName("flatLink")
    button.setText(text)
    button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button

