from src.extraction.zim_media import (
    local_media_relative_path,
    wikimedia_url_zim_i_candidates,
    zim_path_candidates,
)


def test_zim_path_candidates_relative_and_i_prefix() -> None:
    paths = zim_path_candidates("w/heval", "foo.png")
    assert "w/foo.png" in paths
    assert "I/foo.png" in paths


def test_wikimedia_url_zim_i_candidates_transcoded() -> None:
    url = (
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/ab/"
        "LL-Q36163_%28kmr%29-Foo.wav/LL-Q36163_%28kmr%29-Foo.wav.mp3"
    )
    paths = wikimedia_url_zim_i_candidates(url)
    assert "I/LL-Q36163_(kmr)-Foo.wav.mp3" in paths
    assert "I/LL-Q36163_(kmr)-Foo.wav" in paths


def test_local_media_relative_path_stable() -> None:
    rel = local_media_relative_path(
        entry_normalized="heval",
        kind="audio",
        url="https://upload.wikimedia.org/foo/bar.mp3",
    )
    assert rel.startswith("heval/audio/")
    assert rel.endswith(".mp3")
