# ruff: noqa: E501 - HTML fixtures copied from real pages.
"""Section-aware parser, using markup copied from real Wîkîferheng pages."""

from typing import Any

import pytest
from src.dataset.page_parser import (
    commons_file_from_url,
    link_target,
    media_id_for,
    normalize_asset_path,
    parse_page,
)
from src.dataset.schema import TABLE_BY_NAME
from src.dataset.sections import classify_heading, normalize_heading

AUDIO_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/aa/"
    "LL-Q36368_%28kur%29-Dildadil-heval.wav/LL-Q36368_%28kur%29-Dildadil-heval.wav.mp3"
)

BODY = f"""
<div class="mw-heading mw-heading2"><h2 id="Kurmancî"><span class="besazimani" id="ku">Kurmancî</span></h2></div>
<div class="mw-heading mw-heading3"><h3 id="Bilêvkirin">Bilêvkirin</h3></div>
<ul><li><a href="IPA" title="IPA">IPA</a>:&nbsp;<span class="IPA">/hɛˈvɑːl/</span></li>
<li><table class="audiotable"><tbody><tr><td>Deng <span class="usage-label-accent"><span class="ib-content label-content">Amed</span></span>:</td>
<td class="audiofile"><a role="button" href="{AUDIO_URL}"><span>guhdar bike</span></a></td></tr></tbody></table></li>
<li><a href="k%C3%AEte" title="kîte">Kîtekirin</a>: he·val</li></ul>
<div class="mw-heading mw-heading3"><h3 id="Navdêr">Navdêr</h3></div>
<figure class="mw-default-size" typeof="mw:File/Thumb"><img src="./_assets_/040c.jpg" width="250" class="mw-file-element" data-file-width="1024" data-file-height="730"><figcaption>Du heval.</figcaption></figure>
<p><span class="headword-line"><strong class="Latn headword" lang="ku">heval</strong>&nbsp;<span class="gender"><abbr title="mê">m</abbr></span></span></p>
<ol><li><span class="context-qualifier-colon"><span class="usage-label-sense"><span class="ib-content label-content"><a href="kes">kes</a></span></span></span> Kesên hev <a href="nas%C3%AEn" title="nasîn">dinasin</a>.
<dl><dd><span class="h-usage-example"><i class="e-example" lang="ku">Heval, navê te çi ye?</i> ― <span class="e-translation">Translation.</span></span></dd>
<dd><span class="nyms Hevmane"><span class="defdate">Hevmane:</span> <span class="Latn" lang="ku"><a href="yar#Kurmancî" title="yar">yar</a></span></span></dd></dl>
<ul><li><div class="citation-whole"><span class="cited-source"><span class="j-pewist"><b>~1692</b></span>, <span class="j-pewist">Ehmedê Xanî</span>, <cite>Mem û Zîn</cite>:</span><dl><dd><div class="h-quotation"><span class="cited-passage">Rêza yek<br>rêza du</span></div></dd></dl></div></li></ul>
</li>
<li>Keç û kurên ji hev hez dikin.<ul><li><span class="benimune">Nimûneyekê lê zêde bike</span></li></ul></li></ol>
<div class="mw-heading mw-heading4"><h4 id="Tewandin">Tewandin</h4></div>
<div class="inflection-table-wrapper"><table class="inflection-table"><caption>Tewandina heval</caption><tbody>
<tr><th colspan="3">Zayenda mê</th></tr>
<tr><th>Rewş</th><th>Yekjimar</th><th>Pirjimar</th></tr>
<tr><th>Îzafe</th><td><a href="hevala#Kurmancî" title="hevala">heval<b>a</b></a></td><td>—</td></tr>
</tbody></table></div>
<div class="mw-heading mw-heading4"><h4 id="Bi_alfabeyên_din">Bi alfabeyên din</h4></div>
<ul><li><span class="Latn" lang="ku"><a href="kurd%C3%AE-ereb%C3%AE#Kurmancî">kurdî-erebî</a></span>: <span class="Arab" lang="ku"><a href="%D9%87#K">هه‌ڤال</a></span></li></ul>
<div class="mw-heading mw-heading4"><h4 id="Hevmane">Hevmane</h4></div>
<ul><li><span class="Latn" lang="ku"><a href="dost#Kurmancî" title="dost">dost</a></span></li></ul>
<div class="mw-heading mw-heading4"><h4 id="Etîmolojî">Etîmolojî</h4></div>
<p>Ji *<a href="ham" title="ham">ham</a>- a Proto-Îranî.</p>
<div class="mw-heading mw-heading4"><h4 id="Werger">Werger</h4></div>
<div class="NavFrame"><div class="NavHead"><i>heval</i></div><div class="NavContent"><div class="translations">
<ul><li><span class="trad-af">Afrîkansî</span>: <span class="Latn" lang="af"><a href="vriend#Afrîkansî">vriend</a></span>, <span class="Latn" lang="af"><a href="maat#Afrîkansî">maat</a></span></li></ul>
</div></div></div>
<div class="mw-heading mw-heading2"><h2 id="Tirkî"><span class="besazimani" id="tr">Tirkî</span></h2></div>
<div class="mw-heading mw-heading3"><h3 id="Navdêr_2">Navdêr 2</h3></div>
<ol><li>ava</li></ol>
<div class="mw-heading mw-heading3"><h3 id="Çavkanî">Çavkanî</h3></div>
<dl><dd><div class="werger-template-info" data-template-info="tr"><i>Ev made ji wergerên <b><a href="av/Werger#Werger" title="av/Werger">av/Werger</a></b> hatiye çêkirin.</i></div></dd></dl>
"""
FOOTER = (
    '<!--htdig_noindex--><div class="zim-footer"><a class="external text" '
    'title="Last edited on 2026-08-18" href="https://ku.wiktionary.org/wiki/?title=heval&amp;oldid=6335568">W</a></div>'
)


def _page(body: str = BODY, title: str = "heval") -> Any:
    html = f'<div class="mw-content-ltr mw-parser-output" lang="ku">{body}</div>{FOOTER}'
    return parse_page(html=html, title=title, page_id=7, source_zim="maxi", in_latest_dump=True)


def _named(parsed: Any, table: str) -> list[dict[str, Any]]:
    names = [column.name for column in TABLE_BY_NAME[table].columns]
    return [dict(zip(names, row, strict=True)) for row in parsed.rows.get(table, [])]


def test_rows_match_schema_width() -> None:
    parsed = _page()
    for table, rows in parsed.rows.items():
        width = len(TABLE_BY_NAME[table].columns)
        assert all(len(row) == width for row in rows), table


def test_last_section_has_no_stray_wrapper_tag() -> None:
    parsed = _page()
    last = parsed.rows["section_html"][-1][1]
    assert last.count("<div") == last.count("</div>")


def test_page_records_revision_from_footer() -> None:
    page = _named(_page(), "pages")[0]
    assert page["revision_id"] == 6335568
    assert page["last_edited"] == "2026-08-18"
    assert page["page_kind"] == "entry"
    assert page["language_count"] == 2


def test_one_entry_per_language_with_stable_key() -> None:
    entries = {e["language_code"]: e for e in _named(_page(), "entries")}
    assert set(entries) == {"ku", "tr"}
    assert entries["ku"]["entry_key"] == "heval|ku"
    assert entries["ku"]["language_name"] == "Kurmancî"
    assert entries["ku"]["pos_list"] == "noun"
    assert entries["ku"]["has_ipa"] == 1
    assert entries["ku"]["has_audio"] == 1
    assert entries["ku"]["has_etymology"] == 1
    assert entries["ku"]["has_translations"] == 1
    assert entries["ku"]["is_auto_generated"] == 0


def test_section_tree_keeps_wiki_hierarchy() -> None:
    sections = _named(_page(), "sections")
    by_heading = {s["heading"]: s for s in sections}
    assert by_heading["Kurmancî"]["level"] == 2
    assert by_heading["Navdêr"]["parent_section_id"] == by_heading["Kurmancî"]["section_id"]
    assert by_heading["Hevmane"]["parent_section_id"] == by_heading["Navdêr"]["section_id"]
    assert by_heading["Tirkî"]["parent_section_id"] is None
    assert by_heading["Hevmane"]["section_type"] == "synonyms"


def test_numbered_heading_is_homograph() -> None:
    sections = {s["heading"]: s for s in _named(_page(), "sections")}
    assert sections["Navdêr 2"]["pos"] == "noun"
    assert sections["Navdêr 2"]["homograph"] == 2


def test_senses_split_label_text_and_links() -> None:
    senses = _named(_page(), "senses")
    assert senses[0]["labels"] == "kes"
    assert senses[0]["definition"] == "Kesên hev dinasin."
    assert senses[0]["ordinal"] == 1
    assert "nasîn" in senses[0]["linked_terms"]
    assert senses[1]["ordinal"] == 2


def test_example_quotation_and_sense_synonym_attach_to_sense() -> None:
    parsed = _page()
    sense_id = _named(parsed, "senses")[0]["sense_id"]
    examples = _named(parsed, "examples")
    assert [e["example"] for e in examples] == ["Heval, navê te çi ye?"]
    assert examples[0]["translation"] == "Translation."
    assert examples[0]["sense_id"] == sense_id
    quote = _named(parsed, "quotations")[0]
    assert (quote["year"], quote["author"], quote["work"]) == ("1692", "Ehmedê Xanî", "Mem û Zîn")
    assert quote["passage"] == "Rêza yek rêza du"
    assert quote["sense_id"] == sense_id
    synonym = next(r for r in _named(parsed, "relations") if r["sense_id"] == sense_id)
    assert (synonym["relation_type"], synonym["term"]) == ("synonyms", "yar")


def test_add_example_prompt_is_not_an_example() -> None:
    parsed = _page()
    assert not any("Nimûneyekê" in e["example"] for e in _named(parsed, "examples"))
    assert parsed.placeholder_examples == 1


def test_pronunciation_kinds() -> None:
    rows = _named(_page(), "pronunciations")
    kinds = {r["kind"]: r for r in rows}
    assert kinds["ipa"]["value"] == "/hɛˈvɑːl/"
    assert kinds["syllabification"]["value"] == "he·val"
    assert kinds["audio"]["value"] == "LL-Q36368_(kur)-Dildadil-heval.wav"
    assert kinds["audio"]["qualifier"] == "Amed"
    assert kinds["audio"]["media_id"] == media_id_for(AUDIO_URL)


def test_inflection_forms_carry_headers() -> None:
    parsed = _page()
    table = _named(parsed, "inflection_tables")[0]
    assert table["caption"] == "Tewandina heval"
    forms = _named(parsed, "inflection_forms")
    assert len(forms) == 1  # The "—" cell is not a form.
    assert forms[0]["form"] == "hevala"
    assert forms[0]["group_header"] == "Zayenda mê"
    assert forms[0]["row_header"] == "Îzafe"
    assert forms[0]["column_header"] == "Yekjimar"
    assert forms[0]["form_page"] == "hevala"


def test_translations_one_row_per_term() -> None:
    rows = _named(_page(), "translations")
    assert [r["term"] for r in rows] == ["vriend", "maat"]
    assert rows[0]["target_code"] == "af"
    assert rows[0]["target_language"] == "Afrîkansî"
    assert rows[0]["gloss"] == "heval"


def test_other_scripts_use_first_span_as_script_name() -> None:
    row = next(r for r in _named(_page(), "relations") if r["relation_type"] == "other_scripts")
    assert row["qualifier"] == "kurdî-erebî"
    assert row["term"] == "هه‌ڤال"


def test_bot_note_flags_only_its_language() -> None:
    entries = {e["language_code"]: e for e in _named(_page(), "entries")}
    assert entries["tr"]["is_auto_generated"] == 1
    assert entries["tr"]["auto_source_page"] == "av/Werger"
    assert entries["ku"]["is_auto_generated"] == 0


def test_media_records_illustration_and_audio() -> None:
    parsed = _page()
    image_id = media_id_for("_assets_/040c.jpg")
    assert parsed.media[image_id]["original_width"] == 1024
    assert parsed.media[media_id_for(AUDIO_URL)]["kind"] == "audio"
    usages = {u["media_id"]: u for u in _named(parsed, "media_usages")}
    assert usages[image_id]["role"] == "illustration"
    assert usages[image_id]["caption"] == "Du heval."


def test_soft_redirect_page() -> None:
    parsed = _page('<p>Binêre <a href="dib%C3%AAje" title="dibêje">dibêje</a>.</p>', "dibêjitin")
    assert _named(parsed, "pages")[0]["page_kind"] == "soft_redirect"
    assert parsed.rows["redirects"] == [("dibêjitin", "dibêje", "soft")]
    assert not parsed.rows.get("entries")


def test_conjugation_page_uses_leaf_tables_only() -> None:
    body = (
        "<table><tr><td><table class='wikitable'><tr><th>Kes</th><th>Dema niha</th></tr>"
        "<tr><th>ez</th><td>dicûm</td></tr></table></td></tr></table>"
    )
    parsed = _page(body, "Tewandin:cûn")
    assert _named(parsed, "pages")[0]["page_kind"] == "conjugation"
    entry = _named(parsed, "entries")[0]
    assert (entry["language_code"], entry["pos_list"]) == ("ku", "verb_conjugation")
    forms = _named(parsed, "inflection_forms")
    assert [f["form"] for f in forms] == ["dicûm"]
    assert forms[0]["row_header"] == "ez"


def test_lead_text_joins_first_language_without_fake_entry() -> None:
    parsed = _page("<p>Bibîne: av</p>" + BODY)
    assert {e["language_code"] for e in _named(parsed, "entries")} == {"ku", "tr"}
    lead = next(s for s in _named(parsed, "sections") if s["section_type"] == "lead")
    kurmanci = next(e for e in _named(parsed, "entries") if e["language_code"] == "ku")
    assert lead["entry_id"] == kurmanci["entry_id"]


def test_pending_definition_prompt_is_flagged_not_counted() -> None:
    h2 = '<div class="mw-heading mw-heading2"><h2 id="K"><span class="besazimani" id="ku">Kurmancî</span></h2></div>'
    h3 = '<div class="mw-heading mw-heading3"><h3 id="N">Navdêr</h3></div>'
    prompt = "<ol><li><i>Maneya vê madeyê hê nehatiye nivîsîn. Heke hûn maneya wê bizanin</i></li></ol>"
    parsed = _page(h2 + h3 + prompt)
    assert not parsed.rows.get("senses")
    entry = _named(parsed, "entries")[0]
    assert (entry["sense_count"], entry["definition_pending"]) == (0, 1)


def test_footnote_marks_and_reference_lists_are_not_definition_text() -> None:
    h3 = '<div class="mw-heading mw-heading3"><h3 id="N">Navdêr</h3></div>'
    body = (
        h3 + '<ol><li>Gotineke kurdî.<sup class="reference"><a href="#c">[1]</a></sup></li></ol>'
        '<ol class="references"><li>Çavkanîyek</li></ol>'
    )
    senses = _named(_page(body), "senses")
    assert [s["definition"] for s in senses] == ["Gotineke kurdî."]


def test_h2_without_language_marker_is_not_a_language() -> None:
    body = (
        '<div class="mw-heading mw-heading2"><h2 id="B">Binêre</h2></div><p>av</p>'
        '<div class="mw-heading mw-heading2"><h2 id="T">Tabloya tewandinê</h2></div><p>x</p>'
    )
    parsed = _page(body, "Pîsîr")
    entries = _named(parsed, "entries")
    assert [e["entry_key"] for e in entries] == ["Pîsîr|und"]
    assert _named(parsed, "pages")[0]["language_count"] == 0
    kinds = {s["heading"]: s["section_type"] for s in _named(parsed, "sections")}
    assert kinds["Binêre"] == "see_also"
    assert kinds["Tabloya tewandinê"] == "inflection"


def test_repeated_language_merges_into_one_entry() -> None:
    h2 = '<div class="mw-heading mw-heading2"><h2 id="K"><span class="besazimani" id="ku">Kurmancî</span></h2></div>'
    h3 = '<div class="mw-heading mw-heading3"><h3 id="N">Navdêr</h3></div><ol><li>yek</li></ol>'
    parsed = _page(h2 + h3 + h2 + h3)
    entries = _named(parsed, "entries")
    assert len(entries) == 1
    assert entries[0]["sense_count"] == 2
    assert entries[0]["language_code"] == "ku"


@pytest.mark.parametrize(
    ("heading", "kind", "pos", "homograph"),
    [
        ("Navdêr", "pos", "noun", None),
        ("Navdêr 2", "pos", "noun", 2),
        ("Formeke lêkerê", "pos", "verb_form", None),
        ("Bide Ber", "compare", None, None),
        ("Bideber", "compare", None, None),
        ("‌Herwiha", "see_also", None, None),
        ("Etîmolojî", "etymology", None, None),
        ("واتە", "pos", "sense", None),
        ("Peyvek nenas", "other", None, None),
    ],
)
def test_classify_heading(heading: str, kind: str, pos: str | None, homograph: int | None) -> None:
    result = classify_heading(heading, 3)
    assert (result.kind, result.pos, result.homograph) == (kind, pos, homograph)


def test_biwej_depends_on_level() -> None:
    assert classify_heading("Biwêj", 3).pos == "idiom"
    assert classify_heading("Biwêj", 4).kind == "idioms"


def test_normalize_heading_folds_diacritics() -> None:
    assert normalize_heading("  Çavkanî : ") == "cavkani"


def test_link_helpers() -> None:
    assert link_target("l%C3%AAzim#Kurmancî") == "lêzim"
    assert link_target("https://sq.wiktionary.org/wiki/mik") is None
    assert normalize_asset_path("../_assets_/x.png") == "_assets_/x.png"
    assert normalize_asset_path("https://example.org/x.png") is None
    assert commons_file_from_url(AUDIO_URL) == "LL-Q36368_(kur)-Dildadil-heval.wav"
    assert (
        commons_file_from_url("https://upload.wikimedia.org/wikipedia/commons/a/aa/X.wav")
        == "X.wav"
    )
