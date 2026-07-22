"""CV-06 — Closing CTA  (renderer: closing, shape: closing)

The deck's final beat: big close line, contact row, one CTA button. No footer chrome
(role-based rules hide it on closings).

Data contract (`d`):
    title    str   the close ("Let's build smarter.")
    contact  str   contact row ("rowan@smrtbld.com · smrtbld.com")
    cta      str   button label
"""
from ._kit import stage, CENTER, kicker_bar


def render(c, d):
    inner = (c.b("t", "headline", d["title"], "h2", "hl", "font-size:88px")
             + kicker_bar()
             + c.b("k", "subhead", d["contact"], "div", "subhead", "font-size:24px;margin-top:30px")
             + '<div style="margin-top:36px">'
             + c.b("cta", "cta", d["cta"], "a", "cta")
             + '</div>')
    return stage(inner, CENTER + "padding:104px")


SAMPLE = {"title": "Let's build smarter.", "contact": "rowan@smrtbld.com  ·  smrtbld.com",
          "cta": "Book a walkthrough"}
