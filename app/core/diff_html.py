import difflib
import html

from ..theme import MUTED, TEXT

ADDED_BACKGROUND = "#12301f"
REMOVED_BACKGROUND = "#3a1a1d"
ADDED_COLOR = "#7ee2a8"
REMOVED_COLOR = "#ff9a9a"
HUNK_COLOR = "#7fd8ff"


def diff_lines(old_text, new_text, old_label, new_label):
    return list(
        difflib.unified_diff(
            old_text.split("\n"), new_text.split("\n"), fromfile=old_label, tofile=new_label, lineterm="", n=3
        )
    )


def diff_summary(lines):
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    return added, removed


def render_diff(lines):
    rows = []
    for line in lines:
        escaped = html.escape(line) or "&nbsp;"
        escaped = escaped.replace(" ", "&nbsp;")
        if line.startswith("+++") or line.startswith("---"):
            style = f"color:{MUTED};"
        elif line.startswith("@@"):
            style = f"color:{HUNK_COLOR};"
        elif line.startswith("+"):
            style = f"color:{ADDED_COLOR}; background-color:{ADDED_BACKGROUND};"
        elif line.startswith("-"):
            style = f"color:{REMOVED_COLOR}; background-color:{REMOVED_BACKGROUND};"
        else:
            style = f"color:{TEXT};"
        rows.append(f'<div style="{style} white-space:pre-wrap;">{escaped}</div>')
    return (
        f'<div style="font-family:\'JetBrains Mono\',\'DejaVu Sans Mono\',monospace; font-size:12px;">'
        + "".join(rows)
        + "</div>"
    )
