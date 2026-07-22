# Per-template render files (Phase 2)

**Goal (closes the improvement loop):** one **shared** render file per template, so a fix
to a template propagates to *every* deck that uses it — instead of each deck copying the
render logic into its own `generate.py` (where a fix reaches only that deck).

Today rendering is partly **deck-local**: `examples/us-construction-market/generate.py`
carries its own renderer functions + a `RENDER = {name: fn}` dispatch table. This
directory is where that logic moves to become shared. This is Tom & Zain's build-out home.

## The pattern

- One module per catalog **`renderer`** value (the durable template identity), named
  `<renderer>.py` — e.g. NM-01's `renderer` is `narrative_split` → `narrative_split.py`.
- Each module exposes exactly:

  ```python
  def render(c, d) -> str:   # returns the slide's <div class="stage">…</div> HTML
  ```

- **`c` — the block emitter** (a "context"). The host passes an object implementing:
  `c.b(key, typ, html, tag="span", cls="", style="", facts=None) -> str` (mints a stable
  `block_uuid`, records the block on the plan, returns the `data-block`-tagged element)
  and `c.sid` (the slide seed). Render files call *only* `c.b(...)` — they never mint
  uuids or touch plan state, so uuid lifecycle + fact wiring stay with one owner.
- **`d` — the slot data.** Each file documents the `d` keys it needs in its top docstring;
  that docstring is the template's data contract (the catalog `slot_schema` is the
  human-facing mirror).
- Shared primitives (`stage()`, `ACCENT`) live in `_kit.py` so they're defined once.
- `render` returns a **string only** — no file/catalog/PPTX access. build.py adds chrome,
  embeds assets, and wraps the skeleton downstream.

## Converted so far (proof of pattern — non-chart only)

| File | Template | Catalog `renderer` | Shape |
|------|----------|--------------------|-------|
| `narrative_split.py` | NM-01 | `narrative_split` | split |
| `three_stats.py` | NM-02 | `three_stats` | n-across |
| `section_gradient.py` | CV-04 | `section_gradient` | section |
| `four_panel.py` | NM-06 | `four_panel` | grid |

Bodies are ported verbatim from `generate.py`'s deck-local renderers, so output is
byte-identical — this move centralises, it doesn't restyle. The remaining ~100 templates
are unconverted; `load()` raises `KeyError` for those and hosts fall back to local render.

### Not converted here: chart renderers
`donut`, `bar_highlight`, `waterfall`, `pareto`, `funnel`, `forecast`, `heatmap`, `gantt`,
`dashboard`, … are **owned by the PPTX export thread** — they carry a declarative
`data-chart` spec that is rebuilt as a native editable PowerPoint chart, and the donut is
drawn as inline SVG for PDF safety. Forking that logic here would break it. They stay out
until that thread and this scaffold are reconciled (see `load()`'s `CHART_RENDERERS`).

## How `generate.py` will consume these (integration point — NOT wired yet)

`generate.py` currently builds its dispatch table by hand:

```python
RENDER = {"split_stat": split_stat, "three_stats": three_stats, "section": section, …}
fn = RENDER[d["fn"]]
inner_html = fn(c, d)
```

The Phase-2 wiring keeps generate.py's local functions as the fallback and prefers a
shared render file when one exists, dispatching off the **catalog `renderer`** for the
slide's `family`:

```python
import sys, os
sys.path.insert(0, os.path.join(SKILL, "layouts"))
import renderers                       # this package

def render_slide(c, d, catalog_by_id):
    renderer = catalog_by_id.get(d["family"], {}).get("renderer")
    try:
        return renderers.load(renderer)(c, d)     # shared file — fix propagates to all decks
    except KeyError:
        return RENDER[d["fn"]](c, d)               # local fallback until this one is converted
```

Requirements for the host `c`: implement the `c.b(...)` / `c.sid` protocol above.
`generate.py`'s existing `Ctx` already does (its `Ctx.b` matches the signature), and its
`stage()`/`ACCENT` are the same primitives now centralised in `_kit.py`. **This scaffold
does not modify `generate.py`** — wiring it in (and reconciling the chart renderers) is
the next step, owned by the layouts thread with Rowan on the engine side.

## Governance
Changing a shared render file is a **template change** → it goes through the stage-gate
and bumps the template's `version` (see `../GATE.md`). Bank ideas in
`../TEMPLATE-IMPROVEMENTS.md` first.
