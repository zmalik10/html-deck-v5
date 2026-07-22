"""NM-01 — Narrative Split With Accent Stat  (renderer: narrative_split, shape: split)

Thesis/mission on the left; one large accent stat anchoring it on the right.

Data contract (`d`):
    label      str   kicker/eyebrow over the headline
    headline   str   the thesis / mission line
    body       str   supporting paragraph
    bodyfacts  list  (optional) approved-fact ids the body cites
    stat       str   the big accent number (e.g. "$2B+")
    statfact   str   approved-fact id backing the stat (required — it's a rendered stat)
    statlabel  str   caption under the stat
"""
from ._kit import stage


def render(c, d):
    left = (c.b("lab", "label", d["label"], "div", "label")
            + c.b("h", "headline", d["headline"], "h2", "hl", "font-size:56px;margin-top:18px")
            + c.b("body", "body", d["body"], "p", "body", "font-size:21px;margin-top:22px;max-width:46ch", facts=d.get("bodyfacts")))
    right = ('<div style="display:flex;flex-direction:column;justify-content:center;align-items:flex-start;background:var(--sb-sky);padding:0 56px">'
             + c.b("stat", "stat", d["stat"], "div", "", "font-size:150px;font-weight:900;line-height:1;color:var(--sb-ink)", facts=[d["statfact"]])
             + c.b("statlab", "stat_label", d["statlabel"], "div", "", "font-size:18px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--sb-ink);margin-top:12px") + '</div>')
    inner = ('<div style="flex:0 0 60%%;display:flex;flex-direction:column;justify-content:center;padding:0 60px">%s</div>%s' % (left, right))
    return stage(inner, "display:flex")
