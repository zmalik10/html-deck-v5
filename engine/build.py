"""
SmartBuild Deck v5 — build.py  (BUILD + BRAND assembly)

Takes the canonical plan.json + Claude-authored slides.html + assets and
emits two artifacts:  review.html (full authoring chrome) and
presentation.html (clean client deliverable).  Also writes a run manifest
with versions + content hashes, atomically, keeping a per-pass snapshot.

Claude authors slides.html only.  This script never generates layout — it
injects assets (tokens as CSS vars, embedded fonts, logos, icons, images)
and wraps the authored slides with the shared skeleton.  This keeps Python
in its lane (asset injection, not creativity).

Usage:
    python build.py --skill-path <dir> --plan plan.json --slides slides.html --out <dir> [--fidelity]
"""
import argparse, base64, json, os, re, sys, hashlib, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DEFAULT = os.path.dirname(HERE)

LOGO_FILES = {
    "smartbuild": "smartbuild.4c.svg", "smartbuild-badge": "smartbuild-badge.svg",
    "smrtGC": "smrt-GC.4c.svg",
    "smrtSUB": "smrt-SUB.4c.svg", "smrtAE": "smrt-AE.4c.svg", "smrtAEC": "smrt-AEC.4c.png",
    "smrt-E": "smrt-E.4c.svg",
}

# Brand logos are SVG; smrtAEC ships only as a 4c raster (no vector exists). Pick the
# data-URI mime from the file extension so raster logos embed correctly (not as svg+xml).
_LOGO_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def logo_mime(fn):
    return _LOGO_MIME.get(os.path.splitext(fn)[1].lower(), "image/svg+xml")

# Pinned export libs. Fill integrity with real sha384 SRI before client use;
# preflight/SWEEP flags empty integrity for client decks. Empty => loads without SRI (dev).
CDN = {
    "html2canvas": {"url": "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
                    "integrity": "sha384-ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H"},
    "jspdf": {"url": "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
              "integrity": "sha384-JcnsjUPPylna1s1fvi1u12X5qjY5OL56iySh75FdtrwhO/SWXgMjoVqcKyIIWOLk"},
    "pptx": {"url": "https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js",
             "integrity": "sha384-Cck14aA9cifjYolcnjebXRfWGkz5ltHMBiG4px/j8GS+xQcb7OhNQWZYyWjQ+UwQ"},
    # JSZip: required for the gradient-sentinel -> native <a:gradFill> post-build swap
    # (export fails loudly if a gradient is emitted but JSZip is unavailable).
    "jszip": {"url": "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js",
              "integrity": "sha384-+mbV2IY1Zk/X1p/nWllGySJSUN8uMs+gUAN10Or95UBH0fpj6GfKgPmgC5EXieXG"},
}
CDN_ALLOWLIST = ["cdnjs.cloudflare.com", "cdn.jsdelivr.net", "images.unsplash.com"]


def b64(path, mime):
    with open(path, "rb") as f:
        return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode("ascii"))


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def validate_plan(plan, skill_path):
    """Schema validation. Uses jsonschema if available, else structural fallback."""
    schema = load_json(os.path.join(skill_path, "schema", "plan.schema.json"))
    try:
        import jsonschema
        jsonschema.validate(plan, schema)
        return []
    except ImportError:
        errs = []
        for k in schema.get("required", []):
            if k not in plan:
                errs.append("missing top-level key: " + k)
        if plan.get("schema_version") != "5.0.0":
            errs.append("schema_version must be 5.0.0")
        for i, sl in enumerate(plan.get("slides", [])):
            for k in ("slide_uuid", "topic", "layout", "content_blocks"):
                if k not in sl:
                    errs.append("slide[%d] missing %s" % (i, k))
        return errs
    except Exception as e:
        return ["schema validation error: " + str(e)]


def token_css(tokens):
    b = tokens["brand"]
    light, dark = tokens["color"]["light"], tokens["color"]["dark"]
    fam = tokens["typography"]["font_fallback"]
    common = (
        "--sb-sky:%s;--sb-copper:%s;--sb-steel:%s;--sb-pink:%s;--sb-ink:%s;--sb-navy:%s;--sb-on-accent:#fff;"
        "--sb-font-fallback:%s;--sb-radius-large:%s;--sb-anim-button:%s;--sb-anim-bloom:%s;"
    ) % (b["sky"], b["copper"], b["steel"], b["pink"], b["ink"], b["navy"], fam,
         tokens["radius"]["large"], tokens["animation"]["button_hover"], tokens["animation"]["bloom"])
    def theme_vars(c, on_dark):
        # theme-dependent set: existing on-dark vars + new SEMANTIC tokens renderers use
        # so authored slides restyle correctly in either theme.
        return (
            "--sb-deck-bg:%s;--sb-text-on-dark:%s;--sb-body-on-dark:%s;"
            "--sb-panel-bg:%s;--sb-panel-bg-deep:%s;"
            "--sb-text-primary:%s;--sb-text-secondary:%s;--sb-panel:%s;--sb-border-subtle:%s;--sb-title:%s;"
        ) % (
            c["deck-bg"],
            ("#fff" if on_dark else light["text-primary"]),
            ("rgba(255,255,255,0.7)" if on_dark else "rgba(6,12,26,0.7)"),
            ("#0d1829" if on_dark else "#ffffff"),
            ("#080f1e" if on_dark else "#f5f8fc"),
            c["text-primary"], c["text-secondary"], c["bg-secondary"], c["border-color"],
            ("#fff" if on_dark else b["navy"]),
        )
    dark_vars = theme_vars(dark, True)
    light_vars = theme_vars(light, False)
    # :root = deck default (dark); [data-theme=light] = deck-wide light; and the per-slide
    # override redeclares the FULL theme set scoped to that slide's .stage so a per-slide
    # light/dark choice genuinely restyles authored content (higher specificity than root).
    return (
        ":root{%s%s}\n"
        "[data-theme=\"light\"]{%s}\n"
        ".slide[data-variant=\"dark\"] .stage{%s}\n"
        ".slide[data-variant=\"light\"] .stage{%s}\n"
    ) % (common, dark_vars, light_vars, dark_vars, light_vars)


def font_css(skill_path):
    css = ""
    for w in (400, 700, 900):
        uri = b64(os.path.join(skill_path, "assets", "fonts", "montserrat-%d.woff2" % w), "font/woff2")
        css += ("@font-face{font-family:'Montserrat';font-style:normal;font-weight:%d;"
                "font-display:swap;src:url('%s') format('woff2');}\n" % (w, uri))
    return css


def inject_logos(slides_html, skill_path, resolved, brand=True):
    """Replace <img data-logo="X"> with embedded SVG (BRAND) or a labeled placeholder (light)."""
    logo_dir = os.path.join(skill_path, "assets", "logos")

    def repl(m):
        name = m.group(1)
        rest = m.group(2) or ""   # preserve any extra attrs (e.g. style="width:220px")
        fn = LOGO_FILES.get(name)
        if brand and fn and os.path.exists(os.path.join(logo_dir, fn)):
            uri = b64(os.path.join(logo_dir, fn), logo_mime(fn))
            resolved.append({"asset_id": "logo:" + name, "kind": "logo", "source": "SmartBuild brand",
                             "license": "proprietary", "requires_attribution": False, "approved_for_client": True})
            return '<img data-logo="%s" src="%s" alt="%s"%s>' % (name, uri, name, rest)
        # light fidelity: visible placeholder, no heavy embed (carry any inline style through)
        return ('<span data-logo="%s"%s>%s</span>') % (
            name, ' style="display:inline-flex;align-items:center;justify-content:center;min-width:120px;'
            'height:44px;border:1px dashed var(--sb-sky);border-radius:6px;font-size:12px;letter-spacing:.1em;color:var(--sb-sky)"', name)

    # tolerate extra attributes after data-logo (this is why styled logos silently failed before)
    return re.sub(r'<img\s+data-logo="([^"]+)"([^>]*?)\s*/?>', repl, slides_html)


def inject_icons(slides_html, skill_path, resolved):
    """Replace <svg class="icon" data-icon="NAME"></svg> with the catalog SVG (Lucide, ISC — no attribution)."""
    cat_path = os.path.join(skill_path, "libraries", "icons", "catalog.json")
    if not os.path.exists(cat_path):
        return slides_html
    cat = load_json(cat_path)
    by_name = {i["name"]: i["svg"] for i in cat.get("icons", [])}
    used = {}
    n = [0]

    def repl(m):
        name = m.group(1)
        svg = by_name.get(name)
        if not svg:
            return m.group(0)  # leave unknown icon as-is; SWEEP editorial will flag
        used[name] = True
        n[0] += 1
        h = hashlib.md5(("icon:%s:%d" % (name, n[0])).encode()).hexdigest()
        uid = "%s-%s-4%s-8%s-%s" % (h[:8], h[8:12], h[13:16], h[17:20], h[20:32])
        # give the icon a data-block anchor so it is pinnable, and carry its name for descriptions
        return svg.replace('<svg class="icon"',
                           '<svg class="icon" data-block="%s" data-block-type="icon" data-icon-name="%s"' % (uid, name), 1)

    # match the icon placeholder whether or not it carries extra attributes (e.g. style="...")
    out = re.sub(r'<svg\s+class="icon"\s+data-icon="([^"]+)"[^>]*>\s*</svg>', repl, slides_html)
    if used:
        resolved.append({"asset_id": "iconset:lucide", "kind": "icon", "source": "Lucide",
                         "license": "ISC", "link": "https://lucide.dev",
                         "requires_attribution": False, "approved_for_client": True})
    return out


def _img_catalog(skill_path):
    p = os.path.join(skill_path, "libraries", "images", "catalog.json")
    owned, fallback = {}, {}
    if os.path.exists(p):
        cat = load_json(p)
        for e in cat.get("owned", {}).get("entries", []):
            for t in e.get("tags", []):
                owned.setdefault(t, e)
        for e in cat.get("unsplash_fallback", {}).get("entries", []):
            for t in e.get("tags", []):
                fallback.setdefault(t, e)
    return owned, fallback


def _resolve_owned_path(skill_path, file):
    """Locate an owned image file. Preferred home is skill-root-relative
    (assets/images/...); legacy libraries/images/<file> is still honored."""
    if not file:
        return None
    for cand in (os.path.join(skill_path, file),
                 os.path.join(skill_path, "libraries", "images", file)):
        if os.path.exists(cand):
            return cand
    return None


def _img_has_alpha(path):
    """True if the raster at `path` carries a REAL (used) alpha channel — i.e. it is a
    cut-out (e.g. the smrt-E phone or smrt-GC dashboard on a transparent background), not
    a rectangular photo. SVGs are vector and never treated as cut-out rasters here."""
    if not path or path.lower().endswith(".svg"):
        return False
    try:
        from PIL import Image
        im = Image.open(path)
        if im.mode not in ("RGBA", "LA") and not (im.mode == "P" and "transparency" in im.info):
            return False
        a = im.convert("RGBA").getchannel("A")
        lo, _ = a.getextrema()
        return lo < 250                       # at least some pixels are (near-)transparent
    except Exception:
        return False


def _embed_image(path):
    """Embed an owned image as a self-contained data URI. SVG embeds inline (tiny, vector,
    brand-exact). Cut-out rasters (alpha) embed as PNG so transparency is PRESERVED — a
    JPEG/RGB flatten would paint a black box behind the silhouette (the round-2 grey/black
    block). Opaque photos embed compressed as JPEG."""
    if path.lower().endswith(".svg"):
        return b64(path, "image/svg+xml")
    try:
        from PIL import Image
        import io
        im = Image.open(path)
        if _img_has_alpha(path):
            im = im.convert("RGBA")
            if im.width > 1920:
                im = im.resize((1920, round(im.height * 1920 / im.width)))
            buf = io.BytesIO(); im.save(buf, "PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        im = im.convert("RGB")
        if im.width > 1920:
            im = im.resize((1920, round(im.height * 1920 / im.width)))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        return b64(path, mime)


def _embed_remote(url, timeout=25):
    """Download a remote image (Unsplash fallback) and return a self-contained JPEG data-URI,
    so BRAND decks stay self-contained (no live CDN dependency at view time). Returns None on
    any failure (offline, 404, SSL) so the caller can degrade gracefully. SSL: try the default
    trust store, then certifi if installed, then an unverified context as a last resort (these
    are public stock photos, not sensitive endpoints)."""
    import urllib.request, ssl, io
    req = urllib.request.Request(url, headers={"User-Agent": "smartbuild-deck/5"})
    data = None
    for ctx in _ssl_contexts():
        try:
            data = urllib.request.urlopen(req, timeout=timeout, context=ctx).read()
            break
        except Exception:
            continue
    if not data:
        return None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if im.width > 1920:
            im = im.resize((1920, round(im.height * 1920 / im.width)))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def _ssl_contexts():
    import ssl
    ctxs = [None]  # default trust store first
    try:
        import certifi
        ctxs.append(ssl.create_default_context(cafile=certifi.where()))
    except Exception:
        pass
    try:
        ctxs.append(ssl._create_unverified_context())  # last resort for public stock images
    except Exception:
        pass
    return ctxs


def _cover_attr(rest):
    """Inject class="img-cover" (fill slot, object-fit:cover, no distortion) unless the author
    already set a class or an explicit object-fit — so any photo lands formatted, not stretched."""
    return "" if ("class=" in rest or "object-fit" in rest or "img-cover" in rest) else ' class="img-cover"'


def inject_images(slides_html, skill_path, resolved, brand=True, img_choices=None):
    """Replace <img data-image="TAG">. Resolution order at BRAND (owned ALWAYS wins):
      1. OWNED image (libraries/images catalog, by tag) — embedded self-contained.
      2. The slide's plan-recorded Unsplash choice (image_intent.resolved, provider=unsplash) —
         downloaded + embedded as a data-URI (falls back to a live CDN reference if offline).
      3. A blind pre-curated Unsplash catalog fallback (legacy) — embedded, else CDN reference.
      4. A visible placeholder (SWEEP hard-fails an unresolved slot at BRAND).
    Light fidelity always uses the placeholder (progressive fidelity). Injected photos get
    class="img-cover" so they fill their slot without distortion. `img_choices` maps a slot
    tag -> its plan image_intent.resolved dict."""
    owned, fallback = _img_catalog(skill_path)
    img_choices = img_choices or {}

    def placeholder(tag, rest):
        # Light-fidelity placeholder that actually OCCUPIES its slot (never collapses) and
        # reads as an intentional image box. Merge the sizing into any style the renderer
        # already put on the slot so a duplicate style="" attribute can't shadow it (the
        # browser keeps the first style attr, so ours must fold into it). Label text sits
        # inside the data-image element, which the orphan/RC8b check skips.
        ph = ("display:flex;align-items:center;justify-content:center;width:100%;height:100%;"
              "min-height:200px;box-sizing:border-box;background:rgba(255,255,255,0.05);"
              "border:1px dashed var(--sb-steel);border-radius:8px;color:var(--sb-steel);"
              "font-size:13px;font-weight:800;letter-spacing:0.12em;text-transform:uppercase")
        if 'style="' in rest:
            rest = re.sub(r'style="([^"]*)"', lambda mm: 'style="%s;%s"' % (mm.group(1), ph), rest, count=1)
            return '<span data-image="%s"%s>Image</span>' % (tag, rest)
        return '<span data-image="%s"%s style="%s">Image</span>' % (tag, rest, ph)

    def repl(m):
        tag = m.group(1)
        rest = m.group(2) or ""   # carry any authored attrs through (e.g. style="...")
        if not brand:
            return placeholder(tag, rest)
        # 1) OWNED images ALWAYS take priority — never overridden by an Unsplash pick.
        e = owned.get(tag)
        path = _resolve_owned_path(skill_path, e.get("file", "")) if e else None
        if e and path:
            uri = _embed_image(path)
            resolved.append({**e["provenance"], "asset_id": "image:" + e["id"]})
            alt = e.get("mood") or tag
            return '<img data-image="%s"%s%s src="%s" alt="%s">' % (tag, _cover_attr(rest), rest, uri, alt)
        # 2) Plan-recorded Unsplash choice for this slot (only reached when nothing owned fit).
        ch = img_choices.get(tag)
        if ch and ch.get("provider") == "unsplash":
            url = ch.get("url") or (
                "https://images.unsplash.com/photo-%s?w=2400&q=80&auto=format&fit=crop&crop=entropy"
                % ch.get("photo_id", ""))
            prov = {"asset_id": "image:unsplash-" + (ch.get("photo_id") or "sel"), "kind": "image",
                    "source": "Unsplash", "author": ch.get("author", ""),
                    "link": ch.get("author_url") or url, "license": ch.get("license") or "Unsplash",
                    "requires_attribution": True,
                    "approved_for_client": bool(ch.get("approved_for_client", True))}
            uri = _embed_remote(url) if url else None
            if uri:
                resolved.append(prov)
                return '<img data-image="%s"%s%s src="%s" alt="%s">' % (tag, _cover_attr(rest), rest, uri, ch.get("author") or tag)
            if url:  # embed failed (offline?) — reference the CDN so it still renders, and warn
                print("  [warn] could not embed Unsplash image for '%s' (offline?); referencing CDN URL" % tag)
                resolved.append(prov)
                return '<img data-image="%s"%s%s src="%s" alt="%s" crossorigin="anonymous">' % (tag, _cover_attr(rest), rest, url, tag)
        # 3) Legacy blind catalog fallback — embed for self-containment, else reference the CDN.
        e = fallback.get(tag)
        if e:
            url = "https://images.unsplash.com/photo-%s?w=2400&q=85&auto=format&fit=crop" % e["unsplash_id"]
            resolved.append({**e["provenance"], "asset_id": "image:unsplash-" + e["unsplash_id"]})
            uri = _embed_remote(url)
            if uri:
                return '<img data-image="%s"%s%s src="%s" alt="%s">' % (tag, _cover_attr(rest), rest, uri, tag)
            return '<img data-image="%s"%s%s src="%s" alt="%s" crossorigin="anonymous">' % (tag, _cover_attr(rest), rest, url, tag)
        if tag.startswith("product-"):   # RC10: no owned product screenshot for this tag yet
            print("  [warn] product slide using placeholder mockup (no owned image for tag '%s')" % tag)
        return placeholder(tag, rest)

    # tolerate extra attributes after data-image (mirrors the inject_logos fix)
    return re.sub(r'<img\s+data-image="([^"]+)"([^>]*?)\s*/?>', repl, slides_html)


def finalize_image_slots(slides_html, skill_path):
    """Cycle-4 P2/P3 — cut-out product treatment. The product renderer emits its image in
    a `.pt-imgslot` wrapper carrying the DEFAULT rounded framed treatment. Here, at build
    time, we resolve each slot's owned image and PIL-check its alpha: a CUT-OUT (alpha)
    image is rewritten to render FRAMELESS with `object-fit:contain` (no mask, border,
    shadow or background) so the full silhouette floats on the slide background — killing
    both the butchered cover-crop (P3) and the dark grey block (P2). Opaque photos and
    unresolved tags keep the framed treatment. Runs BEFORE inject_images so the style is
    already correct when the tag is embedded. Detection is per-image, so any cut-out
    product image inherits the fix automatically."""
    owned, _ = _img_catalog(skill_path)
    FRAMELESS_SLOT = "flex:1;align-self:stretch;display:flex;align-items:center;justify-content:center"
    FRAMELESS_IMG = "max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;display:block"

    def repl(m):
        block, tag = m.group(0), m.group(1)
        e = owned.get(tag)
        path = _resolve_owned_path(skill_path, e.get("file", "")) if e else None
        # Cut-out treatment for a true alpha PNG OR any product/device screenshot (product-*):
        # device mockups must show the WHOLE device (contain), never be cropped by a cover box,
        # even when the export sits on an opaque studio background.
        if not (_img_has_alpha(path) or tag.startswith("product-") or tag.startswith("device-")):
            return block                       # opaque photo / unresolved -> keep framed
        block = re.sub(r'(<div class="pt-imgslot"[^>]*\sstyle=")[^"]*(")',
                       lambda x: x.group(1) + FRAMELESS_SLOT + x.group(2), block, count=1)
        block = re.sub(r'(<img\s+data-image="' + re.escape(tag) + r'"[^>]*\sstyle=")[^"]*(")',
                       lambda x: x.group(1) + FRAMELESS_IMG + x.group(2), block, count=1)
        return block

    return re.sub(r'<div class="pt-imgslot" data-image-slot="([^"]+)"[^>]*>.*?</div>',
                  repl, slides_html, flags=re.S)


def inject_watermark(slides_html, text):
    wm = '<div class="sb-watermark" aria-hidden="true">%s</div>' % text
    return re.sub(r'(<div class="stage[^"]*"[^>]*>)', lambda m: m.group(1) + wm, slides_html)


def footer_logo_css(skill_path, resolved):
    """BRAND: one CSS rule embedding the footer mark's data URI a single time."""
    fn = os.path.join(skill_path, "assets", "logos", "smartbuild.4c.svg")
    if not os.path.exists(fn):
        return ""
    uri = b64(fn, "image/svg+xml")
    resolved.append({"asset_id": "logo:footer", "kind": "logo", "source": "SmartBuild brand",
                     "license": "proprietary", "requires_attribution": False, "approved_for_client": True})
    return ".sb-footer-logo{background-image:url('%s');}\n" % uri


def catalog_by_id(skill_path):
    p = os.path.join(skill_path, "layouts", "library-v9", "catalog.json")
    if not os.path.exists(p):
        return {}
    return {it["id"]: it for it in load_json(p).get("layouts", [])}


def slide_provenance(plan, cat):
    """Per-slide manifest rows: the template id + version the deck CONSUMED, plus any
    reference-library/deck-archive provenance already carried on the slide.

    The deck stamps what it used: version is the plan's per-slide `templateVersion`
    when present (pinned at build time), else the current catalog `version`. This is
    why a later stage-gated master-template bump never silently changes an in-flight
    deck — the manifest is the record of the version actually rendered. Provenance is
    passed through verbatim from the plan (the reference-library master is itself
    versioned/gated; the slide already stamped the ref_version it consumed)."""
    rows = []
    for sl in plan.get("slides", []):
        if sl.get("status") == "deleted":
            continue
        fam = (sl.get("layout") or {}).get("family")
        entry = cat.get(fam, {})
        row = {
            "slide_uuid": sl.get("slide_uuid"),
            "template_id": fam,
            "template_version": sl.get("templateVersion") or entry.get("version"),
        }
        if not entry and fam not in (None, "custom"):
            row["template_unverified"] = True  # id not in library-v9 catalog (build.py warns separately)
        prov = sl.get("provenance")
        if prov:
            row["provenance"] = prov
        rows.append(row)
    return rows


def slide_role(family, cat):
    """Classify a slide by its template so chrome rules can differ by role."""
    it = cat.get(family, {})
    tags = set(t.lower() for t in it.get("tags", []))
    title = (it.get("title") or "").lower()
    if tags & {"cover", "open"} or "cover" in title:
        return "cover"
    if tags & {"close", "closing", "cta"} or "closing" in title:
        return "closing"
    if tags & {"section", "divider"} or "section header" in title:
        return "section"
    return "content"


STAGE_NAMES = {1: "PLAN", 2: "BUILD", 3: "REFINE", 4: "BRAND & SWEEP", 5: "EXPORT"}


def inject_chrome(slides_html, plan, cat):
    """Deck-level chrome (R2-H1a numbering + R2-H2/H3a chrome-on-references).

    Numbering rule (decided): the COVER (first slide) is unnumbered and UNCOUNTED; the first
    slide after the cover is page 1; EVERY subsequent slide — content, section divider,
    verbatim reference reuse, and the closing — is numbered. Page number == the slide's
    0-based index (cover=0 is skipped, so slide 2 -> 1, slide 3 -> 2, ...).

    Chrome placement: footer logo + page number on every non-cover slide, reference slides
    INCLUDED — the deck chrome sits above the locked render (footer bottom-left, page number
    bottom-right; deck.js auto-contrasts the mark per slide). The cover carries neither."""
    parts = re.split(r'(?=<section class="slide")', slides_html)
    idx = 0
    out = []
    for part in parts:
        if not part.lstrip().startswith("<section"):
            out.append(part); continue
        this_idx = idx
        idx += 1
        if this_idx == 0:                  # cover: unnumbered, uncounted, no chrome
            out.append(part); continue
        # Brand rule: at most ONE SmartBuild logo per slide. If the slide already carries its
        # own SmartBuild mark (a closing badge, a hero wordmark, etc.), do NOT add the footer
        # logo too - keep only the page number.
        has_own_logo = ('data-logo="smartbuild"' in part) or ('data-logo="smartbuild-badge"' in part)
        footer_logo = "" if has_own_logo else '<div class="sb-footer-logo" aria-hidden="true"></div>'
        chrome = (footer_logo
                  + '<div class="sb-page-num" aria-hidden="true">%d</div>' % this_idx)
        part = re.sub(r'(<div class="stage[^"]*"[^>]*>)',
                      lambda m, c=chrome: m.group(1) + c, part, count=1)
        out.append(part)
    return "".join(out)


def reference_slide_indices(plan):
    """0-based indices of slides that are verbatim-locked reference reuses."""
    return {i for i, sl in enumerate(plan.get("slides", []))
            if isinstance(sl.get("reference"), dict) and sl["reference"].get("ref_id")}


def _load_reference_entry(sp, ref_id):
    """Full reference entry: prefer the derived entries/<ref_id>.json, fall back to catalog.json."""
    ed = os.path.join(sp, "layouts", "reference-library", "entries", (ref_id or "") + ".json")
    if os.path.exists(ed):
        return load_json(ed)
    catp = os.path.join(sp, "layouts", "reference-library", "catalog.json")
    if os.path.exists(catp):
        return next((x for x in load_json(catp).get("entries", []) if x.get("ref_id") == ref_id), None)
    return None


def _render_path(sp, rel):
    """Resolve a render pointer, PREFERRING the slimmed copy (rendered.slim/) when present,
    else the original (rendered/)."""
    base = os.path.join(sp, "layouts", "reference-library")
    if rel.startswith("rendered/"):
        slim = os.path.join(base, "rendered.slim/" + rel[len("rendered/"):])
        if os.path.exists(slim):
            return slim
    return os.path.join(base, rel)


def load_reference_render(sp, ref_id, theme):
    """Locked HTML fragment for a verbatim reference entry in the requested theme
    (falls back to the entry's native theme). None if not a verbatim-locked entry."""
    e = _load_reference_entry(sp, ref_id)
    if not e or e.get("render_mode") != "verbatim-locked":
        return None
    render = e.get("render") or {}
    rel = render.get(theme) or render.get(e.get("native_theme")) or next(iter(render.values()), None)
    if not rel:
        return None
    fp = _render_path(sp, rel)
    return read(fp) if os.path.exists(fp) else None


def reference_variants(sp, ref_id):
    """Both baked renders {'light':html,'dark':html} for a verbatim entry (present keys only),
    so a reused verbatim slide can carry BOTH and toggle live per-slide/deck-wide."""
    e = _load_reference_entry(sp, ref_id)
    if not e or e.get("render_mode") != "verbatim-locked":
        return {}
    out = {}
    for th, rel in (e.get("render") or {}).items():
        fp = _render_path(sp, rel)
        if rel and os.path.exists(fp):
            out[th] = read(fp)
    return out


def inject_reference_renders(slides_html, plan, sp, theme):
    """Replace the `.stage` content of any reference slide with its exec-approved LOCKED
    render (word/image/style-for-style; theme picks light/dark). Runs before chrome so a
    locked slide keeps its own baked footer/logo and gets no extra chrome."""
    plan_slides = plan.get("slides", [])
    refs = {i: (sl["reference"].get("ref_id"), sl["reference"].get("theme") or theme)
            for i, sl in enumerate(plan_slides)
            if isinstance(sl.get("reference"), dict) and sl["reference"].get("ref_id")}
    if not refs:
        return slides_html
    parts = re.split(r'(?=<section class="slide")', slides_html)
    out, idx = [], 0
    for part in parts:
        if not part.lstrip().startswith("<section"):
            out.append(part); continue
        if idx in refs:
            ref_id, th = refs[idx]
            variants = reference_variants(sp, ref_id)
            # Inject BOTH renders wrapped so per-slide + deck-wide light/dark toggle live;
            # fall back to the single requested/native render if only one exists.
            if len(variants) >= 2 and "light" in variants and "dark" in variants:
                content = ('<div class="ref-variant ref-light">%s</div>'
                           '<div class="ref-variant ref-dark">%s</div>') % (variants["light"], variants["dark"])
            else:
                content = next(iter(variants.values()), None) or load_reference_render(sp, ref_id, th)
            if content:
                # tag the section so SWEEP/fidelity skip this locked, exec-approved slide
                if "data-reference=" not in part.split(">", 1)[0]:
                    part = part.replace('<section class="slide"',
                                        '<section class="slide" data-reference="%s"' % ref_id, 1)
                part = re.sub(r'(<div class="stage[^"]*"[^>]*>).*?(</div>\s*</section>)',
                              lambda m, r=content: m.group(1) + r + m.group(2),
                              part, count=1, flags=re.S)
            else:
                print("  [warn] reference render missing for %s (theme=%s)" % (ref_id, th))
        idx += 1
        out.append(part)
    return "".join(out)


def build_page(mode, title, slides_html, css_head, ui_html, deck_js, annotations, sources, plan_rev, theme, stage_no=None, stage_name=None, variants=None):
    boot = {
        "__DECK__": {"mode": mode, "title": title, "plan_revision": plan_rev,
                     "stage": stage_no, "stage_name": stage_name, "stage_total": 5},
        "__ANNOTATIONS__": annotations if mode == "review" else [],
        "__SOURCES__": sources,
        "__VARIANTS__": variants or {},
        "__CDN__": CDN,
    }
    boot_js = "".join("window.%s=%s;\n" % (k, json.dumps(v)) for k, v in boot.items())
    # connect-src includes localhost so the file:// view's ↗ button can PROBE for a live
    # edit server (edit_server.py) before opening it — a dead tab reads as "editor broken".
    csp = ("default-src 'self' 'unsafe-inline' data: blob:; "
           "script-src 'self' 'unsafe-inline' " + " ".join("https://" + h for h in CDN_ALLOWLIST) + "; "
           "img-src 'self' data: https:; font-src 'self' data:; "
           "connect-src 'self' https: http://127.0.0.1:* http://localhost:*;")
    return (
        "<!DOCTYPE html>\n<html lang=\"en\" data-theme=\"%s\">\n<head>\n<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        "<meta http-equiv=\"Content-Security-Policy\" content=\"%s\">\n"
        "<title>%s</title>\n<style>\n%s</style>\n</head>\n<body>\n"
        "<div class=\"deck\">\n%s\n</div>\n%s\n"
        "<script>\n%s</script>\n<script>\n%s</script>\n</body>\n</html>\n"
    ) % (theme, csp, title, css_head, slides_html, ui_html, boot_js, deck_js)


def template_library_script(skill_path):
    """Embed the self-contained rendered template library (layouts/library-v9/rendered-gallery.html)
    into review.html as a base64 payload the Template Library button decodes and opens in a new
    tab (via a blob URL). Base64 avoids any </script> from the library terminating this block.
    Returns "" if the library has not been generated yet (run engine/build_gallery.py)."""
    p = os.path.join(skill_path, "layouts", "library-v9", "rendered-gallery.html")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        b64 = base64.b64encode(f.read().encode("utf-8")).decode("ascii")
    return '\n<script type="text/plain" id="tpl-lib-b64">%s</script>\n' % b64


def atomic_write(path, content):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=SKILL_DEFAULT)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--slides", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", action="store_true", help="bake full-fidelity assets (BRAND); omit for light fidelity")
    ap.add_argument("--presentation", action="store_true",
                    help="also emit the clean client presentation.html (default: review.html only)")
    ap.add_argument("--no-library", action="store_true",
                    help="skip embedding the rendered template library into review.html (used by build_gallery.py when building the library's own preview, to avoid recursion)")
    args = ap.parse_args()

    sp = args.skill_path
    plan = load_json(args.plan)
    errs = validate_plan(plan, sp)
    if errs:
        print("PLAN SCHEMA ERRORS:\n  " + "\n  ".join(errs)); sys.exit(2)

    # Layout-library membership check (v9 catalog is the source of truth)
    cat_path = os.path.join(sp, "layouts", "library-v9", "catalog.json")
    if os.path.exists(cat_path):
        known = {it["id"] for it in load_json(cat_path).get("layouts", [])}
        known.add("custom")
        unknown = sorted({s["layout"]["family"] for s in plan.get("slides", []) if s.get("layout", {}).get("family") not in known})
        if unknown:
            print("  [warn] layout ids not in library-v9 catalog (allowed but unverified): " + ", ".join(unknown))

    slides_html = read(args.slides)
    theme = plan["deck"].get("theme", "dark")
    title = plan["deck"]["title"]
    plan_rev = plan.get("plan_revision", 0)

    # Verbatim-locked reference reuse: swap in exec-approved locked renders (theme-aware)
    # before any other injection so those slides stay untouched (they carry their own chrome).
    slides_html = inject_reference_renders(slides_html, plan, sp, theme)

    tokens = load_json(os.path.join(sp, "assets", "tokens", "tokens.json"))
    resolved = list(plan.get("resolved_assets", []))
    slides_html = inject_logos(slides_html, sp, resolved, brand=args.brand)
    slides_html = inject_icons(slides_html, sp, resolved)
    slides_html = finalize_image_slots(slides_html, sp)   # P2/P3: frameless-contain for cut-outs
    # Per-slot image decisions recorded in the plan (image_intent.resolved). Owned images still
    # win inside inject_images; these only cover slots with no owned match (the Unsplash picks).
    img_choices = {}
    for sl in plan.get("slides", []):
        ii = sl.get("image_intent") or {}
        if ii.get("tag") and ii.get("resolved"):
            img_choices.setdefault(ii["tag"], ii["resolved"])
    slides_html = inject_images(slides_html, sp, resolved, brand=args.brand, img_choices=img_choices)
    extra_css = ""
    if args.brand:
        extra_css += footer_logo_css(sp, resolved)
        slides_html = inject_chrome(slides_html, plan, catalog_by_id(sp))  # role-aware footer logo + page number

    css_head = font_css(sp) + token_css(tokens) + read(os.path.join(sp, "frontend", "base.css")) + extra_css
    deck_js = read(os.path.join(sp, "frontend", "deck.js"))
    ui_common = read(os.path.join(sp, "frontend", "ui.common.html"))
    ui_review = read(os.path.join(sp, "frontend", "ui.review.html"))

    # Theme lock (decided during REFINE): once deck.theme_locked is true, the deck ships
    # as the single decided theme - drop the light/dark toggle so there is only one stored
    # version and nothing to switch. EXPORT then uses deck.theme with no prompt.
    if plan["deck"].get("theme_locked"):
        ui_common = re.sub(r'<button id="theme-btn".*?</button>\s*', "", ui_common, flags=re.S)

    # Sources: dedupe resolved assets that carry provenance worth listing
    sources = [{"kind": a.get("kind"), "source": a.get("source"), "author": a.get("author", ""),
                "license": a.get("license", ""), "link": a.get("link", "")}
               for a in resolved if a.get("requires_attribution") or a.get("kind") in ("image", "icon")]
    needs_attr = any(a.get("requires_attribution") for a in resolved)

    # Sources button: forced when attribution required; else present but off-by-default
    ui_common_pres = ui_common
    if not needs_attr and not sources:
        ui_common_pres = re.sub(r'<button id="sources-btn".*?</button>', "", ui_common, flags=re.S)
        ui_common_pres = re.sub(r'<aside id="sources-panel".*?</aside>', "", ui_common_pres, flags=re.S)

    # Per-slide light/dark "main version" choice (recorded via the review Slide Board).
    # Stamp data-variant on the matching <section> so BOTH review and presentation honour
    # it, and hand the same map to the review board as window.__VARIANTS__ so its state seeds
    # consistently (the board's localStorage overrides it during an in-session review).
    variants = {}
    for sl in plan.get("slides", []):
        vc = sl.get("variant_choice")
        if vc in ("light", "dark"):
            variants[sl["slide_uuid"]] = vc
    for suid, vc in variants.items():
        slides_html = re.sub(
            r'(<section class="slide"[^>]*\bdata-slide="' + re.escape(suid) + r'")([^>]*>)',
            lambda m, vc=vc: m.group(1) + ' data-variant="' + vc + '"' + m.group(2),
            slides_html, count=1)

    annotations = []
    for sl in plan.get("slides", []):
        for p in sl.get("pins", []):
            annotations.append({**p, "slide_uuid": sl["slide_uuid"]})

    _stage_no = plan.get("stage")
    _stage_name = STAGE_NAMES.get(_stage_no or 0, "")

    # Review-only "spare" placeholder slide. It starts parked in the Slide Board's
    # "Not used" section (data-placeholder → the board seeds it removed-by-default) so
    # the reviewer always has an empty slide to drag INTO the deck when they want to add
    # one. Never injected into presentation.html, so the client deck / PPTX export are
    # unaffected. Carries a data-block so it satisfies the "no text outside a block" rule.
    placeholder = (
        '<section class="slide" data-slide="placeholder-0000-0000-0000-000000000000" '
        'data-topic="Spare slide" data-placeholder="1"><div class="stage" '
        'style="display:flex;align-items:center;justify-content:center;background:var(--sb-deck-bg)">'
        '<div data-block="placeholder-block-0000" data-block-type="body" '
        'style="text-align:center;font:600 30px Montserrat,sans-serif;color:var(--sb-sky);opacity:.85;padding:0 80px">'
        'Spare slide<br><span style="font-size:18px;font-weight:400;opacity:.8">Drag into the deck to add a new slide</span>'
        '</div></div></section>'
    )
    review_slides = slides_html + placeholder

    # Embed the rendered template library (review-only) so the Template Library button can
    # open it in a new tab. Skipped with --no-library (build_gallery.py's own preview build).
    lib_block = "" if args.no_library else template_library_script(sp)
    review_ui = ui_common + "\n" + ui_review + lib_block

    review = build_page("review", title, review_slides, css_head, review_ui,
                        deck_js, annotations, sources, plan_rev, theme, _stage_no, _stage_name, variants)

    os.makedirs(args.out, exist_ok=True)
    snap_dir = os.path.join(args.out, "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    review_p = os.path.join(args.out, "review.html")
    atomic_write(review_p, review)
    shutil.copy(args.plan, os.path.join(snap_dir, "plan.r%d.json" % plan_rev))

    artifacts = {"review.html": {"path": review_p, "sha256_16": sha(review)}}

    # The clean client presentation.html is opt-in — the working loop only needs review.html.
    # EXPORT / client hand-off pass --presentation to also emit it.
    pres_p = None
    if args.presentation:
        presentation = build_page("presentation", title, slides_html, css_head,
                                  ui_common_pres + chr(10) + ui_review,
                                  deck_js, [], sources, plan_rev, theme, _stage_no, _stage_name, variants)
        pres_p = os.path.join(args.out, "presentation.html")
        atomic_write(pres_p, presentation)
        artifacts["presentation.html"] = {"path": pres_p, "sha256_16": sha(presentation)}

    manifest = {
        "plan_revision": plan_rev,
        "schema_version": plan.get("schema_version"),
        "token_version": tokens.get("token_version"),
        "engine": "build.py v5",
        "fidelity": "brand" if args.brand else "light",
        "audience": plan["deck"].get("audience"),
        "cdn_allowlist": CDN_ALLOWLIST,
        "artifacts": artifacts,
        "resolved_assets": resolved,
        "sources_forced_visible": needs_attr,
        # Per-slide record of the template id + version this deck CONSUMED, plus any
        # reference-library provenance carried on the slide. Stamps what was rendered
        # so a later stage-gated master bump never silently alters an in-flight deck.
        "slides": slide_provenance(plan, catalog_by_id(sp)),
    }
    atomic_write(os.path.join(args.out, "run-manifest.json"), json.dumps(manifest, indent=2))

    # (Re)generate the deck's double-click live-editor launcher (SKILL.md: "Edit Deck.command")
    # on every build, so the launcher always exists and always carries current absolute paths.
    try:
        from edit_server import write_edit_command
        write_edit_command(os.path.abspath(args.plan), os.path.abspath(args.out))
    except Exception:
        pass  # never let launcher generation break a build

    if pres_p:
        print("Built (%s fidelity): %s (%d KB), %s (%d KB)" % (
            manifest["fidelity"], review_p, len(review) // 1024, pres_p, len(presentation) // 1024))
    else:
        print("Built (%s fidelity): %s (%d KB) [review only; pass --presentation for the client deck]" % (
            manifest["fidelity"], review_p, len(review) // 1024))


if __name__ == "__main__":
    main()
