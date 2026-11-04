import html
import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token

from .markdown_tools import github_slug

try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name
    from pygments.token import Token as PygmentsToken
    from pygments.util import ClassNotFound
except ImportError:
    lex = None

MONO_FAMILY = "'JetBrains Mono','Fira Code','DejaVu Sans Mono','Liberation Mono',monospace"
SANS_FAMILY = "'Inter','Segoe UI','Noto Sans','DejaVu Sans',sans-serif"
HEADING_SIZES = {1: 30, 2: 23, 3: 18, 4: 16, 5: 14, 6: 13}
ALERTS = {
    "NOTE": ("alert_note", "ℹ", "Note"),
    "TIP": ("alert_tip", "💡", "Tip"),
    "IMPORTANT": ("alert_important", "❗", "Important"),
    "WARNING": ("alert_warning", "⚠", "Warning"),
    "CAUTION": ("alert_caution", "⛔", "Caution"),
}
MAX_HIGHLIGHT_CHARACTERS = 60000
FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
IMAGE_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ATTRIBUTE = re.compile(r"([\w:-]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class ImageRequest:
    source: str
    alt: str
    max_width: int


@dataclass
class RenderResult:
    html: str
    images: dict = field(default_factory=dict)
    title: str = ""


def pygments_color(token_type, colors):
    mapping = (
        (PygmentsToken.Comment, "comment"),
        (PygmentsToken.Keyword.Type, "class"),
        (PygmentsToken.Keyword, "keyword"),
        (PygmentsToken.Literal.String, "string"),
        (PygmentsToken.Literal.Number, "number"),
        (PygmentsToken.Name.Function, "function"),
        (PygmentsToken.Name.Class, "class"),
        (PygmentsToken.Name.Namespace, "class"),
        (PygmentsToken.Name.Builtin, "builtin"),
        (PygmentsToken.Name.Decorator, "decorator"),
        (PygmentsToken.Name.Tag, "tag"),
        (PygmentsToken.Name.Attribute, "attribute"),
        (PygmentsToken.Name.Constant, "constant"),
        (PygmentsToken.Operator, "operator"),
        (PygmentsToken.Generic.Deleted, "deleted"),
        (PygmentsToken.Generic.Inserted, "inserted"),
        (PygmentsToken.Generic.Heading, "heading"),
        (PygmentsToken.Generic.Subheading, "heading"),
    )
    for parent, name in mapping:
        if token_type in parent:
            return colors.get(name)
    return None


def highlight_code(code, language, colors):
    code = code.rstrip("\n").replace("\t", "    ")
    if lex is None or not language or len(code) > MAX_HIGHLIGHT_CHARACTERS:
        return html.escape(code)
    try:
        lexer = get_lexer_by_name(language.split()[0].strip("{}."), stripnl=False)
    except ClassNotFound:
        return html.escape(code)
    pieces = []
    for token_type, value in lex(code, lexer):
        escaped = html.escape(value)
        color = pygments_color(token_type, colors)
        pieces.append(f'<span style="color:{color}">{escaped}</span>' if color and value.strip() else escaped)
    return "".join(pieces)


def parse_attributes(tag):
    attributes = {}
    for name, value in ATTRIBUTE.findall(tag):
        attributes[name.lower()] = value.strip("\"'")
    return attributes


class QtRenderer(RendererHTML):
    def register_image(self, env, source, alt, max_width):
        key = f"vnimg://{len(env['images'])}"
        env["images"][key] = ImageRequest(source, alt, max_width)
        return key

    def image_max_width(self, env):
        columns = env.get("table_columns", 0)
        width = env["max_width"]
        if columns > 1:
            return max(120, width // columns - 28)
        if env.get("html_table_depth", 0) > 0:
            return max(120, width // 2 - 28)
        return width

    def fence(self, tokens, idx, options, env):
        token = tokens[idx]
        palette = env["palette"]
        language = (token.info or "").strip()
        body = highlight_code(token.content, language, palette["syntax"])
        caption = ""
        if language.split()[:1] == ["mermaid"]:
            caption = (
                f'<p style="margin:0 0 6px 0; color:{palette["muted"]}; font-size:11px;">'
                f'{html.escape(env["settings"]["mermaid_note"])}</p>'
            )
        return self.code_box(body, palette, caption)

    def code_block(self, tokens, idx, options, env):
        body = html.escape(tokens[idx].content.rstrip("\n").replace("\t", "    "))
        return self.code_box(body, env["palette"], "")

    def code_box(self, body, palette, caption):
        return (
            f'<table width="100%" cellspacing="0" cellpadding="11" '
            f'style="background-color:{palette["code_background"]}; border:1px solid {palette["soft_border"]}; '
            f'margin-top:2px; margin-bottom:14px;"><tr><td>{caption}'
            f'<pre style="margin:0; white-space:pre-wrap; font-family:{MONO_FAMILY}; font-size:13px; '
            f'color:{palette["text"]};">{body}</pre></td></tr></table>'
        )

    def code_inline(self, tokens, idx, options, env):
        palette = env["palette"]
        return (
            f'<code style="background-color:{palette["inline_code_background"]}; font-family:{MONO_FAMILY}; '
            f'font-size:13px; color:{palette["text"]};">&nbsp;{html.escape(tokens[idx].content)}&nbsp;</code>'
        )

    def heading_open(self, tokens, idx, options, env):
        token = tokens[idx]
        level = int(token.tag[1])
        title = tokens[idx + 1].content
        slug = github_slug(title)
        count = env["slugs"].get(slug, 0)
        env["slugs"][slug] = count + 1
        anchor = slug if count == 0 else f"{slug}-{count}"
        if level == 1 and not env["title"]:
            env["title"] = re.sub(r"[`*_]", "", title)
        top = 24 if level <= 2 else 20
        return (
            f'<p style="margin-top:{top}px; margin-bottom:{6 if level <= 2 else 10}px;">'
            f'<a name="{html.escape(anchor)}"></a>'
            f'<span style="font-size:{HEADING_SIZES[level]}px; font-weight:700; '
            f'color:{env["palette"]["text"] if level != 6 else env["palette"]["muted"]};">'
        )

    def heading_close(self, tokens, idx, options, env):
        level = int(tokens[idx].tag[1])
        closing = "</span></p>"
        if level <= 2:
            palette = env["palette"]
            closing += (
                f'<hr style="background-color:{palette["soft_border"]}; color:{palette["soft_border"]}; '
                f'height:1px; margin-top:0px; margin-bottom:12px;">'
            )
        return closing

    def hr(self, tokens, idx, options, env):
        palette = env["palette"]
        return (
            f'<hr style="background-color:{palette["border"]}; color:{palette["border"]}; height:3px; '
            f'margin-top:20px; margin-bottom:20px;">'
        )

    def paragraph_open(self, tokens, idx, options, env):
        if tokens[idx].hidden:
            return ""
        children = tokens[idx + 1].children or [] if idx + 1 < len(tokens) else []
        has_image = any(child.type == "image" or (child.type == "html_inline" and "<img" in child.content.lower()) for child in children)
        line_height = "" if has_image else " line-height:150%;"
        return f'<p style="margin-top:0px; margin-bottom:14px;{line_height}">'

    def paragraph_close(self, tokens, idx, options, env):
        return "" if tokens[idx].hidden else "</p>"

    def blockquote_open(self, tokens, idx, options, env):
        token = tokens[idx]
        palette = env["palette"]
        alert = token.meta.get("alert") if token.meta else None
        if alert:
            color_key, symbol, title = ALERTS[alert]
            color = palette[color_key]
            label = env["settings"]["alerts"].get(alert, title)
            return (
                f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px; margin-bottom:14px;"><tr>'
                f'<td width="4" bgcolor="{color}"></td><td style="padding-left:14px; padding-top:2px; padding-bottom:2px;">'
                f'<p style="margin:0 0 6px 0; color:{color}; font-weight:700;">{symbol}&nbsp;&nbsp;{html.escape(label)}</p>'
            )
        return (
            f'<table width="100%" cellspacing="0" cellpadding="0" style="margin-top:6px; margin-bottom:14px;"><tr>'
            f'<td width="4" bgcolor="{palette["quote_bar"]}"></td>'
            f'<td style="padding-left:14px; color:{palette["muted"]};">'
        )

    def blockquote_close(self, tokens, idx, options, env):
        return "</td></tr></table>"

    def bullet_list_open(self, tokens, idx, options, env):
        token = tokens[idx]
        bottom = 14 if token.level == 0 else 0
        style = f"margin-top:0px; margin-bottom:{bottom}px;"
        if token.meta and token.meta.get("tasklist"):
            style += " list-style-type:none; -qt-list-indent:0;"
        return f'<ul style="{style}">'

    def ordered_list_open(self, tokens, idx, options, env):
        token = tokens[idx]
        bottom = 14 if token.level == 0 else 0
        start = token.attrGet("start")
        start_attribute = f' start="{start}"' if start else ""
        return f'<ol{start_attribute} style="margin-top:0px; margin-bottom:{bottom}px;">'

    def list_item_open(self, tokens, idx, options, env):
        return '<li style="margin-top:2px; margin-bottom:2px; line-height:150%;">'

    def table_open(self, tokens, idx, options, env):
        palette = env["palette"]
        columns = 0
        position = idx + 1
        while position < len(tokens) and tokens[position].type != "tr_close":
            if tokens[position].type == "th_open":
                columns += 1
            position += 1
        env["table_columns"] = columns
        env["row_index"] = 0
        return (
            f'<table border="1" cellspacing="0" cellpadding="8" style="border-color:{palette["border"]}; '
            f'border-collapse:collapse; margin-bottom:14px;">'
        )

    def table_close(self, tokens, idx, options, env):
        env["table_columns"] = 0
        return "</table>"

    def tr_open(self, tokens, idx, options, env):
        palette = env["palette"]
        is_body = any(tokens[position].type == "tbody_open" for position in range(max(0, idx - 3), idx))
        if is_body or env.get("in_body"):
            env["in_body"] = True
            env["row_index"] += 1
            if env["row_index"] % 2 == 0:
                return f'<tr bgcolor="{palette["table_stripe"]}">'
        return "<tr>"

    def tbody_close(self, tokens, idx, options, env):
        env["in_body"] = False
        return "</tbody>"

    def th_open(self, tokens, idx, options, env):
        align = self.cell_alignment(tokens[idx])
        return f'<th align="{align}" bgcolor="{env["palette"]["table_stripe"]}" style="font-weight:700;">'

    def td_open(self, tokens, idx, options, env):
        return f'<td align="{self.cell_alignment(tokens[idx])}">'

    @staticmethod
    def cell_alignment(token):
        style = token.attrGet("style") or ""
        for name in ("center", "right"):
            if name in style:
                return name
        return "left"

    def link_open(self, tokens, idx, options, env):
        href = tokens[idx].attrGet("href") or ""
        return f'<a href="{html.escape(href, quote=True)}" style="color:{env["palette"]["link"]};">'

    def image(self, tokens, idx, options, env):
        token = tokens[idx]
        source = token.attrGet("src") or ""
        alt = token.content or ""
        key = self.register_image(env, source, alt, self.image_max_width(env))
        return f'<img src="{key}" alt="{html.escape(alt, quote=True)}">'

    def hardbreak(self, tokens, idx, options, env):
        return "<br>"

    def softbreak(self, tokens, idx, options, env):
        return " "

    def html_block(self, tokens, idx, options, env):
        return self.normalize_html(tokens[idx].content, env) + "\n"

    def html_inline(self, tokens, idx, options, env):
        return self.normalize_html(tokens[idx].content, env)

    def normalize_html(self, fragment, env):
        palette = env["palette"]
        fragment = HTML_COMMENT.sub("", fragment)
        fragment = re.sub(r"</?picture\b[^>]*>|<source\b[^>]*>", "", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"<details\b[^>]*>", "<div>", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"</details>", "</div>", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"<summary\b[^>]*>", '<p style="margin-bottom:6px;"><b>▸&nbsp;', fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"</summary>", "</b></p>", fragment, flags=re.IGNORECASE)
        fragment = re.sub(
            r"<kbd\b[^>]*>",
            f'<span style="background-color:{palette["inline_code_background"]}; font-family:{MONO_FAMILY}; '
            f'font-size:12px;">&nbsp;',
            fragment,
            flags=re.IGNORECASE,
        )
        fragment = re.sub(r"</kbd>", "&nbsp;</span>", fragment, flags=re.IGNORECASE)
        env["html_table_depth"] = max(
            0,
            env.get("html_table_depth", 0)
            + len(re.findall(r"<table\b", fragment, flags=re.IGNORECASE))
            - len(re.findall(r"</table>", fragment, flags=re.IGNORECASE)),
        )
        if "<img" in fragment.lower():
            fragment = IMAGE_TAG.sub(lambda match: self.rewrite_image_tag(match.group(0), env), fragment)
        return fragment

    def rewrite_image_tag(self, tag, env):
        attributes = parse_attributes(tag)
        source = attributes.get("src", "")
        alt = attributes.get("alt", "")
        limit = self.image_max_width(env)
        key = self.register_image(env, source, alt, limit)
        width_attribute = ""
        width = attributes.get("width", "")
        if width.isdigit():
            requested = int(width)
            width_attribute = f' width="{min(requested, limit)}"'
        elif width.endswith("%") and width[:-1].isdigit():
            width_attribute = f' width="{max(16, limit * int(width[:-1]) // 100)}"'
        return f'<img src="{key}" alt="{html.escape(alt, quote=True)}"{width_attribute}>'


def tasks_and_alerts(palette):
    def rule(state):
        tokens = state.tokens
        list_stack = []
        for index, token in enumerate(tokens):
            if token.type in ("bullet_list_open", "ordered_list_open"):
                list_stack.append([index, 0, 0])
            elif token.type in ("bullet_list_close", "ordered_list_close"):
                start, items, tasks = list_stack.pop()
                if items and items == tasks and tokens[start].type == "bullet_list_open":
                    tokens[start].meta = {**(tokens[start].meta or {}), "tasklist": True}
            elif token.type == "list_item_open" and list_stack:
                list_stack[-1][1] += 1
                inline = next((t for t in tokens[index + 1:index + 4] if t.type == "inline"), None)
                if inline is None or not inline.children:
                    continue
                first = inline.children[0]
                match = re.match(r"^\[( |x|X)\]\s+", first.content) if first.type == "text" else None
                if not match:
                    continue
                list_stack[-1][2] += 1
                done = match.group(1) in ("x", "X")
                first.content = first.content[match.end():]
                glyph = Token("html_inline", "", 0)
                color = palette["check_done"] if done else palette["muted"]
                glyph.content = f'<span style="color:{color}; font-size:15px;">{"☑" if done else "☐"}</span>&nbsp;'
                inline.children.insert(0, glyph)
            elif token.type == "blockquote_open" and index + 2 < len(tokens):
                inline = tokens[index + 2]
                if tokens[index + 1].type != "paragraph_open" or inline.type != "inline" or not inline.children:
                    continue
                first = inline.children[0]
                match = re.fullmatch(r"\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", first.content.strip(), flags=re.IGNORECASE)
                if first.type == "text" and match:
                    token.meta = {**(token.meta or {}), "alert": match.group(1).upper()}
                    del inline.children[0]
                    if inline.children and inline.children[0].type in ("softbreak", "hardbreak"):
                        del inline.children[0]

    return rule


def front_matter_table(raw, palette):
    rows = []
    for line in raw.split("\n"):
        key, separator, value = line.partition(":")
        if separator and key.strip() and not key.startswith(" "):
            rows.append((key.strip(), value.strip().strip("\"'")))
    if not rows:
        return ""
    cells = "".join(
        f'<tr><td style="font-weight:700;">{html.escape(key)}</td><td>{html.escape(value)}</td></tr>' for key, value in rows
    )
    return (
        f'<table border="1" cellspacing="0" cellpadding="6" style="border-color:{palette["border"]}; '
        f'border-collapse:collapse; margin-bottom:16px;">{cells}</table>'
    )


def build_stylesheet(palette):
    return f"""
        body {{ background-color:{palette['background']}; color:{palette['text']}; font-family:{SANS_FAMILY}; font-size:15px; }}
        a {{ color:{palette['link']}; text-decoration:none; }}
        th, td {{ color:{palette['text']}; }}
        s, del {{ color:{palette['muted']}; }}
    """


class MarkdownRenderer:
    def __init__(self, palette, labels):
        self.palette = palette
        self.labels = labels
        self.parser = MarkdownIt("commonmark", {"html": True}, renderer_cls=QtRenderer).enable(["table", "strikethrough"])
        self.parser.core.ruler.push("veylora_tasks_and_alerts", tasks_and_alerts(palette))

    def render(self, text, base_dir=None, max_width=760):
        env = {
            "palette": self.palette,
            "settings": self.labels,
            "images": {},
            "slugs": {},
            "title": "",
            "max_width": max_width,
            "base_dir": base_dir,
        }
        prefix = ""
        match = FRONT_MATTER.match(text)
        if match:
            prefix = front_matter_table(match.group(1), self.palette)
            text = text[match.end():]
        body = self.parser.render(text, env)
        document = (
            f"<html><head><style>{build_stylesheet(self.palette)}</style></head>"
            f'<body style="background-color:{self.palette["background"]}; color:{self.palette["text"]};">'
            f"{prefix}{body}</body></html>"
        )
        return RenderResult(document, env["images"], env["title"])


def export_html_document(text, title, palette):
    parser = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    parser.core.ruler.push("veylora_tasks_and_alerts", tasks_and_alerts(palette))
    slugs = {}

    def add_heading_ids(state):
        for index, token in enumerate(state.tokens):
            if token.type == "heading_open":
                slug = github_slug(state.tokens[index + 1].content)
                count = slugs.get(slug, 0)
                slugs[slug] = count + 1
                token.attrSet("id", slug if count == 0 else f"{slug}-{count}")

    parser.core.ruler.push("veylora_heading_ids", add_heading_ids)
    match = FRONT_MATTER.match(text)
    prefix = ""
    if match:
        prefix = front_matter_table(match.group(1), palette)
        text = text[match.end():]
    body = parser.render(text)
    css = f"""
        body {{ background:{palette['background']}; color:{palette['text']}; margin:0; padding:40px 20px;
               font-family:{SANS_FAMILY}; font-size:16px; line-height:1.6; }}
        main {{ max-width:900px; margin:0 auto; }}
        a {{ color:{palette['link']}; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
        h1, h2 {{ border-bottom:1px solid {palette['soft_border']}; padding-bottom:.3em; }}
        h1, h2, h3, h4, h5, h6 {{ margin-top:1.6em; margin-bottom:.6em; line-height:1.25; }}
        code {{ background:{palette['inline_code_background']}; padding:.2em .4em; border-radius:6px;
               font-family:{MONO_FAMILY}; font-size:85%; }}
        pre {{ background:{palette['code_background']}; padding:16px; border-radius:8px; overflow:auto;
              border:1px solid {palette['soft_border']}; }}
        pre code {{ background:none; padding:0; font-size:90%; }}
        blockquote {{ margin:0; padding:0 1em; color:{palette['muted']}; border-left:.25em solid {palette['quote_bar']}; }}
        table {{ border-collapse:collapse; display:block; overflow:auto; }}
        th, td {{ border:1px solid {palette['border']}; padding:6px 13px; }}
        tr:nth-child(2n) {{ background:{palette['table_stripe']}; }}
        img {{ max-width:100%; }} hr {{ border:0; border-top:3px solid {palette['border']}; margin:24px 0; }}
    """
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{css}</style></head><body><main>{prefix}{body}</main></body></html>"
    )
