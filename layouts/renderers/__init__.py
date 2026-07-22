"""Per-template render files (Phase 2).

One module per catalog `renderer`, each exposing `render(c, d) -> str`. `load(name)`
resolves a renderer name (the catalog's `renderer` field) to that callable, so a host
can dispatch straight off the catalog without a hand-maintained name->function table.

Usage from a host (e.g. a deck's generate.py or a future engine authoring pass):

    import sys; sys.path.insert(0, str(skill_path / "layouts"))
    import renderers
    fn = renderers.load(catalog[slide.family]["renderer"])   # e.g. "narrative_split"
    html = fn(ctx, data)                                     # ctx = block emitter, data = slots

See `_kit.py` for the block-emitter (`c`) protocol and `README.md` for the full pattern
and the generate.py integration point.
"""
import importlib

# Chart/data renderers are intentionally NOT provided here — they are owned by the PPTX
# export thread (donut/bar/etc. carry a declarative `data-chart` spec rebuilt as native
# editable PPT charts). Converting them here would fork that logic. Non-chart templates
# only, until that thread and this scaffold are reconciled.
CHART_RENDERERS = frozenset({
    "donut", "bar_highlight", "waterfall", "pareto", "funnel", "forecast",
    "heatmap", "gantt", "dashboard", "bubbles", "matrix2x2",
})


def available():
    """Renderer names with a shared render file present in this directory."""
    import os
    here = os.path.dirname(__file__)
    return sorted(
        f[:-3] for f in os.listdir(here)
        if f.endswith(".py") and not f.startswith("_") and f != "__init__.py"
    )


def load(name):
    """Return the `render(c, d)` callable for a catalog renderer name.

    Raises KeyError if no shared render file exists yet (most of the 105 templates —
    this scaffold converts only a few as proof). Hosts should fall back to their local
    renderer for names not yet converted; see README.
    """
    if name in CHART_RENDERERS:
        raise KeyError("%r is a chart renderer (owned by the PPTX export thread); not provided here" % name)
    try:
        mod = importlib.import_module("." + name, __package__)
    except ModuleNotFoundError:
        raise KeyError("no shared render file for renderer %r (not converted yet)" % name)
    return mod.render
