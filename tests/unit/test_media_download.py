from src.lexicon.media_download import file_matches_expected_size


def test_file_matches_expected_size() -> None:
    assert file_matches_expected_size(100, 100) is True
    assert file_matches_expected_size(100, 99) is False
    assert file_matches_expected_size(100, None) is False
    assert file_matches_expected_size(100, 0) is False
