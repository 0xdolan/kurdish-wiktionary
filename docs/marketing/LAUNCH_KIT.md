# Kurdish Wiktionary dataset: launch kit

Ready-to-use copy. Replace `<KAGGLE_URL>` with https://www.kaggle.com/datasets/zeroxdolan/wiktionary-wordlists, and update the numbers from `build/release/quality/QUALITY.md` if they have changed. **Have a native speaker read the Kurmancî and Soranî text before posting.** It was drafted without native review.

## Taglines

- The Kurdish Wiktionary, ready to build with.
- Kurdish words, ready to build with.
- One lexicon. Every format.
- Kurmancî: *Ferhenga Kurdî, ji bo her kesî.*
- Soranî: <span dir="rtl">فەرهەنگی کوردی، بۆ هەمووان.</span>

## Introductions

**One line:** The Kurdish Wiktionary dataset is a structured dataset of the Kurdish Wiktionary: over a million entries as SQL, Excel, Parquet and an offline dictionary.

**One paragraph:** Kurdish is spoken by tens of millions of people, yet developers and researchers have few clean language resources for it. This dataset takes Wîkîferheng, the Kurdish Wiktionary built by volunteers, and turns its pages into documented tables: definitions, pronunciations, recordings, etymologies, inflected forms, translations and word relations, each in its own table. It comes as Parquet, SQL, Excel, CSV and JSONL, along with an offline dictionary for GoldenDict and MDict. It also says where the data is weak: bot-made entries are flagged, and every release ships a quality report.

**About (for bios and directories):** Open dataset of the Kurdish Wiktionary. Text CC BY-SA 4.0 from Wîkîferheng contributors. Independent project.

Use this notice wherever the name or logo is prominent: *Independent project. Not produced or endorsed by the Wikimedia Foundation or the Wîkîferheng community. Wiktionary and its logo are trademarks of the Wikimedia Foundation.*

## Launch checklist

1. [ ] Kaggle dataset is public, and the page looks right on desktop and phone
2. [ ] Starter notebook is published and linked
3. [ ] Landing page is live (GitHub Pages from `site/`), and its Kaggle link works
4. [ ] GitHub README links to Kaggle
5. [ ] Native speaker has reviewed the Kurdish copy
6. [ ] Wîkîferheng community told first, as a courtesy (see below)
7. [ ] Then post, in the order below

## Announcements

### Wîkîferheng community (first, on the wiki's community page)

> Silav! I've built an open dataset from Wîkîferheng's public dumps (<KAGGLE_URL>). It credits contributors under CC BY-SA 4.0, and it isn't an official project. The aim is to make your work usable for Kurdish language technology and for offline dictionaries. I'd welcome feedback, especially on parsing mistakes. Corrections stay here on the wiki, and each new dump carries them into the dataset.

### X / Bluesky / Mastodon

> Kurdish language data just got easier to use. This dataset turns the Kurdish Wiktionary into 1.1M+ entries of clean tables as Parquet, SQL and Excel, plus an offline dictionary and recordings in many languages. <KAGGLE_URL>

Attach `ad-square-dark.png`.

### LinkedIn

> Building anything with Kurdish is harder than it should be. There's little clean, documented data.
>
> So I've published a structured dataset of Wîkîferheng, the Kurdish Wiktionary:
>
> - 1.1M+ entries, including 440K+ in Kurmancî (many are inflected forms)
> - Definitions, pronunciations, etymologies, inflected forms and translations, each in its own table
> - Parquet, SQL, Excel, CSV and JSONL, plus an offline dictionary
> - A quality report, with bot-made entries flagged
>
> All the credit for the words goes to the volunteers who wrote them. The dataset is under CC BY-SA 4.0: <KAGGLE_URL>

Attach `social-card-dark.png`.

### Hacker News (Show HN)

**Title:** Show HN: The Kurdish Wiktionary as structured open data

> I wanted Kurdish lexical data I could query, and found only wiki dumps. This project parses the Kiwix ZIM dumps of ku.wiktionary.org into a relational schema that follows the wiki's own structure (page, language, part of speech, subsection). Every section type gets a table.
>
> Some things I found: the ZIM dumps contain no audio at all, so recordings have to come from Commons at a polite rate. Their ".jpg" images are actually WebP. And about a fifth of entries are bot-generated from translation tables, which the wiki discloses in a template, so I expose that as a flag. It's one of the most useful filters in the data.
>
> Code: https://github.com/0xdolan/kurdish-wiktionary Data: <KAGGLE_URL>

### Reddit (r/kurdish, r/datasets, r/LanguageTechnology)

Check each subreddit's self-promotion rules first.

> **An open dataset of the Kurdish Wiktionary (1.1M+ entries, CC BY-SA)**
>
> It has definitions, IPA, recordings (mostly non-Kurdish), etymologies, inflection tables, translations and synonyms, in Parquet, SQL, Excel, CSV and JSONL, with an offline dictionary for GoldenDict/MDict too. Be aware that most entries describe non-Kurdish words in Kurdish, many are thin, and a fifth are marked bot-made. Those are flagged, and there's a quality report. Feedback welcome: <KAGGLE_URL>

### Kurmancî post

> Ji bo hemû kesan: Wîkîferheng wekî daneyên vekirî. Zêdetirî 440 hezar gotarên kurmancî, bi bilêvkirin, etîmolojî, tewandin û werger. Herwiha ferhengeke offline ji bo GoldenDict û MDict. <KAGGLE_URL>

### Soranî post

<div dir="rtl">

> بۆ هەمووان: ویکیفەرهەنگی کوردی وەک داتای کراوە. فەرهەنگێکی ئۆفلاین بۆ GoldenDict و MDict، لەگەڵ داتا بۆ گەشەپێدەران. <KAGGLE_URL>

</div>

### Email to researchers and teachers

**Subject:** A structured Kurdish lexicon for your work

> Hello,
>
> I've published a dataset built from the Kurdish Wiktionary: definitions, pronunciations, recordings, etymologies, inflected forms and translations. It's available as Excel, SQL and data-science formats, with an offline dictionary for study.
>
> It's community-written, so it isn't a reviewed reference, and the quality report explains where to be careful. If it's useful to your work or your students, I'd be glad to hear what would make it better.
>
> <KAGGLE_URL>

## Ads

Only run paid ads if you have a budget and a reason. An open dataset usually spreads better through communities. If you do:

| Ad image | Headline | Text | Audience |
|---|---|---|---|
| `ad-square-{light,dark}.png` | Kurdish words, ready to build with | 1.1M+ entries as open data. | Language learners, Kurdish diaspora, educators |
| `ad-portrait-{light,dark}.png` | One lexicon. Every format. | Parquet, SQL, Excel, JSONL and an offline dictionary. | Developers, NLP and data science |
| `ad-story-{light,dark}.png` | The Kurdish dictionary, offline | For GoldenDict and MDict. | Dictionary app users, students |
| `ad-leaderboard-{light,dark}.png` | The Kurdish Wiktionary as open data | | Language tech and open-data sites |

Don't claim "largest", "complete" or "official".

## FAQ

**Is this official?** No. It's an independent project built from public dumps, and it isn't endorsed by the Wikimedia Foundation or the Wîkîferheng community.

**Can I use it commercially?** The text is CC BY-SA 4.0, which allows commercial use if you give credit and share adaptations under the same licence. Media licences vary per file.

**Is it all Kurdish?** No. Wîkîferheng explains words from many languages in Kurdish. About 440K entries are Kurmancî, many of them inflected forms, and about 6K are Soranî. Recordings are mostly English, German and French, and about 3,300 are Kurmancî.

**How accurate is it?** It's community-written, and part of it is machine-made. Treat it as a useful resource, not an authority. `QUALITY.md` has the details.

**I found a mistake.** Fix it on [Wîkîferheng](https://ku.wiktionary.org), and it will reach the next release. Report parsing bugs on [GitHub](https://github.com/0xdolan/kurdish-wiktionary/issues).

## Measures of success

Track Kaggle downloads and notebooks using the dataset, GitHub stars and issues, and, most importantly, projects that actually build on it. Ask users what they made.
