"""PT-02 — Product Split  (renderer: product, shape: split)

Kicker + headline + body + feature checklist on the left; product image on the right.

Image treatment (cycle-4 pin P2/P3, "cut-out phone butchered / grey block in dark"):
the slot is emitted with a default rounded FRAMED treatment (edge-to-edge cover crop,
hairline border + soft shadow) for opaque photos, but build.py finalises it at BUILD
time. When the resolved owned image is a CUT-OUT (has a real alpha channel, e.g. the
smrt-E phone or the smrt-GC dashboard), build.py strips the frame entirely and renders
it FRAMELESS with `object-fit:contain` so the full silhouette floats on the slide
background — no mask, no border, no shadow, no grey field. Detection is PIL-based on the
owned file, so any cut-out product image inherits this automatically. A high-contrast
device skeleton renders if the tag is unresolved.

Data contract (`d`):
    kicker    str   e.g. "Product · smrt-GC"
    title     str
    body      str
    features  list of str
    image_tag str   owned-image tag (e.g. "product-smrt-gc"); "" -> skeleton fallback
"""
from ._kit import stage


def _image_slot(tag):
    if tag:
        # Framed default; build.finalize_image_slots rewrites to frameless-contain for cut-outs.
        return ('<div class="pt-imgslot" data-image-slot="%s" '
                'style="flex:1;align-self:stretch;display:flex;align-items:center;justify-content:center;'
                'border-radius:18px;overflow:hidden;border:1px solid rgba(255,255,255,0.14);'
                'box-shadow:0 22px 60px rgba(0,0,0,0.45)">'
                '<img data-image="%s" alt="" style="width:100%%;height:100%%;object-fit:cover;display:block">'
                '</div>' % (tag, tag))
    # unresolved-tag fallback: crisp device skeleton (high-contrast, clearly a placeholder)
    bars = "".join('<div style="height:%dpx;background:rgba(255,255,255,0.16);border-radius:6px;margin:12px 0;width:%d%%"></div>'
                   % (h, w) for h, w in [(18, 55), (44, 100), (18, 38), (44, 100), (18, 72)])
    return ('<div style="flex:1;align-self:stretch;border-radius:18px;background:var(--sb-panel-bg);'
            'border:1px solid rgba(255,255,255,0.14);padding:26px">'
            '<div style="display:flex;gap:8px;margin-bottom:14px">'
            '<span style="width:10px;height:10px;border-radius:50%;background:var(--sb-copper)"></span>'
            '<span style="width:10px;height:10px;border-radius:50%;background:var(--sb-sky)"></span>'
            '<span style="width:10px;height:10px;border-radius:50%;background:var(--sb-body-on-dark)"></span></div>'
            + bars + '</div>')


def render(c, d):
    feats = ""
    for i, f in enumerate(d.get("features", [])):
        feats += ('<div style="display:flex;gap:12px;align-items:center;margin:13px 0">'
                  '<svg class="icon" data-icon="shield-check" style="width:22px;height:22px;color:var(--sb-sky);flex:none"></svg>'
                  + c.b("f%d" % i, "list_item", f, "span", "body", "font-size:19px") + '</div>')
    left = ('<div style="flex:1.05;display:flex;flex-direction:column;justify-content:center;padding-right:52px">'
            + c.b("k", "label", d["kicker"], "div", "label")
            + c.b("t", "headline", d["title"], "h2", "hl", "font-size:50px;margin-top:12px")
            + c.b("b", "body", d["body"], "div", "body", "font-size:20px;margin-top:16px")
            + '<div style="margin-top:22px">%s</div></div>' % feats)
    inner = '<div style="display:flex;height:100%%;align-items:center">%s%s</div>' % (left, _image_slot(d.get("image_tag", "")))
    return stage(inner, "padding:64px 88px")


SAMPLE = {"kicker": "Product · smrt-GC", "title": "Run the whole project from one place",
          "body": "SmartBuild connects design coordination, RFIs, submittals, scheduling and finance so nothing falls through the cracks.",
          "features": ["Critical Completion Monitor", "RFIs, changes & submittals", "Live schedule + cost"],
          "image_tag": "product-smrt-gc"}
