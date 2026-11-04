import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

from ..theme import SYNTAX

NORMAL = 0
BLOCK_COMMENT = 1
TRIPLE_DOUBLE = 2
TRIPLE_SINGLE = 3
BACKTICK = 4
FENCE = 5
MAX_HIGHLIGHT_CHARACTERS = 1_500_000


def make_format(name, bold=False, italic=False, underline=False):
    result = QTextCharFormat()
    result.setForeground(QColor(SYNTAX[name]))
    if bold:
        result.setFontWeight(QFont.Weight.Bold)
    if italic:
        result.setFontItalic(True)
    if underline:
        result.setFontUnderline(True)
    return result


def formats():
    return {
        "keyword": make_format("keyword", bold=True),
        "string": make_format("string"),
        "number": make_format("number"),
        "comment": make_format("comment", italic=True),
        "function": make_format("function"),
        "type": make_format("type"),
        "literal": make_format("literal"),
        "operator": make_format("operator"),
        "decorator": make_format("decorator"),
        "tag": make_format("tag"),
        "attribute": make_format("attribute"),
        "key": make_format("key"),
        "variable": make_format("attribute"),
        "added": make_format("added"),
        "removed": make_format("removed"),
        "hunk": make_format("hunk"),
    }


class Utf16Highlighter(QSyntaxHighlighter):
    offsets = None

    def prepare(self, text):
        if text.isascii() or all(ord(char) <= 0xFFFF for char in text):
            self.offsets = None
            return
        offsets = [0]
        for char in text:
            offsets.append(offsets[-1] + (2 if ord(char) > 0xFFFF else 1))
        self.offsets = offsets

    def mark(self, start, length, text_format):
        if self.offsets is None:
            self.setFormat(start, length, text_format)
            return
        last = len(self.offsets) - 1
        begin = self.offsets[min(start, last)]
        end = self.offsets[min(start + length, last)]
        self.setFormat(begin, end - begin, text_format)


class MarkdownHighlighter(Utf16Highlighter):
    HEADING = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
    FENCE_LINE = re.compile(r"^\s{0,3}(```|~~~)")
    QUOTE = re.compile(r"^\s{0,3}>")
    RULE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
    LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+[.)])(\s+)(\[[ xX]\])?")
    INLINE = (
        ("italic", re.compile(r"(?<![\w*])\*(?!\s)[^*\n]+?(?<!\s)\*(?![\w*])|(?<![\w_])_(?!\s)[^_\n]+?(?<!\s)_(?![\w_])")),
        ("bold", re.compile(r"\*\*(?!\s)[^*\n]+?(?<!\s)\*\*|__(?!\s)[^_\n]+?(?<!\s)__")),
        ("strike", re.compile(r"~~[^~\n]+?~~")),
        ("link", re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)|<https?://[^>\s]+>|https?://[^\s<>)\]]+")),
        ("tag", re.compile(r"</?[A-Za-z][\w:-]*(?:\s+[\w:-]+(?:=(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?)*\s*/?>")),
        ("code", re.compile(r"`[^`\n]+`")),
    )

    def __init__(self, document):
        super().__init__(document)
        self.heading = make_format("heading", bold=True)
        self.bold = make_format("bold", bold=True)
        self.italic = make_format("italic", italic=True)
        self.strike = make_format("comment")
        self.strike.setFontStrikeOut(True)
        self.link = make_format("link")
        self.code = make_format("code")
        self.quote = make_format("quote", italic=True)
        self.marker = make_format("marker", bold=True)
        self.comment = make_format("comment", italic=True)
        self.tag = make_format("tag")
        self.table = make_format("operator")
        self.formats = {
            "italic": self.italic,
            "bold": self.bold,
            "strike": self.strike,
            "link": self.link,
            "code": self.code,
            "tag": self.tag,
        }

    def highlightBlock(self, text):
        self.prepare(text)
        state = self.previousBlockState()
        if state == FENCE:
            self.mark(0, len(text), self.code)
            self.setCurrentBlockState(NORMAL if self.FENCE_LINE.match(text) else FENCE)
            return
        if state == BLOCK_COMMENT:
            end = text.find("-->")
            if end == -1:
                self.mark(0, len(text), self.comment)
                self.setCurrentBlockState(BLOCK_COMMENT)
                return
            self.mark(0, end + 3, self.comment)
            self.setCurrentBlockState(NORMAL)
            return
        self.setCurrentBlockState(NORMAL)
        if self.FENCE_LINE.match(text):
            self.mark(0, len(text), self.code)
            self.setCurrentBlockState(FENCE)
            return
        if text.lstrip().startswith("<!--") and "-->" not in text:
            self.mark(0, len(text), self.comment)
            self.setCurrentBlockState(BLOCK_COMMENT)
            return
        if self.HEADING.match(text):
            self.mark(0, len(text), self.heading)
            return
        if self.RULE.match(text):
            self.mark(0, len(text), self.marker)
            return
        for name, pattern in self.INLINE:
            for match in pattern.finditer(text):
                self.mark(match.start(), match.end() - match.start(), self.formats[name])
        if self.QUOTE.match(text):
            index = text.index(">")
            self.mark(index, 1, self.marker)
        item = self.LIST_MARKER.match(text)
        if item:
            marker_start = len(item.group(1))
            self.mark(marker_start, len(item.group(2)), self.marker)
            if item.group(4):
                start = item.start(4)
                self.mark(start, 3, self.marker)
        if "|" in text:
            for match in re.finditer(r"\|", text):
                self.mark(match.start(), 1, self.table)


class CodeHighlighter(Utf16Highlighter):
    def __init__(self, document, language):
        super().__init__(document)
        self.language = language
        self.formats = formats()
        self.keywords = {word.lower() for word in language.keywords} if language.case_insensitive else language.keywords
        self.literals = {word.lower() for word in language.literals} if language.case_insensitive else language.literals
        self.is_json = language.id == "json"
        self.is_shell = language.id == "shell"
        self.block_start, self.block_end = language.block_comment if language.block_comment else ("", "")
        parts = []
        if self.block_start:
            parts.append(f"(?P<block>{re.escape(self.block_start)})")
        if language.line_comment:
            parts.append(f"(?P<line>{re.escape(language.line_comment)})")
        if language.triple_quotes:
            parts.append('(?P<triple_double>""")')
            parts.append("(?P<triple_single>''')")
        if "`" in language.quotes:
            parts.append("(?P<backtick>`)")
        for index, quote in enumerate(language.quotes.replace("`", "")):
            escaped = re.escape(quote)
            parts.append(f"(?P<string{index}>{escaped}(?:\\\\.|[^{escaped}\\\\\\n])*(?:{escaped}|$))")
        if self.is_shell:
            parts.append(r"(?P<variable>\$\{?[A-Za-z_]\w*\}?|\$[@#?$!0-9*])")
        if language.id in ("python", "java", "javascript", "typescript", "csharp", "rust"):
            parts.append(r"(?P<decorator>@[A-Za-z_][\w.]*|#!?\[[^\]]*\])")
        parts.append(r"(?P<number>\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*(?:\.\d+)?(?:[eE][-+]?\d+)?)\b)")
        parts.append(r"(?P<word>[A-Za-z_][\w]*)")
        self.pattern = re.compile("|".join(parts))
        self.terminators = {
            BLOCK_COMMENT: self.block_end,
            TRIPLE_DOUBLE: '"""',
            TRIPLE_SINGLE: "'''",
            BACKTICK: "`",
        }
        self.state_formats = {
            BLOCK_COMMENT: self.formats["comment"],
            TRIPLE_DOUBLE: self.formats["string"],
            TRIPLE_SINGLE: self.formats["string"],
            BACKTICK: self.formats["string"],
        }

    def highlightBlock(self, text):
        self.prepare(text)
        state = self.previousBlockState()
        position = 0
        if state in self.terminators:
            end = text.find(self.terminators[state])
            if end == -1:
                self.mark(0, len(text), self.state_formats[state])
                self.setCurrentBlockState(state)
                return
            position = end + len(self.terminators[state])
            self.mark(0, position, self.state_formats[state])
        self.setCurrentBlockState(NORMAL)
        while True:
            match = self.pattern.search(text, position)
            if not match:
                break
            kind = match.lastgroup
            start = match.start()
            if kind == "line":
                self.mark(start, len(text) - start, self.formats["comment"])
                break
            if kind in ("block", "triple_double", "triple_single", "backtick"):
                opened = {"block": BLOCK_COMMENT, "triple_double": TRIPLE_DOUBLE, "triple_single": TRIPLE_SINGLE, "backtick": BACKTICK}[kind]
                terminator = self.terminators[opened]
                end = text.find(terminator, match.end())
                if end == -1:
                    self.mark(start, len(text) - start, self.state_formats[opened])
                    self.setCurrentBlockState(opened)
                    break
                finish = end + len(terminator)
                self.mark(start, finish - start, self.state_formats[opened])
                position = finish
                continue
            length = match.end() - start
            if kind.startswith("string"):
                is_key = self.is_json and re.match(r"\s*:", text[match.end():])
                self.mark(start, length, self.formats["key" if is_key else "string"])
            elif kind == "word":
                self.format_word(text, match, start, length)
            else:
                self.mark(start, length, self.formats[{"number": "number", "decorator": "decorator", "variable": "variable"}[kind]])
            position = match.end()

    def format_word(self, text, match, start, length):
        word = match.group(0)
        lookup = word.lower() if self.language.case_insensitive else word
        if lookup in self.keywords:
            self.mark(start, length, self.formats["keyword"])
        elif lookup in self.literals:
            self.mark(start, length, self.formats["literal"])
        elif re.match(r"\s*\(", text[match.end():]):
            self.mark(start, length, self.formats["function"])
        elif word[0].isupper() and not word.isupper() and not self.is_shell:
            self.mark(start, length, self.formats["type"])


def compile_rules(rules):
    return [(re.compile(pattern, flags), name) for pattern, name, flags in rules]


RULES = {
    "yaml": compile_rules(
        [
            (r"^\s*-\s", "operator", 0),
            (r"^\s*-?\s*[\w.\-\"']+(?=\s*:(\s|$))", "key", 0),
            (r"\b(?:true|false|null|yes|no|on|off)\b|~", "literal", re.IGNORECASE),
            (r"(?<![\w.])-?\d+(?:\.\d+)?\b", "number", 0),
            (r"\"(?:\\.|[^\"\\])*\"|'[^']*'", "string", 0),
            (r"[&*][\w-]+", "decorator", 0),
            (r"(?:^|\s)#.*$", "comment", 0),
        ]
    ),
    "toml": compile_rules(
        [
            (r"^\s*\[[^\]]*\]", "type", 0),
            (r"^\s*[\w.\-]+(?=\s*[=:])", "key", 0),
            (r"\b(?:true|false)\b", "literal", 0),
            (r"(?<![\w.])-?\d+(?:\.\d+)?\b", "number", 0),
            (r"\"(?:\\.|[^\"\\])*\"|'[^']*'", "string", 0),
            (r"(?:^|\s)[#;].*$", "comment", 0),
        ]
    ),
    "html": compile_rules(
        [
            (r"&#?\w+;", "number", 0),
            (r"</?[A-Za-z][\w:-]*|/?>", "tag", 0),
            (r"\b[\w:@.-]+(?==)", "attribute", 0),
            (r"\"[^\"]*\"|'[^']*'", "string", 0),
            (r"<![^>]*>|<\?.*?\?>", "decorator", 0),
        ]
    ),
    "css": compile_rules(
        [
            (r"[.#][A-Za-z_][\w-]*", "type", 0),
            (r"@[\w-]+", "keyword", 0),
            (r"[\w-]+(?=\s*:)", "attribute", 0),
            (r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms|deg|fr)?\b", "number", 0),
            (r"!important", "keyword", 0),
            (r"\"[^\"]*\"|'[^']*'", "string", 0),
            (r"//.*$", "comment", 0),
        ]
    ),
    "diff": compile_rules(
        [
            (r"^(?:diff|index|---|\+\+\+).*$", "comment", 0),
            (r"^@@.*$", "hunk", 0),
            (r"^\+(?!\+\+).*$", "added", 0),
            (r"^-(?!--).*$", "removed", 0),
        ]
    ),
}
RULES["xml"] = RULES["html"]


class RuleHighlighter(Utf16Highlighter):
    def __init__(self, document, language):
        super().__init__(document)
        self.formats = formats()
        key = language.id
        self.rules = RULES.get(key, [])
        self.block_start, self.block_end = language.block_comment if language.block_comment else ("", "")

    def highlightBlock(self, text):
        self.prepare(text)
        for pattern, name in self.rules:
            for match in pattern.finditer(text):
                if match.end() > match.start():
                    self.mark(match.start(), match.end() - match.start(), self.formats[name])
        self.setCurrentBlockState(NORMAL)
        if self.block_start:
            self.apply_block_comments(text)

    def apply_block_comments(self, text):
        comment = self.formats["comment"]
        inside = self.previousBlockState() == BLOCK_COMMENT
        position = 0
        while position <= len(text):
            if inside:
                end = text.find(self.block_end, position)
                if end == -1:
                    self.mark(position, len(text) - position, comment)
                    self.setCurrentBlockState(BLOCK_COMMENT)
                    return
                finish = end + len(self.block_end)
                self.mark(position, finish - position, comment)
                position = finish
                inside = False
            else:
                start = text.find(self.block_start, position)
                if start == -1:
                    return
                inside = True
                self.mark(start, len(self.block_start), comment)
                position = start + len(self.block_start)


def create_highlighter(document, language):
    if language.engine == "markdown":
        return MarkdownHighlighter(document)
    if language.engine == "code":
        return CodeHighlighter(document, language)
    if language.engine == "rules":
        return RuleHighlighter(document, language)
    return None
