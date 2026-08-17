---
name: html-deck-v5
description: Creates on-brand SmartBuild HTML slide decks at any length (3–30+ slides) via a staged pipeline over one canonical plan file. Use whenever anyone at SmartBuild asks for a slide deck, pitch deck, demo walkthrough, presentation, or fullscreen scrolling visual experience. Plans first, builds, refines from your pinned comments, brands, auto-sweeps for correctness, and exports HTML (PPTX/PDF on request). Always invoke before building any SmartBuild deck.
version: 5.0.0
author: SmartBuild
---

# SmartBuild Deck — v5 (staged pipeline)

> **Why this exists.** v4 was a monolith: one step had to be creative *and* rigorous *and* on-brand *and* export-ready at once, so the model half-applied each and dropped things. v5 splits the work into **six focused passes over one canonical plan file** (`plan.json`). Each pass does one job fully and writes a checkable artifact. An automatic gate catches problems before the human sees the deck.

> **The one rule that makes it work:** `plan.json` is the single source of truth for every *decision*. Generated HTML, the resolved-asset manifest, sweep reports and exports are *derived* artifacts. Never keep decision state anywhere but the plan.

---

## NON-NEGOTIABLE — run the whole pipeline, every time
This skill is a **pipeline, not a menu.** Every time you build a SmartBuild deck you run all six passes in order — never skip, reorder, or silently compress a step. Specifically, on EVERY deck:
1. **PLAN → STOP for human approval.** Never start BUILD before the human approves `plan.json`. This stop is mandatory.
2. **BUILD**, then **immediately open `review.html` in Chrome** (`engine/open_deck.py`). Every build ends by reopening the deck — no exceptions.
3. **REFINE** from pinned comments with surgical scope; rebuild and reopen after each batch.
4. **BRAND** (bake real assets) before SWEEP on a deck headed for a human/client.
5. **SWEEP is mandatory and must pass** — run `engine/validate.py` AND `engine/fidelity.py`. Deterministic FAILs block: fix and re-run (up to 3 iterations), then escalate anything unresolved. Never present a deck you have not swept. Never wave off a FAIL.
6. **EXPORT** only after SWEEP is green (and, for client decks, the license gate passes).
- **The two human touchpoints (approve PLAN, review the swept deck) always happen. The deterministic gate always runs.** If you ever find yourself about to hand over a deck without an approved plan or a clean SWEEP, you have skipped a step — go back.
- To enforce the deterministic passes mechanically, use the driver: `python engine/run_pipeline.py --skill-path . --plan plan.json --slides slides.html --out out [--brand] [--presentation]`. It runs BUILD → SWEEP (validate + fidelity) in order and **hard-stops on any gate failure**, so the mechanical steps cannot be skipped. (The creative passes — PLAN, BUILD authoring, REFINE — still need you.)

---

## NON-NEGOTIABLE — use EVERY library, to its fullest. Real content beats plain layout.
These libraries were built at real cost so decks look *made*, not generated. A slide that could carry a real asset but doesn't is a defect. On EVERY deck, actively mine ALL of them — do not default to text-on-a-panel when a relevant asset exists:

- **Image library (`libraries/images/catalog.json`, browse `libraries/images/_gallery.html`) — the FIRST place you look for BRAND-SPECIFIC assets** (for generic mood photos, Unsplash is an equal first-class source — see Image sourcing under PASS 4). It holds real owned assets, resolved by TAG: brand illustrations; **real product screenshots** (`product-smrt-e` = the smrt-E phone app, `product-smrt-gc` = the smrtGC dashboard) — put these on product/feature slides, never a stock photo; **real photos extracted from past decks** (architecture, jobsites); **real exec headshots**; and **8 real client logos** (`client-*`). Owned ALWAYS wins over Unsplash. Read the actual image (Read tool) before choosing so the pick genuinely fits.
- **Logo library (`assets/logos/`, browse `assets/logos/_gallery.html`).** A product name that is a title/hero/wordmark is the LOGO (`<img data-logo>`), never styled text — smartbuild + all five products. **The SmartBuild mark has only two real forms: the FULL-COLOUR wordmark (blue/grey + badge) and the WHITE version (auto-applied on dark backgrounds via CSS). There is NO black logo — never create or imply one.** The badge alone is also extracted as `smartbuild-badge` (`<img data-logo="smartbuild-badge">`) — use it as a creative stand-in for the full wordmark (e.g. a section mark or accent) so the full lockup isn't overused. It follows the same white-on-dark / full-colour-on-light rule.
- **Client logos → build a real logo wall.** Any validation / who-uses-us / proof slide should show the actual `client-*` logos, not text chips.
- **Reference slide library (`layouts/reference-library/`, browse `_gallery.html`).** Exec-approved published slides (about, market, validation, exec team, smrt-E). Search-and-reuse (PASS 1) before authoring net-new; reuse real, polished copy.
- **Icon library (`libraries/icons/`, browse `_gallery.html`).** Use a real icon wherever one genuinely fits a point (pain rows, feature grids) — only from the catalog, matched to the topic.
- **Layout library (104 templates).** Pick image-forward / product / photo / logo-wall / bio-with-photo templates when the content has an asset to show — not only the plainest text template.

A polished deck typically uses images/logos/photos on the MAJORITY of its slides. If a draft is mostly text panels, you have under-used the libraries — go back and mine them. Take the time; browse the galleries; pick real assets deliberately.

---

## The six passes

| # | Pass | Mode | Produces | Human? |
|---|------|------|----------|--------|
| 1 | PLAN | creative | `plan.json` (storyline, slide groups, layouts, content blocks w/ UUIDs, approved facts) | **approve** |
| 2 | BUILD | creative-in-frame | `slides.html` → `review.html` (light fidelity) | — |
| 3 | REFINE | directed | edits driven by pinned comments, surgical scope | **iterate** |
| 4 | BRAND | rigid | full assets baked (logos/images/icons/watermark) | — |
| 5 | SWEEP | rigid | deterministic gate + editorial report; auto-fix loop | — |
| 6 | EXPORT | rigid | HTML now; PPTX/PDF on request | on request |

**Two planned human touchpoints:** approve the PLAN, review the finished swept deck.
**Exception gates** (fire only when needed): stale-pin re-confirm, sweep escalation, out-of-scope REFINE approval.

---

## PASS 1 — PLAN  *(creative; loose)*

Produce `plan.json` validated against `schema/plan.schema.json`. Do this thinking:

1. **Storyline & slide count.** 3 or 30 — whatever the content needs. Never pad to a fixed number.
2. **Group slides into sequences.** Set `group` and `continues`. Slides in one group are a connected sequence → they share a layout shape. A new group → a *different* shape from the previous group. This is how variety works (see Layout variety below).

   **2a. Search-and-reuse BEFORE you author — never reinvent published content.** For every slide need — especially About/company slides and bios — search the **reference library + deck archive** first (`layouts/reference-library/`, see its `INDEX.md`):
   ```bash
   python engine/reference_search.py --role about --entity SmartBuild --audience client
   python engine/reference_search.py --role bio  --entity "Rowan"
   python engine/reference_search.py --text "who we are"        # topic / free-text
   ```
   Then:
   - **AUTO-reuse a canonical match** when the narrative calls for its role (About SmartBuild, About smrt-E, a leader bio) and the audience fits. Copy its `planFragment` into `plan.json`, **re-mint every uuid** (uuids are unique per plan — never shared across decks), and **merge the entry's `approved_facts`** into the plan. If the entry is `status:"draft"`, keep the copy but flag *"(draft copy — confirm wording)"* for the human at approval.
   - **SUGGEST fuzzy / near matches** (`match:"strong"|"fuzzy"`, plus any archive hits) for the human to confirm — don't pull them silently.
   - **STAMP provenance in BOTH places** on every reused/adapted slide — they serve different jobs and both are required:
     1. **Inline on the plan slide** (`slide["provenance"]`) via `inline_provenance()` — the deck-side attribution + SWEEP drift baseline (`blocks_hash`). The schema DOES allow this (`$defs/provenance`).
     2. **Library reverse-index** via `record_reuse()` — appends to the entry's `used_in[]` so owners see where content is reused.
     ```python
     from reference_search import best_canonical, inline_provenance, record_reuse
     hit = best_canonical(role="about", entity="SmartBuild")   # None if no canonical match
     if hit:
         slide = deepcopy(hit["entry"]["planFragment"])        # the real, reviewed slide content
         remint_uuids(slide)                                   # uuids are unique per plan — mint fresh
         slide["provenance"] = inline_provenance(hit, plan_revision=plan_revision, reuse="verbatim")
         record_reuse(hit, deck_title=deck["title"], reuse="verbatim", plan_revision=plan_revision)
     # reuse="adapted" if you changed wording (SWEEP still baselines what you pulled); net-new is "authored" (no stamp)
     ```
     On later SWEEPs, if you edit a stamped slide, `validate.py` raises a NON-blocking advisory to bank the change upward via the gate (`layouts/GATE.md`). The active deck stays fully editable.
   - **Author net-new only when nothing fits.** You are never *limited* to the library — but never rebuild a slide that already exists.
3. **Pick a layout per slide** from `layouts/library-v9/catalog.json` (105 templates; see `library-v9/INDEX.md`) by matching each template's `story_job`/tags to the slide's need. Record its id (e.g. `NM-01`, `AN-09`) as `layout.family`. If nothing fits, invent one (`family: "custom"`) — deck-local until reviewed for promotion.
4. **Write the ACTUAL content of every block — the real words that will appear on the slide** (headline text, body copy, stat values + labels, every card's title and description, labels, CTA wording). NOT just a heading or a data note. The plan is a *full content specification* — a reviewer should be able to read `plan.json` and know exactly what each slide says. BUILD renders this copy; it never invents or fills in wording. Every block gets a **UUID** (`block_uuid`) that never changes. Type each block (`headline`, `stat`, `body`, `cta`, …).
5. **Capture every factual claim/stat in `approved_facts`** with a `value` and `source`, and reference them from blocks via `fact_refs`. **This is not optional** — SWEEP will hard-fail any stat in the deck that isn't an approved fact. Do not invent numbers.
6. **Note image + icon intent** (tags, not assets yet).

**Then STOP and show the plan for approval.** Cheap to change the story now; expensive later.

**UUID lifecycle (never violate):** new block after PLAN → mint fresh UUID; edited block → keep UUID; deleted → tombstone (`status:"deleted"`, keep it so pins resolve to "removed"); split → primary keeps UUID, rest mint; merge → survivor keeps one, others tombstone. UUIDs unique per plan, never re-minted. Slide numbers (`display_index`) are display-only, **never** identifiers.

---

## PASS 2 — BUILD  *(creative within the plan's frame; light fidelity)*

Produce `slides.html` from the approved plan. **Default path: render it from the templates, don't hand-author.**
```bash
python engine/render_slides.py --skill-path . --plan plan.json --out slides.html
```
`render_slides.py` maps each slide's `layout.family` (template id) → its renderer (via `catalog.json`) and lays out the template's shape from your `content_blocks` / `icon_intent` / `image_intent`, using the theme-correct kit (`.sb-card`, `--sb-title` headings, theme body tokens, `.on-media` over photos, `.cta-btn`, `img-cover`, 6px radii, reveal). Output is **code, correct in BOTH light and dark by construction** — never a pasted screenshot, and never near-white/near-black hand-picked colours. A template with no dedicated renderer falls back to a generic stacked-card layout (logged) — build that renderer out rather than hand-authoring around it.
The renderer is a **starting point, not a cage**: adapt spacing/emphasis/extra elements to the content in front of you. If you must hand-edit `slides.html` after rendering, keep every brand/theme rule below — SWEEP enforces them either way.

**Progressive fidelity: do NOT bake heavy assets yet** — render/BUILD uses `<img data-logo>`/`<img data-image>` placeholders; real assets bake at BRAND.

Rules the SWEEP mechanically enforces (so follow them):
- Every slide: `<section class="slide" data-slide="{slide_uuid}" data-topic="…"><div class="stage" style="display:flex;…">…</div></section>`. The **1280×720 `.stage`** is the fixed authoring canvas.
- **Every content element carries `data-block="{block_uuid}"`** and `data-block-type="…"`. This is what makes review pins land exactly.
- **No visible text outside a `data-block`, ever.** Every rendered word — including bar-chart `%` values, process step numbers, tiny labels — must sit inside a `data-block` element. SWEEP hard-fails otherwise (RC8b), and the PPTX exporter positions its editable text objects from `data-block`s (an orphan-text safety net exists, but don't rely on it — un-tagged text is fragile at export). Asset slots (`data-logo`/`data-image`) are exempt.
- **Use brand tokens, never raw hex** — `color:var(--sb-sky)`, etc. (Available: `--sb-sky --sb-copper --sb-steel --sb-pink --sb-ink`, and theme vars `--sb-deck-bg --sb-text-on-dark --sb-body-on-dark`.) SWEEP scans **all** CSS (inline styles, `<style>` blocks, and SVG `stroke`/`fill`) and raises an editorial ADVISORY for any off-palette colour (RC6).
- No inline event handlers, no `<script>` in slides (CSP).

Build the light artifact, then **always open it in Chrome** for review (standard step every build):
```bash
python engine/build.py --skill-path . --plan plan.json --slides slides.html --out out
python engine/open_deck.py --out out            # ← opens review.html in Chrome, every time
```

---

## PASS 3 — REFINE  *(directed; iterative — this is the human loop)*

The reviewer opens `out/review.html`, clicks the pen (Review Mode), clicks any element to drop a **self-describing pin** (captures the element's UUID + a description + content hash + your note). They can also hit **Draw** to circle/mark directly on a slide; slides with drawings get a **screenshot captured into the feedback**. Then **"Copy All Notes to Claude"** copies the notes (and downloads a PNG per drawn slide). Paste the notes back here **and attach the downloaded screenshots** — apply them with surgical scope.

**Deck-level review tools (the review chrome, review.html only).** Beyond per-element pins, the reviewer can restructure the whole deck and choose per-slide styling; every one of these is a *recorded decision* that round-trips inside the SAME "Copy All Notes to Claude" payload (and the board's own **Copy layout & variants**). Apply them to `plan.json`, never as ad-hoc HTML:
- **Slide Board — the full-deck summary view** (**▤** button / press **B**). All slides as thumbnails in two zones: **In deck** (ordered) and **Not used**. *Drag* to reorder; *drag a card into "Not used"* (or click its top-right **✕**) to take it out of the deck without deleting; **↺** puts it back. *Clicking a thumbnail* jumps into the live deck at that slide, in edit mode, ready to pin. Order + inclusion + variant are applied together to the LIVE scrolling deck (it physically reorders, removed slides drop out, and pin s#/nav rebuild to the new order) so slide-level pins land in the right place.
- **Per-slide light/dark "main version."** Reference slides bake BOTH a `.ref-light` and `.ref-dark` render; a ☀/☾ toggle (on each Slide-Board thumbnail, and inline top-left of each stage in edit mode) pins ONE as that slide's main version, overriding the global theme for that slide (`data-variant` on the section). Recorded as **`slide.variant_choice`** (`"light"|"dark"`); `build.py` stamps `data-variant` from it and emits `window.__VARIANTS__` so the board seeds from the baked baseline.
- **A default "Spare" placeholder slide** is injected into `review.html` only (never `presentation.html`/export), parked in "Not used" by default (`data-placeholder` → board seeds it removed). Drag it into the deck to add a new slide; it surfaces in the payload as a NEW blank slide to author.
- **Notes-aware layout.** Opening the notes drawer adds `body.notes-open`; the slide shrinks (`--notes-w`) so the WHOLE slide shows beside the notes instead of hiding behind them.
- Board decisions persist to `localStorage`, keyed to `plan_revision` (stale state is discarded once a rebuild bakes the decisions in). The payload gives the final order, the Not-used list, and explicit light/dark choices — all UUID-anchored.

**On completion — ALWAYS reopen the deck in Chrome (do this every time, not on request).** The moment a batch of notes is applied (and after any pass that regenerates the deck), rebuild and reopen so the human can see the result immediately:
```bash
python engine/build.py --skill-path . --plan plan.json --slides slides.html --out out
python engine/open_deck.py --out out   # ← surfaces the deck: REUSES an existing deck tab (reloads it in place and refocuses it, even on another display/Space); opens a new window ONLY if no tab is showing the deck
```
This is the standing rule for the whole pipeline: **any pass that changes the built deck ends by surfacing it for review** - reuse-first (owner directive 2026-08-13: never stack new tabs/windows when the deck is already open somewhere; refocus and reload the one that exists). Never leave the human to reopen it manually.

**Surgical scope is the law of this pass:** apply *only* what the notes ask. If a note says "3 versions of slide 10's visual," produce three alternates for slide 10 and **touch nothing else**. Update only the referenced blocks in `plan.json` (bump `plan_revision`), then rebuild.

**Make visual changes in the plan/slides source — NEVER by appending an override `<style>` block.** An `<style>`-block override (e.g. recolouring icons) breaks provenance, is invisible to the pin/UUID model, and — until RC6 — hid from the palette guard. Edit the block's own inline style or the template; if a colour is genuinely off-palette on purpose, expect (and accept) the SWEEP palette ADVISORY rather than hiding it.
- A change that must touch shared CSS or other slides is an **out-of-scope/global change** → declare it and get explicit human approval before applying (exception gate).
- If a pin's `content_hash` no longer matches its block (content moved on since the pin was dropped), mark it `stale` and re-confirm with the human rather than applying blindly.

**Lock the theme during REFINE (light or dark).** Every deck ships in ONE decided theme, and that decision is made here, not at export. As part of REFINE, ask the human **light or dark**, then record it: set `deck.theme` to their pick and `deck.theme_locked: true`. Once locked, `build.py` drops the light/dark toggle from the chrome, so the built deck is the single decided version - there is no second theme to switch to or maintain, and EXPORT is seamless (it uses `deck.theme` with no prompt). If the human later wants to see the other theme, flip `deck.theme` and rebuild - but only one theme is ever the stored/decided version at a time. (Per-slide `variant_choice` still exists for the rare slide that must differ, but the deck has one baseline theme.)

**Live-edit mode (PPT-style autosave to disk).** For quick text fixes the reviewer can edit the deck directly and have it save itself - no "Copy notes" round-trip. Launch with `python engine/open_deck.py --edit --out <deck>/out --plan <deck>/plan.json` (or the generated **"Edit Deck.command"** double-click launcher in the deck folder). This starts a tiny local server (`engine/edit_server.py`, stdlib only, localhost only - nothing is hosted or published) and opens the **file** (read-only reference view). **Two-tab workflow:** on the file view the text-tool button shows **↗ ("Open editable version")** - clicking it opens the **editable** version (`http://127.0.0.1`) in a tab beside it, so you can edit on one tab and cross-reference the saved file on the other. On the editable tab that same tool is the plain **`T`** (direct-text-edit): it toggles inline editing and every committed authored-block edit **autosaves instantly to disk**. **Rich formatting:** selecting text pops a format toolbar - **bold / italic / underline** (toggle, so you can un-bold words inside a heavy header), **brand-accent text colours + highlights**, and clear-format; **Enter inserts a line break** for multi-line, spaced layouts. Formatting is stored as sanitised inline HTML in the block's `text_html` (rendered verbatim by every template; plain `text` kept as fallback), so bold/italic/colour/line-breaks survive reload, rebuild, and export - the deck edits like PowerPoint: the new text is written into `plan.json` (source of truth, survives every rebuild/export) AND patched into the on-disk `review.html`; a "Saved" toast confirms. Refresh the file tab (hard-refresh, browsers cache `file://`) to see saved changes land. Purely additive - the build/render/SWEEP/export pipeline is unchanged; over `file://` the autosave no-ops (the `T` tool instead opens the editable tab); reference/verbatim slides stay image-locked (pin those). Single-author local editing, not multi-user co-editing.

Loop BUILD↔REFINE until the reviewer is happy.

---

## PASS 4 — BRAND  *(rigid; bake full fidelity)*

Now spend the bandwidth. Re-run the build with `--brand` to embed real logos, images, icons and watermark, and record resolved-asset provenance:
```bash
python engine/build.py --skill-path . --plan plan.json --slides slides.html --out out --brand
```
BRAND records each injected asset in the plan's `resolved_assets` with `source/author/license/approved_for_client`. That provenance drives the Sources panel and the client license gate.

### Image sourcing — brand-specific owned first, then source Unsplash freely (do this as part of BRAND)
Before the `--brand` build, resolve every slide's `image_intent` to a real photo. Two rules, in order:
1. **Brand-SPECIFIC assets are owned-only, always.** Product screenshots, logos, exec/team headshots, client logos, and photos extracted from our own decks/site come from the owned library (`libraries/images/catalog.json`) — never substitute stock for these. `build.py` embeds them automatically.

   **1a. GENERIC mood photos: Unsplash is a FIRST-CLASS source, not a fallback (owner directive 2026-08-14).** Covers, heroes, closing shots, section rails, persona/atmosphere imagery — these are free to come from Unsplash whenever a fresh photo fits the message better than what we own. Unsplash is free-license, commercial-use, no attribution required, so there is no reason to force an ill-fitting owned photo into a generic slot. **Never reuse the same generic photo twice inside one deck/page**, and check the usage ledger `libraries/images/usage.json` so decks don't share heroes. Fetch and LOOK at 3-5 candidates (Read tool) before choosing; pick for the slide's actual message, and prefer photos that read as real moments over staged stock clichés (generic handshakes, fake boardroom high-fives).

   Resolving Unsplash IDs when the site is blocked in the browser pane: `curl -sL https://unsplash.com/s/photos/<query>` and grep for `images.unsplash.com/photo-[a-z0-9-]*`, then download with `?w=1400&q=78&fm=jpg`.
2. **Recording an Unsplash pick (you choose it — no human step).** Search Unsplash yourself (use the slide's `image_intent.query` / `mood` as the search phrase), pick ONE photo that genuinely fits, and record your choice into that slide's `image_intent.resolved`:
   ```json
   "resolved": { "provider": "unsplash",
     "photo_id": "photo-1503387762-592deb58ef4e",
     "url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e",
     "author": "Jane Doe", "author_url": "https://unsplash.com/@janedoe",
     "license": "Unsplash", "approved_for_client": true }
   ```
   `build.py --brand` then **downloads that photo and bakes it into the HTML as a data-URI** (self-contained; falls back to a live CDN reference only if offline). Unsplash photos are free-license and allowed on client decks (`approved_for_client: true`), recorded with attribution for the Sources panel. Only brand-specific slots (rule 1) are off-limits to Unsplash.
3. **No manual approval loop.** Choose images yourself. If the human dislikes a pick, they pin it in review; then you swap only that slide's `image_intent.resolved.photo_id` and rebuild.
4. **Formatting is guaranteed by the slot, not the photo.** Every image slot must have fixed geometry so any photo fills it without distortion — author slots via `_kit.image_slot(tag, height=…)` or a sized container holding `<img data-image="tag" class="img-cover">` (object-fit:cover). SWEEP fails an image slot that has no sizing, and fails an unresolved slot at BRAND (no dead grey slabs).

---

## PASS 5 — SWEEP  *(rigid; the auto gate — runs before the human sees it)*

Two kinds of check, handled differently on purpose:

**Deterministic checks — hard-fail, drive the auto-fix loop:**
```bash
python engine/validate.py --skill-path . --plan plan.json --out out
python engine/fidelity.py --plan plan.json --out out
```
`validate.py` checks the mechanical contract (fixed canvas, single scroll container, every element tagged, pins resolve, token drift, no inline handlers, CSP, presentation excludes review chrome, client license gate, forced Sources). `fidelity.py` is the **content-fidelity gate** — every rendered stat must map to an approved fact.

**Deterministic advisories — surfaced, never block:** `validate.py` also recomputes the content hash of any slide/block carrying a `provenance` stamp and, on divergence from the published master it was pulled from, prints an `ADVISORY … diverges from published master REF-xyz v<n> — bank as a library update via the gate?`. The active deck is free to edit, so this **escalates to you, it never fails the gate**.

**Editorial checks — YOU judge, advisory, escalate (do NOT loop forever):**
- **Wasted pixel space — run the mechanical density check** (`python engine/density_check.py --out <deck>/out`). It scores every slide's canvas fill by point-sampling the rendered deck; treat a LOW flag on a content slide as a defect (rebalance copy, enlarge type, or outsource a real element into the slack). Covers/closings run airy by design — scores near the threshold there are a judgment call, not an automatic fail.
- Is it clear, correct, does it make sense?
- **Layout variety (relationship-aware):** unrelated topics back-to-back must look *different*; a connected sequence (same `group`) must look the *same*. Flag an unrelated repeat OR a continuation that wrongly differs.
- **No emojis; real icons where they help; icons must match their topic** (`icon_intent.represents`).
- **Concept consistency:** a recurring idea is shown the same way each time.

**The loop:** fix deterministic failures and re-run, up to **3 iterations**. If deterministic checks can't converge, or an editorial issue can't be auto-resolved (e.g. no icon fits), **STOP and escalate the specific issue** to the human — never fake "all clear." When clean, **always end SWEEP by opening the deck in Chrome for the human to review** (standard step — do this every time, not on request):
```bash
python engine/open_deck.py --out out                  # ← DEFAULT: opens review.html (Review Mode + pins) so the human can sign off or flag drift/editorial issues
python engine/open_deck.py --out out --presentation   # ← optional: also open the clean client deck to eyeball the final deliverable
```
Surface any deterministic advisories (library drift) alongside this open so the reviewer can decide whether to bank them.

---

## PASS 6 — EXPORT  *(rigid; on request)*

**Build is review-only by default** — the working loop (BUILD/REFINE/SWEEP) emits just `out/review.html`. The clean client `out/presentation.html` is **opt-in**: pass `--presentation` to `build.py` when you reach EXPORT / client hand-off (`python engine/build.py … --out out --presentation`). This keeps the loop to one artifact.

`out/presentation.html` is the clean client deliverable (no pins/notes/debug; Sources forced-on only if an asset needs attribution). For PPTX/PDF, use the in-deck **Save As** menu (loads pinned libraries from the CDN allowlist on demand; export needs internet). Exports capture the fixed 1280×720 canvas, so they're consistent regardless of screen size.
- **Theme is decided at REFINE, not here — if `deck.theme_locked` is true, export in `deck.theme` with NO prompt.** The light/dark choice is a REFINE step (see PASS 3): the human picked it, the deck shipped in it, the toggle was removed. EXPORT simply honours that locked theme, which is what makes export seamless. Only if a deck reaches EXPORT WITHOUT a locked theme do you ask light or dark and never assume. Either way a PPTX/PDF must be true to ONE theme end-to-end: the export forces the theme onto the DOM (`get_manifest(html, theme)` sets `data-theme`) so every captured fill/text/background comes from that one theme (prevents theme mixing, e.g. a light-mode card fill under dark-mode white text). `export_pptx.py --theme {dark|light}` is **required** (no default) and must match `deck.theme` when locked; the scratch macOS driver takes the same explicit theme.
- **Client decks:** EXPORT is blocked unless every resolved asset is `approved_for_client` (license gate). Never hand a client the `review.html`.
- **PPTX is native, layered, editable — not a screenshot.** Authored slides rebuild as real PowerPoint text/shape/image/chart objects; verbatim-locked reference slides rasterize as a pixel-faithful background **with the exec-approved words overlaid as real editable text boxes** (RC8a). Icons bake their computed paint (RC8c); gradients become native `<a:gradFill>` via a JSZip post-pass that **fails loudly** rather than shipping sentinel rects (RC8d).
- **Rich text carries into PPTX + PDF.** Live-editor formatting (bold / italic / underline / brand colour) exports as real formatted PowerPoint runs (`build_authored_slide` reads bold+italic+underline+color captured from computed styles) and renders in the PDF (HTML→PDF). So emphasis authored in the deck is true in every format.
- **COM-free export (macOS / Linux / any box without PowerPoint).** `export_pptx.py` assembles the deck natively with `python-pptx` (`pptx_assemble`) whenever PowerPoint COM is unavailable or the deck has no verbatim reference slides — authored-only decks export fully anywhere. Run it directly: `python engine/export_pptx.py --skill-path . --plan <deck>/plan.json --slides-html <deck>/out/presentation.html --out <deck>/out/deck.pptx --theme dark`. **PDF:** headless Chrome `--print-to-pdf` of `presentation.html` (each slide → one page). Only decks that reuse verbatim reference slides still need Windows PowerPoint (to InsertFromFile the source); those slides fall back to blank placeholders elsewhere and warn.
- **Verify every export with the fidelity harness** — it renders both sides (Playwright + PowerPoint COM), scores layout-structural SSIM per slide, and asserts the layering contract (zero dropped words, real editable runs, asset census, no sentinels):
```bash
python tests/fidelity_harness.py --export out/presentation.html --pptx out/deck.pptx   # drive the real in-deck export
python tests/fidelity_harness.py --html out/presentation.html --pptx out/deck.pptx --sheet out/fidelity.png
python tests/run_tests.py            # T6 runs this gate on every change
```

---

## Layout variety — the rule (don't get this wrong)
Sameness signals continuity; difference signals a new idea. Enforce via `group`/`continues` + `shape_tags`: **same group → reuse shape; new group → different shape from previous group.** SWEEP judges variety against groups, not raw adjacency.

## Don't force a template onto content that doesn't fit it
A template is a starting point, not a mold to cram content into. Forcing one produces the classic garbage slide: a big empty image panel, off-topic icons, or copy mangled to fit slots. Rules (SWEEP now enforces the first three deterministically):
- **No empty image regions.** Only declare an `image_intent` / reserve an image slot when a real owned image (or an intended, resolvable one) will fill it. If there's no image, pick a text-forward layout or drop the image region — never ship a dead placeholder box. SWEEP hard-fails an unresolved image slot at BRAND.
- **Never force an icon.** Use an icon only when one in `libraries/icons/catalog.json` genuinely matches the topic (check its `tags`). If nothing fits, OMIT the icon — a missing icon beats a wrong one (a hot-springs glyph on a "spreadsheets" row is worse than no icon). SWEEP hard-fails an icon name that isn't in the catalog.
- **Never em dashes.** SmartBuild brand rule: use a plain hyphen (-), never — or –. SWEEP hard-fails em/en dashes in authored copy.
- **Adapt the template, don't mutilate the content.** If a template has four card slots and you have three real points, use three - don't invent filler. If the copy doesn't fit the slot, change the layout, not the message.
- **No dead pixel space - reformat and outsource an element to fill it.** Sparse content (2-3 short cards, a thin list, one small paragraph) on a full-width layout leaves the slide mostly empty; that's a defect, not minimalism. Adapt: RESTACK the content (a short row becomes a stacked column) and FILL the freed side with a real element - an owned-library image first, an Unsplash pick as fallback (declare `image_intent` on the slide so BRAND resolves it), a product logo, or a stat panel. PLAN should declare `image_intent` on any card/list slide whose copy is too light to carry the full canvas; renderers with an image-split variant (e.g. NM-07 card_row) use it automatically. Never ship a slide that is half whitespace when a real asset could carry it.

## Brand & theme rules that MUST hold (SWEEP enforces these — stop hand-fixing them)
Every deck can be viewed in light OR dark, so these are not optional polish. Follow them at BUILD:
- **Theme-legible colour, always.** Text on the deck/card background MUST use a theme-aware token that flips with the theme: `--sb-title` (headings), `--sb-text-on-dark` / `--sb-text-primary` (body/titles), `--sb-body-on-dark` / `--sb-text-secondary` (muted). NEVER hard-code a near-white colour (`#fff`, `white`, `var(--sb-on-accent)`, `rgba(255,255,255,…)`) for on-background text — it disappears in light mode. Fixed white is ONLY for text on a fixed-dark backdrop (a photo/scrim or an accent-filled panel); wrap that overlay content in **`.on-media`** so all of it reads white in both themes (labels stay sky). SWEEP hard-fails fixed-white text that isn't on a backdrop.
- **Product name in a title/hero = the LOGO, not text.** When a product name (`smrtGC`, `smrtSUB`, `smrtAE`, `smrt-E`, `smrtPAY`) is the title or hero wordmark of a slide, render the product logo (`<img data-logo="smrtGC">`), never styled text. Inline mentions inside a sentence stay as `.product-name` text.
- **The slogan is "Work smrter, not harder."** (smrter, not smarter). It is a fixed brand constant. SWEEP hard-fails "Work smarter".
- **Every hero and closing carries an image.** The cover and the closing slide must have a real hero image (owned first, else an Unsplash pick per PASS 4) - never a bare geometric/blank hero. SWEEP hard-fails a cover/closing with no image at BRAND.
- **CTAs are white text on the accent.** Use `.cta-btn` (accent fill, white label, 6px radius). Never dark text on the accent chip.
- **Cards must be visible in both themes.** Use `.sb-card` (or an equivalent visibly-elevated panel) - the raw panel token alone is nearly invisible on the dark deck background.
- **Display/hero text is brand NAVY on a light canvas.** Headlines, big statements, and pull-quotes use `.hl` or `color:var(--sb-title)` — navy (#005491) in light mode, white in dark mode. Never hard-code a near-black colour (`--sb-text-on-dark`, `--sb-text-primary`, `#0f1419`) for display type; that reads flat and off-brand on white. (Small body/caption text still uses the muted body tokens.) SWEEP hard-fails near-black display text ≥36px.

## House style — learned rules (bank of client corrections, 2026-08)
Each of these exists because a reviewer had to correct a shipped deck. Apply them at BUILD so the correction never recurs:
- **COLOUR LOGIC - every colour means something (owner-approved 2026-08-13).** Colours are semantic, not decorative:
  - **Brand blues (sky/navy)** = identity and emphasis: kickers, headline accent words, titles, structural highlights.
  - **`var(--sb-confirm)` (green, official token)** = positive status ONLY: checked items, money earned/payouts, gains. Never decorative.
  - **Ink** = structure: outlines, frames, scrims, checklist boxes.
  - **Copper vs sky** = paired-party contrast (YOUR JOB sky / OUR JOB copper): two parties, two warm-vs-brand voices.
  - **Product accents** = only when that product is the subject. On product-audience labels ("FOR GENERAL CONTRACTORS"), the "FOR" prefix is ink and the audience name carries THAT PRODUCT'S logo accent (owner directive 2026-08-14). NOTE: read accents from the actual logo files - smrtGC=copper(orange), smrtSUB=sky, smrt-E=pink, smrtAEC=steel; the tokens' product_accents map has GC/SUB swapped vs the real wordmarks (flagged, not yet corrected in tokens.json).
  Restraint is part of the logic: one semantic accent per element, and if a colour has no meaning to carry, it stays neutral. Do not "add colour" to decorate - add it to MEAN something.
- **NO accent dashes, ticks, or rules - ever.** The little horizontal hash before a label (.label::before) and the short accent bar under a title (rule()) are BANNED house-wide and removed at source (owner directive, 2026-08-13). Never reintroduce them in renderers, hand-authored slides, or deck patches; a kicker/label is typography alone.
- **No decorative gradients.** Panels, bands and chips use SOLID brand fills (navy `var(--sb-title)`, accent, ink). Where a big surface needs visual interest, use a PHOTOGRAPH with a solid ink overlay - not a gradient.
- **The PHOTO RAIL is the house pattern for detail/phase/section slides (PO-10) - owner directive, use it on EVERY deck.** A full-height photograph rail (slide `image_intent` resolved at BRAND, solid ink overlay ~0.72, `.on-media` badge/kicker/headline/lead) beside an equal-height card grid. A connected sequence (same `group`) repeats the rail treatment with a DIFFERENT photo per slide (variety ledger applies). PLAN should reach for PO-10 whenever a sequence of detail slides carries product or capability content.
- **Product logos are never boxed and never small.** No tiles, chips or containers around product logos; render them bare on the card at >=26px height (30px preferred). On a product-led card the LOGO IS THE TITLE: centered, above the subheader (also centered), description text left-aligned. The deck must read product-first - we are the solution.
- **Icon cards center the icon + subheader, keep the description left-aligned.** Same pattern as logo-led cards.
- **The WEIGHT LADDER - every text role has ONE weight (owner-approved 2026-08-13).** headline 800 (900 only for short display strings of <=4 words) | stat/KPI number 900 (the heaviest thing on its slide) | card/step title 700-800 | CTA 700 | kicker/label 700 + letterspacing | subhead/lead 500-600 at supporting scale (~17-20px - NEVER display-size bold; a 24px/700 subhead reads as a second headline) | body 400 (bold inline only for one scannable phrase, at most twice a slide) | caption/footnote 400. Skip a weight step between adjacent roles so hierarchy is legible; max ~3 weights per slide. All six Montserrat weights (400-900) ship in assets/fonts and embed at build - author exact weights, never rely on browser weight-snapping.
- **Photo-column captions: TITLE centered under the image, DESCRIPTION left-aligned.** In persona/photo-column layouts (a column of image + title + one-liner), the title centers under the image mass; the description below it is left-aligned prose (owner-refined 2026-08-13). This now matches the icon-card pattern: centered identity (icon/title/logo), left-aligned prose.
- **Fill the canvas - wasted container space is a defect.** Bodies >=13px at line-height ~1.55, titles 16-21px; vertically center card content so uneven copy reads as breathing room, not truncation; bottom-anchored chips only align when the row's copy lengths are balanced - balance the copy or don't bottom-anchor. When a cell still has slack, outsource a REAL element into it (owned image, Unsplash photo strip, logo row) - never leave dead panel. `engine/density_check.py` measures this mechanically at SWEEP.
- **Intelligent cropping - aim every crop at the photo's focal point (owner directive 2026-08-13).** `img-cover` defaults to a CENTER crop, which beheads or amputates any subject that sits off-center the moment the slot's aspect differs from the photo's (a landscape photo in a portrait column keeps the empty middle and cuts the people out). For EVERY photo placed in a slot: (1) LOOK at the source image (Read tool) and identify the focal subject - faces first, then the action (hands, device, document), using rule-of-thirds instincts; (2) set `object-position: X% Y%` on the img so the crop window contains that subject (e.g. subjects right-of-center -> ~60-70% x; faces in the upper third -> ~35-45% y); (3) REFERENCE BACK: screenshot the rendered slide and compare against the source - if the crop still misses the subject, adjust and re-check. Never ship a default center crop on an off-center photo.
- **Never crop a supplied product/marketing image.** Fit it whole (`object-fit:contain`) inside a white panel sized to its aspect ratio, and reshape the slide's content around it. Crop-to-fill (`img-cover`) is for photography, not product shots.
- **Product mockup PNGs: alpha-trim, never transform-scale.** If a transparent-margin asset renders small, cut a tight derivative (PIL: crop to thresholded alpha bbox, e.g. alpha>16) and register it in the catalog. `transform:scale` is forbidden - it exports without container clipping.
- **Design the slide AS the content's real-world artifact (the punch-list lesson, owner-praised 2026-08-13).** When content has a native physical form in the audience's world, render the slide as that artifact instead of a generic card grid: warning signs to watch -> a site PUNCH LIST (white ruled checklist sheet floating over a full-bleed jobsite photo with an ink scrim and a big white statement beside it); steps -> a numbered crew briefing; specs -> a drawing title block. A grid of line icons is the blandest possible answer ("AI-generated gloop") - reach for the concept first, the template second.
- **Decks are not websites - never render web-style buttons.** No pill/chip buttons labeled APPLY NOW or similar; a slide cannot be clicked. Calls-to-action are TYPOGRAPHIC statements (bold, letterspaced, accent colour). Pure web artifacts ("Apply now", "Submit") are cut entirely - and per the recomposition rule, the freed space is absorbed by the remaining elements without being asked.
- **Think freely about layout - dead space is YOUR problem to catch, not the reviewer's.** The renderer's output is a first draft, not a verdict. After rendering, LOOK at every slide (density_check + your own eyes): if containers sit half-empty because the copy is short, do not ship it and wait to be corrected - act autonomously: swap to a layout that fits the content's real weight, restack sparse rows into a tighter shape, add real imagery (owned first, Unsplash fallback) or catalog icons into the slack, or merge/split the content across slides. A card with a one-line body in a tall grid cell needs an icon, an image, or a smaller cell - never white air. The reviewer should NEVER have to flag wasted pixels; that correction has been given enough times.
- **Removing or changing an element MUST trigger a recomposition.** When a reviewer cuts content (a contact card, a column, a row), never leave the old skeleton with a hole in it - rethink the slide's composition around what remains (recenter the stack, rebalance the split, promote the imagery). A layout built for content that is no longer there is a defect, not a smaller version of the old slide.
- **Eyebrows/kickers must EARN their place - cut them by default (owner directive 2026-08-14).** A kicker survives ONLY when it adds information or wayfinding the headline lacks (e.g. "THE COMMISSION" under a figurative headline, "WHY PARTNER" framing a benefits grid). Cut any eyebrow that restates the headline ("HOW IT WORKS" over "Three steps to your first payout"), labels the obvious ("QUESTIONS" over "FAQs"), or exists as a brand pun ("BE SMRT"). At BUILD, audit every kicker with this test before rendering it.
- **Tone: clarity over cleverness - presentable corporate work (owner directive 2026-08-14).** No cute/clever labels, puns, or decorative wordplay in authored copy, kickers, badges, or section names. Plain, concrete language wins; a figurative line is acceptable only when it is the source content's own copy or paired with a plain-language anchor. When in doubt, say the thing directly.
- **Numerals are plain: 1, 2, 3 - never zero-padded 01/02/03.** Step numbers, stage counters, and list numerals render as single digits (owner directive 2026-08-13), in the stat weight (900) when they are the visual anchor - and CENTERED in their numeral column, so a single digit sits balanced where a two-digit numeral would have, never hugging one edge of its fixed-width slot.
- **Badges and tags anchor to the container they describe.** A "most popular"-style chip sits tight to a corner of ITS card (top-right preferred), never floating in open space between elements.
- **Icons must be contextually exact, not thematically adjacent.** Before picking from the catalog, restate what the row's copy actually SAYS and match that (a warning-signal row gets alert-triangle, a trades row gets wrench); when the copy names people, documents, money, or risk, the icon names it too. Close-enough icons are what reviewers keep correcting - if no catalog icon matches the actual meaning, omit it.
- **Invert layouts to keep the deck fresh.** Every split/rail/image layout has a legal MIRROR (rail left <-> rail right, image column side swap, numbered rows flipped). When nearby slides would repeat the same composition, invert one - the viewer should never see the same silhouette twice in a row. Within a connected group (same `group`), a mirror still counts as the same treatment, so sequences may alternate sides (photo-rail left on slide A, right on slide B) while keeping the shared visual language.
- **Never silently condense a prompt-slide.** A source slide that is really a prompt (a wall of strategy notes, "make this into a visual") gets its content preserved in full - expand into a connected multi-slide sequence if one slide can't legibly hold it, and surface every proposed cut at PLAN approval. Reviewers treat dropped substance as a defect even when the slide "looked done".

## Export safety (learned the hard way - SWEEP surfaces these as advisories)
The browser renders things the PPTX/PDF exporters cannot. At BUILD:
- **No CSS shape tricks** (rotated-border chevrons, transformed divs) - they export as stray marks. Decorative shapes are inline-SVG data-URI `<img>`s in an on-palette colour.
- **No `transform:scale` on images** - exports ignore container clipping (see alpha-trim rule above).
- **Small-print blocks (<13px) with 2+ inline `.product-name` spans** can merge their wrapped lines into one long paragraph at export - render boilerplate/footnotes as plain text (`brandify` off).
- **Hand-authored patch code:** zip() content lists against STYLE lists only after padding the style list to the content length - a short logos/icons list must never silently drop a content card. Deck copy drives; styling follows.
- **Verify every export against a real renderer.** On macOS PowerPoint's AppleScript is sandbox-blocked; use `python engine/verify_export_macos.py --plan <deck>/plan.json --pptx <deck>/out/deck.pptx --out-dir <dir>` (drives Keynote), then EYEBALL the renders against review.html. Fonts: PPTX only references Montserrat by name - install `assets/fonts/ttf/*.ttf` to `~/Library/Fonts` on any reviewing Mac (see that folder's README), and warn recipients without Montserrat that PowerPoint will substitute.

## Motion, product accent & bloom (BUILD) — use them, don't leave them dormant
The frontend ships three capabilities most decks forget to use. BUILD SHOULD apply them:
- **Scroll-reveal:** tag primary elements with `.reveal` (or `.reveal-left/right/scale/hero`).
  `deck.js` adds `.visible` staggered as each slide scrolls in; exports force the final state.
- **Product accent:** on a slide/card that features a product, set `--sb-product-accent` to that
  product's token (smrtGC=sky, smrtSUB=copper, smrtAE/smrtAEC=steel, smrt-E=pink). `.product-name` and
  `.kpi-num` adopt it automatically — colour-coordinate headers/stats to the product being discussed.
- **TOC click-to-jump (automatic):** any agenda / table-of-contents slide gets clickable
  entries - build.py detects it (topic contains agenda/contents/toc, or the section carries
  `data-toc`), matches each entry block's text against the other slides' headlines and
  topics, and stamps `data-jump="<slide uuid>"`; deck.js smooth-scrolls on click and the
  entry shows a pointer + hover underline. Works in review AND presentation; inert in
  edit/annotate modes and in PPTX/PDF exports. No authoring step needed - just write the
  agenda entries so they echo the slide headlines.
- **Bloom:** for expandable detail, use `_kit.bloom(pid, label, panel_html)` — a trigger button that
  irises a full-slide panel open from its position. Screen-only (hidden in PDF/PPTX).
  For a GRID of expandable topic tiles (the "expand more" pattern), use
  `_kit.bloom_grid(items)` — each tile clicks open into a theme-adaptive detail panel.

## Libraries
- **`layouts/library-v9/` — THE layout library (105 templates). PLAN picks template ids from `library-v9/catalog.json`; read `library-v9/INDEX.md` for the id + `story_job` of each.** Match a template's `story_job`/tags to the slide's need. Invent (`custom`) only when nothing fits; deck-local until review-promoted. `build.py` warns if a slide uses an id not in the catalog. (`layouts/layouts.json` is the legacy seed set, superseded by v9.)
- `libraries/icons/catalog.json` — Lucide icon set (the design system's own library — brand-correct, MIT, no attribution needed).
- `libraries/images/catalog.json` — curated, tagged, **owned/generated** images (don't hunt the web; pick by tag). Embed only used images at BRAND, compressed.

## Rendered template library (browse + edit all 104)
`layouts/library-v9/rendered-gallery.html` is a **self-contained, interactive browser of every v9 template rendered through the deck engine** — not the empty design shells (that's `library.html`), but the real renderers filled with sample content, correct in light and dark. It is a permanent skill artifact; ship the single file and everything travels with it.
- **Regenerate** whenever a renderer changes: `python engine/build_gallery.py` (builds the all-104 preview, then assembles the gallery). Do this after any `render_slides.py` renderer edit so the library stays current.
- **Features baked into the file:** family sections, click-to-zoom, light/dark toggle, **Edit mode** (a change-request box per template + a mass-change box), **Copy to Claude** (emits a structured payload of per-template + mass changes + soft-deletes), **soft-delete with restore**, and **localStorage persistence** keyed by template id (survives reloads and regeneration). Apply a returned payload by editing the named renderers in `render_slides.py`, then regenerate.
- **On every deck**, `build.py` embeds this library (base64, review-only) and the deck chrome shows a **Template Library** button (`▨`, in `ui.review.html`; handler in `deck.js`) that opens the full rendered library in a new tab. It is embedded only in `review.html`, never the client `presentation.html`. `build_gallery.py`'s own preview build passes `--no-library` to avoid recursion.

## Footer chrome & the no-go zone (BRAND)
BRAND bakes footer chrome per slide **by role** (`build.py` classifies via the v9 catalog):
- **Footer logo** (SmartBuild mark, bottom-left). **Brand rule: at most ONE SmartBuild logo per slide.** The footer logo is added to non-cover slides **only when the slide does not already carry its own SmartBuild mark** (a closing badge, a hero wordmark, etc.); if it does, the footer logo is skipped so the slide never shows two. Covers carry their own mark and no footer chrome. The footer mark **auto-contrasts by background luminance between the only two real logos: the WHITE logo on dark/busy backgrounds and the FULL-COLOUR logo on light backgrounds** (`deck.js` samples the bg behind it). There is **NO black SmartBuild logo** - never render one; light backgrounds get the full-colour mark, not a blacked-out one. SWEEP hard-fails any slide with more than one SmartBuild logo.
- **Page number** (bottom-right) on **content** slides only; **hidden on covers, sections, and closings**. Numbering uses true slide position.
- **No-go zone:** the bottom `--sb-safe-bottom` (54px) strip is reserved for the chrome. **Bottom-anchored content (takeaway bands, CTAs) must stop above it** — use `class="sb-safe-bottom"` on full-bleed bottom bands so they push up and never sit under the logo/number. SWEEP verifies chrome counts by role.

## Continuous template-improvement loop
**In the active deck you can change anything freely** — apply every edit the reviewer wants, no restrictions. The loop is about what happens to *good, reusable ideas*:
- When an edit reflects a **template-level** improvement (would help any deck using that layout), **apply it to the master template in the same session** (owner directive 2026-08-13: reviewer-driven fixes influenced by templates are adjusted at the template, not merely banked), log it in `layouts/TEMPLATE-IMPROVEMENTS.md` (template id, issue, fix, date), and **regenerate the rendered gallery** (`python engine/build_gallery.py`) so the library reflects reality.
- Template changes still do **not** silently flow *down* into existing decks — a deck adopts a newer template only on a deliberate refresh.
- **Existing/in-flight decks are unaffected** by later master-template changes — a deck adopts a newer template only on a deliberate refresh.
So: active deck = total freedom; master templates = protected and improved via the gated feedback stack. That's what keeps quality compounding without surprising in-flight work.

## Hand-off / packaging
Before a non-author runs this, `python packaging/preflight.py` verifies fonts, logos, tokens, schema, libraries, and engine are all present and valid. See `packaging/manifest.json`.

## What v5 fixed vs v4
Unenforced rules → an actual sweep. Guessing pins → UUID-anchored self-describing pins. Hand-built 8-slide ceiling → any length. Viewport-dependent export → fixed 1280×720 canvas. Random Unsplash → owned tagged library. No fact-checking → content-fidelity gate. One tangled file → six focused passes over one plan.
