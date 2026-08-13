"""
SmartBuild Deck v5 — validate.py  (SWEEP: deterministic gate)

Two tiers here, and they must never bleed into each other:

  1. HARD-FAIL checks (run_checks) — black-and-white mechanical contract.
     These set the exit code and drive the BRAND<->SWEEP auto-fix loop.
  2. DETERMINISTIC ADVISORIES (drift_advisories) — computed, not judged, but
     NON-blocking. Right now: library-drift detection. An advisory NEVER
     changes the exit code; it escalates to the human, it does not fail.

Editorial judgement (clarity, layout variety, icon relevance, concept
consistency) is a THIRD thing — handled by Claude, not in here, by design
(keeps the auto-fix loop from thrashing on taste).

Library-drift detection
-----------------------
A slide/block pulled from the published master template library carries a
`provenance` stamp (the linking pass writes it; schema owns its shape):

    "provenance": { "source": "reference-library", "ref_id": "REF-xyz",
                    "ref_version": "<n>", "blocks_hash": "sha256:<hash>" }

`blocks_hash` is the canonical content hash AT PULL TIME (written by
reference_search.inline_provenance). On every SWEEP we recompute the current
content hash and, on mismatch, emit an ADVISORY asking whether to bank the edit
back to the library via the gate. The active deck is free to edit — divergence is
expected, so this is advisory ONLY, never a fail. The stamping side
(reference_search.blocks_hash) and this side (_reuse_content_hash) MUST use an
identical recipe or every reuse reads as drift.

Usage:
    python validate.py --skill-path <dir> --plan plan.json --out <build-dir> [--strict-sri]
Exit 0 = all deterministic HARD-FAIL checks pass; 1 = one or more failed.
        (Advisories are printed but do not affect the exit code.)
"""
import argparse, hashlib, json, os, re, sys
from html.parser import HTMLParser


class _OrphanTextFinder(HTMLParser):
    """Find VISIBLE authored text that sits OUTSIDE any [data-block] element (RC8b).
    Walks authored slide sections only (reference sections are pre-stripped by the
    caller), tracking data-block depth, aria-hidden/script/style/chrome subtrees to
    exclude, so the exporter never has to guess at un-tagged words."""
    CHROME = {"sb-page-num", "sb-footer-logo", "sb-watermark", "sb-stage-badge", "sb-review-chip"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.block_depth = None      # depth at which we entered a data-block
        self.skip_depth = None       # depth at which we entered a skipped subtree
        self.orphans = []

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        # data-logo/data-image are ASSET slots (a light-fidelity placeholder renders its tag
        # name as text) — not authored copy, so they don't need a data-block.
        skip = (tag in ("script", "style") or a.get("aria-hidden") == "true"
                or (cls & self.CHROME) or "data-logo" in a or "data-image" in a)
        if self.skip_depth is None and skip:
            self.skip_depth = self.depth
        if self.block_depth is None and "data-block" in a:
            self.block_depth = self.depth

    def handle_endtag(self, tag):
        if self.skip_depth is not None and self.depth <= self.skip_depth:
            self.skip_depth = None
        if self.block_depth is not None and self.depth <= self.block_depth:
            self.block_depth = None
        self.depth -= 1

    def handle_data(self, data):
        if self.skip_depth is not None or self.block_depth is not None:
            return
        if re.search(r"[A-Za-z0-9]", data):        # a real word/number, not a decorative glyph
            self.orphans.append(re.sub(r"\s+", " ", data).strip()[:50])


def authored_text_outside_datablock(review_html):
    """Return orphan-text snippets across all AUTHORED sections (reference sections
    already stripped). Empty list == every visible word is inside a data-block."""
    finder = _OrphanTextFinder()
    finder.feed(review_html)
    return finder.orphans

def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

# --- canonical content hashing (shared contract with the library-linking pass) ---
# Hash the AUTHORED CONTENT only: identity (uuids), lifecycle (status), pin
# metadata, display index and the provenance stamp itself are all excluded, so
# a reorder/insert/re-pin does NOT read as drift — only a change to what the
# slide/block actually says does. sha256[:16] matches build.py's sha().

def _reuse_content_hash(content_blocks):
    """Drift hash: sha256:16 over active block TEXTS only. MUST stay byte-identical to
    reference_search.blocks_hash (the reuse stamp is written with that; SWEEP re-checks
    with this — they have to agree or every reuse reads as drift). Text-only by design:
    layout/topic tweaks are not 'content drift from master', and approved-fact edits are
    already caught by the fidelity gate."""
    parts = [(b.get("text") or "").strip() for b in (content_blocks or [])
             if b.get("status", "active") != "deleted"]
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def drift_advisories(plan):
    """Deterministic ADVISORIES (never hard-fail): flag provenance-stamped
    slides/blocks whose current content no longer matches the published master
    they were pulled from. Returns a list of advisory dicts."""
    advisories = []
    for sl in plan.get("slides", []):
        if sl.get("status") == "deleted":
            continue
        prov = sl.get("provenance")
        if not isinstance(prov, dict):
            continue
        orig = prov.get("blocks_hash")
        if not orig:                                    # no baseline stamped => skip (back-compat)
            continue
        current = _reuse_content_hash(sl.get("content_blocks", []))
        if current == orig:
            continue
        ref = prov.get("ref_id", "REF-?")
        ver = prov.get("ref_version", "?")
        advisories.append({
            "kind": "slide", "uuid": sl.get("slide_uuid"), "ref": ref, "version": ver,
            "original_hash": orig, "current_hash": current,
            "message": "diverges from published master %s v%s — bank as a library update via the gate?" % (ref, ver),
        })
    return advisories

def _hex_norm(h):
    h = h.lstrip("#").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h


def _palette(skill_path):
    """Every brand/theme/status/neutral hex the deck is allowed to paint with (RC6)."""
    toks = load_json(os.path.join(skill_path, "assets", "tokens", "tokens.json"))
    allowed = set()
    for v in toks.get("brand", {}).values():
        allowed.add(_hex_norm(v))
    for v in toks.get("product_accents", {}).values():
        allowed.add(_hex_norm(v))
    for v in toks.get("status", {}).values():
        allowed.add(_hex_norm(v))
    for grp in toks.get("color", {}).values():
        for v in grp.values():
            allowed.add(_hex_norm(v))
    # neutral ramp baked into build.py's token_css (panels, ink) + pure black/white
    allowed.update({"ffffff", "000000", "0d1829", "080f1e", "f5f8fc", "060c1a", "0b1e3a", "0b2a4a"})
    return allowed


def palette_advisories(skill_path, review_html):
    """RC6 brand-colour governance: extract EVERY colour painted in the deck region —
    inline style="" attrs, <style> blocks, AND svg stroke/fill attrs — and flag any that
    isn't in the token palette. This closes the hole where an off-palette colour injected
    via a <style> block (the yellow-icon demo) sailed past the inline-only raw-hex check.
    Editorial ADVISORY only (never hard-fails — a designer may be intentional). Reference-
    locked slides are exec-approved and exempt (their sections are pre-stripped by caller)."""
    allowed = _palette(skill_path)
    counts = {}
    for m in re.finditer(r'#[0-9a-fA-F]{3,6}\b', review_html):
        h = _hex_norm(m.group(0))
        if len(h) != 6:
            continue
        if h in allowed:
            continue
        # tolerance: skip colours within a few levels of an allowed token (anti-aliasing/noise)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        near = any(abs(r - int(a[0:2], 16)) + abs(g - int(a[2:4], 16)) + abs(b - int(a[4:6], 16)) <= 12 for a in allowed)
        if near:
            continue
        counts[h] = counts.get(h, 0) + 1
    return [{"hex": "#" + h, "count": c} for h, c in sorted(counts.items(), key=lambda kv: -kv[1])]


def deck_region(html):
    i = html.find('<div class="deck">')
    j = html.find('</div>\n', i)
    # crude but fine: take from deck open to the fixed-UI marker
    k = html.find('<div id="nav-dots">')
    return html[i:k] if (i >= 0 and k > i) else html

def run_checks(skill_path, plan, out_dir, strict_sri=False):
    review = read(os.path.join(out_dir, "review.html"))
    # presentation.html is opt-in (EXPORT/client only) — the working loop is review-only.
    # Presentation-specific checks run ONLY when it exists; SWEEP never forces its creation.
    _pres_path = os.path.join(out_dir, "presentation.html")
    pres = read(_pres_path) if os.path.exists(_pres_path) else None
    manifest = load_json(os.path.join(out_dir, "run-manifest.json"))
    body = deck_region(review)
    # Verbatim-locked reference slides are exec-approved reproductions: they legitimately
    # carry exact hex colours and aren't tagged like authored slides. Exclude their sections
    # from the authored-content checks (data-slide/data-block/raw-hex).
    body = re.sub(r'<section[^>]*\bdata-reference=[^>]*>.*?</section>', ' ', body, flags=re.S | re.I)
    checks = []

    def chk(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    # 1. Fixed 16:9 canvas
    chk("Fixed 1280x720 stage present", ".stage" in review and "width: 1280px" in review)
    # 2. Single scroll container
    chk("Single .deck scroll container", review.count('<div class="deck">') == 1 and "scroll-snap-type: y mandatory" in review)
    # 3. Every slide carries data-slide; content blocks carry data-block
    slide_ids = re.findall(r'data-slide="([^"]+)"', body)
    chk("Slides tagged with data-slide", len(slide_ids) >= 1, "%d slides" % len(slide_ids))
    block_ids = set(re.findall(r'data-block="([^"]+)"', body))
    chk("Content blocks tagged with data-block", len(block_ids) >= 1, "%d blocks" % len(block_ids))
    # 4. Every pin resolves to a real block
    unresolved = []
    for sl in plan.get("slides", []):
        for p in sl.get("pins", []):
            if p.get("block_uuid") and p["block_uuid"] not in block_ids:
                unresolved.append(p.get("pin_id"))
    chk("All pins resolve to a data-block", not unresolved, ("unresolved: " + ",".join(map(str, unresolved))) if unresolved else "")
    # 5. Token drift — renderers must paint with var(--sb-*) tokens, never raw hex. The ONE
    # allowed exception is a BRAND-PALETTE hex applied by the live rich-text editor (accent
    # emphasis colours are theme-invariant, so an inline brand hex is legitimate). Any
    # OFF-palette raw hex still hard-fails.
    _allowed_hex = _palette(skill_path)
    raw_hex = [h for h in re.findall(r'style="[^"]*?(#[0-9a-fA-F]{3,6})\b', body) if _hex_norm(h) not in _allowed_hex]
    chk("No off-palette raw hex in authored slides (use tokens)", not raw_hex, ("found: " + ",".join(set(raw_hex))) if raw_hex else "")
    # 5b. RC8b: every visible word in an authored slide sits inside a [data-block].
    #     Text outside a data-block is fragile at export (the exporter has an orphan
    #     safety net, but authored decks must be structurally sound first).
    orphans = authored_text_outside_datablock(body)
    chk("No authored text outside a data-block (RC8b)", not orphans,
        ("orphan text: " + "; ".join(orphans[:6])) if orphans else "")
    # 5c. Brand voice — NEVER em/en dashes in VISIBLE authored copy (SmartBuild rule: use a
    #     hyphen). Scan text only — strip HTML comments + tags first so em dashes in metadata
    #     (data-topic attributes, authoring comments) aren't flagged; only rendered copy counts.
    #     Reference slides are exec-approved and already stripped from `body` above.
    _visible = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    _visible = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", " ", _visible, flags=re.S | re.I)
    _visible = re.sub(r"<[^>]+>", " ", _visible)
    dash_hits = [re.sub(r"\s+", " ", m.group(0)).strip()
                 for m in re.finditer(r".{0,18}[—–].{0,18}", _visible)]
    chk("No em/en dashes in authored copy (use a hyphen)", not dash_hits,
        ("found: " + " | ".join(dash_hits[:4])) if dash_hits else "")
    # 5d. Icons resolve — a leftover <svg class="icon" data-icon="NAME"> means NAME is not in
    #     the catalog (inject_icons couldn't swap it), so it renders blank: the "junk icon"
    #     failure mode. Topic-relevance of resolved icons stays an editorial judgement.
    unresolved_icons = re.findall(r'<svg class="icon" data-icon="([^"]+)"', body)
    chk("All icons resolve to a catalog icon", not unresolved_icons,
        ("unknown: " + ",".join(sorted(set(unresolved_icons)))) if unresolved_icons else "")
    # 5e. Image slots must be formatted to fill without distortion. Any resolved <img data-image>
    #     must carry img-cover or an explicit object-fit (build.py adds img-cover automatically;
    #     this catches an authored slot that set its own class but forgot object-fit).
    img_tags = re.findall(r'<img\b[^>]*\bdata-image="[^"]*"[^>]*>', body)
    unformatted = [t for t in img_tags if "img-cover" not in t and "object-fit" not in t]
    chk("Image slots formatted (object-fit:cover)", not unformatted,
        ("%d image slot(s) missing img-cover/object-fit" % len(unformatted)) if unformatted else "")
    # 5f. THEME LEGIBILITY — the deck can be viewed in light OR dark, so fixed near-white text
    #     must sit on a dark/media backdrop or it vanishes in light mode (the recurring
    #     light-mode illegibility bug). Per authored section: if a data-block uses a near-white
    #     text colour and the section has NO dark backdrop (photo, scrim gradient, accent/dark
    #     fill, or an .on-media wrapper), FAIL. On-background text must use theme-aware tokens
    #     (--sb-title / --sb-text-on-dark / --sb-body-on-dark / --sb-text-primary).
    _WHITE = re.compile(r'color:\s*(#fff\b|#ffffff\b|white\b|var\(--sb-on-accent\)|rgba\(\s*255\s*,\s*255\s*,\s*255)', re.I)
    _DARKBG = re.compile(r'data-image=|linear-gradient\(|\bon-media\b|background:\s*var\(--sb-(navy|sky|copper|steel|pink|ink)\)|background:\s*#0[0-9a-f]', re.I)
    illegible = []
    for sec in re.findall(r'<section\b.*?</section>', body, re.S | re.I):
        if _DARKBG.search(sec):
            continue
        for mm in re.finditer(r'<[^>]*\bdata-block="[^"]*"[^>]*\bstyle="([^"]*)"[^>]*>', sec):
            if _WHITE.search(mm.group(1)):
                tp = re.search(r'data-topic="([^"]*)"', sec)
                illegible.append(tp.group(1) if tp else "?")
                break
    chk("Text legible in light mode (white text only on a dark/media backdrop)", not illegible,
        ("fixed-white text off a backdrop on: " + ", ".join(illegible[:5]) + " — use a theme-aware token or an .on-media backdrop") if illegible else "")
    # 5g. Brand slogan spelling — the canonical slogan is "Work smrter, not harder." (SMRTER).
    bad_slogan = re.search(r'work\s+smarter', _visible, re.I)
    chk('Slogan spelled "smrter" (brand)', not bad_slogan,
        'found "Work smarter" — the SmartBuild slogan is "Work smrter, not harder."' if bad_slogan else "")
    # 5h. Display/hero text on a light canvas must be BRAND NAVY, not near-black. Large text
    #     (>=36px) that hard-codes a near-black on-background colour reads flat/off-brand in
    #     light mode; use var(--sb-title) (or .hl) which is navy on light and white on dark.
    big_flat = []
    for mm in re.finditer(r'<[^>]*\bdata-block="[^"]*"[^>]*\bstyle="([^"]*)"[^>]*>', body):
        st = mm.group(1)
        fs = re.search(r'font-size:\s*(\d+)px', st)
        if fs and int(fs.group(1)) >= 36 and re.search(
                r'color:\s*(var\(--sb-text-on-dark\)|var\(--sb-text-primary\)|#0f1419|#000\b|#000000\b|black\b)', st, re.I):
            big_flat.append(fs.group(1) + "px")
    chk("Display text uses brand navy on light (var(--sb-title))", not big_flat,
        ("near-black display text (%s) — use var(--sb-title)/.hl so hero text is navy on white" % ", ".join(big_flat[:4])) if big_flat else "")
    # 6. No inline event handlers anywhere (CSP)
    handlers = re.findall(r'\son[a-z]+="', review)
    chk("No inline event handlers", not handlers, ("found %d" % len(handlers)) if handlers else "")
    # 7. No <script> inside the deck region
    chk("No script tags inside slides", "<script" not in body)
    # 8. CSP meta present
    chk("CSP meta present", "Content-Security-Policy" in review and (pres is None or "Content-Security-Policy" in pres))
    # 9. Headline uppercasing rule present
    chk("Headline uppercase rule present", "text-transform: uppercase" in review)
    # 10. Client license gate
    audience = plan.get("deck", {}).get("audience")
    if audience == "client":
        assets = plan.get("resolved_assets", [])
        bad = [a.get("asset_id") for a in assets if not a.get("approved_for_client")]
        chk("Client license gate (all assets approved_for_client)", not bad, ("not approved: " + ",".join(map(str, bad))) if bad else "")
        if strict_sri:
            missing = [k for k, v in manifest.get("cdn_allowlist", {}) if False]  # placeholder
    # 11-12. Presentation-only checks — run ONLY when presentation.html was built (EXPORT).
    if pres is not None:
        if manifest.get("sources_forced_visible"):
            chk("Sources forced visible in presentation.html", 'id="sources-btn"' in pres)
        chk("presentation.html includes the notes affordance", 'id="edit-toggle"' in pres and 'id="pin-popup"' in pres)

    # 13. Logos actually embedded (brand builds only — light fidelity uses placeholders on purpose)
    if manifest.get("fidelity") == "brand":
        logo_imgs = re.findall(r'<img[^>]*data-logo="[^"]*"[^>]*>', review)
        broken = [t for t in logo_imgs if 'src="data:' not in t]
        chk("All authored logos embedded (brand)", not broken, ("%d unresolved logo(s)" % len(broken)) if broken else ("%d logo(s) embedded" % len(logo_imgs)))
        # No unresolved image slots at brand. inject_images emits an <img data-image> when an
        # asset resolves and a <span data-image> PLACEHOLDER when nothing matches — that
        # placeholder is the dead grey slab of a template forced onto content with no image.
        # At brand every declared image slot must resolve (or the slide should not reserve one).
        img_slabs = re.findall(r'<span[^>]*\bdata-image="([^"]+)"', body)
        chk("No unresolved image slots (brand)", not img_slabs,
            ("unresolved: " + ",".join(sorted(set(img_slabs))) + " — supply an owned image or use a text layout") if img_slabs else "")
        # Chrome counts: the cover (first slide) is unnumbered and gets no chrome. Every other
        # slide gets a PAGE NUMBER. It also gets a FOOTER LOGO *unless* it already carries its
        # own SmartBuild mark (closing badge / hero wordmark) — the brand rule is at most ONE
        # SmartBuild logo per slide. So expected page-nums == (#slides - 1), and expected
        # footer-logos == (non-cover slides that don't already carry their own mark).
        # Tombstoned slides (status:"deleted") stay in the plan for pin resolution but are
        # never rendered — chrome expectations must count LIVE slides only.
        n_slides = len([s for s in plan.get("slides", []) if s.get("status") != "deleted"])
        exp_num = max(0, n_slides - 1)
        slide_parts = [p for p in re.split(r'(?=<section class="slide")', review)
                       if p.lstrip().startswith("<section") and "data-placeholder" not in p]
        def _own_logo(p):
            return ('data-logo="smartbuild"' in p) or ('data-logo="smartbuild-badge"' in p)
        exp_footer = sum(1 for p in slide_parts[1:] if not _own_logo(p))   # drop the cover
        footer = review.count('class="sb-footer-logo"')
        chk("Footer logo on non-cover slides w/o their own mark (brand)", footer == exp_footer, "%d/%d" % (footer, exp_footer))
        pnums = review.count('class="sb-page-num"')
        chk("Page number on every non-cover slide (brand)", pnums == exp_num, "%d/%d" % (pnums, exp_num))
        # Brand rule: NEVER more than one SmartBuild logo mark on a single slide.
        over = []
        for i, p in enumerate(slide_parts):
            n = (p.count('class="sb-footer-logo"') + p.count('data-logo="smartbuild"')
                 + p.count('data-logo="smartbuild-badge"'))
            if n > 1:
                over.append(i + 1)
        chk("At most one SmartBuild logo per slide (brand)", not over,
            ("slides with >1 logo: " + ",".join(map(str, over))) if over else "")
        # Hero imagery — the cover (first slide) and closing (last slide) must carry a real
        # image, not a bare geometric/blank hero (recurring "no photo on the hero/closing" note).
        sl_list = plan.get("slides", [])
        missing_hero = []
        for role, sl in ([("cover", sl_list[0])] if sl_list else []) + ([("closing", sl_list[-1])] if len(sl_list) > 1 else []):
            m = re.search(r'<section[^>]*data-slide="' + re.escape(sl.get("slide_uuid", "")) + r'".*?</section>', review, re.S)
            if "data-image=" not in (m.group(0) if m else ""):
                missing_hero.append(role)
        chk("Hero imagery on cover + closing (brand)", not missing_hero,
            ("no image on: " + ", ".join(missing_hero) + " — every hero/closing needs an image") if missing_hero else "")

    return checks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--strict-sri", action="store_true")
    args = ap.parse_args()
    plan = load_json(args.plan)
    checks = run_checks(args.skill_path, plan, args.out, args.strict_sri)
    passed = sum(1 for _, ok, _ in checks if ok)
    print("SWEEP (deterministic): %d/%d passed\n" % (passed, len(checks)))
    for name, ok, detail in checks:
        print(("  OK   " if ok else "  FAIL ") + name + (("  — " + detail) if detail else ""))

    # Deterministic advisories — surfaced, never blocking (do NOT touch exit code).
    advisories = drift_advisories(plan)
    if advisories:
        print("\nSWEEP advisories (%d) — informational, do not block:" % len(advisories))
        for a in advisories:
            print("  ADVISORY %s %s — %s" % (a["kind"], a["uuid"], a["message"]))

    # RC6 brand-palette guard (all CSS, not just inline) — editorial advisory, never blocks.
    review = read(os.path.join(args.out, "review.html"))
    authored = re.sub(r'<section[^>]*\bdata-reference=[^>]*>.*?</section>', ' ', deck_region(review), flags=re.S | re.I)
    palette = palette_advisories(args.skill_path, authored)
    if palette:
        print("\nSWEEP palette advisories (%d off-palette colour[s]) — informational, do not block:" % len(palette))
        for a in palette:
            print("  ADVISORY off-palette colour %s (%d element[s]) — intended? use a brand token or bank the change."
                  % (a["hex"], a["count"]))

    # Export-safety advisories (TKMS lessons, 2026-08) — patterns that render fine in the
    # browser but break or distort in the PPTX/PDF exporters. Informational, never block.
    exp = []
    if re.search(r'<img[^>]*style="[^"]*transform:\s*scale', authored):
        exp.append("transform:scale on an <img> — the exporter scales WITHOUT container clipping, so the "
                   "image bleeds past its panel. Pre-crop the asset (alpha-trim) instead.")
    for m in re.finditer(r'<(?:div|span)[^>]*style="[^"]*transform:\s*rotate\([^)]*\)[^"]*"[^>]*>', authored):
        tag = m.group(0)
        if 'data-block' in tag:
            continue
        # Only SMALL rotated marks are the proven failure class (border-trick chevrons
        # export as corner brackets). Large rotated outlines (cover motifs) export fine.
        wh = re.search(r'width:\s*(\d+)px', tag)
        if wh and int(wh.group(1)) <= 40:
            exp.append("small CSS-rotated decorative mark (%spx) — border/rotate tricks export as stray "
                       "corner brackets. Use an inline-SVG data-URI image instead." % wh.group(1))
            break
    for m in re.finditer(r'<[a-z]+[^>]*data-block="[^"]*"[^>]*style="[^"]*font-size:(1[0-2](?:\.\d)?)px[^"]*"[^>]*>(.*?)</', authored, re.S):
        if m.group(2).count('class="product-name"') >= 2:
            exp.append("small-print block with 2+ product-name spans — wrapped lines containing multiple "
                       "inline spans can merge into one long paragraph at export. Render boilerplate plain-text.")
            break
    if exp:
        print("\nSWEEP export-safety advisories (%d) — informational, do not block:" % len(exp))
        for e in exp:
            print("  ADVISORY " + e)

    sys.exit(0 if passed == len(checks) else 1)

if __name__ == "__main__":
    main()
