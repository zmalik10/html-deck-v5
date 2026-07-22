"""CC-03 — Two-Column Comparison  (renderer: two_col, shape: split)

Before/after or us/them. Left column carries the pain (copper accent, ✕ glyphs);
right column carries the win (sky accent, ✓ glyphs). Equal-height cards.

Data contract (`d`):
    title  str
    lh,rh  str   column headers (e.g. "Today" / "With SmartBuild")
    left   list of str
    right  list of str
"""
from ._kit import stage, CENTER


def _col(c, side, head, items, accent, glyph):
    lis = ""
    for i, it in enumerate(items):
        lis += ('<li style="display:flex;gap:12px;align-items:flex-start;margin:13px 0">'
                '<span aria-hidden="true" style="%s;font-weight:800;font-size:19px;line-height:1.5">%s</span>'
                % (accent, glyph)
                + c.b("%s%d" % (side, i), "list_item", it, "span", "body", "font-size:20px")
                + '</li>')
    return ('<div style="flex:1;background:var(--sb-panel-bg);border-radius:16px;padding:34px 38px">'
            + c.b("%sh" % side, "card_title", head, "div", "hl", "font-size:24px;%s" % accent)
            + '<ul style="list-style:none;margin:18px 0 0;padding:0">%s</ul></div>' % lis)


def render(c, d):
    inner = (c.b("t", "headline", d["title"], "h2", "hl", "font-size:46px")
             + '<div style="display:flex;gap:30px;margin-top:32px;align-items:stretch">'
             + _col(c, "l", d.get("lh", "Today"), d["left"], "color:var(--sb-copper)", "&#10005;")
             + _col(c, "r", d.get("rh", "With SmartBuild"), d["right"], "color:var(--sb-sky)", "&#10003;")
             + '</div>')
    return stage(inner, CENTER + "padding:80px 96px")


SAMPLE = {"title": "Excel vs. purpose-built",
          "lh": "Today", "rh": "With SmartBuild",
          "left": ["Version chaos", "No audit trail", "Breaks at scale", "Nothing connects"],
          "right": ["One source of truth", "Every change tracked", "Built for the field", "Design → finance connected"]}
