"""PR-04 — Numbered Process Flow  (renderer: process, shape: flow)

A titled left-to-right flow of numbered steps joined by a connector line. Each step's
number sits INSIDE its circle as one visual unit (the number is a data-block; exporters
attach small in-shape text to the shape so circle+number never separate — the round-2
"numbers don't line up with their circles" fix).

Data contract (`d`):
    title  str
    steps  list of (step_title, step_body)   2-5 steps
"""
from ._kit import stage, CENTER


def render(c, d):
    n = len(d["steps"])
    cells = ""
    for i, (st, sb) in enumerate(d["steps"][:5]):
        connector = ""
        if i < n - 1:
            connector = ('<div aria-hidden="true" style="position:absolute;left:54px;top:26px;'
                         'right:-26px;height:2px;background:rgba(0,178,227,0.35)"></div>')
        cells += ('<div style="flex:1;position:relative;display:flex;flex-direction:column;gap:13px">'
                  + connector
                  + '<div style="position:relative;width:54px;height:54px;border-radius:50%;'
                    'background:var(--sb-sky);display:flex;align-items:center;justify-content:center">'
                  + c.b("n%d" % i, "label", str(i + 1), "span", "",
                        "color:var(--sb-ink);font-weight:900;font-size:24px;line-height:1")
                  + '</div>'
                  + c.b("st%d" % i, "card_title", st, "div", "hl", "font-size:22px")
                  + c.b("sb%d" % i, "card_body", sb, "div", "body", "font-size:16px")
                  + '</div>')
    inner = (c.b("t", "headline", d["title"], "h2", "hl", "font-size:46px")
             + '<div style="display:flex;gap:52px;margin-top:44px">%s</div>' % cells)
    return stage(inner, CENTER + "padding:80px 90px")


SAMPLE = {"title": "From the field to the front office",
          "steps": [("Capture", "Field logs, photos and updates from any device."),
                    ("Connect", "Everything syncs to the project record in real time."),
                    ("Coordinate", "smrt-E flags risks and drafts the paperwork."),
                    ("Close out", "Bill, report and hand over — cleanly.")]}
