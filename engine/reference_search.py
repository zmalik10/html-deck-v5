"""
Reference-library + deck-archive search — the helper PLAN calls BEFORE authoring.

PLAN's rule: never reinvent published content. This module searches the two stores
in layouts/reference-library/ (catalog.json = curated/canonical content slides;
archive.json = every past deck's slides) and returns ranked matches so PLAN can:
  1) AUTO-reuse a canonical entry when the narrative calls for its role,
  2) SUGGEST fuzzy/near matches for human confirmation,
  3) stamp provenance on reuse via record_reuse().

Ranking: canonical entries rank first for their role. Everything is scored on
role / entity / topic / audience / free-text overlap; published outranks draft.

Usage (CLI, prints ranked JSON — canonical first):
    python engine/reference_search.py --role about --entity SmartBuild
    python engine/reference_search.py --text "who we are" --audience client --limit 5
    python engine/reference_search.py --role bio --entity "Rowan"

Usage (from PLAN, in-process):
    from reference_search import query, record_reuse, best_canonical
    hits = query(role="about", entity="SmartBuild", audience="client")
    entry = best_canonical(role="about")            # the one to auto-reuse, or None
    record_reuse(entry, deck_title="Gaylor …", reuse="verbatim", plan_revision=1)
"""
import argparse, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REFDIR = os.path.join(SKILL, "layouts", "reference-library")
CATALOG = os.path.join(REFDIR, "catalog.json")
ARCHIVE = os.path.join(REFDIR, "archive.json")
INDEX = os.path.join(REFDIR, "index.json")            # derived, lightweight (search)
ENTRIES_DIR = os.path.join(REFDIR, "entries")          # derived, full per-entry records


# --- content_hash: MUST stay identical to engine/ingest_decks.py -------------
def content_hash(parts):
    """sha256:16 over an ordered, stripped list of strings."""
    norm = [(p or "").strip() for p in parts]
    payload = json.dumps(norm, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def blocks_hash(content_blocks):
    """Drift baseline: content_hash over active block TEXTS only. Facts are excluded
    on purpose — approved-fact changes are already caught by the fidelity gate, and
    text-only keeps the hash stable (no fact-ordering churn). MUST stay byte-identical
    to validate._reuse_content_hash (that copy carries the same warning)."""
    parts = [b.get("text", "") for b in (content_blocks or [])
             if b.get("status", "active") != "deleted"]
    return content_hash(parts)


def inline_provenance(entry, plan_revision=0, reuse="verbatim"):
    """Build the SCHEMA-CONFORMANT inline provenance stamp for a reused reference-library
    slide. This goes on the plan slide's `provenance` (schema $defs/provenance) and is a
    DIFFERENT shape from the `used_in[]` stamp built by _provenance(): _provenance is the
    library-side reverse index; this is the deck-side drift baseline + attribution. Both
    are written on reuse (see SKILL.md PLAN step). Carries blocks_hash so SWEEP can flag
    divergence from the published master. Accepts either a raw catalog entry OR a query()/
    best_canonical() hit (which wraps the entry under `entry`) — unwraps so callers can't
    accidentally stamp an empty baseline."""
    entry = entry.get("entry", entry) if isinstance(entry, dict) else entry
    frag = entry.get("planFragment", {}) or {}
    return {
        "source": "reference-library",
        "ref_id": entry.get("ref_id"),
        "ref_version": str(entry.get("version", "1")),
        "blocks_hash": blocks_hash(frag.get("content_blocks", [])),
        "reuse": reuse,
        "reused_at_revision": plan_revision,
    }


def _load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_catalog():
    return _load(CATALOG) or {"summary": {}, "entries": []}


def load_archive():
    return _load(ARCHIVE) or {"summary": {}, "decks": [], "slides": []}


def load_index():
    """Derived lightweight search index, or None if not generated (build_reference_index.py)."""
    return _load(INDEX)


def get_full_entry(ref_id):
    """Full per-entry record: entries/<ref_id>.json, else fall back to the catalog entry.
    entries/ holds planFragment + render POINTERS + facts (all small text) — NOT the heavy
    render HTML (that loads only at BUILD via load_reference_render)."""
    if not ref_id:
        return None
    e = _load(os.path.join(ENTRIES_DIR, ref_id + ".json"))
    if e is not None:
        return e
    for e in load_catalog().get("entries", []):
        if e.get("ref_id") == ref_id:
            return e
    return None


def _tokens(s):
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) > 1]


def _lc_list(xs):
    return [str(x).lower() for x in (xs or [])]


def _fragment_text(entry):
    """All searchable words a catalog entry carries."""
    frag = entry.get("planFragment", {}) or {}
    parts = [entry.get("title", ""), entry.get("topic", ""), frag.get("topic", "")]
    parts += [b.get("text", "") for b in frag.get("content_blocks", []) if b.get("status", "active") != "deleted"]
    parts += [f.get("text", "") for f in entry.get("approved_facts", [])]
    parts += list(entry.get("topics", []))
    return " ".join(parts)


def _score(cand, role, entity, topic, audience, text):
    """Uniform scorer for a normalized candidate dict."""
    score = 0.0
    reasons = []

    c_role = (cand.get("role") or "").lower()
    c_entities = _lc_list(cand.get("entities"))
    c_topics = _lc_list(cand.get("topics"))
    c_audience = _lc_list(cand.get("audience"))
    haystack = cand.get("_haystack", "").lower()

    if role:
        if c_role == role.lower():
            score += 5; reasons.append("role")
        elif role.lower() in haystack:
            score += 1
    if entity:
        e = entity.lower()
        if any(e == x or e in x or x in e for x in c_entities):
            score += 4; reasons.append("entity")
        elif e in haystack:
            score += 1.5; reasons.append("entity~")
    if topic:
        t = topic.lower()
        if any(t == x or t in x for x in c_topics):
            score += 2; reasons.append("topic")
        elif t in haystack:
            score += 0.8
    if audience:
        if audience.lower() in c_audience:
            score += 1; reasons.append("audience")
    if text:
        toks = set(_tokens(text))
        hits = sum(1 for tk in toks if tk in haystack)
        if hits:
            score += min(hits, 5); reasons.append("text:%d" % hits)

    # canonical priority: dominate for the role it owns, plus a general nudge.
    if cand.get("canonical"):
        score += 20
        reasons.append("canonical")
        if role and c_role == role.lower():
            score += 100  # a canonical entry is THE answer for its role
    # published copy beats draft copy on ties.
    if cand.get("status") == "published":
        score += 3
    elif cand.get("status") == "draft":
        score -= 0.5

    return score, reasons


def _classify(cand, reasons, has_role_query):
    if cand.get("canonical") and ("role" in reasons):
        return "canonical"
    if "entity" in reasons and ("role" in reasons or "topic" in reasons):
        return "strong"
    return "fuzzy"


def query(role=None, entity=None, topic=None, audience=None, text=None,
          sources=("catalog", "archive"), limit=None, min_score=0.5):
    """Ranked matches across the reference-library + archive. Canonical first for its role."""
    cands = []

    if "catalog" in sources:
        idx = load_index()
        if idx is not None:
            # Search the lightweight derived index (no planFragment / no renders loaded).
            for r in idx.get("entries", []):
                if r.get("status") == "deleted":
                    continue
                cands.append({
                    "source": "reference-library",
                    "ref_id": r.get("ref_id"),
                    "archive_id": None,
                    "title": r.get("description") or r.get("ref_id"),
                    "role": r.get("role"),
                    "entities": r.get("entities", []),
                    "topics": r.get("topics", []),
                    "audience": r.get("audience", []),
                    "canonical": bool(r.get("canonical")),
                    "status": r.get("status"),
                    "layout_hint": r.get("layout_hint"),
                    "content_hash": r.get("content_hash"),
                    "_haystack": " ".join([r.get("description", ""), " ".join(r.get("tags", [])),
                                           " ".join(_lc_list(r.get("topics"))), " ".join(_lc_list(r.get("entities"))),
                                           r.get("use_when", "")]),
                    "_entry": None,   # full entry loaded lazily for matched results only
                })
        else:
            # Fallback: no derived index — read the authored catalog directly.
            for e in load_catalog().get("entries", []):
                if e.get("status") == "deleted":
                    continue
                cands.append({
                    "source": "reference-library",
                    "ref_id": e.get("ref_id"),
                    "archive_id": None,
                    "title": e.get("title"),
                    "role": e.get("role"),
                    "entities": e.get("entities", []),
                    "topics": e.get("topics", []),
                    "audience": e.get("audience", []),
                    "canonical": bool(e.get("canonical")),
                    "status": e.get("status"),
                    "layout_hint": e.get("layout_hint"),
                    "content_hash": e.get("content_hash"),
                    "_haystack": _fragment_text(e),
                    "_entry": e,
                })

    if "archive" in sources:
        for s in load_archive().get("slides", []):
            cands.append({
                "source": "archive",
                "ref_id": None,
                "archive_id": s.get("archive_id"),
                "title": s.get("title"),
                "role": s.get("role"),
                "entities": s.get("entities", []),
                "topics": [],
                "audience": [],
                "canonical": False,
                "status": "published",  # archived = shipped
                "layout_hint": None,
                "content_hash": s.get("content_hash"),
                "_haystack": " ".join([s.get("title", ""), s.get("text", "")]),
                "_entry": s,
            })

    results = []
    for c in cands:
        sc, reasons = _score(c, role, entity, topic, audience, text)
        if sc < min_score:
            continue
        out = {k: v for k, v in c.items() if not k.startswith("_")}
        out["score"] = round(sc, 2)
        out["match"] = _classify(c, reasons, bool(role))
        out["why"] = reasons
        # full entry (planFragment + facts) loaded only for MATCHED results, from entries/
        out["entry"] = c["_entry"] if c.get("_entry") is not None else get_full_entry(c.get("ref_id"))
        results.append(out)

    results.sort(key=lambda r: (-r["score"], r.get("ref_id") or r.get("archive_id") or ""))
    return results[:limit] if limit else results


def best_canonical(role, entity=None, audience=None, allow_role_only=False):
    """The canonical entry PLAN may AUTO-reuse for a role, or None. To avoid over-eager
    reuse, auto-reuse requires role + a MATCHED entity (or allow_role_only=True); a
    role-only canonical is NOT auto-pulled — PLAN should fall back to suggestions() and
    let the human confirm. For an explicit pick by id use get_by_ref()."""
    hits = query(role=role, entity=entity, audience=audience, sources=("catalog",))
    for h in hits:
        if h.get("canonical") and h.get("match") == "canonical":
            if allow_role_only or (entity and "entity" in (h.get("why") or [])):
                return h
            return None   # canonical exists but confidence too low -> suggest, don't auto-pull
    return None


def get_by_ref(ref_id):
    """Explicit canonical-key selection (a deliberate pick by id): full entry as a reuse hit, or None."""
    e = get_full_entry(ref_id)
    if not e:
        return None
    return {"ref_id": ref_id, "source": "reference-library", "canonical": bool(e.get("canonical")),
            "content_hash": e.get("content_hash"), "match": "explicit", "entry": e}


def suggestions(role=None, entity=None, topic=None, audience=None, text=None, limit=5):
    """Near matches PLAN should SUGGEST for confirmation (non-canonical / fuzzy)."""
    hits = query(role=role, entity=entity, topic=topic, audience=audience, text=text)
    return [h for h in hits if h["match"] != "canonical"][:limit]


# --- provenance stamping ------------------------------------------------------
def _provenance(cand_or_hit, deck_title, reuse, plan_revision, adapted_note=None):
    ref_id = cand_or_hit.get("ref_id")
    archive_id = cand_or_hit.get("archive_id")
    return {
        "ref_id": ref_id,
        "archive_id": archive_id,
        "source": cand_or_hit.get("source", "reference-library"),
        "reuse": reuse,
        "canonical": bool(cand_or_hit.get("canonical")),
        "content_hash": cand_or_hit.get("content_hash"),
        "deck_title": deck_title,
        "reused_at_revision": plan_revision,
        "adapted_note": adapted_note,
    }


def record_reuse(hit, deck_title, reuse="verbatim", plan_revision=0, adapted_note=None, out_dir=None):
    """Append a reuse EVENT to the DECK-LOCAL log (`<out_dir>/library-events.jsonl`) — never
    mutate the library at runtime. Library data is read-only in Cowork / packaged skills;
    the curator later reflects these events into the library's `used_in[]` via a PR (GATE.md).
    Returns the stamp. If out_dir is None, returns the stamp without writing (caller may log later).
    """
    if reuse not in ("verbatim", "adapted", "authored"):
        raise ValueError("reuse must be verbatim|adapted|authored")
    stamp = _provenance(hit, deck_title, reuse, plan_revision, adapted_note)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "library-events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(stamp, ensure_ascii=False) + "\n")
    return stamp


def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description="Search the reference-library + deck archive (canonical first).")
    ap.add_argument("--role")
    ap.add_argument("--entity")
    ap.add_argument("--topic")
    ap.add_argument("--audience", choices=["internal", "client"])
    ap.add_argument("--text")
    ap.add_argument("--source", choices=["catalog", "archive", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--full", action="store_true", help="include the full entry/planFragment in output")
    args = ap.parse_args()

    if not any([args.role, args.entity, args.topic, args.audience, args.text]):
        ap.error("give at least one of --role/--entity/--topic/--audience/--text")

    srcs = ("catalog", "archive") if args.source == "both" else (args.source,)
    hits = query(role=args.role, entity=args.entity, topic=args.topic,
                 audience=args.audience, text=args.text, sources=srcs, limit=args.limit)

    if not args.full:
        for h in hits:
            h.pop("entry", None)
    print(json.dumps(hits, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
