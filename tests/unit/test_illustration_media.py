# ruff: noqa: E501 - HTML fixtures.
from src.mdict.illustration_media import (
    illustration_media_fingerprints,
    media_path_fingerprint,
)


def test_media_path_fingerprint_matches_zim_and_export() -> None:
    zim = "./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg"
    exported = "heval/image/040c0639ff6f9a949d4aa9c3507b955b-aabeade6c2.jpg"
    assert media_path_fingerprint(zim) == media_path_fingerprint(exported)


def test_illustration_fingerprints_only_from_wene_section() -> None:
    section_html = {
        "navder": '<img src="./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg" />',
        "wêne": '<img src="./_assets_/only-in-wene.png" />',
    }
    fps = illustration_media_fingerprints(section_html)
    assert media_path_fingerprint("./_assets_/only-in-wene.png") in fps
    assert media_path_fingerprint("./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg") not in fps


def test_lede_thumb_in_navder_when_no_wene_heading() -> None:
    section_html = {
        "navder": '<img src="./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg" class="mw-file-element" />',
        "werger": '<img src="./_assets_/hiero_A1.png" />',
    }
    fps = illustration_media_fingerprints(section_html)
    assert media_path_fingerprint("./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg") in fps
    assert media_path_fingerprint("./_assets_/hiero_A1.png") not in fps
