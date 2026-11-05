import logging

from git_version_tagger.text import PrintableFormatter, printable


def test_printable_replaces_terminal_controls_and_bidi_overrides():
    assert printable("Fix \x1b]0;PWNED\x07 \x1b[2J done") == "Fix ?]0;PWNED? ?[2J done"
    assert printable("report\u202egpj.exe") == "report?gpj.exe"
    assert printable("line\rover") == "line?over"
    assert printable("a\nb") == "a?b"
    assert printable("a\nb", keep_newlines=True) == "a\nb"
    assert printable("Релиз 3.26 ✓ → trunk") == "Релиз 3.26 ✓ → trunk"


def test_printable_replaces_arabic_letter_mark_and_unicode_line_breaks():
    assert printable("a\u061cb\u2028c\u2029d") == "a?b?c?d"
    assert printable("a\u2066b\u2069c") == "a?b?c"


def test_printable_formatter_cleans_log_lines_but_keeps_newlines():
    record = logging.LogRecord(
        "git_version_tagger", logging.ERROR, __file__, 1, "Refresh failed: %s", ("remote: \x1b[2J\u202ehi\nnext",), None
    )
    assert PrintableFormatter("%(message)s").format(record) == "Refresh failed: remote: ?[2J?hi\nnext"
