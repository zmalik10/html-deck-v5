"""
SmartBuild Deck v5 — fidelity.py  (SWEEP: content-fidelity hard gate)

Protects against invented facts. The human-approved claims/stats live in
plan.approved_facts. This gate extracts stat-like claims actually rendered
in the deck and fails on any that are NOT in the approved set — so the
pipeline can polish wording but cannot introduce or alter facts on its own.

"Stat-like" = currency ($2B, $4.5M), percentages (93%), and multipliers
(2x, 5X). Plain prose numbers ("3 ideas", years) are ignored to avoid noise;
tune STAT_RE as needed.

Usage:
    python fidelity.py --plan plan.json --out <build-dir>
Exit 0 = no unapproved facts; 1 = unapproved fact(s) found.
"""
import argparse, json, os, re, sys

STAT_RE = re.compile(
    r'\$\s?\d[\d,\.]*\s?[BMK]?\+?'      # currency: $2B+, $4.5M
    r'|\b\d[\d,\.]*\s?%'                # percent: 93%
    r'|\b\d[\d,\.]*\s?[xX]\b'          # multiplier: 2x, 5X
    r'|\b\d[\d,\.]*\s?[BMK]?\+(?!\d)'   # count with plus: 500+, 2B+ (not a +N sign across blocks)
)

def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def visible_text(html):
    i = html.find('<div class="deck">')
    k = html.find('<div id="nav-dots">')
    region = html[i:k] if (i >= 0 and k > i) else html
    region = re.sub(r'<[^>]+>', ' ', region)          # strip tags
    return re.sub(r'\s+', ' ', region)

def norm(tok):
    return re.sub(r'\s+', '', tok.upper()).rstrip('.')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    plan = load_json(args.plan)

    approved = set()
    for f in plan.get("approved_facts", []):
        if f.get("value"):
            approved.add(norm(f["value"]))
        for m in STAT_RE.findall(f.get("text", "")):
            approved.add(norm(m))

    # Prefer presentation.html when it exists (EXPORT); otherwise scan review.html —
    # rendered stats are identical, and the working loop is review-only.
    _pres = os.path.join(args.out, "presentation.html")
    html = read(_pres if os.path.exists(_pres) else os.path.join(args.out, "review.html"))
    # Verbatim-locked reference slides are exec-approved and reused word-for-word; their
    # stats are not subject to the invented-fact gate. Drop those sections before scanning.
    html = re.sub(r'<section[^>]*\bdata-reference=[^>]*>.*?</section>', ' ', html, flags=re.S | re.I)
    text = visible_text(html)
    found = [m for m in STAT_RE.findall(text)]
    unapproved = sorted({m for m in found if norm(m) not in approved})

    print("CONTENT-FIDELITY: %d approved facts, %d stat-like claims rendered." % (len(approved), len(set(map(norm, found)))))
    if unapproved:
        print("  FAIL — unapproved / altered claims rendered (not in approved_facts):")
        for u in unapproved:
            print("    • " + u)
        print("  Fix: add to plan.approved_facts (with source) or correct the slide. Facts cannot be invented mid-pipeline.")
        sys.exit(1)
    print("  OK — every rendered stat maps to an approved fact.")
    sys.exit(0)

if __name__ == "__main__":
    main()
