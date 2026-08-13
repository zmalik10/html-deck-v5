# Montserrat TTFs (for PPTX/PDF viewing)

The deck HTML embeds the woff2 files, so the browser always renders the brand font.
**PPTX exports only reference Montserrat by name** — any machine viewing or presenting
the .pptx must have Montserrat installed or PowerPoint substitutes a different font.

These TTFs were converted from the sibling woff2 files with corrected name tables
(family "Montserrat" Regular/Bold + "Montserrat Black"). Install on any Mac used to
review or present exports:

    cp assets/fonts/ttf/*.ttf ~/Library/Fonts/

Tell clients the font is free (Google Fonts) if they plan to edit the deck.
