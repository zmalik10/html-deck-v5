"""NM-02 — Three Big Stats  (renderer: three_stats, shape: n-across)

A title over three equal proof-metric columns, each an optional icon + number + label.

Data contract (`d`):
    title  str
    stats  list of (num, label, fact_id, icon_name)   exactly the three columns;
           `icon_name` may be "" / None for no icon; `fact_id` backs the number.
"""
from ._kit import stage


def render(c, d):
    cols = ""
    for i, (num, lab, fact, icon) in enumerate(d["stats"]):
        cols += ('<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;%s">' % ("border-right:1px solid rgba(255,255,255,0.10)" if i < 2 else "")
                 + ('<svg class="icon" data-icon="%s" style="width:44px;height:44px"></svg>' % icon if icon else "")
                 + c.b("n%d" % i, "stat", num, "div", "kpi-num", "font-size:104px", facts=[fact])
                 + c.b("l%d" % i, "stat_label", lab, "div", "", "font-size:18px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;text-align:center;color:var(--sb-body-on-dark)") + '</div>')
    inner = ('<div style="padding:48px 72px 24px">'
             + c.b("t", "headline", d["title"], "h2", "hl", "font-size:48px") + '</div>'
             + '<div style="flex:1;display:flex">%s</div>' % cols)
    return stage(inner, "display:flex;flex-direction:column")
