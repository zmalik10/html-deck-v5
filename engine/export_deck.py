"""
export_deck.py — the ONE export path for a built deck.

Produces PPTX / PDF / HTML exactly the way the author does it by hand, so the in-deck
"Save As" button (which calls this via edit_server.py's /export endpoint) and a manual
CLI export run the SAME pipeline — they can never drift apart.

    python engine/export_deck.py --skill-path . --plan <deck>/plan.json --out <deck>/out \
        --format pptx|pdf|html [--rebuild] [--open] [--theme dark|light]

  --rebuild : re-render slides.html from plan.json, then BUILD --brand --presentation, so the
              latest live edits (autosaved into plan.json) are baked into presentation.html
              before exporting. This mirrors the author's own pre-export rebuild.
  --open    : open the produced file in the OS default app (PowerPoint / PDF viewer / browser).
  --theme   : override; otherwise the plan's deck.theme (a theme-locked deck exports as-built).

Prints exactly ONE JSON line on stdout — {ok, format, path, msg} — so the edit server can
parse the result deterministically. Exit code mirrors ok.

Export mechanics, matched to the manual flow:
  • PPTX → engine/export_pptx.py (native python-pptx; copies reference slides, rebuilds
           authored slides as movable objects). Same command the author runs.
  • PDF  → headless Chrome --print-to-pdf of presentation.html (its @page is 1280x720/no-margin,
           so pages come out landscape and full-bleed). Playwright chromium is the fallback.
  • HTML → presentation.html copied to deck.html (the clean, self-contained client file).
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def _emit(ok, fmt, path=None, msg=""):
    """Print the single machine-readable result line and exit."""
    print(json.dumps({"ok": bool(ok), "format": fmt, "path": path, "msg": msg}))
    sys.exit(0 if ok else 1)


def find_chrome():
    try:
        from open_deck import find_chrome as _fc
        c = _fc()
        if c:
            return c
    except Exception:
        pass
    for name in ("chrome", "google-chrome", "google-chrome-stable", "chromium"):
        p = shutil.which(name)
        if p:
            return [p]
    if sys.platform == "darwin":
        cand = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(cand):
            return [cand]
    elif sys.platform.startswith("win"):
        for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")):
            cand = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            if base and os.path.exists(cand):
                return [cand]
    return None


def open_in_app(path):
    """Open the produced file in the OS default app (PowerPoint for .pptx, PDF viewer for .pdf)."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]  # noqa
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def rebuild(py, sp, plan_path, out):
    """Re-render slides.html from the plan, then BUILD --brand --presentation, so
    presentation.html reflects the latest autosaved edits. slides.html is regenerated at
    its conventional location (next to plan.json)."""
    slides = os.path.join(os.path.dirname(plan_path), "slides.html")
    r = subprocess.call([py, os.path.join(HERE, "render_slides.py"),
                         "--skill-path", sp, "--plan", plan_path, "--out", slides])
    if r != 0:
        return False, "render_slides.py failed"
    r = subprocess.call([py, os.path.join(HERE, "build.py"), "--skill-path", sp,
                         "--plan", plan_path, "--slides", slides, "--out", out,
                         "--brand", "--presentation"])
    if r != 0:
        return False, "build.py failed"
    return True, "rebuilt"


def export_pdf(pres, dst):
    """Chrome --print-to-pdf (primary), Playwright chromium (fallback). Returns (ok, msg)."""
    file_url = "file://" + pres
    chrome = find_chrome()
    if chrome:
        base = ["--disable-gpu", "--no-pdf-header-footer",
                "--print-to-pdf=" + dst, "--virtual-time-budget=12000", file_url]
        # newer Chrome wants --headless=new; older only understands --headless. Try both.
        for head in ("--headless=new", "--headless"):
            try:
                subprocess.run(chrome + [head] + base, capture_output=True, text=True, timeout=120)
            except Exception:
                pass
            if os.path.exists(dst):
                return True, "chrome"
    # Fallback: Playwright chromium (same dependency the PPTX path already needs).
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page()
            pg.goto(file_url, wait_until="networkidle")
            pg.pdf(path=dst, width="1280px", height="720px", print_background=True,
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            b.close()
        if os.path.exists(dst):
            return True, "playwright"
    except Exception as e:
        return False, "no Chrome; Playwright fallback errored: %s" % e
    return False, "PDF not produced"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=os.path.dirname(HERE))
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", required=True, choices=["pptx", "pdf", "html"])
    ap.add_argument("--theme", choices=["dark", "light"])
    ap.add_argument("--rebuild", action="store_true",
                    help="re-render + BUILD --brand --presentation first (include latest live edits)")
    ap.add_argument("--open", dest="open_", action="store_true",
                    help="open the produced file in the OS default app")
    args = ap.parse_args()

    py = sys.executable or "python3"
    sp = args.skill_path
    out = os.path.abspath(args.out)
    plan_path = os.path.abspath(args.plan)
    fmt = args.format

    theme = args.theme
    try:
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        theme = theme or plan.get("deck", {}).get("theme", "dark")
    except Exception:
        theme = theme or "dark"

    if args.rebuild:
        ok, msg = rebuild(py, sp, plan_path, out)
        if not ok:
            _emit(False, fmt, None, msg)

    pres = os.path.join(out, "presentation.html")
    if not os.path.exists(pres):
        _emit(False, fmt, None, "presentation.html missing — build with --presentation first")

    if fmt == "html":
        dst = os.path.join(out, "deck.html")
        shutil.copyfile(pres, dst)
        if args.open_:
            open_in_app(dst)
        _emit(True, fmt, dst, "HTML written")

    if fmt == "pptx":
        dst = os.path.join(out, "deck.pptx")
        cmd = [py, os.path.join(HERE, "export_pptx.py"), "--skill-path", sp,
               "--plan", plan_path, "--slides-html", pres, "--out", dst, "--theme", theme]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0 or not os.path.exists(dst):
            _emit(False, fmt, None, "export_pptx.py failed: " + ((p.stderr or p.stdout or "")[-400:]))
        if args.open_:
            open_in_app(dst)
        _emit(True, fmt, dst, "PowerPoint written")

    if fmt == "pdf":
        dst = os.path.join(out, "deck.pdf")
        ok, msg = export_pdf(pres, dst)
        if not ok:
            _emit(False, fmt, None, "PDF export failed (" + msg + ")")
        if args.open_:
            open_in_app(dst)
        _emit(True, fmt, dst, "PDF written")


if __name__ == "__main__":
    main()
