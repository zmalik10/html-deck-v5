"""CC-06 — Takeaways / So-What  (renderer: takeaways, shape: list)

A titled list of conclusions. Each point gets a sky arrow chip; generous line rhythm;
max ~5 points (more belongs on two slides).

Data contract (`d`):
    title   str
    points  list of str
"""
from ._kit import stage, CENTER


def render(c, d):
    lis = ""
    for i, p in enumerate(d["points"][:5]):
        lis += ('<li style="display:flex;gap:18px;align-items:flex-start;margin:19px 0">'
                '<span aria-hidden="true" style="flex:none;width:34px;height:34px;border-radius:9px;'
                'background:rgba(0,178,227,0.14);color:var(--sb-sky);display:flex;align-items:center;'
                'justify-content:center;font-size:17px;font-weight:800">&#10148;</span>'
                + c.b("p%d" % i, "list_item", p, "span", "body", "font-size:23px;line-height:1.45")
                + '</li>')
    inner = (c.b("t", "headline", d["title"], "h2", "hl", "font-size:50px")
             + '<ul style="list-style:none;padding:0;margin:28px 0 0;max-width:1000px">%s</ul>' % lis)
    return stage(inner, CENTER + "padding:80px 104px")


SAMPLE = {"title": "Why now",
          "points": ["A generation comfortable with software is running jobsites",
                     "AI finally makes the paperwork disappear",
                     "Margins are too thin to keep guessing",
                     "The tools that win are the ones people actually use"]}
