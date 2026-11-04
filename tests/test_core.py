import conftest_env
import tempfile
from pathlib import Path

from app.core import calculator, markdown_tools, text_tools
from app.core.document_io import BinaryFileError, read_text_file, write_text_file


def test_encodings_and_line_endings():
    directory = Path(tempfile.mkdtemp())
    for encoding in ("utf-8", "utf-8-sig", "utf-16-le", "utf-16-be", "cp1252"):
        for eol in ("\n", "\r\n", "\r"):
            target = directory / "sample.txt"
            write_text_file(target, "héllo\nwörld ñ\n", encoding, eol)
            loaded = read_text_file(target)
            assert loaded.eol == eol and loaded.text == "héllo\nwörld ñ\n"
    (directory / "binary.bin").write_bytes(bytes(range(256)) * 20)
    try:
        read_text_file(directory / "binary.bin")
    except BinaryFileError:
        pass
    else:
        raise AssertionError("binary file not detected")


def test_text_tools():
    assert text_tools.to_title("hello wORLD it's me") == "Hello World It's Me"
    assert text_tools.to_sentence("hola mundo. otra frase! ¿sí? vale") == "Hola mundo. Otra frase! ¿Sí? Vale"
    assert text_tools.to_snake("helloWorldFOOBar") == "hello_world_foo_bar"
    assert text_tools.to_slug("¿Qué tal, Canción Número 1?") == "que-tal-cancion-numero-1"
    assert text_tools.sort_lines("a10\na2\na1", numeric=True) == "a1\na2\na10"
    assert text_tools.unique_lines("a\nb\na\n\n\nc") == "a\nb\n\n\nc"
    assert text_tools.base64_decode(text_tools.base64_encode("héllo ñ")) == "héllo ñ"
    assert text_tools.hex_decode(text_tools.hex_encode("hi ñ")) == "hi ñ"
    assert text_tools.json_minify('{ "a" : 1 }') == '{"a":1}'
    assert text_tools.json_check('{"a":}') is not None and text_tools.json_check("{}") is None
    assert text_tools.compute_hashes("abc")["SHA-256"].startswith("ba7816bf")
    assert text_tools.extract_urls("ver https://a.com/x, y http://b.org.") == ["https://a.com/x", "http://b.org"]
    assert text_tools.date_to_unix("2023-11-14 22:13:20+00:00") == "1700000000"


def test_calculator_is_safe():
    assert calculator.evaluate("2+3*4") == 14
    assert calculator.format_number(calculator.evaluate("10/4")) == "2.5"
    for malicious in ["__import__('os')", "9**9**9", "1/0", "a+1", "open('x')", "(1).real", "lambda:1"]:
        try:
            calculator.evaluate(malicious)
        except calculator.CalculationError:
            continue
        raise AssertionError(malicious)
    assert calculator.calculate_text("2+2\nhola\n(3+4)*2 = 99")[0] == "2+2 = 4\nhola\n(3+4)*2 = 14"


def test_markdown_tools():
    text = "# Title\n\n```\n# not heading\n```\n\n## Sub\n"
    assert [item[1] for item in markdown_tools.extract_headings(text)] == ["Title", "Sub"]
    assert markdown_tools.generate_toc(text) == "- [Title](#title)\n  - [Sub](#sub)"
    table = ["| a | bb |", "|:-|-:|", "| xxxxx | 1 |"]
    assert markdown_tools.format_table(table).split("\n")[0] == "| a     |  bb |"
    assert markdown_tools.toggle_task_line("- [ ] item") == "- [x] item"
    assert markdown_tools.list_continuation("  1. foo")[0] == "  2. "


if __name__ == "__main__":
    for name, function in list(globals().items()):
        if name.startswith("test_"):
            function()
            print("OK  ", name)
