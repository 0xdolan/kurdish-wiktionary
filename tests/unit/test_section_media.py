from src.mdict.section_media import build_media_href_lookup, resolve_media_href


def test_resolve_media_href_by_zim_path() -> None:
    lookup = build_media_href_lookup(
        [
            {
                "kind": "image",
                "href": "media/heval/image/hiero_Aa1-b0078bd565.png",
                "source_url": "./_assets_/9ae9a9c4e10735879dfb80eb97080019/hiero_Aa1.png",
            }
        ]
    )
    resolved = resolve_media_href(
        "./_assets_/9ae9a9c4e10735879dfb80eb97080019/hiero_Aa1.png",
        lookup,
    )
    assert resolved == "media/heval/image/hiero_Aa1-b0078bd565.png"
