"""NM-04 — Big Statement  (renderer: statement, shape: single)

One full-slide claim, optionally with a supporting line. The emotional/thesis beat.

Data contract (`d`):
    text   str   the statement (may contain a stat — pass its fact id in `facts`)
    sub    str   (optional) supporting line
    facts  list  (optional) approved-fact ids cited by the statement
"""
from ._kit import stage, CENTER


def render(c, d):
    inner = c.b("t", "headline", d["text"], "h2", "hl",
                "font-size:72px;max-width:1010px", facts=d.get("facts"))
    if d.get("sub"):
        inner += c.b("s", "subhead", d["sub"], "div", "subhead",
                     "font-size:27px;margin-top:26px;max-width:860px;line-height:1.35")
    return stage(inner, CENTER + "padding:104px")


SAMPLE = {"text": "$1.3 trillion is spent on U.S. construction every year — and most of it runs on spreadsheets.",
          "sub": "The industry that builds everything is the last to adopt software built for it.",
          "facts": []}
