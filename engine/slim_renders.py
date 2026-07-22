"""
slim_renders.py — NON-DESTRUCTIVE slimming of verbatim reference renders.

Reads layouts/reference-library/rendered/*.html (each an HTML fragment with base64
images embedded) and writes slimmed copies to layouts/reference-library/rendered.slim/,
NEVER touching the originals. Per embedded image:
  - downscale only if very wide (photos to <=1600px; alpha/text kept larger),
  - re-encode (WebP/JPEG for photos, optimized PNG for alpha/text),
  - promote the slimmed image ONLY if it is smaller AND passes an SSIM gate vs the
    original at display size (exec-approved slides must stay faithful); else keep original.

    python engine/slim_renders.py --skill-path .
"""
import argparse, base64, io, os, re
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim

PHOTO_MAX_W = 1280      # slides render at exactly 1280px wide
ALPHA_MAX_W = 1400      # text/alpha art kept a touch larger to protect glyph edges
SSIM_MIN = 0.90         # high-fidelity gate; approved slides stay faithful at display size
DATA_RE = re.compile(r'data:image/([A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)')


def _has_alpha(im):
    return im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)


def _composite(im):
    """Flatten (possibly transparent) image over neutral gray so SSIM captures BOTH
    colour and alpha-edge fidelity — the perceptually meaningful comparison."""
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
    return Image.alpha_composite(bg, im).convert("RGB")


def _ssim(a_rgb, b_rgb):
    return float(ssim(np.asarray(a_rgb), np.asarray(b_rgb), channel_axis=2))


def slim_one_image(raw):
    """Return (new_bytes, mime) for one decoded image, or None to keep the original.
    Lossy WebP (keeps alpha) gated by SSIM; genuine text/line-art fails the gate and
    falls back to lossless. Never grows."""
    try:
        im = Image.open(io.BytesIO(raw)); im.load()
    except Exception:
        return None
    w, h = im.size
    alpha = _has_alpha(im)
    max_w = ALPHA_MAX_W if alpha else PHOTO_MAX_W
    scale = min(1.0, max_w / float(w)) if w else 1.0
    ref = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS) if scale < 1 else im
    src = ref.convert("RGBA") if alpha else ref.convert("RGB")
    ref_cmp = _composite(ref) if alpha else ref.convert("RGB")

    best = None
    for q in (75, 82, 90):                       # lossy WebP preserves alpha
        buf = io.BytesIO(); src.save(buf, "WEBP", quality=q, method=6)
        cand = Image.open(io.BytesIO(buf.getvalue())); cand.load()
        cand_cmp = _composite(cand) if alpha else cand.convert("RGB")
        if ref_cmp.size == cand_cmp.size and _ssim(ref_cmp, cand_cmp) >= SSIM_MIN:
            best = (buf.getvalue(), "webp"); break
    if not best:                                 # lossless fallback (text/line-art)
        buf = io.BytesIO()
        if alpha:
            src.save(buf, "PNG", optimize=True)
        else:
            src.save(buf, "WEBP", lossless=True, method=6)
        best = (buf.getvalue(), "png" if alpha else "webp")

    new_bytes, fmt = best
    if len(new_bytes) >= len(raw):
        return None
    return new_bytes, "image/webp" if fmt == "webp" else "image/png"


def slim_html(html):
    """Replace each embedded image with a slimmed one where it helps."""
    saved = [0, 0]  # before, after (image bytes only)
    def repl(m):
        mime0, b64 = m.group(1), m.group(2)
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return m.group(0)
        saved[0] += len(raw)
        out = slim_one_image(raw)
        if not out:
            saved[1] += len(raw); return m.group(0)
        new_bytes, mime = out
        saved[1] += len(new_bytes)
        return "data:%s;base64,%s" % (mime, base64.b64encode(new_bytes).decode("ascii"))
    new_html = DATA_RE.sub(repl, html)
    return new_html, saved[0], saved[1]


def run(skill_path):
    refdir = os.path.join(skill_path, "layouts", "reference-library")
    src = os.path.join(refdir, "rendered")
    dst = os.path.join(refdir, "rendered.slim")
    os.makedirs(dst, exist_ok=True)
    tot_before = tot_after = 0
    for name in sorted(os.listdir(src)):
        if not name.endswith(".html"):
            continue
        html = open(os.path.join(src, name), encoding="utf-8").read()
        slim, b, a = slim_html(html)
        open(os.path.join(dst, name), "w", encoding="utf-8").write(slim)
        tot_before += b; tot_after += a
    return tot_before, tot_after, dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    b, a, dst = run(args.skill_path)
    print("slim renders written to %s" % dst)
    print("embedded image bytes: %.1f MB -> %.1f MB (%.0f%% smaller), SSIM>=%.2f gate"
          % (b / 1048576, a / 1048576, (100 * (1 - a / b)) if b else 0, SSIM_MIN))


if __name__ == "__main__":
    main()
