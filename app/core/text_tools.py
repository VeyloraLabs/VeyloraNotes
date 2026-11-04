import base64
import binascii
import hashlib
import html
import json
import random
import re
import secrets
import string
import unicodedata
import urllib.parse
import uuid
from collections import Counter
from datetime import datetime, timezone

WORD_PATTERN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def split_words(text):
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    parts = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", parts)
    return [word for word in re.split(r"[^\w]+|_", parts, flags=re.UNICODE) if word]


def to_upper(text):
    return text.upper()


def to_lower(text):
    return text.lower()


def to_title(text):
    return re.sub(r"[^\W_]+(?:['’][^\W_]+)*", lambda match: match.group(0)[:1].upper() + match.group(0)[1:].lower(), text)


def to_sentence(text):
    lowered = text.lower()
    return re.sub(
        r"(^\s*|[.!?]\s+|\n\s*)([¿¡\"“«(]*)([^\W\d_])",
        lambda match: match.group(1) + match.group(2) + match.group(3).upper(),
        lowered,
    )


def invert_case(text):
    return text.swapcase()


def to_camel(text):
    words = split_words(text)
    if not words:
        return text
    return words[0].lower() + "".join(word.capitalize() for word in words[1:])


def to_pascal(text):
    return "".join(word.capitalize() for word in split_words(text))


def to_snake(text):
    return "_".join(word.lower() for word in split_words(text))


def to_kebab(text):
    return "-".join(word.lower() for word in split_words(text))


def to_constant(text):
    return "_".join(word.upper() for word in split_words(text))


def strip_accents(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def to_slug(text):
    cleaned = strip_accents(text).lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    return cleaned.strip("-")


def split_lines(text):
    return text.split("\n")


def sort_lines(text, descending=False, ignore_case=True, numeric=False):
    lines = split_lines(text)
    trailing = lines and lines[-1] == ""
    if trailing:
        lines = lines[:-1]

    def natural_key(line):
        pieces = re.split(r"(\d+)", line.casefold() if ignore_case else line)
        return [int(piece) if piece.isdigit() else piece for piece in pieces]

    if numeric:
        key = natural_key
    elif ignore_case:
        key = lambda line: strip_accents(line).casefold()
    else:
        key = None
    result = sorted(lines, key=key, reverse=descending)
    return "\n".join(result) + ("\n" if trailing else "")


def reverse_lines(text):
    lines = split_lines(text)
    trailing = lines and lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    return "\n".join(reversed(lines)) + ("\n" if trailing else "")


def unique_lines(text):
    seen = set()
    result = []
    for line in split_lines(text):
        if line in seen and line != "":
            continue
        seen.add(line)
        result.append(line)
    return "\n".join(result)


def remove_empty_lines(text):
    return "\n".join(line for line in split_lines(text) if line.strip())


def collapse_empty_lines(text):
    return re.sub(r"\n{3,}", "\n\n", text)


def trim_trailing_spaces(text):
    return "\n".join(line.rstrip() for line in split_lines(text))


def trim_lines(text):
    return "\n".join(line.strip() for line in split_lines(text))


def join_lines(text, separator=" "):
    pieces = [line.strip() for line in split_lines(text) if line.strip()]
    return separator.join(pieces)


def number_lines(text, start=1):
    lines = split_lines(text)
    trailing = lines and lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    width = len(str(start + len(lines) - 1))
    result = "\n".join(f"{index:>{width}}. {line}" for index, line in enumerate(lines, start))
    return result + ("\n" if trailing else "")


def shuffle_lines(text):
    lines = split_lines(text)
    trailing = lines and lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    random.SystemRandom().shuffle(lines)
    return "\n".join(lines) + ("\n" if trailing else "")


def tabs_to_spaces(text, width=4):
    return text.replace("\t", " " * width)


def spaces_to_tabs(text, width=4):
    def convert(match):
        spaces = match.group(0)
        return "\t" * (len(spaces) // width) + " " * (len(spaces) % width)

    return re.sub(r"^ +", convert, text, flags=re.MULTILINE)


def base64_encode(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def base64_decode(text):
    cleaned = re.sub(r"\s+", "", text)
    padded = cleaned + "=" * (-len(cleaned) % 4)
    try:
        return base64.b64decode(padded, validate=False).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as error:
        raise ValueError(str(error)) from error


def url_encode(text):
    return urllib.parse.quote(text, safe="")


def url_decode(text):
    return urllib.parse.unquote(text)


def html_escape(text):
    return html.escape(text, quote=True)


def html_unescape(text):
    return html.unescape(text)


def rot13(text):
    return text.translate(
        str.maketrans(
            "ABCDEFGHIJKLMabcdefghijklmNOPQRSTUVWXYZnopqrstuvwxyz",
            "NOPQRSTUVWXYZnopqrstuvwxyzABCDEFGHIJKLMabcdefghijklm",
        )
    )


def hex_encode(text):
    return text.encode("utf-8").hex(" ")


def hex_decode(text):
    cleaned = re.sub(r"[\s,]|0x", "", text)
    try:
        return bytes.fromhex(cleaned).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(str(error)) from error


def json_format(text, indent=2):
    return json.dumps(json.loads(text), indent=indent, ensure_ascii=False)


def json_minify(text):
    return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)


def json_check(text):
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        return error.lineno, error.colno, error.msg
    return None


def compute_hashes(text):
    data = text.encode("utf-8")
    return {
        "MD5": hashlib.md5(data).hexdigest(),
        "SHA-1": hashlib.sha1(data).hexdigest(),
        "SHA-256": hashlib.sha256(data).hexdigest(),
        "SHA-512": hashlib.sha512(data).hexdigest(),
    }


def compute_stats(text, words_per_minute=200):
    words = WORD_PATTERN.findall(text)
    lines = text.split("\n") if text else []
    paragraphs = [block for block in re.split(r"\n\s*\n", text) if block.strip()]
    sentences = [part for part in re.split(r"[.!?…]+(?:\s|$)", text) if part.strip()]
    frequency = Counter(word.casefold() for word in words if len(word) > 3)
    minutes = len(words) / words_per_minute if words else 0
    return {
        "characters": len(text),
        "characters_no_spaces": len(re.sub(r"\s", "", text)),
        "words": len(words),
        "lines": len(lines),
        "non_empty_lines": sum(1 for line in lines if line.strip()),
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "bytes": len(text.encode("utf-8")),
        "reading_minutes": minutes,
        "average_word_length": (sum(len(word) for word in words) / len(words)) if words else 0,
        "top_words": frequency.most_common(8),
    }


def extract_urls(text):
    return list(dict.fromkeys(match.rstrip(".,;:!?") for match in URL_PATTERN.findall(text)))


def extract_emails(text):
    return list(dict.fromkeys(EMAIL_PATTERN.findall(text)))


def extract_numbers(text):
    return NUMBER_PATTERN.findall(text)


def unix_to_date(text):
    value = text.strip()
    if not re.fullmatch(r"-?\d{1,16}(?:\.\d+)?", value):
        raise ValueError(value)
    number = float(value)
    if abs(number) > 1e11:
        number /= 1000
    moment = datetime.fromtimestamp(number, tz=timezone.utc).astimezone()
    return moment.strftime("%Y-%m-%d %H:%M:%S %z")


def date_to_unix(text):
    value = text.strip().replace("Z", "+00:00")
    formats = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")
    moment = None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        for pattern in formats:
            try:
                moment = datetime.strptime(value, pattern)
                break
            except ValueError:
                continue
    if moment is None:
        raise ValueError(value)
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return str(int(moment.timestamp()))


def convert_timestamp(text):
    try:
        return unix_to_date(text)
    except ValueError:
        return date_to_unix(text)


def new_uuid():
    return str(uuid.uuid4())


def generate_password(length=20, symbols=True):
    alphabet = string.ascii_letters + string.digits + ("!@#$%^&*()-_=+[]{};:,.?" if symbols else "")
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in candidate)
            and any(char.isupper() for char in candidate)
            and any(char.isdigit() for char in candidate)
            and (not symbols or any(char in "!@#$%^&*()-_=+[]{};:,.?" for char in candidate))
        ):
            return candidate


LOREM_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna "
    "aliqua enim ad minim veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea commodo consequat duis aute "
    "irure in reprehenderit voluptate velit esse cillum fugiat nulla pariatur excepteur sint occaecat cupidatat non "
    "proident sunt culpa qui officia deserunt mollit anim id est laborum"
).split()


def lorem_ipsum(paragraphs=3):
    generator = random.Random(2024)
    result = []
    for index in range(paragraphs):
        sentences = []
        for _ in range(generator.randint(3, 5)):
            words = [generator.choice(LOREM_WORDS) for _ in range(generator.randint(8, 16))]
            if index == 0 and not sentences:
                words[:2] = ["lorem", "ipsum"]
            sentences.append(" ".join(words).capitalize() + ".")
        result.append(" ".join(sentences))
    return "\n\n".join(result)

