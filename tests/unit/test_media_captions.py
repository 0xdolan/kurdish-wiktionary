from src.mdict.media_captions import image_captions_from_html, lookup_image_caption


def test_image_captions_from_parsoid_figure() -> None:
    html = (
        '<figure class="mw-default-size" typeof="mw:File/Thumb">'
        '<img src="./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg" />'
        "<figcaption>Du heval.</figcaption></figure>"
    )
    caps = image_captions_from_html(html)
    assert caps["./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg"] == "Du heval."
    assert caps["040c0639ff6f9a949d4aa9c3507b955b.jpg"] == "Du heval."
    assert caps["040c0639ff6f9a949d4aa9c3507b955b"] == "Du heval."


def test_lookup_image_caption_matches_hashed_local_path() -> None:
    caps = {"040c0639ff6f9a949d4aa9c3507b955b": "Du heval."}
    found = lookup_image_caption(
        caps,
        url="./_assets_/040c0639ff6f9a949d4aa9c3507b955b.jpg",
        local_href="media/heval/image/040c0639ff6f9a949d4aa9c3507b955b-aabeade6c2.jpg",
    )
    assert found == "Du heval."
