# Template Improvement Log

Style/layout feedback that applies to a TEMPLATE (not one deck) gets fixed in the
shared layer and logged here, so the template library keeps improving. See the
"Continuous template-improvement loop" section in SKILL.md.

| Date | Template(s) | Issue (from review/sweep) | Fix (shared layer) |
|------|-------------|---------------------------|--------------------|
| 2026-07-02 | all | No footer logo / logos silently dropped when styled | build.py inject_logos tolerates attributes; footer mark baked per slide; SWEEP checks it |
| 2026-07-02 | all | Poor contrast — colour logo hard to read on dark/light bg | deck.js auto white/dark footer logo by sampling bg luminance |
| 2026-07-02 | all | No page numbers | BRAND bakes page number on content slides; SWEEP checks it |
| 2026-07-02 | covers, sections, closings | Footer logo / page number shown where they shouldn't be | build.py role-based chrome: hide logo on cover/closing, hide page number on cover/section/closing |
| 2026-07-02 | NM-06 (four-panel) and any bottom-anchored band | Takeaway band sat under the footer logo/number | `--sb-safe-bottom` no-go zone + `.sb-safe-bottom` on full-bleed bottom bands |
| 2026-07-02 | AN-09 (donut/segments) | Segment %s mis-aligned; colour/number treatment should be standard | %s centred on ring mid-radius (r=145, width+centre); legend $ values coloured to match each arc; arcs separated by deck-colour slivers — adopt as the AN-09 standard |
| 2026-07-02 | NM-02 (three big stats) | Header divider "top line" looked off in dark format | Removed the header `border-bottom` rule |
| 2026-07-02 | NM-06 (four-panel) | Column divider ran into the light-blue takeaway band | 24px gap between grid and band so dividers end above it |
| 2026-07-02 | CC-06 (so-what / synthesis) | Bullet arrows too thin | Heavier glyph `➔` (U+2794), larger — "meatier" |
| PENDING | AN-09 (donut) | Ring drawn with CSS conic-gradient is invisible in PDF/PPTX (html2canvas can't capture it) | Re-render donut as inline SVG (browser-identical, export-safe). Needs go-ahead — touches HTML ground truth. |
| 2026-07-04 | reference renderer (all locked slides) | Images letterboxed by `object-fit:contain`; PowerPoint fills a frame (stretch) + crops via `a:srcRect` | RC2: pictures render as positioned `<div>` with `background-image` + `background-size`/`background-position` computed from `srcRect`; default `100% 100%` stretch |
| 2026-07-04 | reference renderer (diagrams) | Grouped shapes / SmartArt / connectors silently dropped (missing "Operating model" diagram) | RC3: recurse groups with the group transform; COM-rasterize what can't be rebuilt (crop the shape's box from a full-slide COM render) and embed it — never silently omit |
| 2026-07-04 | reference renderer (titles/body) | Theme fonts unresolved (serif titles); bold/size defined on `lstStyle`/placeholder not the run; `a:br` soft breaks dropped | RC4: resolve run props through rPr→pPr/defRPr→shape lstStyle→theme; iterate paragraph XML for `a:br`; map `+mj-lt`/`+mn-lt` to the theme face |
| 2026-07-04 | reference renderer (theme swap) | Recolour flipped bg+text but left shape fills white → white boxes on navy | RC1: all-or-nothing recolour — every surface (fill/border/gradient/text) maps to the nearest brand token; contrast-aware text mapping (≥4.5:1); complex rasters knock out white on dark |
| 2026-07-04 | all (asset embed) | Transparent brand mark near the size cap got JPEG-flattened onto white → white box | RC5: never JPEG-flatten an image with alpha — keep PNG; JPEG only opaque photos |
| 2026-07-04 | all (icons in PPTX) | SVG export stamped one root-level fill/stroke that blanked per-path paint | RC8c: bake each element's computed stroke/fill/stroke-width (currentColor resolved) onto the clone; render at 2× |
| 2026-07-04 | product template (PT-02) | "Product screenshot" was an unreadable CSS mockup | RC10: `data-image` slot wired to real product screenshots extracted from the source deck (`product-smrt-e`/`product-smrt-gc`); high-contrast device panel; `[warn]` if a tag has no owned image |
| 2026-07-04 | review artifact (all) | Covers/sections/reference slides hid the page number → reviewer couldn't cite them | RC7: always-on `sNN/total` review chip on every slide (review.html only; presentation.html unchanged) |
| 2026-07-20 | all / tokens + _kit | Rounding inconsistent (8px CTA, 18px image slots) vs brand 6px rule | tokens.json radius.large 8px->6px; added `card()` (6px) + `image_slot()` (frameless) helpers in renderers/_kit.py |
| 2026-07-20 | assets/logos + build.py | `smrtAEC` had no logo asset — decks that name the product couldn't render its mark | Added `smrt-AEC.4c.png` (official 4c raster; no vector exists) to assets/logos; `LOGO_FILES["smrtAEC"]` + extension-based `logo_mime()` so raster logos embed as image/png (not svg+xml); preflight now checks 6 logos; token accent smrtAEC=steel |
| PENDING (Rowan/engine) | PD-02 + product headers | Full product NAME in a title/header should render as the full-colour product LOGO | data-logo injection for product names at BRAND (build.py inject_logos) + renderer emits `<img data-logo>` in title. Unblocked: `smrtAEC` asset now present (`smrt-AEC.4c.png`); remaining work is the renderer emitting `<img data-logo>` in titles. |
| PENDING (Rowan/engine) | CV-06 / closings | Brand mark floats too high on closing slides | closing renderer + build.py chrome: place the closing brand mark in the centered content flow, not absolute-top |
| PENDING (coordinate) | all (kicker_bar) | Eyebrow accent dash reads as an "AI-generated" tell to some reviewers | Design-philosophy call: keep the intentional kicker vs make it opt-in. Coordinate before changing a shared primitive. |
| PENDING (layouts / Zain) | CC-03 (compare/spectrum) | Old-vs-modern lists want per-row X / check affordances; no CC-03 renderer exists yet | Build a `compare` renderer with inline token-SVG X (old) / check (modern) marks (icon catalog has no check/x) |
| NOTE (already handled) | product / all image slots | "Frameless once the real image resolves" is ALREADY implemented (product.py + build.finalize_image_slots). This deck bypassed it by hardcoding a bordered <img>. Lesson: author images via the shared slot, never hardcode a frame. |

## WT-05 (about_bio) — 2026-07-22
- **Issue:** Renderer ignored the slide's image entirely, so the "photo sliver" that defines the template never appeared; WT-05 slides shipped as text-only.
- **Fix:** Added a full-height left photo sliver (148px, img-cover, 6px radius) rendered only when `has_image(s)` is true, so no empty slot is ever emitted. Bio + about + stats reflow to the right of it.
- **Status:** Applied to render_slides.py; benefits any deck using WT-05.

## WT-06 (prompt_anatomy) — 2026-07-22
- **Issue 1:** Bottom CTA crowded the last lead (no breathing room). **Fix:** kept justify-content:space-between (free space becomes the gap AND the CTA stays inside the card) and tuned heading/lead/CTA font sizes + card padding down so heading + 2 leads + CTA fit the panel with a title present. NOTE: margin-top:auto was tried first but pushed the CTA ~65px below the card border once the title shrank the card - space-between is the correct fix.
- **Issue 2:** No slide-level title, so the slide had no context for what the compare demonstrates. **Fix:** render an optional headline (_headline_block) above the two panels; falls back to no title when absent (back-compat).
- **Status:** Applied to render_slides.py; benefits any deck using WT-06.

## WT-05 (about_bio) photo width — 2026-07-22
- **Issue:** Photo sliver (148px) read as a thin accent, not a real image presence.
- **Fix:** Widened the sliver to 300px so the photo carries real weight on the slide. Content reflows beside it.

## CC-14 (numeral_actions) colour — 2026-07-22
- **Issue:** Slide read as monochrome (navy numerals + subtle grey row rules) - "lacks colour".
- **Fix:** Each numeral now takes a brand accent from ACCENT_CYCLE (sky / copper / steel / pink) and the row top-border adopts the same accent. Adds colour without new elements.

## Quote-mark glyph (p_quote, quote_full/NM-04, proof_stack/NM-09, image_quote_pair/NM-17, prompt_anatomy/WT-06) — 2026-07-22
- **Issue:** Every quote template rendered only an OPENING quote mark, and its line-height:0 / fixed-height styling clipped and mis-placed it. No closing mark.
- **Fix:** Added a shared qmark(opening, size, color, align) helper with non-clipping line-height; every quote template now renders a properly-placed opening mark before the quote AND a closing mark after it. Applied across all 5 renderers.

## NM-04 (quote_full) quote-mark layout — 2026-07-22
- **Issue:** The big open/close decorative marks stacked vertically (above + below the centred quote) read as two floating blobs.
- **Fix:** NM-04 now sets the quote marks INLINE, hugging the text (coloured open mark before the first word, close after the last), instead of large stacked glyphs. Other quote templates keep the decorative qmark() pair.

## Logo system — no black logo, badge extracted (all templates) — 2026-07-22
- **Issue:** Footer auto-contrast rendered a BLACK logo (`.mono-dark` = brightness(0)) on light backgrounds. No official black SmartBuild logo exists. Also only the full lockup was available.
- **Fix:** Removed `.mono-dark` (base.css) and the `lum>0.6 -> mono-dark` branch (deck.js). Logo now has TWO forms only: WHITE on dark bg (`.mono-white`), FULL-COLOUR on light bg. Extended to inline `<img data-logo="smartbuild">` via a `:root[data-theme=dark]` white-filter rule in base.css. Extracted the badge as `assets/logos/smartbuild-badge.svg` (registered in LOGO_FILES) for creative use in place of the wordmark. Contrast (white vs full-colour) is an automatic per-slide/theme decision. SKILL.md footer-chrome + logo-library updated.

## closing_cta (CV-06/09/16) uses the badge — 2026-07-22
- Closings now carry the SmartBuild BADGE (badge_mark(), top-left) instead of the full wordmark, so the lockup isn't overused. Follows the white-on-dark / colour-on-light rule.

## One logo per slide + numbered nav dots — 2026-07-22
- **One logo/slide:** build.py skips the footer logo when a slide already carries its own SmartBuild mark; validate.py adds a hard "at most one SmartBuild logo per slide" check. Fixed the closing (badge + footer wordmark) and the agenda (wordmark + footer wordmark).
- **Numbered nav dots:** deck.js renders the slide number inside each nav bubble; base.css restyles .dot as a 22px numbered pill (light+dark), with overflow safety for long decks. So you know which bubble jumps where.

## Toolbar layout + tooltips (frontend, all decks) — 2026-07-22
- **Issue:** Tool buttons used hardcoded per-id `top` values (fragile: the removed theme button left a gap, tpl-lib-btn had NO top and mispositioned) and the vertically-centered nav dots overlapped them.
- **Fix:** deck.js gathers all `.uibtn` into one `#ui-toolbar` rail; base.css lays it out as a horizontal row across the top-right so it never overlaps the centered right-edge nav dots (verified overlap=false). Removed all per-button top rules; save-menu re-anchored below the rail. Added instant CSS hover tooltips (`.uibtn[data-tip]::after`, fed from each button's title via deck.js) so every tool names itself without a click. Fixed em dashes in the button titles (now visible as tooltips).

## Nav-dot pill + fullscreen placement (frontend) — 2026-07-22
- **Bubbles cropped:** #nav-dots overflow-y:auto forced overflow-x to clip, so the scaled active bubble was cut on the sides. Fix: added horizontal padding + a rounded translucent blurred pill container (border-radius:999px), overflow-x:hidden with room, softer hover/active scale + glow ring. Reads as a bubbly, scrollable rail.
- **Fullscreen placement:** deck.js appends fs-btn LAST so it sits furthest top-right (the row hugs the corner).

## Live-edit mode — PPT-style autosave to disk (new capability) — 2026-07-22
- **Goal:** make the T (direct-text-edit) tool save edits INTO the deck files, persistently, like PowerPoint - replacing PPT for internal decks.
- **Constraint:** a file:// page is sandboxed and cannot write to disk. Solution: a tiny stdlib-only local server (engine/edit_server.py) serves the deck over http://127.0.0.1 and receives edits.
- **Build:** edit_server.py (serve review.html + POST /save-edit → writes plan.json block text AND patches review.html on disk, atomic, stale-rev guarded). open_deck.py gained `--edit` (spawns the server + opens localhost). deck.js: authored-block edits POST to /save-edit on commit with a Saved toast; guarded to http only (no-op on file://, keeps localStorage+copy-notes fallback). Per-deck "Edit Deck.command" double-click launcher.
- **Additive:** the build/render/SWEEP/export pipeline is untouched. Verified end-to-end: edit on slide → plan.json + review.html updated on disk → persists across reload.

## Live-edit two-tab workflow + hoisting fix — 2026-07-22
- **Workflow:** `open_deck.py --edit` now opens the FILE (read-only reference) with the edit server running in the background. The T tool on the file view opens the editable localhost version in a tab BESIDE it (window.open named target 'sbdeck-editor'), so you edit on one tab and cross-reference the saved file on the other. On the editable (http) tab, T toggles inline editing + autosave as before.
- **Bug fixed:** `var CAN_SAVE` was declared AFTER the `if(!CAN_SAVE)` title block, so hoisting left it undefined there and the file-view title/behaviour applied even on localhost. Moved CAN_SAVE to the top of initTextEdit. Verified: localhost → inline edit; file → opens editable tab.

## Distinct file-view "open editor" button — 2026-07-22
- On the read-only file view the text-tool now renders as a distinct ↗ button ("Open editable version (localhost) - then click T there to edit") instead of looking like the in-editor T, so it's clear the file button OPENS the editor and the actual editing T lives inside the localhost tab. Localhost tab unchanged (plain T = inline edit).

## Slide Board changes autosave to disk (frontend + engine, all decks) — 2026-07-22
- **Gap:** only the T (direct-text) tool autosaved to disk; Slide Board decisions (reorder / remove / light-dark / add-spare) persisted ONLY to localStorage and round-tripped via "Copy All Notes to Claude". So a board change never reached plan.json or the built files — the file version silently didn't reflect it.
- **Fix (approved by Zain):** board changes now autosave, mapping onto EXISTING schema fields (no schema/renderer change): order → order of plan['slides']; remove → slide.status='deleted' (already skipped by render_slides.py:3516 + build.py:462); light/dark → slide.variant_choice. deck.js `save()` now also calls a debounced (900ms) `boardAutosave()` → `POST /save-board` (localhost only; seeded so the baked baseline never triggers an initial POST). edit_server.py `save_board()` applies order/status/variant to plan.json (absolute state each time → idempotent, plan_revision NOT bumped so text-edit autosave keeps working), then `_rebuild()` (render_slides → build --brand --presentation) so review.html + presentation.html match. Small bottom-centre toast: "Layout saved ✓ — file updated".
- **Add-spare — CORRECTED (Zain, 2026-07-22): physically bake a real blank slide, live.** Original design (log an authoring request only, nothing baked) was wrong: Zain wants the live board add to *physically insert* the blank "spare slide" into the FILE as a placeholder, immediately — then Claude asks what content it needs and fills that same slide. So `save_board` now MINTS a schema-valid blank slide (`_new_spare_slide()`: layout.family 'custom' → _fallback renderer; topic "New slide (to author)"; group 'spare-<hex>'; a headline + a body prompting for content), inserts it after its anchor uuid, BUMPS plan_revision, rebuilds, and returns `reload:true`. The client reloads (the live DOM can't render HTML it doesn't have; reload also discards the rev-keyed board localStorage so the spare can't be double-minted, and build injects a fresh spare for the next add). The new slide's real uuid is logged to `authoring-requests.json` ({slide_uuid, after_slide_uuid, status:'pending', created_rev}) so Claude finds it (also greppable: topic "New slide (to author)" / group "spare-*") and authors it in place. Verified: POST add → new slide baked after 'agenda' in plan.json + presentation.html (renders placeholder body), rev 5→6, sidecar logged, reload:true; restored, SWEEP 25/25.
- **Verified:** POST reordered two slides + set a variant + logged an add-request → plan.json updated, presentation.html rebuilt in new order, sidecar written, 4.5s. Restored deck, SWEEP 25/25.
- **Follow-up bug — save confirmation invisible:** the autosave toast was `z-index:800` but the Slide Board overlay is `z-index:900` (base.css:499), and adding the spare happens with the board OPEN — so the "Saved ✓ / new-slide request noted" toast rendered BEHIND the board and the user saw nothing ("it doesn't tell me it saved"). Fix: board toast bumped to `z-index:950` (above board, below export-overlay 1000); the add-request message also made clearer and given a longer 5s dwell ("Saved ✓ — new slide requested; ask Claude to author it (won't appear until then)"). NOTE for future: adding the spare is an authoring request, so it correctly does NOT appear in the file until Claude authors it — that's by design, the toast now says so. (Board card DID move correctly on ✕/↺; setRemoved already calls render() — earlier confusion was tangled test state.)

## "Save As" button routes through the real engine export (frontend + engine, all decks) — 2026-07-22
- **Issue:** the in-deck Save As menu ran a DIFFERENT, lower path than a manual export. PDF used CDN html2canvas+jsPDF (rasterized, needs internet, hung forever if the CDN stalled — the "infinite loading screen"); PPTX built nothing, just printed a "run this command yourself" message. Output never matched the engine export the author is happy with.
- **Fix:** one shared export path. New `engine/export_deck.py` is the SINGLE exporter — (optionally) rebuilds presentation.html from plan.json (`--rebuild`: render_slides → build --brand --presentation, so live edits are baked in), then produces the file exactly as a manual export does (PPTX → export_pptx.py; PDF → headless Chrome `--print-to-pdf`, Playwright chromium fallback; HTML → copy presentation.html), and opens it in the OS app (`--open`). Prints one JSON result line.
- **Wiring:** Save As is localhost-only (stripped from the file view), so the deck is always served when it's clickable. `edit_server.py` gained `POST /export` → runs export_deck.py `--rebuild --open` (240s-bounded) and returns the JSON. deck.js `serverExport(fmt)` POSTs to it and drives a TERMINAL overlay: green "Done — opening PowerPoint/PDF" (auto-dismiss) or red "Export failed" (click to dismiss), with a 200s client abort so it can never hang. Old in-browser exporters kept only as an unreachable fallback.
- **Verified:** button → PowerPoint opened with a freshly-rebuilt deck.pptx; overlay ended on "Exported ✓ — opening PowerPoint (deck.pptx)"; PDF + HTML produce identical files to the manual path; SWEEP 25/25 green after rebuild. Needs Chrome (PDF) + Playwright/chromium (PPTX) on the machine — see preflight TODO.

## Tools are localhost-only; file view is a clean presentation (frontend, all decks) — 2026-07-22
- **Contract:** the deck ships as ONE artifact used two ways. Served on localhost (`open_deck.py --edit`) = the full editor, every tool live. Opened as a plain `file://` = a clean PRESENTATION deck — all editing tools are physically removed. Exactly two controls survive on the file view: **Fullscreen** (`#fs-btn`) and the **↗ open-editable-localhost** button (`#text-toggle`). Nav dots stay (a presentation navigation aid, not a tool).
- **Build:** deck.js hoists a single `SERVED = /^https?:$/.test(location.protocol)` signal (aliased by `CAN_SAVE`, so one source of truth). When `!SERVED` it removes `edit-toggle, board-toggle, tpl-lib-btn, theme-btn, save-btn, sources-btn` and their panels (`save-menu, sources-panel, review-panel, pin-popup, slide-board`) from the DOM. `body` gets `deck-served` / `deck-file`. All wiring was already feature-detected, so removal is a clean no-op for the rest.
- **Spare-slide follow-up:** the review-only spare/placeholder slide (`.slide[data-placeholder]`) is normally kept out of the scrolling flow by the Slide Board (`initBoard` seeds it removed → `board-hidden`). Stripping the board on the file view meant `initBoard` bailed early and the spare slide leaked into the presentation. Fix: the `!SERVED` block also removes `.slide[data-placeholder]`, and `slides` is now computed AFTER the strip so nav dots / keyboard nav / observers never count it. On localhost it's left alone (board parks it in "Not used", draggable into "In use"). Verified: file view 13 slides (spare gone), localhost 14 sections / 13 nav dots (spare parked).
- **Verified:** file:// → body `deck-file`, toolbar `[↗, Fullscreen]`, panels gone; localhost → body `deck-served`, full tool set, `T` inline editor. SWEEP 25/25 + fidelity clean unchanged.

## Slide Board thumbnails were blank for text slides — 2026-07-22
- **Cause:** thumbClone() clones the .stage but the clone never fires the reveal IntersectionObserver, so every .reveal* element (all slide text) stayed at opacity:0 → thumbnails looked empty (only baked images showed).
- **Fix:** force `.visible` (+ transition:none) on all .reveal/.reveal-left/-right/-scale/-hero in the clone, same as the PPTX export onclone does. Verified: 13/13 real slides now show full content in the board.

## Review-panel UX bugs (frontend) — 2026-07-22
- **Panel overlapped the toolbar:** sidepanels opened at top:0, sliding OVER the top-right toolbar row. Fix: `.sidepanel { top:64px }` so any panel opens below the toolbar; added a `body.panel-open` class (synced via a MutationObserver over ALL .sidepanels) that hides the centred nav dots while a panel is open. Toolbar (z-index 500) stays clickable above the panel.
- **Pen toggle didn't close its panel:** exitEdit() removed edit-mode but not the panel's .open class, so untoggling the pen left the sidebar stuck open (needed a refresh). Fix: exitEdit() now also removes .open. Verified: enter → panel opens below toolbar, dots hide; toggle off → panel slides out, edit-mode off, dots return.

## Rich-text WYSIWYG editor (PPT replacement) — 2026-07-22
- **Goal:** the live editor must persist bold/italic/underline, colour, highlight, and spacing/line-breaks - not just plain text - so decks can convey emphasis artistically. Applies to EVERY block/template + all future decks.
- **Data model:** new optional `content_block.text_html` (schema). render_slides blk() renders text_html VERBATIM when present, else brandify(text). `text` stays the plain-text fallback (fidelity/search/PPTX).
- **Editor (deck.js):** a floating format toolbar appears over any text selection in edit mode - B/I/U (clean <b>/<i>/<u>, styleWithCSS off, toggles so you can UNBOLD words in a bold header), brand-accent text colours + highlights (styleWithCSS on → <span style>), clear-format. Enter = line break (multi-line); commit on blur/Escape. Captures innerHTML; debounced autosave sends it to /save-edit.
- **Server (edit_server.py):** sanitises to an allowlist (b/strong/i/em/u/mark/span/br; div/p→<br>; style props color/background-color/text-decoration/font-weight/font-style; scripts/handlers/contents dropped). Stores block.text_html (+ plain text) and patches review.html with the markup.
- **SWEEP:** relaxed the hard raw-hex check to allow BRAND-PALETTE hexes (accent emphasis is theme-invariant); off-palette hex still fails. Verified: bold/colour edit persists through reload AND rebuild; 23/23 + fidelity green.

## Rich formatting → PPTX/PDF + COM-free macOS export — 2026-07-22
- **Formatting into PPTX:** deck.js pptRuns/_mRuns now capture italic + underline (bold + colour already were, via computed styles); export_pptx build_authored_slide applies run.font.italic/underline. Verified: cover exports POWER=bold+sky, "A STORY"=bold+italic+underline as native editable runs.
- **COM-free export (NEW):** export_pptx.py assembled decks only via win32com (Windows PowerPoint) → crashed on macOS. Added pptx_assemble() (python-pptx: one blank slide per plan slide) used whenever PowerPoint COM is unavailable OR the deck has no verbatim reference slides. source_theme() made tolerant of entries lacking source_path. Authored-only decks now export fully on mac/linux; ref slides fall back to blank+warn (need Windows to copy verbatim).
- **PDF:** headless Chrome `--print-to-pdf` of presentation.html → 13 pages, formatting preserved (HTML→PDF). Theme uses the locked deck theme (no prompt).
- Verified: all 13 slides present with native text; SWEEP still 23/23.

## Side-border accent bars → PPTX — 2026-07-22
- **Issue:** coloured `border-left` accent bars (e.g. WT-06 prompt_anatomy beats: sky/copper) rendered in HTML+PDF but not PPTX - _mShapeSpec only captured a UNIFORM 4-side border, so single-side accents were dropped.
- **Fix:** added _mBorderBars(cs,b,sc) in deck.js — emits a thin filled rect per coloured side border (left/right/top/bottom, non-uniform), pushed as shapes with the element's z. Verified: slide 7 PPTX now has a 0.06in sky bar + copper bar matching the HTML/PDF.

## 2026-08-11 — affiliate-partner-program deck (renderer block-type coverage)
- **CC-14 (numeral_actions)**: only consumes `list_item`; drops `step_label/step_title/step_body`, `kicker`, `subhead`, `caption`. Proposed: accept the step_* triple (the schema's natural step vocabulary).
- **NM-15 (stat_rail)** [FIXED at source 2026-08-12]: only consumes kpi/stat types; drops `card_title/card_body` rows. Proposed: accept card_title+card_body pairs as bold-lead rows.
- **NM-05 (versus)**: drops `left_label/left_body/right_label/right_body` (the schema types named for it), plus `body` and `cta`. Proposed: consume the left_*/right_* types directly.
- **AN-12 (data_table)**: drops `kicker`, `stat_label`, and its own `headline` when stats present. Proposed: render stat_label/stat/caption triples as tier rows.
- **PD-02 (suite)**: drops `pillar_title/pillar_body` (schema's pillar vocabulary) and `footnote`. Proposed: pillar_title as product logo lookup + pillar_body copy; footnote as bottom strip.
- **NM-13 (faq)**: mis-pairs Q/A when given alternating card_title/card_body; second card_title landed inside first card as body text. Proposed: pair by adjacency.
- **CV-06 (closing_cta)**: drops `kicker`, `body`, `label`, contact blocks (`card_title/card_body/list_item`). Proposed: optional contact-card zone.
- **cover_image (CV-01)**: no `cta` support; adding one shifts centered content under the top-left logo — needs a logo-safe top padding.
- **Cross-cutting**: kickers are dropped by nearly every renderer; worth a shared kicker helper above the headline.
- Workaround this deck: deck-local `patch_slides.py` (render -> patch -> build); all blocks stay pin-addressable.

## 2026-08-12 - kickoff-template deck (renderer block-mapping gaps)
Deck: ~/Decks/kickoff-template (patched deck-locally via patch_slides.py). Each of these renderers
silently DROPPED plan content_blocks it didn't recognize - proposal: every renderer should fall back
to rendering unmapped blocks as a stacked list rather than dropping words on the floor.
- **CV-08**: drops extra `label` blocks (co-brand company name + client logo slot never rendered).
- **NM-18**: dropped all `list_item` + second `subhead` blocks (only image + headline survived).
- **NM-07**: dropped the `subhead` intro line under the headline. **FIXED at master 2026-08-12**: card_row now renders the subhead AND adapts against wasted pixel space - with an `image_intent` on the slide, sparse card rows stack left and the photo fills the right (see SKILL.md "No dead pixel space" rule).
- **WT-01**: scrambled block mapping - used a `body` block as the giant title, put the headline in a card.
- **NM-15**: rendered first `body` as kicker, dropped remaining `body` paragraphs.
- **CC-12**: dropped every step_label/step_title/list_item column (headline-only slide).
- **CC-14**: flattens grouped card_title+list_item structure into one numeral row per list_item.
- **CV-06**: dropped contact `label`/`body` blocks after headline+subhead.
- **PD-11**: dropped card_title/card_body product blocks (headline-only slide).

## 2026-08-12 - TKMS CPSP proposal deck (decks/tkms-proposal)
Renderer gaps worked around via deck-local patch_slides.py; banked as suggestions:
- **NM-15 (stat_rail)** [FIXED at source 2026-08-12]: drops `kicker` and `lead` blocks (uses first `body` as an accent kicker line); a proposal-style slide needs a real lead paragraph under the headline. Suggest: render `kicker` above headline, `lead` as a muted paragraph.
- **NM-07 (card_row)** [FIXED at source 2026-08-12 - adaptive density when copy is heavy]: 3 cards with 40+ word bodies + 2-line headline overflow the 720px stage in image-split mode (headline/subhead overlapped card 1). Suggest: scale card padding/font when total copy is long, as done for stat tiles elsewhere.
- **NM-18 (icon_list)** [FIXED at source 2026-08-12]: drops `kicker` and `footnote`; a bottom takeaway band (accent-left-border card) is a natural fit under the rows.
- **PO-01 (roadmap)** [FIXED at source 2026-08-12 - accepts step_* triple + quote band]: consumes card_title/list_item/body but ignores the documented step_label/step_title/step_body triple and `quote`; a quote band under the phase cards fits the closing-thought pattern.
- **PO-05 (capability)**: renders titles + decorative coverage bars only - cannot express a pillars-x-items capability matrix (pillar_title + list_item groups). Suggest a matrix variant.
- **NM-09 (proof_stack)** [FIXED at source 2026-08-12 - titled cards x3 + footnote]: drops `card_title` (proof cards render body-only), caps proof cards at 2, ignores `footnote` (needed for "results reported by clients" attributions).
- **CV-09 (next_steps -> closing_cta)**: drops `body` paragraphs and contact card_title/card_body pairs; a next-step closing needs the why-now copy + contact cards.
- **_hide_decorative_numerals** [FIXED at source 2026-08-12 - pass now re-runs after the patch hook] runs before deck-local patch_slides.py, so patch-injected ordinal badges need manual aria-hidden="true" (RC8b). Suggest: run the decor pass after the patch hook.
- **validate.py chrome counts (FIXED at source 2026-08-12)**: expected page-number count used len(plan.slides) including tombstoned (status:"deleted") slides, so any deck that deletes slides mid-refine hard-failed the page-number check. Now counts live slides only. (TKMS deck, 4 tombstones.)

## 2026-08-13 - kickoff-template deck: candidate new template
- **Vertical chapter timeline** (kickoff deck slide 6): full-bleed photo + directional scrim, numbered
  nodes (01-0N, aria-hidden) on a glowing connector line, glass body cards stacked top-to-bottom.
  Strong fit for any "journey/phases/chapters" narrative slide. Candidate for promotion to a WT-series
  template; built deck-locally in decks/kickoff-template/patch_slides.py.
- **export_pptx.py tombstone bug (FIXED at source 2026-08-12)**: both assembly paths added a blank PPTX slide per plan slide including status:"deleted" tombstones (TKMS deck shipped 4 trailing blanks). Now filters live slides only, matching render_slides.py.
- **Export-safe decor rule (TKMS lesson)**: CSS rotated-border chevrons export as corner brackets, and CSS transform:scale on images exports WITHOUT container clipping - use inline-SVG data-URI images for decorative marks and pre-cropped raster assets instead. Wrapped lines containing multiple .product-name spans can merge into one long paragraph at export - keep long small-print blocks plain text.
- **PO-10 Photo Rail Detail ADDED (owner sign-off, 2026-08-12)**: Zain designated the TKMS slides 5-7 photo-rail treatment as the persistent house pattern for all future decks. Promoted from deck-local patch to a first-class template + `photo_rail_detail` renderer; SKILL.md house-style section instructs PLAN to default to it for detail/phase sequences.
- **engine/density_check.py ADDED (2026-08-12)**: mechanical fill-score gate for the "no wasted pixel space" house rule - point-samples every rendered slide, flags canvas fill below threshold (default 55%). Part of SWEEP's editorial step; advisory by default, --strict to block.

## 2026-08-13 — affiliate-partner-program deck (reviewer corrections, banked as owner directives)
- **PO-10 (photo_rail_detail)**: (1) support a mirrored variant (rail RIGHT) chosen via shape_tags or alternating within a group - sequences read as clones otherwise; (2) render `icon_intent` icons in the cards (centered icon + title, description left, per the icon-card house rule) - sparse one-line card bodies leave the 2x2 grid half-empty without them.
- **Cross-cutting (added to SKILL.md house style)**: free-layout autonomy on dead space (swap layout / add imagery / restack without waiting for reviewer correction) + layout-inversion as a first-line variety tool.
