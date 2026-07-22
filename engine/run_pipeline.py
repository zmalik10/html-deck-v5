#!/usr/bin/env python3
"""run_pipeline.py — enforce the deterministic passes of the v5 deck pipeline in order.

The skill is a pipeline, not a menu. This driver runs the MECHANICAL passes and
HARD-STOPS on any gate failure, so BUILD/BRAND/SWEEP cannot be silently skipped or
have a FAIL waved off. The creative passes (PLAN, BUILD authoring, REFINE) still need
the model — this driver assumes an approved plan.json + authored slides.html already exist.

    python engine/run_pipeline.py --skill-path . --plan plan.json --slides slides.html --out out
                                  [--brand] [--presentation] [--no-open]

Sequence: BUILD (build.py) -> SWEEP validate (validate.py) -> SWEEP fidelity (fidelity.py)
          -> open review.html in Chrome (open_deck.py, best-effort).
Exit 0 only if BUILD succeeded AND both deterministic gates passed. Any gate FAIL -> exit 1.
"""
import argparse, os, subprocess, sys

def run(step, cmd):
    print("\n" + "=" * 64 + "\n[pipeline] %s\n  $ %s\n" % (step, " ".join(cmd)) + "=" * 64)
    rc = subprocess.call(cmd)
    return rc

def main():
    ap = argparse.ArgumentParser(description="Run the deterministic deck pipeline (BUILD -> SWEEP), hard-stopping on gate failure.")
    ap.add_argument("--skill-path", default=".")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--slides", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand", action="store_true", help="bake full-fidelity assets (BRAND pass)")
    ap.add_argument("--presentation", action="store_true", help="also emit the clean client presentation.html")
    ap.add_argument("--no-open", action="store_true", help="do not open review.html in Chrome at the end")
    ap.add_argument("--render", action="store_true", help="render slides.html from the plan's templates first (render_slides.py)")
    args = ap.parse_args()

    py = sys.executable or "python3"
    eng = os.path.join(args.skill_path, "engine")

    # PASS 2 — render slides.html from the templates (default authoring path).
    if args.render:
        if run("RENDER slides from templates", [py, os.path.join(eng, "render_slides.py"),
                "--skill-path", args.skill_path, "--plan", args.plan, "--out", args.slides]) != 0:
            print("\n[pipeline] STOP — template render failed.")
            sys.exit(1)

    # PASS 2/4 — BUILD (light) or BRAND (--brand)
    build = [py, os.path.join(eng, "build.py"), "--skill-path", args.skill_path,
             "--plan", args.plan, "--slides", args.slides, "--out", args.out]
    if args.brand:
        build.append("--brand")
    if args.presentation:
        build.append("--presentation")
    if run("BUILD" + (" (brand)" if args.brand else " (light)"), build) != 0:
        print("\n[pipeline] STOP — BUILD failed. Fix the plan/slides and re-run.")
        sys.exit(1)

    # PASS 5 — SWEEP: deterministic gates. Both must pass.
    gate_failed = False
    if run("SWEEP — validate.py (mechanical contract)",
           [py, os.path.join(eng, "validate.py"), "--skill-path", args.skill_path,
            "--plan", args.plan, "--out", args.out]) != 0:
        gate_failed = True
    if run("SWEEP — fidelity.py (content-fidelity)",
           [py, os.path.join(eng, "fidelity.py"), "--plan", args.plan, "--out", args.out]) != 0:
        gate_failed = True

    if gate_failed:
        print("\n[pipeline] STOP — SWEEP found deterministic FAILs above. Fix them and re-run "
              "(the loop allows up to 3 iterations; escalate anything that won't converge). "
              "Do NOT hand over or EXPORT this deck.")
        sys.exit(1)

    # Standing rule: every build ends by reopening the deck for review (best-effort).
    if not args.no_open:
        run("OPEN review.html in Chrome",
            [py, os.path.join(eng, "open_deck.py"), "--out", args.out])

    print("\n[pipeline] OK — BUILD succeeded and SWEEP is green. "
          "Human review is the next required step (approve the swept deck) before EXPORT.")
    sys.exit(0)

if __name__ == "__main__":
    main()
