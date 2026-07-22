"""NM-07 — Icon Cards, N-Across  (renderer: icon_cards, shape: n-across)

A titled row of equal cards, each: icon tile + card title + body. The standard
"three reasons / three pillars" beat. Icons use the shared tinted-tile treatment.

Data contract (`d`):
    title  str
    cards  list of (icon_name, card_title, card_body)
    stage_class str (optional) extra stage class (deck-local hook, e.g. review demos)
"""
from ._kit import stage, icon_tile, CENTER


def render(c, d):
    cs = ""
    for i, (icon, ct, cb) in enumerate(d["cards"]):
        cs += ('<div style="flex:1;background:var(--sb-panel-bg);border-radius:16px;padding:30px;'
               'display:flex;flex-direction:column;gap:15px">'
               + icon_tile(icon)
               + c.b("ct%d" % i, "card_title", ct, "div", "hl", "font-size:23px")
               + c.b("cb%d" % i, "card_body", cb, "div", "body", "font-size:17px")
               + '</div>')
    inner = (c.b("t", "headline", d["title"], "h2", "hl", "font-size:46px")
             + '<div style="display:flex;gap:24px;margin-top:32px;align-items:stretch">%s</div>' % cs)
    return stage(inner, CENTER + "padding:80px 90px", d.get("stage_class", ""))


SAMPLE = {"title": "Built for how contractors actually work",
          "cards": [("layers", "One platform", "Design, PM, safety and finance — connected, not bolted together."),
                    ("bar-chart", "smrt-E does the busywork", "AI turns jobsite data into insight and paperwork."),
                    ("shield-check", "By construction people", "Decades of industry leadership, not a side project.")]}
