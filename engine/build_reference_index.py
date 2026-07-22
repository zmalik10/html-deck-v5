"""
build_reference_index.py — derive the lightweight search index + full per-entry
records from the authored reference-library catalog, and SCRUB local paths.

`catalog.json` stays the single authored source of truth. This generator emits:
  - layouts/reference-library/index.json          (tiny: search/suggest only)
  - layouts/reference-library/entries/<ref_id>.json  (full: planFragment, facts, render)
and rewrites catalog.json with local absolute paths scrubbed to repo-relative IDs.

PLAN loads index.json to suggest; the full entry loads on acceptance. Loaders fall
back to catalog.json when the derived files are absent (see reference_search.py).

Run after editing the catalog (or in packaging preflight):
    python engine/build_reference_index.py --skill-path .
"""
import argparse, json, os, re

# Absolute-local-path signatures we must never publish (drive letters, UNC, home dirs).
LOCAL_PATH_RE = re.compile(
    r"""([A-Za-z]:[\\/])            # C:\  or  C:/
        | (\\\\[^\\/]+\\)           # \\server\
        | (/(?:Users|home)/[^/\s]+) # /Users/x  /home/x
        | (AppData[\\/])            # ...AppData\
        | (Users[\\/]rowan)         # Users\rowan
        | (/mnt/[^/\s]+)            # cowork session mnt
     """, re.VERBOSE)


def find_local_paths(obj, path=""):
    """Yield (json_path, value) for every string holding an absolute local path."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from find_local_paths(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from find_local_paths(v, path + "[%d]" % i)
    elif isinstance(obj, str) and LOCAL_PATH_RE.search(obj):
        yield path, obj


def scrub(obj):
    """Return obj with local-path strings replaced. Provenance keeps a repo-relative
    source_id; any other stray absolute path is blanked. Non-destructive to structure."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "source_path" and isinstance(v, str) and LOCAL_PATH_RE.search(v):
                # keep only the basename as a repo-relative id; drop the machine path
                out["source_id"] = os.path.basename(v.replace("\\", "/"))
            else:
                out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str) and LOCAL_PATH_RE.search(obj):
        return ""     # blank any other stray absolute path
    return obj


def derive_description(entry):
    """A curated one-line description if authored, else a sensible derived fallback."""
    if entry.get("description"):
        return entry["description"]
    role = (entry.get("role") or "slide").strip()
    title = re.sub(r"\s+", " ", (entry.get("title") or "").strip())
    if len(title) > 90:
        title = title[:87] + "..."
    return ("%s slide — %s" % (role.capitalize(), title)).strip(" —")


def index_row(entry):
    """The lightweight, search-only record (no planFragment / no renders)."""
    return {
        "ref_id": entry.get("ref_id"),
        "description": derive_description(entry),
        "tags": entry.get("tags", []),
        "use_when": entry.get("use_when", ""),
        "role": entry.get("role"),
        "entities": entry.get("entities", []),
        "topics": entry.get("topics", []),
        "audience": entry.get("audience", []),
        "canonical": bool(entry.get("canonical")),
        "status": entry.get("status", "published"),
        "layout_hint": entry.get("layout_hint"),
        "content_hash": entry.get("content_hash"),
    }


def generate(skill_path):
    refdir = os.path.join(skill_path, "layouts", "reference-library")
    catp = os.path.join(refdir, "catalog.json")
    if not os.path.exists(catp):
        raise SystemExit("no catalog.json at %s" % catp)
    with open(catp, encoding="utf-8") as f:
        cat = json.load(f)

    # 1) scrub the authored catalog in place (removes the leaked temp source_path)
    cat = scrub(cat)
    leaks = list(find_local_paths(cat))
    if leaks:
        raise SystemExit("scrub failed — local paths remain: %s" % leaks[:3])
    _write(catp, cat)

    entries = cat.get("entries", [])
    # 2) index.json (tiny)
    index = {"summary": {"count": len([e for e in entries if e.get("status") != "deleted"])},
             "entries": [index_row(e) for e in entries if e.get("status") != "deleted"]}
    _write(os.path.join(refdir, "index.json"), index)

    # 3) entries/<ref_id>.json (full, scrubbed)
    edir = os.path.join(refdir, "entries")
    os.makedirs(edir, exist_ok=True)
    written = 0
    for e in entries:
        rid = e.get("ref_id")
        if not rid or e.get("status") == "deleted":
            continue
        _write(os.path.join(edir, rid + ".json"), e)
        written += 1

    return {"catalog_scrubbed": catp, "index": len(index["entries"]), "entries": written}


def _write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    res = generate(args.skill_path)
    print("reference index built: %d index rows, %d full entries; catalog scrubbed (%s)"
          % (res["index"], res["entries"], os.path.basename(res["catalog_scrubbed"])))


if __name__ == "__main__":
    main()
