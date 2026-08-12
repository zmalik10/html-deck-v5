# html-deck-v5 — Setup & Golden Rules (read this first)

This is a **self-contained SmartBuild deck skill**. Everything needed to build decks that look
like the Disney "Art of Storytelling" reference deck lives in this one folder — code, all 104
templates, every brand asset, images, logos, the Unsplash catalog, and the live-edit tools. No
external memory or prior conversation is required. Drop it on any machine and it works.

---

## THE GOLDEN RULE — stop and ask permission at every step

**This skill is interactive, not autonomous. It STOPS and asks the human before moving between
passes. Never blast through the pipeline. Never proceed on your own judgement past a stop point.**

Mandatory stop points (ask, wait for an explicit "go", then continue):

1. **After PLAN → STOP.** Present `plan.json` (the outline: slides, topics, layouts, image intents).
   **Do not start BUILD until the human approves the plan.**
2. **After BUILD / after SWEEP → STOP.** Open `review.html`, show the human, and wait. Do not
   REFINE, BRAND, or EXPORT on your own — ask what they want next.
3. **Before EXPORT → STOP.** Confirm before producing PPTX/PDF/HTML.
4. **Before ANY outward or irreversible action → STOP.** Pushing to git, sending, publishing,
   overwriting — always confirm first.

If you ever find yourself about to jump to the next pass without the human saying so, you have
broken the golden rule — stop and ask. This is exactly how the Disney deck was built: plan
approved first, reviewed at each stage, nothing exported until asked.

---

## Install (fresh machine)

1. **Put this folder at** `~/.claude/skills/html-deck-v5` (the folder name must stay
   `html-deck-v5` so the skill registers).
2. **Python deps:**
   ```
   pip install -r requirements.txt
   python -m playwright install chromium
   ```
3. **Install Google Chrome** (used for PDF export).
4. **Verify:** `python packaging/preflight.py` — it checks every file *and* runtime dependency
   and prints the exact command to fix anything missing. Fix until it reports READY.

---

## How to build a deck (the exact Disney flow)

Run all six passes over the one canonical `plan.json`, **stopping at each human touchpoint**:

1. **PLAN** — draft `plan.json` (slides, groups, layouts, `image_intent` per image slot).
   **→ STOP for approval.**
2. **BUILD** — `python engine/render_slides.py --plan plan.json --out slides.html` then
   `python engine/build.py --plan plan.json --slides slides.html --out out`, then open it:
   `python engine/open_deck.py --out out`. **→ STOP; show the human.**
3. **REFINE** — the human loop. Live-edit mode: `python engine/open_deck.py --edit --out out
   --plan plan.json` serves the deck on localhost so text edits and Slide-Board changes
   (reorder / remove / light-dark / add-blank-slide) **autosave to plan.json and rebuild**.
   The plain `file://` view is a clean, tool-free presentation.
4. **BRAND — always `--brand`.** `python engine/build.py --plan plan.json --slides slides.html
   --out out --brand --presentation`. **This is what bakes real logos, owned photos, and
   Unsplash images.** Without `--brand` the deck has NO images — it is a draft only.
5. **SWEEP** — `python engine/validate.py --plan plan.json --out out` AND
   `python engine/fidelity.py --plan plan.json --out out`. Both must pass. **→ STOP; review.**
6. **EXPORT** (on request) — `python engine/export_deck.py --plan plan.json --out out
   --format pptx|pdf|html --rebuild --open`. Runs the real engine export and opens the app.

Or drive the mechanical passes with `python engine/run_pipeline.py --plan plan.json
--slides slides.html --out out --brand --presentation` (BUILD → SWEEP, hard-stops on failure).

---

## Quality mandates — how "every deck looks like Disney"

- **Always `--brand`** for anything a human will see. No `--brand` = no images.
- **Every image slot = a real photo.** Owned first (`libraries/images/catalog.json`), Unsplash
  fallback (baked at BRAND). **Never leave an image slot to a generated/decorative SVG** — SVG is
  only for charts, sparklines, icons, and template motifs, never as a stand-in for a photo.
- **Use Unsplash** for slots with no owned match — it is free-license, approved for client decks,
  and baked into the HTML at `--brand`.
- **Template variety — never repeat a template.** Pick from the 104-template library
  (`layouts/library-v9/`, browse `rendered-gallery.html`); each section uses a *different* layout
  shape. A deck that reuses the same template reads as generated — vary it.
- **Mine every library** (images, logos, client logos, icons, reference slides) — a polished deck
  carries a real asset on the majority of its slides. Text-on-a-panel is the last resort.
- Full brand/voice/template rules are in **`SKILL.md`** — read it before building.

---

## What's in this folder

`SKILL.md` (full instructions) · `engine/` (pipeline: render, build, validate, fidelity,
export_pptx, export_deck, open_deck, **edit_server** for live-edit) · `frontend/` (deck.js/base.css)
· `layouts/` (104 templates + reference library) · `assets/` (logos, fonts, tokens, images) ·
`libraries/` (image/icon catalogs + galleries) · `schema/` (plan schema) · `packaging/` (preflight).
