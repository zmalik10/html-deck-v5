"""
SmartBuild Deck v5 — preflight.py
Verifies a fresh install is complete and valid before a non-author runs it.
Exit 0 = ready; 1 = something missing/invalid.
"""
import json, os, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
results = []

def ok(name, cond, detail=""):
    results.append((name, bool(cond), detail))

def exists(*parts):
    return os.path.exists(os.path.join(SKILL, *parts))

def parses(*parts):
    try:
        with open(os.path.join(SKILL, *parts), encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception as e:
        return False

# runtime
ok("Python >= 3.8", sys.version_info >= (3, 8), sys.version.split()[0])
try:
    import jsonschema  # noqa
    ok("jsonschema available (full validation)", True)
except ImportError:
    ok("jsonschema available (optional)", True, "absent — using structural fallback (fine)")

# assets
fonts = [f for f in ("montserrat-400.woff2", "montserrat-700.woff2", "montserrat-900.woff2") if exists("assets", "fonts", f)]
ok("Fonts present (3 woff2)", len(fonts) == 3, "%d/3" % len(fonts))
logos = [f for f in ("smartbuild.4c.svg", "smrt-GC.4c.svg", "smrt-SUB.4c.svg", "smrt-AE.4c.svg", "smrt-AEC.4c.png", "smrt-E.4c.svg") if exists("assets", "logos", f)]
ok("Logos present (6: 5 svg + smrtAEC png)", len(logos) == 6, "%d/6" % len(logos))
ok("tokens.json parses", parses("assets", "tokens", "tokens.json"))

# schema
ok("plan.schema.json parses", parses("schema", "plan.schema.json"))

# frontend
for f in ("base.css", "deck.js", "ui.common.html", "ui.review.html"):
    ok("frontend/%s present" % f, exists("frontend", f))

# libraries
ok("layouts.json parses", parses("layouts", "layouts.json"))
ok("icons/catalog.json parses", parses("libraries", "icons", "catalog.json"))
ok("images/catalog.json parses", parses("libraries", "images", "catalog.json"))

# engine
for f in ("build.py", "validate.py", "fidelity.py"):
    ok("engine/%s present" % f, exists("engine", f))

# reference-library (the Slide Vault that ships bundled) — presence + derived index
ok("reference-library/catalog.json parses", parses("layouts", "reference-library", "catalog.json"))
ok("reference-library/index.json present (run build_reference_index.py)",
   exists("layouts", "reference-library", "index.json"))
ok("reference-library/entries/ present", os.path.isdir(os.path.join(SKILL, "layouts", "reference-library", "entries")))
# SECURITY: no packaged catalog/index/entries may contain an absolute local path
try:
    import glob as _glob
    sys.path.insert(0, os.path.join(SKILL, "engine"))
    from build_reference_index import find_local_paths as _flp
    _leaks = 0
    _refdir = os.path.join(SKILL, "layouts", "reference-library")
    _files = [os.path.join(_refdir, "catalog.json"), os.path.join(_refdir, "index.json")]
    _files += _glob.glob(os.path.join(_refdir, "entries", "*.json"))
    for _p in _files:
        if os.path.exists(_p):
            with open(_p, encoding="utf-8") as _f:
                _leaks += len(list(_flp(json.load(_f))))
    ok("No local-path leaks in packaged library data", _leaks == 0,
       "%d absolute local path(s) found — re-run build_reference_index.py" % _leaks if _leaks else "")
except Exception as _e:
    ok("Local-path leak scan ran", False, "scan error: %s" % _e)
# bundle size guard (Cowork import): the packaged skill data should stay small
try:
    # Approximate the SHIPPED payload: skip the same heavy items .coworkignore drops.
    _total = 0
    for _root, _dirs, _fs in os.walk(SKILL):
        _dirs[:] = [d for d in _dirs if d not in
                    ("__pycache__", ".git", "examples", ".local", "rendered", "extracted")]
        for _fn in _fs:
            if _fn == "library.html":
                continue
            _total += os.path.getsize(os.path.join(_root, _fn))
    _mb = _total / (1024 * 1024)
    ok("Bundle size under 10 MB (Cowork-importable)", _mb < 10, "%.1f MB" % _mb)
except Exception:
    pass

# SRI advisory
try:
    import re
    bp = open(os.path.join(SKILL, "engine", "build.py"), encoding="utf-8").read()
    empties = bp.count('"integrity": ""')
    ok("SRI hashes set (advisory for client export)", empties == 0,
       "%d export libs have empty integrity — fill before client-facing export" % empties if empties else "")
except Exception:
    pass

passed = sum(1 for _, c, _ in results if c)
print("PREFLIGHT: %d/%d\n" % (passed, len(results)))
for name, c, detail in results:
    print(("  OK   " if c else "  FAIL ") + name + (("  — " + detail) if detail else ""))
# SRI is advisory-only; don't fail the whole preflight on it
hard = [r for r in results if not r[1] and not r[0].startswith("SRI")]
sys.exit(0 if not hard else 1)
