#!/usr/bin/env python3
"""render_slides.py — turn a plan's chosen TEMPLATES + content into native, theme-flexible
slides (PASS 2 BUILD authoring, done by the engine instead of by hand).

Each plan slide names a template id in layout.family (e.g. NM-18). catalog.json maps that id
to a RENDERER name (e.g. icon_list). This module implements those renderers as theme-correct,
brand-correct code built on the shared kit (sb-card, --sb-title headings, theme body tokens,
.on-media over photos, .cta-btn, img-cover, 6px radii, reveal). The renderer is a STARTING
POINT: it lays out the template's shape and fills it with the slide's real content_blocks /
icon_intent / image_intent — adapt freely, but the output is code, never a pasted screenshot,
and it is correct in BOTH light and dark by construction.

    python engine/render_slides.py --skill-path . --plan plan.json --out slides.html

Unimplemented templates fall back to a generic stacked-card renderer (logged), so any plan
still produces a coherent, on-brand slide.
"""
import json, os, re, argparse, subprocess, sys

PROD = ["smrtPAY", "smrtGC", "smrtSUB", "smrtAEC", "smrtAE", "smrt-E"]
ACCENT = {"smrtGC": "sky", "smrtSUB": "copper", "smrtAE": "steel", "smrtAEC": "steel",
          "smrt-E": "pink", "smrtPAY": "navy"}

# ---------- content helpers ----------
def brandify(text):
    text = (text or "").replace("SmartBuild", "SMARTBUILD")
    for tok in PROD:
        text = text.replace(tok, '<span class="no-caps">%s</span>' % tok)
    return text

def blk(b, tag="div", cls="", style="", raw=None):
    if not b:
        return ""
    # Rich inline formatting authored in the live editor (bold/italic/underline/colour/
    # line-breaks) is stored as text_html and rendered VERBATIM; otherwise plain text.
    if raw is not None:
        inner = raw
    elif b.get("text_html"):
        inner = b["text_html"]
    else:
        inner = brandify(b.get("text", ""))
    c = ' class="%s"' % cls if cls else ""
    st = ' style="%s"' % style if style else ""
    return '<%s data-block="%s" data-block-type="%s"%s%s>%s</%s>' % (
        tag, b["block_uuid"], b.get("type", "body"), c, st, inner, tag)

def grp(slide):
    d = {}
    for b in slide.get("content_blocks", []):
        if b.get("status") == "deleted":
            continue
        d.setdefault(b["type"], []).append(b)
    return d

def icons_of(slide):
    return [i.get("name") for i in slide.get("icon_intent", []) if i.get("name")]

def has_image(slide):
    ii = slide.get("image_intent") or {}
    return bool(ii.get("tag"))

def img_tag(slide):
    return (slide.get("image_intent") or {}).get("tag", "")

def is_product_word(text):
    return (text or "").strip() in PROD

# ---------- kit primitives (theme-correct) ----------
def icon(name, size=34):
    return '<svg class="icon" data-icon="%s" style="width:%dpx;height:%dpx;flex:none"></svg>' % (name, size, size)

def rule(mt="0", center=False):
    m = "margin:%s auto 0;" % mt if center else "margin-top:%s;" % mt
    return '<div style="%swidth:64px;height:8px;background:var(--sb-product-accent,var(--sb-sky))"></div>' % m

def photo_bg(tag, scrim="90deg,rgba(6,12,26,0.86) 0%,rgba(6,12,26,0.45) 52%,rgba(6,12,26,0.05) 100%"):
    # BOLD brand duotone: the photo is colourised by a saturated accent (multiply), then a
    # navy legibility gradient keeps .on-media text readable on the content side. Photos read
    # as branded colour, not grey stock.
    return ('<div style="position:absolute;inset:0"><img data-image="%s" class="img-cover"></div>'
            '<div style="position:absolute;inset:0;background:var(--sb-product-accent,var(--sb-navy));mix-blend-mode:multiply;opacity:0.5"></div>'
            '<div style="position:absolute;inset:0;background:linear-gradient(%s)"></div>') % (tag, scrim)

def logo_mark():
    return '<img data-logo="smartbuild" style="position:absolute;left:64px;top:52px;height:38px;z-index:4">'

def badge_mark(size=52):
    """The SmartBuild BADGE alone as the corner mark - a creative stand-in for the
    full wordmark (closings use this so the lockup is not overused). Follows the same
    white-on-dark / full-colour-on-light rule as the wordmark."""
    return '<img data-logo="smartbuild-badge" style="position:absolute;left:64px;top:46px;height:%dpx;z-index:4">' % size

# =====================================================================
# SHARED SHAPE PRIMITIVES  (theme-correct, hex-free, every word in a blk)
# ---------------------------------------------------------------------
# Contract for ALL primitives + renderers:
#   * Colours: ONLY var(--sb-*) tokens or rgba(); NEVER a raw #hex.
#   * Text: every visible word must go through blk(block_dict, ...) so it
#     carries data-block/data-block-type (preserves the block_uuid).
#   * White text is ONLY legal inside .on-media or on an accent/navy panel.
#     Filled accent panels => wrap content in class="on-media".
#   * Display/hero text (>=36px) uses .hl or color:var(--sb-title) (navy on
#     light, white on dark) - never a near-black token.
#   * Body/muted text uses var(--sb-body-on-dark); card titles use
#     var(--sb-text-on-dark). Card surfaces use class="sb-card".
#   * Icons come from icons_of(slide) (catalog names only); omit if absent.
# Primitives return an HTML STRING (compose them); a renderer returns
# (inner_html, pad).
# =====================================================================
ACCENT_CYCLE = ["var(--sb-sky)", "var(--sb-copper)", "var(--sb-steel)",
                "var(--sb-pink)", "var(--sb-navy)"]
ACC = "var(--sb-product-accent,var(--sb-sky))"

def _first(g, t):
    return g.get(t, [None])[0]

def _num(text):
    """Parse the leading numeric magnitude from a stat/label string (for chart geometry)."""
    m = re.search(r'-?\d[\d,\.]*', (text or "").replace(",", ""))
    try:
        return float(m.group(0)) if m else 0.0
    except Exception:
        return 0.0

def p_kicker(g):
    return blk(_first(g, "label"), "div", "label reveal", "margin-bottom:16px")

def p_title(g, size=46, center=False, mb="6px", block=None):
    """Headline as brand-navy display type + accent rule."""
    head = block or _headline_block(g)
    if not head:
        return ""
    ta = "text-align:center;" if center else ""
    r = ('<div style="display:flex;justify-content:center">' + rule(mb) + '</div>') if center else rule(mb)
    return blk(head, "h2", "hl reveal", "font-size:%dpx;margin:0;%s" % (size, ta)) + r

def p_body(block, size=19, mt="22px", mw="720px"):
    return blk(block, "div", "reveal", "font-size:%dpx;line-height:1.6;color:var(--sb-body-on-dark);margin-top:%s;max-width:%s" % (size, mt, mw))

def p_split(left, right, lflex="1", rflex="1", gap=44, align="stretch"):
    return ('<div style="display:flex;gap:%dpx;height:100%%;align-items:%s">'
            '<div style="flex:%s;display:flex;flex-direction:column;justify-content:center">%s</div>'
            '<div style="flex:%s;display:flex;flex-direction:column;justify-content:center">%s</div></div>'
            % (gap, align, lflex, left, rflex, right))

def p_media(tag, h=340, frame=True):
    """Framed image slot (emits an <img data-image> that BRAND resolves)."""
    inner = '<div style="border-radius:6px;overflow:hidden;height:%dpx"><img data-image="%s" class="img-cover"></div>' % (h, tag or "image")
    if frame:
        return ('<div class="reveal-right" style="width:100%%;background:%s;border-radius:10px;padding:14px;'
                'box-shadow:0 20px 50px rgba(6,12,26,0.18)">%s</div>' % (ACC, inner))
    return '<div class="reveal-right" style="width:100%%;border-radius:6px;overflow:hidden;height:%dpx"><img data-image="%s" class="img-cover"></div>' % (h, tag or "image")

def p_accent_box(inner_html, style=""):
    """Accent/navy filled panel; content is white via .on-media."""
    return ('<div class="reveal on-media" style="background:%s;border-radius:6px;padding:40px;%s">%s</div>'
            % (ACC, style, inner_html))

def p_cards(titles, bodies, ic=None, cols=3, scale=True, min_h=None):
    """Responsive grid of sb-cards: optional icon + title + body."""
    ic = ic or []
    n = min(len(titles), len(bodies)) if bodies else len(titles)
    cells = ""
    rev = "reveal-scale" if scale else "reveal"
    mh = "min-height:%dpx;" % min_h if min_h else ""
    for i in range(n):
        head = (icon(ic[i], 36) + '<div style="height:14px"></div>') if i < len(ic) else ""
        cells += ('<div class="%s sb-card" style="padding:26px 28px;%s">' % (rev, mh)
                  + head
                  + (blk(titles[i], "div", "no-caps", "font-weight:800;font-size:20px;color:var(--sb-text-on-dark);margin-bottom:8px") if i < len(titles) else "")
                  + (blk(bodies[i], "div", "", "font-size:16px;line-height:1.5;color:var(--sb-body-on-dark)") if i < len(bodies) else "")
                  + '</div>')
    return '<div style="display:grid;grid-template-columns:%s;gap:22px;width:100%%">%s</div>' % ("1fr " * cols, cells)

def p_stat_tiles(stats, labels, cols=None):
    n = min(len(stats), len(labels)) if labels else len(stats)
    cols = cols or max(1, n)
    cells = ""
    for i in range(n):
        cells += ('<div class="reveal-scale sb-card" style="padding:40px 28px;text-align:center">'
                  + blk(stats[i], "div", "kpi-num", "font-size:%dpx" % (84 if n <= 3 else 60))
                  + (blk(labels[i], "div", "kpi-label", "margin-top:12px;font-size:15px;color:var(--sb-body-on-dark)") if i < len(labels) else "")
                  + '</div>')
    return '<div style="display:grid;grid-template-columns:%s;gap:24px;width:100%%">%s</div>' % ("1fr " * cols, cells)

def p_list(items, accent=True, numbered=False, size=18):
    rows = ""
    for i, b in enumerate(items):
        if numbered:
            mark = ('<span aria-hidden="true" class="on-media" style="flex:none;width:30px;height:30px;border-radius:6px;background:%s;'
                    'display:flex;align-items:center;justify-content:center;font-weight:900;font-size:15px">%d</span>' % (ACC, i + 1))
        else:
            mark = '<span style="flex:none;width:9px;height:9px;border-radius:50%%;background:%s"></span>' % (ACC if accent else "var(--sb-body-on-dark)")
        rows += ('<div style="display:flex;gap:14px;align-items:center;padding:11px 0;border-top:1px solid var(--sb-border-subtle)">'
                 + mark + blk(b, "div", "", "font-size:%dpx;color:var(--sb-text-on-dark)" % size) + '</div>')
    return '<div class="reveal">%s</div>' % rows

def chevron_connector(color=ACC):
    """A right-pointing flow chevron as an inline SVG. MUST be SVG, not a CSS
    border+rotate() box — the latter has no fill and a non-uniform border, so the PPTX
    exporter drops it entirely (and can't represent the rotation). SVG rasterises to PNG
    on export like every other icon, so the arrow transfers to PowerPoint."""
    return ('<div style="flex:0 0 34px;display:flex;align-items:center;justify-content:center">'
            '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" style="opacity:0.6">'
            '<path d="M9 5l7 7-7 7" stroke="%s" stroke-width="4" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg></div>' % color)

def p_flow(titles, bodies, chevron=True):
    n = min(len(titles), len(bodies)) if bodies else len(titles)
    chev = chevron_connector(ACC)
    cards = ""
    for i in range(n):
        cards += ('<div class="reveal sb-card" style="flex:1;padding:30px 26px">'
                  + blk(titles[i], "div", "no-caps", "font-weight:900;font-size:22px;color:var(--sb-text-on-dark);margin-bottom:12px")
                  + (blk(bodies[i], "div", "", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark)") if i < len(bodies) else "")
                  + '</div>')
        if chevron and i < n - 1:
            cards += chev
    return '<div style="display:flex;gap:%dpx;width:100%%;align-items:stretch">%s</div>' % (6 if chevron else 22, cards)

def p_timeline(labels, titles, bodies):
    n = max(len(labels), len(titles), len(bodies))
    cols = ""
    for i in range(n):
        lab = blk(labels[i], "div", "label", "color:%s;margin-bottom:10px" % ACC) if i < len(labels) else ""
        node = '<div style="height:16px;height:16px;border-radius:50%%;background:%s;margin:8px 0"></div>' % ACC
        ttl = blk(titles[i], "div", "no-caps", "font-weight:800;font-size:19px;color:var(--sb-text-on-dark);margin:6px 0 6px") if i < len(titles) else ""
        bod = blk(bodies[i], "div", "", "font-size:14px;line-height:1.5;color:var(--sb-body-on-dark)") if i < len(bodies) else ""
        cols += '<div style="flex:1;padding:0 14px">%s%s%s%s</div>' % (lab, node, ttl, bod)
    line = '<div style="position:absolute;left:0;right:0;top:39px;height:3px;background:var(--sb-border-subtle);z-index:0"></div>'
    return '<div class="reveal" style="position:relative">%s<div style="display:flex;position:relative;z-index:1">%s</div></div>' % (line, cols)

def p_chips(label_blocks):
    prodcol = {"smrtGC": "var(--sb-sky)", "smrtSUB": "var(--sb-copper)", "smrtAE": "var(--sb-steel)",
               "smrtAEC": "var(--sb-steel)", "smrt-E": "var(--sb-pink)", "smrtPAY": "var(--sb-navy)"}
    chips = ""
    for b in label_blocks:
        txt = (b.get("text") or "").strip()
        col = prodcol.get(txt, ACC)
        chips += ('<div class="reveal-scale sb-card" style="flex:1;border-top:5px solid %s;padding:22px 10px;text-align:center">' % col
                  + blk(b, "div", "no-caps", "font-weight:800;font-size:22px;color:%s" % col) + '</div>')
    return '<div style="display:flex;gap:18px">%s</div>' % chips

def qmark(opening=True, size=80, color=None, align=None):
    """Decorative typographic quote mark. Every quote template pairs an OPENING
    mark before the quote with a CLOSING mark after it - never a lone opener.
    line-height is sized so the tall glyph is not clipped (older code used
    line-height:0 / height:0, which cut the mark and mis-placed it)."""
    color = color or ACC
    glyph = "&ldquo;" if opening else "&rdquo;"
    ta = ("text-align:%s;" % align) if align else ""
    return ('<div aria-hidden="true" style="font-size:%dpx;line-height:0.7;height:%dpx;'
            'color:%s;font-weight:800;%s">%s</div>' % (size, int(size * 0.62), color, ta, glyph))

def p_quote(quote_b, cite_b=None, on_media=False):
    col = "var(--sb-title)" if not on_media else "#fff"
    q = (qmark(True, 80, ACC)
         + blk(quote_b, "div", "reveal-hero no-caps", "font-size:46px;font-weight:800;line-height:1.25;color:%s;max-width:960px" % col)
         + qmark(False, 80, ACC)
         + (blk(cite_b, "div", "reveal", "font-size:15px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:%s;margin-top:28px" % ACC) if cite_b else ""))
    return q

def p_table(header_blocks, rows_blocks, highlight_row=None):
    """header_blocks: list of blocks; rows_blocks: list of lists of blocks."""
    ths = "".join('<th style="text-align:left;padding:14px 18px;font-weight:800;font-size:14px;letter-spacing:0.06em;text-transform:uppercase">'
                  + blk(h, "span", "on-media", "") + '</th>' for h in header_blocks)
    head = '<thead><tr class="on-media" style="background:%s">%s</tr></thead>' % (ACC, ths)
    body = ""
    for ri, row in enumerate(rows_blocks):
        hl = "background:rgba(255,255,255,0.05);" if (highlight_row is not None and ri == highlight_row) else ("background:rgba(255,255,255,0.02);" if ri % 2 else "")
        tds = "".join('<td style="padding:13px 18px;font-size:16px;color:var(--sb-text-on-dark);border-top:1px solid var(--sb-border-subtle)">'
                      + blk(c, "span", "", "") + '</td>' for c in row)
        body += '<tr style="%s">%s</tr>' % (hl, tds)
    return '<div class="reveal" style="border-radius:6px;overflow:hidden;border:1px solid var(--sb-border-subtle)"><table style="width:100%%;border-collapse:collapse">%s<tbody>%s</tbody></table></div>' % (head, body)

def p_photo_content(tag, content_html, align="center", scrim="90deg,rgba(6,12,26,0.92) 0%,rgba(6,12,26,0.55) 55%,rgba(6,12,26,0.15) 100%"):
    photo = photo_bg(tag, scrim) if tag else '<div style="position:absolute;inset:0;background:var(--sb-panel-bg)"></div>'
    return (photo + logo_mark()
            + '<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;justify-content:center;align-items:%s;padding:0 72px;box-sizing:border-box">%s</div>'
            % ("center;text-align:center" if align == "center" else "flex-start", content_html))

# ---------- chart primitives (SVG/CSS geometry; labels overlaid as blks) ----------
def c_bars(pairs, highlight_idx=None, horizontal=True):
    """pairs: list of (label_block, value_block). Geometry from _num(value)."""
    vals = [_num((v or {}).get("text")) for _, v in pairs] or [0]
    mx = max(vals + [1])
    rows = ""
    if horizontal:
        for i, (lb, vb) in enumerate(pairs):
            col = "var(--sb-copper)" if highlight_idx == i else ACC
            w = max(2, (vals[i] / mx) * 100)
            rows += ('<div style="display:flex;align-items:center;gap:16px;margin:10px 0">'
                     + blk(lb, "div", "", "flex:0 0 200px;font-size:15px;color:var(--sb-text-on-dark);text-align:right")
                     + '<div style="flex:1;height:26px;background:var(--sb-border-subtle);border-radius:6px;overflow:hidden">'
                     + '<div style="height:100%%;width:%.1f%%;background:%s;border-radius:6px"></div></div>' % (w, col)
                     + blk(vb, "div", "", "flex:0 0 90px;font-weight:900;font-size:17px;color:%s" % col) + '</div>')
        return '<div class="reveal" style="width:100%%">%s</div>' % rows
    # vertical
    for i, (lb, vb) in enumerate(pairs):
        col = "var(--sb-copper)" if highlight_idx == i else ACC
        h = max(3, (vals[i] / mx) * 100)
        rows += ('<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%%">'
                 + blk(vb, "div", "", "font-weight:900;font-size:16px;color:%s;margin-bottom:6px" % col)
                 + '<div style="width:60%%;height:%.1f%%;background:%s;border-radius:6px 6px 0 0"></div>' % (h, col)
                 + blk(lb, "div", "", "font-size:14px;color:var(--sb-body-on-dark);margin-top:8px;text-align:center") + '</div>')
    return '<div class="reveal" style="display:flex;gap:18px;align-items:stretch;height:280px">%s</div>' % rows

def c_donut(seg_blocks, size=240):
    vals = [_num((b or {}).get("text")) for b in seg_blocks] or [1]
    tot = sum(vals) or 1
    r, cx = 80, size / 2
    circ = 2 * 3.14159 * r
    off = 0.0
    arcs = ""
    legend = ""
    for i, b in enumerate(seg_blocks):
        frac = vals[i] / tot
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        arcs += ('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-width="34" '
                 'stroke-dasharray="%.2f %.2f" stroke-dashoffset="%.2f" transform="rotate(-90 %d %d)"/>'
                 % (cx, cx, r, col, circ * frac, circ * (1 - frac), -circ * off, cx, cx))
        off += frac
        legend += ('<div style="display:flex;align-items:center;gap:10px;margin:8px 0">'
                   '<span style="width:14px;height:14px;border-radius:3px;background:%s;flex:none"></span>' % col
                   + blk(b, "div", "", "font-size:16px;color:var(--sb-text-on-dark)") + '</div>')
    svg = '<svg viewBox="0 0 %d %d" style="width:%dpx;height:%dpx;flex:none">%s</svg>' % (size, size, size, size, arcs)
    return '<div class="reveal" style="display:flex;gap:44px;align-items:center">%s<div>%s</div></div>' % (svg, legend)

def c_rings(ring_blocks):
    """Concentric TAM/SAM/SOM rings (largest first)."""
    n = len(ring_blocks)
    circles = ""
    labels = ""
    for i, b in enumerate(ring_blocks):
        d = 100 - i * (70 // max(1, n))
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        circles += ('<div style="position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);'
                    'width:%d%%;height:%d%%;border-radius:50%%;background:%s;opacity:%.2f"></div>'
                    % (d, d, col, 0.85 - i * 0.18))
        labels += '<div style="margin:6px 0">' + blk(b, "div", "", "font-size:16px;color:var(--sb-text-on-dark)") + '</div>'
    rings = '<div style="position:relative;flex:0 0 320px;height:320px">%s</div>' % circles
    return '<div class="reveal" style="display:flex;gap:44px;align-items:center">%s<div>%s</div></div>' % (rings, labels)

def c_funnel(stage_blocks):
    n = len(stage_blocks)
    rows = ""
    for i, b in enumerate(stage_blocks):
        w = 100 - i * (55 // max(1, n))
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        rows += ('<div style="display:flex;justify-content:center;margin:6px 0">'
                 '<div class="on-media" style="width:%d%%;background:%s;padding:16px;text-align:center;border-radius:4px">' % (w, col)
                 + blk(b, "div", "", "font-weight:800;font-size:17px") + '</div></div>')
    return '<div class="reveal" style="width:100%%">%s</div>' % rows

def c_progress(pairs):
    """Horizontal % rows (pareto/dashboard); alias of horizontal bars."""
    return c_bars(pairs, horizontal=True)

# ---------- renderers: each returns (inner_html, pad) ----------
def _fallback(s, acc):
    g = grp(s)
    head = g.get("headline", [None])[0]
    parts = [blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 24px")] if head else []
    cards = ""
    bodies = g.get("body", []) + g.get("card_body", []) + g.get("list_item", [])
    titles = g.get("card_title", [])
    for i, cb in enumerate(bodies):
        t = titles[i] if i < len(titles) else None
        cards += ('<div class="reveal sb-card" style="padding:24px 26px">'
                  + (blk(t, "div", "no-caps", "font-weight:800;font-size:20px;color:var(--sb-text-on-dark);margin-bottom:6px") if t else "")
                  + blk(cb, "div", "", "font-size:16px;line-height:1.5;color:var(--sb-body-on-dark)")
                  + '</div>')
    inner = "".join(parts) + ('<div style="display:flex;flex-direction:column;gap:16px">%s</div>' % cards if cards else "")
    return inner, 64

def cover_geo(s, acc):
    g = grp(s)
    label, head = g.get("label", [None])[0], g.get("headline", [None])[0]
    sub, cap = g.get("subhead", [None])[0], g.get("caption", [None])[0]
    photo = photo_bg(img_tag(s)) if has_image(s) else ""
    motif = ('<div style="position:absolute;right:-40px;top:50%;transform:translateY(-50%);width:520px;height:520px;pointer-events:none;z-index:1">'
             '<div style="position:absolute;right:60px;top:40px;width:300px;height:300px;background:var(--sb-product-accent,var(--sb-sky));opacity:0.12;border-radius:6px;transform:rotate(12deg)"></div>'
             '<div style="position:absolute;right:150px;top:150px;width:220px;height:220px;border:3px solid var(--sb-product-accent,var(--sb-sky));opacity:0.30;border-radius:6px;transform:rotate(-8deg)"></div></div>')
    # product name in a title => the LOGO, not text
    if head and is_product_word(head.get("text")):
        prod = head["text"].strip()
        title = blk(head, "div", "reveal-hero", "margin:0",
                    raw='<img data-logo="%s" alt="%s" style="height:116px;display:block">' % (prod, prod))
    else:
        # Adaptive display size: a long title must not overflow the 720 canvas.
        n = len((head.get("text") or "")) if head else 0
        tsize = 104 if n <= 20 else 92 if n <= 30 else 78 if n <= 44 else 66
        title = blk(head, "h1", "hl reveal-hero", "font-size:%dpx;line-height:0.98;margin:0" % tsize)
    subsize = 30 if len((sub.get("text") or "")) <= 90 else 24 if sub else 30
    content = ('<div style="max-width:820px">'
               + blk(label, "div", "label reveal", "color:var(--sb-product-accent,var(--sb-sky));margin-bottom:20px")
               + title
               + blk(sub, "div", "reveal", "font-size:%dpx;font-weight:700;line-height:1.45;margin-top:24px" % subsize)
               + blk(cap, "div", "reveal", "font-size:15px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;opacity:0.85;margin-top:30px")
               + '</div>')
    wrap_cls = "on-media" if photo else ""
    inner = (photo + motif + logo_mark()
             + '<div class="%s" style="position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;justify-content:center;padding:0 72px;box-sizing:border-box">%s</div>'
             % (wrap_cls, content))
    return inner, 0

def closing_cta(s, acc):
    g = grp(s)
    head, sub, cta = g.get("headline", [None])[0], g.get("subhead", [None])[0], g.get("cta", [None])[0]
    photo = photo_bg(img_tag(s)) if has_image(s) else ""
    content = (blk(head, "h1", "hl reveal-hero", "font-size:80px;margin:0")
               + blk(sub, "div", "reveal no-caps", "font-size:26px;font-weight:700;margin-top:22px")
               + (blk(cta, "div", "cta-btn reveal", "margin-top:38px") if cta else ""))
    wrap_cls = "on-media" if photo else ""
    inner = (photo + badge_mark()
             + '<div class="%s" style="position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 72px;box-sizing:border-box">%s</div>'
             % (wrap_cls, content))
    return inner, 0

def photo_statement(s, acc):
    g = grp(s)
    label, head, sub = g.get("label", [None])[0], g.get("headline", [None])[0], g.get("subhead", [None])[0]
    photo = photo_bg(img_tag(s)) if has_image(s) else '<div style="position:absolute;inset:0;background:var(--sb-panel-bg)"></div>'
    content = ('<div style="max-width:640px">'
               + blk(label, "div", "label reveal", "color:var(--sb-product-accent,var(--sb-sky));margin-bottom:18px")
               + blk(head, "h2", "hl reveal-left", "font-size:52px;margin:0")
               + blk(sub, "div", "reveal no-caps", "font-size:22px;line-height:1.5;opacity:0.92;margin-top:20px")
               + '</div>')
    inner = (photo
             + '<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;align-items:center;padding:0 72px;box-sizing:border-box">%s</div>' % content)
    return inner, 0

def quote_full(s, acc):
    g = grp(s)
    quote, cap = g.get("quote", [None])[0], g.get("caption", [None])[0]
    # NM-04 sets the quote marks INLINE, hugging the text (coloured open mark before
    # the first word, close after the last) rather than as big glyphs stacked
    # above/below the text.
    acc = "var(--sb-product-accent,var(--sb-sky))"
    def _inline_quote(b):
        txt = brandify(b.get("text", "")) if b else ""
        return ('<span style="color:%s">&ldquo;</span>' % acc) + txt + ('<span style="color:%s">&rdquo;</span>' % acc)
    if has_image(s):
        photo = photo_bg(img_tag(s), "180deg,rgba(6,12,26,0.55),rgba(6,12,26,0.78)")
        content = ('<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 90px;box-sizing:border-box">'
                   + blk(quote, "div", "reveal-hero no-caps", "font-size:46px;font-weight:800;line-height:1.3;max-width:940px", raw=_inline_quote(quote))
                   + blk(cap, "div", "reveal", "font-size:15px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;margin-top:28px")
                   + '</div>')
        return photo + content, 0
    # no photo: display quote in BRAND NAVY (var(--sb-title)) - navy on light, white on dark
    inner = ('<div style="margin:auto;text-align:center;max-width:960px">'
             + blk(quote, "div", "reveal-hero no-caps", "font-size:46px;font-weight:800;line-height:1.3;color:var(--sb-title)", raw=_inline_quote(quote))
             + blk(cap, "div", "reveal", "font-size:15px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:var(--sb-product-accent,var(--sb-sky));margin-top:28px")
             + '</div>')
    return inner, 64

def _headline_block(g):
    return g.get("headline", [None])[0]

def icon_list(s, acc):
    g = grp(s); head = _headline_block(g)
    kick = _first(g, "kicker")
    footnote = _first(g, "footnote")
    titles, bodies = g.get("card_title", []), g.get("card_body", [])
    ic = icons_of(s)
    rows = ""
    for i in range(min(len(titles), len(bodies))):
        rows += ('<div class="reveal sb-card" style="display:flex;gap:18px;align-items:center;padding:22px 24px">'
                 + (icon(ic[i]) if i < len(ic) else "")
                 + '<div>'
                 + blk(titles[i], "div", "no-caps", "font-weight:800;font-size:20px;color:var(--sb-text-on-dark);margin-bottom:4px")
                 + blk(bodies[i], "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark)")
                 + '</div></div>')
    photo = ""
    if has_image(s):
        # NATURAL content photo — it sits BESIDE the icon rows, not behind text, so it gets NO
        # duotone/scrim. photo_bg() (tint + legibility gradient) is reserved for full-bleed
        # backgrounds that carry .on-media text; a standalone image must read as a real photo.
        photo = ('<div class="reveal-left" style="flex:1;min-height:200px;border-radius:6px;overflow:hidden;margin-top:26px;position:relative">'
                 + '<img data-image="%s" class="img-cover"></div>' % img_tag(s))
    kicker_html = blk(kick, "div", "reveal", "font-size:14px;font-weight:800;letter-spacing:0.2em;color:" + ACC + ";margin:0 0 10px") if kick else ""
    # optional takeaway band under the rows (TKMS gap, 2026-08: footnote blocks rendered empty)
    if footnote:
        rows += ('<div class="reveal sb-card" style="padding:16px 22px;border-left:5px solid ' + ACC + '">'
                 + blk(footnote, "div", "", "font-size:14px;line-height:1.5;color:var(--sb-text-on-dark);font-weight:600") + '</div>')
    left = ('<div style="flex:0 0 40%;display:flex;flex-direction:column;justify-content:center">'
            + kicker_html + blk(head, "h2", "hl reveal-left", "font-size:46px;margin:0 0 4px") + rule() + photo + '</div>')
    right = '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:16px">%s</div>' % rows
    return f'<div style="display:flex;gap:44px;height:100%;align-items:stretch">{left}{right}</div>', 64

def _card_grid(s, cols):
    g = grp(s); head = _headline_block(g)
    titles, bodies = g.get("card_title", []), g.get("card_body", [])
    ic = icons_of(s)
    cells = ""
    for i in range(min(len(titles), len(bodies))):
        cells += ('<div class="reveal-scale sb-card" style="padding:28px 30px;display:flex;gap:16px;align-items:flex-start">'
                  + (icon(ic[i], 36) if i < len(ic) else "")
                  + '<div>'
                  + blk(titles[i], "div", "no-caps", "font-weight:800;font-size:21px;color:var(--sb-text-on-dark);margin-bottom:6px")
                  + blk(bodies[i], "div", "", "font-size:16px;line-height:1.5;color:var(--sb-body-on-dark)")
                  + '</div></div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:46px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;align-items:center">'
             + '<div style="display:grid;grid-template-columns:%s;gap:22px;width:100%%">%s</div></div>' % ("1fr " * cols, cells))
    return inner, 64

def feature_benefit(s, acc):
    return _card_grid(s, 2)

def card_row(s, acc):
    """NM-07: claim + supporting cards. ADAPTIVE against wasted pixel space: a short card
    row (sparse copy) leaves the slide mostly empty, so when the slide carries an image
    (owned first, Unsplash fallback per PASS 4) the cards STACK on the left and the photo
    fills the right - reformat + outsource an element rather than ship dead space."""
    g = grp(s); head = _headline_block(g)
    sub = g.get("subhead", [None])[0]
    titles, bodies = g.get("card_title", []), g.get("card_body", [])
    ic = icons_of(s)
    n = min(len(titles), len(bodies))
    split = has_image(s)
    # ADAPTIVE DENSITY (TKMS overflow, 2026-08): three long cards + a 2-line headline
    # overflow the 720px stage in split mode. When total copy is heavy, tighten card
    # padding/type instead of letting content collide with the headline.
    heavy = split and n >= 3 and sum(len(b.get("text", "")) for b in bodies[:n]) > 500
    card_pad = "padding:16px 22px" if heavy else ("padding:24px 26px" if split else "flex:1;padding:32px 28px")
    t_size, b_size = ("17.5px", "14px") if heavy else ("22px", "16px")
    cards = ""
    for i in range(n):
        cards += ('<div class="reveal sb-card" style="%s">' % card_pad
                  + (icon(ic[i], 36) + '<div style="height:14px"></div>' if i < len(ic) else rule("0") + '<div style="height:16px"></div>')
                  + blk(titles[i], "div", "no-caps", "font-weight:900;font-size:%s;color:var(--sb-text-on-dark);margin-bottom:%s" % (t_size, "8px" if heavy else "12px"))
                  + blk(bodies[i], "div", "", "font-size:%s;line-height:1.5;color:var(--sb-body-on-dark)" % b_size)
                  + '</div>')
    if split:
        # Stacked cards left, natural photo right (no scrim - it sits beside text, not under it).
        subh = blk(sub, "div", "reveal no-caps", "font-size:18px;font-weight:600;color:var(--sb-body-on-dark);margin:14px 0 0") if sub else ""
        left = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:18px;min-width:0">'
                + cards + '</div>')
        right = ('<div class="reveal-right" style="flex:0 0 42%;border-radius:6px;overflow:hidden;position:relative;min-height:0">'
                 + '<img data-image="%s" class="img-cover" style="position:absolute;inset:0;width:100%%;height:100%%;object-fit:cover"></div>' % img_tag(s))
        inner = (blk(head, "h2", "hl reveal", "font-size:%s;margin:0 0 6px" % ("32px" if heavy else "44px"))
                 + rule("6px") + subh
                 + f'<div style="flex:1;display:flex;gap:36px;align-items:stretch;min-height:0;margin-top:{"16px" if heavy else "26px"}">{left}{right}</div>')
        return inner, 64
    subh = ('<div style="display:flex;justify-content:center">'
            + blk(sub, "div", "reveal no-caps", "font-size:18px;font-weight:600;color:var(--sb-body-on-dark);margin-top:12px;text-align:center")
            + '</div>') if sub else ""
    inner = (blk(head, "h2", "hl reveal", "font-size:46px;text-align:center;margin:0 0 6px")
             + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>' + subh
             + f'<div style="flex:1;display:flex;align-items:center"><div style="display:flex;gap:24px;width:100%;align-items:stretch">{cards}</div></div>')
    return inner, 64

def three_stats(s, acc):
    g = grp(s); head = _headline_block(g)
    stats, labels = g.get("stat", []), g.get("stat_label", [])
    # Solid colour-blocked tiles (sky / copper / pink) with white text — a bold colour splash,
    # not grey cards. The featured product accent leads the cycle when the slide carries one.
    cyc = ["var(--sb-product-accent,var(--sb-sky))", "var(--sb-copper)", "var(--sb-pink)", "var(--sb-steel)"]
    cards = ""
    for i in range(min(len(stats), len(labels))):
        col = cyc[i % len(cyc)]
        cards += ('<div class="reveal-scale on-media" style="flex:1;background:%s;border-radius:6px;padding:48px 30px;text-align:center;box-shadow:0 16px 40px rgba(6,12,26,0.28)">' % col
                  + blk(stats[i], "div", "", "font-size:96px;font-weight:900;line-height:0.95;letter-spacing:-0.03em")
                  + blk(labels[i], "div", "", "margin-top:16px;font-size:16px;font-weight:700;line-height:1.35;opacity:0.95")
                  + '</div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:46px;text-align:center;margin:0 0 6px")
             + '<div style="display:flex;justify-content:center">' + rule("6px", center=True) + '</div>'
             + f'<div style="flex:1;display:flex;align-items:center"><div style="display:flex;gap:24px;width:100%;align-items:stretch">{cards}</div></div>')
    return inner, 64

def narrative_split(s, acc):
    g = grp(s); head, body = _headline_block(g), g.get("body", [None])[0]
    kpi, kl = g.get("kpi", [None])[0], g.get("kpi_label", [None])[0]
    left = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding-right:20px">'
            + blk(head, "h2", "hl reveal-left", "font-size:48px;margin:0")
            + blk(body, "div", "reveal", "font-size:21px;line-height:1.6;color:var(--sb-body-on-dark);margin-top:26px;max-width:560px") + '</div>')
    right = ""
    if kpi:
        right = ('<div class="reveal-right on-media" style="flex:0 0 360px;background:var(--sb-product-accent,var(--sb-navy));border-radius:6px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:48px">'
                 + blk(kpi, "div", "", "font-size:112px;font-weight:900;line-height:1;letter-spacing:-0.03em")
                 + blk(kl, "div", "", "font-size:16px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;opacity:0.85;margin-top:14px") + '</div>')
    return f'<div style="display:flex;gap:48px;height:100%;align-items:stretch">{left}{right}</div>', 64

def three_step(s, acc):
    g = grp(s); head = _headline_block(g)
    titles, bodies = g.get("card_title", []), g.get("card_body", [])
    chev = chevron_connector()
    cards = ""
    n = min(len(titles), len(bodies))
    for i in range(n):
        cards += ('<div class="reveal sb-card" style="flex:1;padding:32px 26px">'
                  + blk(titles[i], "div", "no-caps", "font-weight:900;font-size:24px;color:var(--sb-text-on-dark);margin-bottom:12px")
                  + blk(bodies[i], "div", "", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark)") + '</div>')
        if i < n - 1:
            cards += chev
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + f'<div style="flex:1;display:flex;align-items:center"><div style="display:flex;gap:6px;width:100%;align-items:stretch">{cards}</div></div>')
    return inner, 64

def versus(s, acc):
    g = grp(s); head = _headline_block(g)
    titles = g.get("card_title", [])
    items = g.get("list_item", [])
    half = len(items) // 2 if items else 0
    cols = [(titles[0] if titles else None, items[:half]), (titles[1] if len(titles) > 1 else None, items[half:])]
    out = ""
    for ci, (title, its) in enumerate(cols):
        accent = "var(--sb-product-accent,var(--sb-sky))" if ci == 1 else "var(--sb-text-secondary)"
        lis = ""
        for b in its:
            lis += ('<div style="display:flex;gap:12px;align-items:center;padding:11px 0;border-top:1px solid var(--sb-border-subtle)">'
                    '<span style="width:9px;height:9px;border-radius:50%%;background:%s;flex:none"></span>' % accent
                    + blk(b, "div", "", "font-size:17px;color:var(--sb-text-on-dark)") + '</div>')
        border = "border:2px solid var(--sb-product-accent,var(--sb-sky));" if ci == 1 else ""
        out += ('<div class="reveal sb-card" style="flex:1;%spadding:30px 34px">' % border
                + blk(title, "div", "no-caps", "font-weight:900;font-size:24px;color:%s;margin-bottom:8px" % accent) + lis + '</div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:46px;text-align:center;margin:0 0 6px")
             + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>'
             + f'<div style="flex:1;display:flex;align-items:center"><div style="display:flex;gap:32px;width:100%;align-items:stretch">{out}</div></div>')
    return inner, 64

def suite(s, acc):
    g = grp(s); head, body = _headline_block(g), g.get("body", [None])[0]
    stat, sl = g.get("stat", [None])[0], g.get("stat_label", [None])[0]
    labels = g.get("label", [])
    prodcol = {"smrtGC": "var(--sb-sky)", "smrtSUB": "var(--sb-copper)", "smrtAE": "var(--sb-steel)",
               "smrtAEC": "var(--sb-steel)", "smrt-E": "var(--sb-pink)", "smrtPAY": "var(--sb-navy)"}
    descs = g.get("card_body", [])
    chips = ""
    for i, b in enumerate(labels):
        txt = (b.get("text") or "").strip()
        col = prodcol.get(txt, "var(--sb-product-accent,var(--sb-sky))")
        # Product NAME renders as its LOGO (brand rule); non-product labels stay text.
        if is_product_word(txt):
            head_html = blk(b, "div", "no-caps", "height:44px;display:flex;align-items:center;justify-content:center",
                            raw='<img data-logo="%s" style="height:38px;max-width:100%%">' % txt)
        else:
            head_html = blk(b, "div", "no-caps", "font-weight:800;font-size:22px;text-align:center;color:%s" % col)
        desc = (blk(descs[i], "div", "", "font-size:14px;line-height:1.5;color:var(--sb-body-on-dark);text-align:center;margin-top:14px")
                if i < len(descs) else "")
        chips += ('<div class="reveal-scale sb-card" style="flex:1;border-top:5px solid %s;padding:26px 18px;'
                  'display:flex;flex-direction:column;align-items:center">' % col
                  + head_html + desc + '</div>')
    rail = ""
    if stat:
        rail = ('<div class="reveal on-media" style="display:flex;align-items:center;justify-content:space-between;gap:24px;background:var(--sb-product-accent,var(--sb-navy));border-radius:6px;padding:26px 38px;margin-top:22px">'
                '<div style="display:flex;align-items:baseline;gap:16px">'
                + blk(stat, "div", "", "font-size:64px;font-weight:900;line-height:1")
                + blk(sl, "div", "", "font-size:16px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;max-width:280px") + '</div></div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:42px;margin:0 0 12px;max-width:900px")
             + (blk(body, "div", "reveal", "font-size:18px;line-height:1.55;color:var(--sb-body-on-dark);max-width:820px;margin-bottom:26px") if body else "")
             + ('<div style="display:flex;gap:20px;align-items:stretch">%s</div>' % chips if chips else "") + rail)
    return inner, 64

def product_pillar(s, acc):
    g = grp(s); head, body = _headline_block(g), g.get("body", [None])[0]
    kpi, kl = g.get("kpi", [None])[0], g.get("kpi_label", [None])[0]
    left = ('<div style="flex:0 0 52%;display:flex;flex-direction:column;justify-content:center;padding-right:28px">'
            + blk(head, "h2", "hl reveal-left", "font-size:44px;margin:0")
            + blk(body, "div", "reveal", "font-size:19px;line-height:1.6;color:var(--sb-body-on-dark);margin-top:22px")
            + ('<div class="reveal" style="display:flex;align-items:baseline;gap:16px;margin-top:30px">'
               + blk(kpi, "div", "kpi-num", "font-size:70px") + blk(kl, "div", "kpi-label", "color:var(--sb-body-on-dark);font-size:15px") + '</div>' if kpi else "")
            + '</div>')
    imgtag = img_tag(s) or "product"
    # pt-imgslot: build.py keeps the framed accent box for a real photo, but flips a cut-out /
    # product-* device screenshot to FRAMELESS object-fit:contain so the whole device shows.
    framed = ("width:100%;height:360px;background:var(--sb-product-accent,var(--sb-sky));border-radius:10px;"
              "padding:14px;box-shadow:0 20px 50px rgba(6,12,26,0.18);overflow:hidden;box-sizing:border-box")
    imgst = "width:100%;height:100%;object-fit:cover;border-radius:6px;display:block"
    right = ('<div class="reveal-right" style="flex:1;display:flex;align-items:center;justify-content:center">'
             '<div class="pt-imgslot" data-image-slot="%s" style="%s"><img data-image="%s" style="%s"></div></div>'
             % (imgtag, framed, imgtag, imgst))
    return f'<div style="display:flex;gap:40px;height:100%;align-items:stretch">{left}{right}</div>', 64

def section_gradient(s, acc):
    g = grp(s); label, head = g.get("label", [None])[0], _headline_block(g)
    inner = ('<div style="margin:auto 0;max-width:880px">'
             + blk(label, "div", "label reveal", "color:var(--sb-product-accent,var(--sb-sky));margin-bottom:18px")
             + blk(head, "h2", "hl reveal-left", "font-size:60px;margin:0") + rule("28px") + '</div>')
    return inner, 64

# >>> EXT RENDERERS START >>>
def cover_agenda(s, acc):
    g = grp(s)
    head = _headline_block(g)
    caps = g.get("caption", [])
    date = caps[0] if caps else None
    footer = caps[1] if len(caps) > 1 else None
    items = g.get("list_item", [])
    if has_image(s):
        bg = photo_bg(img_tag(s), "120deg,rgba(6,12,26,0.94) 0%,rgba(6,12,26,0.78) 46%,rgba(6,12,26,0.55) 100%")
    else:
        bg = '<div style="position:absolute;inset:0;background:linear-gradient(135deg,rgba(6,12,26,0.96),var(--sb-navy))"></div>'
    left = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding-right:30px">'
            + blk(head, "h1", "hl reveal-hero", "font-size:64px;line-height:1.0;margin:0")
            + (blk(date, "div", "reveal", "font-size:16px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:var(--sb-body-on-dark);margin-top:26px") if date else "")
            + '</div>')
    rows = ""
    for i, b in enumerate(items):
        rows += ('<div style="display:flex;gap:16px;align-items:center;padding:14px 0;border-top:1px solid rgba(255,255,255,0.16)">'
                 + '<span aria-hidden="true" class="on-media" style="flex:none;width:30px;height:30px;border-radius:6px;background:%s;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:15px">%d</span>' % (ACC, i + 1)
                 + blk(b, "div", "on-media", "font-size:18px;font-weight:700;line-height:1.3") + '</div>')
    agenda = ('<div class="reveal-right on-media" style="flex:0 0 42%%;align-self:center;background:rgba(255,255,255,0.06);'
              'border:1px solid rgba(255,255,255,0.16);border-radius:6px;padding:30px 34px">%s</div>' % rows)
    content = ('<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;padding:0 72px;box-sizing:border-box">'
               '<div style="display:flex;gap:44px;width:100%;align-items:center">' + left + agenda + '</div></div>')
    foot_html = (blk(footer, "div", "on-media reveal", "position:absolute;left:72px;bottom:46px;z-index:3;font-size:14px;"
                     "font-weight:700;letter-spacing:0.14em;text-transform:uppercase;opacity:0.8") if footer else "")
    inner = bg + logo_mark() + content + foot_html
    return inner, 0

def section_photos(s, acc):
    g = grp(s)
    label = _first(g, "stat_label") or _first(g, "label")
    head = _headline_block(g)
    footer = _first(g, "caption")
    left = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:0 60px 0 72px;box-sizing:border-box">'
            + (blk(label, "div", "label reveal", "color:var(--sb-product-accent,var(--sb-sky));margin-bottom:20px") if label else "")
            + blk(head, "h2", "hl reveal-left", "font-size:58px;line-height:1.05;margin:0")
            + rule("30px")
            + (blk(footer, "div", "reveal", "font-size:14px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;"
                   "color:var(--sb-body-on-dark);margin-top:40px") if footer else "")
            + '</div>')
    if has_image(s):
        right = ('<div class="reveal-right" style="flex:0 0 40%;position:relative;overflow:hidden">'
                 '<div style="position:absolute;inset:0"><img data-image="' + img_tag(s) + '" class="img-cover"></div></div>')
    else:
        right = ('<div class="reveal-right" style="flex:0 0 40%;position:relative;overflow:hidden;'
                 'background:linear-gradient(135deg,var(--sb-product-accent,var(--sb-sky)),var(--sb-navy))">'
                 '<div style="position:absolute;right:40px;top:60px;width:200px;height:200px;'
                 'border:3px solid rgba(255,255,255,0.30);border-radius:6px;transform:rotate(12deg)"></div>'
                 '<div style="position:absolute;right:120px;bottom:60px;width:150px;height:150px;'
                 'background:rgba(255,255,255,0.12);border-radius:6px;transform:rotate(-8deg)"></div></div>')
    inner = '<div style="display:flex;height:100%%;align-items:stretch">%s%s</div>' % (left, right) + logo_mark()
    return inner, 0

def deck_shell(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    stats = g.get("stat", [])
    slabels = g.get("stat_label", [])
    titles = g.get("card_title", [])
    cta = _first(g, "cta")
    frames = []
    if bodies:
        frames.append(blk(bodies[0], "div", "no-caps", "font-size:16px;font-weight:800;color:var(--sb-text-on-dark);line-height:1.4"))
    if len(bodies) > 1:
        frames.append(blk(bodies[1], "div", "", "font-size:15px;color:var(--sb-body-on-dark);line-height:1.5"))
    if stats:
        st = '<div style="display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline">'
        for i, sb in enumerate(stats):
            st += blk(sb, "span", "kpi-num", "font-size:34px")
            if i < len(slabels):
                st += blk(slabels[i], "span", "", "font-size:12px;color:var(--sb-body-on-dark)")
        st += '</div>'
        frames.append(st)
    for t in titles[:4]:
        frames.append(blk(t, "div", "no-caps", "font-size:19px;font-weight:900;color:var(--sb-text-on-dark);line-height:1.25"))
    if cta:
        frames.append(blk(cta, "div", "cta-btn", ""))
    cells = ""
    for i, fr in enumerate(frames):
        cells += ('<div class="reveal-scale sb-card" style="min-height:148px;padding:22px 24px;'
                  'display:flex;flex-direction:column;justify-content:center;gap:12px">'
                  '<span aria-hidden="true" class="on-media" style="flex:none;width:26px;height:26px;border-radius:6px;'
                  'background:%s;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:13px">%d</span>' % (ACC, i + 1)
                  + '<div>' + fr + '</div></div>')
    grid = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:20px;width:100%%">%s</div>' % cells
    inner = ""
    if head:
        inner += blk(head, "h2", "hl reveal", "font-size:40px;margin:0 0 6px") + rule("6px") + '<div style="height:26px"></div>'
    inner += grid
    return inner, 64

def cover_cobrand(s, acc):
    g = grp(s)
    heads = g.get("headline", [])
    head = heads[0] if heads else None
    sub = heads[1] if len(heads) > 1 else _first(g, "subhead")
    foot = _first(g, "caption")
    if has_image(s):
        right_field = ('<div class="reveal-right" style="position:absolute;right:0;top:0;bottom:0;width:46%;z-index:0">'
                       '<div style="position:absolute;inset:0"><img data-image="' + img_tag(s) + '" class="img-cover"></div></div>')
    else:
        right_field = ('<div style="position:absolute;right:-40px;top:50%;transform:translateY(-50%);width:520px;height:520px;'
                       'pointer-events:none;z-index:0">'
                       '<div style="position:absolute;right:60px;top:40px;width:300px;height:300px;'
                       'background:var(--sb-product-accent,var(--sb-sky));opacity:0.12;border-radius:6px;transform:rotate(12deg)"></div>'
                       '<div style="position:absolute;right:150px;top:150px;width:220px;height:220px;'
                       'border:3px solid var(--sb-product-accent,var(--sb-sky));opacity:0.30;border-radius:6px;transform:rotate(-8deg)"></div></div>')
    left = ('<div style="position:absolute;left:72px;top:0;bottom:0;width:44%;z-index:2;'
            'display:flex;flex-direction:column;justify-content:center">'
            + blk(head, "h1", "hl reveal-hero", "font-size:60px;line-height:1.02;margin:0")
            + (blk(sub, "div", "reveal no-caps", "font-size:26px;font-weight:800;color:var(--sb-title);margin-top:22px") if sub else "")
            + (blk(foot, "div", "reveal", "font-size:16px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;"
                   "color:var(--sb-body-on-dark);margin-top:40px") if foot else "")
            + '</div>')
    inner = right_field + logo_mark() + left
    return inner, 0

def cover_agenda_photo(s, acc):
    g = grp(s)
    heads = g.get("headline", [])
    head = heads[0] if heads else None
    sub = heads[1] if len(heads) > 1 else _first(g, "subhead")
    date = _first(g, "caption")
    items = g.get("list_item", [])
    if has_image(s):
        bg = photo_bg(img_tag(s), "120deg,rgba(6,12,26,0.92) 0%,rgba(6,12,26,0.72) 50%,rgba(6,12,26,0.55) 100%")
    else:
        bg = '<div style="position:absolute;inset:0;background:linear-gradient(135deg,rgba(6,12,26,0.96),var(--sb-navy))"></div>'
    left = ('<div class="on-media" style="flex:1;display:flex;flex-direction:column;justify-content:center;padding-right:30px">'
            + blk(head, "h1", "hl reveal-hero", "font-size:56px;line-height:1.02;margin:0")
            + (blk(sub, "div", "reveal no-caps", "font-size:26px;font-weight:800;margin-top:18px") if sub else "")
            + (blk(date, "div", "reveal", "font-size:16px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;"
                   "color:var(--sb-body-on-dark);margin-top:26px") if date else "")
            + '</div>')
    rows = ""
    for b in items:
        rows += ('<div style="padding:16px 0;border-top:1px solid rgba(255,255,255,0.22)">'
                 + blk(b, "div", "on-media", "font-size:18px;font-weight:700;line-height:1.35") + '</div>')
    panel = ('<div class="reveal-right on-media" style="flex:0 0 40%%;align-self:stretch;background:%s;border-radius:6px;'
             'padding:34px 38px;display:flex;flex-direction:column;justify-content:center">%s</div>' % (ACC, rows))
    content = ('<div style="position:absolute;inset:0;z-index:2;display:flex;padding:64px 72px;box-sizing:border-box;'
               'gap:44px;align-items:stretch">' + left + panel + '</div>')
    inner = bg + logo_mark() + content
    return inner, 0

def closing_contact(s, acc):
    g = grp(s)
    invite = _first(g, "card_body") or _first(g, "body") or _headline_block(g)
    emails = g.get("list_item", [])
    bg = '<div style="position:absolute;inset:0;background:linear-gradient(135deg,rgba(6,12,26,0.98),var(--sb-navy))"></div>'
    big_logo = '<img data-logo="smartbuild" class="reveal" style="height:60px;display:block;margin-bottom:34px">'
    email_rows = ""
    for b in emails:
        email_rows += ('<div class="reveal" style="display:flex;gap:14px;align-items:center;margin:14px 0">'
                       + '<span style="flex:none;width:10px;height:10px;border-radius:50%%;background:%s"></span>' % ACC
                       + blk(b, "div", "on-media", "font-size:22px;font-weight:700") + '</div>')
    left = ('<div class="on-media" style="flex:1;display:flex;flex-direction:column;justify-content:center;z-index:2">'
            + big_logo
            + (blk(invite, "div", "reveal no-caps", "font-size:30px;font-weight:600;line-height:1.3;max-width:520px;margin-bottom:30px") if invite else "")
            + email_rows + '</div>')
    if has_image(s):
        right = ('<div class="reveal-right" style="flex:0 0 46%;display:flex;align-items:center;justify-content:center;z-index:2">'
                 '<div style="width:100%;background:var(--sb-product-accent,var(--sb-sky));border-radius:10px;padding:14px;'
                 'box-shadow:0 20px 50px rgba(6,12,26,0.4)">'
                 '<div style="border-radius:6px;overflow:hidden;height:300px"><img data-image="' + img_tag(s) + '" class="img-cover"></div></div></div>')
    else:
        right = ""
    content = ('<div style="position:absolute;inset:0;z-index:2;display:flex;gap:48px;padding:64px 72px;box-sizing:border-box;'
               'align-items:stretch">' + left + right + '</div>')
    inner = bg + content
    return inner, 0

def image_metric(s, acc):
    g = grp(s)
    stats = g.get("stat", []) + g.get("kpi", [])
    labels = g.get("stat_label", []) + g.get("kpi_label", [])
    cap = _first(g, "caption")
    left = p_title(g, 44) if _headline_block(g) else ""
    if _first(g, "body"):
        left += p_body(_first(g, "body"))
    hero = stats[0] if stats else None
    if hero:
        hl_lab = labels[0] if labels else None
        left += ('<div class="reveal" style="display:flex;align-items:baseline;gap:14px;margin-top:28px">'
                 + blk(hero, "div", "kpi-num", "font-size:88px")
                 + (blk(hl_lab, "div", "kpi-label", "color:var(--sb-body-on-dark);font-size:16px") if hl_lab else "")
                 + '</div>')
    sup = stats[1:3]
    if sup:
        tiles = ""
        for i, st in enumerate(sup):
            lb = labels[i + 1] if (i + 1) < len(labels) else None
            tiles += ('<div class="reveal-scale sb-card" style="flex:1;padding:22px 20px;text-align:center">'
                      + blk(st, "div", "kpi-num", "font-size:42px")
                      + (blk(lb, "div", "kpi-label", "margin-top:8px;font-size:14px;color:var(--sb-body-on-dark)") if lb else "")
                      + '</div>')
        left += '<div style="display:flex;gap:16px;margin-top:26px">' + tiles + '</div>'
    if cap:
        left += blk(cap, "div", "reveal", "font-size:13px;letter-spacing:0.1em;text-transform:uppercase;color:var(--sb-body-on-dark);margin-top:22px")
    right = p_media(img_tag(s) or "metric")
    return p_split(left, right, gap=44, align="center"), 64

def logo_board(s, acc):
    # Real logo WALL: each label block's text is an image tag (e.g. client-gen-pro) rendered as
    # an actual logo on a white tile. Falls back to a text chip if a label isn't an image tag.
    g = grp(s)
    head = _headline_block(g)
    logos = g.get("label", [])
    sub = _first(g, "body")
    proof = _first(g, "stat") or _first(g, "kpi")
    cap = _first(g, "caption")
    inner = ""
    if head:
        inner += (blk(head, "h2", "hl reveal", "font-size:42px;margin:0 0 6px;text-align:center")
                  + '<div style="display:flex;justify-content:center">' + rule("6px", center=True) + '</div>')
    if sub:
        inner += blk(sub, "div", "reveal", "font-size:18px;line-height:1.5;text-align:center;color:var(--sb-body-on-dark);max-width:820px;margin:14px auto 0")
    if logos:
        tiles = ""
        for b in logos:
            txt = (b.get("text") or "").strip()
            is_img = txt.startswith("client-") or txt.startswith("logo-") or txt.startswith("img-")
            if is_img:
                tiles += ('<div class="reveal-scale" style="background:var(--sb-on-accent);border-radius:6px;height:118px;'
                          'display:flex;align-items:center;justify-content:center;padding:18px;box-shadow:0 8px 24px rgba(6,12,26,0.20)">'
                          + blk(b, "div", "", "width:100%;height:100%;display:flex;align-items:center;justify-content:center",
                                raw='<img data-image="%s" style="max-width:84%%;max-height:72%%;object-fit:contain">' % txt) + '</div>')
            else:
                tiles += ('<div class="reveal-scale sb-card" style="height:118px;display:flex;align-items:center;justify-content:center;padding:18px;text-align:center">'
                          + blk(b, "div", "no-caps", "font-weight:800;font-size:18px;color:var(--sb-text-on-dark)") + '</div>')
        inner += ('<div style="flex:1;display:flex;align-items:center;margin-top:26px">'
                  '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px;width:100%">' + tiles + '</div></div>')
    if proof:
        inner += ('<div class="reveal on-media" style="margin-top:24px;background:' + ACC + ';border-radius:6px;padding:30px;text-align:center">'
                  + blk(proof, "div", "", "font-size:62px;font-weight:900;line-height:1")
                  + (blk(cap, "div", "", "font-size:15px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;opacity:0.9;margin-top:10px") if cap else "")
                  + '</div>')
    elif cap:
        inner += blk(cap, "div", "reveal", "font-size:15px;text-align:center;color:var(--sb-body-on-dark);margin-top:20px")
    return inner, 64

def proof_stack(s, acc):
    g = grp(s)
    claim = _headline_block(g)
    kick = _first(g, "kicker")
    stats = g.get("stat", []) + g.get("kpi", [])
    labels = g.get("stat_label", []) + g.get("kpi_label", [])
    q = _first(g, "quote")
    qcite = _first(g, "caption")
    media = g.get("card_body", [])
    mtitles = g.get("card_title", [])
    footnote = _first(g, "footnote")
    inner = ""
    if claim:
        inner += (blk(claim, "h2", "hl reveal", "font-size:40px;margin:0 0 6px;text-align:center")
                  + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>')
    if stats:
        tiles = ""
        for i, st in enumerate(stats[:4]):
            lb = labels[i] if i < len(labels) else None
            tiles += ('<div class="reveal-scale sb-card" style="flex:1;padding:26px 16px;text-align:center">'
                      + blk(st, "div", "kpi-num", "font-size:54px")
                      + (blk(lb, "div", "kpi-label", "margin-top:8px;font-size:14px;color:var(--sb-body-on-dark)") if lb else "")
                      + '</div>')
        inner += '<div style="display:flex;gap:18px;margin-top:28px">' + tiles + '</div>'
    bottom = ""
    if q:
        bottom += ('<div class="reveal sb-card" style="flex:2;padding:30px 34px">'
                   + qmark(True, 60, ACC)
                   + blk(q, "div", "no-caps", "font-size:22px;font-weight:700;line-height:1.35;color:var(--sb-text-on-dark)")
                   + qmark(False, 60, ACC, align="right")
                   + (blk(qcite, "div", "", "font-size:13px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:" + ACC + ";margin-top:16px") if qcite else "")
                   + '</div>')
    if media:
        # titled proof cards, side by side (up to 3) - card_title pairs with card_body
        # (TKMS gap, 2026-08: titles were dropped and cards capped at 2).
        mcards = ""
        for mi, mb in enumerate(media[:3]):
            mt = mtitles[mi] if mi < len(mtitles) else None
            mcards += ('<div class="reveal sb-card" style="flex:1;padding:20px 22px">'
                       + (blk(mt, "div", "no-caps", "font-weight:800;font-size:16px;color:var(--sb-text-on-dark);margin-bottom:6px") if mt else "")
                       + blk(mb, "div", "", "font-size:14px;line-height:1.5;color:var(--sb-body-on-dark)") + '</div>')
        bottom += '<div style="flex:2;display:flex;gap:16px;align-items:stretch">' + mcards + '</div>'
    if bottom:
        inner += '<div style="display:flex;gap:20px;margin-top:22px;align-items:stretch">' + bottom + '</div>'
    if footnote:
        inner += blk(footnote, "div", "reveal", "font-size:12px;color:var(--sb-body-on-dark);margin-top:16px;font-style:italic")
    if kick:
        inner = blk(kick, "div", "reveal", "font-size:14px;font-weight:800;letter-spacing:0.2em;color:" + ACC + ";margin:0 0 10px;text-align:center") + inner
    return inner, 64

def case_study(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    challenge = bodies[0] if bodies else None
    solution = bodies[1] if len(bodies) > 1 else None
    stat = _first(g, "stat") or _first(g, "kpi")
    sl = _first(g, "stat_label") or _first(g, "kpi_label")
    q = _first(g, "quote")
    qcite = _first(g, "caption")
    left = p_media(img_tag(s) or "case", h=430)
    right = ""
    if head:
        right += blk(head, "h2", "hl reveal", "font-size:34px;margin:0 0 18px")
    for b in [challenge, solution]:
        if b:
            right += ('<div class="reveal" style="display:flex;gap:12px;margin-bottom:14px">'
                      '<span style="flex:none;width:9px;height:9px;border-radius:50%;background:' + ACC + ';margin-top:8px"></span>'
                      + blk(b, "div", "", "font-size:17px;line-height:1.55;color:var(--sb-body-on-dark)") + '</div>')
    if stat:
        right += ('<div class="reveal on-media" style="background:' + ACC + ';border-radius:6px;padding:22px 26px;margin-top:8px;display:flex;align-items:baseline;gap:14px">'
                  + blk(stat, "div", "", "font-size:52px;font-weight:900;line-height:1")
                  + (blk(sl, "div", "", "font-size:14px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;opacity:0.9") if sl else "")
                  + '</div>')
    if q:
        right += ('<div class="reveal" style="margin-top:18px;border-left:4px solid ' + ACC + ';padding-left:18px">'
                  + blk(q, "div", "no-caps", "font-size:18px;line-height:1.4;color:var(--sb-text-on-dark)")
                  + (blk(qcite, "div", "", "font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:" + ACC + ";margin-top:10px") if qcite else "")
                  + '</div>')
    return p_split(left, right, gap=44, align="center"), 64

def psp(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    proof = _first(g, "card_body")
    cta = _first(g, "cta")
    ic = icons_of(s)
    cards_data = []
    if len(bodies) > 0:
        cards_data.append(bodies[0])
    if len(bodies) > 1:
        cards_data.append(bodies[1])
    if proof:
        cards_data.append(proof)
    n = len(cards_data)
    chev = ('<div style="flex:0 0 30px;display:flex;align-items:center;justify-content:center">'
            '<div style="width:14px;height:14px;border-top:4px solid ' + ACC + ';border-right:4px solid ' + ACC + ';transform:rotate(45deg);opacity:0.6"></div></div>')
    cards = ""
    for i, b in enumerate(cards_data):
        cards += ('<div class="reveal sb-card" style="flex:1;padding:30px 26px">'
                  + ((icon(ic[i], 34) + '<div style="height:14px"></div>') if i < len(ic) else "")
                  + blk(b, "div", "", "font-size:17px;line-height:1.55;color:var(--sb-body-on-dark)") + '</div>')
        if i < n - 1:
            cards += chev
    inner = ""
    if head:
        inner += (blk(head, "h2", "hl reveal", "font-size:42px;margin:0 0 6px;text-align:center")
                  + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>')
    inner += '<div style="display:flex;gap:6px;align-items:stretch;margin-top:26px">' + cards + '</div>'
    reason = bodies[2] if len(bodies) > 2 else None
    footer = ""
    if reason:
        footer += blk(reason, "div", "", "font-size:17px;line-height:1.5;color:var(--sb-text-on-dark);max-width:640px")
    if cta:
        footer += blk(cta, "div", "cta-btn reveal", "")
    if footer:
        inner += ('<div class="reveal" style="display:flex;justify-content:space-between;align-items:center;gap:24px;margin-top:26px;padding-top:22px;border-top:1px solid var(--sb-border-subtle)">' + footer + '</div>')
    return inner, 64

def messaging_house(s, acc):
    g = grp(s)
    promise = _headline_block(g)
    pillars = g.get("card_title", [])
    proofs = g.get("card_body", [])
    inner = ""
    if promise:
        inner += ('<div class="reveal on-media" style="background:' + ACC + ';border-radius:6px 6px 0 0;padding:30px;text-align:center;margin-bottom:16px">'
                  + blk(promise, "div", "no-caps", "font-size:30px;font-weight:900;line-height:1.2") + '</div>')
    if pillars:
        cols = ""
        for i, p in enumerate(pillars[:3]):
            col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
            cols += ('<div class="reveal-scale sb-card" style="flex:1;border-top:5px solid ' + col + ';padding:34px 22px;text-align:center;display:flex;align-items:center;justify-content:center;min-height:150px">'
                     + blk(p, "div", "no-caps", "font-weight:800;font-size:22px;color:var(--sb-text-on-dark)") + '</div>')
        inner += '<div style="display:flex;gap:16px">' + cols + '</div>'
    if proofs:
        row = ""
        for pb in proofs:
            row += blk(pb, "div", "", "flex:1;font-size:15px;line-height:1.45;color:var(--sb-body-on-dark);text-align:center;padding:0 12px")
        inner += ('<div class="reveal sb-card" style="margin-top:16px;padding:24px;display:flex;gap:12px;align-items:center;justify-content:space-around">' + row + '</div>')
    return inner, 64

def faq(s, acc):
    g = grp(s)
    head = _headline_block(g)
    titles = g.get("card_title", [])
    proof = _first(g, "card_body")
    pairs = []
    i = 0
    while i < len(titles):
        obj = titles[i]
        resp = titles[i + 1] if (i + 1) < len(titles) else None
        pairs.append((obj, resp))
        i += 2
    inner = ""
    if head:
        inner += (blk(head, "h2", "hl reveal", "font-size:42px;margin:0 0 6px;text-align:center")
                  + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>')
    rows = ""
    for obj, resp in pairs:
        resp_html = ""
        if resp:
            resp_html = ('<div style="display:flex;gap:12px">'
                         '<span style="flex:none;width:9px;height:9px;border-radius:50%;background:' + ACC + ';margin-top:8px"></span>'
                         + blk(resp, "div", "", "font-size:16px;line-height:1.5;color:var(--sb-body-on-dark)") + '</div>')
        rows += ('<div class="reveal sb-card" style="flex:1;padding:28px 30px">'
                 + blk(obj, "div", "no-caps", "font-weight:900;font-size:20px;color:var(--sb-text-on-dark);margin-bottom:12px")
                 + resp_html + '</div>')
    inner += '<div style="display:flex;gap:20px;margin-top:26px;align-items:stretch">' + rows + '</div>'
    if proof:
        inner += ('<div class="reveal on-media" style="background:' + ACC + ';border-radius:6px;padding:22px 28px;margin-top:20px;text-align:center">'
                  + blk(proof, "div", "", "font-size:16px;font-weight:700;line-height:1.4") + '</div>')
    return inner, 64

def photo_timeline(s, acc):
    g = grp(s)
    head = _headline_block(g)
    roles = g.get("body", [])
    years = g.get("caption", [])
    tag = img_tag(s) or "timeline"
    n = min(4, max(len(roles), len(years))) or 4
    cols = ""
    for i in range(n):
        yr = years[i] if i < len(years) else None
        role = roles[i] if i < len(roles) else None
        cols += ('<div class="reveal-scale" style="flex:1;display:flex;flex-direction:column">'
                 '<div style="border-radius:6px;overflow:hidden;height:360px"><img data-image="' + tag + '" class="img-cover"></div>'
                 + (blk(yr, "div", "label", "color:" + ACC + ";margin-top:18px") if yr else "")
                 + (blk(role, "div", "", "font-size:15px;line-height:1.45;color:var(--sb-text-on-dark);margin-top:8px") if role else "")
                 + '</div>')
    inner = ""
    if head:
        inner += blk(head, "h2", "hl reveal", "font-size:38px;margin:0 0 20px")
    inner += '<div style="flex:1;display:flex;align-items:center"><div style="display:flex;gap:22px;width:100%;align-items:flex-start">' + cols + '</div></div>'
    return inner, 64

def stat_rail(s, acc):
    g = grp(s)
    head = _headline_block(g)
    # kicker: prefer a real kicker block; fall back to the legacy body-as-kicker.
    # lead: a real paragraph under the rule (TKMS gap, 2026-08: lead blocks rendered empty).
    kicker = _first(g, "kicker") or _first(g, "body")
    lead = _first(g, "lead")
    stats = g.get("stat", []) + g.get("kpi", [])
    labels = g.get("stat_label", []) + g.get("kpi_label", [])
    left = ""
    if kicker:
        left += blk(kicker, "div", "reveal", "font-size:15px;font-weight:700;letter-spacing:0.06em;color:" + ACC + ";margin-bottom:14px")
    if head:
        left += blk(head, "h2", "hl reveal-left", "font-size:40px;margin:0 0 8px") + rule("2px")
    if lead:
        left += blk(lead, "div", "reveal", "font-size:15px;line-height:1.55;color:var(--sb-body-on-dark);margin:14px 0 0")
    rows = ""
    for i, st in enumerate(stats[:4]):
        lb = labels[i] if i < len(labels) else None
        rows += ('<div class="reveal" style="display:flex;align-items:baseline;gap:16px;padding:14px 0;border-top:1px solid var(--sb-border-subtle)">'
                 + blk(st, "div", "kpi-num", "font-size:44px;flex:0 0 130px")
                 + (blk(lb, "div", "", "font-size:16px;line-height:1.45;color:var(--sb-body-on-dark)") if lb else "")
                 + '</div>')
    left += '<div style="margin-top:16px">' + rows + '</div>'
    right = p_media(img_tag(s) or "context")
    return p_split(left, right, lflex="1.4", rflex="1", gap=40, align="center"), 64

def logo_landscape(s, acc):
    g = grp(s)
    head = _headline_block(g)
    cats = g.get("stat_label", [])
    annos = g.get("body", [])
    n = len(cats)
    if len(annos) > n:
        ann_list = annos[:n]
        takeaway = annos[n]
    else:
        ann_list = annos
        takeaway = None
    inner = ""
    if head:
        inner += blk(head, "h2", "hl reveal", "font-size:38px;margin:0 0 22px")
    cols = ""
    for i, c in enumerate(cats):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        an = ann_list[i] if i < len(ann_list) else None
        cols += ('<div class="reveal-scale sb-card" style="flex:1;padding:26px 22px;border-top:5px solid ' + col + '">'
                 + blk(c, "div", "no-caps", "font-weight:800;font-size:17px;color:var(--sb-text-on-dark);margin-bottom:14px")
                 + (blk(an, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark)") if an else "")
                 + '</div>')
    inner += '<div style="display:flex;gap:18px;align-items:stretch">' + cols + '</div>'
    if takeaway:
        inner += ('<div class="reveal on-media" style="background:' + ACC + ';border-radius:6px;padding:24px 30px;margin-top:20px">'
                  + blk(takeaway, "div", "", "font-size:17px;font-weight:700;line-height:1.45") + '</div>')
    return inner, 64

def image_quote_pair(s, acc):
    g = grp(s)
    head = _headline_block(g)
    quotes = g.get("quote", [])
    cites = g.get("caption", [])
    tag = img_tag(s) or "compare"
    inner = ""
    if head:
        inner += (blk(head, "h2", "hl reveal", "font-size:40px;margin:0 0 6px;text-align:center")
                  + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>')
    cols = ""
    for i in range(2):
        q = quotes[i] if i < len(quotes) else None
        cite = cites[i] if i < len(cites) else None
        cols += ('<div class="reveal-scale" style="flex:1;display:flex;flex-direction:column">'
                 '<div style="border-radius:6px;overflow:hidden;height:280px"><img data-image="' + tag + '" class="img-cover"></div>'
                 '<div class="sb-card" style="padding:24px 26px;margin-top:14px;flex:1">'
                 + qmark(True, 50, ACC)
                 + (blk(q, "div", "no-caps", "font-size:19px;font-weight:700;line-height:1.35;color:var(--sb-text-on-dark)") if q else "")
                 + qmark(False, 50, ACC, align="right")
                 + (blk(cite, "div", "", "font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:" + ACC + ";margin-top:14px") if cite else "")
                 + '</div></div>')
    inner += '<div style="flex:1;display:flex;align-items:center;margin-top:24px"><div style="display:flex;gap:28px;width:100%;align-items:stretch">' + cols + '</div></div>'
    return inner, 64

def photo_columns(s, acc):
    g = grp(s)
    thesis = _headline_block(g)
    roles = g.get("body", [])
    outcomes = g.get("card_body", [])
    # Per-column image tags (one photo per person) come from label blocks; else one shared tag.
    tags = [(b.get("text") or "").strip() for b in g.get("label", [])]
    default = img_tag(s) or "persona"
    count = min(4, max(len(roles), len(outcomes), len(tags))) or 4
    cols = ""
    for i in range(count):
        role = roles[i] if i < len(roles) else None
        out = outcomes[i] if i < len(outcomes) else None
        itag = tags[i] if i < len(tags) else default
        cols += ('<div class="reveal-scale" style="flex:1;display:flex;flex-direction:column">'
                 # Headshots vary in source framing (some tight to the head, some with headroom),
                 # so a landscape crop can't frame them all consistently. Use a SQUARE tile that
                 # matches the (square) source, centred in the column, so each face shows FULLY —
                 # no clipped heads. object-position:center top still protects any non-square source.
                 '<div style="width:100%;max-width:290px;aspect-ratio:1/1;margin:0 auto;border-radius:6px;overflow:hidden"><img data-image="' + itag + '" class="img-cover" style="object-position:center top"></div>'
                 + (blk(role, "div", "no-caps", "font-weight:800;font-size:18px;color:var(--sb-text-on-dark);margin-top:14px") if role else "")
                 + (blk(out, "div", "", "font-size:14px;line-height:1.45;color:var(--sb-body-on-dark);margin-top:6px") if out else "")
                 + '</div>')
    inner = '<div style="display:flex;gap:20px;align-items:stretch">' + cols + '</div>'
    if thesis:
        inner += ('<div class="reveal on-media" style="background:' + ACC + ';border-radius:6px;padding:26px 30px;margin-top:22px;text-align:center">'
                  + blk(thesis, "div", "no-caps", "font-size:26px;font-weight:900;line-height:1.25") + '</div>')
    return inner, 64

def contrast_labels(s, acc):
    g = grp(s)
    labels = g.get("stat_label", [])
    head = _headline_block(g)
    left_lab = labels[0] if labels else None
    right_lab = labels[1] if len(labels) > 1 else None
    photo = photo_bg(img_tag(s) or "contrast", "90deg,rgba(6,12,26,0.55) 0%,rgba(6,12,26,0.12) 50%,rgba(6,12,26,0.55) 100%")
    left_plate = ""
    if left_lab:
        left_plate = ('<div class="reveal-left on-media" style="background:' + ACC + ';border-radius:6px;padding:18px 26px;box-shadow:0 12px 30px rgba(6,12,26,0.35)">'
                      + blk(left_lab, "div", "no-caps", "font-weight:900;font-size:24px") + '</div>')
    right_plate = ""
    if right_lab:
        right_plate = ('<div class="reveal-right on-media" style="background:var(--sb-navy);border-radius:6px;padding:18px 26px;box-shadow:0 12px 30px rgba(6,12,26,0.35)">'
                       + blk(right_lab, "div", "no-caps", "font-weight:900;font-size:24px") + '</div>')
    overlay = ('<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;align-items:center;justify-content:space-between;padding:0 60px;box-sizing:border-box">'
               + left_plate + right_plate + '</div>')
    header = ""
    if head:
        header = ('<div class="on-media" style="position:absolute;top:52px;left:0;right:0;z-index:3;text-align:center;padding:0 60px;box-sizing:border-box">'
                  + blk(head, "div", "hl", "font-size:38px;font-weight:900;line-height:1.1") + '</div>')
    return photo + logo_mark() + overlay + header, 0

def logo_wall_quotes(s, acc):
    g = grp(s)
    head = _headline_block(g)
    quotes = g.get("quote", [])
    cites = g.get("caption", [])
    tiles = ""
    for i in range(8):
        tiles += ('<div class="reveal-scale sb-card" style="height:74px;display:flex;align-items:center;justify-content:center">'
                  '<span style="width:46px;height:10px;border-radius:6px;background:var(--sb-border-subtle)"></span></div>')
    left_head = blk(head, "div", "label reveal", "margin-bottom:18px") if head else ""
    left = ('<div style="flex:1.1;display:flex;flex-direction:column;justify-content:center">'
            + left_head
            + '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' + tiles + '</div></div>')
    rows = ""
    for i, q in enumerate(quotes[:3]):
        cite = cites[i] if i < len(cites) else None
        rows += ('<div style="padding:18px 0;border-top:1px solid rgba(255,255,255,0.18)">'
                 + blk(q, "div", "no-caps", "font-size:18px;font-weight:700;line-height:1.4")
                 + (blk(cite, "div", "", "font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;opacity:0.8;margin-top:10px") if cite else "")
                 + '</div>')
    right = ('<div class="reveal-right on-media" style="flex:1;background:var(--sb-navy);border-radius:6px;padding:34px 40px;display:flex;flex-direction:column;justify-content:center">' + rows + '</div>')
    inner = '<div style="display:flex;gap:36px;height:100%;align-items:stretch">' + left + right + '</div>'
    return inner, 64

def photo_collage_band(s, acc):
    g = grp(s)
    title = _headline_block(g)
    tag = img_tag(s) or "collage"
    cells = ""
    for _ in range(4):
        cells += '<div style="overflow:hidden"><img data-image="' + tag + '" class="img-cover"></div>'
    grid = ('<div style="position:absolute;inset:0;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:4px">' + cells + '</div>')
    scrim = '<div style="position:absolute;inset:0;background:rgba(6,12,26,0.25);z-index:1"></div>'
    band = ""
    if title:
        band = ('<div class="on-media" style="position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);z-index:3;background:' + ACC + ';padding:34px 60px;text-align:center;box-shadow:0 20px 60px rgba(6,12,26,0.4)">'
                + blk(title, "div", "hl", "font-size:46px;font-weight:900;line-height:1.15") + '</div>')
    return grid + scrim + logo_mark() + band, 0

def photo_filmstrip(s, acc):
    g = grp(s)
    roles = g.get("body", [])
    years = g.get("caption", [])
    tag = img_tag(s) or "era"
    n = min(4, max(len(roles), len(years))) or 4
    frames = ""
    for i in range(n):
        role = roles[i] if i < len(roles) else None
        yr = years[i] if i < len(years) else None
        plate = ('<div class="on-media" style="position:absolute;left:0;right:0;bottom:0;z-index:2;background:linear-gradient(0deg,rgba(6,12,26,0.92),rgba(6,12,26,0));padding:30px 20px 22px">'
                 + (blk(yr, "div", "", "font-size:13px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase") if yr else "")
                 + (blk(role, "div", "", "font-size:15px;line-height:1.35;margin-top:6px") if role else "")
                 + '</div>')
        frames += ('<div style="flex:1;position:relative;overflow:hidden">'
                   '<img data-image="' + tag + '" class="img-cover">' + plate + '</div>')
    inner = '<div style="position:absolute;inset:0;display:flex;gap:3px">' + frames + '</div>' + logo_mark()
    return inner, 0

def case_photo_split(s, acc):
    g = grp(s)
    title = _headline_block(g)
    body = _first(g, "body")
    tag = img_tag(s) or "case"
    left = ('<div class="on-media" style="flex:0 0 44%;background:var(--sb-navy);display:flex;flex-direction:column;justify-content:center;padding:0 56px;box-sizing:border-box">'
            + (blk(title, "div", "hl", "font-size:44px;font-weight:900;line-height:1.15;margin:0") if title else "")
            + '<div style="width:90px;height:6px;background:' + ACC + ';border-radius:6px;margin:22px 0"></div>'
            + (blk(body, "div", "", "font-size:18px;line-height:1.6;opacity:0.92") if body else "")
            + '</div>')
    right = ('<div style="flex:1;position:relative;overflow:hidden;background:var(--sb-panel)">'
             '<div style="position:absolute;left:6%;top:10%;width:60%;height:56%;border-radius:6px;overflow:hidden;box-shadow:0 24px 60px rgba(6,12,26,0.4)"><img data-image="' + tag + '" class="img-cover"></div>'
             '<div style="position:absolute;right:6%;bottom:8%;width:56%;height:52%;border-radius:6px;overflow:hidden;box-shadow:0 24px 60px rgba(6,12,26,0.4);border:4px solid var(--sb-navy)"><img data-image="' + tag + '" class="img-cover"></div>'
             '</div>')
    inner = '<div style="display:flex;height:100%">' + left + right + '</div>'
    return inner, 0

def persona_story(s, acc):
    g = grp(s)
    body = _first(g, "body")          # job-to-be-done
    bullets = g.get("list_item", [])  # benefit bullets
    proof = _first(g, "card_body")    # proof point
    left = p_media(img_tag(s) or "persona", h=420)
    right = p_title(g, 42)            # feature claim
    if body:
        right += p_body(body, 18, mt="18px", mw="560px")
    if bullets:
        right += p_list(bullets)
    if proof:
        right += ('<div class="reveal sb-card" style="margin-top:18px;padding:18px 22px">'
                  + blk(proof, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark)")
                  + '</div>')
    return p_split(left, right, gap=44), 64

def device_overlay(s, acc):
    g = grp(s)
    chat = _first(g, "body")        # phone/chat UI copy
    stat = _first(g, "stat")        # benefit statement
    sl = _first(g, "stat_label")
    outcome = _first(g, "card_body")
    bubble = ''
    if chat:
        bubble = ('<div class="sb-card" style="padding:12px 14px;border-radius:6px 6px 6px 0">'
                  + blk(chat, "div", "", "font-size:13px;line-height:1.45;color:var(--sb-text-on-dark)")
                  + '</div>')
    phone = ('<div style="position:absolute;right:22px;bottom:22px;width:210px;background:var(--sb-panel);'
             'border-radius:18px;border:1px solid var(--sb-border-subtle);box-shadow:0 24px 60px rgba(6,12,26,0.45);'
             'padding:16px 14px;z-index:3">'
             '<div style="width:46px;height:5px;border-radius:6px;background:var(--sb-border-subtle);margin:0 auto 12px"></div>'
             + bubble + '</div>')
    left = ('<div class="reveal-right" style="position:relative;height:440px;border-radius:10px;overflow:hidden">'
            '<div style="position:absolute;inset:0"><img data-image="%s" class="img-cover"></div>'
            % (img_tag(s) or "field-worker")
            + phone + '</div>')
    right = p_title(g, 42)
    if stat:
        right += ('<div class="reveal" style="display:flex;align-items:baseline;gap:14px;margin-top:26px">'
                  + blk(stat, "div", "kpi-num", "font-size:76px")
                  + (blk(sl, "div", "kpi-label", "color:var(--sb-body-on-dark);font-size:15px") if sl else "")
                  + '</div>')
    if outcome:
        right += p_body(outcome, 18, mt="18px", mw="520px")
    return p_split(left, right, gap=44), 64

def screenshot_callouts(s, acc):
    g = grp(s)
    head = _headline_block(g)
    anns = g.get("body", [])
    _st = img_tag(s) or "screenshot"
    _framed = ("width:100%;height:400px;background:" + ACC + ";border-radius:10px;padding:14px;"
               "box-shadow:0 20px 50px rgba(6,12,26,0.18);overflow:hidden;box-sizing:border-box")
    shot = ('<div class="reveal-right" style="display:flex;align-items:center">'
            '<div class="pt-imgslot" data-image-slot="' + _st + '" style="' + _framed + '">'
            '<img data-image="' + _st + '" style="width:100%;height:100%;object-fit:cover;border-radius:6px;display:block"></div></div>')
    calls = ""
    for i, a in enumerate(anns):
        badge = ('<span aria-hidden="true" class="on-media" style="flex:none;width:30px;height:30px;border-radius:6px;background:%s;'
                 'display:flex;align-items:center;justify-content:center;font-weight:900;font-size:15px">%d</span>'
                 % (ACC, i + 1))
        calls += ('<div class="reveal sb-card" style="display:flex;gap:14px;align-items:flex-start;padding:18px 20px">'
                  + badge
                  + blk(a, "div", "", "font-size:16px;line-height:1.5;color:var(--sb-body-on-dark)")
                  + '</div>')
    right = '<div style="display:flex;flex-direction:column;gap:14px">%s</div>' % calls
    top = blk(head, "h2", "hl reveal", "font-size:40px;margin:0 0 6px") + rule("6px")
    body_row = ('<div style="flex:1;display:flex;align-items:center">'
                '<div style="display:flex;gap:40px;width:100%%;align-items:center">'
                '<div style="flex:1.15">%s</div><div style="flex:1">%s</div></div></div>' % (shot, right))
    return top + body_row, 64

def product_spotlight(s, acc):
    g = grp(s)
    head = _headline_block(g)
    sub = _first(g, "subhead")
    paras = g.get("card_body", [])
    scenario = _first(g, "card_title")
    imgtag = img_tag(s) or "product"
    left = ('<div class="reveal-right" style="flex:0 0 40%;display:flex;align-items:center;justify-content:center">'
            '<div style="width:100%;background:' + ACC + ';border-radius:10px;padding:14px;'
            'box-shadow:0 20px 50px rgba(6,12,26,0.18)">'
            '<div style="border-radius:6px;overflow:hidden;height:400px">'
            '<img data-image="' + imgtag + '" class="img-cover"></div></div></div>')
    right = blk(head, "h2", "hl reveal-left", "font-size:44px;margin:0")
    right += '<div style="width:110px;height:6px;background:var(--sb-pink);border-radius:6px;margin-top:14px"></div>'
    if sub:
        right += blk(sub, "div", "reveal no-caps", "font-size:20px;font-weight:700;color:var(--sb-sky);margin-top:16px")
    for p in paras:
        right += ('<div class="reveal" style="border-left:3px solid ' + ACC + ';padding:4px 0 4px 16px;margin-top:16px">'
                  + blk(p, "div", "", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark)") + '</div>')
    if scenario:
        right += ('<div class="reveal" style="margin-top:22px">'
                  + blk(scenario, "div", "no-caps", "font-style:italic;font-size:16px;color:var(--sb-text-on-dark)")
                  + '</div>')
    right_wrap = '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">%s</div>' % right
    return '<div style="display:flex;gap:44px;height:100%%;align-items:stretch">%s%s</div>' % (left, right_wrap), 64

def phone_on_photo(s, acc):
    g = grp(s)
    head = _headline_block(g)
    benefit = _first(g, "card_title")
    chat = _first(g, "body")
    outcome = _first(g, "card_body")
    photo = photo_bg(img_tag(s) or "jobsite")
    bubble = ''
    if chat:
        bubble = ('<div class="sb-card" style="padding:14px 16px;border-radius:6px 6px 6px 0">'
                  + blk(chat, "div", "", "font-size:14px;line-height:1.5;color:var(--sb-text-on-dark)")
                  + '</div>')
    phone = ('<div style="position:absolute;right:80px;top:50%;transform:translateY(-50%);width:280px;'
             'background:var(--sb-panel);border-radius:26px;border:1px solid var(--sb-border-subtle);'
             'box-shadow:0 30px 70px rgba(6,12,26,0.5);padding:22px 18px;z-index:3">'
             '<div style="width:52px;height:6px;border-radius:6px;background:var(--sb-border-subtle);margin:0 auto 16px"></div>'
             + bubble + '</div>')
    content = ('<div style="max-width:540px">'
               + (blk(benefit, "div", "label reveal", "color:var(--sb-product-accent,var(--sb-sky));margin-bottom:16px") if benefit else "")
               + blk(head, "h2", "hl reveal-left", "font-size:52px;margin:0")
               + (blk(outcome, "div", "reveal no-caps", "font-size:20px;line-height:1.5;margin-top:20px") if outcome else "")
               + '</div>')
    inner = (photo + logo_mark() + phone
             + '<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;align-items:center;'
             'padding:0 72px;box-sizing:border-box">%s</div>' % content)
    return inner, 0

def device_in_context(s, acc):
    g = grp(s)
    claim = _headline_block(g)
    cases = g.get("list_item", [])
    screen = ('<div class="reveal-right" style="flex:0 0 46%;display:flex;align-items:center;justify-content:center">'
              '<div style="width:100%;background:var(--sb-navy);border-radius:14px;padding:16px;'
              'box-shadow:0 24px 60px rgba(6,12,26,0.35);border:1px solid var(--sb-border-subtle)">'
              '<div style="display:flex;gap:6px;margin-bottom:10px">'
              '<span style="width:9px;height:9px;border-radius:50%;background:var(--sb-border-subtle)"></span>'
              '<span style="width:9px;height:9px;border-radius:50%;background:var(--sb-border-subtle)"></span>'
              '<span style="width:9px;height:9px;border-radius:50%;background:var(--sb-border-subtle)"></span></div>'
              '<div style="border-radius:6px;overflow:hidden;height:340px">'
              '<img data-image="' + (img_tag(s) or "device-screen") + '" class="img-cover"></div></div></div>')
    right = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
             + blk(claim, "h2", "hl reveal-left", "font-size:44px;margin:0") + rule("18px")
             + (p_list(cases) if cases else "") + '</div>')
    return '<div style="display:flex;gap:44px;height:100%%;align-items:stretch">%s%s</div>' % (screen, right), 64

def app_showcase(s, acc):
    g = grp(s)
    head = _headline_block(g)
    top = (blk(head, "h2", "hl reveal", "font-size:40px;text-align:center;margin:0 0 6px")
           + '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>')
    dots = (''.join('<span style="width:11px;height:11px;border-radius:50%;background:var(--sb-border-subtle)"></span>'
                    for _ in range(3)))
    frame = ('<div class="reveal-scale" style="flex:1;min-height:0;display:flex;flex-direction:column;'
             'justify-content:center;margin-top:20px">'
             '<div style="width:100%;flex:1;min-height:0;max-height:560px;display:flex;flex-direction:column;'
             'border-radius:10px;overflow:hidden;border:1px solid var(--sb-border-subtle);'
             'box-shadow:0 24px 60px rgba(6,12,26,0.2);background:var(--sb-panel)">'
             '<div style="flex:none;display:flex;align-items:center;gap:8px;padding:12px 18px;'
             'border-bottom:1px solid var(--sb-border-subtle)">' + dots + '</div>'
             '<div style="flex:1;min-height:0;overflow:hidden">'
             '<img data-image="' + (img_tag(s) or "app-screenshot") + '" class="img-cover"></div>'
             '</div></div>')
    return top + frame, 56

def exec_summary(s, acc):
    g = grp(s)
    head = _headline_block(g)
    msgs = g.get("card_body", [])
    decision = _first(g, "body")
    ic = icons_of(s)
    inner = p_title(g, 44)
    rows = ""
    for i, b in enumerate(msgs):
        if i < len(ic):
            head_ic = icon(ic[i], 30)
        else:
            head_ic = ('<span aria-hidden="true" class="on-media" style="flex:none;width:34px;height:34px;border-radius:6px;background:%s;'
                       'display:flex;align-items:center;justify-content:center;font-weight:900;font-size:16px">%d</span>' % (ACC, i + 1))
        rows += ('<div class="reveal sb-card" style="display:flex;gap:18px;align-items:center;padding:22px 26px">'
                 + head_ic
                 + blk(b, "div", "", "font-size:18px;line-height:1.5;color:var(--sb-text-on-dark)")
                 + '</div>')
    inner += '<div style="display:flex;flex-direction:column;gap:14px;margin-top:26px">%s</div>' % rows
    if decision:
        inner += ('<div style="margin-top:22px">'
                  + p_accent_box(blk(decision, "div", "", "font-size:20px;font-weight:700;line-height:1.45"))
                  + '</div>')
    return inner, 64

def recommendation(s, acc):
    g = grp(s)
    head = _headline_block(g)
    rats = g.get("card_body", [])
    nxt = _first(g, "list_item")
    ic = icons_of(s)
    top = blk(head, "h2", "hl reveal", "font-size:46px;margin:0 0 6px") + rule("6px")
    cards = ""
    for i, b in enumerate(rats):
        head_ic = (icon(ic[i], 34) + '<div style="height:12px"></div>') if i < len(ic) else ""
        cards += ('<div class="reveal sb-card" style="flex:1;padding:28px 26px">'
                  + head_ic
                  + blk(b, "div", "", "font-size:17px;line-height:1.55;color:var(--sb-body-on-dark)")
                  + '</div>')
    row = '<div style="display:flex;gap:22px;align-items:stretch">%s</div>' % cards
    band = ""
    if nxt:
        band = ('<div style="margin-top:22px">'
                + p_accent_box(blk(nxt, "div", "", "font-size:19px;font-weight:700"))
                + '</div>')
    inner = top + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">' + row + band + '</div>'
    return inner, 64

def options(s, acc):
    g = grp(s)
    heads = g.get("headline", [])
    rec = heads[0] if heads else None
    opts = g.get("card_title", [])
    crit = _first(g, "body")
    ic = icons_of(s)
    top = ""
    if rec:
        top = blk(rec, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
    if crit:
        top += p_body(crit, 18, "16px", "820px")
    cards = ""
    for i, b in enumerate(opts):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        head_ic = (icon(ic[i], 42) + '<div style="height:16px"></div>') if i < len(ic) else ""
        cards += ('<div class="reveal-scale sb-card" style="flex:1 1 0;min-width:0;max-width:340px;min-height:230px;'
                  'border-top:6px solid %s;padding:36px 30px;display:flex;flex-direction:column;'
                  'align-items:center;justify-content:center;text-align:center">' % col
                  + head_ic
                  + blk(b, "div", "no-caps", "font-weight:900;font-size:26px;line-height:1.2;color:var(--sb-text-on-dark)")
                  + '</div>')
    row = ('<div style="display:flex;gap:26px;align-items:stretch;justify-content:center;'
           'flex-wrap:nowrap;margin-top:30px;width:100%%">%s</div>' % cards)
    inner = top + '<div style="flex:1;display:flex;align-items:center;justify-content:center">' + row + '</div>'
    return inner, 64

def matrix2x2(s, acc):
    g = grp(s)
    bodies = g.get("body", [])
    xax = bodies[0] if len(bodies) > 0 else None
    yax = bodies[1] if len(bodies) > 1 else None
    target = bodies[2] if len(bodies) > 2 else None
    items = g.get("list_item", [])
    panel_title = _first(g, "card_title")
    head = _headline_block(g)
    chips = ""
    for b in items:
        chips += ('<span class="on-media" style="display:inline-block;background:rgba(255,255,255,0.18);'
                  'border:1px solid rgba(255,255,255,0.45);border-radius:6px;padding:9px 16px;margin:5px;'
                  'font-size:16px;font-weight:700;line-height:1.15">%s</span>' % blk(b, "span"))
    empty = '<div class="sb-card" style="border-radius:6px"></div>'
    target_cell = ('<div class="reveal-scale on-media" style="background:%s;border-radius:6px;padding:26px;'
                   'display:flex;flex-wrap:wrap;align-content:center;justify-content:center;'
                   'align-items:center;gap:4px">%s</div>' % (ACC, chips))
    # Grid fills its column vertically (flex:1) and is capped + centered horizontally
    grid = ('<div style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:18px;'
            'width:100%;max-width:560px;height:400px;align-self:center">'
            + empty + target_cell + empty + empty + '</div>')
    yaxis = ('<div style="display:flex;align-items:center;flex:none">'
             '<div style="writing-mode:vertical-rl;transform:rotate(180deg);font-size:15px;font-weight:800;'
             'letter-spacing:0.04em;color:var(--sb-body-on-dark);max-width:52px;text-align:center">%s</div></div>'
             % blk(yax, "span"))
    xaxis = ('<div style="text-align:center;font-size:15px;font-weight:800;letter-spacing:0.04em;'
             'color:var(--sb-body-on-dark);margin-top:16px">%s</div>' % blk(xax, "span"))
    matrix = ('<div style="flex:1;display:flex;gap:16px;align-items:stretch;justify-content:center">'
              + yaxis
              + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">' + grid + xaxis + '</div></div>')
    panel = ('<div class="reveal-right" style="flex:0 0 290px;display:flex;flex-direction:column;justify-content:center">'
             + (blk(panel_title, "div", "no-caps", "font-size:25px;font-weight:900;color:var(--sb-title);margin-bottom:14px") if panel_title else "")
             + (p_body(target, 18, "0", "300px") if target else "") + '</div>')
    title = blk(head, "h2", "hl reveal", "font-size:38px;margin:0 0 16px") if head else ""
    inner = title + '<div style="flex:1;display:flex;gap:40px;align-items:stretch">' + matrix + panel + '</div>'
    return inner, 64

def tree(s, acc):
    g = grp(s)
    heads = g.get("headline", [])
    root = heads[0] if heads else None
    hyp = heads[1] if len(heads) > 1 else None
    branches = g.get("card_title", [])[:3]
    root_node = ('<div class="reveal-left on-media" style="background:%s;border-radius:6px;padding:26px 24px;'
                 'display:flex;align-items:center;min-height:120px">%s</div>'
                 % (ACC, blk(root, "div", "no-caps", "font-size:24px;font-weight:900;line-height:1.25")))
    conn = ('<svg viewBox="0 0 100 100" preserveAspectRatio="none" style="width:100%%;height:100%%">'
            '<line x1="0" y1="50" x2="100" y2="17" stroke="%s" stroke-width="1.5"/>'
            '<line x1="0" y1="50" x2="100" y2="50" stroke="%s" stroke-width="1.5"/>'
            '<line x1="0" y1="50" x2="100" y2="83" stroke="%s" stroke-width="1.5"/></svg>' % (ACC, ACC, ACC))
    bcards = ""
    for b in branches:
        bcards += ('<div class="reveal sb-card" style="flex:1;display:flex;align-items:center;padding:20px 24px">'
                   + blk(b, "div", "no-caps", "font-size:20px;font-weight:800;color:var(--sb-text-on-dark)") + '</div>')
    branch_col = '<div style="flex:1;display:flex;flex-direction:column;gap:16px">%s</div>' % bcards
    row = ('<div style="flex:1;display:flex;align-items:stretch">'
           '<div style="flex:0 0 260px;display:flex;align-items:center">' + root_node + '</div>'
           '<div style="flex:0 0 70px">' + conn + '</div>'
           + branch_col + '</div>')
    band = ""
    if hyp:
        band = ('<div style="margin-top:22px">'
                + p_accent_box(blk(hyp, "div", "no-caps", "font-size:22px;font-weight:800;line-height:1.3")) + '</div>')
    inner = p_kicker(g) + row + band
    return inner, 64

def synthesis(s, acc):
    g = grp(s)
    findings = g.get("card_title", [])
    concl = _headline_block(g)
    action = _first(g, "list_item")
    ic = icons_of(s)
    cards = ""
    for i, b in enumerate(findings):
        head_ic = (icon(ic[i], 32) + '<div style="height:10px"></div>') if i < len(ic) else ""
        cards += ('<div class="reveal sb-card" style="flex:1;padding:26px 24px">'
                  + head_ic
                  + blk(b, "div", "no-caps", "font-size:20px;font-weight:800;color:var(--sb-text-on-dark);line-height:1.3") + '</div>')
    row = '<div style="display:flex;gap:20px;align-items:stretch">%s</div>' % cards
    arrow = ('<div style="display:flex;justify-content:center;margin:18px 0">'
             '<div style="width:18px;height:18px;border-right:4px solid %s;border-bottom:4px solid %s;transform:rotate(45deg)"></div></div>' % (ACC, ACC))
    syn_inner = blk(concl, "div", "no-caps", "font-size:30px;font-weight:900;line-height:1.25")
    if action:
        syn_inner += blk(action, "div", "", "font-size:18px;font-weight:700;margin-top:14px;opacity:0.92")
    band = p_accent_box(syn_inner)
    inner = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
             + row + arrow + band + '</div>')
    return inner, 64

def hub(s, acc):
    g = grp(s)
    bodies = g.get("body", [])
    center_b = bodies[0] if bodies else None
    pains = bodies[1:5]
    syn = _headline_block(g)
    ic = icons_of(s)
    positions = [(50, 13), (16, 50), (84, 50), (50, 87)]

    def node(b, x, y, i):
        ib = (icon(ic[i], 26) + '<div style="height:8px"></div>') if i < len(ic) else ""
        tmpl = ('<div class="reveal-scale sb-card" style="position:absolute;left:%d%%;top:%d%%;'
                'transform:translate(-50%%,-50%%);width:26%%;padding:16px;box-sizing:border-box">%s%s</div>')
        return tmpl % (x, y, ib, blk(b, "div", "", "font-size:14px;line-height:1.4;color:var(--sb-text-on-dark)"))
    nodes = ""
    for i, b in enumerate(pains):
        x, y = positions[i]
        nodes += node(b, x, y, i)
    center = ('<div class="on-media" style="position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);'
              'width:30%%;background:%s;border-radius:6px;padding:22px 18px;box-sizing:border-box;text-align:center;z-index:2">'
              % ACC
              + blk(center_b, "div", "", "font-size:16px;font-weight:800;line-height:1.4") + '</div>')
    lines = ""
    for (x, y) in positions[:len(pains)]:
        lines += '<line x1="50" y1="50" x2="%d" y2="%d" stroke="%s" stroke-width="0.6"/>' % (x, y, ACC)
    svg = ('<svg viewBox="0 0 100 100" preserveAspectRatio="none" '
           'style="position:absolute;inset:0;width:100%;height:100%;z-index:0">' + lines + '</svg>')
    diagram = '<div style="position:relative;flex:1;min-height:340px">' + svg + nodes + center + '</div>'
    band = ""
    if syn:
        band = ('<div style="margin-top:18px">'
                + p_accent_box(blk(syn, "div", "no-caps", "font-size:24px;font-weight:800;line-height:1.3")) + '</div>')
    inner = p_kicker(g) + diagram + band
    return inner, 64

def layers(s, acc):
    g = grp(s)
    b = g.get("body", [])
    cb = g.get("card_body", [])
    ordered = []
    ordered += b[:3]
    if cb:
        ordered.append(cb[0])
    if len(b) > 3:
        ordered.append(b[3])
    if not ordered:
        ordered = b + cb
    n = len(ordered)
    disp = list(reversed(ordered))
    rows = ""
    for i, bb in enumerate(disp):
        if n > 1:
            w = 60 + i * (40 // (n - 1))
        else:
            w = 100
        if i == 0:
            cell = ('<div class="reveal on-media" style="width:%d%%;background:%s;border-radius:6px;padding:18px 24px;margin:0 auto;text-align:center">' % (w, ACC)
                    + blk(bb, "div", "", "font-size:17px;font-weight:800;line-height:1.4") + '</div>')
        else:
            cell = ('<div class="reveal sb-card" style="width:%d%%;padding:16px 24px;margin:0 auto;text-align:center">' % w
                    + blk(bb, "div", "", "font-size:15px;line-height:1.4;color:var(--sb-text-on-dark)") + '</div>')
        rows += '<div style="margin:7px 0">%s</div>' % cell
    inner = p_kicker(g) + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">%s</div>' % rows
    return inner, 64

def maturity(s, acc):
    g = grp(s)
    stages = g.get("card_title", [])
    cur = _first(g, "stat")
    sweet = _first(g, "body")
    n = len(stages)
    cur_idx = int(_num((cur or {}).get("text"))) - 1 if cur else -1
    cols = ""
    for i, b in enumerate(stages):
        if n > 1:
            h = 40 + i * (60 // (n - 1))
        else:
            h = 100
        is_cur = (i == cur_idx)
        barcol = "var(--sb-copper)" if is_cur else ACC
        badge = ""
        if is_cur and cur:
            badge = ('<div class="on-media" style="background:var(--sb-copper);border-radius:6px;padding:6px 10px;margin-bottom:8px;display:inline-block">'
                     + blk(cur, "span", "", "font-size:13px;font-weight:800") + '</div>')
        bar = '<div class="reveal-scale" style="width:70%%;height:%d%%;background:%s;border-radius:6px 6px 0 0;min-height:40px"></div>' % (h, barcol)
        cols += ('<div style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%">'
                 + badge + bar
                 + blk(b, "div", "no-caps", "font-size:15px;font-weight:800;color:var(--sb-text-on-dark);margin-top:12px;text-align:center") + '</div>')
    chart = '<div style="flex:1;display:flex;gap:16px;align-items:flex-end;height:300px">%s</div>' % cols
    band = ""
    if sweet:
        band = ('<div style="margin-top:22px">'
                + p_accent_box(blk(sweet, "div", "", "font-size:18px;font-weight:700;line-height:1.45")) + '</div>')
    inner = p_kicker(g) + chart + band
    return inner, 64

def business_case(s, acc):
    g = grp(s)
    b = g.get("body", [])
    ct = g.get("card_title", [])
    opp = b[0] if len(b) > 0 else None
    inv = b[1] if len(b) > 1 else None
    risks = b[2] if len(b) > 2 else None
    decision = b[3] if len(b) > 3 else None
    benefits = ct[0] if ct else None
    ic = icons_of(s)
    panels = [opp, inv, benefits, risks]
    cells = ""
    for i, pb in enumerate(panels):
        if not pb:
            continue
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        head_ic = (icon(ic[i], 44) + '<div style="height:18px"></div>') if i < len(ic) else ""
        cells += ('<div class="reveal-scale sb-card" style="border-top:6px solid %s;padding:46px 48px;'
                  'min-height:180px;display:flex;flex-direction:column;justify-content:center">' % col
                  + head_ic
                  + blk(pb, "div", "", "font-size:24px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    grid = ('<div style="flex:1;display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:1fr;gap:26px;'
            'align-content:stretch">%s</div>' % cells)
    band = ""
    if decision:
        band = ('<div style="margin-top:24px">'
                + p_accent_box(blk(decision, "div", "", "font-size:21px;font-weight:700;line-height:1.4")) + '</div>')
    head = _headline_block(g)
    title = blk(head, "h2", "hl reveal", "font-size:40px;margin:0 0 20px") if head else ""
    inner = (p_kicker(g) + title
             + '<div style="flex:1;display:flex;flex-direction:column">' + grid + band + '</div>')
    return inner, 64

def journey_columns(s, acc):
    g = grp(s)
    stages = g.get("card_title", [])
    bullets = g.get("list_item", [])
    badges = g.get("caption", [])
    takeaway = _first(g, "body")
    n = len(stages)
    groups = [[] for _ in range(n)]
    if n:
        base = len(bullets) // n
        rem = len(bullets) % n
        idx = 0
        for i in range(n):
            cnt = base + (1 if i < rem else 0)
            groups[i] = bullets[idx:idx + cnt]
            idx += cnt
    cols = ""
    for i, st in enumerate(stages):
        circle = ('<div aria-hidden="true" class="on-media" style="width:52px;height:52px;border-radius:50%%;background:%s;'
                  'display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:900;margin-bottom:16px">%d</div>'
                  % (ACC, i + 1))
        blist = ""
        for bl in groups[i]:
            blist += ('<div style="display:flex;gap:8px;padding:6px 0;font-size:14px;color:var(--sb-body-on-dark);line-height:1.4">'
                      '<span style="flex:none;width:6px;height:6px;border-radius:50%%;background:%s;margin-top:7px"></span>' % ACC
                      + blk(bl, "span") + '</div>')
        badge = ""
        if i < len(badges):
            badge = ('<div class="sb-card" style="margin-top:12px;padding:8px 12px;text-align:center">'
                     + blk(badges[i], "div", "no-caps", "font-size:12px;font-weight:800;letter-spacing:0.06em;color:%s" % ACC) + '</div>')
        cols += ('<div class="reveal sb-card" style="flex:1;padding:24px 20px;display:flex;flex-direction:column">'
                 + circle
                 + blk(st, "div", "no-caps", "font-size:18px;font-weight:900;color:var(--sb-text-on-dark);margin-bottom:10px")
                 + '<div style="flex:1">' + blist + '</div>'
                 + badge + '</div>')
    row = '<div style="display:flex;gap:16px;align-items:stretch">%s</div>' % cols
    band = ""
    if takeaway:
        band = ('<div style="margin-top:20px">'
                + p_accent_box(blk(takeaway, "div", "", "font-size:18px;font-weight:700;line-height:1.4")) + '</div>')
    head = _headline_block(g)
    title = blk(head, "h2", "hl reveal", "font-size:40px;margin:0 0 18px") if head else p_kicker(g)
    inner = title + '<div style="flex:1;display:flex;align-items:center">' + row + '</div>' + band
    return inner, 64

def hub_field(s, acc):
    g = grp(s)
    bodies = g.get("body", [])
    central = bodies[0] if bodies else None
    streams = bodies[1:]
    reality = _first(g, "stat_label")
    ring = [(50, 7), (77, 13), (91, 33), (93, 62), (79, 85), (50, 93), (21, 85), (7, 62), (9, 33), (23, 13)]
    streams = streams[:len(ring)]
    lines = ('<defs><marker id="cc13ar" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">'
             '<path d="M0,0 L6,3 L0,6 Z" fill="rgba(255,255,255,0.55)"/></marker></defs>')
    for (x, y) in ring[:len(streams)]:
        lines += ('<line x1="%d" y1="%d" x2="50" y2="50" stroke="rgba(255,255,255,0.4)" '
                  'stroke-width="0.5" marker-end="url(#cc13ar)"/>' % (x, y))
    svg = ('<svg viewBox="0 0 100 100" preserveAspectRatio="none" '
           'style="position:absolute;inset:0;width:100%;height:100%;z-index:0">' + lines + '</svg>')
    snodes = ""
    tmpl = ('<div style="position:absolute;left:%d%%;top:%d%%;transform:translate(-50%%,-50%%);width:19%%;'
            'background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.28);border-radius:6px;'
            'padding:10px 12px;box-sizing:border-box;z-index:2;text-align:center">%s</div>')
    for i, b in enumerate(streams):
        x, y = ring[i]
        snodes += tmpl % (x, y, blk(b, "div", "", "font-size:13px;line-height:1.35;font-weight:600"))
    center = ('<div class="on-media" style="position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);'
              'width:24%%;background:%s;border:2px solid rgba(255,255,255,0.4);border-radius:6px;padding:20px 16px;'
              'box-sizing:border-box;text-align:center;z-index:3">%s</div>'
              % (ACC, blk(central, "div", "", "font-size:16px;font-weight:900;line-height:1.35")))
    diagram = '<div style="position:relative;flex:1;min-height:380px">' + svg + snodes + center + '</div>'
    kicker = blk(reality, "div", "label", "letter-spacing:0.14em;text-transform:uppercase;font-size:14px;font-weight:800;margin-bottom:20px;opacity:0.85") if reality else ""
    inner = ('<div style="position:absolute;inset:0;background:var(--sb-navy)"></div>'
             '<div class="on-media" style="position:absolute;inset:0;padding:52px 60px;box-sizing:border-box;'
             'display:flex;flex-direction:column;z-index:1">' + kicker + diagram + '</div>')
    return inner, 0

def numeral_actions(s, acc):
    g = grp(s)
    actions = g.get("list_item", [])
    head = _headline_block(g)
    rows = ""
    for i, b in enumerate(actions):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]   # colour each numeral (sky / copper / steel / pink)
        rows += ('<div class="reveal" style="display:flex;gap:28px;align-items:center;padding:22px 0;border-top:2px solid ' + col + '">'
                 + '<div aria-hidden="true" style="font-size:76px;font-weight:900;line-height:0.9;flex:none;min-width:90px;color:%s">%d</div>' % (col, i + 1)
                 + blk(b, "div", "", "font-size:22px;font-weight:700;line-height:1.4;color:var(--sb-text-on-dark)") + '</div>')
    title = blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 10px") if head else ""
    inner = title + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">%s</div>' % rows
    return inner, 64

def waterfall(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stats = g.get("stat", [])
    drivers = g.get("card_title", [])
    sub = _first(g, "body")
    start_b = stats[0] if stats else None
    end_b = stats[1] if len(stats) > 1 else None
    start_v = _num(start_b.get("text")) if start_b else 0.0
    NEG = ("save", "saving", "reduc", "fewer", "less", "lower", "down", "cut", "avoid", "loss", "churn")
    cols = []
    if start_b:
        cols.append({"kind": "total", "block": start_b, "base": 0.0, "top": start_v, "run": start_v})
    run = start_v
    for d in drivers:
        raw = d.get("text") or ""
        t = raw.lower()
        mag = _num(raw)
        neg = raw.strip().startswith("-") or ("−" in raw) or any(k in t for k in NEG)
        dv = -mag if neg else mag
        base = min(run, run + dv)
        top = max(run, run + dv)
        cols.append({"kind": "delta", "block": d, "base": base, "top": top, "up": dv >= 0, "run": run + dv})
        run += dv
    end_v = _num(end_b.get("text")) if end_b else run
    if end_b:
        cols.append({"kind": "total", "block": end_b, "base": 0.0, "top": end_v, "run": end_v})
    mx = max([c["top"] for c in cols] + [start_v, end_v, run, 1.0])
    chartH = 300.0
    scale = chartH / mx
    n = max(1, len(cols))
    cells = ""
    labels = ""
    for c in cols:
        base_px = c["base"] * scale
        bar_px = max(3.0, (c["top"] - c["base"]) * scale)
        if c["kind"] == "total":
            col = "var(--sb-steel)"
            top_val = ('<div style="position:absolute;left:0;right:0;bottom:%.1fpx;text-align:center">' % (c["top"] * scale + 8)
                       + blk(c["block"], "div", "", "font-weight:900;font-size:20px;color:var(--sb-title)") + '</div>')
            lab = "<div style=\"height:1px\"></div>"
        else:
            col = ACC if c["up"] else "var(--sb-copper)"
            top_val = ""
            lab = blk(c["block"], "div", "", "font-size:13px;line-height:1.35;color:var(--sb-body-on-dark);text-align:center")
        cells += ('<div style="flex:1;position:relative;height:%dpx">' % int(chartH)
                  + '<div style="position:absolute;left:16%%;right:16%%;bottom:%.1fpx;height:%.1fpx;background:%s;border-radius:3px 3px 0 0"></div>' % (base_px, bar_px, col)
                  + top_val + '</div>')
        labels += '<div style="flex:1;padding:0 4px">%s</div>' % lab
    seg = ""
    for i in range(len(cols) - 1):
        y = chartH - cols[i]["run"] * scale
        x1 = i * 100 + 84
        x2 = (i + 1) * 100 + 16
        seg += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" style="stroke:var(--sb-border-subtle);stroke-width:2" stroke-dasharray="5,5"/>' % (x1, y, x2, y))
    svg = ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%%;height:%dpx;pointer-events:none">%s</svg>'
           % (n * 100, int(chartH), int(chartH), seg))
    chart = ('<div class="reveal" style="position:relative;padding-top:34px">'
             + '<div style="position:relative;display:flex;gap:12px;align-items:flex-end">' + svg + cells + '</div>'
             + '<div style="display:flex;gap:12px;margin-top:12px">' + labels + '</div></div>')
    inner = (p_title(g, 42) if head else "") + chart
    if sub:
        inner += p_body(sub, 17, mt="24px", mw="900px")
    return inner, 64

def bar_highlight(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stats = g.get("stat", [])
    labels = g.get("card_title") or g.get("label") or []
    bodies = g.get("body", [])
    cap = _first(g, "caption")
    actions = g.get("list_item", [])
    if stats:
        pairs = []
        for i in range(len(stats)):
            if i < len(labels):
                lb = labels[i]
            elif i < len(bodies):
                lb = bodies[i]
            else:
                lb = stats[i]
            pairs.append((lb, stats[i]))
        chart = c_bars(pairs, highlight_idx=0, horizontal=True)
    elif bodies:
        chart = p_list(bodies[:-1] if len(bodies) > 1 else bodies)
    else:
        chart = ""
    interp = bodies[-1] if (stats and bodies) else (bodies[-1] if len(bodies) > 1 else None)
    side = ""
    if interp:
        side += blk(interp, "div", "", "font-size:17px;line-height:1.55;color:var(--sb-text-on-dark);margin-bottom:16px")
    if actions:
        side += p_list(actions, accent=True, size=16)
    if cap:
        side += blk(cap, "div", "", "font-size:13px;font-style:italic;color:var(--sb-body-on-dark);margin-top:16px")
    right = ('<div class="reveal-right sb-card" style="padding:28px 30px;border-top:5px solid var(--sb-copper)">%s</div>' % side) if side else ""
    inner = (p_title(g, 42) if head else "")
    if right:
        inner += '<div style="margin-top:26px">' + p_split(chart, right, lflex="1.5", rflex="1", gap=36, align="center") + '</div>'
    else:
        inner += '<div style="margin-top:26px">%s</div>' % chart
    return inner, 64

def pareto(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stats = g.get("stat", [])
    cats = g.get("card_title") or g.get("label") or g.get("body") or []
    vital = None
    action = _first(g, "list_item")
    note = _first(g, "card_body")
    bodies = g.get("body", [])
    if bodies:
        vital = bodies[-1]
    n = len(stats)
    chart = ""
    if n:
        vals = [_num(b.get("text")) for b in stats]
        order = sorted(range(n), key=lambda i: vals[i], reverse=True)
        mx = max(vals + [1.0])
        tot = sum(vals) or 1.0
        chartH = 250.0
        barMax = chartH * 0.78  # reserve top headroom so value labels stay INSIDE the plot
        lineTop = 20.0          # keep the 100% cumulative point off the very top edge
        cum = 0.0
        cum_pts = []
        seen80 = False
        bars_html = ""
        labels_html = ""
        for rank, i in enumerate(order):
            cum += vals[i]
            cpct = cum / tot
            cum_pts.append(cpct)
            in_vital = not seen80
            if cpct >= 0.8 and not seen80:
                seen80 = True
            col = ACC if in_vital else "var(--sb-steel)"
            barh = max(4.0, vals[i] / mx * barMax)
            vb = stats[i]
            lb = cats[i] if i < len(cats) else None
            bars_html += ('<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end">'
                          + blk(vb, "div", "", "font-weight:900;font-size:15px;color:%s;margin-bottom:6px" % col)
                          + '<div style="width:64%%;height:%.1fpx;background:%s;border-radius:4px 4px 0 0"></div>' % (barh, col)
                          + '</div>')
            labels_html += ('<div style="flex:1;text-align:center">'
                            + (blk(lb, "div", "", "font-size:12px;line-height:1.3;color:var(--sb-body-on-dark)") if lb else "")
                            + '</div>')
        line_pts = ""
        dots = ""
        for rank, cpct in enumerate(cum_pts):
            x = (rank + 0.5) * 1000.0 / n
            y = chartH - cpct * (chartH - lineTop)
            line_pts += "%.1f,%.1f " % (x, y)
            dots += '<circle cx="%.1f" cy="%.1f" r="5" style="fill:var(--sb-copper)"/>' % (x, y)
        svg = ('<svg viewBox="0 0 1000 %d" preserveAspectRatio="none" style="position:absolute;left:0;top:0;width:100%%;height:%dpx;pointer-events:none">'
               '<polyline points="%s" style="fill:none;stroke:var(--sb-copper);stroke-width:3"/>%s</svg>'
               % (int(chartH), int(chartH), line_pts.strip(), dots))
        plot = ('<div style="position:relative;height:%dpx;display:flex;gap:12px;align-items:flex-end">%s%s</div>'
                % (int(chartH), svg, bars_html))
        axis = '<div style="display:flex;gap:12px;margin-top:10px">%s</div>' % labels_html
        chart = '<div class="reveal sb-card" style="padding:22px 26px">%s%s</div>' % (plot, axis)
    foot = ""
    if vital:
        foot += blk(vital, "div", "", "font-size:17px;line-height:1.55;color:var(--sb-text-on-dark)")
    if note:
        foot += blk(note, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark);margin-top:8px")
    left_foot = ('<div class="reveal sb-card" style="flex:1.4;padding:22px 26px">%s</div>' % foot) if foot else ""
    right_foot = ('<div class="reveal-right sb-card" style="flex:1;padding:22px 26px;border-top:5px solid var(--sb-copper)">'
                  + p_list([action], accent=True, size=16) + '</div>') if action else ""
    inner = (blk(head, "h2", "hl reveal", "font-size:42px;margin:0") if head else "")
    inner += '<div style="margin-top:30px">%s</div>' % chart
    if left_foot or right_foot:
        inner += '<div style="display:flex;gap:20px;margin-top:22px;align-items:stretch">%s%s</div>' % (left_foot, right_foot)
    return inner, 64

def small_multiples(s, acc):
    g = grp(s)
    head = _headline_block(g)
    panels = g.get("body", [])
    sparks = [
        "M0,30 L14,26 L28,28 L42,18 L56,20 L70,10 L84,12 L100,4",
        "M0,8 L14,12 L28,10 L42,20 L56,18 L70,28 L84,26 L100,34",
        "M0,20 L14,10 L28,26 L42,14 L56,30 L70,16 L84,28 L100,12",
        "M0,24 L14,22 L28,23 L42,20 L56,21 L70,17 L84,18 L100,10",
    ]
    cols = ["var(--sb-sky)", "var(--sb-copper)", "var(--sb-steel)", "var(--sb-pink)"]
    cells = ""
    for i, b in enumerate(panels[:4]):
        col = cols[i % len(cols)]
        d = sparks[i % len(sparks)]
        area = d + " L100,40 L0,40 Z"
        spark = ('<svg viewBox="0 0 100 40" preserveAspectRatio="none" style="width:100%%;height:70px">'
                 '<path d="%s" style="fill:%s;fill-opacity:0.14"/>'
                 '<path d="%s" style="fill:none;stroke:%s;stroke-width:2.5"/></svg>' % (area, col, d, col))
        cells += ('<div class="reveal-scale sb-card" style="padding:24px 26px">'
                  + '<div style="border-bottom:3px solid %s;padding-bottom:14px;margin-bottom:14px">%s</div>' % (col, spark)
                  + blk(b, "div", "no-caps", "font-size:16px;line-height:1.5;font-weight:700;color:var(--sb-text-on-dark)")
                  + '</div>')
    grid = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:22px;width:100%%">%s</div>' % cells
    inner = ""
    if head:
        inner += blk(head, "h2", "hl reveal", "font-size:40px;margin:0 0 6px") + rule("6px")
        inner += '<div style="height:24px"></div>'
    inner += grid
    return inner, 64

def forecast(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    base_b = bodies[0] if len(bodies) > 0 else None
    up_b = bodies[1] if len(bodies) > 1 else None
    down_b = bodies[2] if len(bodies) > 2 else None
    assum_b = bodies[3] if len(bodies) > 3 else None
    trig_b = bodies[4] if len(bodies) > 4 else None
    # --- chart geometry (viewBox stretched to fill; HTML overlays stay crisp) ---
    # fork_x = 42% -> where recorded history ends ("today") and the three
    # scenarios diverge. y is 0(top)..300(bottom); low y = high value.
    W, H = 620.0, 300.0
    fx = W * 0.42            # today / fork x
    fy = 150.0               # value at the fork
    rx = W - 24.0            # right edge of the plot
    y_up, y_base, y_down = 45.0, 150.0, 255.0
    hist = f"M24,205 L{fx:.1f},{fy:.1f}"
    up = f"M{fx:.1f},{fy:.1f} L{rx:.1f},{y_up:.1f}"
    base = f"M{fx:.1f},{fy:.1f} L{rx:.1f},{y_base:.1f}"
    down = f"M{fx:.1f},{fy:.1f} L{rx:.1f},{y_down:.1f}"
    band = f"M{fx:.1f},{fy:.1f} L{rx:.1f},{y_up:.1f} L{rx:.1f},{y_down:.1f} Z"
    divider = f"M{fx:.1f},14 L{fx:.1f},{H - 14:.1f}"
    baseline = f"M24,{H - 14:.1f} L{rx:.1f},{H - 14:.1f}"
    svg = (
        f'<svg viewBox="0 0 {int(W)} {int(H)}" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%">'
        # baseline axis + shaded uncertainty cone
        f'<path d="{baseline}" style="fill:none;stroke:var(--sb-border-subtle);stroke-width:1.5"/>'
        f'<path d="{band}" style="fill:var(--sb-sky);fill-opacity:0.16"/>'
        # vertical "today" divider where history forks into scenarios
        f'<path d="{divider}" style="fill:none;stroke:var(--sb-title);stroke-width:2;stroke-opacity:0.5" stroke-dasharray="3,6"/>'
        # solid recorded history, then dashed scenario projections
        f'<path d="{hist}" style="fill:none;stroke:var(--sb-title);stroke-width:3.5"/>'
        f'<path d="{up}" style="fill:none;stroke:var(--sb-sky);stroke-width:3" stroke-dasharray="9,6"/>'
        f'<path d="{base}" style="fill:none;stroke:var(--sb-steel);stroke-width:3" stroke-dasharray="9,6"/>'
        f'<path d="{down}" style="fill:none;stroke:var(--sb-copper);stroke-width:3" stroke-dasharray="9,6"/>'
        '</svg>'
    )
    # scenario spec: (block, line-colour, endpoint top as % of plot height)
    scen = [
        (up_b, "var(--sb-sky)", 15.0),
        (base_b, "var(--sb-steel)", 50.0),
        (down_b, "var(--sb-copper)", 85.0),
    ]
    # crisp colour-coded endpoint dots on the plot (SVG dots would shear)
    dots = ""
    for _b, col, top in scen:
        dots += (f'<span aria-hidden="true" style="position:absolute;left:calc(96.1% - 7px);'
                 f'top:calc({top}% - 7px);width:14px;height:14px;border-radius:50%;'
                 f'background:{col};box-shadow:0 0 0 3px var(--sb-panel-bg)"></span>')
    # fork node marks exactly where "today" sits on the history line
    dots += ('<span aria-hidden="true" style="position:absolute;left:calc(42% - 6px);'
             'top:calc(50% - 6px);width:12px;height:12px;border-radius:50%;'
             'background:var(--sb-title);box-shadow:0 0 0 3px var(--sb-panel-bg)"></span>')
    plot_area = f'<div class="reveal" style="position:relative;flex:1;height:100%">{svg}{dots}</div>'
    # legend / endpoint labels: colour swatch + scenario note, aligned to each
    # line's endpoint so it doubles as an at-endpoint label AND a colour key.
    rows = ""
    for b, col, top in scen:
        if not b:
            continue
        swatch = (f'<span aria-hidden="true" style="flex:none;width:16px;height:16px;border-radius:4px;'
                  f'background:{col};margin-top:2px"></span>')
        rows += (f'<div class="reveal-right" style="position:absolute;left:0;right:0;top:calc({top}% - 12px);'
                 'display:flex;gap:10px;align-items:flex-start">'
                 + swatch
                 + blk(b, "div", "no-caps", "font-size:15px;line-height:1.35;font-weight:700;color:var(--sb-text-on-dark)")
                 + '</div>')
    legend_col = f'<div style="position:relative;flex:0 0 230px;height:100%">{rows}</div>'
    chart_row = f'<div style="display:flex;gap:22px;height:300px">{plot_area}{legend_col}</div>'
    chart_card = f'<div class="reveal sb-card" style="padding:22px 26px;margin-top:18px">{chart_row}</div>'
    # supporting notes (assumptions / triggers) beneath the chart
    notes = ""
    for b in (assum_b, trig_b):
        if b:
            notes += ('<div class="reveal sb-card" style="flex:1;padding:16px 22px;border-left:5px solid ' + ACC + '">'
                      + blk(b, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark)") + '</div>')
    inner = (p_title(g, 42) if head else "") + chart_card
    if notes:
        inner += f'<div style="display:flex;gap:20px;margin-top:18px">{notes}</div>'
    return inner, 64

def heatmap(s, acc):
    g = grp(s)
    head = _headline_block(g)
    titles = g.get("card_title", [])
    vals = g.get("stat", [])
    legend = None
    impl = None
    bodies = g.get("body", [])
    if bodies:
        legend = bodies[0]
        impl = bodies[1] if len(bodies) > 1 else None
    V = len(vals)
    T = len(titles)
    R = C = 0
    disc = T * T - 4 * V
    if V and disc >= 0:
        root = int(disc ** 0.5)
        if root * root == disc and (T + root) % 2 == 0:
            R = (T + root) // 2
            C = (T - root) // 2
    if not (R and C and R * C == V):
        C = max(1, int(round(V ** 0.5))) if V else 1
        R = (V + C - 1) // C if V else 0
    row_labels = titles[:R]
    col_labels = titles[R:R + C]
    nums = [_num(v.get("text")) for v in vals]
    lo, hi = (min(nums), max(nums)) if nums else (0.0, 1.0)
    span = (hi - lo) or 1.0
    corner = '<div></div>'
    header = corner
    for j in range(C):
        cb = col_labels[j] if j < len(col_labels) else None
        header += ('<div style="text-align:center;padding:0 6px 10px">'
                   + (blk(cb, "div", "no-caps", "font-size:13px;font-weight:800;color:var(--sb-text-on-dark)") if cb else "") + '</div>')
    body_rows = ""
    for i in range(R):
        rb = row_labels[i] if i < len(row_labels) else None
        body_rows += ('<div style="display:contents">'
                      + '<div style="display:flex;align-items:center;justify-content:flex-end;padding-right:14px">'
                      + (blk(rb, "div", "no-caps", "font-size:14px;font-weight:800;color:var(--sb-text-on-dark);text-align:right") if rb else "") + '</div>')
        for j in range(C):
            idx = i * C + j
            if idx < V:
                op = 0.18 + 0.78 * ((nums[idx] - lo) / span)
                cell = ('<div style="position:relative;border-radius:5px;min-height:52px;display:flex;align-items:center;justify-content:center">'
                        '<div style="position:absolute;inset:0;border-radius:5px;background:%s;opacity:%.2f"></div>' % (ACC, op)
                        + blk(vals[idx], "div", "", "position:relative;font-weight:900;font-size:16px;color:var(--sb-title)") + '</div>')
                body_rows += cell
            else:
                body_rows += '<div></div>'
        body_rows += '</div>'
    grid = ('<div class="reveal" style="display:grid;grid-template-columns:minmax(120px,1.2fr) repeat(%d,1fr);gap:8px;align-items:stretch">%s%s</div>'
            % (C, header, body_rows))
    foot = ""
    if legend:
        foot += blk(legend, "div", "", "font-size:14px;color:var(--sb-body-on-dark)")
    inner = (p_title(g, 40) if head else "") + '<div style="margin-top:22px">%s</div>' % grid
    if legend:
        inner += '<div style="margin-top:16px">%s</div>' % foot
    if impl:
        inner += '<div class="reveal sb-card" style="margin-top:14px;padding:18px 24px;border-left:5px solid var(--sb-product-accent,var(--sb-sky))">' + blk(impl, "div", "", "font-size:16px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>'
    return inner, 64

def funnel(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stages = g.get("card_title", [])
    insight = _first(g, "card_body") or _first(g, "body")
    fun = c_funnel(stages) if stages else ""
    right = ""
    if insight:
        right = ('<div class="reveal-right sb-card" style="padding:28px 30px;border-top:5px solid var(--sb-copper);display:flex;flex-direction:column;justify-content:center">'
                 + blk(insight, "div", "", "font-size:18px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    inner = (p_title(g, 42) if head else "")
    if right:
        inner += '<div style="margin-top:24px">' + p_split(fun, right, lflex="1.6", rflex="1", gap=36, align="center") + '</div>'
    else:
        inner += '<div style="margin-top:24px">%s</div>' % fun
    return inner, 64

def rings(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    ring_blocks = bodies[:3]
    impl = bodies[3] if len(bodies) > 3 else None
    caps = g.get("caption", [])
    visual = c_rings(ring_blocks) if ring_blocks else ""
    inner = (p_title(g, 42) if head else "") + '<div style="margin-top:20px">%s</div>' % visual
    extra = ""
    if impl:
        extra += ('<div class="reveal sb-card" style="flex:1.4;padding:20px 26px;border-left:5px solid var(--sb-product-accent,var(--sb-sky))">'
                  + blk(impl, "div", "", "font-size:16px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    capinner = ""
    for c in caps:
        capinner += blk(c, "div", "", "font-size:13px;font-style:italic;color:var(--sb-body-on-dark);margin:4px 0")
    if capinner:
        extra += '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">%s</div>' % capinner
    if extra:
        inner += '<div style="display:flex;gap:22px;margin-top:20px;align-items:stretch">%s</div>' % extra
    return inner, 64

def donut(s, acc):
    g = grp(s)
    head = _headline_block(g)
    ask = _first(g, "cta")
    segs = g.get("body", [])
    seg_blocks = segs[:3] if len(segs) > 1 else segs
    ret = segs[3] if len(segs) > 3 else None
    milestones = g.get("list_item", [])
    chart = c_donut(seg_blocks) if seg_blocks else ""
    right = ""
    if ask:
        right += ('<div class="reveal on-media" style="background:%s;border-radius:6px;padding:22px 26px;margin-bottom:18px">' % ACC
                  + blk(ask, "div", "", "font-size:26px;font-weight:900;line-height:1.1") + '</div>')
    if milestones:
        right += p_list(milestones, accent=True, size=16)
    if ret:
        right += blk(ret, "div", "", "font-size:15px;line-height:1.55;color:var(--sb-body-on-dark);margin-top:16px")
    inner = (p_title(g, 42) if head else "")
    if right:
        inner += '<div style="margin-top:22px">' + p_split(chart, '<div>%s</div>' % right, lflex="1.3", rflex="1", gap=40, align="center") + '</div>'
    else:
        inner += '<div style="margin-top:22px">%s</div>' % chart
    return inner, 64

def bubbles(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    xax = bodies[0] if len(bodies) > 0 else None
    yax = bodies[1] if len(bodies) > 1 else None
    zone = bodies[3] if len(bodies) > 3 else None
    moves = bodies[4] if len(bodies) > 4 else None
    items = g.get("card_title") or g.get("label") or []
    sizes = g.get("stat", [])
    positions = [(72, 24), (58, 40), (30, 62), (80, 45), (45, 30), (22, 78), (66, 66), (38, 48)]
    bubbles_html = ""
    if items:
        svals = [_num(x.get("text")) for x in sizes] if sizes else []
        smax = max(svals + [1.0]) if svals else 1.0
        for i, it in enumerate(items[:8]):
            px, py = positions[i % len(positions)]
            if i < len(svals):
                dia = 44 + 46 * (svals[i] / smax)
            else:
                dia = 62
            col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
            in_zone = px >= 50 and py <= 50
            bubbles_html += ('<div style="position:absolute;left:%.0f%%;top:%.0f%%;transform:translate(-50%%,-50%%);width:%.0fpx;height:%.0fpx;border-radius:50%%;background:%s;opacity:0.9;display:flex;align-items:center;justify-content:center;text-align:center;padding:4px;box-sizing:border-box">' % (px, py, dia, dia, col)
                             + blk(it, "div", "on-media", "font-size:12px;font-weight:800;line-height:1.15") + '</div>')
    else:
        for i in range(4):
            px, py = positions[i]
            col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
            bubbles_html += '<div style="position:absolute;left:%.0f%%;top:%.0f%%;transform:translate(-50%%,-50%%);width:%dpx;height:%dpx;border-radius:50%%;background:%s;opacity:0.85"></div>' % (px, py, 70 - i * 8, 70 - i * 8, col)
    zone_shade = '<div style="position:absolute;left:50%;top:0;right:0;height:50%;background:var(--sb-product-accent,var(--sb-sky));opacity:0.08;border-radius:0 6px 0 0"></div>'
    zone_lab = ('<div style="position:absolute;right:14px;top:10px;max-width:180px;text-align:right">'
                + blk(zone, "div", "", "font-size:13px;font-weight:800;color:var(--sb-product-accent,var(--sb-sky))") + '</div>') if zone else ""
    axes = ('<div style="position:absolute;left:0;bottom:0;width:100%;height:2px;background:var(--sb-border-subtle)"></div>'
            '<div style="position:absolute;left:0;bottom:0;width:2px;height:100%;background:var(--sb-border-subtle)"></div>')
    yl = ('<div style="position:absolute;left:-12px;top:50%;transform:translateY(-50%) rotate(-90deg);transform-origin:center;white-space:nowrap">'
          + blk(yax, "div", "", "font-size:13px;font-weight:800;letter-spacing:0.06em;color:var(--sb-body-on-dark)") + '</div>') if yax else ""
    plot = ('<div class="reveal" style="position:relative;height:330px;margin-left:34px;border-radius:6px">'
            + zone_shade + axes + zone_lab + bubbles_html + '</div>')
    xl = ('<div style="text-align:center;margin-top:10px;margin-left:34px">'
          + blk(xax, "div", "", "font-size:13px;font-weight:800;letter-spacing:0.06em;color:var(--sb-body-on-dark)") + '</div>') if xax else ""
    left = '<div style="position:relative">%s%s%s</div>' % (yl, plot, xl)
    right = ""
    if moves:
        right = ('<div class="reveal-right sb-card" style="padding:26px 28px;display:flex;flex-direction:column;justify-content:center">'
                 + blk(moves, "div", "", "font-size:17px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    inner = (p_title(g, 42) if head else "")
    if right:
        inner += '<div style="margin-top:20px">' + p_split(left, right, lflex="1.6", rflex="1", gap=36, align="center") + '</div>'
    else:
        inner += '<div style="margin-top:20px">%s</div>' % left
    return inner, 64

def dashboard(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stats = g.get("stat", [])
    labels = g.get("stat_label", [])
    bodies = g.get("body", [])
    trend = bodies[0] if len(bodies) > 0 else None
    comment = bodies[1] if len(bodies) > 1 else None
    sparks = [
        "M0,28 L20,24 L40,26 L60,16 L80,12 L100,4",
        "M0,20 L20,22 L40,14 L60,18 L80,10 L100,6",
        "M0,30 L20,20 L40,24 L60,14 L80,16 L100,8",
    ]
    cols = ["var(--sb-sky)", "var(--sb-copper)", "var(--sb-steel)"]
    tiles = ""
    for i, st in enumerate(stats[:3]):
        col = cols[i % len(cols)]
        d = sparks[i % len(sparks)]
        spark = ('<svg viewBox="0 0 100 32" preserveAspectRatio="none" style="width:100%%;height:34px;margin-top:10px">'
                 '<path d="%s" style="fill:none;stroke:%s;stroke-width:3"/></svg>' % (d, col))
        tiles += ('<div class="reveal-scale sb-card" style="flex:1;padding:26px 28px;border-top:4px solid %s">' % col
                  + blk(st, "div", "kpi-num", "font-size:56px")
                  + (blk(labels[i], "div", "kpi-label", "margin-top:6px;font-size:14px;color:var(--sb-body-on-dark)") if i < len(labels) else "")
                  + spark + '</div>')
    tiles_row = '<div style="display:flex;gap:20px">%s</div>' % tiles
    area_d = "M0,60 L40,50 L80,54 L120,38 L160,42 L200,26 L240,30 L280,14 L320,18 L360,6"
    area_fill = area_d + " L360,80 L0,80 Z"
    trend_card = ('<div class="reveal sb-card" style="flex:2;padding:24px 28px">'
                  + (blk(trend, "div", "no-caps", "font-weight:800;font-size:18px;color:var(--sb-text-on-dark);margin-bottom:12px") if trend else "")
                  + '<svg viewBox="0 0 360 80" preserveAspectRatio="none" style="width:100%;height:120px">'
                  + '<path d="%s" style="fill:var(--sb-product-accent,var(--sb-sky));fill-opacity:0.12"/>' % area_fill
                  + '<path d="%s" style="fill:none;stroke:var(--sb-product-accent,var(--sb-sky));stroke-width:3"/></svg>' % area_d
                  + '</div>')
    comment_card = ('<div class="reveal-right sb-card" style="flex:1;padding:24px 28px;border-left:5px solid var(--sb-product-accent,var(--sb-sky));display:flex;align-items:center">'
                    + blk(comment, "div", "", "font-size:16px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>') if comment else ""
    bottom = '<div style="display:flex;gap:20px;margin-top:20px;align-items:stretch">%s%s</div>' % (trend_card, comment_card)
    inner = (p_title(g, 40) if head else "") + '<div style="margin-top:22px">' + tiles_row + bottom + '</div>'
    return inner, 64

def data_table(s, acc):
    g = grp(s)
    kicker = _first(g, "label")
    headers = g.get("headline", [])
    row_labels = g.get("card_title", [])
    figures = g.get("stat", [])
    cap = _first(g, "caption")
    takeaway = _first(g, "body")
    C = len(headers)
    header_blocks = headers
    rows_blocks = []
    if C >= 2 and row_labels:
        per = C - 1
        fi = 0
        for rl in row_labels:
            row = [rl]
            for _ in range(per):
                row.append(figures[fi] if fi < len(figures) else None)
                fi += 1
            rows_blocks.append(row)
    elif row_labels:
        for i, rl in enumerate(row_labels):
            row = [rl]
            if i < len(figures):
                row.append(figures[i])
            rows_blocks.append(row)
        if not header_blocks:
            header_blocks = []
    table = p_table(header_blocks, rows_blocks) if rows_blocks else ""
    inner = ""
    if kicker:
        inner += p_kicker(g)
    inner += table
    if takeaway:
        inner += ('<div class="reveal sb-card" style="margin-top:20px;padding:18px 24px;border-left:5px solid var(--sb-product-accent,var(--sb-sky))">'
                  + blk(takeaway, "div", "", "font-size:16px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    if cap:
        inner += blk(cap, "div", "", "font-size:13px;font-style:italic;color:var(--sb-body-on-dark);margin-top:12px")
    return inner, 64

def status_grid(s, acc):
    def _status_color(txt):
        t = (txt or "").strip().lower()
        num = _num(t)
        has_num = any(ch.isdigit() for ch in t)
        if has_num:
            if num >= 80:
                return "var(--sb-sky)"
            if num >= 50:
                return "var(--sb-copper)"
            return "var(--sb-pink)"
        bad = ("low", "off", "red", "miss", "fail", "block", "behind", "at risk", "risk", "no")
        mid = ("med", "mid", "amber", "warn", "watch", "yellow", "partial")
        if t in ("l",) or any(k in t for k in bad):
            return "var(--sb-pink)"
        if t in ("m",) or any(k in t for k in mid):
            return "var(--sb-copper)"
        return "var(--sb-sky)"
    g = grp(s)
    head = _headline_block(g)
    criteria = g.get("card_title", [])
    statuses = g.get("stat", [])
    items = g.get("list_item", [])
    bodies = g.get("body", [])
    legend = bodies[0] if bodies else None
    C = len(criteria)
    V = len(statuses)
    matrix = C >= 1 and V and (V % C == 0) and (V // C <= max(1, len(items)))
    grid = ""
    row_actions = []
    if matrix:
        R = V // C
        row_labels = items[:R]
        row_actions = items[R:2 * R]
        header = '<div></div>'
        for cb in criteria:
            header += '<div style="text-align:center;padding:0 4px 10px">' + blk(cb, "div", "no-caps", "font-size:13px;font-weight:800;color:var(--sb-text-on-dark)") + '</div>'
        rows_html = ""
        for i in range(R):
            rl = row_labels[i] if i < len(row_labels) else None
            rows_html += '<div style="display:flex;align-items:center;padding-right:12px">' + (blk(rl, "div", "no-caps", "font-size:15px;font-weight:700;color:var(--sb-text-on-dark)") if rl else "") + '</div>'
            for j in range(C):
                st = statuses[i * C + j]
                col = _status_color(st.get("text"))
                rows_html += ('<div style="display:flex;align-items:center;justify-content:center;padding:6px">'
                              '<div class="on-media" style="min-width:56px;padding:8px 12px;border-radius:5px;background:%s;text-align:center">' % col
                              + blk(st, "div", "", "font-size:14px;font-weight:900") + '</div></div>')
        grid = ('<div class="reveal" style="display:grid;grid-template-columns:minmax(150px,1.4fr) repeat(%d,1fr);gap:8px;align-items:stretch">%s%s</div>'
                % (C, header, rows_html))
    else:
        rows_html = ""
        for i, it in enumerate(items):
            st = statuses[i] if i < len(statuses) else None
            chip = ""
            if st:
                col = _status_color(st.get("text"))
                chip = ('<div class="on-media" style="flex:none;min-width:60px;padding:8px 14px;border-radius:5px;background:%s;text-align:center">' % col
                        + blk(st, "div", "", "font-size:14px;font-weight:900") + '</div>')
            rows_html += ('<div class="reveal sb-card" style="display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 22px">'
                          + blk(it, "div", "", "font-size:17px;color:var(--sb-text-on-dark)") + chip + '</div>')
        grid = '<div style="display:flex;flex-direction:column;gap:12px">%s</div>' % rows_html
    inner = (p_title(g, 40) if head else "") + '<div style="margin-top:22px">%s</div>' % grid
    if legend:
        inner += '<div style="margin-top:16px">' + blk(legend, "div", "", "font-size:14px;color:var(--sb-body-on-dark)") + '</div>'
    if matrix and row_actions:
        inner += '<div style="margin-top:14px">' + p_list(row_actions, accent=True, size=15) + '</div>'
    return inner, 64

def cost_benefit(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    invest = bodies[0] if len(bodies) > 0 else None
    risk = bodies[1] if len(bodies) > 1 else None
    payback = bodies[2] if len(bodies) > 2 else None
    benefits = g.get("card_title", [])[:4]      # AN-14 is a 2-benefit stack; cap so extras can't overflow
    chartH = 260.0
    # Benefit segment heights ALWAYS normalized to fit benH exactly (never overflow the column).
    benH = 0.86 * chartH
    vals = [_num(b.get("text")) for b in benefits]
    if benefits and sum(vals) > 0:
        tot = sum(vals) or 1.0
        seg_h = [max(30.0, (v / tot) * benH) for v in vals]
    elif benefits:
        seg_h = [benH / len(benefits)] * len(benefits)
    else:
        seg_h = []
    ssum = sum(seg_h) or 1.0
    seg_h = [h * benH / ssum for h in seg_h]     # re-normalize so the stack fits within benH
    iv = _num(invest.get("text")) if invest else 0.0
    iv_h = max(30.0, min(chartH, iv)) if iv > 0 else 0.60 * chartH
    inv_bar = ('<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:%dpx">' % int(chartH)
               + '<div style="width:66%%;height:%.1fpx;background:var(--sb-copper);border-radius:6px 6px 0 0"></div></div>' % iv_h)
    seg_stack = ""
    bcols = ["var(--sb-sky)", "var(--sb-steel)", "var(--sb-pink)", "var(--sb-navy)"]
    for i, b in enumerate(benefits):
        seg_stack += ('<div class="on-media" style="height:%.1fpx;background:%s;display:flex;align-items:center;justify-content:center;text-align:center;padding:4px 8px;box-sizing:border-box;border-radius:%s">' % (seg_h[i], bcols[i % len(bcols)], "6px 6px 0 0" if i == 0 else "0")
                      + blk(b, "div", "", "font-size:13px;font-weight:800;line-height:1.15") + '</div>')
    if not seg_stack:
        seg_stack = '<div style="height:%.1fpx;background:var(--sb-sky);border-radius:6px 6px 0 0"></div>' % (0.7 * chartH)
    ben_bar = ('<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:%dpx">' % int(chartH)
               + '<div style="width:66%%;display:flex;flex-direction:column;justify-content:flex-end">%s</div></div>' % seg_stack)
    # bars clipped to a fixed height so nothing can spill upward over the title
    bars = '<div style="display:flex;gap:30px;align-items:flex-end;height:%dpx;overflow:hidden">%s%s</div>' % (int(chartH), inv_bar, ben_bar)
    # invest caption sits in its own row BELOW the bars (free to wrap without changing bar heights)
    cap = ('<div style="display:flex;gap:30px;margin-top:12px"><div style="flex:1;text-align:center">'
           + (blk(invest, "div", "", "font-size:13px;line-height:1.4;color:var(--sb-body-on-dark)") if invest else "")
           + '</div><div style="flex:1"></div></div>')
    chart = '<div class="reveal" style="max-width:440px">%s%s</div>' % (bars, cap)
    notes = ""
    for b in (risk, payback):
        if b:
            notes += ('<div class="reveal-right sb-card" style="padding:20px 24px;margin-bottom:16px">'
                      + blk(b, "div", "", "font-size:16px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    inner = (p_title(g, 42) if head else "")
    inner += '<div style="margin-top:20px">' + p_split(chart, '<div>%s</div>' % notes, lflex="1", rflex="1", gap=44, align="center") + '</div>'
    return inner, 64

def multiplier_rows(s, acc):
    g = grp(s)
    kicker = _first(g, "label")
    factors = g.get("stat", [])
    # ONE claim per multiplier: author supplies a card_title block for each stat
    # row (that is the "text box beside the number"). Fall back to headline blocks
    # if no card_titles were given, so a single-headline slide still degrades gracefully.
    claims = g.get("card_title", []) or g.get("headline", [])
    # italic attribution under each claim comes from caption blocks (one per row)
    sources = g.get("caption", [])
    footer = _first(g, "body")
    rows = ""
    n = max(len(factors), len(claims))
    for i in range(n):
        f = factors[i] if i < len(factors) else None
        c = claims[i] if i < len(claims) else None
        src = sources[i] if i < len(sources) else None
        border = "border-top:1px solid var(--sb-border-subtle);" if i else ""
        rows += ('<div class="reveal" style="display:flex;align-items:center;gap:34px;padding:26px 0;%s">' % border
                 + '<div style="flex:0 0 160px">' + blk(f, "div", "kpi-num", "font-size:62px;line-height:1") + '</div>'
                 + '<div style="flex:1">'
                 + (blk(c, "div", "no-caps", "font-weight:800;font-size:23px;line-height:1.3;color:var(--sb-text-on-dark)") if c else "")
                 + (blk(src, "div", "", "font-size:14px;font-style:italic;color:var(--sb-body-on-dark);margin-top:8px") if src else "")
                 + '</div></div>')
    inner = ""
    if kicker:
        inner += p_kicker(g)
    inner += rows
    if footer:
        inner += ('<div class="reveal" style="margin-top:22px">'
                  + blk(footer, "div", "", "font-size:17px;font-weight:800;letter-spacing:0.02em;color:var(--sb-product-accent,var(--sb-sky))") + '</div>')
    return inner, 64

def roadmap(s, acc):
    g = grp(s)
    head = _headline_block(g)
    kick = g.get("kicker", [None])[0]
    # Accepts BOTH the generic card_title/list_item/body triple and the documented
    # step_label/step_title/step_body triple, plus an optional closing quote band
    # (TKMS deck gap, 2026-08: plans authored with step_* rendered empty).
    phases = (g.get("card_title") or g.get("step_title") or [])[:4]
    mils = g.get("list_item") or g.get("step_label") or []
    owners = g.get("body") or g.get("step_body") or []
    quote = g.get("quote", [None])[0]
    n = len(phases)
    chev = ('<div style="flex:0 0 26px;display:flex;align-items:center;justify-content:center">'
            '<div style="width:14px;height:14px;border-top:4px solid ' + ACC + ';border-right:4px solid ' + ACC
            + ';transform:rotate(45deg);opacity:0.55"></div></div>')
    cells = ""
    for i in range(n):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        mil = mils[i] if i < len(mils) else None
        own = owners[i] if i < len(owners) else None
        badge = ('<span class="on-media" style="flex:none;width:36px;height:36px;border-radius:6px;background:' + col
                 + ';display:flex;align-items:center;justify-content:center;font-weight:900;font-size:16px">' + str(i + 1) + '</span>')
        milhtml = ""
        if mil:
            milhtml = ('<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px">'
                       '<span style="flex:none;width:8px;height:8px;border-radius:50%;background:' + col + ';margin-top:7px"></span>'
                       + blk(mil, "div", "", "font-size:15px;line-height:1.4;color:var(--sb-text-on-dark);font-weight:700") + '</div>')
        cells += ('<div class="reveal-scale sb-card" style="flex:1;padding:24px 22px;border-top:5px solid ' + col + '">'
                  + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">' + badge
                  + blk(phases[i], "div", "no-caps", "font-weight:900;font-size:20px;color:var(--sb-text-on-dark)") + '</div>'
                  + milhtml
                  + (blk(own, "div", "", "font-size:14px;line-height:1.5;color:var(--sb-body-on-dark)") if own else "")
                  + '</div>')
        if i < n - 1:
            cells += chev
    kicker_html = blk(kick, "div", "reveal", "font-size:14px;font-weight:800;letter-spacing:0.2em;color:" + ACC + ";margin:0 0 10px") if kick else ""
    qband = ""
    if quote:
        qband = ('<div class="reveal sb-card" style="margin-top:20px;padding:18px 30px;border-left:5px solid ' + ACC + '">'
                 + blk(quote, "div", "no-caps", "font-size:19px;font-weight:700;line-height:1.4;font-style:italic;color:var(--sb-text-on-dark)") + '</div>')
    inner = (kicker_html + blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;align-items:center"><div style="display:flex;gap:6px;width:100%;align-items:stretch">'
             + cells + '</div></div>' + qband)
    return inner, 64

def gantt(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    mils = g.get("list_item", [])
    rows = [bodies[i:i + 4] for i in range(0, len(bodies), 4)]
    spans = []
    mx = 1.0
    for r in rows:
        se = (r[1].get("text") if len(r) > 1 and r[1] else "") or ""
        nums = re.findall(r'\d[\d.]*', se.replace(",", ""))
        if len(nums) >= 2:
            a, b = float(nums[0]), float(nums[1])
        elif len(nums) == 1:
            a, b = 0.0, float(nums[0])
        else:
            a, b = -1.0, -1.0
        spans.append([a, b])
        if b > mx:
            mx = b
    n = len(rows)
    grid = ""
    for gx in range(1, 5):
        left = gx * 20.0
        grid += ('<div style="position:absolute;top:0;bottom:0;left:' + ("%.1f" % left)
                 + '%;width:1px;background:var(--sb-border-subtle)"></div>')
    rowshtml = ""
    for i, r in enumerate(rows):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        act = r[0] if len(r) > 0 else None
        se = r[1] if len(r) > 1 else None
        dep = r[2] if len(r) > 2 else None
        risk = r[3] if len(r) > 3 else None
        a, b = spans[i]
        if a < 0:
            width = max(18.0, 100.0 / max(1, n))
            leftp = (i / max(1, n)) * (100.0 - width)
        else:
            leftp = (a / mx) * 100.0
            width = max(8.0, ((b - a) / mx) * 100.0)
        bar = ('<div style="position:absolute;left:' + ("%.1f" % leftp) + '%;width:' + ("%.1f" % width)
               + '%;top:6px;bottom:6px;background:' + col + ';border-radius:6px;display:flex;align-items:center;padding:0 12px;overflow:hidden">'
               + (blk(se, "span", "on-media", "font-size:12px;font-weight:800;white-space:nowrap") if se else "") + '</div>')
        labelcol = ('<div style="flex:0 0 230px;padding-right:14px">'
                    + (blk(act, "div", "", "font-size:15px;font-weight:800;color:var(--sb-text-on-dark);line-height:1.3") if act else "")
                    + (blk(dep, "div", "", "font-size:12px;color:var(--sb-body-on-dark);margin-top:3px") if dep else "")
                    + '</div>')
        track = ('<div style="flex:1;position:relative;height:42px;background:var(--sb-border-subtle);border-radius:6px">'
                 + grid + bar + '</div>')
        riskcol = ('<div style="flex:0 0 170px;padding-left:14px">'
                   + (blk(risk, "div", "", "font-size:12px;font-weight:700;color:var(--sb-copper);line-height:1.35") if risk else "") + '</div>')
        rowshtml += '<div class="reveal" style="display:flex;align-items:center;margin:8px 0">' + labelcol + track + riskcol + '</div>'
    milhtml = ""
    if mils:
        chips = ""
        for b in mils:
            chips += ('<div style="display:flex;align-items:center;gap:10px">'
                      '<span style="flex:none;width:14px;height:14px;background:' + ACC + ';transform:rotate(45deg)"></span>'
                      + blk(b, "div", "", "font-size:14px;font-weight:700;color:var(--sb-text-on-dark)") + '</div>')
        milhtml = ('<div class="reveal" style="display:flex;flex-wrap:wrap;gap:26px;margin-top:22px;padding-top:18px;'
                   'border-top:1px solid var(--sb-border-subtle)">' + chips + '</div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:12px">'
             + rowshtml + milhtml + '</div>')
    return inner, 64

def swimlane(s, acc):
    g = grp(s)
    head = _headline_block(g)
    lanes = g.get("card_title", [])[:3]
    bodies = g.get("body", [])
    handoff = bodies[0] if len(bodies) > 0 else None
    bottleneck = bodies[1] if len(bodies) > 1 else None
    n = len(lanes)
    offs = [8.0, 38.0, 66.0]
    seg_w = 26.0
    laneshtml = ""
    for i in range(n):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        left = offs[i] if i < len(offs) else (8.0 + i * 28.0)
        header = ('<div class="on-media" style="flex:0 0 190px;background:' + col
                  + ';border-radius:6px;padding:0 20px;display:flex;align-items:center;min-height:74px">'
                  + blk(lanes[i], "div", "no-caps", "font-weight:900;font-size:18px") + '</div>')
        seg = ('<div style="position:absolute;top:14px;bottom:14px;left:' + ("%.1f" % left) + '%;width:' + ("%.1f" % seg_w)
               + '%;background:' + col + ';opacity:0.9;border-radius:6px"></div>')
        track = ('<div style="flex:1;position:relative;background:var(--sb-border-subtle);border-radius:6px;'
                 'min-height:74px;margin-left:16px">' + seg + '</div>')
        laneshtml += '<div class="reveal" style="display:flex;align-items:stretch;margin:8px 0">' + header + track + '</div>'
    calls = ""
    if handoff:
        calls += ('<div class="reveal sb-card" style="flex:1;padding:20px 24px;border-left:5px solid ' + ACC + '">'
                  + blk(handoff, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    if bottleneck:
        calls += ('<div class="reveal sb-card" style="flex:1;padding:20px 24px;border-left:5px solid var(--sb-copper)">'
                  + blk(bottleneck, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    callhtml = '<div style="display:flex;gap:20px;margin-top:18px">' + calls + '</div>' if calls else ""
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:10px">'
             + laneshtml + callhtml + '</div>')
    return inner, 64

def journey(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stages = g.get("card_title", [])[:4]
    bodies = g.get("body", [])
    pains = bodies[0] if len(bodies) > 0 else None
    opps = bodies[1] if len(bodies) > 1 else None
    n = len(stages)
    # --- journey curve (taller, clearer) -----------------------------------
    # viewBox is 0..100 in both axes; preserveAspectRatio="none" stretches the
    # polyline horizontally, so we keep the stroke crisp with a non-scaling
    # stroke and draw the node dots as real (round) HTML elements on top rather
    # than <circle>s, which would otherwise squish into thin ellipses.
    H = 150
    ys = [30, 62, 46, 18]
    pts = []
    for i in range(max(1, n)):
        x = (100.0 / max(1, n)) * (i + 0.5)
        y = ys[i % len(ys)]
        pts.append((x, y))
    poly = " ".join(("%.1f,%.1f" % (x, y)) for x, y in pts)
    curve_svg = ('<svg viewBox="0 0 100 100" preserveAspectRatio="none" '
                 'style="position:absolute;inset:0;width:100%;height:100%;display:block">'
                 '<polyline points="' + poly + '" fill="none" stroke="' + ACC
                 + '" stroke-width="3" vector-effect="non-scaling-stroke" '
                 'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    dots = ""
    for x, y in pts:
        dots += ('<div aria-hidden="true" style="position:absolute;left:%.1f%%;top:%.1f%%;'
                 'width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%%;'
                 'background:%s;box-shadow:0 0 0 6px rgba(6,12,26,0.10),'
                 '0 4px 12px rgba(6,12,26,0.35)"></div>') % (x, y, ACC)
    curve = ('<div class="reveal" style="position:relative;width:100%;height:'
             + str(H) + 'px;margin-bottom:10px">' + curve_svg + dots + '</div>')
    # --- stage badges (enlarged circles) -----------------------------------
    cards = ""
    for i in range(n):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        cards += ('<div class="reveal-scale sb-card" style="flex:1;padding:24px 20px;text-align:center;border-top:6px solid ' + col + '">'
                  + '<div class="on-media" style="width:52px;height:52px;border-radius:50%;background:' + col
                  + ';display:flex;align-items:center;justify-content:center;font-weight:900;font-size:24px;margin:0 auto 14px">' + str(i + 1) + '</div>'
                  + blk(stages[i], "div", "no-caps", "font-weight:800;font-size:18px;color:var(--sb-text-on-dark)") + '</div>')
    stagerow = '<div style="display:flex;gap:22px;align-items:stretch">' + cards + '</div>'
    # --- optional pains / opportunities bands -------------------------------
    bands = ""
    if pains:
        bands += ('<div class="reveal sb-card" style="flex:1;padding:20px 26px;border-left:6px solid var(--sb-copper)">'
                  + blk(pains, "div", "", "font-size:15px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    if opps:
        bands += ('<div class="reveal sb-card" style="flex:1;padding:20px 26px;border-left:6px solid ' + ACC + '">'
                  + blk(opps, "div", "", "font-size:15px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    bandhtml = '<div style="display:flex;gap:20px;margin-top:20px">' + bands + '</div>' if bands else ""
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:16px">'
             + curve + stagerow + bandhtml + '</div>')
    return inner, 64

def capability(s, acc):
    g = grp(s)
    head = _headline_block(g)
    caps = g.get("card_title", [])
    bodies = g.get("body", [])
    gap = bodies[0] if len(bodies) > 0 else None
    owner = bodies[1] if len(bodies) > 1 else None
    ic = icons_of(s)
    cells = ""
    for i, c in enumerate(caps):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        head_ic = (icon(ic[i], 32) + '<div style="height:10px"></div>') if i < len(ic) else ""
        cells += ('<div class="reveal-scale sb-card" style="padding:24px 24px;border-top:5px solid ' + col + '">'
                  + head_ic
                  + blk(c, "div", "no-caps", "font-weight:800;font-size:19px;color:var(--sb-text-on-dark);margin-bottom:14px")
                  + '<div style="height:8px;border-radius:6px;background:var(--sb-border-subtle);overflow:hidden">'
                  + '<div style="height:100%;width:100%;background:' + col + ';border-radius:6px"></div></div></div>')
    ncols = len(caps) if 0 < len(caps) <= 4 else (4 if len(caps) > 4 else 1)
    grid = ('<div style="display:grid;grid-template-columns:' + ("1fr " * max(1, ncols)) + ';gap:20px">' + cells + '</div>')
    ecells = ""
    if gap:
        ecells += ('<div class="reveal sb-card" style="flex:1;padding:20px 24px;border:2px dashed var(--sb-copper)">'
                   + blk(gap, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    if owner:
        ecells += ('<div class="reveal sb-card" style="flex:1;padding:20px 24px;border-left:5px solid ' + ACC + '">'
                   + blk(owner, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    extra = ('<div style="display:flex;gap:20px;margin-top:20px">' + ecells + '</div>') if ecells else ""
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:12px">'
             + grid + extra + '</div>')
    return inner, 64

def opmodel(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    stat = _first(g, "stat")
    sl = _first(g, "stat_label")
    ic = icons_of(s)
    n = len(bodies)
    # Even grid: one row when we can, no dangling cell. Featured stat lives
    # in its own full-width band, so the component grid stays balanced.
    cols = n if n <= 4 else (3 if n <= 6 else 4)
    cells = ""
    for i, b in enumerate(bodies):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        head_ic = (icon(ic[i], 32) + '<div style="height:12px"></div>') if i < len(ic) else ""
        cells += ('<div class="reveal-scale sb-card" style="padding:26px 26px;display:flex;flex-direction:column;border-top:5px solid ' + col + '">'
                  + head_ic
                  + blk(b, "div", "", "font-size:16px;line-height:1.55;color:var(--sb-text-on-dark)") + '</div>')
    grid = ""
    if cells:
        grid = ('<div style="display:grid;grid-template-columns:' + ("1fr " * cols).strip()
                + ';gap:22px;width:100%;align-items:stretch">' + cells + '</div>')
    statband = ""
    if stat:
        divider_label = ""
        if sl:
            divider_label = ('<div aria-hidden="true" style="width:2px;height:64px;background:rgba(255,255,255,0.35);flex:none"></div>'
                             + blk(sl, "div", "", "font-size:18px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;line-height:1.35;max-width:340px;opacity:0.92"))
        statband = ('<div class="reveal-scale on-media" style="background:' + ACC
                    + ';border-radius:6px;padding:36px 52px;display:flex;align-items:center;justify-content:center;gap:40px;flex-wrap:wrap;text-align:center">'
                    + blk(stat, "div", "", "font-size:82px;font-weight:900;line-height:0.95")
                    + divider_label
                    + '</div>')
    if statband and grid:
        stack = statband + '<div style="height:26px"></div>' + grid
    else:
        stack = statband + grid
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:14px">'
             + stack + '</div>')
    return inner, 64

def org(s, acc):
    g = grp(s)
    head = _headline_block(g)
    funcs = g.get("card_title", [])[:3]
    bodies = g.get("body", [])
    leader = bodies[0] if len(bodies) > 0 else None
    roles = bodies[1] if len(bodies) > 1 else None
    gaps = bodies[2] if len(bodies) > 2 else None
    n = len(funcs)
    leadbox = ('<div class="reveal on-media" style="max-width:460px;margin:0 auto;background:var(--sb-navy);border-radius:6px;padding:22px 30px;text-align:center">'
               + (blk(leader, "div", "", "font-size:17px;font-weight:800;line-height:1.4") if leader else "") + '</div>')
    connector = '<div style="display:flex;justify-content:center"><div style="width:3px;height:26px;background:var(--sb-border-subtle)"></div></div>'
    fcells = ""
    for i in range(n):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        fcells += ('<div class="reveal-scale sb-card" style="flex:1;padding:20px 20px;text-align:center;border-top:5px solid ' + col + '">'
                   + blk(funcs[i], "div", "no-caps", "font-weight:800;font-size:18px;color:var(--sb-text-on-dark)") + '</div>')
    frow = '<div style="display:flex;gap:24px;align-items:stretch">' + fcells + '</div>'
    rolehtml = ""
    if roles:
        rolehtml = ('<div class="reveal sb-card" style="padding:18px 24px;margin-top:18px;border-left:5px solid ' + ACC + '">'
                    + blk(roles, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    gaphtml = ""
    if gaps:
        gaphtml = ('<div class="reveal sb-card" style="padding:16px 24px;margin-top:14px;border:2px dashed var(--sb-copper)">'
                   + blk(gaps, "div", "", "font-size:14px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:10px">'
             + leadbox + connector + frow + rolehtml + gaphtml + '</div>')
    return inner, 64

def architecture(s, acc):
    g = grp(s)
    head = _headline_block(g)
    bodies = g.get("body", [])
    flow = bodies[:4]
    controls = bodies[4] if len(bodies) > 4 else None
    ic = icons_of(s)
    chev = ('<div style="flex:0 0 30px;display:flex;align-items:center;justify-content:center">'
            '<div style="width:15px;height:15px;border-top:4px solid ' + ACC + ';border-right:4px solid ' + ACC
            + ';transform:rotate(45deg);opacity:0.55"></div></div>')
    cards = ""
    for i, b in enumerate(flow):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        head_ic = (icon(ic[i], 30) + '<div style="height:10px"></div>') if i < len(ic) else ""
        badge = ('<span class="on-media" style="flex:none;width:30px;height:30px;border-radius:6px;background:' + col
                 + ';display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px;margin-bottom:12px">' + str(i + 1) + '</span>')
        cards += ('<div class="reveal sb-card" style="flex:1;padding:24px 22px;border-top:5px solid ' + col + '">'
                  + head_ic + badge
                  + blk(b, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
        if i < len(flow) - 1:
            cards += chev
    flowrow = '<div style="display:flex;gap:6px;align-items:stretch">' + cards + '</div>'
    ctrl = ""
    if controls:
        ctrl = ('<div class="reveal sb-card" style="margin-top:20px;padding:20px 26px;border-left:5px solid var(--sb-copper);display:flex;align-items:center;gap:14px">'
                + (icon(ic[len(flow)], 26) if len(ic) > len(flow) else "")
                + blk(controls, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;margin-top:14px">'
             + flowrow + ctrl + '</div>')
    return inner, 64

def stage_logo_map(s, acc):
    g = grp(s)
    head = _headline_block(g)
    stages = g.get("card_title", [])[:5]
    descs = g.get("card_body", [])
    items = g.get("list_item", [])
    n = len(stages)
    if n == 0:
        return _fallback(s, acc)
    # every stage gets a paired description tile BENEATH it (card_body by index);
    # any list_item blocks are distributed round-robin as extra tool chips.
    chip_groups = [[] for _ in range(n)]
    for idx, t in enumerate(items):
        chip_groups[idx % n].append(t)
    ladder = ["var(--sb-navy)", "var(--sb-steel)", "var(--sb-sky)", "var(--sb-copper)", "var(--sb-pink)"]
    cols = ""
    for i in range(n):
        col = ladder[i % len(ladder)]
        if i == 0:
            clip = "polygon(0 0, calc(100% - 20px) 0, 100% 50%, calc(100% - 20px) 100%, 0 100%)"
        else:
            clip = "polygon(0 0, calc(100% - 20px) 0, 100% 50%, calc(100% - 20px) 100%, 0 100%, 20px 50%)"
        chevron = ('<div class="on-media" style="background:%s;min-height:60px;display:flex;align-items:center;'
                   'justify-content:center;text-align:center;padding:0 22px;clip-path:%s">' % (col, clip)
                   + blk(stages[i], "div", "no-caps", "font-weight:900;font-size:16px") + '</div>')
        # description text box beneath every stage
        desc_tile = ""
        if i < len(descs):
            desc_tile = ('<div class="reveal sb-card" style="flex:1;padding:16px 18px;display:flex;align-items:center">'
                         + blk(descs[i], "div", "", "font-size:14px;line-height:1.5;color:var(--sb-body-on-dark)") + '</div>')
        # optional tool chips from list_item blocks
        chips = ""
        for j, t in enumerate(chip_groups[i]):
            dot = ACCENT_CYCLE[(i + j) % len(ACCENT_CYCLE)]
            chips += ('<div class="reveal sb-card" style="display:flex;align-items:center;gap:10px;padding:10px 14px">'
                      '<span style="flex:none;width:12px;height:12px;border-radius:50%%;background:%s"></span>' % dot
                      + blk(t, "div", "no-caps", "font-size:13px;font-weight:700;color:var(--sb-text-on-dark)") + '</div>')
        chip_wrap = ('<div style="display:flex;flex-direction:column;gap:8px">' + chips + '</div>') if chips else ""
        cols += ('<div style="flex:1;display:flex;flex-direction:column;gap:12px">'
                 + chevron + desc_tile + chip_wrap + '</div>')
    inner = (blk(head, "h2", "hl reveal", "font-size:42px;margin:0 0 6px") + rule("6px")
             + '<div style="flex:1;display:flex;gap:14px;align-items:stretch;margin-top:18px">' + cols + '</div>')
    return inner, 64

def exercise(s, acc):
    g = grp(s)
    ic = icons_of(s)
    label = _first(g, "label")
    debrief = _first(g, "headline")
    instr = _first(g, "caption")
    bodies = g.get("body", [])
    objective = bodies[0] if len(bodies) > 0 else None
    participant = bodies[1] if len(bodies) > 1 else None
    timer = bodies[2] if len(bodies) > 2 else None
    left = ""
    if label:
        left += blk(label, "div", "label reveal", "margin-bottom:14px")
    if objective:
        left += blk(objective, "h2", "hl reveal-left", "font-size:38px;line-height:1.18;margin:0")
    left += rule("18px")
    if instr:
        left += blk(instr, "div", "reveal", "font-size:17px;line-height:1.55;color:var(--sb-body-on-dark);margin-top:20px;max-width:460px")
    if timer:
        tchip = icon(ic[0], 26) if ic else ""
        tchip += blk(timer, "div", "no-caps", "font-weight:800;font-size:18px;color:var(--sb-text-on-dark)")
        left += ('<div class="reveal sb-card" style="display:inline-flex;align-items:center;gap:12px;padding:14px 22px;margin-top:28px">'
                 + tchip + '</div>')
    right = ""
    if participant:
        right += p_accent_box(blk(participant, "div", "", "font-size:21px;font-weight:700;line-height:1.4"),
                              "min-height:200px;display:flex;align-items:center")
    if debrief:
        right += ('<div class="reveal sb-card" style="margin-top:22px;padding:26px 30px;border-left:6px solid ' + ACC + '">'
                  + blk(debrief, "div", "no-caps", "font-weight:800;font-size:24px;color:var(--sb-text-on-dark);line-height:1.3")
                  + '</div>')
    return p_split(left, right, lflex="1", rflex="1", gap=44), 64

def sticky(s, acc):
    g = grp(s)
    synth = _first(g, "headline")
    bodies = g.get("body", [])
    # Up to 4 sticky-note themes; a trailing body (only if it would be a lonely
    # 4th) becomes the votes tally band beneath the notes.
    if len(bodies) > 3:
        themes = bodies[:3]
        votes = bodies[3]
    else:
        themes = bodies
        votes = None
    n = max(1, len(themes))
    cols = min(n, 3)
    inner = ""
    if synth:
        inner += blk(synth, "h2", "hl reveal", "font-size:46px;text-align:center;margin:0 0 8px")
        inner += '<div style="display:flex;justify-content:center">' + rule("8px") + '</div>'
    rot = ["-1.5deg", "1deg", "-0.75deg", "1.25deg"]
    # Taller, larger sticky notes that genuinely fill the row.
    card_min = 340 if synth else 400
    cells = ""
    for i, t in enumerate(themes):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        num = ('<div aria-hidden="true" style="width:52px;height:52px;border-radius:6px;background:%s;'
               'display:flex;align-items:center;justify-content:center;font-weight:900;font-size:24px;'
               'color:var(--sb-text-on-dark);margin-bottom:22px">%d</div>' % (col, i + 1))
        cells += ('<div class="reveal-scale sb-card" style="min-height:%dpx;padding:40px 38px;'
                  'border-top:8px solid %s;transform:rotate(%s);display:flex;flex-direction:column;'
                  'justify-content:flex-start">' % (card_min, col, rot[i % 4])
                  + num
                  + blk(t, "div", "", "font-size:26px;line-height:1.45;font-weight:600;color:var(--sb-text-on-dark)")
                  + '</div>')
    grid = ('<div style="display:grid;grid-template-columns:%s;gap:32px;width:100%%;align-items:stretch">'
            % ("1fr " * cols) + cells + '</div>')
    votes_band = ""
    if votes:
        votes_band = ('<div class="reveal" style="margin-top:34px;display:flex;justify-content:center">'
                      + '<div class="sb-card" style="display:inline-block;padding:24px 44px;text-align:center">'
                      + blk(votes, "div", "no-caps", "font-weight:800;font-size:24px;color:var(--sb-text-on-dark)")
                      + '</div></div>')
    inner += ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:8px">'
              + grid + votes_band + '</div>')
    return inner, 64

def readout(s, acc):
    g = grp(s)
    ic = icons_of(s)
    bodies = g.get("body", [])
    objectives = bodies[0] if len(bodies) > 0 else None
    decisions = bodies[1] if len(bodies) > 1 else None
    owners = bodies[2] if len(bodies) > 2 else None
    open_q = _first(g, "headline")
    steps = g.get("list_item", [])
    quad = [(objectives, False), (decisions, False), (open_q, True), (owners, False)]
    cells = ""
    idx = 0
    for b, hl in quad:
        if not b:
            continue
        col = ACCENT_CYCLE[idx % len(ACCENT_CYCLE)]
        head = (icon(ic[idx], 30) + '<div style="height:12px"></div>') if idx < len(ic) else ""
        border = ("border:2px solid " + ACC + ";") if hl else ("border-top:5px solid " + col + ";")
        cells += ('<div class="reveal sb-card" style="' + border + 'padding:24px 26px">'
                  + head
                  + blk(b, "div", "", "font-size:17px;line-height:1.5;color:var(--sb-text-on-dark)")
                  + '</div>')
        idx += 1
    grid = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">' + cells + '</div>'
    steps_html = ""
    if steps:
        steps_html = '<div style="margin-top:22px">' + p_list(steps, numbered=True, size=17) + '</div>'
    return grid + steps_html, 64

def docmock(s, acc):
    g = grp(s)
    titles = g.get("card_title", [])
    ctx_t = titles[0] if len(titles) > 0 else None
    prompt_t = titles[1] if len(titles) > 1 else None
    excerpt = _first(g, "caption")
    bodies = g.get("body", [])
    constraints = bodies[0] if len(bodies) > 0 else None
    example = bodies[1] if len(bodies) > 1 else None
    head = _headline_block(g)
    accent = "var(--sb-product-accent,var(--sb-sky))"

    def _sec(t, b):
        h = ""
        if t:
            h += blk(t, "div", "no-caps", "font-weight:800;font-size:19px;letter-spacing:0.04em;text-transform:uppercase;color:" + accent + ";margin-bottom:10px")
        if b:
            h += blk(b, "div", "", "font-size:17px;line-height:1.6;color:var(--sb-text-on-dark)")
        return h
    sec1 = _sec(ctx_t, constraints)
    sec2 = _sec(prompt_t, example)
    doc = ('<div class="reveal sb-card" style="max-width:860px;margin:0 auto;padding:40px 48px;border-left:6px solid ' + ACC + '">'
           + sec1
           + ('<div style="height:1px;background:var(--sb-border-subtle);margin:26px 0"></div>' if (sec1 and sec2) else "")
           + sec2
           + (('<div style="margin-top:24px">'
              + blk(excerpt, "div", "", "font-size:14px;font-style:italic;color:var(--sb-body-on-dark)")
              + '</div>') if excerpt else "")
           + '</div>')
    inner = ""
    if head:
        inner += blk(head, "h2", "hl reveal", "font-size:40px;text-align:center;margin:0 0 22px")
    inner += doc
    return inner, 64

def about_bio(s, acc):
    g = grp(s)
    about = _first(g, "card_body")
    stats = g.get("stat", [])
    slabels = g.get("stat_label", [])
    name_role = _first(g, "body")
    creds = g.get("list_item", [])
    label = _first(g, "label")
    left = ""
    if label:
        left += blk(label, "div", "label reveal", "margin-bottom:14px")
    if about:
        left += blk(about, "div", "reveal-left", "font-size:20px;line-height:1.6;color:var(--sb-text-on-dark);max-width:480px")
    if stats:
        tiles = ""
        for i, st in enumerate(stats):
            tiles += ('<div style="flex:1">'
                      + blk(st, "div", "kpi-num", "font-size:54px")
                      + (blk(slabels[i], "div", "kpi-label", "margin-top:6px;font-size:13px;color:var(--sb-body-on-dark)") if i < len(slabels) else "")
                      + '</div>')
        left += '<div class="reveal" style="display:flex;gap:24px;margin-top:34px">' + tiles + '</div>'
    right = ""
    if name_role:
        right += blk(name_role, "div", "no-caps", "font-weight:800;font-size:26px;color:var(--sb-title);margin-bottom:12px")
    if creds:
        right += p_list(creds, size=17)
    right = '<div style="border-left:2px solid var(--sb-border-subtle);padding-left:40px">' + right + '</div>'
    body = p_split(left, right, lflex="1.2", rflex="1", gap=48, align="center")
    # Photo sliver: WT-05's signature is a full-height photo strip on the left
    # (company/context). Only rendered when the slide actually carries an image
    # so a slot never ships empty.
    if has_image(s):
        sliver = ('<div class="reveal-left" style="flex:0 0 300px;border-radius:6px;overflow:hidden;'
                  'align-self:stretch"><img data-image="%s" class="img-cover"></div>' % img_tag(s))
        inner = ('<div style="display:flex;gap:40px;height:100%;align-items:stretch">' + sliver
                 + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">' + body + '</div></div>')
        return inner, 64
    return body, 64

def prompt_anatomy(s, acc):
    g = grp(s)
    quote = _first(g, "quote")
    role = _first(g, "card_body")
    context = _first(g, "caption")
    constraint = _first(g, "body")
    task = _first(g, "cta")
    # LEFT cell: the raw prompt, distributed to fill the full cell height
    left_inner = (
        qmark(True, 108, ACC)
        + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:12px 0">'
        + (blk(quote, "div", "no-caps", "font-size:25px;font-weight:600;line-height:1.5;color:var(--sb-body-on-dark)") if quote else "")
        + qmark(False, 108, ACC, align="right")
        + '</div>'
        + '<div style="width:96px;height:6px;border-radius:6px;background:' + ACC + '"></div>'
    )
    left = ('<div class="reveal-left sb-card" style="flex:1;padding:40px 42px;display:flex;flex-direction:column;justify-content:space-between">'
            + left_inner + '</div>')
    # RIGHT cell: anatomy of the prompt, distributed top / middle / bottom to fill the cell
    top = ""
    if role:
        top = blk(role, "div", "no-caps", "font-weight:800;font-size:22px;line-height:1.3;color:var(--sb-text-on-dark)")
    mid = ""
    for i, b in enumerate([context, constraint]):
        if not b:
            continue
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        mid += ('<div style="border-left:6px solid ' + col + ';padding:10px 0 10px 22px">'
                + blk(b, "div", "", "font-size:17px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')
    bottom = ""
    if task:
        bottom = blk(task, "div", "cta-btn no-caps", "font-size:17px")
    # space-between distributes free space AS the gap between heading / leads / CTA,
    # so the CTA always has breathing room above it AND stays inside the card
    # (margin-top:auto could push it past the bottom border once a title shrinks
    # the card). Sizes above are tuned so heading + 2 leads + CTA fit the panel.
    parts = (
        '<div>' + top + '</div>'
        + '<div style="display:flex;flex-direction:column;gap:16px">' + mid + '</div>'
        + ('<div>' + bottom + '</div>' if bottom else '<div></div>')
    )
    right = ('<div class="reveal-right sb-card" style="flex:1;padding:36px 40px;border:2px solid ' + ACC + ';display:flex;flex-direction:column;justify-content:space-between">'
             + parts + '</div>')
    # Optional slide title (context header) above the two panels.
    head = _headline_block(g)
    title = blk(head, "h2", "hl reveal", "font-size:34px;margin:0 0 14px") if head else ""
    inner = title + '<div style="flex:1;display:flex;gap:32px;align-items:stretch;min-height:0">' + left + right + '</div>'
    return inner, 64

def poll(s, acc):
    g = grp(s)
    ic = icons_of(s)
    question = _first(g, "headline")
    instr = _first(g, "caption")
    notice = _first(g, "card_title")
    tile = ""
    if ic:
        tile = ('<div class="reveal-scale sb-card" style="width:120px;height:120px;display:flex;align-items:center;justify-content:center;margin:0 auto 30px">'
                + icon(ic[0], 52) + '</div>')
    center = ('<div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:60px 72px 40px">'
              + tile
              + (blk(question, "h2", "hl reveal", "font-size:60px;line-height:1.1;margin:0;max-width:1000px") if question else "")
              + (blk(instr, "div", "reveal", "font-size:20px;color:var(--sb-body-on-dark);margin-top:24px") if instr else "")
              + '</div>')
    band = ""
    if notice:
        band = ('<div class="reveal on-media" style="background:' + ACC + ';padding:26px 72px;display:flex;align-items:center;justify-content:center">'
                + blk(notice, "div", "no-caps", "font-weight:800;font-size:20px") + '</div>')
    inner = '<div style="height:100%;display:flex;flex-direction:column">' + center + band + '</div>'
    return inner, 0

def rules_photo(s, acc):
    g = grp(s)
    ic = icons_of(s)
    rules = g.get("card_title", [])
    expl = g.get("card_body", [])
    n = min(len(rules), len(expl)) if expl else len(rules)
    cells = ""
    for i in range(n):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        head = ""
        if i < len(ic):
            head = ('<div class="sb-card" style="width:78px;height:78px;display:flex;align-items:center;justify-content:center;margin-bottom:18px;border-top:4px solid ' + col + '">'
                    + icon(ic[i], 34) + '</div>')
        cells += ('<div class="reveal-scale sb-card" style="flex:1;padding:30px 28px;border-top:5px solid ' + col + '">'
                  + head
                  + blk(rules[i], "div", "no-caps", "font-weight:900;font-size:21px;color:var(--sb-text-on-dark);margin-bottom:12px;line-height:1.25")
                  + (blk(expl[i], "div", "", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark)") if i < len(expl) else "")
                  + '</div>')
    cards = '<div style="flex:1;display:flex;gap:22px;align-items:stretch">' + cells + '</div>'
    head_b = _headline_block(g)
    heading = blk(head_b, "h2", "hl reveal", "font-size:38px;margin:0 0 20px") if head_b else ""
    if has_image(s):
        rail = ('<div class="reveal-left" style="flex:0 0 300px;border-radius:6px;overflow:hidden">'
                '<img data-image="' + (img_tag(s) or "workshop") + '" class="img-cover" style="height:100%"></div>')
        body = ('<div style="display:flex;gap:34px;height:100%;align-items:stretch">' + rail
                + '<div style="flex:1;display:flex;flex-direction:column">' + heading + cards + '</div></div>')
        return body, 64
    inner = heading + '<div style="flex:1;display:flex;align-items:center">' + cards + '</div>'
    return inner, 64

def icon_trio(s, acc):
    g = grp(s)
    ic = icons_of(s)
    heads = g.get("body", [])
    expl = g.get("card_body", [])
    head_b = _headline_block(g)
    n = max(len(heads), len(expl), len(ic))
    n = min(n, 3) if n else 0
    cols = ""
    for i in range(n):
        circle_icon = icon(ic[i], 42) if i < len(ic) else ""
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        circle = ('<div style="width:130px;height:130px;border-radius:50%;border:3px solid ' + col
                  + ';display:flex;align-items:center;justify-content:center;margin:0 auto 22px;flex:none">' + circle_icon + '</div>')
        h = blk(heads[i], "div", "no-caps", "font-weight:800;font-size:22px;color:var(--sb-text-on-dark);margin-bottom:12px") if i < len(heads) else ""
        e = blk(expl[i], "div", "", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark)") if i < len(expl) else ""
        # Equal-height card: circle pinned near top, text region grows to fill,
        # so all three cards share the same height with no ragged empty space.
        cols += ('<div class="sb-card reveal-scale" style="flex:1;display:flex;flex-direction:column;'
                 'align-items:center;text-align:center;padding:40px 28px;box-sizing:border-box">'
                 + circle
                 + '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
                 + h + e + '</div></div>')
    row = ('<div style="display:flex;gap:24px;align-items:stretch;justify-content:center;width:100%;height:100%">'
           + cols + '</div>')
    inner = ""
    if head_b:
        inner += blk(head_b, "h2", "hl reveal", "font-size:40px;text-align:center;margin:0 0 6px")
        inner += '<div style="display:flex;justify-content:center">' + rule("6px") + '</div>'
    inner += '<div style="flex:1;display:flex;align-items:stretch;margin-top:28px">' + row + '</div>'
    return inner, 64

def doc_response(s, acc):
    g = grp(s)
    subject = _first(g, "body")
    paras = g.get("card_body", [])
    head_b = _headline_block(g)
    doc = ""
    if subject:
        doc += blk(subject, "div", "no-caps", "font-weight:800;font-size:22px;color:var(--sb-title);margin-bottom:18px;line-height:1.3")
    for p in paras:
        doc += blk(p, "div", "", "font-size:16px;line-height:1.65;color:var(--sb-text-on-dark);margin-bottom:14px")
    left = ('<div class="reveal-left sb-card" style="padding:38px 40px;border-left:6px solid ' + ACC + ';height:100%;box-sizing:border-box">' + doc + '</div>')
    if has_image(s):
        right = p_media(img_tag(s), h=440)
    else:
        skel = ""
        for w in ["96%", "100%", "90%", "94%", "82%", "100%", "88%"]:
            skel += '<div style="height:8px;border-radius:6px;background:var(--sb-border-subtle);width:' + w + ';margin:14px 0"></div>'
        right = ('<div class="reveal-right sb-card" style="padding:34px 36px;height:100%;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center">'
                 + '<div style="width:44px;height:8px;border-radius:6px;background:' + ACC + ';margin-bottom:22px"></div>'
                 + skel + '</div>')
    inner_split = p_split(left, right, lflex="1.25", rflex="1", gap=40, align="stretch")
    if head_b:
        heading = blk(head_b, "h2", "hl reveal", "font-size:38px;margin:0 0 20px")
        return heading + '<div style="flex:1">' + inner_split + '</div>', 64
    return inner_split, 64

def doc_infographic(s, acc):
    g = grp(s)
    sections = g.get("card_title", [])
    steps = g.get("list_item", [])
    outcome = _first(g, "card_body")
    head_b = _headline_block(g)
    accent = "var(--sb-product-accent,var(--sb-sky))"
    sec_html = ""
    for t in sections:
        sec_html += ('<div style="margin-bottom:22px">'
                     + blk(t, "div", "no-caps", "font-weight:800;font-size:16px;letter-spacing:0.04em;text-transform:uppercase;color:" + accent + ";margin-bottom:10px")
                     + '<div style="height:6px;border-radius:6px;background:var(--sb-border-subtle);width:100%;margin-bottom:8px"></div>'
                     + '<div style="height:6px;border-radius:6px;background:var(--sb-border-subtle);width:82%"></div>'
                     + '</div>')
    left = '<div class="reveal-left sb-card" style="flex:1;padding:34px 36px">' + sec_html + '</div>'
    chips = ""
    n = len(steps)
    for i, st in enumerate(steps):
        col = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
        chips += ('<div class="sb-card" style="padding:16px 20px;border-left:4px solid ' + col + '">'
                  + blk(st, "div", "no-caps", "font-weight:700;font-size:16px;color:var(--sb-text-on-dark)") + '</div>')
        if i < n - 1:
            chips += ('<div style="display:flex;justify-content:center;padding:2px 0">'
                      '<div style="width:12px;height:12px;border-right:3px solid ' + ACC + ';border-bottom:3px solid ' + ACC + ';transform:rotate(45deg);opacity:0.6"></div></div>')
    flow = '<div style="display:flex;flex-direction:column;gap:0">' + chips + '</div>'
    outcome_band = ""
    if outcome:
        outcome_band = p_accent_box(blk(outcome, "div", "no-caps", "font-weight:800;font-size:18px;text-align:center;line-height:1.4"), "margin-top:22px;padding:22px")
    right = ('<div class="reveal-right sb-card" style="flex:1;padding:30px 32px;display:flex;flex-direction:column;justify-content:center">' + flow + outcome_band + '</div>')
    split = '<div style="display:flex;gap:34px;height:100%;align-items:stretch">' + left + right + '</div>'
    if head_b:
        return blk(head_b, "h2", "hl reveal", "font-size:38px;margin:0 0 20px") + '<div style="flex:1">' + split + '</div>', 64
    return split, 64

def context_brief(s, acc):
    g = grp(s)
    bullets = g.get("list_item", [])
    bodies = g.get("body", [])
    prompt = bodies[0] if bodies else None
    briefs = bodies[1:] if len(bodies) > 1 else []
    head_b = _headline_block(g)
    left = ""
    if bullets:
        left += p_list(bullets, size=17)
    if prompt:
        left += ('<div class="reveal sb-card" style="margin-top:22px;padding:20px 24px;border-left:6px solid ' + ACC + '">'
                 + blk(prompt, "div", "no-caps", "font-size:17px;line-height:1.5;color:var(--sb-text-on-dark);font-weight:600") + '</div>')
    doc = ""
    for b in briefs:
        doc += blk(b, "div", "", "font-size:16px;line-height:1.7;color:var(--sb-text-on-dark);margin-bottom:14px")
    skel = ""
    for w in ["100%", "94%", "97%", "88%", "92%"]:
        skel += '<div style="height:7px;border-radius:6px;background:var(--sb-border-subtle);width:' + w + ';margin:12px 0"></div>'
    right = '<div class="reveal-right sb-card" style="flex:1;padding:34px 38px">' + doc + skel + '</div>'
    left_wrap = '<div style="flex:0 0 40%;display:flex;flex-direction:column;justify-content:center">' + left + '</div>'
    split = '<div style="display:flex;gap:38px;height:100%;align-items:stretch">' + left_wrap + right + '</div>'
    if head_b:
        return blk(head_b, "h2", "hl reveal", "font-size:38px;margin:0 0 20px") + '<div style="flex:1">' + split + '</div>', 64
    return split, 64

def blank(s, acc):
    g = grp(s)
    head = _headline_block(g)
    titles = g.get("card_title", [])
    bodies = g.get("card_body", []) or g.get("body", [])
    foot = _first(g, "caption")
    ic = icons_of(s)
    n = max(len(titles), len(bodies))
    cards = ""
    for i in range(n):
        t = titles[i] if i < len(titles) else None
        b = bodies[i] if i < len(bodies) else None
        head_ic = (icon(ic[i], 34) + '<div style="height:12px"></div>') if i < len(ic) else ""
        cards += ('<div class="reveal-scale sb-card" style="flex:1;padding:28px 26px">'
                  + head_ic
                  + (blk(t, "div", "no-caps", "font-weight:900;font-size:22px;color:var(--sb-text-on-dark);margin-bottom:10px") if t else "")
                  + (blk(b, "div", "", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark)") if b else "")
                  + '</div>')
    inner = blk(head, "h2", "hl reveal", "font-size:44px;margin:0 0 6px") + rule("6px")
    if cards:
        inner += ('<div style="flex:1;display:flex;align-items:center">'
                  '<div style="display:flex;gap:22px;width:100%%;align-items:stretch">%s</div></div>' % cards)
    if foot:
        inner += blk(foot, "div", "reveal", "font-size:13px;letter-spacing:0.12em;text-transform:uppercase;color:var(--sb-body-on-dark);margin-top:18px;opacity:0.8")
    return inner, 64

def source_page(s, acc):
    g = grp(s)
    head = _headline_block(g)
    caps = g.get("caption", [])
    why = _first(g, "body")
    excerpt = caps[0] if len(caps) > 0 else None
    meta = caps[1:] if len(caps) > 1 else []
    top = ""
    if head:
        top = blk(head, "h2", "hl reveal", "font-size:42px;margin:0 0 6px") + rule("6px")
    left = ""
    if excerpt:
        left += ('<div class="reveal-left sb-card" style="border-left:6px solid %s;padding:24px 28px">' % ACC
                 + blk(excerpt, "div", "no-caps", "font-size:21px;line-height:1.5;font-weight:600;color:var(--sb-text-on-dark)")
                 + '</div>')
    if meta:
        rows = ""
        for b in meta:
            rows += ('<div style="display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-top:1px solid var(--sb-border-subtle)">'
                     '<span style="flex:none;width:8px;height:8px;border-radius:50%%;background:%s;margin-top:7px"></span>' % ACC
                     + blk(b, "div", "", "font-size:16px;line-height:1.5;color:var(--sb-body-on-dark)") + '</div>')
        left += '<div class="reveal" style="margin-top:16px">%s</div>' % rows
    right = ""
    if why:
        right = p_accent_box(blk(why, "div", "", "font-size:20px;line-height:1.55;font-weight:600"))
    body = ""
    if left or right:
        body = p_split(left, right, lflex="1.4", rflex="1", gap=40, align="stretch")
    inner = top + '<div style="flex:1;display:flex;align-items:center;margin-top:22px">%s</div>' % body
    return inner, 64

def gradient_divider(s, acc):
    g = grp(s)
    head = _headline_block(g)
    sub = _first(g, "subhead")
    grad = '<div style="position:absolute;inset:0;background:linear-gradient(120deg,var(--sb-navy) 0%,var(--sb-steel) 100%)"></div>'
    wash = ('<div style="position:absolute;right:-60px;top:-80px;width:520px;height:520px;border-radius:50%;'
            'background:radial-gradient(circle,var(--sb-product-accent,var(--sb-sky)) 0%,rgba(255,255,255,0) 70%);'
            'opacity:0.22;pointer-events:none;z-index:1"></div>')
    title_html = ""
    if head:
        title_html = blk(head, "h2", "hl reveal-left", "font-size:56px;margin:0")
        if sub:
            title_html += blk(sub, "div", "reveal", "font-size:18px;font-weight:600;margin-top:14px;opacity:0.85")
    inner = (grad + wash + logo_mark()
             + '<div class="on-media" style="position:absolute;left:64px;bottom:64px;right:64px;z-index:2;max-width:900px">%s</div>' % title_html)
    return inner, 0

# ---------------------------------------------------------------------
# SMARTBUILD AI ROADMAP — deck-local renderers (Workflow -> Data -> Agent)
# ---------------------------------------------------------------------
def wf_stage(s, acc):
    """Signature Workflow -> Data -> Agent slide: kicker + headline/subhead, a
    three-step flow (System of Record -> Portfolio Repository -> System of Action),
    then EITHER a four-pillar value row (workflow slides) OR a single takeaway
    footnote (the thesis slide). Same shape every time => concept consistency."""
    g = grp(s)
    kicker = _first(g, "kicker"); head = _first(g, "headline"); sub = _first(g, "subhead")
    slabels = g.get("step_label", []); stitles = g.get("step_title", []); sbodies = g.get("step_body", [])
    ptitles = g.get("pillar_title", []); pbodies = g.get("pillar_body", [])
    vlabel = _first(g, "value_label"); foot = _first(g, "footnote")
    ic = icons_of(s)

    header = ((blk(kicker, "div", "label reveal", "color:%s;margin-bottom:10px" % ACC) if kicker else "")
              + '<div style="display:flex;align-items:baseline;gap:20px;flex-wrap:wrap">'
              + blk(head, "h2", "hl reveal-left", "font-size:34px;margin:0;line-height:1.05")
              + (blk(sub, "div", "reveal no-caps", "font-size:18px;font-weight:700;color:var(--sb-body-on-dark)") if sub else "")
              + '</div>')

    chev = chevron_connector()
    n = min(len(slabels), len(stitles), len(sbodies))
    cards = ""
    for i in range(n):
        border = "border:2px solid %s;" % ACC if i == n - 1 else ""
        cards += ('<div class="reveal sb-card" style="flex:1;%spadding:20px 22px;display:flex;flex-direction:column;gap:8px">' % border
                  + blk(slabels[i], "div", "", "font-size:12px;font-weight:800;letter-spacing:0.14em;color:%s" % ACC)
                  + blk(stitles[i], "div", "no-caps", "font-weight:900;font-size:19px;color:var(--sb-text-on-dark);line-height:1.1")
                  + blk(sbodies[i], "div", "", "font-size:14px;line-height:1.5;color:var(--sb-body-on-dark)")
                  + '</div>')
        if i < n - 1:
            cards += chev
    flow = '<div style="display:flex;gap:6px;align-items:stretch">%s</div>' % cards

    tail = ""
    if ptitles:
        cols = ""
        m = min(len(ptitles), len(pbodies))
        for i in range(m):
            cols += ('<div class="reveal" style="flex:1;display:flex;flex-direction:column;gap:8px">'
                     + (icon(ic[i], 26) if i < len(ic) else "")
                     + blk(ptitles[i], "div", "", "font-size:12px;font-weight:900;letter-spacing:0.08em;color:var(--sb-text-on-dark)")
                     + blk(pbodies[i], "div", "", "font-size:13px;line-height:1.45;color:var(--sb-body-on-dark)")
                     + '</div>')
        tail = ('<div style="border-top:1px solid var(--sb-border-subtle);padding-top:16px">'
                + (blk(vlabel, "div", "label reveal", "color:%s;margin-bottom:14px" % ACC) if vlabel else "")
                + '<div style="display:flex;gap:26px;align-items:flex-start">%s</div></div>' % cols)
    elif foot:
        tail = ('<div class="reveal sb-card" style="border-left:4px solid %s;padding:18px 22px">' % ACC
                + blk(foot, "div", "", "font-size:17px;line-height:1.5;color:var(--sb-text-on-dark)") + '</div>')

    inner = ('<div style="display:flex;flex-direction:column;gap:22px;height:100%;justify-content:center">'
             + header + flow + tail + '</div>')
    return inner, 64


def wf_contrast(s, acc):
    """Two-column contrast: 'Most AI today' (muted) vs 'The SMARTBUILD approach'
    (accent-bordered), a lead paragraph above and a pull-quote band below."""
    g = grp(s)
    kicker = _first(g, "kicker"); head = _first(g, "headline"); lead = _first(g, "lead")
    llab = _first(g, "left_label"); rlab = _first(g, "right_label")
    lbods = g.get("left_body", []); rbods = g.get("right_body", []); quote = _first(g, "quote")

    def lines(bods):
        return "".join(blk(b, "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark);margin-top:10px") for b in bods)

    left = ('<div class="reveal sb-card" style="flex:1;padding:24px 26px">'
            + blk(llab, "div", "", "font-weight:900;font-size:15px;letter-spacing:0.08em;color:var(--sb-text-secondary)")
            + lines(lbods) + '</div>')
    right = ('<div class="reveal sb-card" style="flex:1;border:2px solid %s;padding:24px 26px">' % ACC
             + blk(rlab, "div", "", "font-weight:900;font-size:15px;letter-spacing:0.08em;color:%s" % ACC)
             + lines(rbods) + '</div>')
    qband = ""
    if quote:
        qband = ('<div class="reveal" style="border-left:4px solid %s;padding:12px 24px">' % ACC
                 + blk(quote, "div", "no-caps", "font-size:19px;font-weight:800;line-height:1.4;color:var(--sb-title)") + '</div>')
    inner = ('<div style="display:flex;flex-direction:column;gap:16px;height:100%;justify-content:center">'
             + (blk(kicker, "div", "label reveal", "color:%s" % ACC) if kicker else "")
             + blk(head, "h2", "hl reveal-left", "font-size:38px;margin:0;line-height:1.05")
             + (blk(lead, "div", "reveal no-caps", "font-size:16px;line-height:1.55;color:var(--sb-body-on-dark);max-width:1010px") if lead else "")
             + '<div style="display:flex;gap:22px;align-items:stretch">%s%s</div>' % (left, right)
             + qband + '</div>')
    return inner, 64


def wf_pillars(s, acc):
    """Four-pillar value framework: kicker + headline + intro, then four icon cards
    (Productivity / Reduced Cost / Reduced Risk / Employee Experience)."""
    g = grp(s)
    kicker = _first(g, "kicker"); head = _first(g, "headline"); sub = _first(g, "subhead")
    ptitles = g.get("pillar_title", []); pbodies = g.get("pillar_body", []); ic = icons_of(s)
    cards = ""
    m = min(len(ptitles), len(pbodies))
    for i in range(m):
        cards += ('<div class="reveal-scale sb-card" style="flex:1;padding:26px 22px;display:flex;flex-direction:column;gap:12px">'
                  + (icon(ic[i], 34) if i < len(ic) else "")
                  + blk(ptitles[i], "div", "", "font-weight:900;font-size:17px;letter-spacing:0.04em;color:var(--sb-text-on-dark)")
                  + blk(pbodies[i], "div", "", "font-size:15px;line-height:1.5;color:var(--sb-body-on-dark)")
                  + '</div>')
    inner = ('<div style="display:flex;flex-direction:column;gap:20px;height:100%;justify-content:center">'
             + (blk(kicker, "div", "label reveal", "color:%s" % ACC) if kicker else "")
             + blk(head, "h2", "hl reveal", "font-size:44px;margin:0")
             + (blk(sub, "div", "reveal no-caps", "font-size:17px;line-height:1.55;color:var(--sb-body-on-dark);max-width:980px") if sub else "")
             + '<div style="display:flex;gap:20px;align-items:stretch;margin-top:6px">%s</div>' % cards
             + '</div>')
    return inner, 64


def wf_moat(s, acc):
    """Closing 'moat' statement over a photo backdrop, badge mark top-left, tagline
    on an accent rule."""
    g = grp(s)
    kicker = _first(g, "kicker"); head = _first(g, "headline"); body = _first(g, "body"); tag = _first(g, "tagline")
    photo = photo_bg(img_tag(s)) if has_image(s) else '<div style="position:absolute;inset:0;background:linear-gradient(120deg,var(--sb-navy),var(--sb-steel))"></div>'
    content = ('<div style="max-width:920px">'
               + (blk(kicker, "div", "label reveal", "color:var(--sb-product-accent,var(--sb-sky));margin-bottom:16px") if kicker else "")
               + blk(head, "h1", "reveal-hero", "font-size:62px;line-height:1.0;margin:0;font-weight:900")
               + (blk(body, "div", "reveal no-caps", "font-size:20px;line-height:1.55;margin-top:24px") if body else "")
               + (blk(tag, "div", "reveal", "font-size:22px;font-weight:800;margin-top:28px;padding-top:20px;border-top:2px solid var(--sb-product-accent,var(--sb-sky))") if tag else "")
               + '</div>')
    inner = (photo + badge_mark()
             + '<div class="on-media" style="position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;justify-content:center;padding:0 76px;box-sizing:border-box">%s</div>' % content)
    return inner, 0
# <<< EXT RENDERERS END <<<

REGISTRY = {
    "cover_geo": cover_geo, "cover_image": cover_geo, "cover_dark_photo": cover_geo,
    "closing_cta": closing_cta, "photo_closing": closing_cta, "next_steps": closing_cta,
    "photo_statement": photo_statement, "photo_quote_band": photo_statement,
    "quote_full": quote_full, "icon_list": icon_list, "feature_benefit": feature_benefit,
    "card_row": card_row, "icon_cards": card_row, "three_stats": three_stats,
    "narrative_split": narrative_split, "three_step": three_step, "field_flow": three_step,
    "versus": versus, "suite": suite, "product_family": suite,
    "product_pillar": product_pillar, "section_gradient": section_gradient, "section_minimal": section_gradient,
}

# >>> EXT REGISTRY START >>>
REGISTRY.update({
    "cover_agenda": cover_agenda,
    "section_photos": section_photos,
    "deck_shell": deck_shell,
    "cover_cobrand": cover_cobrand,
    "cover_agenda_photo": cover_agenda_photo,
    "closing_contact": closing_contact,
    "image_metric": image_metric,
    "logo_board": logo_board,
    "proof_stack": proof_stack,
    "case_study": case_study,
    "psp": psp,
    "messaging_house": messaging_house,
    "faq": faq,
    "photo_timeline": photo_timeline,
    "stat_rail": stat_rail,
    "logo_landscape": logo_landscape,
    "image_quote_pair": image_quote_pair,
    "photo_columns": photo_columns,
    "contrast_labels": contrast_labels,
    "logo_wall_quotes": logo_wall_quotes,
    "photo_collage_band": photo_collage_band,
    "photo_filmstrip": photo_filmstrip,
    "case_photo_split": case_photo_split,
    "persona_story": persona_story,
    "device_overlay": device_overlay,
    "screenshot_callouts": screenshot_callouts,
    "product_spotlight": product_spotlight,
    "phone_on_photo": phone_on_photo,
    "device_in_context": device_in_context,
    "app_showcase": app_showcase,
    "exec_summary": exec_summary,
    "recommendation": recommendation,
    "options": options,
    "matrix2x2": matrix2x2,
    "tree": tree,
    "synthesis": synthesis,
    "hub": hub,
    "layers": layers,
    "maturity": maturity,
    "business_case": business_case,
    "journey_columns": journey_columns,
    "hub_field": hub_field,
    "numeral_actions": numeral_actions,
    "waterfall": waterfall,
    "bar_highlight": bar_highlight,
    "pareto": pareto,
    "small_multiples": small_multiples,
    "forecast": forecast,
    "heatmap": heatmap,
    "funnel": funnel,
    "rings": rings,
    "donut": donut,
    "bubbles": bubbles,
    "dashboard": dashboard,
    "data_table": data_table,
    "status_grid": status_grid,
    "cost_benefit": cost_benefit,
    "multiplier_rows": multiplier_rows,
    "roadmap": roadmap,
    "gantt": gantt,
    "swimlane": swimlane,
    "journey": journey,
    "capability": capability,
    "opmodel": opmodel,
    "org": org,
    "architecture": architecture,
    "stage_logo_map": stage_logo_map,
    "exercise": exercise,
    "sticky": sticky,
    "readout": readout,
    "docmock": docmock,
    "about_bio": about_bio,
    "prompt_anatomy": prompt_anatomy,
    "poll": poll,
    "rules_photo": rules_photo,
    "icon_trio": icon_trio,
    "doc_response": doc_response,
    "doc_infographic": doc_infographic,
    "context_brief": context_brief,
    "blank": blank,
    "source_page": source_page,
    "gradient_divider": gradient_divider,
    "wf_stage": wf_stage,
    "wf_contrast": wf_contrast,
    "wf_pillars": wf_pillars,
    "wf_moat": wf_moat,
})
# <<< EXT REGISTRY END <<<

# ---------- deck-level accent ----------
def deck_accent(plan):
    hay = (plan["deck"].get("title", "") + " " + plan["deck"].get("subtitle", ""))
    for p in PROD:
        if p in hay:
            return ACCENT.get(p, "sky")
    return "sky"

def slide_accent(slide, default):
    """Per-slide product accent: if a slide features a product (its topic/headline names one),
    tint that slide with the product's colour (smrtGC=sky, smrtSUB=copper, smrtAE=steel,
    smrt-E=pink, smrtPAY=navy). Otherwise inherit the deck default. Lets a product spotlight
    slide (e.g. smrt-E) carry its own colour without a global override."""
    head = _headline_block(grp(slide))
    hay = (slide.get("topic", "") + " " + (head.get("text", "") if head else ""))
    for p in PROD:
        if p in hay:
            return ACCENT.get(p, default)
    return default

STAGE = ('display:flex;flex-direction:column;justify-content:center;box-sizing:border-box;'
         'font-family:Montserrat,var(--sb-font-fallback);color:var(--sb-text-on-dark);'
         'position:relative;overflow:hidden')

_DECOR_NUM = re.compile(r'<(span|div)((?:(?!data-block|aria-hidden)[^>])*?)>(\s*\d{1,3}\s*)</\1>')

def _hide_decorative_numerals(html):
    """Generated ordinal/step numerals (badges, big numerals) are decorative chrome, not
    authored content: they carry no data-block (real stats always do). Mark them
    aria-hidden so RC8b treats them as chrome, matching how the gate skips aria-hidden."""
    return _DECOR_NUM.sub(r'<\1\2 aria-hidden="true">\3</\1>', html)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=".")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    plan = json.load(open(args.plan))
    cat = json.load(open(os.path.join(args.skill_path, "layouts", "library-v9", "catalog.json")))
    id2r = {l["id"]: l.get("renderer") for l in cat["layouts"]}
    acc = deck_accent(plan)
    out, warnings = [], []
    for s in plan.get("slides", []):
        if s.get("status") == "deleted":
            continue
        fam = (s.get("layout") or {}).get("family", "")
        rname = id2r.get(fam)
        fn = REGISTRY.get(rname)
        if not fn:
            fn = _fallback
            warnings.append("%s (%s->%s)" % (fam, rname, "fallback"))
        sacc = slide_accent(s, acc)                  # per-slide product accent (e.g. smrt-E -> pink)
        inner, pad = fn(s, sacc)
        stage_style = STAGE + ";--sb-product-accent:var(--sb-%s)" % sacc
        # A little extra breathing room at the TOP on content slides so titles don't sit
        # flush against the top edge (full-bleed slides, pad 0, are untouched).
        top = pad + 26 if pad else 0
        out.append('<section class="slide" data-slide="%s" data-topic="%s"><div class="stage" style="%s;padding:%dpx %dpx %dpx %dpx">%s</div></section>'
                   % (s["slide_uuid"], s.get("topic", ""), stage_style, top, pad, pad, pad, inner))
    html = "\n".join(out)
    html = _hide_decorative_numerals(html)
    with open(args.out, "w") as f:
        f.write(html)
    print("rendered %d slides -> %s" % (len(out), args.out))
    # Deck-local renderer patches: a deck may ship a patch_slides.py next to its plan.json
    # (the documented pattern for renderer gaps). Running it HERE — immediately after every
    # fresh render — guarantees the patches apply on EVERY pipeline that renders (manual
    # builds, the edit server's rebuild, export_deck.py), exactly once per render.
    patcher = os.path.join(os.path.dirname(os.path.abspath(args.plan)), "patch_slides.py")
    if os.path.exists(patcher):
        r = subprocess.call([sys.executable or "python3", patcher],
                            cwd=os.path.dirname(patcher))
        if r != 0:
            print("  [warn] deck-local patch_slides.py exited %d — slides may be unpatched" % r)
        else:
            # Patch output may add its own ordinal badges/numerals; re-run the decorative-
            # numeral pass on the patched file so RC8b treats them as chrome (TKMS, 2026-08:
            # the pass previously ran only pre-patch, forcing manual aria-hidden in patches).
            h = open(args.out).read()
            h2 = _hide_decorative_numerals(h)
            if h2 != h:
                with open(args.out, "w") as f:
                    f.write(h2)
    if warnings:
        print("  [warn] no dedicated renderer (used fallback) for: " + ", ".join(warnings))

if __name__ == "__main__":
    main()
