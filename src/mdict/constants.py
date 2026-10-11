"""Shared MDict export constants."""

STYLESHEET_HREF = "css/wiktionary.css"
SPEAKER_ICON_HREF = "img/volume-up.png"

STYLESHEET_LINK = (
    f'<link rel="stylesheet" type="text/css" href="{STYLESHEET_HREF}" />'
)

ENTRY_SCRIPT_HREF = "js/wikt-entry.js"

ENTRY_SCRIPT_TAG = f'<script type="text/javascript" src="{ENTRY_SCRIPT_HREF}"></script>'

# External links from MDict articles (not entry://).
WIKTIONARY_EXTERNAL_REL = 'noopener noreferrer'
WIKTIONARY_EXTERNAL_TARGET = "_blank"
