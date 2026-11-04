from dataclasses import dataclass, field
from pathlib import Path

C_LIKE_KEYWORDS = (
    "if else for while do switch case default break continue return goto sizeof typedef struct union enum static const "
    "extern volatile register inline auto void int long short char float double signed unsigned bool"
)


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    extensions: tuple = ()
    engine: str = "code"
    line_comment: str = ""
    block_comment: tuple = ()
    quotes: str = "\"'"
    triple_quotes: bool = False
    keywords: frozenset = field(default_factory=frozenset)
    literals: frozenset = field(default_factory=frozenset)
    case_insensitive: bool = False
    filenames: tuple = ()


def words(text):
    return frozenset(text.split())


LANGUAGES = (
    Language("plain", "", (".txt", ".text", ".log", ".out", ".nfo"), engine="plain", line_comment="#"),
    Language("markdown", "Markdown", (".md", ".markdown", ".mdown", ".mkd", ".mdx"), engine="markdown", block_comment=("<!--", "-->")),
    Language(
        "json", "JSON", (".json", ".jsonc", ".json5", ".geojson", ".webmanifest"), quotes='"',
        line_comment="//", block_comment=("/*", "*/"), literals=words("true false null"),
    ),
    Language(
        "python", "Python", (".py", ".pyw", ".pyi"), line_comment="#", triple_quotes=True,
        keywords=words(
            "and as assert async await break class continue def del elif else except finally for from global if import in is "
            "lambda nonlocal not or pass raise return try while with yield match case self cls print"
        ),
        literals=words("True False None"),
    ),
    Language(
        "javascript", "JavaScript", (".js", ".mjs", ".cjs", ".jsx"), line_comment="//", block_comment=("/*", "*/"), quotes="\"'`",
        keywords=words(
            "async await break case catch class const continue debugger default delete do else export extends finally for "
            "function if import in instanceof let new of return static super switch this throw try typeof var void while with yield"
        ),
        literals=words("true false null undefined NaN Infinity"),
    ),
    Language(
        "typescript", "TypeScript", (".ts", ".tsx"), line_comment="//", block_comment=("/*", "*/"), quotes="\"'`",
        keywords=words(
            "async await break case catch class const continue default delete do else enum export extends finally for function "
            "if implements import in instanceof interface let namespace new of private protected public readonly return static "
            "super switch this throw try type typeof var void while yield abstract declare keyof"
        ),
        literals=words("true false null undefined NaN Infinity"),
    ),
    Language("html", "HTML", (".html", ".htm", ".xhtml", ".vue"), engine="rules", block_comment=("<!--", "-->")),
    Language("xml", "XML", (".xml", ".svg", ".xsd", ".xsl", ".plist", ".rss", ".atom"), engine="rules", block_comment=("<!--", "-->")),
    Language("css", "CSS", (".css", ".scss", ".sass", ".less"), engine="rules", block_comment=("/*", "*/")),
    Language("yaml", "YAML", (".yaml", ".yml"), engine="rules", line_comment="#"),
    Language("toml", "TOML / INI", (".toml", ".ini", ".cfg", ".conf", ".properties", ".desktop", ".editorconfig"), engine="rules", line_comment="#"),
    Language(
        "shell", "Shell", (".sh", ".bash", ".zsh", ".fish", ".bashrc", ".profile"), line_comment="#",
        filenames=("makefile", "dockerfile", ".bashrc", ".zshrc", ".profile"),
        keywords=words(
            "if then else elif fi for while until do done case esac in function select time return exit break continue export "
            "local readonly declare unset source alias echo cd set shift trap"
        ),
        literals=words("true false"),
    ),
    Language(
        "c", "C", (".c", ".h"), line_comment="//", block_comment=("/*", "*/"),
        keywords=words(C_LIKE_KEYWORDS), literals=words("NULL true false"),
    ),
    Language(
        "cpp", "C++", (".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx"), line_comment="//", block_comment=("/*", "*/"),
        keywords=words(
            C_LIKE_KEYWORDS + " class public private protected virtual override namespace using template typename new delete "
            "this try catch throw operator friend explicit constexpr nullptr noexcept final"
        ),
        literals=words("NULL nullptr true false"),
    ),
    Language(
        "java", "Java", (".java",), line_comment="//", block_comment=("/*", "*/"),
        keywords=words(
            "abstract assert boolean break byte case catch char class const continue default do double else enum extends final "
            "finally float for if implements import instanceof int interface long native new package private protected public "
            "return short static super switch synchronized this throw throws try void volatile while var record"
        ),
        literals=words("true false null"),
    ),
    Language(
        "csharp", "C#", (".cs",), line_comment="//", block_comment=("/*", "*/"),
        keywords=words(
            "abstract as base bool break byte case catch char class const continue decimal default delegate do double else enum "
            "event explicit extern finally fixed float for foreach if implicit in int interface internal is lock long namespace "
            "new object operator out override params private protected public readonly ref return sealed short static string "
            "struct switch this throw try typeof uint ulong unsafe ushort using var virtual void volatile while async await"
        ),
        literals=words("true false null"),
    ),
    Language(
        "go", "Go", (".go",), line_comment="//", block_comment=("/*", "*/"), quotes="\"'`",
        keywords=words(
            "break case chan const continue default defer else fallthrough for func go goto if import interface map package "
            "range return select struct switch type var"
        ),
        literals=words("true false nil iota"),
    ),
    Language(
        "rust", "Rust", (".rs",), line_comment="//", block_comment=("/*", "*/"),
        keywords=words(
            "as async await break const continue crate dyn else enum extern fn for if impl in let loop match mod move mut pub "
            "ref return self Self static struct super trait type unsafe use where while"
        ),
        literals=words("true false"),
    ),
    Language(
        "php", "PHP", (".php",), line_comment="//", block_comment=("/*", "*/"),
        keywords=words(
            "abstract and array as break case catch class clone const continue declare default do echo else elseif empty "
            "extends final finally for foreach function global if implements include instanceof interface isset namespace new "
            "or print private protected public require return static switch throw trait try use var while yield"
        ),
        literals=words("true false null TRUE FALSE NULL"),
    ),
    Language(
        "ruby", "Ruby", (".rb", ".rake", ".gemspec"), line_comment="#",
        keywords=words(
            "alias and begin break case class def defined do else elsif end ensure for if in module next not or redo rescue "
            "retry return self super then undef unless until when while yield puts require attr_accessor"
        ),
        literals=words("true false nil"),
    ),
    Language(
        "lua", "Lua", (".lua",), line_comment="--", block_comment=("--[[", "]]"),
        keywords=words("and break do else elseif end for function goto if in local not or repeat return then until while"),
        literals=words("true false nil"),
    ),
    Language(
        "sql", "SQL", (".sql",), line_comment="--", block_comment=("/*", "*/"), case_insensitive=True,
        keywords=words(
            "select from where and or not insert into values update set delete create table alter drop index view join inner "
            "left right outer full on group by order having limit offset as distinct union all case when then else end "
            "primary key foreign references default unique check constraint begin commit rollback like in is between exists"
        ),
        literals=words("null true false"),
    ),
    Language(
        "batch", "Batch", (".bat", ".cmd"), engine="plain", line_comment="REM ",
    ),
    Language(
        "diff", "Diff", (".diff", ".patch"), engine="rules",
    ),
)

LANGUAGE_BY_ID = {language.id: language for language in LANGUAGES}
EXTENSION_MAP = {extension: language for language in LANGUAGES for extension in language.extensions}
FILENAME_MAP = {name: language for language in LANGUAGES for name in language.filenames}

TEXT_EXTENSIONS = frozenset(
    extension for language in LANGUAGES for extension in language.extensions
) | frozenset({".csv", ".tsv", ".tex", ".rst", ".org", ".srt", ".gitignore", ".env", ".lock"})


def language_for_path(path):
    if not path:
        return LANGUAGE_BY_ID["plain"]
    name = Path(path).name.lower()
    if name in FILENAME_MAP:
        return FILENAME_MAP[name]
    return EXTENSION_MAP.get(Path(path).suffix.lower(), LANGUAGE_BY_ID["plain"])


def language_by_id(language_id):
    return LANGUAGE_BY_ID.get(language_id, LANGUAGE_BY_ID["plain"])


def is_text_candidate(path):
    path = Path(path)
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in FILENAME_MAP or path.suffix == ""
