"""
SmartBuild Deck v5 — open_deck.py
Open a built deck in Chrome for review. Standard step after BUILD and after SWEEP.

    python engine/open_deck.py --out out                 # opens review.html (default)
    python engine/open_deck.py --out out --presentation   # opens the clean client deck

Tries Chrome explicitly (so review chrome/pins work as intended), falls back to the
default browser. Cross-platform: Windows / macOS / Linux.
"""
import argparse, os, sys, shutil, subprocess, webbrowser, time


def find_chrome():
    # explicit name on PATH
    for name in ("chrome", "google-chrome", "google-chrome-stable", "chromium"):
        p = shutil.which(name)
        if p:
            return [p]
    if sys.platform.startswith("win"):
        for base in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            cand = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            if base and os.path.exists(cand):
                return [cand]
    elif sys.platform == "darwin":
        cand = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(cand):
            return [cand]
    return None


def refocus_macos(path, url):
    """Owner directive 2026-08-13: never stack deck tabs. If a Chrome tab already
    shows THIS deck file (any ?v=), reload it in place with the fresh URL and bring
    that tab/window to the front - across Spaces and displays. Returns True when an
    existing tab was reused; False means the caller should open normally. Only
    called when Chrome is already running (never launches it)."""
    if sys.platform != "darwin":
        return False
    probe = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
    if probe.returncode != 0:
        return False
    # NOTE: Chrome's "set index of w to 1" switches the tab but does NOT reliably
    # raise the window (minimized windows and other Spaces stay hidden). After
    # activating, raise the window for real via System Events AXRaise, keyed off
    # the active tab's title (2026-08-13: reviewer reported the deck not surfacing).
    script = """
    tell application "Google Chrome"
      repeat with w in windows
        set tabIdx to 0
        repeat with t in tabs of w
          set tabIdx to tabIdx + 1
          if URL of t contains "%s" then
            set URL of t to "%s"
            set active tab index of w to tabIdx
            try
              if minimized of w then set minimized of w to false
            end try
            set index of w to 1
            activate
            -- BONUS raise via System Events: only works if the calling terminal has
            -- Accessibility permission; harmless (fully swallowed) when it does not.
            try
              set tabTitle to title of active tab of w
              tell application "System Events" to tell process "Google Chrome"
                perform action "AXRaise" of (first window whose title contains tabTitle)
                set frontmost to true
              end tell
            end try
            return "refocused"
          end if
        end repeat
      end repeat
    end tell
    return "none"
    """ % (path.replace("\\", "/"), url)
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        return "refocused" in (r.stdout or "")
    except Exception:
        return False


def ensure_edit_server(out_dir, plan_path):
    """Owner directive 2026-08-13: the review chrome's editor button must ALWAYS work.
    Ensure a live edit server for THIS deck exists whenever the deck is surfaced:
    reuse one already answering /whoami for this plan; otherwise spawn edit_server.py
    detached in the background (survives this process; localhost only; no browser tab
    is opened - the deck's editor button connects to it on demand)."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    try:
        from edit_server import pick_port, server_identity, write_edit_command, PORT_TRIES
    except Exception as e:
        print("  [warn] edit server unavailable (%s) - the editor button will not work" % e)
        return None
    plan_abs = os.path.abspath(plan_path)
    if not os.path.exists(plan_abs):
        return None
    skill_root = os.path.dirname(here)
    write_edit_command(plan_abs, out_dir, skill_root)   # keep the double-click launcher fresh
    for p in range(8770, 8770 + PORT_TRIES):
        who = server_identity("127.0.0.1", p)
        if who and who.get("app") == "sbdeck-edit-server" and who.get("plan_path") == plan_abs:
            return p
    port = pick_port("127.0.0.1", 8770)
    devnull = open(os.devnull, "w")
    subprocess.Popen([sys.executable, os.path.join(here, "edit_server.py"),
                      "--skill-path", skill_root, "--out", os.path.abspath(out_dir),
                      "--plan", plan_abs, "--port", str(port)],
                     stdout=devnull, stderr=devnull, start_new_session=True)
    for _ in range(20):
        time.sleep(0.2)
        if server_identity("127.0.0.1", port):
            return port
    return None


def open_edit_mode(args):
    """Live-edit mode: start the local edit server (autosaves text edits to disk) and open
    the deck at its localhost URL. A plain file:// page can't write to disk; this can.

    Robustness contract (the editor must come up correctly EVERY time):
      - a live editor for the SAME deck on the preferred port is reused, not duplicated;
      - a busy port (stale server, another deck's editor) is skipped for the next free one;
      - the EDITABLE localhost tab is opened directly (the file view is the reference copy);
      - the double-click "Edit Deck.command" launcher is (re)generated next to plan.json."""
    if not args.plan:
        print("--edit requires --plan <deck>/plan.json"); sys.exit(1)
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    from edit_server import pick_port, server_identity, write_edit_command, PORT_BASE, PORT_TRIES

    review = os.path.abspath(os.path.join(args.out, "review.html"))
    plan_abs = os.path.abspath(args.plan)
    skill_root = os.path.dirname(here)
    if not os.path.exists(review):
        print("Not found: " + review + " — build the deck first."); sys.exit(1)

    launcher = write_edit_command(plan_abs, args.out, skill_root)

    # Reuse a live editor already serving THIS deck (any port in the window); otherwise
    # bind the first free port. Never crash on "Address already in use".
    srv, port = None, None
    for p in range(args.port, args.port + PORT_TRIES):
        who = server_identity("127.0.0.1", p)
        if who and who.get("app") == "sbdeck-edit-server" and who.get("plan_path") == plan_abs:
            port = p
            print("Reusing the editor already running for this deck on port %d." % p)
            break
    if port is None:
        port = pick_port("127.0.0.1", args.port)
        srv = subprocess.Popen([sys.executable, os.path.join(here, "edit_server.py"),
                                "--skill-path", skill_root, "--out", os.path.abspath(args.out),
                                "--plan", plan_abs, "--port", str(port)])
        for _ in range(20):  # wait until it answers (max ~4s), not a blind sleep
            time.sleep(0.2)
            if server_identity("127.0.0.1", port):
                break

    # Open the EDITABLE version front and centre — this is the editor the user asked for.
    # The file:// copy stays available as the read-only reference (SKILL.md two-tab flow).
    edit_url = "http://127.0.0.1:%d/review.html" % port
    file_url = "file:///" + review.replace("\\", "/") + "?v=" + str(int(time.time()))
    chrome = find_chrome()
    if chrome:
        try:
            subprocess.Popen(chrome + (["--new-window"] if args.new_window else []) + [edit_url])
        except Exception:
            webbrowser.open(edit_url)
    else:
        webbrowser.open(edit_url)
    print("EDIT MODE ready.\n  Editable version (open now): %s\n  File view (read-only reference): %s"
          % (edit_url, file_url)
          + ("\n  Double-click launcher: %s" % launcher if launcher else "")
          + "\n  Text edits autosave to disk. Close this window (Ctrl+C) to stop the edit server.")
    if srv is None:
        return  # reused an existing server; nothing to babysit
    try:
        srv.wait()
    except KeyboardInterrupt:
        srv.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="build output dir")
    ap.add_argument("--presentation", action="store_true", help="open presentation.html instead of review.html")
    ap.add_argument("--new-window", dest="new_window", action="store_true", default=True,
                    help="open in a fresh Chrome window so it always surfaces (default)")
    ap.add_argument("--reuse-window", dest="new_window", action="store_false",
                    help="reuse the current window (opens a background tab; may not surface)")
    ap.add_argument("--edit", action="store_true",
                    help="live-edit mode: serve the deck on localhost so direct-text edits autosave to disk")
    ap.add_argument("--plan", help="deck plan.json (source of truth) — required with --edit")
    ap.add_argument("--port", type=int, default=8770, help="localhost port for --edit")
    args = ap.parse_args()

    if args.edit:
        return open_edit_mode(args)

    fname = "presentation.html" if args.presentation else "review.html"
    path = os.path.abspath(os.path.join(args.out, fname))
    if not os.path.exists(path):
        print("Not found: " + path + " — build first.")
        sys.exit(1)
    # cache-buster: relaunching the same file:// URL only refocuses a stale tab
    # (Chrome won't reload), so a fresh ?v= forces the updated deck to render.
    url = "file:///" + path.replace("\\", "/") + "?v=" + str(int(time.time()))

    # The editor button in the deck probes localhost for a live edit server; keep one
    # running for this deck at all times (reuse-first, detached spawn otherwise).
    plan_guess = args.plan or os.path.join(os.path.dirname(os.path.abspath(args.out)), "plan.json")
    eport = ensure_edit_server(args.out, plan_guess)
    if eport:
        print("Edit server live on port %d - the deck's editor button is active." % eport)

    # Reuse-first (owner directive): an existing tab showing this deck is reloaded
    # in place and refocused - a new window opens ONLY when no such tab exists.
    if refocus_macos(path, url):
        print("Refocused the existing %s tab in Chrome (reloaded in place):\n  %s" % (fname, url))
        return

    chrome = find_chrome()
    if chrome:
        try:
            # --new-window (default) forces a fresh top-level window so the deck
            # actually surfaces; without it Chrome opens a background tab in the
            # existing window and the reviewer never sees it.
            flags = ["--new-window"] if args.new_window else []
            subprocess.Popen(chrome + flags + [url])
            print("Opened %s in Chrome%s:\n  %s" % (fname, " (new window)" if args.new_window else "", url))
            return
        except Exception as e:
            print("Chrome launch failed (%s); falling back to default browser." % e)
    webbrowser.open(url)
    print("Opened %s in your default browser:\n  %s" % (fname, url))


if __name__ == "__main__":
    main()
