#!/usr/bin/env python3
"""density_check.py — mechanical "no wasted pixel space" gate (house rule, 2026-08).

Renders review.html headless and samples a grid of points across every slide's
1280x720 stage. A sample point counts as FILLED when the element under it is real
content (inside a data-block, an image/logo/svg, or a visibly-elevated card/band);
it counts as EMPTY when it hits the bare stage/section background. The fill score
is the filled fraction of all sampled points.

This is the codified version of the manual screenshot QA that caught the TKMS
wasted-space defects: cards with dead bottoms, half-empty columns, floating logos.

Usage:
    python engine/density_check.py --out <deck>/out [--threshold 0.55] [--strict]

Default is ADVISORY (exit 0, prints per-slide scores + flags). --strict exits 1
when any slide scores below threshold. Cover/closing/full-bleed slides tend to
score high automatically (the photo fills the canvas); a low score on a content
slide means: enlarge type, rebalance copy, or outsource a real element (photo,
logo row, stat chip) into the slack — see SKILL.md "House style".

Requires Playwright (pip install playwright && playwright install chromium).
Degrades with a clear message when unavailable so teammate machines don't break.
"""
import argparse, asyncio, os, sys

GRID_X, GRID_Y = 40, 24          # 960 sample points per slide
PAD = 8                          # skip the outermost pixels (rounded corners, borders)

SAMPLE_JS = """
async (args) => {
  const [gx, gy, pad] = args;
  const stage = document.querySelector('section.slide.__dc_target .stage')
             || document.querySelector('section.slide.__dc_target');
  if (!stage) return null;
  const r = stage.getBoundingClientRect();
  let filled = 0, total = 0;
  const isContent = (el) => {
    if (!el || el === document.documentElement || el === document.body) return false;
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      if (n.hasAttribute && (n.hasAttribute('data-block') || n.hasAttribute('data-image') || n.hasAttribute('data-logo'))) return true;
      const tag = (n.tagName || '').toLowerCase();
      if (tag === 'img' || tag === 'svg') return true;
      if (n.classList && (n.classList.contains('sb-card') || n.classList.contains('on-media'))) return true;
      // any element painting its own background (bands, chips, rails) counts as content
      if (n !== document.body && n.classList && !n.classList.contains('stage') && !n.classList.contains('slide')) {
        const bg = getComputedStyle(n).backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
          const st = getComputedStyle(n.closest('.stage') || document.body).backgroundColor;
          if (bg !== st) return true;
        }
      }
      if (n === stage) break;
    }
    return false;
  };
  for (let i = 0; i < gx; i++) {
    for (let j = 0; j < gy; j++) {
      const x = r.left + pad + (r.width - 2 * pad) * (i + 0.5) / gx;
      const y = r.top + pad + (r.height - 2 * pad) * (j + 0.5) / gy;
      // Sample the WHOLE stack at the point, not just the topmost element: a
      // transparent layout wrapper above a full-bleed photo/scrim must not hide
      // the real content underneath (fixed 2026-08-13 - NM-25 false LOW).
      const stack = document.elementsFromPoint(x, y);
      total++;
      if (stack.some(isContent)) filled++;
    }
  }
  return { filled, total };
}
"""


async def run(out_dir, threshold):
    from playwright.async_api import async_playwright
    url = "file://" + os.path.abspath(os.path.join(out_dir, "review.html"))
    rows, flagged = [], []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1280, "height": 800})
        await page.goto(url)
        await page.wait_for_timeout(1500)
        n = await page.eval_on_selector_all("section.slide:not([data-placeholder])", "els => els.length")
        for i in range(n):
            await page.evaluate(
                """(idx) => {
                    document.querySelectorAll('section.slide').forEach(s => s.classList.remove('__dc_target'));
                    const els = document.querySelectorAll('section.slide:not([data-placeholder])');
                    els[idx].classList.add('__dc_target');
                    els[idx].scrollIntoView();
                }""", i)
            await page.wait_for_timeout(1200)   # let reveal animations land
            res = await page.evaluate(SAMPLE_JS, [GRID_X, GRID_Y, PAD])
            topic = await page.evaluate(
                "() => document.querySelector('section.slide.__dc_target').dataset.topic || ''")
            if not res:
                continue
            fill = res["filled"] / max(1, res["total"])
            rows.append((i + 1, fill, topic[:60]))
            if fill < threshold:
                flagged.append((i + 1, fill, topic[:60]))
        await b.close()
    print("DENSITY CHECK (fill = content-hit fraction of %d sample points/slide):" % (GRID_X * GRID_Y))
    for idx, fill, topic in rows:
        mark = "  LOW " if fill < threshold else "  ok  "
        print("%s slide %2d  %3d%%  %s" % (mark, idx, round(fill * 100), topic))
    if flagged:
        print("\n%d slide(s) below %d%% fill - rebalance copy, enlarge type, or outsource a real "
              "element (photo / logo row / stat chip) into the slack. See SKILL.md House style." %
              (len(flagged), round(threshold * 100)))
    else:
        print("\nAll slides at or above %d%% fill." % round(threshold * 100))
    return flagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="deck out/ dir containing review.html")
    ap.add_argument("--threshold", type=float, default=0.55)
    ap.add_argument("--strict", action="store_true", help="exit 1 when any slide is below threshold")
    args = ap.parse_args()
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("density_check: Playwright not installed - skipping (pip install playwright && "
              "playwright install chromium). This check is advisory; the build is not blocked.")
        sys.exit(0)
    flagged = asyncio.run(run(args.out, args.threshold))
    sys.exit(1 if (args.strict and flagged) else 0)


if __name__ == "__main__":
    main()
