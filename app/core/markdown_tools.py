import re

FENCE_PATTERN = re.compile(r"^\s{0,3}(```|~~~)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
LIST_PATTERN = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)(\[[ xX]\]\s+)?")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")
TASK_PATTERN = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+)\[( |x|X)\](\s+.*)?$")


def extract_headings(text):
    headings = []
    in_fence = False
    for number, line in enumerate(text.split("\n"), 1):
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_PATTERN.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip(), number))
    return headings


def github_slug(title):
    cleaned = re.sub(r"[`*_~]", "", title.strip().lower())
    cleaned = re.sub(r"[^\w\- ]", "", cleaned, flags=re.UNICODE)
    return cleaned.replace(" ", "-")


def generate_toc(text, max_level=3):
    headings = [item for item in extract_headings(text) if item[0] <= max_level]
    if not headings:
        return ""
    base = min(level for level, _, _ in headings)
    seen = {}
    lines = []
    for level, title, _ in headings:
        slug = github_slug(title)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchor = slug if count == 0 else f"{slug}-{count}"
        clean_title = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", title)
        lines.append(f"{'  ' * (level - base)}- [{clean_title}](#{anchor})")
    return "\n".join(lines)


def split_row(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells = re.split(r"(?<!\\)\|", stripped)
    return [cell.strip() for cell in cells]


def display_width(text):
    import unicodedata

    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def format_table(lines):
    rows = [split_row(line) for line in lines if line.strip()]
    if len(rows) < 2:
        return "\n".join(lines)
    columns = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (columns - len(row)))
    separator = rows[1]
    alignments = []
    for cell in separator:
        left = cell.startswith(":")
        right = cell.endswith(":")
        alignments.append("center" if left and right else "right" if right else "left" if left else "none")
    body = [rows[0]] + rows[2:]
    widths = [max(3, max(display_width(row[index]) for row in body)) for index in range(columns)]

    def pad(cell, index):
        gap = widths[index] - display_width(cell)
        if alignments[index] == "right":
            return " " * gap + cell
        if alignments[index] == "center":
            left = gap // 2
            return " " * left + cell + " " * (gap - left)
        return cell + " " * gap

    def separator_cell(index):
        width = widths[index]
        kind = alignments[index]
        if kind == "center":
            return ":" + "-" * (width - 2) + ":"
        if kind == "right":
            return "-" * (width - 1) + ":"
        if kind == "left":
            return ":" + "-" * (width - 1)
        return "-" * width

    output = ["| " + " | ".join(pad(cell, index) for index, cell in enumerate(rows[0])) + " |"]
    output.append("| " + " | ".join(separator_cell(index) for index in range(columns)) + " |")
    for row in rows[2:]:
        output.append("| " + " | ".join(pad(cell, index) for index, cell in enumerate(row)) + " |")
    return "\n".join(output)


def find_table_range(lines, index):
    def is_table_line(position):
        return 0 <= position < len(lines) and "|" in lines[position] and lines[position].strip() != ""

    if not is_table_line(index):
        return None
    start = index
    while is_table_line(start - 1):
        start -= 1
    end = index
    while is_table_line(end + 1):
        end += 1
    if end - start < 1 or not TABLE_SEPARATOR_PATTERN.match(lines[start + 1]):
        return None
    return start, end


def build_table(columns, rows, header_prefix="Col"):
    header = [f"{header_prefix} {index + 1}" for index in range(columns)]
    lines = [header, ["---"] * columns] + [[""] * columns for _ in range(rows)]
    return format_table(["| " + " | ".join(row) + " |" for row in lines])


def toggle_task_line(line):
    task = TASK_PATTERN.match(line)
    if task:
        marker = " " if task.group(2) in ("x", "X") else "x"
        return f"{task.group(1)}[{marker}]{task.group(3) or ''}"
    item = LIST_PATTERN.match(line)
    if item:
        return line[: item.end()] + "[ ] " + line[item.end():]
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    return f"{indent}- [ ] {stripped}"


def list_continuation(line):
    match = LIST_PATTERN.match(line)
    if not match:
        return None
    indent, marker, _spacing, task = match.groups()
    content = line[match.end():]
    marker_text = marker
    number = re.match(r"(\d+)([.)])", marker)
    if number:
        marker_text = f"{int(number.group(1)) + 1}{number.group(2)}"
    prefix = f"{indent}{marker_text} " + ("[ ] " if task else "")
    return prefix, content.strip() == "", match.end()
