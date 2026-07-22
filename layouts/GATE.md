# Template & Reference-Library Stage-Gate

How a **shared master** (a layout template, or a reference-library entry) changes.
The one rule this enforces: **suggestions flow UP; approved changes bump a version;
versioned changes never auto-flow DOWN into in-flight decks.**

This is the governance side of the continuous-improvement loop described in `SKILL.md`
and banked in `TEMPLATE-IMPROVEMENTS.md`. Read those first for the *why*; this file is
the *how* and the promotion checklist.

---

## What this gate governs

1. **Layout templates** — the 105 entries in `library-v9/catalog.json` (each carries a
   `version`), mastered in the browsable library HTML.
2. **Reference-library entries** — curated, reviewed, reusable content slides (About
   SmartBuild, About smrt-E, bios, etc.) and the deck archive. *Not built yet* (see
   HANDOVER open item #1), but it is versioned by the **same** gate: each entry carries
   a `version`, and a deck that reuses it stamps the `ref_version` it consumed into the
   slide's `provenance` (schema `$defs/provenance`).

Both are **shared masters**: many decks depend on them, so a change to one can ripple.
The gate keeps that ripple deliberate.

---

## The core nuance (do not lose this)

- **The active deck is fully editable.** Change anything in your working deck; nothing
  here locks it.
- **Template/reference-level ideas get *banked* as suggestions**, not applied to the
  master. For templates that means a row in `TEMPLATE-IMPROVEMENTS.md`; for reference
  entries, the equivalent feedback stack for that store.
- **Masters change ONLY through this gate** (owner review → PR → version bump).
- **A version bump never silently flows down.** Existing / in-flight decks keep rendering
  the version they already consumed. They adopt a newer version only on a **deliberate
  refresh**. The run manifest records what each deck actually consumed (see below), so
  "which version is this deck on?" is always answerable.

---

## Promotion workflow (banked suggestion → shipped version)

1. **Bank** — a reviewer logs the idea:
   - Template: append a row to `layouts/TEMPLATE-IMPROVEMENTS.md`
     (`Date | Template(s) | Issue | Proposed fix`). Mark it `PENDING`.
   - Reference entry: log it in that store's feedback stack (same shape).
2. **Owner review** — the zone owner (templates: Tom & Zain; reference library: TBD)
   triages banked suggestions. Accept, revise, or decline. Declined items stay logged
   with the reason.
3. **PR** — the owner implements the accepted change in the **master**
   (the browsable library HTML for templates; the reference store for entries) and opens
   a git PR. The PR description names the affected id(s) and the intended bump level.
4. **Version bump** — bump the entry's `version` per the rules below **in the same PR**.
   No master change lands without a bump; no bump lands without a master change.
5. **Sync + commit** — for templates, regenerate the catalog with
   `python engine/sync_library.py --html "<library.html>"` and commit
   `catalog.json` + `INDEX.md`. (See the **resync caveat** below.)
6. **Adopt deliberately** — decks pick up the new version only when someone re-runs the
   relevant pass against the updated master. Never automatic.

---

## Version bump rules (per entry, semver-ish `MAJOR.MINOR.PATCH`)

| Level | When | Examples |
|-------|------|----------|
| **PATCH** | Visual / spacing / copy-in-template fix. **No slot or structure change.** | tighten a divider, fix contrast, nudge padding |
| **MINOR** | **Additive, back-compatible.** New optional slot/option; old decks still render unchanged. | add an optional badge slot, add a color option |
| **MAJOR** | **Breaking.** Slot renamed/removed, structure changed; old plans may not map. | drop a required slot, re-topology the layout |

Default for every entry today: **`1.0.0`**. The same table applies to reference-library
entries (a MAJOR there means the reused content's meaning/structure changed enough that
a deck should re-review before adopting).

---

## How a deck records what it consumed (the down-flow firewall)

`build.py`'s **run-manifest writer** stamps, per slide:

```json
"slides": [
  { "slide_uuid": "...", "template_id": "CV-01", "template_version": "1.0.0",
    "provenance": { "source": "reference-library", "ref_id": "ref-about-smartbuild",
                    "ref_version": "3.1.0", "title": "About SmartBuild" } }
]
```

- `template_version` = the plan's per-slide `templateVersion` if pinned, else the current
  catalog `version`. Either way it is a **record of what rendered**, so a later gated bump
  to the master cannot retroactively change this deck's manifest.
- `provenance` is passed through verbatim from the slide (schema `$defs/provenance`),
  giving the reference-library / deck-archive lineage and the `ref_version` consumed.
- `template_unverified: true` appears when a slide's `family` is not a catalog id
  (an invented `custom`-style layout) — a signal it hasn't been through the gate at all.

---

## Source of truth for `version`

- **Templates:** the per-template `version` in `library-v9/catalog.json` (mirrored in
  `INDEX.md`). Long-term this should live in the **browsable library master HTML** so it
  survives a resync.
- **Reference entries:** the per-entry `version` in the reference store (when built).

### ⚠ Resync caveat (engine follow-up, owner: Rowan)

`catalog.json` is **generated** by `engine/sync_library.py` from the master library HTML.
Today `sync_library.py` copies each template's metadata **except `version` is not yet
carried from / defaulted by the master**, so a naive resync could drop versions back out.
Until the master HTML carries `version` per template (and `sync_library.py` preserves it,
defaulting missing to `1.0.0`), **a resync must re-apply versions** — do not blindly
overwrite `catalog.json` from an unversioned master. Tracked as an `engine/` task
(out of scope for this `layouts/` change, which added the field and the convention).
