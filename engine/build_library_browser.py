"""
Build the unified SmartBuild slide library browser: ONE file, TWO libraries.

  Library 1  "Layout Templates"        — the v9 master (empty layout shells; how a slide
                                          is arranged). Embedded from the master HTML.
  Library 2  "Existing Finished Slides" — exec-approved, verbatim-locked finished slides
                                          rendered properly (light/dark toggle). From the
                                          reference-library renders.

A top switch flips between the two; the finished library has its own light/dark toggle.
Regenerate whenever the master or the reference renders change:

    python engine/build_library_browser.py \
        --master "<...>/smartbuild_slide_template_library_v9.html"

Output: layouts/library-v9/library.html  (self-contained).
"""
import argparse, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REFDIR = os.path.join(SKILL, "layouts", "reference-library")
LIBV9 = os.path.join(SKILL, "layouts", "library-v9")
DEFAULT_MASTER = r"C:\Users\rowan\OneDrive - SMARTBUILD Construction Solutions\Documents\1. Personal\Files\smartbuild_slide_template_library_v9.html"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def split_master(html):
    """Return (styles, body_inner) from the master HTML."""
    styles = "\n".join(re.findall(r"<style[^>]*>.*?</style>", html, re.S | re.I))
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else html
    return styles, body


def finished_cards():
    """Cards for every reference-library entry with a verbatim-locked render."""
    cat = json.load(open(os.path.join(REFDIR, "catalog.json"), encoding="utf-8"))
    cards, n = [], 0
    for e in cat.get("entries", []):
        render = e.get("render") or {}
        if e.get("render_mode") != "verbatim-locked" or not render:
            continue
        light = render.get("light"); dark = render.get("dark")
        lh = read(os.path.join(REFDIR, light)) if light and os.path.exists(os.path.join(REFDIR, light)) else ""
        dh = read(os.path.join(REFDIR, dark)) if dark and os.path.exists(os.path.join(REFDIR, dark)) else ""
        badge = "canonical · locked" if e.get("canonical") else "locked"
        cards.append(
            '<figure class="fs-card">'
            '<div class="fs-thumb">'
            '<div class="stage fs-v fs-light">%s</div>'
            '<div class="stage fs-v fs-dark">%s</div>'
            '</div>'
            '<figcaption><span class="fs-title">%s</span>'
            '<span class="fs-role">%s</span><span class="fs-badge">%s</span></figcaption>'
            '</figure>' % (lh, dh, e.get("title", e["ref_id"]), e.get("role", ""), badge))
        n += 1
    # note the text-only (not yet rendered) entries
    text_only = [e for e in cat.get("entries", []) if e.get("render_mode") != "verbatim-locked"]
    return cards, n, len(text_only)


CSS = """
/* Library browser must scroll as a normal document. base.css (injected for the
   finished-slide .stage renders) sets html,body{height:100%;overflow:hidden} for the
   fixed-canvas DECK — that clamp hides everything past slide ~8 here. Undo it. */
html,body{height:auto !important;min-height:100%;overflow:auto !important}
:root{--ink:#0b2a4a;--sky:#61CEFF;--navy:#0B1E3A;}
#lib-switch{position:sticky;top:0;z-index:9999;display:flex;gap:8px;align-items:center;
  padding:12px 20px;background:#0b1e3a;color:#fff;font-family:Montserrat,system-ui,sans-serif;box-shadow:0 2px 12px rgba(0,0,0,.3)}
#lib-switch b{margin-right:12px;letter-spacing:.04em}
#lib-switch button{font:600 13px Montserrat,system-ui,sans-serif;border:0;border-radius:8px;padding:8px 14px;cursor:pointer;
  background:#1c3a63;color:#cfe4ff}
#lib-switch button.active{background:var(--sky);color:#04223d}
#lib-switch .spacer{flex:1}
#lib-switch .theme{background:transparent;border:1px solid #33557f;color:#cfe4ff}
#lib-templates,#lib-finished{display:none}
body[data-lib="templates"] #lib-templates{display:block}
body[data-lib="finished"] #lib-finished{display:block}
#lib-finished{background:#eef2f6;min-height:100vh;padding:26px 30px;font-family:Montserrat,system-ui,sans-serif}
#lib-finished h1{color:var(--ink);font-size:22px;margin:0 0 4px}
#lib-finished .sub{color:#5b6b7d;font-size:13px;margin:0 0 22px}
.fs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(372px,1fr));gap:26px}
.fs-card{background:#fff;border-radius:12px;box-shadow:0 6px 24px rgba(10,30,60,.12);overflow:hidden;margin:0}
.fs-thumb{position:relative;width:100%;aspect-ratio:16/9;overflow:hidden;background:#000}
.fs-thumb .stage{position:absolute;top:0;left:0;transform:scale(.29);transform-origin:top left}
body[data-fstheme="light"] .fs-dark{display:none}
body[data-fstheme="dark"] .fs-light{display:none}
.fs-card figcaption{display:flex;align-items:center;gap:8px;padding:12px 14px}
.fs-title{font-weight:700;color:var(--ink);font-size:14px;flex:1}
.fs-role{font-size:11px;color:#7488a0;text-transform:uppercase;letter-spacing:.08em}
.fs-badge{font-size:10px;font-weight:700;color:#04223d;background:var(--sky);border-radius:999px;padding:3px 9px}
"""

JS = """
function showLib(n){document.body.dataset.lib=n;
  document.getElementById('btn-t').classList.toggle('active',n==='templates');
  document.getElementById('btn-f').classList.toggle('active',n==='finished');}
function toggleFsTheme(){var b=document.body;b.dataset.fstheme=(b.dataset.fstheme==='dark'?'light':'dark');
  document.getElementById('fs-theme').textContent=(b.dataset.fstheme==='dark'?'\\u25D1 Dark':'\\u25D0 Light');}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", default=DEFAULT_MASTER)
    ap.add_argument("--out", default=os.path.join(LIBV9, "library.html"))
    args = ap.parse_args()

    if not os.path.exists(args.master):
        raise SystemExit("Master library not found: %s" % args.master)
    styles, body = split_master(read(args.master))
    base_css = read(os.path.join(SKILL, "frontend", "base.css"))
    cards, n_fin, n_text = finished_cards()

    tmpl_count = len(re.findall(r'\bDrop-in\b|\btemplate\b', body)) or "105"
    switch = (
        '<div id="lib-switch"><b>SmartBuild Slide Library</b>'
        '<button id="btn-t" class="active" onclick="showLib(\'templates\')">Layout Templates</button>'
        '<button id="btn-f" onclick="showLib(\'finished\')">Existing Finished Slides (%d)</button>'
        '<span class="spacer"></span>'
        '<button id="fs-theme" class="theme" onclick="toggleFsTheme()">◑ Dark</button></div>' % n_fin)

    finished = (
        '<section id="lib-finished"><h1>Existing Finished Slides</h1>'
        '<p class="sub">Exec-approved, review-passed slides — reused <b>verbatim</b> (word / image / style-for-style). '
        'Template is locked; only the underlying image swaps with the theme. %d rendered here · %d more available as text reuse.</p>'
        '<div class="fs-grid">%s</div></section>' % (n_fin, n_text, "\n".join(cards)))

    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>SmartBuild Slide Library — Templates + Finished</title>'
        '%s\n<style>%s\n%s</style></head>'
        '<body data-lib="templates" data-fstheme="dark">%s'
        '<section id="lib-templates">%s</section>%s'
        '<script>%s</script></body></html>'
    ) % (styles, base_css, CSS, switch, body, finished, JS)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote %s (%.1f MB) — Templates + %d finished slides (%d text-only)"
          % (args.out, len(html) / 1e6, n_fin, n_text))


if __name__ == "__main__":
    main()
