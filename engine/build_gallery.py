"""
Build the RENDERED TEMPLATE LIBRARY — a self-contained, interactive browser of every
v9 template rendered through the deck engine.

One command regenerates it end to end:
    python engine/build_gallery.py [--skill-path .]

It (1) generates a preview plan with one slide per catalog template (filled with sample
content so every slot shows), (2) renders + builds it (light fidelity, --no-library so the
library never embeds itself), and (3) assembles the gallery to:
    layouts/library-v9/rendered-gallery.html

The output is fully self-contained (base.css, tokens, fonts, icons, and all 104 rendered
stages baked in) and carries all features — light/dark, click-to-zoom, EDIT MODE with
per-template + mass "Copy to Claude" change requests, soft-delete with restore, and
localStorage persistence keyed by template id (survives reloads and regeneration). Send the
single HTML file to anyone and every template + feature travels with it.

build.py embeds this file into each deck's review.html behind the Template Library button.
"""
import os, re, json, argparse, subprocess, sys, uuid, html as _h

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DEFAULT = os.path.dirname(HERE)

ICONS = ["building", "users", "dollar-sign", "clock", "shield-check", "bar-chart", "file-text", "wrench"]
FAM_ORDER = [("CV", "Cover & framing"), ("NM", "Narrative & marketing"), ("PD", "Product & demo"),
             ("CC", "Consulting core"), ("AN", "Analytical & charts"), ("PO", "Process & operating"),
             ("WT", "Workshop & training"), ("UT", "Utility")]


def esc(x):
    return _h.escape(x or "")


def build_preview_plan(cat):
    ids = [t["id"] for t in cat["layouts"]]
    U = lambda: str(uuid.uuid4())
    b = lambda t, text: {"block_uuid": U(), "type": t, "text": text}

    def blocks():
        # plain numbers only (no $ % x +) so the fidelity gate stays green with no approved_facts
        return [
            b("label", "SECTION LABEL"),
            # product-name labels so suite / product-family templates render real logos
            b("label", "smrtGC"), b("label", "smrtSUB"), b("label", "smrtAE"), b("label", "smrt-E"),
            b("headline", "A Clear Headline For This Layout"),
            b("subhead", "A supporting subhead line that adds context."),
            b("body", "One tight paragraph that explains the core idea in plain, on-site language."),
            b("body", "The main risk to watch, stated short and honest."),
            b("body", "Payback logic: why the return lands inside the first year."),
            b("card_title", "First Point"), b("card_body", "Short supporting explanation for the first point."),
            b("card_title", "Second Point"), b("card_body", "Short supporting explanation for the second point."),
            b("card_title", "Third Point"), b("card_body", "Short supporting explanation for the third point."),
            b("card_title", "Fourth Point"), b("card_body", "Short supporting explanation for the fourth point."),
            b("stat", "65"), b("stat_label", "first proof metric"),
            b("stat", "240"), b("stat_label", "second proof metric"),
            b("stat", "18"), b("stat_label", "third proof metric"),
            b("kpi", "3"), b("kpi_label", "headline number"),
            b("list_item", "First list item worth stating plainly."),
            b("list_item", "Second list item worth stating plainly."),
            b("list_item", "Third list item worth stating plainly."),
            b("list_item", "Fourth list item worth stating plainly."),
            b("quote", "We finally work off one source of truth."),
            b("caption", "Site Superintendent, Denver"),
            b("cta", "See how it works"),
        ]

    slides = []
    for i, tid in enumerate(ids, 1):
        slides.append({
            "slide_uuid": U(), "display_index": i, "topic": tid,
            "layout": {"family": tid, "shape_tags": []},
            "group": "g-" + tid, "continues": False,
            "content_blocks": blocks(),
            "image_intent": {"tag": "preview-" + tid, "mood": "jobsite", "query": "construction"},
            "icon_intent": [{"name": ICONS[j % len(ICONS)], "represents": "preview icon"} for j in range(4)],
        })
    return {
        "schema_version": "5.0.0", "plan_revision": 1, "stage": 1,
        "deck": {"title": "TEMPLATE LIBRARY PREVIEW", "subtitle": "every v9 layout",
                 "audience": "internal", "theme": "dark"},
        "approved_facts": [], "slides": slides,
    }


GAL_CSS = """
/* override the embedded deck CSS that locks scrolling (body{overflow:hidden}) */
html{height:auto!important;overflow:visible!important}
body{height:auto!important;min-height:100%!important;overflow-y:auto!important;overflow-x:hidden!important;
  display:block!important;flex:none!important;padding:0!important}
:root{color-scheme:dark;}
.gbar{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:14px;padding:14px 28px;
  background:var(--sb-deck-bg);border-bottom:1px solid var(--sb-border-subtle);flex-wrap:wrap}
.gbar h1{font-size:19px;margin:0;color:var(--sb-title);font-weight:900;letter-spacing:-0.01em}
.gbar .sub{color:var(--sb-body-on-dark);font-size:13px;font-weight:700}
.gbar .sub b{color:var(--sb-sky)}
.gbar .sp{flex:1}
.gbar button{font-family:inherit;font-weight:800;font-size:13px;border:1px solid var(--sb-border-subtle);
  background:transparent;color:var(--sb-title);padding:9px 15px;border-radius:6px;cursor:pointer;white-space:nowrap}
.gbar button:hover{border-color:var(--sb-sky)}
.gbar button.on{background:var(--sb-sky);border-color:var(--sb-sky);color:#04223d}
#copybtn{background:var(--sb-sky);border-color:var(--sb-sky);color:#04223d}
.savenote{font-size:11px;color:var(--sb-body-on-dark);font-weight:700}
#massbar{display:none;padding:14px 28px;background:var(--sb-panel);border-bottom:1px solid var(--sb-border-subtle)}
body.edit #massbar{display:block}
#massbar label{display:block;font-size:12px;font-weight:900;letter-spacing:0.12em;text-transform:uppercase;color:var(--sb-sky);margin-bottom:7px}
#massbar textarea{width:100%;min-height:56px;box-sizing:border-box;background:var(--sb-deck-bg);color:var(--sb-title);
  border:1px solid var(--sb-border-subtle);border-radius:6px;padding:10px 12px;font-family:inherit;font-size:14px;resize:vertical}
.wrap{padding:10px 28px 80px}
.famhead{color:var(--sb-title);font-size:15px;font-weight:900;letter-spacing:0.14em;text-transform:uppercase;
  margin:34px 0 14px;display:flex;align-items:center;gap:10px}
.famhead .famn{background:var(--sb-sky);color:#04223d;border-radius:999px;font-size:12px;padding:2px 9px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,435px);gap:26px;justify-content:start}
.card{margin:0;width:435px}
.card.is-deleted{display:none}
body.show-deleted .card.is-deleted{display:block;opacity:0.5}
.frame{width:435px;height:245px;overflow:hidden;border:1px solid var(--sb-border-subtle);
  border-radius:8px;position:relative;background:var(--sb-deck-bg);cursor:zoom-in}
.frame .stage{position:absolute;top:0;left:0;transform:scale(0.3398)!important;transform-origin:top left!important}
.delbtn{position:absolute;top:8px;right:8px;z-index:20;width:28px;height:28px;border-radius:6px;border:none;
  background:rgba(199,80,39,0.92);color:#fff;font-size:14px;font-weight:900;cursor:pointer;display:none;line-height:1}
.frame:hover .delbtn{display:block}
.restorebtn{position:absolute;top:8px;right:8px;z-index:20;border:none;background:var(--sb-sky);color:#04223d;
  font-weight:800;font-size:12px;padding:6px 10px;border-radius:6px;cursor:pointer;display:none}
.card.is-deleted .delbtn{display:none!important}
body.show-deleted .card.is-deleted .restorebtn{display:block}
figcaption{padding:10px 4px 0;display:flex;flex-wrap:wrap;align-items:baseline;gap:8px}
.cid{font-weight:900;color:var(--sb-sky);font-size:14px}
.ctitle{font-weight:800;color:var(--sb-title);font-size:14px}
.crend{font-family:monospace;font-size:11px;color:var(--sb-body-on-dark);background:var(--sb-panel);padding:1px 6px;border-radius:4px}
.cjob{flex-basis:100%;color:var(--sb-body-on-dark);font-size:12px;line-height:1.4;margin-top:2px}
.notebox{display:none;width:435px;box-sizing:border-box;margin-top:8px;min-height:44px;background:var(--sb-panel);
  color:var(--sb-title);border:1px solid var(--sb-border-subtle);border-radius:6px;padding:8px 10px;
  font-family:inherit;font-size:13px;resize:vertical}
body.edit .notebox{display:block}
.notebox.has{border-color:var(--sb-sky)}
/* force final (revealed) state — opacity only. NEVER force transform:none here: many
   elements use inline transform:translate(-50%,-50%) for POSITIONING; the .visible class
   (added on load by the script) supplies the correct final transform and inline
   positioning transforms win over it, exactly as in the real deck. */
.reveal,.reveal-left,.reveal-right,.reveal-scale,.reveal-hero{opacity:1!important}
#modal,#copymodal{position:fixed;inset:0;z-index:200;background:rgba(6,12,26,0.85);display:none;align-items:center;justify-content:center}
#modal.open,#copymodal.open{display:flex}
#modal .mframe{width:1088px;max-width:94vw;height:612px;overflow:hidden;border-radius:10px;
  border:1px solid var(--sb-border-subtle);position:relative;background:var(--sb-deck-bg)}
#modal .mframe .stage{position:absolute;top:0;left:0;transform:scale(0.85)!important;transform-origin:top left!important}
.copybox{width:760px;max-width:92vw;background:var(--sb-deck-bg);border:1px solid var(--sb-border-subtle);
  border-radius:10px;padding:22px}
.copybox h3{margin:0 0 12px;color:var(--sb-title);font-size:16px}
.copybox textarea{width:100%;height:340px;box-sizing:border-box;background:var(--sb-panel);color:var(--sb-title);
  border:1px solid var(--sb-border-subtle);border-radius:6px;padding:12px;font-family:monospace;font-size:12px;resize:vertical}
.copybox .row{display:flex;gap:10px;margin-top:12px}
.copybox button{font-family:inherit;font-weight:800;font-size:13px;border:1px solid var(--sb-border-subtle);
  background:transparent;color:var(--sb-title);padding:9px 16px;border-radius:6px;cursor:pointer}
.copybox #docopy{background:var(--sb-sky);border-color:var(--sb-sky);color:#04223d}
"""

SCRIPT = r"""
(function(){
 var KEY='sb-tpl-lib-v1';
 var store={deleted:[],notes:{},mass:''};
 try{ var s=JSON.parse(localStorage.getItem(KEY)); if(s){store.deleted=s.deleted||[];store.notes=s.notes||{};store.mass=s.mass||'';} }catch(e){}
 // Match the deck's final render state without clobbering positioning transforms.
 document.querySelectorAll('.reveal,.reveal-left,.reveal-right,.reveal-scale,.reveal-hero').forEach(function(e){e.classList.add('visible');});
 var canSave=true; try{localStorage.setItem('__t','1');localStorage.removeItem('__t');}catch(e){canSave=false;}
 function save(){ if(!canSave)return; try{localStorage.setItem(KEY,JSON.stringify(store));}catch(e){} }
 function updateCount(){
   var vis=document.querySelectorAll('.card:not(.is-deleted)').length;
   var c=document.getElementById('count'); if(c)c.textContent=vis;
   document.querySelectorAll('.famhead').forEach(function(h){
     var fam=h.getAttribute('data-fam');
     h.querySelector('.famn').textContent=document.querySelectorAll('.card[data-id^="'+fam+'-"]:not(.is-deleted)').length;
   });
   var sn=document.getElementById('savenote'); if(sn) sn.textContent = canSave ? 'saved' : 'NOT saved (localStorage blocked)';
 }
 document.querySelectorAll('.card').forEach(function(card){
   var id=card.getAttribute('data-id');
   if(store.deleted.indexOf(id)>=0) card.classList.add('is-deleted');
   var nb=card.querySelector('.notebox');
   if(store.notes[id]){ nb.value=store.notes[id]; nb.classList.add('has'); }
 });
 var massEl=document.getElementById('mass'); if(massEl) massEl.value=store.mass;
 updateCount();
 document.querySelectorAll('.notebox').forEach(function(nb){
   nb.addEventListener('input',function(){
     var id=nb.getAttribute('data-id'), v=nb.value.trim();
     if(v){store.notes[id]=v;nb.classList.add('has');}else{delete store.notes[id];nb.classList.remove('has');}
     save();
   });
 });
 if(massEl) massEl.addEventListener('input',function(){store.mass=massEl.value;save();});
 document.querySelectorAll('.delbtn').forEach(function(b){b.addEventListener('click',function(e){e.stopPropagation();
   var card=b.closest('.card'),id=card.getAttribute('data-id');
   if(store.deleted.indexOf(id)<0)store.deleted.push(id); card.classList.add('is-deleted'); save(); updateCount();});});
 document.querySelectorAll('.restorebtn').forEach(function(b){b.addEventListener('click',function(e){e.stopPropagation();
   var card=b.closest('.card'),id=card.getAttribute('data-id');
   store.deleted=store.deleted.filter(function(x){return x!==id;}); card.classList.remove('is-deleted'); save(); updateCount();});});
 var modal=document.getElementById('modal');
 document.querySelectorAll('.frame').forEach(function(f){f.addEventListener('click',function(e){
   if(e.target.classList.contains('delbtn')||e.target.classList.contains('restorebtn'))return;
   var box=document.createElement('div'); box.className='mframe';
   box.appendChild(f.querySelector('.stage').cloneNode(true));
   modal.innerHTML=''; modal.appendChild(box); modal.classList.add('open');});});
 modal.addEventListener('click',function(e){ if(e.target===modal) modal.classList.remove('open'); });
 document.getElementById('editbtn').addEventListener('click',function(){document.body.classList.toggle('edit');this.classList.toggle('on');});
 document.getElementById('showdel').addEventListener('click',function(){document.body.classList.toggle('show-deleted');this.classList.toggle('on');});
 document.getElementById('themebtn').addEventListener('click',function(){
   var r=document.documentElement; r.setAttribute('data-theme', r.getAttribute('data-theme')==='light'?'dark':'light');});
 function payload(){
   var L=['SmartBuild Rendered Template Library - change requests',''];
   var mass=(store.mass||'').trim();
   L.push('## MASS CHANGE (apply to ALL templates):'); L.push(mass?mass:'(none)'); L.push('');
   var ids=Object.keys(store.notes).filter(function(id){return (store.notes[id]||'').trim();}).sort();
   L.push('## PER-TEMPLATE CHANGES ('+ids.length+'):'); if(!ids.length)L.push('(none)');
   ids.forEach(function(id){var c=document.querySelector('.card[data-id="'+id+'"]');
     L.push('- '+id+' ('+(c?c.getAttribute('data-rend'):'')+' | '+(c?c.getAttribute('data-title'):'')+'): '+store.notes[id].trim());});
   L.push('');
   L.push('## DELETE THESE ('+store.deleted.length+') - remove renderer + catalog entry:'); if(!store.deleted.length)L.push('(none)');
   store.deleted.slice().sort().forEach(function(id){var c=document.querySelector('.card[data-id="'+id+'"]');
     L.push('- '+id+' ('+(c?c.getAttribute('data-rend'):'')+')');});
   return L.join('\n');
 }
 var cm=document.getElementById('copymodal'), ct=document.getElementById('copytext');
 document.getElementById('copybtn').addEventListener('click',function(){ct.value=payload();cm.classList.add('open');ct.focus();ct.select();try{navigator.clipboard.writeText(ct.value);}catch(e){}});
 document.getElementById('docopy').addEventListener('click',function(){ct.focus();ct.select();var ok=false;try{ok=document.execCommand('copy');}catch(e){}try{navigator.clipboard.writeText(ct.value);ok=true;}catch(e){}this.textContent=ok?'Copied!':'Select + Cmd/Ctrl+C';var b=this;setTimeout(function(){b.textContent='Copy';},1500);});
 document.getElementById('closecopy').addEventListener('click',function(){cm.classList.remove('open');});
 cm.addEventListener('click',function(e){if(e.target===cm)cm.classList.remove('open');});
 document.addEventListener('keydown',function(e){if(e.key==='Escape'){modal.classList.remove('open');cm.classList.remove('open');}});
})();
"""


def assemble_gallery(review_html, cat):
    style = re.search(r'<style\b[^>]*>.*?</style>', review_html, re.S).group(0)
    cspm = re.search(r'<meta http-equiv="Content-Security-Policy"[^>]*>', review_html)
    csp = cspm.group(0) if cspm else ""
    meta = {l["id"]: l for l in cat["layouts"]}
    sections = {}
    for m in re.finditer(r'<section class="slide"[^>]*data-topic="([^"]+)"[^>]*>(.*?)</section>', review_html, re.S):
        sections[m.group(1)] = m.group(2)
    cards_by_fam = {}
    for tid, inner in sections.items():
        if tid not in meta:
            continue
        t = meta[tid]
        title = esc(t.get("title") or t.get("name") or tid)
        job = esc((t.get("story_job") or "")[:150])
        rn = esc(t.get("renderer") or "")
        card = ('<figure class="card" data-id="%s" data-rend="%s" data-title="%s">'
                '<div class="frame" tabindex="0">'
                '<button class="delbtn" title="Delete template">&#10005;</button>'
                '<button class="restorebtn" title="Restore">&#8635; restore</button>'
                '%s</div>'
                '<figcaption><span class="cid">%s</span> <span class="ctitle">%s</span>'
                '<span class="crend">%s</span><span class="cjob">%s</span></figcaption>'
                '<textarea class="notebox" data-id="%s" placeholder="Change request for %s (%s)..."></textarea>'
                '</figure>') % (esc(tid), rn, title, inner, esc(tid), title, rn, job, esc(tid), esc(tid), rn)
        cards_by_fam.setdefault(tid.split("-")[0], []).append((tid, card))
    body = []
    for fam, label in FAM_ORDER:
        items = sorted(cards_by_fam.get(fam, []), key=lambda x: x[0])
        if not items:
            continue
        body.append('<h2 class="famhead" data-fam="%s">%s <span class="famn">%d</span></h2>' % (fam, label, len(items)))
        body.append('<div class="grid">' + "".join(c for _, c in items) + '</div>')
    total = sum(len(v) for v in cards_by_fam.values())
    return ("""<!doctype html><html data-theme="dark"><head>
<meta charset="UTF-8">%s
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SmartBuild - Rendered Template Library (all %d)</title>
%s
<style>%s</style>
</head><body>
<div class="gbar"><h1>Rendered Template Library</h1>
<span class="sub"><b id="count">%d</b> of %d v9 templates - rendered through the deck engine</span>
<span class="savenote" id="savenote"></span><span class="sp"></span>
<button id="editbtn">Edit mode</button><button id="showdel">Show deleted</button>
<button id="copybtn">Copy to Claude</button><button id="themebtn">Toggle light / dark</button></div>
<div id="massbar"><label>Mass change - applied to ALL templates</label>
<textarea id="mass" placeholder="e.g. increase headline size across the board; add more breathing room in card grids..."></textarea></div>
<div class="wrap">%s</div>
<div id="modal"></div>
<div id="copymodal"><div class="copybox"><h3>Change requests - paste this to Claude</h3>
<textarea id="copytext" readonly></textarea>
<div class="row"><button id="docopy">Copy</button><button id="closecopy">Close</button></div></div></div>
<script>%s</script>
</body></html>""") % (csp, total, style, GAL_CSS, total, total, "".join(body), SCRIPT), total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-path", default=SKILL_DEFAULT)
    args = ap.parse_args()
    sp = os.path.abspath(args.skill_path)
    cat = json.load(open(os.path.join(sp, "layouts", "library-v9", "catalog.json")))
    prev = os.path.join(sp, "layouts", "library-v9", "_preview")
    os.makedirs(prev, exist_ok=True)
    plan_p = os.path.join(prev, "plan.json")
    json.dump(build_preview_plan(cat), open(plan_p, "w"), indent=2)
    slides_p = os.path.join(prev, "slides.html")
    out_d = os.path.join(prev, "out")
    py = sys.executable or "python3"
    subprocess.run([py, os.path.join(sp, "engine", "render_slides.py"),
                    "--skill-path", sp, "--plan", plan_p, "--out", slides_p], check=True)
    subprocess.run([py, os.path.join(sp, "engine", "build.py"),
                    "--skill-path", sp, "--plan", plan_p, "--slides", slides_p,
                    "--out", out_d, "--no-library"], check=True)
    review = open(os.path.join(out_d, "review.html")).read()
    html, total = assemble_gallery(review, cat)
    dest = os.path.join(sp, "layouts", "library-v9", "rendered-gallery.html")
    open(dest, "w").write(html)
    print("wrote %s | %d templates | %d bytes" % (dest, total, len(html)))


if __name__ == "__main__":
    main()
