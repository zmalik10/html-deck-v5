# Reference Library — search-and-reuse before you author

This directory is the deck builder's **content memory**. It has two stores and one rule.

> **The rule:** PLAN never reinvents content that is already published. It **searches here first**,
> **reuses** what fits, **adapts** near-matches, and only **authors net-new** when nothing fits.
> It is *not* limited to what's here — it just never rebuilds a slide that already exists.

## The two stores

### 1. `catalog.json` — canonical & curated content slides
Finished, reviewed **content** slides carrying the **actual words** (not empty layout shapes — that's
`layouts/library-v9/`). Each entry is one reusable slide. **Canonical** entries are the single approved
rendering of a recurring slide; they rank first for their role.

Seeded canonical entries (all `status:"draft"` until real published content is ingested):

| ref_id | title | role | layout_hint | canonical |
|---|---|---|---|---|
| `REF-about-smartbuild` | About SmartBuild | about | NM-01 | ✅ |
| `REF-about-smrt-e` | About smrt-E | about | NM-07 | ✅ |
| `REF-bio-rowan` | Bio — Rowan Steel Hall | bio | WT-05 | ✅ |
| `REF-bio-zulq` | Bio — Zulq | bio | WT-05 | ✅ |
| `REF-bio-vinay` | Bio — Vinay | bio | WT-05 | ✅ |

> **Draft status matters.** `status:"draft"` means the *words* are a best-effort seed, not verified
> published copy. Draft entries are still searchable and reusable, but PLAN should flag "(draft — confirm
> copy)" when it reuses one, and they must be replaced by the first ingest of the real slide. `REF-bio-zulq`
> and `REF-bio-vinay` carry placeholder role/credential copy and **must not** go to a client until replaced.

**Entry shape** (see `summary.entry_fields` for the authoritative list):
- `ref_id`, `title`, `role`, `entities[]`, `topics[]`, `audience[]`
- `canonical` (bool), `status` (`draft`|`published`), `layout_hint` (a library-v9 id)
- `content_hash` — `sha256:16` over the fragment's content (drift detection)
- `approved_facts[]` — the facts the fragment's `fact_refs` point at (merged into the plan on reuse)
- `provenance` — where this entry came from (`origin`, `source_deck`, `source_path`, `ingested_at`, `note`)
- `used_in[]` — the reuse log (provenance stamps; see below)
- `planFragment` — a full `plan.schema.json` **slide object** (real content blocks with UUIDs)

### 2. `archive.json` — the searchable deck archive
A per-slide index of **every past/published deck**, built by `engine/ingest_decks.py` from real files
(`.pptx`/`.pdf`/`.html`). Each slide: `title`, `text`, `role`, `entities`, `content_hash`. PLAN searches
this next to the catalog so it can reuse/adapt real prior slides. Recognizable About/bio slides are
**promoted** into `catalog.json` as canonical candidates. Empty until the first ingest.

## content_hash — one algorithm, everywhere
`sha256:16` = `"sha256:"` + first 16 hex chars of `sha256(json.dumps(parts, ensure_ascii, no-space))`,
where `parts` is an **ordered, stripped** list of strings. Identical `content_hash()` helper lives in
`engine/ingest_decks.py` and `engine/reference_search.py`.
- catalog entry → `parts` = active planFragment block texts + fact values/texts
- archive slide → `parts` = `[title, text]`
- archive deck → `parts` = its ordered per-slide hashes (drives idempotent re-ingest)

## Provenance — stamped on every reused/adapted slide
When PLAN **reuses or adapts** a slide, `reference_search.record_reuse()` appends a provenance stamp to the
source's `used_in[]` (catalog `entry.used_in` for library reuse; archive `slide.used_in` for archive reuse).
**Net-new authored slides are `source:"authored"` and carry no stamp** — the point is to trace *reused
published content*, not everything.

Provenance is recorded **in this library, not inline in `plan.json`** — the plan schema
(`schema/plan.schema.json`) sets `additionalProperties:false` on slides/blocks, so an inline provenance key
would fail SWEEP's validation. Keeping the stamp here is non-breaking and keeps a per-entry reuse history.

Stamp shape (see `summary.provenance_contract.shape`):
```
{ ref_id, archive_id, source, reuse, canonical, content_hash, deck_title, reused_at_revision, adapted_note }
```

## How PLAN uses this (wired in SKILL.md · PASS 1 and PLAN.md)
1. **Search** the library + archive for each slide need (`engine/reference_search.py`).
2. **Auto-reuse** a canonical entry when the narrative calls for its role (About/bio) and audience fits.
3. **Suggest** fuzzy/near matches for human confirmation rather than silently pulling them.
4. **Stamp provenance** on every reused/adapted slide via `record_reuse()`.
5. **Author net-new** only when nothing fits — never rebuild already-published content.

## Commands
```bash
# ingest a decks folder into the archive (+ promote About/bio into the catalog)
python engine/ingest_decks.py                     # default src (see --help), idempotent
python engine/ingest_decks.py --src "<folder>" --dry-run

# search from PLAN (prints ranked JSON; canonical first)
python engine/reference_search.py --role about --entity SmartBuild
python engine/reference_search.py --text "who we are" --audience client
```
