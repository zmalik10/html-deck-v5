"""CV-04 — Section Header, Gradient Band  (renderer: section_gradient, shape: section)

A chapter divider: accent rule, section number, large section title. No body content.

Data contract (`d`):
    num    str   section number/label (e.g. "01")
    title  str   the section title
"""
from ._kit import stage, ACCENT


def render(c, d):
    inner = ('<div style="width:80px;height:5px;background:var(--sb-sky);margin-bottom:28px"></div>'
             + c.b("n", "label", d["num"], "div", "", "font-size:22px;font-weight:900;letter-spacing:.3em;%s" % ACCENT)
             + c.b("t", "headline", d["title"], "h2", "hl", "font-size:76px;margin-top:8px"))
    return stage(inner, "display:flex;flex-direction:column;justify-content:center;padding:0 110px")
