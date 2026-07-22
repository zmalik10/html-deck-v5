"""AN-03 — Horizontal Comparison Bars  (renderer: hbars, shape: rows)

A titled set of labelled horizontal bars with right-aligned values. Pure HTML/CSS bars
(each bar is a real shape for export — NOT a data-chart native chart; use the chart
renderers for those). EVERY visible text carries a data-block so nothing drops in PPTX.

Data contract (`d`):
    title  str
    rows   list of (label, value_num, display)   value_num scales the bar (max = 100%),
           display is the printed value ("34%"); back each display with a fact id in
           `rowfacts` (aligned list) — they are rendered stats.
    rowfacts list  approved-fact ids per row
"""
from ._kit import stage, CENTER


def render(c, d):
    mx = max(v for _, v, _ in d["rows"]) or 1
    rows = ""
    for i, (lab, v, disp) in enumerate(d["rows"]):
        fact = (d.get("rowfacts") or [None] * len(d["rows"]))[i]
        rows += ('<div style="display:flex;align-items:center;gap:22px;margin:15px 0">'
                 + c.b("l%d" % i, "label", lab, "div", "body", "width:255px;font-size:19px;flex:none")
                 + '<div style="flex:1;height:32px;background:var(--sb-panel-bg);border-radius:7px;overflow:hidden">'
                   '<div style="width:%d%%;height:100%%;background:var(--sb-sky);border-radius:7px"></div></div>'
                 % int(v / mx * 100)
                 + c.b("v%d" % i, "stat", disp, "div", "kpi-num",
                       "width:96px;font-size:26px;text-align:right;flex:none", facts=[fact])
                 + '</div>')
    inner = (c.b("t", "headline", d["title"], "h2", "hl", "font-size:46px")
             + '<div style="margin-top:30px">%s</div>' % rows)
    return stage(inner, CENTER + "padding:80px 104px")


SAMPLE = {"title": "Where the time goes on a typical project",
          "rows": [("Rework & errors", 34, "34%"), ("Chasing information", 27, "27%"),
                   ("Manual reporting", 22, "22%"), ("Actual building", 17, "17%")],
          "rowfacts": ["fact-34", "fact-27", "fact-22", "fact-17"]}
