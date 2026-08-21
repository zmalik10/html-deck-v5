/* ============================================================
   SmartBuild Deck v5 — deck.js
   No inline handlers anywhere (CSP-friendly). All behavior here.
   build.py injects, before this file:
     window.__DECK__      = { mode: 'review'|'presentation', title, plan_revision }
     window.__ANNOTATIONS__ = [ {pin_id, block_uuid, note, description, content_hash, x, y, slide_uuid} ]
     window.__SOURCES__   = [ {kind, source, author, license, link},            // resolved assets
                              {kind:'reference', source, deck, date, link} ]   // reference-library reuse
   In presentation mode the review chrome is physically absent; this
   script feature-detects each element before wiring it.
============================================================ */
(function () {
  'use strict';
  var MODE = (window.__DECK__ && window.__DECK__.mode) || 'presentation';
  document.body.classList.add('mode-' + MODE);
  var PLAN_REV = (window.__DECK__ && window.__DECK__.plan_revision) || 0;
  var $ = function (id) { return document.getElementById(id); };

  /* ============================================================
     TOOLS ARE LOCALHOST-ONLY  (served vs file:// contract)
     The deck ships as ONE artifact used two ways:
       • served on localhost (open_deck.py --edit)  → the full editor; every tool live.
       • opened as a plain file://                  → a clean PRESENTATION deck.
     On the file view ALL editing tools are physically removed. Exactly two controls
     survive: Fullscreen (#fs-btn) and the button that opens the editable localhost
     version (#text-toggle, repurposed to "↗" further down). Nav dots stay as a
     presentation navigation aid — they are not a tool.
     The signal is the URL protocol: http/https = served (localhost editor),
     file = presentation. This is the single source of truth for the whole deck
     (CAN_SAVE below is aliased to it), so tools can never leak onto the file view.
  ============================================================ */
  var SERVED = /^https?:$/.test(location.protocol);
  document.body.classList.add(SERVED ? 'deck-served' : 'deck-file');
  if (!SERVED) {
    ['edit-toggle', 'board-toggle', 'tpl-lib-btn', 'theme-btn', 'save-btn', 'sources-btn',
     'save-menu', 'sources-panel', 'review-panel', 'pin-popup', 'slide-board']
      .forEach(function (id) { var el = $(id); if (el && el.parentNode) el.parentNode.removeChild(el); });
    // The spare/placeholder slide is a Slide-Board affordance — it parks in the board's
    // "Not used" tray so you can drag it into the deck. The board exists ONLY on the
    // localhost editor, so on the file view the spare has no home and is normally kept out
    // of the flow by the board that never runs here. Drop it so it never shows when
    // presenting. (On localhost it's left alone — the board keeps it parked in "Not used".)
    Array.prototype.slice.call(document.querySelectorAll('.slide[data-placeholder]'))
      .forEach(function (el) { if (el.parentNode) el.parentNode.removeChild(el); });
  }

  // Computed AFTER the file-view strip so nav dots, keyboard nav, and the intersection
  // observers only ever see the slides that actually render.
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));

  /* ---- content hash: djb2 over normalized text (mirrors engine) ---- */
  function contentHash(s) {
    s = (s || '').replace(/\s+/g, ' ').trim();
    var h = 5381;
    for (var i = 0; i < s.length; i++) { h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff; }
    return (h >>> 0).toString(16);
  }

  /* ============================================================
     FIXED-CANVAS SCALING — keep 1280x720 stage fit to viewport
  ============================================================ */
  function rescale() {
    // When the notes panel is open, reserve its width so the WHOLE slide fits in the
    // space beside it (the slide is also narrowed via body.notes-open .slide in CSS).
    var notesW = document.body.classList.contains('notes-open')
      ? (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--notes-w')) || 0) : 0;
    var availW = Math.max(320, window.innerWidth - notesW);
    var s = Math.min(availW / 1280, window.innerHeight / 720);
    document.documentElement.style.setProperty('--deck-scale', s);
  }
  window.addEventListener('resize', rescale);
  rescale();

  /* ---- stage context lives in the NOTES chrome only (cycle-10 pin-1) ----
     No on-slide chip/badge of any kind: reviewers rejected every on-canvas stamp
     (orange badge, then the sNN/REFINE chip). Slide + stage context is appended to
     the review-panel header instead, visible only when the notes drawer is open. */
  (function () {
    var d = window.__DECK__ || {};
    var stageTag = d.stage ? (' · ' + (d.stage_name || 'STAGE') + ' ' + d.stage + '/' + (d.stage_total || 5)) : '';
    var ph = document.querySelector('#review-panel h3');
    if (ph && stageTag) ph.textContent = ph.textContent + stageTag;
  })();

  /* ---- footer-logo auto contrast (R2-H4: DETERMINISTIC, direction-independent) ----
     The old path sampled document.elementsFromPoint at the mark's VIEWPORT position on every
     scroll intersection — scrolling backward, the sample landed mid-transition on the
     NEIGHBOURING slide's pixels, so the logo flipped colour by scroll direction. Fixed: read
     the slide's OWN background composition (the first opaque solid background-colour on the
     stage or its ancestors — never viewport pixels), compute ONCE per slide, cache it, and
     recompute only on a theme toggle. A full-bleed photo/gradient (no opaque solid) keeps the
     brand-colour mark. */
  function stageBgLuminance(stage) {
    var node = stage;
    while (node && node !== document.documentElement) {
      var m = getComputedStyle(node).backgroundColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/);
      if (m && (m[4] === undefined || parseFloat(m[4]) > 0.5)) {
        return (0.299 * (+m[1]) + 0.587 * (+m[2]) + 0.114 * (+m[3])) / 255;
      }
      node = node.parentElement;
    }
    return null;
  }
  function contrastForStage(stage, force) {
    if (!stage) return;
    var el = stage.querySelector('.sb-footer-logo'); if (!el) return;
    if (!force && stage.dataset._contrastDone === '1') return;   // once per slide -> no scroll flip
    stage.dataset._contrastDone = '1';
    el.classList.remove('mono-white');
    // A renderer-declared full-bleed dark stage (photo + ink veil) has no opaque
    // background-color to sample, so the walk below would read the deck bg and keep the
    // full-colour mark on near-black. Trust the declaration. (fixed 2026-08-20)
    if (stage.dataset.bleed === 'dark') { el.classList.add('mono-white'); return; }
    var lum = stageBgLuminance(stage);
    if (lum === null)                       // photo/gradient → assume the deck theme's dominant tone
      lum = (document.documentElement.dataset.theme === 'light') ? 0.9 : 0.1;
    // Two real logos only: WHITE on dark backgrounds, FULL-COLOUR on light. No black logo.
    if (lum < 0.5) el.classList.add('mono-white');
  }
  /* recompute every slide's mark contrast (theme toggle changes every background) */
  function recomputeAllContrast() {
    document.querySelectorAll('.slide .stage').forEach(function (st) { contrastForStage(st, true); });
  }

  /* ============================================================
     NAV DOTS + REVEAL + ACTIVE TRACKING
  ============================================================ */
  var dotsEl = $('nav-dots');
  var currentSlide = slides[0];
  // Rebuildable so the Slide Board can regenerate dots after it reorders / removes
  // slides in the live deck (dots must track the CURRENT visible `slides` array).
  function buildNavDots() {
    if (!dotsEl) return;
    dotsEl.innerHTML = '';
    slides.forEach(function (sl, i) {
      var d = document.createElement('button');
      d.className = 'dot';
      d.textContent = (i + 1);                       // numbered so you know which to click
      d.title = sl.getAttribute('data-topic') || ('Slide ' + (i + 1));
      d.addEventListener('click', function () { sl.scrollIntoView({ behavior: 'smooth' }); });
      dotsEl.appendChild(d);
    });
  }
  buildNavDots();

  /* ---- Toolbar: collect the loose fixed .uibtn tools into ONE top-right rail so they
     never overlap each other or the nav dots, and expose each button's title as a
     data-tip so CSS shows an instant hover tooltip (title kept for accessibility). ---- */
  (function setupToolbar() {
    var btns = Array.prototype.slice.call(document.querySelectorAll('.uibtn'));
    if (!btns.length) return;
    // Fullscreen goes LAST so it sits furthest top-right (the row hugs the right corner).
    var fs = null;
    btns = btns.filter(function (b) { if (b.id === 'fs-btn') { fs = b; return false; } return true; });
    if (fs) btns.push(fs);
    var bar = document.getElementById('ui-toolbar');
    if (!bar) { bar = document.createElement('div'); bar.id = 'ui-toolbar'; document.body.appendChild(bar); }
    btns.forEach(function (b) {
      var t = b.getAttribute('title');
      if (t) b.setAttribute('data-tip', t);
      bar.appendChild(b);                      // moves the node (event listeners persist)
    });
  })();

  var activeIO = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      currentSlide = e.target;
      var idx = slides.indexOf(e.target);
      if (dotsEl) Array.prototype.forEach.call(dotsEl.children, function (d, i) { d.classList.toggle('active', i === idx); });
      contrastForStage(e.target.querySelector('.stage'));
    });
  }, { threshold: 0.5 });
  slides.forEach(function (sl) { activeIO.observe(sl); });
  // Compute every mark's contrast ONCE at load (H4: deterministic, not scroll-speed dependent).
  // stageBgLuminance reads computed backgrounds, not viewport pixels, so it is correct for
  // off-screen slides too — the value is then frozen (cached) and never flips on scroll.
  recomputeAllContrast();

  var revealIO = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale, .reveal-hero').forEach(function (el, i) {
          setTimeout(function () { el.classList.add('visible'); }, i * 120);
        });
      }
    });
  }, { threshold: 0.15 });
  slides.forEach(function (sl) { revealIO.observe(sl); });
  // Failsafe: content must NEVER be stuck hidden. Always reveal the first slide on load
  // (it's in view immediately), and if IntersectionObserver is unavailable, reveal all.
  var REVEAL_SEL = '.reveal, .reveal-left, .reveal-right, .reveal-scale, .reveal-hero';
  if (slides[0]) slides[0].querySelectorAll(REVEAL_SEL).forEach(function (el, i) { setTimeout(function () { el.classList.add('visible'); }, i * 120); });
  if (!('IntersectionObserver' in window)) document.querySelectorAll(REVEAL_SEL).forEach(function (el) { el.classList.add('visible'); });

  /* ============================================================
     KEYBOARD NAV
  ============================================================ */
  document.addEventListener('keydown', function (e) {
    if (['INPUT', 'TEXTAREA'].indexOf(e.target.tagName) >= 0 || e.target.isContentEditable) return;
    var idx = slides.indexOf(currentSlide);
    if (e.key === 'ArrowDown' || e.key === 'PageDown') { e.preventDefault(); (slides[Math.min(idx + 1, slides.length - 1)] || {}).scrollIntoView && slides[Math.min(idx + 1, slides.length - 1)].scrollIntoView({ behavior: 'smooth' }); }
    if (e.key === 'ArrowUp' || e.key === 'PageUp') { e.preventDefault(); (slides[Math.max(idx - 1, 0)] || {}).scrollIntoView && slides[Math.max(idx - 1, 0)].scrollIntoView({ behavior: 'smooth' }); }
    if (e.key === 'f' || e.key === 'F') toggleFullscreen();
    if (e.key === 'Escape') {
      document.querySelectorAll('.bloom-panel.open').forEach(function (p) { p.classList.remove('open'); });
      var sm = $('save-menu'); if (sm) sm.classList.remove('open');
    }
  });

  /* ============================================================
     BLOOM
  ============================================================ */
  document.querySelectorAll('[data-bloom]').forEach(function (t) {
    t.addEventListener('click', function (e) {
      if (document.body.classList.contains('edit-mode')) return;
      e.stopPropagation();
      var r = t.getBoundingClientRect();
      var panel = $(t.getAttribute('data-bloom'));
      if (!panel) return;
      panel.style.setProperty('--ox', ((r.left + r.width / 2) / window.innerWidth * 100).toFixed(1) + '%');
      panel.style.setProperty('--oy', ((r.top + r.height / 2) / window.innerHeight * 100).toFixed(1) + '%');
      panel.classList.add('open');
    });
  });
  document.querySelectorAll('[data-close]').forEach(function (b) {
    b.addEventListener('click', function (e) { e.stopPropagation(); var p = $(b.getAttribute('data-close')); if (p) p.classList.remove('open'); });
  });

  /* ============================================================
     THEME + FULLSCREEN
  ============================================================ */
  var themeBtn = $('theme-btn');
  if (themeBtn) themeBtn.addEventListener('click', function () {
    var el = document.documentElement;
    el.dataset.theme = (el.dataset.theme === 'light') ? 'dark' : 'light';
    recomputeAllContrast();                 // every slide's bg changed (H4: deterministic recompute)
  });
  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(function () {});
    else document.exitFullscreen().catch(function () {});
  }
  var fsBtn = $('fs-btn'); if (fsBtn) fsBtn.addEventListener('click', toggleFullscreen);

  /* ============================================================
     REVIEW MODE + SELF-DESCRIBING PINS  (review mode only)
  ============================================================ */
  var annotations = (window.__ANNOTATIONS__ || []).slice();
  var pinSeq = annotations.reduce(function (m, a) { return Math.max(m, parseInt((a.pin_id || '0').replace(/\D/g, ''), 10) || 0); }, 0);
  var pending = null;
  var editToggle = $('edit-toggle');
  var reviewPanel = $('review-panel');
  var pinPopup = $('pin-popup');
  var ppText = $('pp-text');
  var ppTarget = $('pp-target');
  var ppProv = $('pp-prov');

  function quadrant(x, y) {
    var v = y < 38 ? 'top' : (y > 62 ? 'bottom' : 'middle');
    var h = x < 38 ? 'left' : (x > 62 ? 'right' : 'center');
    return v + '-' + h;
  }
  function describe(block) {
    var type = block.getAttribute('data-block-type') || block.tagName.toLowerCase();
    var slide = block.closest('.slide');
    var topic = slide ? (slide.getAttribute('data-topic') || '') : '';
    var text;
    if (type === 'icon') {
      text = "icon '" + (block.getAttribute('data-icon-name') || '') + "'";
      var host = block.parentElement;
      var ctx = host && host.querySelector('[data-block-type="card_title"],[data-block-type="headline"],[data-block-type="card_body"]');
      if (ctx) text += ' in “' + (ctx.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40) + '”';
    } else {
      text = (block.textContent || '').replace(/\s+/g, ' ').trim();
      if (text.length > 80) text = text.slice(0, 77) + '...';
    }
    return { type: type, topic: topic, text: text };
  }

  /* ---- PROVENANCE (published-content awareness) ------------------------------
     A slide or block may carry a provenance stamp identifying it as content
     reused from a PUBLISHED master. Contract (an upstream pass emits it; REFINE
     only READS it and degrades to a no-op when absent):
        window.__PROVENANCE__ = { "<block_uuid|slide_uuid>": stamp }   // uuid-keyed, OR
        <el data-provenance='{...}'>                                    // element-local
     stamp = { source, refId, version, originalHash }
        source       — master deck / library the content came from
        refId        — its id in that master
        version      — the published version being edited against
        originalHash — contentHash() of the text at publish time
     Block-level stamp wins over slide-level. If the live text no longer hashes
     to originalHash the block has "diverged from master". -------------------- */
  function parseProv(el) {
    if (!el || !el.getAttribute) return null;
    var raw = el.getAttribute('data-provenance');
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
  }
  function readProvenance(block, slide) {
    var p = parseProv(block) || parseProv(slide);
    if (p) return p;
    var map = window.__PROVENANCE__;
    if (map && typeof map === 'object') {
      var bid = block && block.getAttribute && block.getAttribute('data-block');
      var sid = slide && slide.getAttribute && slide.getAttribute('data-slide');
      return (bid && map[bid]) || (sid && map[sid]) || null;
    }
    return null;
  }
  // Normalize a stamp + live block into what review chrome renders.
  function provInfo(prov, block) {
    if (!prov) return null;
    var oh = prov.originalHash || prov.original_hash || '';
    var diverged = false;
    if (oh && block) diverged = contentHash(block.textContent) !== String(oh);
    return {
      source: prov.source || '', refId: prov.refId || prov.ref_id || '',
      version: prov.version || '', originalHash: String(oh || ''), diverged: diverged
    };
  }
  function provLabel(p) {
    if (!p) return '';
    var parts = [];
    if (p.source) parts.push(p.source);
    if (p.refId) parts.push('#' + p.refId);
    if (p.version) parts.push(String(p.version));
    return parts.join(' · ');
  }
  // Resolve an annotation's live slide/block elements (works for hydrated pins too).
  function annEls(a) {
    return {
      slide: a.slide_uuid ? document.querySelector('.slide[data-slide="' + a.slide_uuid + '"]') : null,
      block: a.block_uuid ? document.querySelector('[data-block="' + a.block_uuid + '"]') : null
    };
  }
  function annProv(a) { var e = annEls(a); return provInfo(readProvenance(e.block, e.slide), e.block); }
  // Slide topic resolved from the DOM (hydrated pins don't carry slide_topic).
  function slideTopicOf(a) {
    var e = annEls(a);
    return (e.slide && e.slide.getAttribute('data-topic')) || a.slide_topic || '';
  }
  // Pin's anchored text changed since drop? (schema: content_hash mismatch => stale)
  function annStale(a) {
    if (!a.content_hash || !a.block_uuid) return false;
    var e = annEls(a); if (!e.block) return false;          // handled as "target removed"
    return contentHash(e.block.textContent) !== String(a.content_hash);
  }
  function annTargetRemoved(a) { return !!a.block_uuid && !annEls(a).block; }

  // slide DOM order helpers (payload + panel read top-to-bottom like the deck)
  function slideIndexOf(sid) {
    for (var i = 0; i < slides.length; i++) { if (slides[i].getAttribute('data-slide') === sid) return i; }
    return -1;
  }
  function orderedSlideIds(bySlide) {
    return Object.keys(bySlide).sort(function (a, b) {
      var ia = slideIndexOf(a), ib = slideIndexOf(b);
      if (ia < 0) ia = 1e9; if (ib < 0) ib = 1e9;
      return ia - ib;
    });
  }
  function byPosition(a, b) {                                // top-to-bottom on the slide, then pin #
    var ay = a.y == null ? 1e9 : a.y, by = b.y == null ? 1e9 : b.y;
    if (Math.abs(ay - by) > 4) return ay - by;
    var na = parseInt((a.pin_id || '').replace(/\D/g, ''), 10) || 0;
    var nb = parseInt((b.pin_id || '').replace(/\D/g, ''), 10) || 0;
    return na - nb;
  }

  function enterEdit() { document.body.classList.add('edit-mode'); if (editToggle) editToggle.classList.add('active'); if (reviewPanel) reviewPanel.classList.add('open'); }
  // Un-toggling the pen must also CLOSE the panel it opened (otherwise the sidebar was
  // stuck open with no way to dismiss it but a refresh).
  function exitEdit() { document.body.classList.remove('edit-mode'); if (editToggle) editToggle.classList.remove('active'); if (reviewPanel) reviewPanel.classList.remove('open'); if (pinPopup) pinPopup.classList.remove('visible'); pending = null; }
  if (editToggle) editToggle.addEventListener('click', function () { document.body.classList.contains('edit-mode') ? exitEdit() : enterEdit(); });

  // Mirror panel open-state onto <body>: `notes-open` (review panel → shrink the slide so it
  // shows beside the notes) and a general `panel-open` (ANY sidepanel open → the fixed
  // top-right toolbar and nav dots get out of the panel's way; see base.css).
  function syncPanelChrome() {
    document.body.classList.toggle('notes-open', !!(reviewPanel && reviewPanel.classList.contains('open')));
    document.body.classList.toggle('panel-open', !!document.querySelector('.sidepanel.open'));
    rescale();
  }
  var panelObs = new MutationObserver(syncPanelChrome);
  Array.prototype.forEach.call(document.querySelectorAll('.sidepanel'),
    function (p) { panelObs.observe(p, { attributes: true, attributeFilter: ['class'] }); });
  syncPanelChrome();

  {
    document.querySelectorAll('.stage').forEach(function (stage) {
      stage.addEventListener('click', function (e) {
        if (!document.body.classList.contains('edit-mode')) return;
        if (document.body.classList.contains('text-edit-mode')) return;   // typing text, not pinning
        if (e.target.closest('.bloom-panel, .bloom-trigger, .ann-pin, .sb-vtoggle, .sb-delbtn')) return;
        // resolve the element actually under the click (catches icons etc.), then its data-block
        var hit = document.elementFromPoint(e.clientX, e.clientY);
        var block = (hit && hit.closest('[data-block]')) || e.target.closest('[data-block]');
        var rect = stage.getBoundingClientRect();
        // position within the 1280x720 stage, de-scaling the transform
        var scale = rect.width / 1280;
        var x = ((e.clientX - rect.left) / scale) / 1280 * 100;
        var y = ((e.clientY - rect.top) / scale) / 720 * 100;
        var slide = stage.closest('.slide');
        var d = block ? describe(block) : { type: 'slide', topic: slide ? slide.getAttribute('data-topic') : '', text: '(no specific element)' };
        var coord = '@ ' + x.toFixed(0) + '%,' + y.toFixed(0) + '% (' + quadrant(x, y) + ')';
        var prov = provInfo(readProvenance(block, slide), block);
        pending = {
          block_uuid: block ? block.getAttribute('data-block') : null,
          slide_uuid: slide ? slide.getAttribute('data-slide') : null,
          slide_topic: slide ? (slide.getAttribute('data-topic') || '') : '',
          description: d.type + (d.text ? ' — "' + d.text + '"' : '') + '  ' + coord,
          content_hash: block ? contentHash(block.textContent) : '',
          x: +x.toFixed(2), y: +y.toFixed(2)
        };
        if (ppTarget) ppTarget.textContent = (block ? d.type : 'slide') + ' · ' + (d.topic || '');
        if (ppProv) {                                        // warn reviewer they're editing PUBLISHED content
          if (prov) {
            ppProv.innerHTML = '<span class="pp-prov-tag">Published</span>' + escapeHtml(provLabel(prov)) +
              (prov.diverged ? '<span class="pp-badge diverged">diverged from master</span>' : '');
            ppProv.style.display = 'block';
          } else { ppProv.style.display = 'none'; ppProv.textContent = ''; }
        }
        if (pinPopup) {
          pinPopup.style.left = Math.min(e.clientX + 12, window.innerWidth - 316) + 'px';
          pinPopup.style.top = Math.min(e.clientY - 20, window.innerHeight - 220) + 'px';
          pinPopup.classList.add('visible');
        }
        if (ppText) { ppText.value = ''; ppText.focus(); }
      });
    });
    var ppSave = $('pp-save'), ppCancel = $('pp-cancel');
    if (ppSave) ppSave.addEventListener('click', function () {
      var text = ppText ? ppText.value.trim() : '';
      if (!text || !pending) { if (pinPopup) pinPopup.classList.remove('visible'); pending = null; return; }
      pinSeq++;
      var note = Object.assign({ pin_id: 'pin-' + pinSeq, note: text, dropped_at_revision: PLAN_REV }, pending);
      annotations.push(note);
      dropPin(note);
      if (pinPopup) pinPopup.classList.remove('visible'); pending = null;
      renderReview();
    });
    if (ppCancel) ppCancel.addEventListener('click', function () { if (pinPopup) pinPopup.classList.remove('visible'); pending = null; });
  }

  function dropPin(note) {
    var slide = document.querySelector('.slide[data-slide="' + note.slide_uuid + '"]') || (note.block_uuid && document.querySelector('[data-block="' + note.block_uuid + '"]'));
    var stage = slide ? (slide.querySelector ? slide.querySelector('.stage') || slide.closest('.stage') : null) : null;
    if (!stage) return;
    var pin = document.createElement('div');
    pin.className = 'ann-pin'; pin.id = note.pin_id;
    pin.style.left = note.x + '%'; pin.style.top = note.y + '%';
    pin.innerHTML = '<span>' + note.pin_id.replace(/\D/g, '') + '</span>';
    // reflect published / diverged / stale state on the marker itself
    var info = annProv(note);
    var title = note.pin_id + (note.note ? ': ' + note.note : '');
    if (info) { pin.classList.add('published'); title += '\nPublished: ' + provLabel(info); if (info.diverged) { pin.classList.add('diverged'); title += '  (diverged from master)'; } }
    if (annStale(note)) { pin.classList.add('stale'); title += '\n(edited since pinned)'; }
    pin.title = title;
    stage.appendChild(pin);
  }

  // copy button lights up for pins OR any Slide Board decision (reorder/remove/variant)
  function boardHasChanges() { return !!(window.__BOARD_API__ && window.__BOARD_API__.hasChanges()); }
  function textEditsChanged() { return !!(window.__TEXTEDITS_API__ && window.__TEXTEDITS_API__.hasChanges()); }
  function copyEnabled() { return annotations.length > 0 || boardHasChanges() || textEditsChanged(); }
  function refreshCopyState() { var b = $('copy-notes'); if (b) b.disabled = !copyEnabled(); }

  function renderReview() {
    var list = $('review-list'); var copyBtn = $('copy-notes');
    if (!list) return;
    list.innerHTML = '';
    if (!annotations.length) { list.innerHTML = '<div class="rn-empty">No pins yet. Click the pen, then any element — or use the Slide Board (▤) to reorder, remove, or set light/dark per slide.</div>'; if (copyBtn) copyBtn.disabled = !copyEnabled(); return; }
    if (copyBtn) copyBtn.disabled = !copyEnabled();

    // group notes by slide, ordered top-to-bottom through the deck
    var bySlide = {};
    annotations.forEach(function (a) { (bySlide[a.slide_uuid] = bySlide[a.slide_uuid] || []).push(a); });
    orderedSlideIds(bySlide).forEach(function (sid) {
      var items = bySlide[sid].slice().sort(byPosition);
      var idx = slideIndexOf(sid);
      var grp = document.createElement('div'); grp.className = 'review-group';
      var head = document.createElement('div'); head.className = 'rg-head';
      head.innerHTML = '<span class="rg-num">' + (idx >= 0 ? 's' + (idx + 1) : '—') + '</span>' +
        '<span class="rg-topic">' + escapeHtml(slideTopicOf(items[0]) || 'Untitled slide') + '</span>' +
        '<span class="rg-count">' + items.length + '</span>';
      grp.appendChild(head);
      items.forEach(function (a) { grp.appendChild(noteRow(a)); });
      list.appendChild(grp);
    });
  }

  function noteRow(a) {
    var row = document.createElement('div'); row.className = 'review-note';
    var info = annProv(a);
    var badges = '';
    if (info) { row.classList.add('is-published'); badges += '<span class="rn-prov"><span class="rn-prov-tag">Published</span>' + escapeHtml(provLabel(info)) + '</span>'; }
    if (info && info.diverged) badges += '<span class="rn-badge diverged">diverged from master</span>';
    if (annTargetRemoved(a)) badges += '<span class="rn-badge removed">target removed</span>';
    else if (annStale(a)) badges += '<span class="rn-badge stale">edited since pinned</span>';
    row.innerHTML =
      '<div class="rn-target">' + escapeHtml(a.pin_id) + ' · ' + escapeHtml(a.description || '') + '</div>' +
      (badges ? '<div class="rn-meta">' + badges + '</div>' : '') +
      '<div class="rn-text">' + escapeHtml(a.note) + '</div>';
    return row;
  }
  function escapeHtml(s) { return (s || '').replace(/[&<>"]/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]; }); }

  // Build the pin-notes section of the payload ('' when there are no pins).
  function buildNotesText() {
    if (!annotations.length) return '';
    var bySlide = {};
    annotations.forEach(function (a) { (bySlide[a.slide_uuid] = bySlide[a.slide_uuid] || []).push(a); });
    var order = orderedSlideIds(bySlide);
    var pubCount = annotations.filter(annProv).length;

    var out = 'DECK REVIEW NOTES — apply ONLY these changes, with surgical scope. Do not touch anything not referenced.\n';
    out += '# ' + annotations.length + ' note(s) across ' + order.length + ' slide(s) · plan_revision ' + PLAN_REV;
    if (pubCount) out += ' · ' + pubCount + ' on PUBLISHED content (edits diverge from master — preserve original intent)';
    out += '\n\n';

    order.forEach(function (sid) {
      var items = bySlide[sid].slice().sort(byPosition);
      var idx = slideIndexOf(sid);
      out += '### ' + (idx >= 0 ? 's' + (idx + 1) + ' · ' : '') + (slideTopicOf(items[0]) || '(untitled)') + '  [slide ' + sid + ']\n';
      items.forEach(function (a) {
        out += '- [' + a.pin_id + '] block_uuid=' + (a.block_uuid || '(slide-level)') + '\n';
        out += '  where: ' + (a.description || '') + '\n';
        var info = annProv(a);
        if (info) out += '  source: PUBLISHED — ' + provLabel(info) + (info.diverged ? '  [DIVERGED FROM MASTER]' : '') + '\n';
        if (annTargetRemoved(a)) out += '  warning: pin target no longer exists (target removed) — confirm before applying\n';
        else if (annStale(a)) out += '  warning: anchored content changed since this note was written (content_hash mismatch) — re-confirm intent\n';
        out += '  change: ' + a.note + '\n';
      });
      out += '\n';
    });
    return out;
  }
  function flashCopyConfirm(msg) {
    var c = $('copy-confirm'); if (!c) return;
    c.textContent = msg; c.style.opacity = 1; setTimeout(function () { c.style.opacity = 0; }, 2600);
  }
  var copyBtn = $('copy-notes');
  if (copyBtn) copyBtn.addEventListener('click', function () {
    var bapi = window.__BOARD_API__, hasBoard = !!(bapi && bapi.hasChanges());
    var tapi = window.__TEXTEDITS_API__, hasText = !!(tapi && tapi.hasChanges());
    if (!annotations.length && !hasBoard && !hasText) return;
    var parts = [];
    var notes = buildNotesText(); if (notes) parts.push(notes.replace(/\n+$/, ''));
    if (hasText) parts.push(tapi.payloadText());
    if (hasBoard) parts.push(bapi.payloadText());
    var out = parts.join('\n\n') + '\n';
    var bits = [];
    if (annotations.length) bits.push(annotations.length + ' note(s)');
    if (hasText) bits.push('text edit(s)');
    if (hasBoard) bits.push('layout/variant changes');
    navigator.clipboard.writeText(out).then(function () { flashCopyConfirm('✓ ' + bits.join(' + ') + ' copied — paste into Claude'); });
  });

  // hydrate existing pins/notes
  annotations.forEach(dropPin); renderReview();

  // (Drawing / review-sheet feature parked — pins carry precise element + coordinates in text.)


  /* ============================================================
     SOURCES PANEL
  ============================================================ */
  /* The Sources manifest carries TWO provenance streams into one panel:
       (1) resolved ASSET provenance (fonts/logos/icons/images) recorded at BRAND —
           {kind, source, author, license, link}; and
       (2) REFERENCE-LIBRARY provenance for content/layouts reused from a prior
           deck — {kind:'reference', source, deck|reused_from, date, license?, link?}.
     build.py compiles window.__SOURCES__ from both (build.py owns emission; this
     only renders what it receives). Rendering is field-tolerant so the contract
     can grow without breaking a shipped deck, and a reference entry always shows
     the source deck + date the content came from. */
  function isReferenceSource(s) { return !!(s && (s.kind === 'reference' || s.deck || s.reused_from)); }
  function sourceRow(s) {
    var row = document.createElement('div');
    if (isReferenceSource(s)) {
      row.className = 'src-row src-ref';
      var deck = s.deck || s.reused_from || '';
      var origin = [deck, s.date].filter(Boolean).map(escapeHtml).join(' · ');
      row.innerHTML =
        '<div class="src-kind">reused' + (s.license ? ' · ' + escapeHtml(s.license) : '') + '</div>' +
        escapeHtml(s.source || s.template || s.title || 'Reused content') +
        (origin ? '<div class="src-origin" style="opacity:.6;font-size:12px;margin-top:2px">from ' + origin + '</div>' : '') +
        (s.link ? '<br><a href="' + escapeHtml(s.link) + '" target="_blank" rel="noopener">' + escapeHtml(s.link) + '</a>' : '');
    } else {
      row.className = 'src-row';
      row.innerHTML =
        '<div class="src-kind">' + escapeHtml(s.kind || '') + (s.license ? ' · ' + escapeHtml(s.license) : '') + '</div>' +
        escapeHtml(s.source || '') + (s.author ? ' — ' + escapeHtml(s.author) : '') +
        (s.link ? '<br><a href="' + escapeHtml(s.link) + '" target="_blank" rel="noopener">' + escapeHtml(s.link) + '</a>' : '');
    }
    return row;
  }
  function renderSources(list, src) {
    list.innerHTML = '';
    if (!src.length) { list.innerHTML = '<div style="opacity:.4;font-size:13px">No third-party sources.</div>'; return; }
    var assets = src.filter(function (s) { return !isReferenceSource(s); });
    var refs = src.filter(isReferenceSource);
    var both = assets.length && refs.length;   // only show section headers when both streams present
    function section(label, rows) {
      if (!rows.length) return;
      if (both) {
        var h = document.createElement('div'); h.className = 'src-section';
        h.setAttribute('style', 'font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.5;margin:14px 0 6px');
        h.textContent = label; list.appendChild(h);
      }
      rows.forEach(function (s) { list.appendChild(sourceRow(s)); });
    }
    section('Assets', assets);
    section('Reused from prior decks', refs);
  }

  var sourcesBtn = $('sources-btn'), sourcesPanel = $('sources-panel');
  if (sourcesBtn && sourcesPanel) {
    var sourcesListEl = $('sources-list');
    if (sourcesListEl) renderSources(sourcesListEl, window.__SOURCES__ || []);
    sourcesBtn.addEventListener('click', function () { sourcesPanel.classList.toggle('open'); sourcesBtn.classList.toggle('active'); });
  }

  // generic side-panel close buttons
  document.querySelectorAll('.sidepanel .panel-close').forEach(function (b) {
    b.addEventListener('click', function () { var p = b.closest('.sidepanel'); if (p) p.classList.remove('open'); if (p && p.id === 'review-panel') exitEdit(); });
  });

  /* ============================================================
     EXPORT — HTML / PDF / PPTX  (captures the fixed 1280x720 stage)
  ============================================================ */
  var CDN = (window.__CDN__ || {}); // {html2canvas:{url,integrity}, jspdf:{...}, pptx:{...}}
  function loadScript(spec) {
    return new Promise(function (resolve, reject) {
      if (!spec || !spec.url) return reject(new Error('missing CDN spec'));
      if (document.querySelector('script[src="' + spec.url + '"]')) return resolve();
      var s = document.createElement('script'); s.src = spec.url; s.crossOrigin = 'anonymous';
      if (spec.integrity) s.integrity = spec.integrity;
      s.onload = resolve; s.onerror = function () { reject(new Error('Failed to load ' + spec.url)); };
      document.head.appendChild(s);
    });
  }
  var saveBtn = $('save-btn'), saveMenu = $('save-menu');
  if (saveBtn && saveMenu) {
    saveBtn.addEventListener('click', function (e) { e.stopPropagation(); saveMenu.classList.toggle('open'); });
    document.addEventListener('click', function () { saveMenu.classList.remove('open'); });
    saveMenu.addEventListener('click', function (e) { e.stopPropagation(); });
    saveMenu.querySelectorAll('button[data-export]').forEach(function (b) {
      b.addEventListener('click', function () {
        saveMenu.classList.remove('open');
        var f = b.getAttribute('data-export');
        // Save As lives ONLY on the localhost editor (stripped from the file view). There the
        // edit server can run the REAL engine export — the same pipeline a manual export uses —
        // and open the result in PowerPoint / a PDF viewer. Route to it. The old in-browser
        // path (html2canvas/jsPDF, CDN) stays only as a defensive fallback if somehow unserved.
        if (SERVED) { serverExport(f); return; }
        if (f === 'html') exportHTML(); else if (f === 'pdf') exportPDF(); else if (f === 'pptx') exportPPTX();
      });
    });
  }
  function prog(msg, pct) { var o = $('export-overlay'), m = $('export-msg'), fl = $('export-fill'); if (o) o.classList.add('visible'); if (m) m.textContent = msg || ''; if (fl && pct != null) fl.style.width = Math.min(pct, 100) + '%'; }
  function hideProg() { var o = $('export-overlay'); if (o) o.classList.remove('visible'); }

  /* ---- Terminal overlay states so an export always ENDS (never an infinite spinner):
     resolve to a green "Done" (auto-dismiss) or a red "Export failed" (click to dismiss). ---- */
  function progTitle(t) { var el = document.querySelector('#export-overlay .exp-title'); if (el) el.textContent = t; }
  function progReset() { var o = $('export-overlay'); if (o) o.classList.remove('done', 'error'); progTitle('Exporting Deck'); var fl = $('export-fill'); if (fl) fl.style.width = '0%'; }
  function hideProgReset() { hideProg(); setTimeout(progReset, 320); }
  function progDone(msg) {
    var o = $('export-overlay'); if (!o) return;
    o.classList.remove('error'); o.classList.add('done'); progTitle('Done');
    var m = $('export-msg'); if (m) m.textContent = msg || 'Exported ✓';
    var fl = $('export-fill'); if (fl) fl.style.width = '100%';
    setTimeout(hideProgReset, 2600);
  }
  function progError(msg) {
    var o = $('export-overlay'); if (!o) { alert('Export failed: ' + msg); return; }
    o.classList.remove('done'); o.classList.add('error'); progTitle('Export failed');
    var m = $('export-msg'); if (m) m.textContent = msg || 'Something went wrong';
    var dismiss = function () { hideProgReset(); document.removeEventListener('click', dismiss); };
    setTimeout(function () { document.addEventListener('click', dismiss); }, 60);
  }

  /* Real export via the edit server (localhost only): it runs the SAME engine pipeline as a
     manual export (rebuild → export_pptx.py / Chrome print-to-pdf) and opens the file in the OS
     app. Always resolves — a hard client timeout guarantees the overlay can't hang forever. */
  function serverExport(format) {
    var LABEL = { pptx: 'PowerPoint', pdf: 'PDF', html: 'HTML' };
    var o = $('export-overlay'); if (o) o.classList.add('visible');
    progReset(); progTitle('Exporting Deck');
    var m = $('export-msg'); if (m) m.textContent = 'Rebuilding + generating ' + (LABEL[format] || format) + '… this can take a few seconds';
    var fl = $('export-fill'); if (fl) fl.style.width = '35%';
    var ctrl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctrl) ctrl.abort(); }, 200000);
    fetch('/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format: format }), signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, msg: 'unexpected server response (is this the localhost editor?)' }; });
    }).then(function (j) {
      clearTimeout(to);
      if (j && j.ok) {
        var fname = j.path ? (' (' + String(j.path).split(/[\\/]/).pop() + ')') : '';
        progDone('Exported ✓ — opening ' + (LABEL[format] || format) + fname);
      } else { progError((j && j.msg) || 'unknown error'); }
    }).catch(function (e) {
      clearTimeout(to);
      progError(e && e.name === 'AbortError' ? 'Timed out — the export took too long'
        : ('Could not reach the edit server' + (e && e.message ? ': ' + e.message : '')));
    });
  }

  function exportHTML() {
    try {
      var blob = new Blob([document.documentElement.outerHTML], { type: 'text/html;charset=utf-8' });
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = (window.__DECK__.title || 'deck') + '.html'; a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 8000);
    } catch (e) { alert('HTML export failed: ' + e.message); }
  }
  function eachStage(cb) { return document.querySelectorAll('.stage'); }
  async function capture(stage) {
    // useCORS (not allowTaint): allowTaint lets cross-origin pixels draw but then
    // taints the canvas so toDataURL() throws and the WHOLE export dies. With CORS
    // only, an image lacking ACAO is simply dropped from that one slide — a far
    // safer failure. backgroundColor:null keeps the stage's own bg (no white slivers).
    // onclone forces reveal-on-scroll content visible in the CLONE, so the live deck
    // is never mutated. (Conic-gradient/donut reconciliation is owned by the PPTX
    // thread — intentionally not touched here.)
    return await html2canvas(stage, {
      scale: 2, useCORS: true, backgroundColor: null, logging: false, imageTimeout: 20000,
      width: 1280, height: 720, windowWidth: 1280, windowHeight: 720,
      onclone: function (doc) {
        doc.querySelectorAll('.sb-review-chip, .ann-pin, #review-panel, #pin-popup').forEach(function (e) { e.remove(); });
        var r = doc.querySelectorAll('.reveal');
        for (var k = 0; k < r.length; k++) r[k].classList.add('visible');
      }
    });
  }
  function nextFrame() { return new Promise(function (r) { requestAnimationFrame(function () { requestAnimationFrame(r); }); }); }
  async function fontsReady() { try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) {} }
  async function imagesReady(stage) {
    var imgs = Array.prototype.slice.call(stage.querySelectorAll('img'));
    await Promise.all(imgs.map(function (im) {
      if (im.complete && im.naturalWidth) return Promise.resolve();
      if (im.decode) return im.decode().catch(function () {});   // resolves even if decode fails; capture drops it
      return new Promise(function (r) { im.addEventListener('load', r); im.addEventListener('error', r); });
    }));
  }
  async function captureWithRetry(stage) {
    try { return await capture(stage); }
    catch (e) { await new Promise(function (r) { setTimeout(r, 150); }); return await capture(stage); }
  }
  async function exportPDF() {
    prog('Loading libraries...', 2);
    var restore = currentSlide;                       // return the deck to where the user was
    try {
      await loadScript(CDN.html2canvas); await loadScript(CDN.jspdf);
      if (typeof html2canvas !== 'function' || !(window.jspdf && window.jspdf.jsPDF)) {
        throw new Error('export libraries did not initialise');
      }
      var jsPDF = window.jspdf.jsPDF;
      var pdf = new jsPDF({ orientation: 'landscape', unit: 'px', format: [1280, 720], hotfixes: ['px_scaling'] });
      var stages = eachStage();
      await fontsReady();                             // capture with correct Montserrat metrics, once
      for (var i = 0; i < stages.length; i++) {
        prog('Rendering slide ' + (i + 1) + '/' + stages.length, i / stages.length * 90);
        stages[i].scrollIntoView({ behavior: 'instant' });
        await nextFrame();                            // let layout settle (2 rAFs) instead of a fixed timer
        contrastForStage(stages[i]);
        await imagesReady(stages[i]);
        var c;
        try { c = await captureWithRetry(stages[i]); }
        catch (e) { throw new Error('slide ' + (i + 1) + ' could not be rendered (' + e.message + ')'); }
        if (i > 0) pdf.addPage([1280, 720], 'landscape');
        pdf.addImage(c.toDataURL('image/jpeg', 0.93), 'JPEG', 0, 0, 1280, 720);
      }
      hideProg(); pdf.save((window.__DECK__.title || 'deck') + '.pdf');
    } catch (e) {
      hideProg();
      alert('PDF export failed: ' + e.message + '\n(Export needs internet to load libraries.)');
    } finally {
      if (restore && restore.scrollIntoView) restore.scrollIntoView({ behavior: 'instant' });
    }
  }
  function cssColorToHex(c) {
    var m = (c || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return '000000';
    return [1, 2, 3].map(function (i) { return (+m[i]).toString(16).padStart(2, '0'); }).join('');
  }
  /* Walk a text block into pptxgenjs runs, preserving per-run colour/bold
     (nested <span> accents), letter-spacing, uppercase, and <br> breaks so a
     coloured word like "2026" or a two-line headline survives as editable text. */
  /* Split one text node's value into the VISUAL lines the browser laid it out as, by scanning
     per-character client rects and detecting the y-jump where a soft wrap occurred. Returns the
     raw substrings (one per rendered line); a single-line node returns [text] unchanged. */
  function nodeVisualLines(node) {
    var text = node.nodeValue || '';
    if (text.length < 2) return [text];
    var range = document.createRange();
    var lines = [], start = 0, prevTop = null, lineH = 0;
    for (var i = 0; i < text.length; i++) {
      range.setStart(node, i); range.setEnd(node, i + 1);
      var rects = range.getClientRects();
      if (!rects.length) continue;
      var rr = rects[0];
      if (!lineH && rr.height) lineH = rr.height;
      if (prevTop !== null && rr.top > prevTop + (lineH || 4) * 0.5) { lines.push(text.slice(start, i)); start = i; }
      prevTop = rr.top;
    }
    lines.push(text.slice(start));
    return lines;
  }
  function pptRuns(root, baseCs) {
    var runs = [];
    function emit(text, cs, brk) {
      if (!text) { if (brk && runs.length) runs[runs.length - 1].options.breakLine = true; return; }
      if (cs.textTransform === 'uppercase') text = text.toUpperCase();
      var o = { fontFace: 'Montserrat', fontSize: parseFloat(cs.fontSize) * 0.75,
                color: cssColorToHex(cs.color), bold: parseInt(cs.fontWeight, 10) >= 600,
                italic: cs.fontStyle === 'italic',
                underline: (cs.textDecorationLine || cs.textDecoration || '').indexOf('underline') >= 0 };
      var ls = cs.letterSpacing;
      if (/px$/.test(ls) && Math.abs(parseFloat(ls)) > 0.05) o.charSpacing = parseFloat(ls) * 0.75;
      if (brk) o.breakLine = true;
      runs.push({ text: text, options: o });
    }
    function walk(node, cs) {
      Array.prototype.forEach.call(node.childNodes, function (ch) {
        if (ch.nodeType === 3) {
          if (!/\S/.test(ch.nodeValue) && ch.nodeValue !== ' ') return;
          // Split the text node at the browser's SOFT-WRAP points and mark each as a breakLine.
          // The exporter then reproduces the exact wrap (PowerPoint's Montserrat is wider than
          // Chrome's, so left to re-wrap it adds a line and the block overflows the next one).
          var vlines = nodeVisualLines(ch);
          for (var li = 0; li < vlines.length; li++) {
            var t = vlines[li].replace(/\s+/g, ' ');
            if (li > 0) t = t.replace(/^ /, '');
            if (t.trim() !== '' || (li === 0 && t === ' ')) emit(t, cs, false);
            if (li < vlines.length - 1 && runs.length) runs[runs.length - 1].options.breakLine = true;
          }
        } else if (ch.nodeType === 1) {
          if (ch.tagName === 'BR') { if (runs.length) runs[runs.length - 1].options.breakLine = true; }
          else walk(ch, getComputedStyle(ch));
        }
      });
    }
    walk(root, baseCs);
    if (!runs.length) emit(root.innerText || '', baseCs, false);
    while (runs.length && runs[0].text.trim() === '') runs.shift();
    while (runs.length && runs[runs.length - 1].text.trim() === '') runs.pop();
    return runs;
  }
  /* ---- CSS colour -> {hex, alpha} (handles rgb/rgba/named/var via computed) ---- */
  function parseRGBA(c) {
    var m = (c || '').match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.%]+))?/);
    if (!m) return null;
    var hex = [1, 2, 3].map(function (i) { return Math.round(+m[i]).toString(16).padStart(2, '0'); }).join('');
    var a = m[4] === undefined ? 1 : (String(m[4]).indexOf('%') >= 0 ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
    return { hex: hex, alpha: isNaN(a) ? 1 : a };
  }
  var SKIP_SHAPE = /\b(bloom-panel|bloom-trigger|bloom-close|ann-pin|draw-layer)\b/;

  /* A leaf TEXT unit: an element that holds text and whose only element children
     are inline <span>s (a paragraph line). This is the unit we emit as one editable
     text box so mid-line accent spans (bold/coloured words) stay grouped as runs. */
  function isTextUnit(el) {
    if (!(el.innerText || '').trim()) return false;
    var kids = el.children;
    for (var i = 0; i < kids.length; i++) {
      var t = kids[i].tagName;
      if (t !== 'SPAN' && t !== 'B' && t !== 'STRONG' && t !== 'EM' && t !== 'I' && t !== 'BR') return false;
    }
    return true;
  }

  /* NOTE (Track D): the reference-slide RASTER+overlay export path (`renderReferenceSlide`)
     was DELETED. It is permanently rejected — a screenshot with text laid over it is a
     photocopy, not a translation. Reference slides are now exported by the ENGINE
     (engine/export_pptx.py), which COPIES the original source slide natively (every shape
     movable) and brand-recolours it. The in-deck PPTX button no longer builds a deck; it
     directs to that engine EXPORT pass (see exportPPTX below). */

  /* Serialize an inline SVG to a crisp, self-contained data URI (RC8c). The clone
     BAKES each element's COMPUTED stroke/fill/stroke-width as literal attributes —
     resolving currentColor against the element's computed colour — instead of
     stamping one root-level override that blanks per-path paint. Rendered at 2x so
     strokes stay sharp at export scale (viewBox keeps stroke-width proportional). */
  function svgToDataUri(svg, b, sc) {
    var RES = 2;
    var clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', Math.round(b.w * sc * RES));
    clone.setAttribute('height', Math.round(b.h * sc * RES));
    var hasVB = svg.getAttribute('viewBox');
    var src = svg.querySelectorAll('*'), dst = clone.querySelectorAll('*');
    for (var k = 0; k < src.length; k++) {
      var scs = getComputedStyle(src[k]), ce = dst[k]; if (!ce) continue;
      if (scs.stroke && scs.stroke !== 'none') ce.setAttribute('stroke', scs.stroke); // currentColor already resolved
      if (scs.fill) ce.setAttribute('fill', scs.fill);
      var sw = parseFloat(scs.strokeWidth);
      // no viewBox -> px space is scaled by RES, so scale the stroke to match
      if (sw > 0) ce.setAttribute('stroke-width', hasVB ? sw : sw * RES);
    }
    var rcs = getComputedStyle(svg);
    if (rcs.stroke && rcs.stroke !== 'none') clone.setAttribute('stroke', rcs.stroke);
    if (rcs.fill) clone.setAttribute('fill', rcs.fill);
    try {
      return 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(new XMLSerializer().serializeToString(clone))));
    } catch (e) { return 'data:image/svg+xml;base64,' + btoa(new XMLSerializer().serializeToString(clone)); }
  }

  /* ================= ENGINE EXPORT MANIFEST (Track A/C) =================
     window.__exportManifest() walks each AUTHORED stage and RETURNS a JSON manifest
     (shapes/images/svgs/texts with logical-pixel boxes, per-run styles, z-order,
     native-chart specs) instead of building a pptx. This is the ONLY export path — the
     old in-browser raster/native builders (renderStageNative/emitBox/addOneText/
     addImageLayer/addNativeChart) were deleted; the engine (engine/export_pptx.py) is
     the sole exporter.
     engine/export_pptx.py drives headless Chrome, pulls this, and constructs slides
     with python-pptx (deterministic, unit-testable, no CDN roulette). REFERENCE slides
     are excluded — the engine copies those natively from the source deck. */
  function _mBox(el, sr, sc) {
    var r = el.getBoundingClientRect();
    return { x: (r.left - sr.left) / sc, y: (r.top - sr.top) / sc, w: r.width / sc, h: r.height / sc };
  }
  function _mContentBox(el, sr, sc) {
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    var pl = parseFloat(cs.paddingLeft) || 0, pr = parseFloat(cs.paddingRight) || 0,
        pt = parseFloat(cs.paddingTop) || 0, pb = parseFloat(cs.paddingBottom) || 0;
    var Ll = (r.left - sr.left) / sc, Lt = (r.top - sr.top) / sc, Lw = r.width / sc, Lh = r.height / sc;
    var cw = Lw - pl - pr, ch = Lh - pt - pb;
    return { x: Ll + pl, y: Lt + pt, w: cw < 1 ? Lw : cw, h: ch < 1 ? Lh : ch };
  }
  function _mRuns(el, cs) {
    return pptRuns(el, cs).map(function (r) {
      return { text: r.text, color: r.options.color, bold: !!r.options.bold,
               italic: !!r.options.italic, underline: !!r.options.underline,
               size: r.options.fontSize, charSpacing: r.options.charSpacing,
               breakLine: !!r.options.breakLine };   // carry soft-wrap/<br> breaks to the exporter
    });
  }
  function _mAlign(cs) {
    return cs.textAlign === 'center' ? 'center'
      : ((cs.textAlign === 'right' || cs.textAlign === 'end') ? 'right' : 'left');
  }
  /* Parse a CSS linear-gradient into {angle(css deg), stops:[{color,alpha,pos}]} so the
     exporter can lay a real gradient fill (legibility scrims fade dark->clear across a slide;
     a flat fill would darken the whole thing and bury the artwork underneath). */
  function _parseGradient(bgimg) {
    var m = bgimg.match(/linear-gradient\(([\s\S]*)\)/);
    if (!m) return null;
    var body = m[1], angle = 180;                 // CSS default = to bottom
    var am = body.match(/^\s*(-?[\d.]+)deg/);
    if (am) angle = parseFloat(am[1]);
    else if (/to\s+right/.test(body)) angle = 90;
    else if (/to\s+left/.test(body)) angle = 270;
    else if (/to\s+top/.test(body)) angle = 0;
    else if (/to\s+bottom/.test(body)) angle = 180;
    var stops = [], re = /(rgba?\([^)]+\))\s*([\d.]+%)?/g, mm;
    while ((mm = re.exec(body))) {
      var q = parseRGBA(mm[1]); if (!q) continue;
      stops.push({ color: q.hex, alpha: q.alpha, pos: mm[2] ? parseFloat(mm[2]) / 100 : null });
    }
    if (stops.length < 2) return null;
    if (stops[0].pos === null) stops[0].pos = 0;
    if (stops[stops.length - 1].pos === null) stops[stops.length - 1].pos = 1;
    for (var i = 1; i < stops.length - 1; i++) if (stops[i].pos === null) stops[i].pos = i / (stops.length - 1);
    return { angle: angle, stops: stops };
  }
  /* one element's fill/border as a shape spec (mirrors emitBox's decisions) */
  function _mShapeSpec(cs, b) {
    var out = { box: b, shape: 'rect' }, has = false;
    var op = parseFloat(cs.opacity); if (isNaN(op)) op = 1;   // element opacity scales fill alpha
    var bg = parseRGBA(cs.backgroundColor);
    if (bg && bg.alpha * op > 0.02) { out.fill = bg.hex; var a = bg.alpha * op; if (a < 0.99) out.fillAlpha = a; has = true; }
    else if (cs.backgroundImage && cs.backgroundImage.indexOf('linear-gradient') >= 0) {
      // Capture the FULL gradient (stops+angle). A dark->clear scrim must stay a gradient, and
      // the dark-theme .sb-card frosted panel (translucent-white stops) also renders truer as a
      // gradient than as a flat fill. Keep a flat fallback for exporters that can't gradient.
      var grad = _parseGradient(cs.backgroundImage);
      if (grad) {
        if (op < 0.99) grad.stops.forEach(function (s) { s.alpha *= op; });
        out.gradient = grad;
        for (var k = 0; k < grad.stops.length; k++) { if (grad.stops[k].alpha > 0.05) { out.fill = grad.stops[k].color; if (grad.stops[k].alpha < 0.99) out.fillAlpha = grad.stops[k].alpha; break; } }
        has = true;
      }
    }
    var rad = parseFloat(cs.borderTopLeftRadius) || 0;
    var bw = parseFloat(cs.borderTopWidth) || 0, bc = parseRGBA(cs.borderTopColor);
    var uniform = bw > 0.5 && bc && bc.alpha > 0.05
      && cs.borderTopWidth === cs.borderRightWidth && cs.borderTopWidth === cs.borderBottomWidth && cs.borderTopWidth === cs.borderLeftWidth
      && cs.borderTopColor === cs.borderRightColor && cs.borderTopColor === cs.borderBottomColor && cs.borderTopColor === cs.borderLeftColor;
    if (uniform) { out.line = bc.hex; out.lineW = bw; has = true; }
    if (!has) return null;
    if (rad > 0 && rad >= Math.min(b.w, b.h) / 2 - 1) out.shape = 'ellipse';
    else if (rad > 2) { out.shape = 'roundRect'; out.rectRadius = rad; }
    return out;
  }
  /* Asymmetric side borders (e.g. a coloured `border-left` accent bar) that _mShapeSpec's
     uniform-border test skips. Emit each as a thin filled rectangle so the accent survives
     into PPTX (it already rendered in HTML/PDF). Widths are px -> 1280-space via sc. */
  function _mBorderBars(cs, b, sc) {
    var out = [];
    var uniform = cs.borderTopWidth === cs.borderRightWidth && cs.borderTopWidth === cs.borderBottomWidth && cs.borderTopWidth === cs.borderLeftWidth
      && cs.borderTopColor === cs.borderRightColor && cs.borderTopColor === cs.borderBottomColor && cs.borderTopColor === cs.borderLeftColor;
    if (uniform) return out;                              // a real box outline — handled by _mShapeSpec
    ['Left', 'Right', 'Top', 'Bottom'].forEach(function (side) {
      var raw = parseFloat(cs['border' + side + 'Width']) || 0;
      var col = parseRGBA(cs['border' + side + 'Color']);
      if (raw <= 0.5 || !col || col.alpha <= 0.05) return;
      var w = raw / sc, box;
      if (side === 'Left') box = { x: b.x, y: b.y, w: w, h: b.h };
      else if (side === 'Right') box = { x: b.x + b.w - w, y: b.y, w: w, h: b.h };
      else if (side === 'Top') box = { x: b.x, y: b.y, w: b.w, h: w };
      else box = { x: b.x, y: b.y + b.h - w, w: b.w, h: w };
      out.push({ box: box, shape: 'rect', fill: col.hex });
    });
    return out;
  }
  /* Rasterize an inline SVG to a PNG data URI (python-pptx add_picture cannot embed
     SVG). Drawn at 3x for crisp icons. Resolves to null on failure. */
  function _svgToPng(svg, b, sc) {
    return new Promise(function (resolve) {
      var uri;
      try { uri = svgToDataUri(svg, b, sc); } catch (e) { return resolve(null); }
      var img = new Image();
      img.onload = function () {
        try {
          var c = document.createElement('canvas');
          c.width = Math.max(2, Math.round(b.w * 3)); c.height = Math.max(2, Math.round(b.h * 3));
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL('image/png'));
        } catch (e) { resolve(null); }
      };
      img.onerror = function () { resolve(null); };
      img.src = uri;
    });
  }
  /* ---- background-composite FLATTENER ----
     PowerPoint can't do mix-blend-mode or match layered CSS gradients, so rebuilding a photo's
     duotone tint + legibility scrim as separate PPTX layers looks harsher than the HTML. Instead
     we BAKE the exact browser composite (photo + every full-covering overlay, honouring blend
     mode / opacity / gradient) into ONE flat PNG via canvas — pixel-identical to the HTML — and
     drop the overlay layers. Text stays a separate editable layer on top. */
  function _rgbaStr(hex, a) {
    return 'rgba(' + parseInt(hex.slice(0, 2), 16) + ',' + parseInt(hex.slice(2, 4), 16) + ',' + parseInt(hex.slice(4, 6), 16) + ',' + a + ')';
  }
  function _canvasGradient(ctx, g, W, H) {
    var a = (g.angle || 180) * Math.PI / 180, dx = Math.sin(a), dy = -Math.cos(a);
    var cx = W / 2, cy = H / 2, half = (Math.abs(dx) * W + Math.abs(dy) * H) / 2;
    var lg = ctx.createLinearGradient(cx - dx * half, cy - dy * half, cx + dx * half, cy + dy * half);
    g.stops.forEach(function (s) { lg.addColorStop(Math.max(0, Math.min(1, s.pos)), _rgbaStr(s.color, s.alpha)); });
    return lg;
  }
  function _posFrac(v) {
    if (!v) return 0.5; v = v.trim();
    if (v === 'left' || v === 'top') return 0;
    if (v === 'right' || v === 'bottom') return 1;
    if (v === 'center') return 0.5;
    var m = v.match(/(-?[\d.]+)%/); return m ? Math.max(0, Math.min(1, parseFloat(m[1]) / 100)) : 0.5;
  }
  /* Bake an object-fit:cover image's ACTUAL crop (honouring object-position) into a PNG at the
     display box's aspect ratio. Without this, add_picture stretches the full image into the box —
     a square headshot in a landscape tile came out distorted (and the HTML crop was ignored). */
  function _coverCrop(img, box, cs) {
    try {
      var iw = img.naturalWidth, ih = img.naturalHeight; if (!iw || !ih) return null;
      var boxAR = box.w / box.h, imgAR = iw / ih, sw, sh;
      if (imgAR > boxAR) { sh = ih; sw = ih * boxAR; } else { sw = iw; sh = iw / boxAR; }
      var op = (cs.objectPosition || '50% 50%').split(/\s+/);
      var sx = (iw - sw) * _posFrac(op[0]), sy = (ih - sh) * _posFrac(op[1] !== undefined ? op[1] : '50%');
      var c = document.createElement('canvas');
      c.width = Math.max(2, Math.round(box.w * 2)); c.height = Math.max(2, Math.round(box.h * 2));
      c.getContext('2d').drawImage(img, sx, sy, sw, sh, 0, 0, c.width, c.height);
      return c.toDataURL('image/png');
    } catch (e) { return null; }
  }
  function _flattenComposite(img, overlays, box, sc) {
    try {
      var W = Math.max(2, Math.round(box.w * sc * 2)), H = Math.max(2, Math.round(box.h * sc * 2));
      var c = document.createElement('canvas'); c.width = W; c.height = H;
      var ctx = c.getContext('2d');
      var iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height;
      if (iw && ih) {                                   // replicate object-fit:cover
        var scale = Math.max(W / iw, H / ih), dw = iw * scale, dh = ih * scale;
        ctx.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
      }
      overlays.forEach(function (el) {
        var cs = getComputedStyle(el);
        ctx.globalAlpha = isNaN(parseFloat(cs.opacity)) ? 1 : parseFloat(cs.opacity);
        ctx.globalCompositeOperation = (cs.mixBlendMode === 'multiply') ? 'multiply' : 'source-over';
        var bgc = parseRGBA(cs.backgroundColor);
        if (bgc && bgc.alpha > 0.02) { ctx.fillStyle = _rgbaStr(bgc.hex, bgc.alpha); ctx.fillRect(0, 0, W, H); }
        else if (/linear-gradient/.test(cs.backgroundImage)) {
          var g = _parseGradient(cs.backgroundImage);
          if (g) { ctx.fillStyle = _canvasGradient(ctx, g, W, H); ctx.fillRect(0, 0, W, H); }
        }
      });
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
      return c.toDataURL('image/png');
    } catch (e) { return null; }
  }
  async function _manifestForStage(stage, sr, sc) {
    var man = { shapes: [], images: [], charts: [], texts: [] };
    var scs = getComputedStyle(stage), sbg = parseRGBA(scs.backgroundColor);
    if (sbg && sbg.alpha > 0.5) man.bg = sbg.hex;
    var inShape = {};
    // Pre-pass: bake photo+overlay composites (see _flattenComposite) so PPTX backgrounds match
    // the HTML 1:1. Marks the baked-in overlay layers `data-flat-skip` so the shape walk drops them.
    Array.prototype.forEach.call(stage.querySelectorAll('img.img-cover'), function (img) {
      var box = _mBox(img, sr, sc);
      var container = img.parentElement && img.parentElement.parentElement;
      if (!container) return;
      var overlays = Array.prototype.filter.call(container.children, function (el) {
        if (el === img.parentElement || el.contains(img)) return false;
        if (el.tagName === 'IMG' || el.querySelector && el.querySelector('img,[data-block],svg')) return false;
        if ((el.innerText || '').trim()) return false;
        var cs = getComputedStyle(el);
        var hasBg = (parseRGBA(cs.backgroundColor) && parseRGBA(cs.backgroundColor).alpha > 0.02) || /linear-gradient/.test(cs.backgroundImage);
        var eb = _mBox(el, sr, sc);
        return hasBg && eb.w >= box.w * 0.8 && eb.h >= box.h * 0.8;
      });
      if (!overlays.length) return;
      var uri = _flattenComposite(img, overlays, box, sc);
      if (uri) { img.__flatURI = uri; overlays.forEach(function (o) { o.setAttribute('data-flat-skip', '1'); }); }
    });
    // Stamp every element with its DOM (paint) order so shapes AND images share ONE z-space.
    // Without this the exporter drew all shapes then all images, so a legibility scrim (a shape
    // that sits ABOVE the photo in the DOM) landed UNDER the photo and vanished.
    var _domZ = 0;
    (function stampZ(node) { Array.prototype.forEach.call(node.children, function (el) { el.__z = _domZ++; stampZ(el); }); })(stage);
    // shape layer + text-in-shape (small containers: numbers-in-circles fix)
    (function walk(node) {
      Array.prototype.forEach.call(node.children, function (el) {
        var tag = el.tagName.toUpperCase();
        if (el.hasAttribute('data-chart')) return;
        if (tag === 'IMG' || tag === 'SVG') return;
        if (el.hasAttribute('data-logo') || el.hasAttribute('data-image')) return;
        if (el.getAttribute('data-flat-skip')) return;   // baked into the flattened photo composite
        if (el.className && SKIP_SHAPE.test(el.className)) return;
        if (el.classList && (el.classList.contains('sb-footer-logo') || el.classList.contains('sb-page-num'))) return;
        var cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return;
        var b = _mBox(el, sr, sc);
        if (b.w > 0.4 && b.h > 0.4) {
          var spec = _mShapeSpec(cs, b);
          if (spec) {
            if (b.w <= 72 && b.h <= 72) {
              var blk = el.hasAttribute('data-block') ? el : el.querySelector('[data-block]');
              if (blk && (blk.innerText || '').trim() && isTextUnit(blk)) {
                spec.text = { runs: _mRuns(blk, getComputedStyle(blk)), align: 'center' };
                inShape[blk.getAttribute('data-block')] = 1;
              } else if (!el.querySelector('[data-block]') && (el.innerText || '').trim() && isTextUnit(el)) {
                // Small badge whose label is a RAW text node (e.g. numbered step badges: a
                // <span> holding just "1"). No data-block to bind, so text-in-shape used to
                // miss it — the digit then fell to the orphan pass as a TOP-LEFT textbox.
                // Attach it here so it centres (H+V) inside its own badge shape.
                spec.text = { runs: _mRuns(el, cs), align: 'center' };
                el.setAttribute('data-inshape', '1');
              }
            }
            spec.z = el.__z;
            man.shapes.push(spec);
          }
          // Coloured side-border accents (e.g. border-left bars) — thin rects on top.
          _mBorderBars(cs, b, sc).forEach(function (bar) { bar.z = el.__z; man.shapes.push(bar); });
        }
        if (el.hasAttribute('data-block')) return;
        walk(el);
      });
    })(stage);
    // image layer (photos, vector logos, inline svg icons)
    Array.prototype.forEach.call(stage.querySelectorAll('img'), function (im) {
      if (im.closest('[data-chart]') || !im.src) return;
      var b = _mBox(im, sr, sc); if (b.w < 6 || b.h < 6) return;
      var data = im.__flatURI || im.src;   // flattened photo+scrim composite when one was baked
      // object-fit:cover -> crop to the box aspect (honouring object-position) so the PPTX shows
      // the same crop as the HTML instead of stretching the full image (headshots, content photos).
      if (!im.__flatURI && getComputedStyle(im).objectFit === 'cover') {
        var cropped = _coverCrop(im, b, getComputedStyle(im));
        if (cropped) data = cropped;
      }
      // python-pptx add_picture cannot embed SVG — rasterize SVG-sourced imgs (e.g. the
      // brand logo <img data-logo>) to PNG via canvas (the img is already loaded).
      if (/^data:image\/svg/i.test(data)) {
        try {
          var c = document.createElement('canvas');
          c.width = Math.max(2, Math.round(b.w * 3)); c.height = Math.max(2, Math.round(b.h * 3));
          c.getContext('2d').drawImage(im, 0, 0, c.width, c.height);
          data = c.toDataURL('image/png');
        } catch (e) { return; }
      }
      man.images.push({ box: b, data: data, z: im.__z });
    });
    var svgs = Array.prototype.slice.call(stage.querySelectorAll('svg')).filter(function (svg) {
      if (svg.closest('[data-chart]')) return false;
      var b = _mBox(svg, sr, sc); return b.w >= 6 && b.h >= 6;   // keep small icons (px, not in)
    });
    for (var si = 0; si < svgs.length; si++) {
      var sb = _mBox(svgs[si], sr, sc);
      var png = await _svgToPng(svgs[si], sb, sc);
      if (png) man.images.push({ box: sb, data: png, z: svgs[si].__z });
    }
    // native charts
    Array.prototype.slice.call(stage.querySelectorAll('[data-chart]')).forEach(function (el) {
      try { man.charts.push({ box: _mBox(el, sr, sc), spec: JSON.parse(el.getAttribute('data-chart')) }); } catch (e) {}
    });
    // text layer (data-blocks), skipping any promoted into a shape
    Array.prototype.slice.call(stage.querySelectorAll('[data-block]'))
      .filter(function (el) { return (el.innerText || '').trim() && !el.closest('[data-chart]'); })
      .forEach(function (el) {
        if (inShape[el.getAttribute('data-block')]) return;
        var cs = getComputedStyle(el);
        man.texts.push({ box: _mContentBox(el, sr, sc), runs: _mRuns(el, cs), align: _mAlign(cs),
          lineHeight: /px$/.test(cs.lineHeight) ? parseFloat(cs.lineHeight) : null });
      });
    // orphan-text safety net (never drop a visible word)
    (function walkOrphan(node) {
      Array.prototype.forEach.call(node.children, function (el) {
        var cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return;
        var tag = el.tagName.toUpperCase();
        if (tag === 'IMG' || tag === 'SVG') return;
        if (el.hasAttribute('data-chart') || el.hasAttribute('data-block')) return;
        if (el.getAttribute('data-inshape')) return;   // already centred inside its badge shape
        if (el.classList && (el.classList.contains('sb-page-num') || el.classList.contains('sb-footer-logo')
            || el.classList.contains('sb-watermark') || el.classList.contains('sb-stage-badge')
            || el.classList.contains('sb-review-chip'))) return;
        if (el.querySelector('[data-block]')) { walkOrphan(el); return; }
        if (isTextUnit(el)) {
          man.texts.push({ box: _mContentBox(el, sr, sc), runs: _mRuns(el, cs), align: _mAlign(cs), lineHeight: null });
          return;
        }
        walkOrphan(el);
      });
    })(stage);
    // page-number chrome (as a real text box so the census matches the HTML)
    var pn = stage.querySelector('.sb-page-num');
    if (pn && (pn.innerText || '').trim()) {
      man.pageNum = { box: _mBox(pn, sr, sc), text: pn.innerText.trim(),
                      color: cssColorToHex(getComputedStyle(pn).color), size: parseFloat(getComputedStyle(pn).fontSize) };
    }
    return man;
  }
  window.__exportManifest = async function () {
    var LOGW = 1280, stages = eachStage(), out = [];
    for (var i = 0; i < stages.length; i++) {
      var stage = stages[i], slSec = stage.closest('.slide');
      if (slSec && slSec.hasAttribute('data-reference')) continue;   // engine copies these natively
      // Force EVERY reveal variant to its FINAL visible state INSTANTLY before the shape walk.
      // Two bugs fixed: (1) only .reveal (not -scale/-left/-right/-hero) was revealed; (2) the
      // .visible opacity is a 0.7s TRANSITION, so reading it immediately gave opacity:0 and the
      // walk dropped those elements — losing colour-block panels/cards. transition:none snaps it.
      stage.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale, .reveal-hero')
        .forEach(function (el) { el.classList.add('visible'); el.style.transition = 'none'; });
      try { contrastForStage(stage); } catch (e) {}
      var sr = stage.getBoundingClientRect(), sc = sr.width / LOGW;
      out.push(await _manifestForStage(stage, sr, sc));
    }
    return out;
  };

  /* PPTX export (Track D): the browser NO LONGER builds a .pptx. The official exporter is
     engine/export_pptx.py — it copies reference slides natively from the source deck and
     reconstructs authored slides from window.__exportManifest(), producing fully-native,
     movable objects. The in-deck button therefore either hands over the engine-produced
     artifact (if the EXPORT pass embedded one as window.__ENGINE_PPTX__ = {name, dataUri})
     or directs the user to run the EXPORT pass. No second, lower-quality exporter ships. */
  function exportPPTX() {
    var art = window.__ENGINE_PPTX__;
    if (art && art.dataUri) {
      var a = document.createElement('a');
      a.href = art.dataUri; a.download = art.name || ((window.__DECK__.title || 'deck') + '.pptx');
      a.click();
      return;
    }
    var o = $('export-overlay'), m = $('export-msg'), fl = $('export-fill');
    if (o && m) {
      if (fl) fl.style.width = '100%';
      o.classList.add('visible');
      m.innerHTML = 'PowerPoint is produced by the engine EXPORT pass, not the browser — ' +
        'it copies every reference slide natively and rebuilds authored slides as movable ' +
        'objects.<br><br>Run:<br><code>python engine/export_pptx.py --skill-path . ' +
        '--plan &lt;plan.json&gt; --slides-html &lt;out/presentation.html&gt; --out &lt;deck.pptx&gt;</code>' +
        '<br><br>(click anywhere to dismiss)';
      var dismiss = function () { o.classList.remove('visible'); document.removeEventListener('click', dismiss); };
      setTimeout(function () { document.addEventListener('click', dismiss); }, 50);
    } else {
      alert('PowerPoint export is produced by the engine EXPORT pass: ' +
            'python engine/export_pptx.py --plan <plan.json> --slides-html <out/presentation.html> --out <deck.pptx>');
    }
  }

  /* ============================================================
     SLIDE BOARD + PER-SLIDE LIGHT/DARK  (review mode only)
     Two review affordances that RECORD decisions and round-trip them to Claude
     via the copy payload (never edit slide content here):
       1. Per-slide light/dark: each reference slide bakes BOTH a .ref-light and
          .ref-dark render. An inline ☀/☾ toggle (top-left of each stage) and the
          board's Light/Dark segment pin ONE as that slide's "main" version,
          overriding the global theme for that slide (data-variant on the .slide).
       2. Slide Board (▤ / press B): all slides as thumbnails in parallel — drag
          to reorder, ✕ to remove (↺ to restore), Light/Dark per card. Clicking a
          thumbnail jumps into the live deck at that slide, in edit mode, ready to
          pin. Decisions persist to localStorage and are emitted as a plan spec.
     ORDER + VARIANT + DELETION are layered together onto the LIVE scrolling deck:
     the deck is physically reordered, deleted slides drop out of the flow, and the
     visible-slide index + nav dots are rebuilt so pin s#, keyboard nav, and dots
     all track the NEW order — so you can reorder, delete, then scroll the live deck
     in the new order and drop slide-level feedback that lands in the right place.
     Also available inline on every stage in edit mode: ☀/☾ variant + 🗑 delete.
  ============================================================ */
  (function initBoard() {
    if (MODE !== 'review') return;
    var boardEl = $('slide-board'), gridEl = $('board-grid'), subEl = $('board-sub');
    var parkedEl = $('board-parked');
    var toggleBtn = $('board-toggle');
    if (!boardEl || !gridEl) return;

    var META = slides.map(function (sl, i) {
      return { uuid: sl.getAttribute('data-slide'), topic: sl.getAttribute('data-topic') || ('Slide ' + (i + 1)), el: sl };
    });
    var byUuid = {}; META.forEach(function (m) { byUuid[m.uuid] = m; });
    var ORIG_ORDER = META.map(function (m) { return m.uuid; });
    var LS_KEY = 'sbdeck:board:' + ((window.__DECK__ && window.__DECK__.title) || 'deck');

    var state = { order: ORIG_ORDER.slice(), removed: {}, variants: {} };
    function defaultVariant() { return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'; }
    function resolvedVariant(uuid) { return state.variants[uuid] || defaultVariant(); }

    // Baked baseline: build emits window.__VARIANTS__ from slide.variant_choice already
    // applied to the deck. Seed state from it AND keep it as the baseline so "changes"
    // are measured against what's baked in, not against empty (else a fresh rebuilt deck
    // would falsely report every already-applied choice as a pending change).
    var planVars = window.__VARIANTS__ || {};
    var BASE_VARIANTS = {};
    Object.keys(planVars).forEach(function (u) { if (byUuid[u]) { state.variants[u] = planVars[u]; BASE_VARIANTS[u] = planVars[u]; } });

    // Placeholder / "Not used" baseline: the build marks any spare slide with
    // data-placeholder; it starts parked in the Not-used section by default (that IS
    // the baseline, so a fresh deck with a spare doesn't read as a pending change).
    var BASE_REMOVED = {};
    META.forEach(function (m) {
      m.placeholder = m.el.hasAttribute('data-placeholder');
      if (m.placeholder) { state.removed[m.uuid] = true; BASE_REMOVED[m.uuid] = true; }
    });

    function load() {
      try {
        var raw = localStorage.getItem(LS_KEY); if (!raw) return;
        var s = JSON.parse(raw);
        // Saved board state is tied to the plan revision it was made against. Once a
        // rebuild bakes those decisions in (revision bumps), the old state is stale —
        // discard it so the rebuilt deck starts clean from the new baked baseline.
        if (!s || s.rev !== PLAN_REV) { localStorage.removeItem(LS_KEY); return; }
        var savedOrder = (s && Array.isArray(s.order)) ? s.order : [];
        if (savedOrder.length) {
          var known = savedOrder.filter(function (u) { return byUuid[u]; });
          ORIG_ORDER.forEach(function (u) { if (known.indexOf(u) < 0) known.push(u); });   // new slides append
          state.order = known;
        }
        if (s && s.removed) state.removed = s.removed;
        if (s && s.variants) state.variants = s.variants;
        // A placeholder that didn't exist when this state was saved must stay parked
        // (otherwise a spare slide added by a newer build could leak into the deck).
        Object.keys(BASE_REMOVED).forEach(function (u) { if (savedOrder.indexOf(u) < 0) state.removed[u] = true; });
      } catch (e) {}
    }
    function save() {
      try { localStorage.setItem(LS_KEY, JSON.stringify({ rev: PLAN_REV, order: state.order, removed: state.removed, variants: state.variants })); } catch (e) {}
      scheduleBoardSave();   // live-edit mode: also persist the layout decision to disk (debounced)
    }

    /* ---- Board autosave to disk (localhost editor only) --------------------------------
       Reorder / remove / light-dark autosave into plan.json (order = array order,
       remove = slide.status "deleted", variant = slide.variant_choice) and the deck is
       rebuilt so review.html + presentation.html match the board — the file always reflects
       what you did. Adding the spare slide is NOT content, so it can't be baked: it's recorded
       as an authoring request (authoring-requests.json) for Claude to fulfil. Debounced so a
       burst of drags triggers ONE rebuild. ------------------------------------------------ */
    var bToastEl = null, bToastT = null;
    function boardToast(msg, kind, ms) {
      if (!bToastEl) {
        bToastEl = document.createElement('div');
        // z-index 950: ABOVE the Slide Board overlay (900) so the toast is visible while the
        // board is open (adding the spare happens with the board open), below export (1000).
        bToastEl.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(8px);' +
          'z-index:950;padding:9px 16px;border-radius:999px;font:700 12px Montserrat,system-ui,sans-serif;' +
          'letter-spacing:.02em;color:#fff;background:#0d1829;border:1px solid rgba(255,255,255,.14);' +
          'box-shadow:0 6px 20px rgba(0,0,0,.4);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s';
        document.body.appendChild(bToastEl);
      }
      bToastEl.textContent = msg;
      bToastEl.style.background = kind === 'err' ? '#7a1533' : (kind === 'saved' ? '#0b6e4f' : '#0d1829');
      bToastEl.style.opacity = '1'; bToastEl.style.transform = 'translateX(-50%) translateY(0)';
      clearTimeout(bToastT);
      bToastT = setTimeout(function () { bToastEl.style.opacity = '0'; bToastEl.style.transform = 'translateX(-50%) translateY(8px)'; }, ms || 2200);
    }
    function boardSavePayload() {
      var active = [], addReqs = [], lastReal = null;
      state.order.forEach(function (u) {
        if (state.removed[u]) return;                                   // parked → not in deck
        var m = byUuid[u];
        if (m && m.placeholder) { addReqs.push({ after: lastReal, topic: m.topic }); return; }  // spare = authoring request
        active.push(u); lastReal = u;
      });
      var removed = Object.keys(state.removed).filter(function (u) {
        return state.removed[u] && !(byUuid[u] && byUuid[u].placeholder);
      });
      var variants = {};
      Object.keys(state.variants).forEach(function (u) {
        if (byUuid[u] && !byUuid[u].placeholder) variants[u] = state.variants[u];
      });
      return { rev: PLAN_REV, active: active, removed: removed, variants: variants, add_requests: addReqs };
    }
    var boardSaveT = null, lastBoardJSON = JSON.stringify(boardSavePayload());  // seed = baseline (no initial POST)
    function scheduleBoardSave() {
      if (!SERVED) return;                       // file view has no board anyway; belt-and-suspenders
      clearTimeout(boardSaveT);
      boardSaveT = setTimeout(boardAutosave, 900);
    }
    function boardAutosave() {
      var js = JSON.stringify(boardSavePayload());
      if (js === lastBoardJSON) return;          // nothing changed since the last write
      lastBoardJSON = js;
      boardToast('Saving layout…');
      fetch('/save-board', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: js })
        .then(function (r) {
          if (r.status === 409) {           // plan moved on (e.g. a slide was added) → reload to resync
            boardToast('Deck changed — refreshing…', 'saved', 3000);
            setTimeout(function () { location.reload(); }, 900);
            return null;
          }
          return r.json().catch(function () { return { ok: false, msg: 'bad response' }; });
        })
        .then(function (j) {
          if (!j) return;
          if (j.ok) {
            if (j.reload) {
              // a real blank slide was minted into the deck; reload to show it live (the DOM
              // can't render a slide it doesn't have HTML for) and pick up the fresh spare.
              boardToast('Blank slide added ✓ — refreshing to show it…', 'saved', 3000);
              setTimeout(function () { location.reload(); }, 950);
            } else {
              boardToast('Layout saved ✓ — file updated', 'saved');
            }
          } else boardToast((j && j.msg) || 'Save failed', 'err');
        })
        .catch(function () { boardToast('Could not reach the edit server', 'err'); });
    }

    // ---- apply LIGHT/DARK choice to every slide (cheap; no reflow of order) ----
    function applyVariants() {
      META.forEach(function (m) {
        if (state.variants[m.uuid]) m.el.setAttribute('data-variant', state.variants[m.uuid]);
        else m.el.removeAttribute('data-variant');
      });
      try { recomputeAllContrast(); } catch (e) {}
    }
    // ---- reflect ORDER + DELETIONS in the LIVE scrolling deck, then rebuild the
    //      visible-slide index + nav dots so pin s#, keyboard nav, and dots all
    //      track the NEW order. Reorder is skipped when the DOM already matches
    //      (so a variant/delete toggle doesn't needlessly reflow the big slides). ----
    function currentDomOrder() {
      return Array.prototype.slice.call(document.querySelectorAll('.slide'))
        .map(function (el) { return el.getAttribute('data-slide'); }).join(',');
    }
    function applyOrderAndVisibility() {
      var parent = META.length ? META[0].el.parentNode : null;
      if (parent && currentDomOrder() !== state.order.join(',')) {
        state.order.forEach(function (u) { var m = byUuid[u]; if (m) parent.appendChild(m.el); });
      }
      META.forEach(function (m) { m.el.classList.toggle('board-hidden', !!state.removed[m.uuid]); });
      slides = state.order.filter(function (u) { return !state.removed[u]; }).map(function (u) { return byUuid[u].el; });
      buildNavDots();
      try { recomputeAllContrast(); } catch (e) {}
    }

    function orderChanged() {
      if (state.order.length !== ORIG_ORDER.length) return true;
      for (var i = 0; i < state.order.length; i++) if (state.order[i] !== ORIG_ORDER[i]) return true;
      return false;
    }
    function removedSet() { return Object.keys(state.removed).filter(function (u) { return state.removed[u]; }); }
    function removedChanged() {
      var a = removedSet().sort(), b = Object.keys(BASE_REMOVED).sort();
      if (a.length !== b.length) return true;
      for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return true;
      return false;
    }
    function variantsChanged() {
      var a = state.variants, b = BASE_VARIANTS, ak = Object.keys(a), bk = Object.keys(b);
      if (ak.length !== bk.length) return true;
      for (var i = 0; i < ak.length; i++) { if (a[ak[i]] !== b[ak[i]]) return true; }
      return false;
    }
    function hasChanges() { return orderChanged() || removedChanged() || variantsChanged(); }

    function setVariant(uuid, v) {
      state.variants[uuid] = v;
      if (byUuid[uuid]) byUuid[uuid].el.setAttribute('data-variant', v);
      try { recomputeAllContrast(); } catch (e) {}
      save(); syncInlineToggles();
      if (boardEl.classList.contains('open')) render();
      refreshCopyState();
    }
    function setRemoved(uuid, val) {
      if (val) state.removed[uuid] = true; else delete state.removed[uuid];
      save(); applyOrderAndVisibility();
      if (boardEl.classList.contains('open')) render();
      refreshCopyState();
    }

    /* ---- inline per-slide ☀/☾ toggle on every stage (visible in edit mode) ---- */
    var inlineToggles = {};
    function buildInlineToggles() {
      META.forEach(function (m) {
        var stage = m.el.querySelector('.stage'); if (!stage) return;
        var wrap = document.createElement('div'); wrap.className = 'sb-vtoggle';
        ['light', 'dark'].forEach(function (v) {
          var b = document.createElement('button'); b.type = 'button';
          b.textContent = v === 'light' ? '☀ Light' : '☾ Dark';
          b.setAttribute('data-variant-set', v);
          b.addEventListener('click', function (e) { e.stopPropagation(); setVariant(m.uuid, v); });
          wrap.appendChild(b);
        });
        stage.appendChild(wrap);
        inlineToggles[m.uuid] = wrap;
        // delete-this-slide button (top-right); slide drops out of the live flow
        var del = document.createElement('button'); del.type = 'button'; del.className = 'sb-delbtn';
        del.textContent = '🗑'; del.title = 'Delete this slide from the deck (restore via the Slide Board)';
        del.addEventListener('click', function (e) { e.stopPropagation(); setRemoved(m.uuid, true); });
        stage.appendChild(del);
      });
      syncInlineToggles();
    }
    function syncInlineToggles() {
      Object.keys(inlineToggles).forEach(function (u) {
        var rv = resolvedVariant(u);
        Array.prototype.forEach.call(inlineToggles[u].children, function (b) {
          b.classList.toggle('active', b.getAttribute('data-variant-set') === rv);
        });
      });
    }

    /* ---- board grid ---- */
    function thumbClone(m) {
      var stage = m.el.querySelector('.stage'); if (!stage) return null;
      var wrap = document.createElement('div'); wrap.className = 'board-thumb';
      wrap.setAttribute('data-variant', resolvedVariant(m.uuid));
      var clone = stage.cloneNode(true);
      Array.prototype.forEach.call(clone.querySelectorAll('.ann-pin, .sb-vtoggle'), function (e) { e.remove(); });
      // Force scroll-reveal content to its FINAL visible state in the thumbnail — the board's
      // clone never triggers the IntersectionObserver, so without this every .reveal* element
      // (i.e. all the slide text) sits at opacity:0 and the thumb looks blank.
      Array.prototype.forEach.call(
        clone.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale, .reveal-hero'),
        function (e) { e.classList.add('visible'); e.style.transition = 'none'; });
      clone.style.transform = 'none'; clone.style.margin = '0';
      wrap.appendChild(clone);
      return wrap;
    }
    function scaleThumbs() {
      Array.prototype.forEach.call(boardEl.querySelectorAll('.board-thumbwrap'), function (tw) {
        var thumb = tw.querySelector('.board-thumb'); if (!thumb) return;
        thumb.style.transform = 'scale(' + (tw.clientWidth / 1280) + ')';
      });
    }

    // Build one card. `number` is the deck position (null for parked); `parked` = in Not-used.
    function buildCard(uuid, number, parked) {
      var m = byUuid[uuid];
      var card = document.createElement('div');
      card.className = 'board-card' + (parked ? ' is-parked' : '');
      card.setAttribute('draggable', 'true'); card.setAttribute('data-uuid', uuid);
      card.setAttribute('data-parked', parked ? '1' : '0');

      var tw = document.createElement('div'); tw.className = 'board-thumbwrap';
      var badge = document.createElement('div'); badge.className = 'board-badge';
      badge.textContent = parked ? '—' : String(number);
      tw.appendChild(badge);
      var th = thumbClone(m); if (th) tw.appendChild(th);
      // ✕ move to Not used  /  ↺ add back to deck — the primary remove affordance
      var del = document.createElement('button'); del.type = 'button';
      del.className = 'board-del' + (parked ? ' is-restore' : '');
      del.textContent = parked ? '↺' : '✕';
      del.title = parked ? 'Add this slide back into the deck' : 'Move this slide to Not used (remove from deck)';
      del.addEventListener('click', function (e) { e.stopPropagation(); setRemoved(uuid, !parked); });
      tw.appendChild(del);
      // light/dark switch (bottom-right), shows + flips the current main version in place
      var mode = document.createElement('div'); mode.className = 'board-mode';
      [['light', '☀', 'Light version'], ['dark', '☾', 'Dark version']].forEach(function (cfg) {
        var b = document.createElement('button'); b.type = 'button'; b.textContent = cfg[1]; b.title = cfg[2];
        if (resolvedVariant(uuid) === cfg[0]) b.classList.add('active');
        b.addEventListener('click', function (e) { e.stopPropagation(); setVariant(uuid, cfg[0]); });
        mode.appendChild(b);
      });
      tw.appendChild(mode);
      // click a thumbnail → jump into the LIVE deck at that slide (in-deck cards only)
      tw.addEventListener('click', function () {
        if (parked) return;
        closeBoard(); enterEdit();
        var el = byUuid[uuid] && byUuid[uuid].el;
        if (el) el.scrollIntoView({ behavior: 'instant' });
      });
      card.appendChild(tw);

      var foot = document.createElement('div'); foot.className = 'board-foot';
      var topic = document.createElement('span'); topic.className = 'board-topic';
      topic.textContent = m.topic + (m.placeholder ? ' (spare)' : ''); topic.title = m.topic;
      foot.appendChild(topic);
      card.appendChild(foot);

      wireDrag(card);
      return card;
    }

    function render() {
      gridEl.innerHTML = ''; if (parkedEl) parkedEl.innerHTML = '';
      var active = state.order.filter(function (u) { return !state.removed[u]; });
      var parked = state.order.filter(function (u) { return state.removed[u]; });
      if (subEl) subEl.textContent = active.length + ' in deck' +
        (parked.length ? ' · ' + parked.length + ' not used' : '') + (orderChanged() ? ' · reordered' : '');
      active.forEach(function (uuid, i) { gridEl.appendChild(buildCard(uuid, i + 1, false)); });
      if (parkedEl) {
        if (!parked.length) {
          var empty = document.createElement('div'); empty.className = 'board-parked-empty';
          empty.textContent = 'Nothing here. Drag a slide down (or hit ✕) to take it out of the deck without deleting it.';
          parkedEl.appendChild(empty);
        } else {
          parked.forEach(function (uuid) { parkedEl.appendChild(buildCard(uuid, null, true)); });
        }
      }
      requestAnimationFrame(scaleThumbs);
    }

    // Move `u` next to `targetUuid` (before/after) and set its parked state. Single
    // ordered list; the removed flag decides which zone a slide shows in.
    function applyDrop(u, targetUuid, after, parked) {
      if (parked) state.removed[u] = true; else delete state.removed[u];
      var arr = state.order.slice();
      var from = arr.indexOf(u); if (from >= 0) arr.splice(from, 1);
      var to = targetUuid ? arr.indexOf(targetUuid) : arr.length;
      if (to < 0) to = arr.length; else if (after) to += 1;
      arr.splice(to, 0, u);
      state.order = arr;
      save(); applyOrderAndVisibility(); render(); refreshCopyState();
    }
    function clearDropCues() {
      Array.prototype.forEach.call(boardEl.querySelectorAll('.drop-before,.drop-after'), function (c) { c.classList.remove('drop-before', 'drop-after'); });
      Array.prototype.forEach.call(boardEl.querySelectorAll('.drop-zone-active'), function (z) { z.classList.remove('drop-zone-active'); });
    }

    var dragUuid = null;
    function wireDrag(card) {
      card.addEventListener('dragstart', function (e) {
        dragUuid = card.getAttribute('data-uuid'); card.classList.add('dragging');
        try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', dragUuid); } catch (x) {}
      });
      card.addEventListener('dragend', function () { dragUuid = null; card.classList.remove('dragging'); clearDropCues(); });
      card.addEventListener('dragover', function (e) {
        if (!dragUuid || card.getAttribute('data-uuid') === dragUuid) return; e.preventDefault(); e.stopPropagation();
        var r = card.getBoundingClientRect(), after = (e.clientX - r.left) > r.width / 2;
        card.classList.toggle('drop-after', after); card.classList.toggle('drop-before', !after);
      });
      card.addEventListener('dragleave', function () { card.classList.remove('drop-before', 'drop-after'); });
      card.addEventListener('drop', function (e) {
        e.preventDefault(); e.stopPropagation(); if (!dragUuid) return;
        var targetUuid = card.getAttribute('data-uuid');
        var parked = card.getAttribute('data-parked') === '1';
        if (targetUuid !== dragUuid) {
          var r = card.getBoundingClientRect(), after = (e.clientX - r.left) > r.width / 2;
          applyDrop(dragUuid, targetUuid, after, parked);
        } else { render(); }
      });
    }
    // Dropping onto a zone's empty space (or the parked drop-target) — set parked by zone.
    function wireZone(zoneEl, parked) {
      if (!zoneEl) return;
      zoneEl.addEventListener('dragover', function (e) { if (!dragUuid) return; e.preventDefault(); zoneEl.classList.add('drop-zone-active'); });
      zoneEl.addEventListener('dragleave', function (e) { if (e.target === zoneEl) zoneEl.classList.remove('drop-zone-active'); });
      zoneEl.addEventListener('drop', function (e) {
        if (!dragUuid) return; e.preventDefault();
        applyDrop(dragUuid, null, false, parked);   // append to end of that zone
      });
    }

    function payloadText() {
      var keptOrder = state.order.filter(function (u) { return !state.removed[u]; });
      var removedReal = state.order.filter(function (u) { return state.removed[u] && !(byUuid[u] && byUuid[u].placeholder); });
      var varKeys = Object.keys(state.variants);
      var out = 'DECK LAYOUT & VARIANT DECISIONS — apply to plan.json. Surgical: change ONLY slide order, inclusion, and per-slide variant. Do not edit slide content.\n';
      out += '# ' + keptOrder.length + ' slide(s) in deck' + (removedReal.length ? ', ' + removedReal.length + ' moved to Not used' : '') +
             (orderChanged() ? ', order changed' : ', order unchanged') + ' · plan_revision ' + PLAN_REV + '\n\n';
      out += 'FINAL SLIDE ORDER (top → bottom, keep in this sequence):\n';
      keptOrder.forEach(function (u, i) {
        var ph = byUuid[u] && byUuid[u].placeholder;
        out += ' ' + (i + 1) + '. [slide ' + u + '] ' + (byUuid[u] ? byUuid[u].topic : '') +
               (ph ? '  ← NEW blank slide inserted here (author content for it)' : '') +
               ' → ' + resolvedVariant(u).toUpperCase() + '\n';
      });
      if (removedReal.length) {
        out += '\nNOT USED (remove these slides from the deck):\n';
        removedReal.forEach(function (u) { out += ' - [slide ' + u + '] ' + (byUuid[u] ? byUuid[u].topic : '') + '\n'; });
      }
      if (varKeys.length) {
        out += '\nEXPLICIT LIGHT/DARK CHOICES (record as the main version — set slide.variant_choice):\n';
        varKeys.forEach(function (u) { out += ' - [slide ' + u + '] ' + (byUuid[u] ? byUuid[u].topic : '') + ' → ' + state.variants[u].toUpperCase() + '\n'; });
        out += '(Slides without an explicit choice follow the deck default theme: ' + defaultVariant().toUpperCase() + '.)\n';
      }
      return out;
    }

    function openBoard() { render(); boardEl.classList.add('open'); }
    function closeBoard() { boardEl.classList.remove('open'); gridEl.innerHTML = ''; if (parkedEl) parkedEl.innerHTML = ''; }   // free cloned thumbs
    function toggleBoard() { boardEl.classList.contains('open') ? closeBoard() : openBoard(); }

    if (toggleBtn) toggleBtn.addEventListener('click', toggleBoard);
    var closeBtn = $('board-close'); if (closeBtn) closeBtn.addEventListener('click', closeBoard);
    var resetBtn = $('board-reset');
    if (resetBtn) resetBtn.addEventListener('click', function () {
      // discard board changes → back to the baked baseline (placeholder parked, baked variants)
      state = { order: ORIG_ORDER.slice(), removed: {}, variants: {} };
      Object.keys(BASE_REMOVED).forEach(function (u) { state.removed[u] = true; });
      Object.keys(BASE_VARIANTS).forEach(function (u) { state.variants[u] = BASE_VARIANTS[u]; });
      save(); applyVariants(); applyOrderAndVisibility(); syncInlineToggles(); render(); refreshCopyState();
    });
    var bCopy = $('board-copy');
    if (bCopy) bCopy.addEventListener('click', function () {
      if (!hasChanges()) { flashCopyConfirm('No board changes yet'); return; }
      navigator.clipboard.writeText(payloadText() + '\n').then(function () {
        var orig = bCopy.textContent; bCopy.textContent = '✓ Copied';
        setTimeout(function () { bCopy.textContent = orig; }, 1800);
      });
    });
    document.addEventListener('keydown', function (e) {
      if (['INPUT', 'TEXTAREA'].indexOf(e.target.tagName) >= 0 || e.target.isContentEditable) return;
      if (e.key === 'b' || e.key === 'B') { e.preventDefault(); toggleBoard(); }
      else if (e.key === 'Escape' && boardEl.classList.contains('open')) closeBoard();
    });
    window.addEventListener('resize', function () { if (boardEl.classList.contains('open')) scaleThumbs(); });

    window.__BOARD_API__ = { hasChanges: hasChanges, payloadText: payloadText };

    wireZone(gridEl, false);      // drop here → In deck
    wireZone(parkedEl, true);     // drop here → Not used
    load();
    buildInlineToggles();
    applyVariants();
    applyOrderAndVisibility();
    refreshCopyState();
  })();

  /* ============================================================
     DIRECT TEXT EDIT  (review mode only)
     Type directly on the slide. Toggle with the T button. Editable ONLY on authored
     slides (verbatim/reference slides are image-locked — pin those instead). Each edit
     is captured block-precise, persists (localStorage, plan-revision guarded), and
     round-trips inside "Copy All Notes to Claude" as a DIRECT TEXT EDITS block that
     Claude applies verbatim to plan.json.
  ============================================================ */
  (function initTextEdit() {
    if (MODE !== 'review') return;
    var btn = $('text-toggle'); if (!btn) return;
    // Live-edit autosave: only when the deck is SERVED (http/localhost via `open_deck.py
    // --edit`), never from a plain file:// page (a sandboxed file can't write to disk).
    // Defined FIRST so the title logic below sees its real value (var-hoisting would
    // otherwise leave it undefined here and the file-view title would always apply).
    // Aliased to the deck-wide SERVED signal (top of file) so there is ONE source of truth
    // for "am I the localhost editor or a plain file?" — tools can't leak onto the file view.
    var CAN_SAVE = SERVED;
    var EDIT_URL = (window.__EDIT_URL__ || 'http://127.0.0.1:8770/review.html');
    // On the read-only file:// view the T tool can't save (a sandboxed file can't be
    // written). Instead it OPENS the editable localhost version in a tab beside this one,
    // so you can edit there and cross-reference the saved file here.
    if (!CAN_SAVE) {
      // On the read-only file view this is NOT the text editor - it's the button that
      // OPENS the editable localhost version (where you then click T to edit). Make it
      // look distinct from the in-editor "T": a pop-out glyph + its own tooltip.
      btn.textContent = '↗';   // ↗ open-in-new-tab
      btn.title = 'Open editable version (localhost) - then click T there to edit';
      btn.setAttribute('data-tip', btn.title);
    }
    var LS = 'sbdeck:textedits:' + ((window.__DECK__ && window.__DECK__.title) || 'deck');
    var edits = {};      // block_uuid -> {slide_uuid, slide_topic, old, new}
    var baseline = {};   // block_uuid -> original text (pre-edit)

    function norm(s) { return (s || '').replace(/\s+/g, ' ').trim(); }

    // Small autosave status toast (bottom-centre), only shown in live-edit mode.
    var toastEl = null, toastT = null;
    function toast(msg, kind) {
      if (!toastEl) {
        toastEl = document.createElement('div');
        toastEl.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(8px);' +
          'z-index:700;padding:9px 16px;border-radius:999px;font:700 12px Montserrat,system-ui,sans-serif;' +
          'letter-spacing:.02em;color:#fff;background:#0d1829;border:1px solid rgba(255,255,255,.14);' +
          'box-shadow:0 6px 20px rgba(0,0,0,.4);opacity:0;pointer-events:none;transition:opacity .2s,transform .2s';
        document.body.appendChild(toastEl);
      }
      toastEl.textContent = msg;
      toastEl.style.background = kind === 'err' ? '#7a1533' : (kind === 'saved' ? '#0b6e4f' : '#0d1829');
      toastEl.style.opacity = '1'; toastEl.style.transform = 'translateX(-50%) translateY(0)';
      clearTimeout(toastT);
      toastT = setTimeout(function () { toastEl.style.opacity = '0'; toastEl.style.transform = 'translateX(-50%) translateY(8px)'; }, 1600);
    }

    // Autosave one authored block edit to disk via the edit server (PPT-style persistence).
    // Sends the block's rich innerHTML (bold/italic/underline/colour/line-breaks); the server
    // sanitises it and stores block.text_html + a plain-text fallback. Skips redundant writes.
    var lastSaved = {};
    function autosaveToDisk(el, key) {
      if (!CAN_SAVE || key.charAt(0) !== 'b') return;         // block edits only; ref slides round-trip via notes
      var uuid = el.getAttribute('data-block'); if (!uuid) return;
      var richHtml = el.innerHTML;
      if (lastSaved[key] === richHtml) return;                // nothing changed since last save
      lastSaved[key] = richHtml;
      toast('Saving…');
      fetch('/save-edit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rev: PLAN_REV, kind: 'block', block_uuid: uuid,
                               html: richHtml, text: el.innerText,
                               slide_uuid: (el.closest('.slide') || {}).getAttribute && el.closest('.slide').getAttribute('data-slide') })
      }).then(function (r) {
        if (r.status === 409) { toast('Deck changed — reload', 'err'); return; }
        return r.json();
      }).then(function (j) {
        if (j && j.ok) toast('Saved ✓', 'saved');
        else if (j) toast('Not saved', 'err');
      }).catch(function () { toast('Save failed', 'err'); });
    }

    // Build the full editable set and STAMP each element with a stable data-te key.
    //  - authored blocks:  key "b:<block_uuid>"        (applies to plan.json block text)
    //  - approved/reference leaf text: key "r:<ref_id>:<variant>:<idx>"  (ADAPTS the slide)
    function editableEls() {
      var out = [];
      Array.prototype.slice.call(document.querySelectorAll('.slide:not([data-reference]) [data-block]')).forEach(function (el) {
        if (el.getAttribute('data-block-type') === 'icon') return;
        if (!(el.textContent || '').trim()) return;
        if (!isTextUnit(el)) return;
        if (!el.dataset.te) el.dataset.te = 'b:' + el.getAttribute('data-block');
        out.push(el);
      });
      var TEXT_TAGS = { SPAN: 1, P: 1, DIV: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, LI: 1, TD: 1,
                        TH: 1, A: 1, STRONG: 1, EM: 1, B: 1, I: 1, LABEL: 1, FIGCAPTION: 1, SMALL: 1, BLOCKQUOTE: 1 };
      Array.prototype.slice.call(document.querySelectorAll('.slide[data-reference]')).forEach(function (sec) {
        var ref = sec.getAttribute('data-reference');
        Array.prototype.slice.call(sec.querySelectorAll('.ref-variant')).forEach(function (v) {
          var variant = v.classList.contains('ref-dark') ? 'dark' : 'light', idx = 0;
          Array.prototype.slice.call(v.querySelectorAll('*')).forEach(function (el) {
            if (el.childElementCount !== 0) return;                       // leaf text only
            if (el.closest('svg')) return;                               // SVG internals aren't slide text
            if (!TEXT_TAGS[el.tagName.toUpperCase()]) return;            // only real HTML text holders
            if (!(el.textContent || '').trim()) return;
            if (!el.dataset.te) el.dataset.te = 'r:' + ref + ':' + variant + ':' + idx;
            idx++; out.push(el);
          });
        });
      });
      return out;
    }

    function load() {
      try {
        var raw = localStorage.getItem(LS); if (!raw) return;
        var s = JSON.parse(raw);
        if (!s || s.rev !== PLAN_REV) { localStorage.removeItem(LS); return; }
        edits = s.edits || {};
      } catch (e) {}
    }
    function save() { try { localStorage.setItem(LS, JSON.stringify({ rev: PLAN_REV, edits: edits })); } catch (e) {} }

    function applyEdits() {   // reflect persisted edits into the DOM (by stamped key)
      Object.keys(edits).forEach(function (key) {
        var el = document.querySelector('[data-te="' + key.replace(/"/g, '\\"') + '"]');
        if (el && el.childElementCount === 0) el.textContent = edits[key].new;
      });
    }
    function record(el) {
      var key = el.dataset.te; if (!key) return;
      var val = norm(el.innerText), base = (key in baseline) ? baseline[key] : val;
      if (val === base) { delete edits[key]; }
      else {
        var slide = el.closest('.slide');
        var e = { slide_uuid: slide ? slide.getAttribute('data-slide') : null,
                  slide_topic: slide ? (slide.getAttribute('data-topic') || '') : '',
                  old: base, new: val };
        if (key.charAt(0) === 'r') {
          var parts = key.split(':'); e.kind = 'ref'; e.ref_id = parts[1]; e.variant = parts[2];
        } else e.kind = 'block';
        edits[key] = e;
      }
      save(); refreshCopyState();
      autosaveToDisk(el, key);   // live-edit mode: persist rich HTML straight to disk (no-op on file://)
    }
    function setEditable(on) {
      editableEls().forEach(function (el) {
        if (on) { el.setAttribute('contenteditable', 'true'); el.setAttribute('spellcheck', 'false'); }
        else el.removeAttribute('contenteditable');
      });
    }
    var wired = false;
    function wireOnce() {
      if (wired) return; wired = true;
      editableEls().forEach(function (el) {
        el.addEventListener('blur', function () { if (document.body.classList.contains('text-edit-mode')) record(el); });
        el.addEventListener('keydown', function (e) {
          // Escape commits (blur). Enter inserts a line break for multi-line rich text
          // (PowerPoint-style); the edit commits when you click away. Enter is handled
          // EXPLICITLY as <br> — the contenteditable default wraps lines in <div>s, which
          // depends on browser quirks and bloats what the sanitiser has to unwrap.
          if (e.key === 'Escape') { e.preventDefault(); el.blur(); }
          else if (e.key === 'Enter') { e.preventDefault(); document.execCommand('insertLineBreak'); }
        });
        el.addEventListener('input', function () { scheduleSave(el); });   // debounced live save while typing
        el.addEventListener('paste', function (e) {
          e.preventDefault();
          var t = ((e.clipboardData || window.clipboardData).getData('text') || '');
          document.execCommand('insertText', false, t);
        });
      });
    }
    function enter() { document.body.classList.add('text-edit-mode'); btn.classList.add('active'); wireOnce(); setEditable(true); }
    function exit() { document.body.classList.remove('text-edit-mode'); btn.classList.remove('active'); setEditable(false); }
    // file:// view → find the LIVE editor before opening anything. The edit server may sit
    // on any port in the 8770+ window (busy ports fall through to the next), and blindly
    // opening a dead or wrong-deck URL is exactly what reads as "the editor is broken".
    // Each candidate port answers /whoami with its deck_title; we open the one serving
    // THIS deck, and if none answers we say how to start it instead of opening a dead tab.
    function probeEditor(port, tries, done) {
      if (tries <= 0) { done(null); return; }
      var ctl = ('AbortController' in window) ? new AbortController() : null;
      var t = setTimeout(function () { if (ctl) ctl.abort(); }, 900);
      fetch('http://127.0.0.1:' + port + '/whoami', { signal: ctl ? ctl.signal : undefined })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          clearTimeout(t);
          var mine = (window.__DECK__ && window.__DECK__.title) || '';
          if (j && j.app === 'sbdeck-edit-server' && (!mine || j.deck_title === mine)) {
            done('http://127.0.0.1:' + port + '/review.html');
          } else {
            probeEditor(port + 1, tries - 1, done);   // an editor, but for another deck
          }
        })
        .catch(function () { clearTimeout(t); probeEditor(port + 1, tries - 1, done); });
    }
    btn.addEventListener('click', function () {
      if (!CAN_SAVE) {                       // file:// view → open the editable tab beside it
        btn.disabled = true;
        probeEditor(8770, 10, function (url) {
          btn.disabled = false;
          if (url) { window.open(url, 'sbdeck-editor'); return; }  // named target: reuses the editor tab
          alert('The live editor is not running.\n\n' +
                'Start it first, then click this button again:\n' +
                '  • double-click "Edit Deck.command" in the deck folder, or\n' +
                '  • run: python engine/open_deck.py --edit --out <deck>/out --plan <deck>/plan.json');
        });
        return;
      }
      document.body.classList.contains('text-edit-mode') ? exit() : enter();
    });

    /* ---- Rich-text format toolbar (bold / italic / underline / brand colour / highlight) ----
       A floating bar appears over any text selection inside an editable block and applies
       inline formatting; each command debounce-saves the block. This is what lets the deck
       replace PowerPoint - artistic emphasis that persists into the file. */
    var saveTimer = null;
    function scheduleSave(el) {
      if (!el || !el.dataset || !el.dataset.te) return;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () { autosaveToDisk(el, el.dataset.te); }, 650);
    }
    function currentEditable() {
      var s = getSelection(); if (!s || !s.rangeCount) return null;
      var n = s.anchorNode; n = (n && n.nodeType === 3) ? n.parentElement : n;
      return (n && n.closest) ? n.closest('[contenteditable="true"][data-te]') : null;
    }
    var fbar = null;
    // B/I/U as clean <b>/<i>/<u> tags (styleWithCSS off); colours as <span style> (on) so the
    // sanitiser keeps them. Colours are BRAND accents (in the token palette + theme-invariant).
    function execTag(c) { document.execCommand('styleWithCSS', false, false); return document.execCommand(c, false, null); }
    function execColor(prop, hex) { document.execCommand('styleWithCSS', false, true); return document.execCommand(prop, false, hex); }
    function afterCmd() { var ed = currentEditable(); if (ed) scheduleSave(ed); positionFormatBar(); }
    function buildFormatBar() {
      fbar = document.createElement('div'); fbar.id = 'sb-format-bar'; fbar.style.display = 'none';
      function keep(b) { b.addEventListener('mousedown', function (e) { e.preventDefault(); }); }   // keep the selection
      function tbtn(inner, title, fn) {
        var b = document.createElement('button'); b.className = 'fb-btn'; b.innerHTML = inner; b.title = title;
        keep(b); b.addEventListener('click', function (e) { e.preventDefault(); fn(); afterCmd(); }); return b;
      }
      function swatch(hex, title, hl) {
        var s = document.createElement('button'); s.className = 'fb-sw' + (hl ? ' fb-hl' : ''); s.title = title; s.style.background = hex; keep(s);
        s.addEventListener('click', function (e) {
          e.preventDefault();
          if (hl) { if (!execColor('hiliteColor', hex)) execColor('backColor', hex); } else execColor('foreColor', hex);
          afterCmd();
        });
        return s;
      }
      fbar.appendChild(tbtn('<b>B</b>', 'Bold', function () { execTag('bold'); }));
      fbar.appendChild(tbtn('<i>I</i>', 'Italic', function () { execTag('italic'); }));
      fbar.appendChild(tbtn('<u>U</u>', 'Underline', function () { execTag('underline'); }));
      var sep = document.createElement('span'); sep.className = 'fb-sep'; fbar.appendChild(sep);
      [['#00B2E3', 'Sky'], ['#E17126', 'Copper'], ['#76A3B2', 'Steel'], ['#ED1651', 'Pink'], ['#005491', 'Navy'], ['#FFFFFF', 'White'], ['#0F1419', 'Ink']]
        .forEach(function (c) { fbar.appendChild(swatch(c[0], 'Text colour: ' + c[1], false)); });
      var sep2 = document.createElement('span'); sep2.className = 'fb-sep'; fbar.appendChild(sep2);
      [['#00B2E3', 'Sky'], ['#ED1651', 'Pink'], ['#E17126', 'Copper']]
        .forEach(function (c) { fbar.appendChild(swatch(c[0], 'Highlight: ' + c[1], true)); });
      var clr = document.createElement('button'); clr.className = 'fb-sw fb-clear'; clr.title = 'Remove highlight'; clr.textContent = '×';
      clr.addEventListener('mousedown', function (e) { e.preventDefault(); });
      clr.addEventListener('click', function (e) { e.preventDefault(); if (!execColor('hiliteColor', 'transparent')) execColor('backColor', 'transparent'); afterCmd(); });
      fbar.appendChild(clr);
      var sep3 = document.createElement('span'); sep3.className = 'fb-sep'; fbar.appendChild(sep3);
      fbar.appendChild(tbtn('T<span style="font-size:9px">✕</span>', 'Clear all formatting', function () { document.execCommand('removeFormat', false, null); }));
      document.body.appendChild(fbar);
    }
    function positionFormatBar() {
      var s = getSelection();
      if (!document.body.classList.contains('text-edit-mode') || !s || !s.rangeCount || s.isCollapsed || !currentEditable()) {
        if (fbar) fbar.style.display = 'none'; return;
      }
      if (!fbar) buildFormatBar();
      var r = s.getRangeAt(0).getBoundingClientRect();
      fbar.style.display = 'flex';
      var bw = fbar.offsetWidth || 320, bh = fbar.offsetHeight || 40;
      var left = Math.max(8, Math.min(window.innerWidth - bw - 8, r.left + r.width / 2 - bw / 2));
      var top = r.top - bh - 10; if (top < 8) top = r.bottom + 10;
      fbar.style.left = left + 'px'; fbar.style.top = top + 'px';
    }
    document.addEventListener('selectionchange', function () { setTimeout(positionFormatBar, 0); });
    document.addEventListener('scroll', function () { if (fbar && fbar.style.display !== 'none') positionFormatBar(); }, true);
    // keyboard shortcuts save too (⌘/Ctrl B/I/U fire execCommand natively)
    document.addEventListener('keyup', function (e) {
      if (document.body.classList.contains('text-edit-mode') && (e.metaKey || e.ctrlKey) && /^[biu]$/i.test(e.key)) {
        var ed = currentEditable(); if (ed) scheduleSave(ed);
      }
    });

    // Click-through focus: on overlay-heavy slides (reference renders, layered templates)
    // a click can land on a covering element instead of the text. In text-edit mode, if an
    // editable element sits UNDER the pointer, focus it and drop the caret at the click.
    document.addEventListener('mousedown', function (e) {
      if (!document.body.classList.contains('text-edit-mode')) return;
      var top = document.elementFromPoint(e.clientX, e.clientY);
      // UI chrome (format bar, toolbar, menus, panels) is appended to <body>, OUTSIDE any
      // .slide, and often sits ON TOP of slide text. A click on that chrome must NOT be
      // redirected into the editable behind it — doing so stole the caret/selection from
      // under the format bar and dropped edit context. Let chrome handle its own click.
      if (!top || !top.closest || !top.closest('.slide')) return;
      if (top.closest('[data-te][contenteditable="true"]')) return;  // native works
      var stack = document.elementsFromPoint(e.clientX, e.clientY);
      for (var i = 0; i < stack.length; i++) {
        var ed = stack[i].closest && stack[i].closest('[data-te][contenteditable="true"]');
        if (ed) {
          e.preventDefault(); ed.focus();
          try {
            var r = document.caretRangeFromPoint && document.caretRangeFromPoint(e.clientX, e.clientY);
            if (r && ed.contains(r.startContainer)) { var s = getSelection(); s.removeAllRanges(); s.addRange(r); }
          } catch (x) {}
          break;
        }
      }
    }, true);

    function hasChanges() { return Object.keys(edits).length > 0; }
    function bySlide(a, b) { return slideIndexOf(edits[a].slide_uuid) - slideIndexOf(edits[b].slide_uuid); }
    function payloadText() {
      var ks = Object.keys(edits); if (!ks.length) return '';
      var blk = ks.filter(function (k) { return edits[k].kind !== 'ref'; }).sort(bySlide);
      var ref = ks.filter(function (k) { return edits[k].kind === 'ref'; }).sort(bySlide);
      var out = '';
      if (blk.length) {
        out += 'DIRECT TEXT EDITS — apply VERBATIM to plan.json: set each block\'s text to "new" (authored slides).\n';
        out += '# ' + blk.length + ' block(s) · plan_revision ' + PLAN_REV + '\n\n';
        blk.forEach(function (k) {
          var e = edits[k], i = slideIndexOf(e.slide_uuid);
          out += '- [' + (i >= 0 ? 's' + (i + 1) : '—') + ' · ' + (e.slide_topic || '') + '] block_uuid=' + k.slice(2) + '\n';
          out += '  old: "' + e.old + '"\n  new: "' + e.new + '"\n';
        });
      }
      if (ref.length) {
        if (out) out += '\n';
        out += 'REFERENCE SLIDE TEXT EDITS — these ADAPT an approved/verbatim slide (it now diverges from the approved master; apply as an adapted deck-local copy, do NOT change the library).\n';
        out += '# ' + ref.length + ' edit(s) on approved slides · plan_revision ' + PLAN_REV + '\n\n';
        ref.forEach(function (k) {
          var e = edits[k], i = slideIndexOf(e.slide_uuid);
          out += '- [' + (i >= 0 ? 's' + (i + 1) : '—') + '] ref_id=' + e.ref_id + ' (' + e.variant + ' variant)\n';
          out += '  old: "' + e.old + '"\n  new: "' + e.new + '"\n';
        });
      }
      return out;
    }
    window.__TEXTEDITS_API__ = { hasChanges: hasChanges, payloadText: payloadText };

    // stamp keys + baseline BEFORE applying persisted edits, so "old" is the true original.
    // Seed lastSaved with the baked innerHTML so an unchanged blur never triggers a save.
    editableEls().forEach(function (el) {
      var k = el.dataset.te;
      if (!(k in baseline)) baseline[k] = norm(el.innerText);
      if (!(k in lastSaved)) lastSaved[k] = el.innerHTML;
    });
    load();
    applyEdits();
    refreshCopyState();
  })();
})();

/* Template Library button (review only): decode the embedded base64 library and open it
   in a new tab via a blob URL. No-op if the button/payload are absent (presentation.html
   or a build made with --no-library). */
(function () {
  var btn = document.getElementById('tpl-lib-btn');
  var src = document.getElementById('tpl-lib-b64');
  if (!btn || !src) { if (btn) btn.style.display = 'none'; return; }
  var url = null;
  btn.addEventListener('click', function () {
    try {
      if (!url) {
        var bytes = Uint8Array.from(atob(src.textContent.trim()), function (c) { return c.charCodeAt(0); });
        var html = new TextDecoder('utf-8').decode(bytes);
        url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
      }
      window.open(url, '_blank');
    } catch (e) { alert('Could not open the template library: ' + e); }
  });
})();

  /* ---- TOC click-to-jump (owner feature 2026-08-14) ----------------------------------
     build.py stamps agenda/TOC entries with data-jump="<slide uuid>". Clicking one
     smooth-scrolls to that slide. Inert while editing/annotating so pins and text
     edits never hijack. */
  document.addEventListener('click', function (e) {
    var j = e.target.closest && e.target.closest('[data-jump]');
    if (!j) return;
    if (document.body.classList.contains('edit-mode') ||
        document.body.classList.contains('text-edit-mode') ||
        /\bmode-\w+/.test(document.body.className)) return;
    var t = document.querySelector('section.slide[data-slide="' + j.getAttribute('data-jump') + '"]');
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth' }); }
  });

