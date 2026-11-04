import codecs
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

ENCODINGS = (
    ("utf-8", "UTF-8"),
    ("utf-8-sig", "UTF-8 BOM"),
    ("utf-16-le", "UTF-16 LE"),
    ("utf-16-be", "UTF-16 BE"),
    ("cp1252", "Windows-1252"),
    ("latin-1", "ISO-8859-1"),
    ("cp850", "DOS-850"),
    ("mac-roman", "Mac Roman"),
)

EOL_NAMES = {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}
MAX_BINARY_SAMPLE = 8192


class BinaryFileError(Exception):
    pass


@dataclass
class LoadedText:
    text: str
    encoding: str
    eol: str


def encoding_label(encoding):
    for codec, label in ENCODINGS:
        if codec == encoding:
            return label
    return encoding.upper()


def detect_eol(text):
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf == 0 and lf == 0 and cr == 0:
        return "\n"
    best = max((lf, "\n"), (crlf, "\r\n"), (cr, "\r"), key=lambda item: item[0])
    return best[1]


def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def looks_binary(data):
    sample = data[:MAX_BINARY_SAMPLE]
    if not sample or sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return False
    if b"\x00" in sample:
        even_nulls = sample[0::2].count(0)
        odd_nulls = sample[1::2].count(0)
        half = len(sample) / 2
        if even_nulls > half * 0.6 or odd_nulls > half * 0.6:
            return False
        return True
    control = sum(1 for byte in sample if byte < 9 or 13 < byte < 32 and byte != 27)
    return control / len(sample) > 0.15


def decode_bytes(data, forced_encoding=None):
    if forced_encoding:
        encoding = forced_encoding
        payload = data
        if encoding == "utf-8" and data.startswith(codecs.BOM_UTF8):
            encoding = "utf-8-sig"
        text = payload.decode(encoding, errors="replace")
        return text, encoding
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace"), "utf-8-sig"
    if data.startswith(codecs.BOM_UTF16_LE):
        return data[2:].decode("utf-16-le", errors="replace"), "utf-16-le"
    if data.startswith(codecs.BOM_UTF16_BE):
        return data[2:].decode("utf-16-be", errors="replace"), "utf-16-be"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    sample = data[:MAX_BINARY_SAMPLE]
    if sample and sample.count(0) > len(sample) * 0.3:
        encoding = "utf-16-le" if sample[1::2].count(0) >= sample[0::2].count(0) else "utf-16-be"
        return data.decode(encoding, errors="replace"), encoding
    return data.decode("cp1252", errors="replace"), "cp1252"


def read_text_file(path, forced_encoding=None, allow_binary=False):
    data = Path(path).read_bytes()
    if not allow_binary and looks_binary(data):
        raise BinaryFileError(str(path))
    raw_text, encoding = decode_bytes(data, forced_encoding)
    eol = detect_eol(raw_text)
    return LoadedText(normalize_newlines(raw_text), encoding, eol)


def encode_text(text, encoding, eol):
    converted = normalize_newlines(text)
    if eol != "\n":
        converted = converted.replace("\n", eol)
    if encoding == "utf-8-sig":
        return codecs.BOM_UTF8 + converted.encode("utf-8")
    if encoding == "utf-16-le":
        return codecs.BOM_UTF16_LE + converted.encode("utf-16-le")
    if encoding == "utf-16-be":
        return codecs.BOM_UTF16_BE + converted.encode("utf-16-be")
    return converted.encode(encoding, errors="replace")


def write_text_file(path, text, encoding="utf-8", eol="\n"):
    destination = Path(path)
    payload = encode_text(text, encoding, eol)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".veyloranotes-", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.exists():
            try:
                os.chmod(temporary, destination.stat().st_mode & 0o7777)
            except OSError:
                pass
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def disk_signature(path):
    try:
        info = Path(path).stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)
