"""NM-03 — KPI Hero  (renderer: kpi_hero, shape: single)

One huge proof number with a claim line and a sourced support sentence. The number and
its claim share a left baseline; the source renders as a caption, not body copy.

Data contract (`d`):
    num      str   the big number ("2x", "$180M")
    numfact  str   approved-fact id backing it (required — rendered stat)
    claim    str   the claim line under the number
    support  str   supporting sentence; put the source in `source`
    source   str   (optional) source attribution, rendered as a caption
"""
from ._kit import stage, CENTER


def render(c, d):
    inner = (c.b("n", "stat", d["num"], "div", "kpi-num", "font-size:200px;line-height:.88", facts=[d.get("numfact")])
             + c.b("c", "headline", d["claim"], "div", "hl", "font-size:44px;margin-top:18px")
             + c.b("s", "body", d["support"], "div", "body", "font-size:21px;margin-top:16px;max-width:760px"))
    if d.get("source"):
        inner += c.b("src", "caption", d["source"], "div", "",
                     "font-size:14px;margin-top:14px;font-style:italic;color:var(--sb-body-on-dark);opacity:.75")
    return stage(inner, CENTER + "padding:96px 104px")


SAMPLE = {"num": "2x", "numfact": "fact-2x", "claim": "Median profit-margin lift",
          "support": "Contractors on purpose-built PM software vs. spreadsheets.",
          "source": "Source: Dodge Construction Network"}
