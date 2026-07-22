"""NM-04q — Pull Quote  (renderer: quote, shape: single)

One voice-of-customer quote with attribution. Typography rules (fixes the cycle-4
"doubled quote marks" defect): the quote TEXT run carries NO quotation glyphs at all —
the punctuation is the large blue SVG ornament, used TWICE: one OPENING mark before the
text (top-left) and one CLOSING mark after it (bottom-right of the quote block), where
the closing mark is the same ornament rotated 180deg. This removes the previous
double-marking (blue opening ornament PLUS white curly quotes in the text). The
ornament exports as an image object; no oversized text glyphs, no unclosed quote.

Data contract (`d`):
    text  str   the quote, WITHOUT quotation marks (the SVG ornaments ARE the marks)
    who   str   attribution (rendered with an em-dash lead-in)
"""
from ._kit import stage, CENTER

_MARK_PATHS = ('<path d="M2 46 Q2 14 26 0 L30 8 Q14 18 13 30 Q14 29 18 29 Q28 29 28 38.5 Q28 46 18 46 Z" fill="var(--sb-sky)"/>'
               '<path d="M36 46 Q36 14 60 0 L64 8 Q48 18 47 30 Q48 29 52 29 Q62 29 62 38.5 Q62 46 52 46 Z" fill="var(--sb-sky)"/>')


def _mark(closing=False):
    """The large blue quote ornament. Opening = as drawn (top-left); closing = the SAME
    mark rotated 180deg, pushed to the bottom-right of the quote block (mirror pair)."""
    style = ("display:block;width:64px;height:46px;opacity:.85;"
             + ("align-self:flex-end;margin-top:22px;transform:rotate(180deg)"
                if closing else "align-self:flex-start;margin-bottom:22px"))
    return ('<svg aria-hidden="true" width="64" height="46" viewBox="0 0 64 46" style="%s">%s</svg>'
            % (style, _MARK_PATHS))


def render(c, d):
    text = d["text"].strip().rstrip(".")
    block = ('<div style="max-width:1000px;display:flex;flex-direction:column">'
             + _mark(False)
             + c.b("q", "quote", text, "div", "hl",
                   "font-size:48px;font-weight:700;line-height:1.18")
             + _mark(True)
             + '</div>')
    inner = (block
             + c.b("w", "caption", "&mdash; " + d["who"], "div", "subhead",
                   "font-size:21px;margin-top:26px"))
    return stage(inner, CENTER + "padding:96px 104px")


SAMPLE = {"text": "This is the first tool my whole team actually logs into every day",
          "who": "Operations Director, pilot customer"}
