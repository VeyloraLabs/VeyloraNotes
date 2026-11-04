import conftest_env
import ast
import re
import sys
from pathlib import Path

from app.strings import STRINGS

ROOT = Path(conftest_env.ROOT)
used = set()
dynamic = set()
for path in list((ROOT / "app").rglob("*.py")):
    if path.name == "strings.py":
        continue
    source = path.read_text()
    for match in re.finditer(r"""\bt\(\s*(f?)["']([^"']+)["']""", source):
        fstring, key = match.groups()
        if fstring or "{" in key:
            dynamic.add(key)
        else:
            used.add(key)
    for match in re.finditer(r"""i18n\.t\(\s*(f?)["']([^"']+)["']""", source):
        fstring, key = match.groups()
        if fstring or "{" in key:
            dynamic.add(key)
        else:
            used.add(key)
    for match in re.finditer(r"""add\(\s*"([\w.]+)\"""", source):
        used.add("cmd." + match.group(1))
    for match in re.finditer(r"""\(\s*"(menu\.[\w.]+)\"""", source):
        used.add(match.group(1))
    for match in re.finditer(r""""(menu\.[\w]+)\"""", source):
        used.add(match.group(1))
    for match in re.finditer(r""""((?:cat|doc)\.[\w]+)\"""", source):
        used.add(match.group(1))
from app.gui.tool_actions import TRANSFORMS
for name in TRANSFORMS:
    used.add(f"cmd.tool.{name}")
for name in ("urls", "emails", "numbers"):
    used.add(f"tools.extract_title.{name}")
for key in ("files", "outline", "search"):
    used.add(f"sidebar.tab.{key}")
for key in ("words", "characters", "characters_no_spaces", "lines", "paragraphs", "sentences", "bytes", "reading"):
    used.add(f"stats.{key}")
for key in ("LF", "CRLF", "CR"):
    used.add(f"eol.{key}")
for key in ("success", "error", "warning", "info"):
    used.add(f"notify.{key}")
missing = sorted(key for key in used if key not in STRINGS)
unused = sorted(key for key in STRINGS if key not in used and not any(key.startswith(d.split("{")[0]) for d in dynamic))
print("MISSING", len(missing))
for key in missing:
    print("  ", key)
print("UNUSED", len(unused))
for key in unused:
    print("  ", key)
print("dynamic:", sorted(dynamic))
