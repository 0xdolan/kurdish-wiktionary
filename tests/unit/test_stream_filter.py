import io

from src.core.stream_filter import _LineFilterWriter, _should_suppress_text


def test_line_filter_suppresses_bare_ku() -> None:
    buf = io.StringIO()
    writer = _LineFilterWriter(buf)
    writer.write("'ku'\n")
    writer.flush()
    assert buf.getvalue() == ""


def test_should_suppress_stemming_line() -> None:
    assert _should_suppress_text("No stemming for language 'ku'")
    assert not _should_suppress_text("real error line")


def test_line_filter_suppresses_stemming_noise() -> None:
    buf = io.StringIO()
    writer = _LineFilterWriter(buf)
    writer.write("No stemming for language 'ku'\n")
    writer.write("real error line\n")
    writer.flush()
    assert "stemming" not in buf.getvalue()
    assert "real error line" in buf.getvalue()
