"""Shared render-kit for per-template render files (Phase 2).

ONE shared render file per template lives in this directory, keyed by the catalog
`renderer` field (e.g. NM-01 -> narrative_split.py). Each file exposes a single:

    def render(c, d) -> str      # returns the slide's <div class="stage">...</div>

so a fix to a template propagates to EVERY deck that uses it, instead of being copied
into each deck's local `generate.py`. This module holds the primitives every render
file shares, so those primitives also live in one place.

------------------------------------------------------------------------------------
The two halves of the render contract
------------------------------------------------------------------------------------
1. `c` — the BLOCK EMITTER (a "context"). The host (a deck's generate.py, or a future
   engine authoring pass) passes an object that implements this protocol:

       c.b(key, typ, html, tag="span", cls="", style="", facts=None) -> str
           Mints a stable block_uuid, appends {block_uuid, type, text, fact_refs} to
           the plan's content_blocks for this slide, and returns the HTML for the
           element carrying `data-block`/`data-block-type` (so pins + SWEEP work).
       c.sid  -> str   the slide id / seed (used for any extra uuids, e.g. a CTA link)

   The render file NEVER mints uuids or touches plan state directly — it only calls
   `c.b(...)`. This keeps uuid lifecycle + fact-ref wiring in one owner (the host).

2. `d` — the DATA the template needs (its slot values). Each render file documents the
   `d` keys it expects at the top of the file; that docstring IS the template's data
   contract. The catalog `slot_schema` for the template is the human-facing version of
   the same thing.

`render` returns a string only. It must not write files or read the catalog.
------------------------------------------------------------------------------------
"""

# Brand accent shorthand, shared so every template uses the same token.
ACCENT = "color:var(--sb-sky)"

# Shared design scale (keep every template on the same rhythm; tokens only, no raw hex —
# the SWEEP raw-hex check scans authored styles).
PAD = "padding:88px 104px"            # standard content padding
CENTER = "display:flex;flex-direction:column;justify-content:center;"


def stage(inner, style="", cls=""):
    """Wrap a template's inner HTML in the fixed-canvas stage element.

    Identical to the deck-local `stage()` helper decks use today; centralised here so
    the wrapper is defined once. `data-block` anchoring, chrome injection and asset
    embedding are added downstream by build.py — render files emit content only.
    `cls` appends extra stage classes (e.g. a deck-local hook class)."""
    classes = ("stage " + cls).strip()
    return '<div class="%s"%s>%s</div>' % (classes, (' style="%s"' % style) if style else "", inner)


def kicker_bar():
    """The section accent rule: short, radiused, aligned to the text left edge —
    deliberately styled so it reads as intentional design, never a stray line."""
    return '<div aria-hidden="true" style="width:64px;height:4px;background:var(--sb-sky);border-radius:2px;margin-top:26px"></div>'


def icon_tile(name, size=48, tile=76):
    """An icon in a tinted rounded tile — the standard icon treatment for cards/lists."""
    return ('<div aria-hidden="true" style="width:%dpx;height:%dpx;border-radius:16px;background:rgba(0,178,227,0.12);'
            'display:flex;align-items:center;justify-content:center;flex:none">'
            '<svg class="icon" data-icon="%s" style="width:%dpx;height:%dpx;color:var(--sb-sky)"></svg></div>'
            % (tile, tile, name, size, size))


class Ctx:
    """Reference block-emitter (the `c` protocol) for hosts that don't need a custom one.

    Mints DETERMINISTIC per-slide uuids (uuid5 of sid+key — stable across rebuilds so
    pins survive regeneration) and accumulates the slide's content_blocks.

        ctx = Ctx("slide-07")
        html = renderers.load("quote")(ctx, d)
        plan_slide["content_blocks"] = ctx.blocks
    """

    def __init__(self, sid):
        import uuid as _uuid
        self.sid = str(sid)
        self.blocks = []
        self._uuid = _uuid

    def _mint(self, key):
        return str(self._uuid.uuid5(self._uuid.NAMESPACE_URL, "sb-deck:%s:%s" % (self.sid, key)))

    def b(self, key, typ, html, tag="span", cls="", style="", facts=None):
        import re as _re
        u = self._mint(key)
        blk = {"block_uuid": u, "type": typ,
               "text": _re.sub(r"<[^>]+>", "", html).strip()}
        if facts:
            blk["fact_refs"] = [f for f in facts if f]
        self.blocks.append(blk)
        return '<%s class="%s" data-block="%s" data-block-type="%s"%s>%s</%s>' % (
            tag, cls, u, typ, (' style="%s"' % style) if style else "", html, tag)


def card(inner, style="", accent=None):
    """Standard content container: token surface + 6px radius (brand rule: 6px on ALL
    containers, never a pill). `accent` (a brand token, e.g. 'var(--sb-sky)') adds a top rule.
    Use this instead of hand-rolling card styles so rounding/border stay consistent."""
    top = ("border-top:5px solid %s;" % accent) if accent else ""
    return ('<div style="background:var(--sb-panel-bg);border:1px solid var(--sb-border-subtle);'
            'border-radius:6px;%s%s">%s</div>' % (top, style, inner))


def image_slot(tag, style="width:100%;height:100%;object-fit:contain"):
    """A frameless image slot. NEVER hardcode a border/frame here: build.finalize_image_slots
    frames only UNRESOLVED placeholders, and a resolved (esp. cut-out) image renders frameless.
    Hardcoding a frame is the bug that made the smrt-E phone sit in a box."""
    return '<img data-image="%s" alt="" style="%s">' % (tag, style)


def reveal_cls(base="reveal", extra=""):
    """Scroll-reveal class string. `base` = reveal | reveal-left | reveal-right |
    reveal-scale | reveal-hero. deck.js adds .visible when the slide scrolls into view
    (staggered). Print/PPTX force the final state, so exports are unaffected."""
    return (base + " " + extra).strip()


def bloom(pid, trigger_label, panel_inner):
    """Click-to-expand 'bloom': a trigger button that irises a full-slide panel open from
    its own position (deck.js wires open/close/Esc; CSP-safe via data-* attrs, no onclick).
    Screen-only — @media print hides .bloom-panel, so exports show the base slide.
    Returns (trigger_html, panel_html); place the trigger in the stage and the panel as a
    sibling inside the same stage. `pid` is the panel DOM id."""
    trigger = ('<button class="bloom-trigger" type="button" data-bloom="%s">%s</button>'
               % (pid, trigger_label))
    panel = ('<div class="bloom-panel" id="%s"><div class="bloom-inner">%s'
             '<button class="bloom-close" type="button" data-close="%s" aria-label="Close">&times;</button>'
             '</div></div>' % (pid, panel_inner, pid))
    return trigger, panel


def bloom_grid(items, columns=None):
    """A GRID of click-to-expand "bloom" tiles — the "expand more" pattern. Each `items`
    entry is a dict:
        id     : unique DOM id for this tile's panel (e.g. "bloom-prod-smrtgc")
        tile   : tile inner HTML — already data-block-tagged by the caller (via c.b)
        panel  : panel inner HTML — already tagged; shown when the tile expands
        accent : optional brand token for the tile's top rule (default var(--sb-sky))
    Returns (grid_html, panels_html): place grid_html where the tiles go and panels_html
    as a sibling INSIDE THE SAME stage. deck.js wires open/close/Esc; the panel is
    THEME-ADAPTIVE (base.css .bloom-panel = light in light mode, dark in dark mode) and
    screen-only (hidden in PDF/PPTX). The helper only wires the bloom mechanics + default
    tile chrome + close button — it never mints uuids or tags content (that stays with
    the caller, so pins + SWEEP keep working)."""
    n = columns or len(items) or 1
    tiles, panels = "", ""
    for it in items:
        pid = it["id"]
        accent = it.get("accent", "var(--sb-sky)")
        tiles += (
            '<div class="bloom-tile reveal-scale" data-bloom="%s" '
            'style="background:var(--sb-panel-bg);border:1px solid var(--sb-border-subtle);'
            'border-top:5px solid %s;border-radius:6px;padding:24px 22px;--sb-product-accent:%s;">%s'
            '<div aria-hidden="true" style="margin-top:16px;font-size:12px;font-weight:800;'
            'letter-spacing:0.08em;text-transform:uppercase;color:%s;">Explore &rarr;</div></div>'
            % (pid, accent, accent, it["tile"], accent)
        )
        panels += (
            '<div class="bloom-panel" id="%s"><div class="bloom-inner" style="max-width:1040px;">%s'
            '<button class="bloom-close" type="button" data-close="%s" aria-label="Close">&times;</button>'
            '</div></div>' % (pid, it["panel"], pid)
        )
    grid = ('<div style="display:grid;grid-template-columns:repeat(%d,1fr);gap:18px;align-items:stretch;">%s</div>'
            % (n, tiles))
    return grid, panels


def image_slot(tag, width="100%", height="360px", radius="6px", extra=""):
    """A correctly-formatted photo slot. The wrapper FIXES the geometry (width/height/overflow),
    and the <img> fills it via .img-cover (object-fit:cover) so any resolved photo — owned first,
    else the slide's Unsplash pick — crops to fit instead of stretching. BUILD authors this;
    BRAND swaps <img data-image="tag"> for the chosen, embedded photo. Always give a real height
    so the slot is never a zero-height (invisible) or unbounded box."""
    return ('<div style="width:%s;height:%s;overflow:hidden;border-radius:%s;%s">'
            '<img data-image="%s" class="img-cover"></div>' % (width, height, radius, extra, tag))
