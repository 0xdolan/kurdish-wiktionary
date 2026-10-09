import io

from src.core.stream_filter import _LineFilterWriter


def test_line_filter_suppresses_stemming_noise() -> None:
    buf = io.StringIO()
    writer = _LineFilterWriter(buf)
    writer.write("No stemming for language 'ku'\n")
    writer.write("real error line\n")
    writer.flush()
    assert "stemming" not in buf.getvalue()
    assert "real error line" in buf.getvalue()
